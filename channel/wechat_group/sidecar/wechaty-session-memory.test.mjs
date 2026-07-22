import assert from 'node:assert/strict'
import { existsSync } from 'node:fs'
import { mkdtemp, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import path from 'node:path'
import test from 'node:test'

import { MemoryCard } from 'memory-card'

import {
  WECHAT4U_MEMORY_SLOT,
  WechatGroupSessionMemory,
  resolveWechatGroupMemoryFilePath,
} from './wechaty-session-memory.mjs'

const temporaryDirectories = []
const WECHATY_PUPPET_MEMORY_NAMESPACE = 'puppet'

async function createMemoryPrefix() {
  const directory = await mkdtemp(path.join(tmpdir(), 'lightagent-wechat-memory-'))
  temporaryDirectories.push(directory)
  return path.join(directory, 'wechat_group')
}

async function loadWechatyMemory(memoryPrefix) {
  const rootMemory = new WechatGroupSessionMemory(memoryPrefix)
  await rootMemory.load()
  return {
    puppetMemory: rootMemory.multiplex(WECHATY_PUPPET_MEMORY_NAMESPACE),
    rootMemory,
  }
}

test.afterEach(async () => {
  await Promise.all(
    temporaryDirectories.splice(0).map((directory) =>
      rm(directory, { recursive: true, force: true }),
    ),
  )
})

test('resolves the exact memory-card file path without duplicating the suffix', async () => {
  const prefix = await createMemoryPrefix()
  const expectedPath = `${prefix}.memory-card.json`

  assert.equal(resolveWechatGroupMemoryFilePath(prefix), expectedPath)
  assert.equal(resolveWechatGroupMemoryFilePath(expectedPath), expectedPath)
})

test('loads, gets, sets, and saves data through memory-card file storage', async () => {
  const prefix = await createMemoryPrefix()
  const session = { skey: 'persisted-session' }
  const {
    puppetMemory: firstPuppetMemory,
    rootMemory: firstRootMemory,
  } = await loadWechatyMemory(prefix)

  assert.ok(firstRootMemory instanceof MemoryCard)
  assert.ok(firstPuppetMemory instanceof WechatGroupSessionMemory)
  await firstPuppetMemory.set(WECHAT4U_MEMORY_SLOT, session)
  await firstRootMemory.set('ordinary-key', 'ordinary-value')
  await firstRootMemory.save()

  const {
    puppetMemory: secondPuppetMemory,
    rootMemory: secondRootMemory,
  } = await loadWechatyMemory(prefix)

  assert.deepEqual(await secondPuppetMemory.get(WECHAT4U_MEMORY_SLOT), session)
  assert.equal(await secondRootMemory.get('ordinary-key'), 'ordinary-value')
  assert.equal(existsSync(resolveWechatGroupMemoryFilePath(prefix)), true)
})

test('puppet memory delete protects only the Wechat4U login slot', async () => {
  const prefix = await createMemoryPrefix()
  const memoryFilePath = resolveWechatGroupMemoryFilePath(prefix)
  const session = { skey: 'protected-session' }
  const { puppetMemory, rootMemory } = await loadWechatyMemory(prefix)
  await puppetMemory.set(WECHAT4U_MEMORY_SLOT, session)
  await puppetMemory.set('ordinary-key', 'ordinary-value')

  assert.equal(await puppetMemory.delete(WECHAT4U_MEMORY_SLOT), false)
  assert.equal(await puppetMemory.delete('ordinary-key'), true)
  await rootMemory.save()

  assert.equal(existsSync(memoryFilePath), true)
  const { puppetMemory: reloadedPuppetMemory } = await loadWechatyMemory(prefix)
  assert.deepEqual(await reloadedPuppetMemory.get(WECHAT4U_MEMORY_SLOT), session)
  assert.equal(await reloadedPuppetMemory.has('ordinary-key'), false)
})

test('puppet memory clear removes ordinary data but preserves the Wechat4U login slot', async () => {
  const prefix = await createMemoryPrefix()
  const memoryFilePath = resolveWechatGroupMemoryFilePath(prefix)
  const session = { skey: 'protected-session' }
  const { puppetMemory, rootMemory } = await loadWechatyMemory(prefix)
  await puppetMemory.set(WECHAT4U_MEMORY_SLOT, session)
  await puppetMemory.set('ordinary-key', 'ordinary-value')
  await rootMemory.save()

  await puppetMemory.clear()
  await rootMemory.save()

  assert.equal(existsSync(memoryFilePath), true)
  const { puppetMemory: reloadedPuppetMemory } = await loadWechatyMemory(prefix)
  assert.deepEqual(await reloadedPuppetMemory.get(WECHAT4U_MEMORY_SLOT), session)
  assert.equal(await reloadedPuppetMemory.has('ordinary-key'), false)
})

test('puppet memory destroy preserves the Wechat4U login slot and the cache file', async () => {
  const prefix = await createMemoryPrefix()
  const memoryFilePath = resolveWechatGroupMemoryFilePath(prefix)
  const session = { skey: 'protected-session' }
  const { puppetMemory, rootMemory } = await loadWechatyMemory(prefix)
  await puppetMemory.set(WECHAT4U_MEMORY_SLOT, session)
  await puppetMemory.set('ordinary-key', 'ordinary-value')
  await rootMemory.save()

  await puppetMemory.destroy()

  assert.equal(existsSync(memoryFilePath), true)
  const { puppetMemory: reloadedPuppetMemory } = await loadWechatyMemory(prefix)
  assert.deepEqual(await reloadedPuppetMemory.get(WECHAT4U_MEMORY_SLOT), session)
  assert.equal(await reloadedPuppetMemory.has('ordinary-key'), false)
})

test('root memory clear preserves the multiplexed Wechat4U login slot', async () => {
  const prefix = await createMemoryPrefix()
  const memoryFilePath = resolveWechatGroupMemoryFilePath(prefix)
  const session = { skey: 'protected-session' }
  const { puppetMemory, rootMemory } = await loadWechatyMemory(prefix)
  await puppetMemory.set(WECHAT4U_MEMORY_SLOT, session)
  await puppetMemory.set('ordinary-key', 'ordinary-value')
  await rootMemory.set('root-key', 'root-value')
  await rootMemory.save()

  await rootMemory.clear()
  await rootMemory.save()

  assert.equal(existsSync(memoryFilePath), true)
  const {
    puppetMemory: reloadedPuppetMemory,
    rootMemory: reloadedRootMemory,
  } = await loadWechatyMemory(prefix)
  assert.deepEqual(await reloadedPuppetMemory.get(WECHAT4U_MEMORY_SLOT), session)
  assert.equal(await reloadedPuppetMemory.has('ordinary-key'), false)
  assert.equal(await reloadedRootMemory.has('root-key'), false)
})

test('root memory destroy preserves the multiplexed Wechat4U login slot and cache file', async () => {
  const prefix = await createMemoryPrefix()
  const memoryFilePath = resolveWechatGroupMemoryFilePath(prefix)
  const session = { skey: 'protected-session' }
  const { puppetMemory, rootMemory } = await loadWechatyMemory(prefix)
  await puppetMemory.set(WECHAT4U_MEMORY_SLOT, session)
  await puppetMemory.set('ordinary-key', 'ordinary-value')
  await rootMemory.set('root-key', 'root-value')
  await rootMemory.save()

  await rootMemory.destroy()

  assert.equal(existsSync(memoryFilePath), true)
  const {
    puppetMemory: reloadedPuppetMemory,
    rootMemory: reloadedRootMemory,
  } = await loadWechatyMemory(prefix)
  assert.deepEqual(await reloadedPuppetMemory.get(WECHAT4U_MEMORY_SLOT), session)
  assert.equal(await reloadedPuppetMemory.has('ordinary-key'), false)
  assert.equal(await reloadedRootMemory.has('root-key'), false)
})
