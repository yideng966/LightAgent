import { create } from 'zustand'
import apiClient from '../api/client'
import type { ChatMessage, MessageStep, Attachment, StreamEvent, HistoryMessage } from '../types'

/**
 * Per-session chat state. Supports parallel sessions: each session keeps its
 * own message list and active stream, so switching sessions never interrupts a
 * background run. The active EventSource lives in `streams` (outside React).
 */

interface SessionRuntime {
  messages: ChatMessage[]
  isStreaming: boolean
  requestId: string | null
  // history pagination
  historyPage: number
  historyHasMore: boolean
  historyLoaded: boolean
}

interface ChatState {
  sessions: Record<string, SessionRuntime>

  getSession: (sid: string) => SessionRuntime
  ensureSession: (sid: string) => void

  send: (sid: string, text: string, attachments: Attachment[]) => Promise<void>
  cancel: (sid: string) => Promise<void>
  regenerate: (sid: string, botMessageId: string) => Promise<void>
  editUserMessage: (sid: string, messageId: string) => { text: string; attachments: Attachment[] } | null
  deleteMessage: (sid: string, userSeq: number, cascade: boolean) => Promise<void>

  loadHistory: (sid: string, page?: number) => Promise<void>
  clearLocal: (sid: string) => void
}

// EventSource instances kept outside the store (not serializable).
const streams: Record<string, EventSource> = {}

const EMPTY: SessionRuntime = {
  messages: [],
  isStreaming: false,
  requestId: null,
  historyPage: 0,
  historyHasMore: false,
  historyLoaded: false,
}

function uid(prefix: string): string {
  return `${prefix}_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`
}

/**
 * History keeps the English cancel marker for the LLM; strip it for display so
 * the bubble shows a clean answer + a dedicated "cancelled" badge instead.
 */
function stripCancelMarker(text: string): string {
  if (!text) return text
  return text
    .replace(/_\(Cancelled by user\)_/g, '')
    .replace(/_\(Cancelled\)_/g, '')
    .trim()
}

/** Convert a backend history message into a UI ChatMessage. */
function historyToMessage(m: HistoryMessage): ChatMessage {
  if (m.role === 'user') {
    return {
      id: uid('user'),
      role: 'user',
      content: m.content,
      timestamp: m.created_at,
      userSeq: m._seq,
    }
  }

  // The backend stores the final answer both as `content` and as the LAST
  // `content` step. Strip that trailing content step so it isn't rendered
  // twice (matches the web console's renderStepsHtml logic).
  const raw = m.steps || []
  let lastContentIdx = -1
  for (let i = raw.length - 1; i >= 0; i--) {
    if (raw[i].type === 'content') {
      lastContentIdx = i
      break
    }
  }
  const steps: MessageStep[] = raw
    .filter((_, i) => i !== lastContentIdx)
    .map((s) => ({ ...s }))
  const finalContent = m.content || (lastContentIdx >= 0 ? raw[lastContentIdx].content || '' : '')

  return {
    id: uid('assistant'),
    role: 'assistant',
    content: finalContent,
    timestamp: m.created_at,
    steps,
    reasoning: m.reasoning,
    kind: m.kind,
    extras: m.extras,
    botSeq: m._seq,
  }
}

export const useChatStore = create<ChatState>((set, get) => {
  // --- helpers operating on a single session immutably ---
  const patchSession = (sid: string, patch: Partial<SessionRuntime>) =>
    set((st) => ({
      sessions: { ...st.sessions, [sid]: { ...(st.sessions[sid] || EMPTY), ...patch } },
    }))

  const patchMessages = (sid: string, fn: (msgs: ChatMessage[]) => ChatMessage[]) =>
    set((st) => {
      const cur = st.sessions[sid] || EMPTY
      return { sessions: { ...st.sessions, [sid]: { ...cur, messages: fn(cur.messages) } } }
    })

  const updateMsg = (sid: string, id: string, fn: (m: ChatMessage) => ChatMessage) =>
    patchMessages(sid, (msgs) => msgs.map((m) => (m.id === id ? fn(m) : m)))

  /** Attach an EventSource for a request and wire all SSE events to a bot message. */
  const attachStream = (sid: string, requestId: string, botId: string) => {
    const es = apiClient.createSSEStream(requestId)
    streams[sid] = es
    let tailTimer: ReturnType<typeof setTimeout> | null = null

    const closeStream = () => {
      if (tailTimer) {
        clearTimeout(tailTimer)
        tailTimer = null
      }
      es.close()
      if (streams[sid] === es) delete streams[sid]
    }

    // Mark the turn as complete: UI becomes interactive again immediately.
    const completeTurn = () => {
      patchSession(sid, { isStreaming: false, requestId: null })
      updateMsg(sid, botId, (m) => ({ ...m, isStreaming: false }))
    }

    const finishStream = () => {
      completeTurn()
      closeStream()
    }

    es.onmessage = (event) => {
      let data: StreamEvent
      try {
        data = JSON.parse(event.data)
      } catch {
        return // keepalive
      }

      switch (data.type) {
        case 'reasoning':
          updateMsg(sid, botId, (m) => ({ ...m, reasoning: (m.reasoning || '') + (data.content || '') }))
          break

        case 'delta':
          updateMsg(sid, botId, (m) => ({ ...m, content: m.content + (data.content || '') }))
          break

        case 'message_end':
          // Freeze accumulated text as a content step when tool calls follow,
          // mirroring the web console's interleaved step model.
          if (data.has_tool_calls) {
            updateMsg(sid, botId, (m) => {
              if (!m.content.trim()) return m
              const steps = [...(m.steps || []), { type: 'content' as const, content: m.content.trim() }]
              return { ...m, steps, content: '' }
            })
          }
          break

        case 'tool_start':
          updateMsg(sid, botId, (m) => {
            // commit any reasoning into a thinking step
            const steps = [...(m.steps || [])]
            if (m.reasoning && m.reasoning.trim()) {
              steps.push({ type: 'thinking', content: m.reasoning.trim() })
            }
            steps.push({
              type: 'tool',
              id: data.tool_call_id,
              name: data.tool,
              arguments: data.arguments,
              status: 'running',
            })
            return { ...m, steps, reasoning: '', content: '' }
          })
          break

        case 'tool_progress':
          updateMsg(sid, botId, (m) => ({
            ...m,
            steps: (m.steps || []).map((s) =>
              s.type === 'tool' && s.id === data.tool_call_id ? { ...s, result: data.content } : s
            ),
          }))
          break

        case 'tool_end':
          updateMsg(sid, botId, (m) => ({
            ...m,
            steps: (m.steps || []).map((s) =>
              s.type === 'tool' && s.id === data.tool_call_id
                ? {
                    ...s,
                    status: data.status,
                    result: data.result ?? s.result,
                    execution_time: data.execution_time,
                    is_error: data.status !== 'success',
                  }
                : s
            ),
          }))
          break

        case 'cancelled':
          updateMsg(sid, botId, (m) => ({ ...m, isCancelled: true }))
          break

        case 'done':
          updateMsg(sid, botId, (m) => {
            const next = stripCancelMarker(data.content || m.content)
            return {
              ...m,
              content: next,
              botSeq: data.bot_seq ?? m.botSeq,
              isStreaming: false,
            }
          })
          // backfill the preceding user message's seq for edit/delete
          if (data.user_seq != null) {
            patchMessages(sid, (msgs) => {
              const idx = msgs.findIndex((m) => m.id === botId)
              for (let i = idx - 1; i >= 0; i--) {
                if (msgs[i].role === 'user') {
                  msgs[i] = { ...msgs[i], userSeq: data.user_seq }
                  break
                }
              }
              return [...msgs]
            })
          }
          // The answer is final: free the UI now (don't wait for onerror).
          completeTurn()
          // Backend keeps the stream open for a short tail (e.g. TTS audio via
          // voice_attach). Close it ourselves if nothing else arrives.
          if (tailTimer) clearTimeout(tailTimer)
          tailTimer = setTimeout(closeStream, 1500)
          break

        case 'voice_attach':
          if (data.audio_url) {
            updateMsg(sid, botId, (m) => ({
              ...m,
              extras: { ...(m.extras || {}), audio: data.audio_url },
            }))
          }
          finishStream()
          break

        case 'error':
          updateMsg(sid, botId, (m) => ({ ...m, error: data.message || 'stream error', isStreaming: false }))
          finishStream()
          break
      }
    }

    es.onerror = () => {
      // Stream closed (often the normal end after `done`/tail). Finalize.
      finishStream()
    }
  }

  return {
    sessions: {},

    getSession: (sid) => get().sessions[sid] || EMPTY,

    ensureSession: (sid) => {
      if (!get().sessions[sid]) patchSession(sid, { ...EMPTY })
    },

    send: async (sid, text, attachments) => {
      const userMsg: ChatMessage = {
        id: uid('user'),
        role: 'user',
        content: text,
        timestamp: Date.now() / 1000,
        attachments: attachments.length ? attachments : undefined,
      }
      const botId = uid('assistant')
      const botMsg: ChatMessage = {
        id: botId,
        role: 'assistant',
        content: '',
        timestamp: Date.now() / 1000,
        steps: [],
        isStreaming: true,
      }
      patchMessages(sid, (msgs) => [...msgs, userMsg, botMsg])
      patchSession(sid, { isStreaming: true })

      try {
        const res = await apiClient.sendMessage(sid, text, {
          stream: true,
          attachments: attachments.length ? attachments : undefined,
        })
        if (res.status === 'success' && res.stream && res.request_id) {
          patchSession(sid, { requestId: res.request_id })
          attachStream(sid, res.request_id, botId)
        } else if (res.inline_reply) {
          updateMsg(sid, botId, (m) => ({ ...m, content: res.inline_reply || '', isStreaming: false }))
          patchSession(sid, { isStreaming: false })
        } else {
          updateMsg(sid, botId, (m) => ({ ...m, error: 'send failed', isStreaming: false }))
          patchSession(sid, { isStreaming: false })
        }
      } catch (err) {
        updateMsg(sid, botId, (m) => ({ ...m, error: `${err}`, isStreaming: false }))
        patchSession(sid, { isStreaming: false })
      }
    },

    cancel: async (sid) => {
      const s = get().sessions[sid]
      if (!s?.requestId) return
      try {
        await apiClient.cancel({ requestId: s.requestId, sessionId: sid })
      } catch {
        /* ignore */
      }
    },

    regenerate: async (sid, botMessageId) => {
      const s = get().sessions[sid] || EMPTY
      const idx = s.messages.findIndex((m) => m.id === botMessageId)
      if (idx < 0) return
      // find the user message that produced this bot reply
      let userMsg: ChatMessage | null = null
      for (let i = idx - 1; i >= 0; i--) {
        if (s.messages[i].role === 'user') {
          userMsg = s.messages[i]
          break
        }
      }
      if (!userMsg) return
      // delete the turn on the backend (by the user's seq) then resend
      if (userMsg.userSeq != null) {
        try {
          await apiClient.deleteMessage({ sessionId: sid, userSeq: userMsg.userSeq, deleteUser: true, cascade: true })
        } catch {
          /* ignore */
        }
      }
      // drop the user+bot messages locally from idx-? : remove from the user msg onward
      const userIdx = s.messages.indexOf(userMsg)
      patchMessages(sid, (msgs) => msgs.slice(0, userIdx))
      await get().send(sid, userMsg.content, userMsg.attachments || [])
    },

    editUserMessage: (sid, messageId) => {
      const s = get().sessions[sid] || EMPTY
      const msg = s.messages.find((m) => m.id === messageId)
      if (!msg || msg.role !== 'user') return null
      const userIdx = s.messages.indexOf(msg)
      // cascade-delete this turn on the backend
      if (msg.userSeq != null) {
        apiClient
          .deleteMessage({ sessionId: sid, userSeq: msg.userSeq, deleteUser: true, cascade: true })
          .catch(() => {})
      }
      patchMessages(sid, (msgs) => msgs.slice(0, userIdx))
      return { text: msg.content, attachments: msg.attachments || [] }
    },

    deleteMessage: async (sid, userSeq, cascade) => {
      try {
        await apiClient.deleteMessage({ sessionId: sid, userSeq, deleteUser: true, cascade })
      } catch {
        /* ignore */
      }
      // reload history to reflect server state
      await get().loadHistory(sid, 1)
    },

    loadHistory: async (sid, page = 1) => {
      try {
        const res = await apiClient.getHistory(sid, page, 20)
        const uiMsgs = res.messages.map(historyToMessage)
        patchSession(sid, {
          historyPage: res.page,
          historyHasMore: res.has_more,
          historyLoaded: true,
        })
        if (page === 1) {
          patchMessages(sid, () => uiMsgs)
        } else {
          // older page: prepend
          patchMessages(sid, (msgs) => [...uiMsgs, ...msgs])
        }
      } catch {
        patchSession(sid, { historyLoaded: true })
      }
    },

    clearLocal: (sid) => {
      const es = streams[sid]
      if (es) {
        es.close()
        delete streams[sid]
      }
      patchSession(sid, { ...EMPTY })
    },
  }
})
