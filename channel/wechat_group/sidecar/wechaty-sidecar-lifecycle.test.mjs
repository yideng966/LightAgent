import assert from 'node:assert/strict'
import { EventEmitter } from 'node:events'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

import { WechatGroupSessionMemory } from './wechaty-session-memory.mjs'

async function loadLifecycleModule() {
  try {
    return await import('./wechaty-sidecar-lifecycle.mjs')
  } catch (error) {
    assert.fail(`sidecar lifecycle module is unavailable: ${error.message}`)
  }
}

test('loads protected session memory before injecting it into Wechaty', async () => {
  const lifecycle = await loadLifecycleModule()
  assert.equal(typeof lifecycle.createSessionBackedWechaty, 'function')

  const events = []
  class ObservedSessionMemory extends WechatGroupSessionMemory {
    async load() {
      events.push('load')
    }
  }
  const builtBot = { name: 'test-bot' }
  const WechatyBuilder = {
    build(options) {
      events.push('build')
      assert.ok(options.memory instanceof ObservedSessionMemory)
      return builtBot
    },
  }

  const result = await lifecycle.createSessionBackedWechaty({
    WechatyBuilder,
    SessionMemory: ObservedSessionMemory,
    config: {
      memory_path: 'test-memory-prefix',
      puppet: 'test-puppet',
    },
  })

  assert.deepEqual(events, ['load', 'build'])
  assert.equal(result.bot, builtBot)
  assert.ok(result.memory instanceof WechatGroupSessionMemory)
  assert.equal(result.options.name, 'test-memory-prefix')
  assert.equal(result.options.puppet, 'test-puppet')
  assert.equal(result.options.memory, result.memory)
})

test('session-preserving shutdown closes input, saves memory, then exits', async () => {
  const lifecycle = await loadLifecycleModule()
  assert.equal(typeof lifecycle.createSessionPreservingShutdown, 'function')

  const events = []
  const shutdown = lifecycle.createSessionPreservingShutdown({
    closeInput: () => events.push('close'),
    getMemory: () => ({
      save: async () => events.push('save'),
    }),
    reportError: error => events.push(`error:${error.message}`),
    exitProcess: code => events.push(`exit:${code}`),
  })

  await shutdown('stop')

  assert.deepEqual(events, ['close', 'save', 'exit:0'])
})

test('session-preserving shutdown is idempotent while and after saving', async () => {
  const lifecycle = await loadLifecycleModule()
  let releaseSave
  const events = []
  const shutdown = lifecycle.createSessionPreservingShutdown({
    closeInput: () => events.push('close'),
    getMemory: () => ({
      save: () => new Promise(resolve => {
        events.push('save')
        releaseSave = resolve
      }),
    }),
    reportError: error => events.push(`error:${error.message}`),
    exitProcess: code => events.push(`exit:${code}`),
  })

  const first = shutdown('stop')
  const second = shutdown('SIGINT')
  assert.equal(first, second)
  assert.deepEqual(events, ['close', 'save'])

  releaseSave()
  await Promise.all([first, second])
  const third = shutdown('SIGTERM')
  assert.equal(third, first)
  await third

  assert.deepEqual(events, ['close', 'save', 'exit:0'])
})

test('session-preserving shutdown reports save failure and still exits', async () => {
  const lifecycle = await loadLifecycleModule()
  const events = []
  const shutdown = lifecycle.createSessionPreservingShutdown({
    closeInput: () => events.push('close'),
    getMemory: () => ({
      save: async () => {
        events.push('save')
        throw new Error('save failed')
      },
    }),
    reportError: (error, reason) => events.push(`error:${reason}:${error.message}`),
    exitProcess: code => events.push(`exit:${code}`),
  })

  await shutdown('SIGTERM')

  assert.deepEqual(events, [
    'close',
    'save',
    'error:SIGTERM:save failed',
    'exit:0',
  ])
})

test('registers SIGINT and SIGTERM for session-preserving shutdown', async () => {
  const lifecycle = await loadLifecycleModule()
  assert.equal(
    typeof lifecycle.registerSessionPreservingSignalHandlers,
    'function',
  )

  const processRef = new EventEmitter()
  const reasons = []
  lifecycle.registerSessionPreservingSignalHandlers({
    processRef,
    shutdown: reason => reasons.push(reason),
  })

  processRef.emit('SIGINT')
  processRef.emit('SIGTERM')

  assert.deepEqual(reasons, ['SIGINT', 'SIGTERM'])
})

test('sidecar wires stop and signals without an in-process logout path', async () => {
  const source = await readFile(
    new URL('./wechaty-sidecar.mjs', import.meta.url),
    'utf8',
  )

  assert.match(source, /createSessionBackedWechaty/)
  assert.match(source, /createSessionPreservingShutdown/)
  assert.match(source, /registerSessionPreservingSignalHandlers/)
  assert.match(source, /memory:\s*null/)
  assert.match(source, /state\.memory\s*=\s*memory/)
  assert.match(source, /case\s+['"]stop['"]:\s*\n\s*await shutdown\(['"]stop['"]\)/)
  assert.doesNotMatch(source, /state\.bot\.stop\s*\(/)
  assert.doesNotMatch(source, /case\s+['"]relogin['"]\s*:/)
})
