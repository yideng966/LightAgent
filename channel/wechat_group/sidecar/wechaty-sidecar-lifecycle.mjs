import { WechatGroupSessionMemory } from './wechaty-session-memory.mjs'

export async function createSessionBackedWechaty({
  WechatyBuilder,
  config,
  SessionMemory = WechatGroupSessionMemory,
}) {
  const memoryPath = config.memory_path || 'lightagent-wechat-group'
  const memory = new SessionMemory(memoryPath)
  await memory.load()

  const options = {
    name: memoryPath,
    puppet: config.puppet || 'wechaty-puppet-wechat4u',
    memory,
  }
  return {
    bot: WechatyBuilder.build(options),
    memory,
    options,
  }
}

export function createSessionPreservingShutdown({
  closeInput,
  getMemory,
  reportError,
  exitProcess,
}) {
  let shutdownPromise = null

  return function shutdown(reason = 'stop') {
    if (shutdownPromise) return shutdownPromise

    shutdownPromise = (async () => {
      try {
        closeInput()
      } catch (error) {
        try { reportError(error, reason) } catch {}
      }

      try {
        const memory = getMemory()
        if (memory) await memory.save()
      } catch (error) {
        try { reportError(error, reason) } catch {}
      } finally {
        exitProcess(0)
      }
    })()

    return shutdownPromise
  }
}

export function registerSessionPreservingSignalHandlers({
  processRef,
  shutdown,
}) {
  for (const signal of ['SIGINT', 'SIGTERM']) {
    processRef.once(signal, () => {
      const result = shutdown(signal)
      result?.catch?.(() => {})
    })
  }
}
