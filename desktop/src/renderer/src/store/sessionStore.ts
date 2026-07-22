import { create } from 'zustand'
import apiClient from '../api/client'
import type { SessionItem } from '../types'

const ACTIVE_KEY = 'lightagent_session_id'

interface SessionState {
  sessions: SessionItem[]
  total: number
  page: number
  hasMore: boolean
  loading: boolean
  activeId: string

  loadSessions: (page?: number) => Promise<void>
  loadMore: () => Promise<void>
  setActive: (id: string) => void
  newSession: () => string
  rename: (id: string, title: string) => Promise<void>
  remove: (id: string) => Promise<void>
}

function genId(): string {
  return `session_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`
}

function readActive(): string {
  return localStorage.getItem(ACTIVE_KEY) || genId()
}

export const useSessionStore = create<SessionState>((set, get) => ({
  sessions: [],
  total: 0,
  page: 1,
  hasMore: false,
  loading: false,
  activeId: readActive(),

  loadSessions: async (page = 1) => {
    set({ loading: true })
    try {
      const res = await apiClient.getSessions(page, 50)
      set((s) => ({
        sessions: page === 1 ? res.sessions : [...s.sessions, ...res.sessions],
        total: res.total,
        page: res.page,
        hasMore: res.has_more,
        loading: false,
      }))
    } catch {
      set({ loading: false })
    }
  },

  loadMore: async () => {
    const { hasMore, loading, page } = get()
    if (!hasMore || loading) return
    await get().loadSessions(page + 1)
  },

  setActive: (id) => {
    localStorage.setItem(ACTIVE_KEY, id)
    set({ activeId: id })
  },

  newSession: () => {
    const id = genId()
    localStorage.setItem(ACTIVE_KEY, id)
    set({ activeId: id })
    return id
  },

  rename: async (id, title) => {
    await apiClient.renameSession(id, title)
    set((s) => ({
      sessions: s.sessions.map((sess) => (sess.session_id === id ? { ...sess, title } : sess)),
    }))
  },

  remove: async (id) => {
    await apiClient.deleteSession(id)
    set((s) => ({ sessions: s.sessions.filter((sess) => sess.session_id !== id) }))
    // If we removed the active one, start a fresh session
    if (get().activeId === id) get().newSession()
  },
}))
