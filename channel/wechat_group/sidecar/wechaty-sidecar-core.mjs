import path from 'node:path'
import fs from 'node:fs/promises'
import xml2js from 'xml2js'

const { parseStringPromise } = xml2js

const APP_MESSAGE_TYPE_REFER = 57
const MESSAGE_TYPE_NAMES = {
  1: 'file',
  2: 'audio',
  5: 'sticker',
  6: 'image',
  7: 'text',
  15: 'video',
}
const DEFAULT_ALIAS_SYNC_COOLDOWN_MINUTES = 1
const aliasSyncCooldownByRoom = new Map()

function stringValue(value = '') {
  if (value === null || value === undefined) return ''
  return String(value)
}

function decodeXmlAttribute(value = '') {
  let text = String(value || '')
  for (let i = 0; i < 2; i++) {
    text = text
      .replace(/&amp;/giu, '&')
      .replace(/&lt;/giu, '<')
      .replace(/&gt;/giu, '>')
      .replace(/&quot;/giu, '"')
      .replace(/&apos;/giu, "'")
  }
  return text
}

function emptyQuoteResult(quoteDiagnostics = {}) {
  return {
    is_quote_self: false,
    quote: {},
    forward: {},
    raw_app_type: '',
    quote_diagnostics: {
      parse_status: 'not_attempted',
      xml_candidate_count: 0,
      parsed_candidate_count: 0,
      ...quoteDiagnostics,
    },
  }
}

function normalizeRawPayloadError(error) {
  const message = stringValue(error?.message || error).toLowerCase()
  if (/id not found|no rawpayload/iu.test(message)) return 'id_not_found'
  if (/not a function/iu.test(message)) return 'method_unavailable'
  const name = stringValue(error?.name).trim().toLowerCase()
  if (['error', 'typeerror', 'rangeerror'].includes(name)) return name
  return 'unknown_error'
}

function rawPayloadType(value) {
  const text = stringValue(value).trim()
  return /^-?\d{1,12}$/u.test(text) ? text : ''
}

function rawPayloadShape(payload = {}) {
  const msgType = payload?.MsgType
  const appMsgType = payload?.AppMsgType
  return {
    has_content: typeof payload?.Content === 'string' && payload.Content.length > 0,
    has_original_content: typeof payload?.OriginalContent === 'string' && payload.OriginalContent.length > 0,
    msg_type: msgType === null || msgType === undefined ? '' : rawPayloadType(msgType),
    app_msg_type: appMsgType === null || appMsgType === undefined ? '' : rawPayloadType(appMsgType),
  }
}

export async function resolveMessageRawPayload(bot, messageId) {
  const id = stringValue(messageId).trim()
  const diagnostics = {
    status: 'missing',
    source: '',
    method_available: false,
    cache_available: false,
    method_error: '',
    cache_error: '',
    has_content: false,
    has_original_content: false,
    msg_type: '',
    app_msg_type: '',
  }
  if (!id) {
    diagnostics.method_error = 'message_id_missing'
    return { payload: null, diagnostics }
  }

  let puppet = null
  try {
    puppet = bot?.puppet || bot?.__puppet || null
  } catch (error) {
    diagnostics.method_error = normalizeRawPayloadError(error)
    puppet = bot?.__puppet || null
  }
  const resolver = puppet?.messageRawPayload
  diagnostics.method_available = typeof resolver === 'function'
  if (diagnostics.method_available) {
    try {
      const payload = await resolver.call(puppet, id)
      if (payload && typeof payload === 'object') {
        return {
          payload,
          diagnostics: {
            ...diagnostics,
            status: 'resolved',
            source: 'puppet_method',
            ...rawPayloadShape(payload),
          },
        }
      }
      diagnostics.method_error = 'empty_payload'
    } catch (error) {
      diagnostics.method_error = normalizeRawPayloadError(error)
    }
  }

  const cache = isWechat4uBot({ puppet }) ? puppet?.cacheMessageRawPayload : null
  diagnostics.cache_available = typeof cache?.get === 'function'
  if (diagnostics.cache_available) {
    try {
      const payload = cache.get(id)
      if (payload && typeof payload === 'object') {
        return {
          payload,
          diagnostics: {
            ...diagnostics,
            status: 'resolved',
            source: 'puppet_cache',
            ...rawPayloadShape(payload),
          },
        }
      }
      diagnostics.cache_error = 'id_not_found'
    } catch (error) {
      diagnostics.cache_error = normalizeRawPayloadError(error)
    }
  }
  return { payload: null, diagnostics }
}

function decodeXmlEntitiesOnce(value = '') {
  return String(value || '')
    .replace(/&amp;/giu, '&')
    .replace(/&lt;/giu, '<')
    .replace(/&gt;/giu, '>')
    .replace(/&quot;/giu, '"')
    .replace(/&apos;/giu, "'")
}

function buildRawMessageXmlCandidates(rawPayload = {}) {
  const fields = ['Content', 'OriginalContent', 'OriContent', 'MMActualContent']
  const candidates = []
  const seen = new Set()
  for (const field of fields) {
    let content = stringValue(rawPayload?.[field]).trim()
    for (let decodePass = 0; content && decodePass < 3; decodePass += 1) {
      const start = content.search(/<msg(?:\s|>)/iu)
      if (start >= 0) {
        const end = content.lastIndexOf('</msg>')
        const xml = content.slice(start, end >= start ? end + '</msg>'.length : undefined).trim()
        if (xml && !seen.has(xml)) {
          seen.add(xml)
          candidates.push(xml)
        }
      }
      if (decodePass < 2) content = decodeXmlEntitiesOnce(content)
    }
  }
  return candidates
}

function firstValue(value) {
  return Array.isArray(value) ? value[0] : value
}

async function parseRawAppMessage(rawPayload = {}) {
  const candidates = buildRawMessageXmlCandidates(rawPayload)
  let fallback = null
  let parsedCandidateCount = 0
  for (const content of candidates) {
    try {
      const parsed = await parseStringPromise(content, { explicitArray: false })
      parsedCandidateCount += 1
      const appmsg = firstValue(parsed?.msg?.appmsg)
      if (!appmsg || typeof appmsg !== 'object') continue
      if (!fallback) fallback = appmsg
      const appType = Number(firstValue(appmsg?.type))
      const refer = firstValue(appmsg?.refermsg)
      if (appType !== APP_MESSAGE_TYPE_REFER || (refer && typeof refer === 'object')) {
        return { appmsg, candidateCount: candidates.length, parsedCandidateCount }
      }
    } catch {}
  }
  return { appmsg: fallback, candidateCount: candidates.length, parsedCandidateCount }
}

function buildForwardPreview(appmsg = {}) {
  const type = Number(appmsg?.type || 0)
  const title = stringValue(appmsg?.title)
  const description = stringValue(appmsg?.des)
  const recordItem = stringValue(appmsg?.recorditem)
  const source = stringValue(appmsg?.sourcedisplayname || appmsg?.sourceusername || appmsg?.fromusername)
  const looksLikeForward = Boolean(
    recordItem ||
    type === 19 ||
    /聊天记录|转发/iu.test(title) ||
    /聊天记录|转发/iu.test(description),
  )
  if (!looksLikeForward) return {}
  const countMatches = [
    ...title.matchAll(/(\d+)\s*(条|段|个)/giu),
    ...description.matchAll(/(\d+)\s*(条|段|个)/giu),
  ]
  return {
    title: title.slice(0, 120),
    description: description.slice(0, 240),
    source: source.slice(0, 120),
    record_count_hint: countMatches.length ? Number(countMatches[0][1]) || 0 : 0,
    record_item: recordItem.slice(0, 2000),
  }
}

export function detectMessageMediaType(message) {
  let rawType = ''
  try {
    rawType = message?.type?.()
  } catch {
    rawType = ''
  }
  if (typeof rawType === 'number') {
    return MESSAGE_TYPE_NAMES[rawType] || 'text'
  }
  const normalized = String(rawType || '').trim().toLowerCase()
  if (normalized.includes('emoticon') || normalized.includes('sticker')) return 'sticker'
  if (normalized.includes('image')) return 'image'
  if (normalized.includes('audio') || normalized.includes('voice')) return 'audio'
  if (normalized.includes('video')) return 'video'
  if (normalized.includes('attachment') || normalized.includes('file')) return 'file'
  return 'text'
}

export function sanitizeMediaFilePart(value = '') {
  const cleaned = String(value || '')
    .replace(/[\\/]+/g, '_')
    .replace(/\.\.+/g, '')
    .replace(/[^\w@.-]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 120)
  return cleaned || 'unknown'
}

function mediaExtension(fileName = '', mediaType = '') {
  if (mediaType === 'sticker') return 'gif'
  const ext = path.extname(String(fileName || '')).toLowerCase().replace('.', '')
  if (ext) return ext
  if (mediaType === 'image') return 'jpg'
  if (mediaType === 'audio') return 'mp3'
  if (mediaType === 'video') return 'mp4'
  return 'dat'
}

export function buildMediaFilePath(mediaDir, roomId, messageId, fileName = '', mediaType = 'image') {
  const dir = path.join(String(mediaDir || ''), sanitizeMediaFilePart(roomId))
  const baseName = sanitizeMediaFilePart(messageId)
  const ext = mediaExtension(fileName, mediaType)
  return path.join(dir, `${baseName}.${ext}`)
}

export function extractStickerMediaUrl(rawText = '') {
  const text = String(rawText || '')
  for (const attr of ['cdnurl', 'externurl', 'encrypturl', 'thumburl']) {
    const match = text.match(new RegExp(`${attr}\\s*=\\s*["']([^"']+)`, 'iu'))
    if (match?.[1]) return decodeXmlAttribute(match[1])
  }
  return ''
}

export async function downloadStickerMediaFromText(rawText = '', targetPath = '', deps = {}) {
  const url = extractStickerMediaUrl(rawText)
  if (!url || !targetPath) return false
  const fetchFn = deps.fetch || globalThis.fetch
  if (typeof fetchFn !== 'function') return false
  const mkdir = deps.mkdir || fs.mkdir
  const writeFile = deps.writeFile || fs.writeFile
  const response = await fetchFn(url, {
    headers: { 'User-Agent': 'Mozilla/5.0' },
  })
  if (!response?.ok) return false
  const arrayBuffer = await response.arrayBuffer()
  const buffer = Buffer.from(arrayBuffer)
  if (!buffer.length) return false
  await mkdir(path.dirname(targetPath), { recursive: true })
  await writeFile(targetPath, buffer)
  return true
}

export async function downloadStickerMediaWithFallback(
  rawText = '',
  targetPath = '',
  primaryDownload = null,
  deps = {},
) {
  if (!targetPath) return false
  if (typeof primaryDownload === 'function') {
    try {
      await primaryDownload(targetPath)
    } catch {}
  }

  const stat = deps.stat || fs.stat
  try {
    const current = await stat(targetPath)
    if (Number(current?.size || 0) > 0) return true
  } catch {}

  try {
    return await downloadStickerMediaFromText(rawText, targetPath, deps)
  } catch {
    return false
  }
}

export async function extractQuotedMessageFromRawPayload(rawPayload = {}, selfId = '') {
  const parseResult = await parseRawAppMessage(rawPayload)
  const appmsg = parseResult.appmsg
  const quoteDiagnostics = {
    parse_status: parseResult.candidateCount ? 'appmsg_missing' : 'xml_candidate_missing',
    xml_candidate_count: parseResult.candidateCount,
    parsed_candidate_count: parseResult.parsedCandidateCount,
  }
  if (!appmsg) return emptyQuoteResult(quoteDiagnostics)
  const appType = stringValue(firstValue(appmsg?.type))
  let quote = {}
  let isQuoteSelf = false
  const refer = firstValue(appmsg?.refermsg)
  if (Number(appType) === APP_MESSAGE_TYPE_REFER && refer && typeof refer === 'object') {
    quote = {
      sender_id: stringValue(firstValue(refer.fromusr)),
      sender_name: stringValue(firstValue(refer.displayname)),
      message_id: stringValue(firstValue(refer.svrid)),
      type: stringValue(firstValue(refer.type)),
      content: stringValue(firstValue(refer.content)),
    }
    isQuoteSelf = Boolean(selfId && quote.sender_id === selfId)
  }
  quoteDiagnostics.parse_status = Number(appType) !== APP_MESSAGE_TYPE_REFER
    ? 'not_quote'
    : quote.message_id
      ? 'quote_parsed'
      : 'refermsg_missing'
  return {
    is_quote_self: isQuoteSelf,
    quote,
    forward: buildForwardPreview(appmsg),
    raw_app_type: appType,
    quote_diagnostics: quoteDiagnostics,
  }
}

export async function findRoomById(bot, roomId) {
  if (!bot) throw new Error('bot not started')
  const room = await bot.Room.find({ id: roomId })
  return room
}

export async function findContactById(bot, contactId) {
  if (!bot) throw new Error('bot not started')
  return bot.Contact.find({ id: contactId })
}

export async function resolveMentionContacts(room, mentionIds, findContact) {
  const mentions = []
  for (const contactId of mentionIds || []) {
    const wanted = String(contactId || '').trim()
    if (!wanted) continue
    let contact = null
    try {
      const members = await room.memberAll?.()
      contact = (members || []).find(item => String(item?.id || '').trim() === wanted) || null
    } catch {}
    if (contact) {
      mentions.push(contact)
      continue
    }
    if (!contact) {
      contact = await findContact(wanted).catch(() => null)
    }
    if (!contact) continue
    const inRoom = await room.has?.(contact).catch(() => false)
    if (inRoom) mentions.push(contact)
  }
  return mentions
}

function cleanMentionName(value = '') {
  return String(value || '')
    .replace(/<br\s*\/?>/giu, ' ')
    .replace(/<[^>]+>/gu, '')
    .replace(/&nbsp;/giu, ' ')
    .replace(/&amp;/giu, '&')
    .replace(/&lt;/giu, '<')
    .replace(/&gt;/giu, '>')
    .replace(/^[@＠]+/u, '')
    .replace(/[\r\n]+/g, ' ')
    .replace(/\s{2,}/g, ' ')
    .trim()
    .slice(0, 40)
}

function stripLeadingMentionText(text = '') {
  let value = String(text || '').trim()
  for (let i = 0; i < 5; i++) {
    const next = value.replace(/^[@＠][^\s\u2005\u2006\u2007\u2008\u2009\u200a，,：:、]{0,40}[\s\u2005\u2006\u2007\u2008\u2009\u200a，,：:、]*/u, '').trim()
    if (next === value) break
    value = next
  }
  return value || String(text || '').trim()
}

function looksLikeRawWechatInternalId(value = '') {
  const text = String(value || '').trim().replace(/^[@\uFF20]+/u, '')
  return /^[0-9a-f]{32,}$/iu.test(text) || /^wxid_[a-z0-9_-]{4,}$/iu.test(text)
}

function cleanVisibleMentionName(value = '') {
  const cleaned = cleanMentionName(value)
  return looksLikeRawWechatInternalId(cleaned) ? '' : cleaned
}

function extractSenderNameFromRawPayload(rawPayload = {}) {
  if (!rawPayload || typeof rawPayload !== 'object') return ''
  const content = String(rawPayload?.Content || rawPayload?.MMActualContent || '')
  const original = String(rawPayload?.OriginalContent || '')
  const candidates = [
    rawPayload?.ActualNickName,
    rawPayload?.RecommendInfo?.NickName,
    rawPayload?.User?.NickName,
  ]
  if (content.includes(':\n')) candidates.push(content.split(':\n')[0])
  if (original.includes(':<br/>')) candidates.push(original.split(':<br/>')[0])
  return candidates.map(cleanVisibleMentionName).find(Boolean) || ''
}

export async function resolveContactDisplayName(contact, room = null, rawPayload = null) {
  const candidates = []
  try { candidates.push(await room?.alias?.(contact) || '') } catch {}
  candidates.push(extractSenderNameFromRawPayload(rawPayload))
  try { candidates.push(contact?.name?.() || '') } catch {}
  return candidates.map(cleanVisibleMentionName).find(Boolean) || ''
}

function normalizeWechatIdCandidate(value = '') {
  return String(value || '').trim()
}

export async function resolveContactWechatId(contact, rawPayload = null) {
  try { await contact?.ready?.() } catch {}
  const payload = contact?.payload || {}
  const candidates = []
  candidates.push(payload.weixin)
  try { candidates.push(contact?.handle?.() || '') } catch {}
  candidates.push(payload.handle)
  candidates.push(payload.address)
  candidates.push(rawPayload?.Alias)
  candidates.push(rawPayload?.alias)
  candidates.push(rawPayload?.weixin)
  candidates.push(rawPayload?.handle)
  return candidates.map(normalizeWechatIdCandidate).find(Boolean) || ''
}

export async function buildRoomMemberPayload(contact, room = null, rawPayload = null) {
  const senderId = String(contact?.id || '').trim()
  const nickname = await resolveContactDisplayName(contact, room, rawPayload)
  const wechatId = await resolveContactWechatId(contact, rawPayload)
  return {
    sender_id: senderId,
    sender_nickname: nickname || senderId,
    wechat_id: wechatId,
  }
}

export function buildMessageIdentityPayload({
  roomId = '',
  roomName = '',
  senderInfo = {},
  selfInfo = {},
} = {}) {
  const runtimeRoomId = String(roomId || '').trim()
  const runtimeSenderId = String(senderInfo?.id || '').trim()
  const runtimeSelfId = String(selfInfo?.id || '').trim()
  const senderName = String(senderInfo?.name || runtimeSenderId || '').trim()
  const roomAlias = String(senderInfo?.room_alias || '').trim()
  const senderWechatId = String(senderInfo?.wechat_id || '').trim()
  return {
    runtime_room_id: runtimeRoomId,
    runtime_sender_id: runtimeSenderId,
    runtime_self_id: runtimeSelfId,
    sender_wechat_id: senderWechatId,
    sender_room_alias: roomAlias,
    account_fingerprint: {
      runtime_self_id: runtimeSelfId,
      self_name: String(selfInfo?.name || runtimeSelfId || '').trim(),
      wechat_id: String(selfInfo?.wechat_id || '').trim(),
    },
    room_fingerprint: {
      runtime_room_id: runtimeRoomId,
      room_name: String(roomName || runtimeRoomId || '').trim(),
      self_runtime_id: runtimeSelfId,
    },
    member_fingerprint: {
      runtime_sender_id: runtimeSenderId,
      display_name: senderName,
      room_alias: roomAlias,
      wechat_id: senderWechatId,
    },
  }
}

export function memberPayloadMatchesQuery(payload = {}, query = '') {
  const q = String(query || '').trim().toLowerCase()
  if (!q) return true
  const haystack = [
    payload?.sender_id,
    payload?.sender_nickname,
    payload?.wechat_id,
  ].map(value => String(value || '')).join(' ').toLowerCase()
  return haystack.includes(q)
}

function stripLeadingWechatMentionText(text = '') {
  let value = String(text || '').trim()
  for (let i = 0; i < 5; i++) {
    const next = stripOneLeadingWechatMention(value)
    if (next === value) break
    value = next
  }
  return value || String(text || '').trim()
}

function stripOneLeadingWechatMention(text = '') {
  const value = String(text || '').trim()
  const match = value.match(/^[@\uFF20]([^\s\u2005\u2006\u2007\u2008\u2009\u200a,，.。!！?？:：、]{1,128})([\s\u2005\u2006\u2007\u2008\u2009\u200a,，.。!！?？:：、]*)/u)
  if (!match) return value
  const name = match[1] || ''
  if (!looksLikeRawWechatInternalId(name) && name.length > 40) return value
  return value.slice(match[0].length).trim()
}

export function buildManualMentionText(text = '', targets = []) {
  const names = targets.map(item => cleanVisibleMentionName(item?.name || '')).filter(Boolean)
  if (!names.length) return String(text || '')
  return `${names.map(name => `@${name}`).join('\u2005')}\u2005${stripLeadingWechatMentionText(text)}`
}

function escapeMsgSourceXml(value = '') {
  return String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;')
}

function makeClientMsgId() {
  return Math.ceil(Date.now() * 1000)
}

function buildAtUserList(targets = []) {
  const seen = new Set()
  const ids = []
  for (const target of targets || []) {
    const id = String(target?.id || target?.contact?.id || '').trim()
    if (!id || id.startsWith('@@') || seen.has(id)) continue
    seen.add(id)
    ids.push(id)
    if (ids.length >= 20) break
  }
  return ids
}

function buildMsgSourceXml(targetIds = []) {
  const ids = targetIds.map(id => String(id || '').trim()).filter(Boolean)
  if (!ids.length) return ''
  return `<msgsource><atuserlist>${ids.map(escapeMsgSourceXml).join(',')}</atuserlist></msgsource>`
}

function normalizeAliasSyncCooldownMinutes(value) {
  const minutes = Number(value)
  if (!Number.isFinite(minutes) || minutes < 1) return DEFAULT_ALIAS_SYNC_COOLDOWN_MINUTES
  return minutes
}

function shouldRefreshRoomAlias(roomId, cooldownMinutes, cooldownStore, nowMs) {
  const normalizedRoomId = String(roomId || '').trim()
  if (!normalizedRoomId) return false
  const store = cooldownStore || aliasSyncCooldownByRoom
  const currentNowMs = Number(nowMs)
  const safeNowMs = Number.isFinite(currentNowMs) ? currentNowMs : Date.now()
  const cooldownMs = normalizeAliasSyncCooldownMinutes(cooldownMinutes) * 60 * 1000
  const hasLastSync = store.has(normalizedRoomId)
  const lastSyncAt = hasLastSync ? Number(store.get(normalizedRoomId)) : 0
  if (hasLastSync && Number.isFinite(lastSyncAt) && safeNowMs - lastSyncAt < cooldownMs) {
    return false
  }
  store.set(normalizedRoomId, safeNowMs)
  return true
}

export async function resolveMentionTargets(room, mentionIds, findContact, options = {}) {
  const mentions = await resolveMentionContacts(room, mentionIds, findContact)
  const targets = []
  let aliasRefreshAttempted = false
  const cooldownMinutes = options.aliasSyncCooldownMinutes
  const cooldownStore = options.aliasSyncCooldownStore
  const nowMs = options.nowMs
  for (const contact of mentions) {
    let name = ''
    try { name = await room.alias(contact) || '' } catch {}
    if (
      !name &&
      !aliasRefreshAttempted &&
      room?.sync &&
      shouldRefreshRoomAlias(room?.id, cooldownMinutes, cooldownStore, nowMs)
    ) {
      aliasRefreshAttempted = true
      try {
        await room.sync()
        name = await room.alias(contact) || ''
      } catch {}
    }
    if (!name) {
      try { name = contact.name() || '' } catch {}
    }
    targets.push({ id: contact.id, contact, name: cleanMentionName(name) })
  }
  return targets
}

export function getWechat4uRuntime(bot) {
  return bot?.puppet?.wechat4u || bot?.puppet?.wechat4uBridge?.wechat4u || null
}

export function isWechat4uBot(bot) {
  const puppetName = String(bot?.puppet?.constructor?.name || bot?.puppet?.name || '').trim()
  return /wechat4u/iu.test(puppetName) || !!getWechat4uRuntime(bot)
}

export async function sendWechat4uRawTextWithMsgSource(wechat4u, room, text, mentionTargets = []) {
  const roomId = String(room?.id || '').trim()
  if (!wechat4u || !roomId) throw new Error('wechat4u runtime or room id missing')
  if (!wechat4u.request || !wechat4u.CONF || !wechat4u.PROP || !wechat4u.user || !wechat4u.getBaseRequest) {
    throw new Error('wechat4u internals unavailable')
  }
  const targetIds = buildAtUserList(mentionTargets)
  if (!targetIds.length) throw new Error('mention target id missing')
  const msgSource = buildMsgSourceXml(targetIds)
  const content = buildManualMentionText(text, mentionTargets)
  const clientMsgId = makeClientMsgId()
  const response = await wechat4u.request({
    method: 'POST',
    url: wechat4u.CONF.API_webwxsendmsg,
    params: {
      pass_ticket: wechat4u.PROP.passTicket,
      lang: 'zh_CN',
    },
    data: {
      BaseRequest: wechat4u.getBaseRequest(),
      Scene: 0,
      Msg: {
        Type: wechat4u.CONF.MSGTYPE_TEXT,
        Content: content,
        FromUserName: wechat4u.user.UserName || wechat4u.user.userName || wechat4u.user['UserName'],
        ToUserName: roomId,
        LocalID: clientMsgId,
        ClientMsgId: clientMsgId,
        MsgSource: msgSource,
      },
    },
  })
  const data = response?.data || {}
  const ret = Number(data?.BaseResponse?.Ret)
  if (ret !== 0) {
    const errMsg = data?.BaseResponse?.ErrMsg || JSON.stringify(data?.BaseResponse || data)
    throw new Error(`webwxsendmsg ret=${data?.BaseResponse?.Ret} ${errMsg}`)
  }
  return { ok: true, roomId, targetIds, msgSource, content, response: data }
}

export async function sendText(command, deps) {
  const room = await deps.findRoom(command.room_id)
  if (!room) throw new Error(`room not found: ${command.room_id}`)
  const mentionTargets = await resolveMentionTargets(
    room,
    command.mention_ids || [],
    deps.findContact,
    {
      aliasSyncCooldownMinutes: command.alias_sync_cooldown_minutes,
      aliasSyncCooldownStore: deps.aliasSyncCooldownStore,
      nowMs: deps.nowMs?.(),
    },
  )
  const wechat4u = deps.getWechat4u?.()
  const useVisibleMentionText = mentionTargets.length && (deps.isWechat4u?.() || wechat4u)
  if (mentionTargets.length && wechat4u) {
    try {
      await sendWechat4uRawTextWithMsgSource(wechat4u, room, command.text, mentionTargets)
    } catch (error) {
      const errorMessage = String(error?.message || error || 'unknown error')
        .replace(/[\r\n]+/g, ' ')
        .slice(0, 500)
      deps.logWarning?.(
        `[wechat_group] true mention failed; falling back to visible text ` +
        `(reason=wechat4u_raw_send_failed, mention_count=${mentionTargets.length}, error=${errorMessage})`,
      )
      await room.say(buildManualMentionText(command.text, mentionTargets))
    }
  } else if (useVisibleMentionText) {
    deps.logWarning?.(
      `[wechat_group] true mention unavailable; falling back to visible text ` +
      `(reason=wechat4u_runtime_unavailable, mention_count=${mentionTargets.length})`,
    )
    await room.say(buildManualMentionText(command.text, mentionTargets))
  } else if (mentionTargets.length) {
    const contacts = mentionTargets.map(item => item.contact).filter(Boolean)
    const manualText = buildManualMentionText(command.text, mentionTargets)
    try {
      await room.say(command.text, ...contacts)
    } catch {
      await room.say(manualText || command.text)
    }
  } else {
    await room.say(command.text)
  }
  deps.emit('send_result', { ok: true, command: 'send_text', room_id: command.room_id })
}
