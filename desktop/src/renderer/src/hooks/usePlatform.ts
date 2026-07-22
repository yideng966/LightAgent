import { useEffect, useState } from 'react'

export type Platform = 'mac' | 'win' | 'linux'

function detectPlatform(): Platform {
  const p = window.electronAPI?.platform
  if (p === 'darwin') return 'mac'
  if (p === 'win32') return 'win'
  if (p === 'linux') return 'linux'
  // Fallback for browser dev without electron
  if (typeof navigator !== 'undefined' && /Mac/i.test(navigator.platform)) return 'mac'
  return 'win'
}

/**
 * Resolves the host platform and applies a `.platform-*` class on <html>
 * so CSS can branch on platform (titlebar layout, scrollbars, etc.).
 */
export function usePlatform(): { platform: Platform; isMac: boolean; isWin: boolean } {
  const [platform] = useState<Platform>(detectPlatform)

  useEffect(() => {
    const root = document.documentElement
    root.classList.remove('platform-mac', 'platform-win', 'platform-linux')
    root.classList.add(`platform-${platform}`)
  }, [platform])

  return { platform, isMac: platform === 'mac', isWin: platform === 'win' }
}
