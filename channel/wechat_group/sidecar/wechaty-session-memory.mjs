import { MemoryCard } from 'memory-card'

const MEMORY_CARD_FILE_SUFFIX = '.memory-card.json'
const WECHATY_PUPPET_MEMORY_NAMESPACE = 'puppet'

export const WECHAT4U_MEMORY_SLOT = 'PUPPET-WECHAT4U'

export function resolveWechatGroupMemoryFilePath(memoryPrefix) {
  return memoryPrefix.endsWith(MEMORY_CARD_FILE_SUFFIX)
    ? memoryPrefix
    : `${memoryPrefix}${MEMORY_CARD_FILE_SUFFIX}`
}

export class WechatGroupSessionMemory extends MemoryCard {
  async delete(name) {
    if (name === WECHAT4U_MEMORY_SLOT) {
      return false
    }
    return super.delete(name)
  }

  async clear() {
    const sessionMemory = this.isMultiplex()
      ? this
      : this.multiplex(WECHATY_PUPPET_MEMORY_NAMESPACE)
    const hasSession = await sessionMemory.has(WECHAT4U_MEMORY_SLOT)
    const session = hasSession
      ? await sessionMemory.get(WECHAT4U_MEMORY_SLOT)
      : undefined

    await super.clear()
    if (hasSession) {
      const restoredSessionMemory = this.isMultiplex()
        ? this
        : this.multiplex(WECHATY_PUPPET_MEMORY_NAMESPACE)
      await restoredSessionMemory.set(WECHAT4U_MEMORY_SLOT, session)
    }
  }

  async destroy() {
    await this.clear()
    await this.save()
  }
}
