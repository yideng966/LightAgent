import React, { useEffect, useMemo, useState } from 'react'
import { Plus, MessageSquare, Pencil, Trash2, Check, X, History } from 'lucide-react'
import { t } from '../i18n'
import { useSessionStore } from '../store/sessionStore'
import { useUIStore } from '../store/uiStore'
import { usePlatform } from '../hooks/usePlatform'
import type { SessionItem } from '../types'

function groupByTime(sessions: SessionItem[]): { label: string; items: SessionItem[] }[] {
  const now = new Date()
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime() / 1000
  const startOfYesterday = startOfToday - 86400

  const today: SessionItem[] = []
  const yesterday: SessionItem[] = []
  const earlier: SessionItem[] = []

  for (const s of sessions) {
    const ts = s.last_active || s.created_at
    if (ts >= startOfToday) today.push(s)
    else if (ts >= startOfYesterday) yesterday.push(s)
    else earlier.push(s)
  }

  return [
    { label: t('session_today'), items: today },
    { label: t('session_yesterday'), items: yesterday },
    { label: t('session_earlier'), items: earlier },
  ].filter((g) => g.items.length > 0)
}

const SessionList: React.FC = () => {
  const { sessions, activeId, loading, loadSessions, loadMore, hasMore, setActive, newSession, rename, remove } =
    useSessionStore()
  const toggleSessions = useUIStore((s) => s.toggleSessions)
  const navCollapsed = useUIStore((s) => s.navCollapsed)
  const { isMac } = usePlatform()
  // When the nav rail is collapsed on macOS, the native traffic lights spill
  // past it, so nudge the history button right to keep it (and its sibling in
  // the main header) clear of the lights and aligned across states.
  const trafficOffset = isMac && navCollapsed ? 'ml-2' : ''
  // Nudge header buttons down a touch to sit level with the macOS traffic lights.
  const trafficDrop = isMac ? 'mt-1' : ''
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editValue, setEditValue] = useState('')

  useEffect(() => {
    loadSessions(1)
  }, [loadSessions])

  const groups = useMemo(() => groupByTime(sessions), [sessions])

  const startEdit = (s: SessionItem) => {
    setEditingId(s.session_id)
    setEditValue(s.title || '')
  }

  const commitEdit = async () => {
    if (editingId && editValue.trim()) {
      await rename(editingId, editValue.trim())
    }
    setEditingId(null)
  }

  return (
    <div className="w-[240px] flex-shrink-0 flex flex-col h-full bg-surface border-r border-default">
      {/* Header */}
      <div className="flex items-center justify-between px-2 h-[44px] flex-shrink-0 titlebar-drag border-b border-default">
        <button
          onClick={toggleSessions}
          title={t('session_history')}
          className={`titlebar-no-drag inline-flex items-center justify-center w-7 h-7 rounded-btn text-content-tertiary hover:text-content hover:bg-surface-2 cursor-pointer transition-colors ${trafficDrop} ${trafficOffset}`}
        >
          <History size={16} />
        </button>
        <button
          onClick={() => newSession()}
          title={t('session_new')}
          className={`titlebar-no-drag inline-flex items-center gap-1.5 px-2.5 h-7 rounded-btn text-[12px] font-medium text-accent hover:bg-accent-soft cursor-pointer transition-colors ${trafficDrop}`}
        >
          <Plus size={15} />
          {t('session_new')}
        </button>
      </div>

      {/* List */}
      <div
        className="flex-1 overflow-y-auto px-2 pb-2"
        onScroll={(e) => {
          const el = e.currentTarget
          if (el.scrollHeight - el.scrollTop - el.clientHeight < 80 && hasMore && !loading) loadMore()
        }}
      >
        {sessions.length === 0 && !loading && (
          <div className="flex flex-col items-center justify-center h-40 text-center px-4">
            <MessageSquare size={22} className="text-content-disabled mb-2" />
            <p className="text-xs text-content-tertiary">{t('session_empty')}</p>
          </div>
        )}

        {groups.map((group) => (
          <div key={group.label} className="mb-2">
            <div className="px-2 pt-2 pb-1 text-[11px] font-medium uppercase tracking-wide text-content-disabled">
              {group.label}
            </div>
            {group.items.map((s) => {
              const isActive = s.session_id === activeId
              const isEditing = editingId === s.session_id
              return (
                <div
                  key={s.session_id}
                  onClick={() => !isEditing && setActive(s.session_id)}
                  className={`group flex items-center gap-2 px-2 h-9 rounded-btn cursor-pointer transition-colors ${
                    isActive ? 'bg-accent-soft' : 'hover:bg-surface-2'
                  }`}
                >
                  {isEditing ? (
                    <input
                      autoFocus
                      value={editValue}
                      onChange={(e) => setEditValue(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') commitEdit()
                        if (e.key === 'Escape') setEditingId(null)
                      }}
                      onClick={(e) => e.stopPropagation()}
                      className="flex-1 min-w-0 bg-inset border border-strong rounded px-1.5 py-0.5 text-[13px] text-content focus:outline-none focus:border-accent"
                    />
                  ) : (
                    <span
                      className={`flex-1 min-w-0 truncate text-[13px] ${
                        isActive ? 'text-accent font-medium' : 'text-content-secondary'
                      }`}
                    >
                      {s.title || s.session_id}
                    </span>
                  )}

                  {isEditing ? (
                    <div className="flex items-center gap-0.5">
                      <IconBtn onClick={(e) => { e.stopPropagation(); commitEdit() }}><Check size={13} /></IconBtn>
                      <IconBtn onClick={(e) => { e.stopPropagation(); setEditingId(null) }}><X size={13} /></IconBtn>
                    </div>
                  ) : (
                    <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                      <IconBtn onClick={(e) => { e.stopPropagation(); startEdit(s) }} title={t('session_rename')}>
                        <Pencil size={13} />
                      </IconBtn>
                      <IconBtn onClick={(e) => { e.stopPropagation(); remove(s.session_id) }} title={t('session_delete')} danger>
                        <Trash2 size={13} />
                      </IconBtn>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        ))}

        {loading && (
          <div className="px-2 py-2 space-y-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="skeleton h-7 w-full" />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

const IconBtn: React.FC<{
  onClick: (e: React.MouseEvent) => void
  title?: string
  danger?: boolean
  children: React.ReactNode
}> = ({ onClick, title, danger, children }) => (
  <button
    onClick={onClick}
    title={title}
    className={`inline-flex items-center justify-center w-6 h-6 rounded cursor-pointer transition-colors text-content-tertiary ${
      danger ? 'hover:text-danger hover:bg-danger-soft' : 'hover:text-content hover:bg-surface'
    }`}
  >
    {children}
  </button>
)

export default SessionList
