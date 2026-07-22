import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildMediaFilePath,
  buildManualMentionText,
  detectMessageMediaType,
  downloadStickerMediaFromText,
  downloadStickerMediaWithFallback,
  extractStickerMediaUrl,
  extractQuotedMessageFromRawPayload,
  resolveMessageRawPayload,
  sanitizeMediaFilePart,
  sendText,
  sendWechat4uRawTextWithMsgSource,
  resolveContactDisplayName,
  resolveContactWechatId,
  buildRoomMemberPayload,
  memberPayloadMatchesQuery,
} from './wechaty-sidecar-core.mjs'

function buildReferMsgContent({ fromusr = '@bot', displayname = 'LightBot', content = 'previous answer', title = 'current reply', type = 1, messageId = '123456' } = {}) {
  return `<msg><appmsg><title>${title}</title><des></des><type>57</type><url></url><appattach></appattach><thumburl></thumburl><md5></md5><refermsg><type>${type}</type><svrid>${messageId}</svrid><fromusr>${fromusr}</fromusr><chatusr>@@room</chatusr><displayname>${displayname}</displayname><content>${content}</content></refermsg></appmsg><fromusername>@@room</fromusername><appinfo><appname></appname></appinfo></msg>`
}

function escapeXml(value = '') {
  return String(value)
    .replace(/&/gu, '&amp;')
    .replace(/</gu, '&lt;')
    .replace(/>/gu, '&gt;')
}

test('extractQuotedMessageFromRawPayload marks quote self when refermsg sender is current bot', async () => {
  const result = await extractQuotedMessageFromRawPayload({
    MsgType: 49,
    Content: buildReferMsgContent({ fromusr: '@bot', displayname: 'LightBot', content: 'hello from bot' }),
  }, '@bot')

  assert.equal(result.is_quote_self, true)
  assert.deepEqual(result.quote, {
    sender_id: '@bot',
    sender_name: 'LightBot',
    message_id: '123456',
    type: '1',
    content: 'hello from bot',
  })
  assert.equal(result.quote_diagnostics.parse_status, 'quote_parsed')
  assert.equal(result.quote_diagnostics.xml_candidate_count, 1)
  assert.equal(result.quote_diagnostics.parsed_candidate_count, 1)
})

test('extractQuotedMessageFromRawPayload does not mark quote self for other sender', async () => {
  const result = await extractQuotedMessageFromRawPayload({
    MsgType: 49,
    Content: buildReferMsgContent({ fromusr: '@alice', displayname: 'Alice', content: 'hello from alice' }),
  }, '@bot')

  assert.equal(result.is_quote_self, false)
  assert.equal(result.quote.sender_id, '@alice')
})

test('extractQuotedMessageFromRawPayload falls back to escaped OriginalContent for image references', async () => {
  const originalContent = buildReferMsgContent({
    fromusr: '@alice',
    displayname: 'Alice',
    content: '[图片]',
    type: 3,
    messageId: '3493626914644513230',
  })
  const result = await extractQuotedMessageFromRawPayload({
    MsgType: 49,
    Content: '<msg><appmsg><type>57</type></appmsg></msg>',
    OriginalContent: `@alice:<br/>${escapeXml(originalContent)} trailing-data`,
  }, '@bot')

  assert.equal(result.is_quote_self, false)
  assert.equal(result.raw_app_type, '57')
  assert.deepEqual(result.quote, {
    sender_id: '@alice',
    sender_name: 'Alice',
    message_id: '3493626914644513230',
    type: '3',
    content: '[图片]',
  })
  assert.equal(result.quote_diagnostics.parse_status, 'quote_parsed')
  assert.equal(result.quote_diagnostics.xml_candidate_count, 2)
  assert.equal(result.quote_diagnostics.parsed_candidate_count, 2)
})

test('extractQuotedMessageFromRawPayload reports missing XML candidates without raw content', async () => {
  const result = await extractQuotedMessageFromRawPayload({ MsgType: 1 }, '@bot')

  assert.equal(result.raw_app_type, '')
  assert.deepEqual(result.quote, {})
  assert.deepEqual(result.quote_diagnostics, {
    parse_status: 'xml_candidate_missing',
    xml_candidate_count: 0,
    parsed_candidate_count: 0,
  })
})

test('resolveMessageRawPayload uses the public puppet method when available', async () => {
  class PuppetWechat4u {
    async messageRawPayload(id) {
      assert.equal(id, 'message-1')
      return { MsgType: 49, AppMsgType: 57, Content: '<msg />' }
    }
  }

  const result = await resolveMessageRawPayload({ puppet: new PuppetWechat4u() }, 'message-1')

  assert.equal(result.payload.MsgType, 49)
  assert.deepEqual(result.diagnostics, {
    status: 'resolved',
    source: 'puppet_method',
    method_available: true,
    cache_available: false,
    method_error: '',
    cache_error: '',
    has_content: true,
    has_original_content: false,
    msg_type: '49',
    app_msg_type: '57',
  })
})

test('resolveMessageRawPayload falls back to the Wechat4u puppet cache', async () => {
  const payload = { MsgType: 49, Content: '<msg />' }
  class PuppetWechat4u {
    cacheMessageRawPayload = new Map([['message-2', payload]])

    async messageRawPayload() {
      throw new Error('id not found')
    }
  }

  const result = await resolveMessageRawPayload({ puppet: new PuppetWechat4u() }, 'message-2')

  assert.equal(result.payload, payload)
  assert.equal(result.diagnostics.status, 'resolved')
  assert.equal(result.diagnostics.source, 'puppet_cache')
  assert.equal(result.diagnostics.method_error, 'id_not_found')
  assert.equal(result.diagnostics.cache_available, true)
})

test('resolveMessageRawPayload does not inspect another puppets internal cache', async () => {
  let cacheReads = 0
  const puppet = {
    cacheMessageRawPayload: {
      get() {
        cacheReads += 1
        return { MsgType: 49, Content: '<msg />' }
      },
    },
  }

  const result = await resolveMessageRawPayload({ puppet }, 'message-3')

  assert.equal(result.payload, null)
  assert.equal(result.diagnostics.cache_available, false)
  assert.equal(cacheReads, 0)
})

test('resolveMessageRawPayload diagnostics never include error text or arbitrary raw types', async () => {
  class PuppetWechat4u {
    cacheMessageRawPayload = new Map()

    async messageRawPayload() {
      const error = new Error('failed for C:\\private\\quote.xml <msg>secret</msg>')
      error.name = 'C:\\private\\quote.xml'
      throw error
    }
  }

  const result = await resolveMessageRawPayload({ puppet: new PuppetWechat4u() }, 'message-4')
  const serialized = JSON.stringify(result.diagnostics)

  assert.equal(result.payload, null)
  assert.equal(result.diagnostics.method_error, 'unknown_error')
  assert.equal(result.diagnostics.cache_error, 'id_not_found')
  assert.doesNotMatch(serialized, /private|secret|<msg>/iu)
})

test('sendText mentions the original sender by contact id after room membership check', async () => {
  const alice = { id: 'wxid_alice', name: () => 'Alice' }
  const room = {
    id: 'room@@abc',
    hasCalls: [],
    sayCalls: [],
    async has(contact) {
      this.hasCalls.push(contact)
      return contact.id === alice.id
    },
    async say(...args) {
      this.sayCalls.push(args)
    },
  }
  const emitted = []

  await sendText(
    { room_id: room.id, text: 'hello', mention_ids: [alice.id] },
    {
      emit: (type, payload) => emitted.push({ type, payload }),
      findRoom: async roomId => roomId === room.id ? room : undefined,
      findContact: async contactId => contactId === alice.id ? alice : undefined,
    },
  )

  assert.deepEqual(room.hasCalls, [alice])
  assert.deepEqual(room.sayCalls, [['hello', alice]])
  assert.deepEqual(emitted, [{
    type: 'send_result',
    payload: { ok: true, command: 'send_text', room_id: room.id },
  }])
})

test('sendText resolves mention target from current room members when contact lookup misses', async () => {
  const alice = { id: 'wxid_alice', name: () => 'Alice' }
  const room = {
    id: 'room@@abc',
    memberAllCalls: 0,
    sayCalls: [],
    async memberAll() {
      this.memberAllCalls += 1
      return [alice]
    },
    async has() {
      throw new Error('room.has should not be needed for memberAll matches')
    },
    async alias(contact) {
      return contact.id === alice.id ? 'Alice Alias' : ''
    },
    async say(...args) {
      this.sayCalls.push(args)
    },
  }

  await sendText(
    { room_id: room.id, text: 'hello', mention_ids: [alice.id] },
    {
      emit: () => {},
      findRoom: async roomId => roomId === room.id ? room : undefined,
      findContact: async () => undefined,
    },
  )

  assert.equal(room.memberAllCalls, 1)
  assert.deepEqual(room.sayCalls, [['hello', alice]])
})

test('sendText treats configured wechat4u puppet as visible mention mode even without runtime internals', async () => {
  const alice = { id: 'wxid_alice', name: () => 'Alice Contact' }
  const room = {
    id: 'room@@abc',
    sayCalls: [],
    async memberAll() {
      return [alice]
    },
    async alias(contact) {
      return contact.id === alice.id ? 'Alice Alias' : ''
    },
    async say(...args) {
      this.sayCalls.push(args)
    },
  }
  const warnings = []

  await sendText(
    { room_id: room.id, text: 'hello', mention_ids: [alice.id] },
    {
      emit: () => {},
      findRoom: async roomId => roomId === room.id ? room : undefined,
      findContact: async () => undefined,
      getWechat4u: () => null,
      isWechat4u: () => true,
      logWarning: message => warnings.push(message),
    },
  )

  assert.deepEqual(room.sayCalls, [['@Alice Alias\u2005hello']])
  assert.deepEqual(warnings, [
    '[wechat_group] true mention unavailable; falling back to visible text (reason=wechat4u_runtime_unavailable, mention_count=1)',
  ])
})

test('sendText uses visible room alias mention text for wechat4u', async () => {
  const alice = { id: 'wxid_alice', name: () => 'Alice Contact' }
  const room = {
    id: 'room@@abc',
    sayCalls: [],
    async memberAll() {
      return [alice]
    },
    async has(contact) {
      return contact.id === alice.id
    },
    async alias(contact) {
      return contact.id === alice.id ? 'Alice Alias' : ''
    },
    async say(...args) {
      this.sayCalls.push(args)
    },
  }
  const warnings = []

  await sendText(
    { room_id: room.id, text: '@Wrong hello', mention_ids: [alice.id] },
    {
      emit: () => {},
      findRoom: async roomId => roomId === room.id ? room : undefined,
      findContact: async () => alice,
      getWechat4u: () => ({}),
      logWarning: message => warnings.push(message),
    },
  )

  assert.deepEqual(room.sayCalls, [['@Alice Alias\u2005hello']])
  assert.equal(warnings.length, 1)
  assert.match(warnings[0], /reason=wechat4u_raw_send_failed/)
  assert.match(warnings[0], /error=wechat4u internals unavailable/)
  assert.doesNotMatch(warnings[0], /@Wrong|hello|Alice Alias/)
})

test('buildManualMentionText strips leading long raw sender id from model output', () => {
  const rawSenderId = '@ec16ad646512ce039fd5b1885a848f170362fed7b7fbe874d257455cf85ea0b2'

  const text = buildManualMentionText(`${rawSenderId} hello`, [{ name: 'Alice Alias' }])

  assert.equal(text, '@Alice Alias\u2005hello')
})

test('buildManualMentionText does not expose raw sender id as visible mention name', () => {
  const text = buildManualMentionText('hello', [
    { name: '@ec16ad646512ce039fd5b1885a848f170362fed7b7fbe874d257455cf85ea0b2' },
  ])

  assert.equal(text, 'hello')
})

test('resolveContactDisplayName prefers room alias over raw contact id', async () => {
  const rawSenderId = '@ec16ad646512ce039fd5b1885a848f170362fed7b7fbe874d257455cf85ea0b2'
  const contact = { id: rawSenderId, name: () => rawSenderId }
  const room = { alias: async () => 'Alice Alias' }

  const name = await resolveContactDisplayName(contact, room)

  assert.equal(name, 'Alice Alias')
})

test('resolveContactDisplayName uses raw payload sender nickname when contact name is raw id', async () => {
  const rawSenderId = '@ec16ad646512ce039fd5b1885a848f170362fed7b7fbe874d257455cf85ea0b2'
  const contact = { id: rawSenderId, name: () => rawSenderId }

  const name = await resolveContactDisplayName(contact, null, { ActualNickName: 'Alice Raw' })

  assert.equal(name, 'Alice Raw')
})

test('resolveContactWechatId reads wechat id from contact payload aliases', async () => {
  const contact = {
    id: '@alice',
    payload: {
      weixin: 'yideng0803',
      handle: '',
      address: '',
    },
    weixin: () => '',
  }

  const wechatId = await resolveContactWechatId(contact)

  assert.equal(wechatId, 'yideng0803')
})

test('buildRoomMemberPayload includes wechat id from raw Alias fallback', async () => {
  const contact = {
    id: '@alice',
    name: () => 'Alice',
    payload: {},
  }

  const payload = await buildRoomMemberPayload(contact, null, { Alias: 'yideng0803' })

  assert.deepEqual(payload, {
    sender_id: '@alice',
    sender_nickname: 'Alice',
    wechat_id: 'yideng0803',
  })
})

test('memberPayloadMatchesQuery searches id nickname and wechat id', () => {
  const payload = {
    sender_id: '@alice',
    sender_nickname: '灯火通明',
    wechat_id: 'yideng0803',
  }

  assert.equal(memberPayloadMatchesQuery(payload, 'yideng0803'), true)
  assert.equal(memberPayloadMatchesQuery(payload, '灯火'), true)
  assert.equal(memberPayloadMatchesQuery(payload, '@alice'), true)
  assert.equal(memberPayloadMatchesQuery(payload, 'missing'), false)
})

test('sendText refreshes room members before falling back to contact name for wechat4u mentions', async () => {
  const alice = { id: 'wxid_alice', name: () => 'Alice Contact' }
  const room = {
    id: 'room@@abc',
    aliasReady: false,
    syncCalls: 0,
    sayCalls: [],
    async memberAll() {
      return [alice]
    },
    async alias(contact) {
      if (contact.id !== alice.id) return ''
      return this.aliasReady ? 'Alice Room Alias' : ''
    },
    async sync() {
      this.syncCalls += 1
      this.aliasReady = true
    },
    async say(...args) {
      this.sayCalls.push(args)
    },
  }

  await sendText(
    { room_id: room.id, text: 'hello', mention_ids: [alice.id] },
    {
      emit: () => {},
      findRoom: async roomId => roomId === room.id ? room : undefined,
      findContact: async () => undefined,
      getWechat4u: () => ({}),
    },
  )

  assert.equal(room.syncCalls, 1)
  assert.deepEqual(room.sayCalls, [['@Alice Room Alias\u2005hello']])
})

test('sendText throttles alias refresh sync by room within cooldown minutes', async () => {
  const alice = { id: 'wxid_alice', name: () => 'Alice Contact' }
  let roomAlias = ''
  const room = {
    id: 'room@@cooldown',
    syncCalls: 0,
    sayCalls: [],
    async memberAll() {
      return [alice]
    },
    async alias(contact) {
      if (contact.id !== alice.id) return ''
      return roomAlias
    },
    async sync() {
      this.syncCalls += 1
      roomAlias = 'Alice Room Alias'
    },
    async say(...args) {
      this.sayCalls.push(args)
    },
  }
  const cooldownStore = new Map()
  let nowMs = 0
  const deps = {
    emit: () => {},
    findRoom: async roomId => roomId === room.id ? room : undefined,
    findContact: async () => undefined,
    getWechat4u: () => ({}),
    aliasSyncCooldownStore: cooldownStore,
    nowMs: () => nowMs,
  }

  await sendText(
    { room_id: room.id, text: 'hello', mention_ids: [alice.id], alias_sync_cooldown_minutes: 1 },
    deps,
  )

  roomAlias = ''
  nowMs = 30 * 1000
  await sendText(
    { room_id: room.id, text: 'hello again', mention_ids: [alice.id], alias_sync_cooldown_minutes: 1 },
    deps,
  )

  roomAlias = ''
  nowMs = 61 * 1000
  await sendText(
    { room_id: room.id, text: 'hello after cooldown', mention_ids: [alice.id], alias_sync_cooldown_minutes: 1 },
    deps,
  )

  assert.equal(room.syncCalls, 2)
  assert.deepEqual(room.sayCalls, [
    ['@Alice Room Alias\u2005hello'],
    ['@Alice Contact\u2005hello again'],
    ['@Alice Room Alias\u2005hello after cooldown'],
  ])
})

test('sendText uses wechat4u MsgSource atuserlist for real group mention when runtime internals are available', async () => {
  const alice = { id: '@alice', name: () => 'Alice Contact' }
  const room = {
    id: '@@room',
    sayCalls: [],
    async memberAll() {
      return [alice]
    },
    async alias(contact) {
      return contact.id === alice.id ? 'Alice Alias' : ''
    },
    async say(...args) {
      this.sayCalls.push(args)
    },
  }
  const requests = []
  const wechat4u = {
    CONF: {
      API_webwxsendmsg: 'https://wx.example/cgi-bin/mmwebwx-bin/webwxsendmsg',
      MSGTYPE_TEXT: 1,
    },
    PROP: { passTicket: 'ticket-1' },
    user: { UserName: '@bot' },
    getBaseRequest: () => ({ Uin: '1', Sid: 'sid', Skey: 'skey', DeviceID: 'device' }),
    request: async payload => {
      requests.push(payload)
      return { data: { BaseResponse: { Ret: 0 }, MsgID: 'msg-1' } }
    },
  }

  await sendText(
    { room_id: room.id, text: 'hello', mention_ids: [alice.id] },
    {
      emit: () => {},
      findRoom: async roomId => roomId === room.id ? room : undefined,
      findContact: async () => undefined,
      getWechat4u: () => wechat4u,
    },
  )

  assert.deepEqual(room.sayCalls, [])
  assert.equal(requests.length, 1)
  assert.equal(requests[0].data.Msg.Content, '@Alice Alias\u2005hello')
  assert.equal(requests[0].data.Msg.MsgSource, '<msgsource><atuserlist>@alice</atuserlist></msgsource>')
})

test('sendText falls back to visible mention text when native contact mention fails', async () => {
  const alice = { id: 'wxid_alice', name: () => 'Alice Contact' }
  const room = {
    id: 'room@@abc',
    sayCalls: [],
    async has(contact) {
      return contact.id === alice.id
    },
    async alias(contact) {
      return contact.id === alice.id ? 'Alice Alias' : ''
    },
    async say(...args) {
      this.sayCalls.push(args)
      if (args.length > 1) throw new Error('native mention failed')
    },
  }

  await sendText(
    { room_id: room.id, text: 'hello', mention_ids: [alice.id] },
    {
      emit: () => {},
      findRoom: async roomId => roomId === room.id ? room : undefined,
      findContact: async contactId => contactId === alice.id ? alice : undefined,
    },
  )

  assert.deepEqual(room.sayCalls, [
    ['hello', alice],
    ['@Alice Alias\u2005hello'],
  ])
})

test('sendWechat4uRawTextWithMsgSource sends atuserlist metadata for real group mention', async () => {
  const requests = []
  const wechat4u = {
    CONF: {
      API_webwxsendmsg: 'https://wx.example/cgi-bin/mmwebwx-bin/webwxsendmsg',
      MSGTYPE_TEXT: 1,
    },
    PROP: { passTicket: 'ticket-1' },
    user: { UserName: '@bot' },
    getBaseRequest: () => ({ Uin: '1', Sid: 'sid', Skey: 'skey', DeviceID: 'device' }),
    request: async payload => {
      requests.push(payload)
      return { data: { BaseResponse: { Ret: 0 }, MsgID: 'msg-1', LocalID: 'local-1' } }
    },
  }

  const result = await sendWechat4uRawTextWithMsgSource(
    wechat4u,
    { id: '@@room' },
    'hello',
    [{ id: '@alice', name: 'Alice' }],
  )

  assert.equal(result.ok, true)
  assert.equal(requests.length, 1)
  assert.equal(requests[0].url, wechat4u.CONF.API_webwxsendmsg)
  assert.equal(requests[0].data.Msg.ToUserName, '@@room')
  assert.equal(requests[0].data.Msg.Content, '@Alice\u2005hello')
  assert.equal(requests[0].data.Msg.MsgSource, '<msgsource><atuserlist>@alice</atuserlist></msgsource>')
  assert.deepEqual(requests[0].data.BaseRequest, wechat4u.getBaseRequest())
})

test('sendWechat4uRawTextWithMsgSource accepts wxid member ids for real group mention', async () => {
  const requests = []
  const wechat4u = {
    CONF: {
      API_webwxsendmsg: 'https://wx.example/cgi-bin/mmwebwx-bin/webwxsendmsg',
      MSGTYPE_TEXT: 1,
    },
    PROP: { passTicket: 'ticket-1' },
    user: { UserName: '@bot' },
    getBaseRequest: () => ({ Uin: '1', Sid: 'sid', Skey: 'skey', DeviceID: 'device' }),
    request: async payload => {
      requests.push(payload)
      return { data: { BaseResponse: { Ret: 0 }, MsgID: 'msg-1', LocalID: 'local-1' } }
    },
  }

  await sendWechat4uRawTextWithMsgSource(
    wechat4u,
    { id: '@@room' },
    'hello',
    [{ id: 'wxid_alice', name: 'Alice' }],
  )

  assert.equal(requests.length, 1)
  assert.equal(requests[0].data.Msg.MsgSource, '<msgsource><atuserlist>wxid_alice</atuserlist></msgsource>')
})

test('detectMessageMediaType identifies image messages from numeric or string message type', () => {
  assert.equal(detectMessageMediaType({ type: () => 6 }), 'image')
  assert.equal(detectMessageMediaType({ type: () => 'Image' }), 'image')
  assert.equal(detectMessageMediaType({ type: () => 2 }), 'audio')
  assert.equal(detectMessageMediaType({ type: () => 'Text' }), 'text')
})

test('detectMessageMediaType distinguishes stickers from normal images', () => {
  assert.equal(detectMessageMediaType({ type: () => 5 }), 'sticker')
  assert.equal(detectMessageMediaType({ type: () => 'Emoticon' }), 'sticker')
})

test('detectMessageMediaType treats numeric text messages as text', () => {
  assert.equal(detectMessageMediaType({ type: () => 7 }), 'text')
})

test('sanitizeMediaFilePart removes path separators and unsafe characters', () => {
  assert.equal(sanitizeMediaFilePart('../room@@abc/hello world'), 'room@@abc_hello_world')
  assert.equal(sanitizeMediaFilePart(''), 'unknown')
})

test('buildMediaFilePath keeps media files under the configured media directory', () => {
  const path = buildMediaFilePath('D:/lightagent/media', '../room@@abc', '../../msg-1', 'photo.large.JPG')

  assert.equal(path.replaceAll('\\', '/'), 'D:/lightagent/media/room@@abc/msg-1.jpg')
})

test('buildMediaFilePath stores stickers with gif extension', () => {
  const path = buildMediaFilePath('D:/lightagent/media', 'room@@abc', 'msg-1', 'emoji.jpg', 'sticker')

  assert.equal(path.replaceAll('\\', '/'), 'D:/lightagent/media/room@@abc/msg-1.gif')
})

test('extractStickerMediaUrl reads escaped cdnurl from emoji xml', () => {
  const xml = '<msg><emoji cdnurl="http://wx.example/stodownload?m=abc&amp;amp;filekey=key" encrypturl="http://wx.example/encrypted" /></msg>'

  assert.equal(extractStickerMediaUrl(xml), 'http://wx.example/stodownload?m=abc&filekey=key')
})

test('downloadStickerMediaFromText writes fetched sticker bytes', async () => {
  const writes = []
  const mkdirs = []
  const ok = await downloadStickerMediaFromText(
    '<msg><emoji cdnurl="http://wx.example/sticker.gif?m=abc&amp;amp;filekey=key" /></msg>',
    'D:/lightagent/media/room/msg-1.gif',
    {
      fetch: async url => ({
        ok: true,
        status: 200,
        arrayBuffer: async () => new Uint8Array([0x47, 0x49, 0x46, 0x38]).buffer,
        url,
      }),
      mkdir: async dir => mkdirs.push(dir),
      writeFile: async (target, buffer) => writes.push([target, Buffer.from(buffer)]),
    },
  )

  assert.equal(ok, true)
  assert.equal(mkdirs[0].replaceAll('\\', '/'), 'D:/lightagent/media/room')
  assert.equal(writes[0][0].replaceAll('\\', '/'), 'D:/lightagent/media/room/msg-1.gif')
  assert.deepEqual([...writes[0][1]], [0x47, 0x49, 0x46, 0x38])
})

test('downloadStickerMediaWithFallback uses raw XML after FileBox download rejects', async () => {
  const writes = []
  const target = 'D:/lightagent/media/room/msg-1.gif'
  const ok = await downloadStickerMediaWithFallback(
    '<msg><emoji cdnurl="http://wx.example/sticker.gif?m=abc&amp;amp;filekey=key" /></msg>',
    target,
    async () => {
      throw new TypeError("Cannot read properties of undefined (reading 'msg')")
    },
    {
      stat: async () => { throw new Error('not found') },
      fetch: async () => ({
        ok: true,
        arrayBuffer: async () => new Uint8Array([0x47, 0x49, 0x46, 0x38]).buffer,
      }),
      mkdir: async () => {},
      writeFile: async (filePath, buffer) => writes.push([filePath, Buffer.from(buffer)]),
    },
  )

  assert.equal(ok, true)
  assert.equal(writes[0][0].replaceAll('\\', '/'), target)
  assert.deepEqual([...writes[0][1]], [0x47, 0x49, 0x46, 0x38])
})

test('downloadStickerMediaWithFallback suppresses parser errors for placeholder stickers', async () => {
  let attempts = 0
  const ok = await downloadStickerMediaWithFallback(
    '[动画表情]',
    'D:/lightagent/media/room/msg-2.gif',
    async () => {
      attempts += 1
      throw new TypeError("Cannot read properties of undefined (reading 'msg')")
    },
    {
      stat: async () => { throw new Error('not found') },
      fetch: async () => { throw new Error('fetch should not be called') },
    },
  )

  assert.equal(ok, false)
  assert.equal(attempts, 1)
})
