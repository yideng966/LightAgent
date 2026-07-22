import { create } from 'zustand'
import type { UpdateStatus } from '../types'

interface UpdateState {
  status: UpdateStatus | null
  /** Latest available version, kept across download progress updates. */
  version: string | null
  /** Download progress 0-100 while state === 'downloading'. */
  percent: number
  /** User dismissed the badge for this version (don't nag again until next). */
  dismissedVersion: string | null

  setStatus: (s: UpdateStatus) => void
  dismiss: () => void

  // Actions proxied to the main process via the preload bridge.
  download: () => void
  install: () => void
}

export const useUpdateStore = create<UpdateState>((set, get) => ({
  status: null,
  version: null,
  percent: 0,
  dismissedVersion: null,

  setStatus: (s) =>
    set(() => {
      if (s.state === 'available') return { status: s, version: s.version, percent: 0 }
      if (s.state === 'downloading') return { status: s, percent: s.percent }
      if (s.state === 'downloaded') return { status: s, version: s.version, percent: 100 }
      return { status: s }
    }),

  dismiss: () => set((st) => ({ dismissedVersion: st.version })),

  download: () => window.electronAPI?.downloadUpdate?.(),
  install: () => window.electronAPI?.installUpdate?.(),
}))

// Subscribe to main-process update events. Returns an unsubscribe fn.
export function initUpdateListener(): (() => void) | undefined {
  return window.electronAPI?.onUpdateStatus?.((status) => {
    useUpdateStore.getState().setStatus(status as UpdateStatus)
  })
}

// Whether a new version should be surfaced (available/downloading/downloaded
// and not dismissed for that version).
export function hasPendingUpdate(state: UpdateState): boolean {
  const s = state.status
  if (!s) return false
  const active = s.state === 'available' || s.state === 'downloading' || s.state === 'downloaded'
  return active && state.dismissedVersion !== state.version
}
