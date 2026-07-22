import readline from 'node:readline'
import fs from 'node:fs/promises'
import path from 'node:path'
import { WechatyBuilder } from 'wechaty'
import { FileBox } from 'file-box'
import {
  buildMessageIdentityPayload,
  buildMediaFilePath,
  buildRoomMemberPayload,
  detectMessageMediaType,
  downloadStickerMediaWithFallback,
  extractQuotedMessageFromRawPayload,
  findContactById,
  findRoomById,
  getWechat4uRuntime,
  isWechat4uBot,
  memberPayloadMatchesQuery,
  resolveMessageRawPayload,
  resolveContactDisplayName,
  resolveContactWechatId,
  sendText as sendTextCore,
} from './wechaty-sidecar-core.mjs'
import {
  createSessionBackedWechaty,
  createSessionPreservingShutdown,
  registerSessionPreservingSignalHandlers,
} from './wechaty-sidecar-lifecycle.mjs'

const config = JSON.parse(process.argv[2] || '{}')

const state = {
  bot: null,
  memory: null,
  self: null,
}

function emit(type, payload = {}) {
  process.stdout.write(JSON.stringify({ type, ...payload }) + '\n')
}

async function listRooms() {
  const rooms = await state.bot.Room.findAll()
  const payload = []
  for (const room of rooms) {
    payload.push({
      id: room.id,
      name: await room.topic(),
    })
  }
  emit('rooms', { rooms: payload })
}

async function contactRawPayload(contact) {
  try {
    if (contact?.id && typeof state.bot?.puppet?.contactRawPayload === 'function') {
      return await state.bot.puppet.contactRawPayload(contact.id)
    }
  } catch {}
  return null
}

async function contactPayload(contact, room = null, rawPayload = null) {
  let roomAlias = ''
  try { roomAlias = await room?.alias?.(contact) || '' } catch {}
  return {
    id: contact.id,
    name: await resolveContactDisplayName(contact, room, rawPayload),
    wechat_id: await resolveContactWechatId(contact, rawPayload),
    room_alias: roomAlias,
  }
}

async function listRoomMembers(command) {
  const room = await findRoom(command.room_id)
  if (!room) throw new Error(`room not found: ${command.room_id}`)
  if (typeof room.sync === 'function') {
    await room.sync().catch(() => {})
  }
  const contacts = await room.memberAll?.() || []
  const query = String(command.query || '').trim()
  const members = []
  for (const contact of contacts) {
    let payload = await buildRoomMemberPayload(contact, room)
    if (query && !memberPayloadMatchesQuery(payload, query)) {
      const rawPayload = await contactRawPayload(contact)
      if (rawPayload) {
        payload = await buildRoomMemberPayload(contact, room, rawPayload)
      }
    }
    members.push(payload)
  }
  emit('room_members', {
    room_id: command.room_id,
    request_id: command.request_id || '',
    members,
  })
}

async function downloadMessageMedia(message, roomId, mediaType, rawContent = '') {
  if (mediaType === 'text') return ''
  if (mediaType === 'sticker') {
    const target = buildMediaFilePath(
      config.media_dir || config.memory_path || '.',
      roomId,
      message.id || String(Date.now()),
      '',
      mediaType,
    )
    const downloaded = await downloadStickerMediaWithFallback(
      rawContent || message.text?.() || '',
      target,
      async () => {
        if (!message?.toFileBox) return
        const fileBox = await message.toFileBox()
        await fs.mkdir(path.dirname(target), { recursive: true })
        await fileBox.toFile(target, true)
      },
    )
    return downloaded ? target : ''
  }
  if (!message?.toFileBox) return ''
  const fileBox = await message.toFileBox()
  const target = buildMediaFilePath(
    config.media_dir || config.memory_path || '.',
    roomId,
    message.id || String(Date.now()),
    fileBox?.name || '',
    mediaType,
  )
  await fs.mkdir(path.dirname(target), { recursive: true })
  await fileBox.toFile(target, true)
  return target
}

async function handleMessage(message) {
  const room = message.room()
  if (!room) return

  const talker = message.talker ? message.talker() : message.from()
  const mentions = await message.mentionList().catch(() => [])
  const self = state.self
  const roomName = await room.topic()
  const rawPayloadResult = await resolveMessageRawPayload(state.bot, message.id)
  const rawPayload = rawPayloadResult.payload
  const talkerInfo = await contactPayload(talker, room, rawPayload)
  const selfInfo = self ? await contactPayload(self) : { id: '', name: '' }
  const mediaType = detectMessageMediaType(message)
  let filePath = ''
  if (mediaType !== 'text') {
    try {
      filePath = await downloadMessageMedia(message, room.id, mediaType, rawPayload?.Content || '')
    } catch (error) {
      emit('error', {
        message: `failed to download ${mediaType} message ${message.id || ''}: ${error.message || String(error)}`,
      })
    }
  }
  let quoteInfo = {
    is_quote_self: false,
    quote: {},
    forward: {},
    raw_app_type: '',
    quote_diagnostics: { parse_status: 'not_attempted' },
  }
  if (rawPayload) {
    try {
      quoteInfo = await extractQuotedMessageFromRawPayload(rawPayload, selfInfo.id)
    } catch {
      quoteInfo.quote_diagnostics = { parse_status: 'unexpected_error' }
    }
  }
  const quoteDiagnostics = {
    ...rawPayloadResult.diagnostics,
    ...quoteInfo.quote_diagnostics,
  }

  emit('message', {
    message_id: message.id,
    timestamp: Math.floor(Date.now() / 1000),
    room_id: room.id,
    room_name: roomName,
    sender_id: talkerInfo.id,
    sender_name: talkerInfo.name,
    self_id: selfInfo.id,
    self_name: selfInfo.name,
    text: message.text(),
    message_type: mediaType,
    file_path: filePath,
    is_at: self ? mentions.some(contact => contact.id === self.id) : false,
    at_list: mentions.map(contact => contact.id),
    is_quote_self: quoteInfo.is_quote_self,
    quote: quoteInfo.quote,
    forward: quoteInfo.forward,
    raw_app_type: quoteInfo.raw_app_type,
    quote_diagnostics: quoteDiagnostics,
    my_msg: self ? talkerInfo.id === self.id : false,
    ...buildMessageIdentityPayload({
      roomId: room.id,
      roomName,
      senderInfo: talkerInfo,
      selfInfo,
    }),
  })
}

async function start() {
  if (state.bot) return
  const { bot, memory } = await createSessionBackedWechaty({
    WechatyBuilder,
    config,
  })
  state.bot = bot
  state.memory = memory

  state.bot
    .on('scan', (qrcode, status) => {
      emit('qr', {
        status,
        qrcode,
        url: `https://wechaty.js.org/qrcode/${encodeURIComponent(qrcode)}`,
      })
    })
    .on('login', async user => {
      state.self = user
      emit('status', { status: 'logged_in', self_id: user.id, self_name: user.name() })
      await listRooms()
      emit('status', { status: 'connected', self_id: user.id, self_name: user.name() })
    })
    .on('logout', user => {
      emit('status', { status: 'idle', self_id: user.id, self_name: user.name() })
    })
    .on('message', handleMessage)
    .on('error', error => {
      emit('error', { message: error.message || String(error) })
    })

  emit('status', { status: 'starting' })
  await state.bot.start()
}

async function findRoom(roomId) {
  return findRoomById(state.bot, roomId)
}

async function sendText(command) {
  await sendTextCore(command, {
    emit,
    findRoom,
    findContact: contactId => findContactById(state.bot, contactId),
    getWechat4u: () => getWechat4uRuntime(state.bot),
    isWechat4u: () => isWechat4uBot(state.bot),
    logWarning: message => console.error(message),
  })
}

async function sendFile(command) {
  const room = await findRoom(command.room_id)
  if (!room) throw new Error(`room not found: ${command.room_id}`)
  await room.say(FileBox.fromFile(command.path || command.file_path))
  emit('send_result', { ok: true, command: 'send_file', room_id: command.room_id })
}

async function handleCommand(command) {
  switch (command.type) {
    case 'start':
      await start()
      break
    case 'stop':
      await shutdown('stop')
      break
    case 'list_rooms':
      await listRooms()
      break
    case 'list_room_members':
      await listRoomMembers(command)
      break
    case 'send_text':
      await sendText(command)
      break
    case 'send_file':
    case 'send_image':
    case 'send_audio':
      await sendFile(command)
      break
    default:
      emit('error', { message: `unknown command: ${command.type}` })
  }
}

const rl = readline.createInterface({ input: process.stdin })
const shutdown = createSessionPreservingShutdown({
  closeInput: () => rl.close(),
  getMemory: () => state.memory,
  reportError: (error, reason) => emit('error', {
    message: `failed to save WeChat session during ${reason}: ${error.message || String(error)}`,
  }),
  exitProcess: code => process.exit(code),
})
registerSessionPreservingSignalHandlers({ processRef: process, shutdown })

rl.on('line', line => {
  Promise.resolve()
    .then(() => handleCommand(JSON.parse(line)))
    .catch(error => emit('error', { message: error.message || String(error) }))
})

start().catch(error => emit('error', { message: error.message || String(error) }))
