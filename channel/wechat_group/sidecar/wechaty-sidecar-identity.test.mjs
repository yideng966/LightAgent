import test from 'node:test'
import assert from 'node:assert/strict'

import { buildMessageIdentityPayload } from './wechaty-sidecar-core.mjs'

test('buildMessageIdentityPayload adds fingerprints while preserving runtime ids', () => {
  const payload = buildMessageIdentityPayload({
    roomId: 'room@@runtime',
    roomName: '测试群',
    senderInfo: {
      id: 'wxid_alice',
      name: 'Alice',
      wechat_id: 'alice_wechat',
      room_alias: '阿狸',
    },
    selfInfo: {
      id: 'wxid_bot',
      name: 'LightBot',
      wechat_id: 'bot_wechat',
    },
  })

  assert.equal(payload.runtime_room_id, 'room@@runtime')
  assert.equal(payload.runtime_sender_id, 'wxid_alice')
  assert.equal(payload.runtime_self_id, 'wxid_bot')
  assert.deepEqual(payload.account_fingerprint, {
    runtime_self_id: 'wxid_bot',
    self_name: 'LightBot',
    wechat_id: 'bot_wechat',
  })
  assert.deepEqual(payload.room_fingerprint, {
    runtime_room_id: 'room@@runtime',
    room_name: '测试群',
    self_runtime_id: 'wxid_bot',
  })
  assert.deepEqual(payload.member_fingerprint, {
    runtime_sender_id: 'wxid_alice',
    display_name: 'Alice',
    room_alias: '阿狸',
    wechat_id: 'alice_wechat',
  })
})
