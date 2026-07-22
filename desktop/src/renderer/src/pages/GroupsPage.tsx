import React, { useEffect, useMemo, useRef, useState } from 'react'
import {
  Check,
  ChevronDown,
  Loader2,
  MessageCircle,
  RefreshCw,
  Search,
  Settings2,
  SlidersHorizontal,
  UserRound,
  X,
} from 'lucide-react'
import { t } from '../i18n'
import apiClient from '../api/client'
import type { ChannelInfo, WechatGroupRoom } from '../types'
import { Btn, Toggle } from './settings/primitives'

interface GroupsPageProps {
  baseUrl: string
}

type SectionKey = 'basic' | 'rooms' | 'persona'

const WECHAT_GROUP_CUSTOM_PERSONA = 'custom'
const WECHAT_GROUP_PENDING_ROOM_STATUSES = new Set(['suspected', 'legacy_imported', 'conflict', 'identity_unresolved'])

const isSelectableWechatGroupRoom = (room: WechatGroupRoom): boolean =>
  !!String(room.stable_room_id || '').trim() &&
  room.identity_requires_confirmation !== true &&
  !WECHAT_GROUP_PENDING_ROOM_STATUSES.has(String(room.binding_status || '').trim())

const splitLines = (value: string): string[] =>
  value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean)

const sameSet = (a: string[], b: string[]) => {
  if (a.length !== b.length) return false
  const left = [...a].sort()
  const right = [...b].sort()
  return left.every((item, idx) => item === right[idx])
}

const GroupsPage: React.FC<GroupsPageProps> = ({ baseUrl }) => {
  const [section, setSection] = useState<SectionKey>('basic')
  const [channel, setChannel] = useState<ChannelInfo | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [status, setStatus] = useState<{ text: string; error: boolean } | null>(null)

  const [rooms, setRooms] = useState<WechatGroupRoom[]>([])
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [selectedNames, setSelectedNames] = useState<string[]>([])
  const [personaPrompt, setPersonaPrompt] = useState('')
  const [recentEnabled, setRecentEnabled] = useState(true)
  const [recentLimit, setRecentLimit] = useState(20)
  const [recentMinutes, setRecentMinutes] = useState(60)

  const extra = channel?.extra
  const maxLength = extra?.persona.max_length || 6000
  const active = !!channel?.active
  const loginStatus = channel?.login_status || ''

  const load = async () => {
    setLoading(true)
    setStatus(null)
    try {
      apiClient.setBaseUrl(baseUrl)
      const channels = await apiClient.getChannels()
      const wechatGroup = channels.find((item) => item.name === 'wechat_group') || null
      setChannel(wechatGroup)
      const nextExtra = wechatGroup?.extra
      setRooms(nextExtra?.rooms || [])
      setSelectedIds(nextExtra?.selected_room_ids || [])
      setSelectedNames(nextExtra?.selected_room_names || [])
      setPersonaPrompt(nextExtra?.persona.prompt || '')
      setRecentEnabled(nextExtra?.recent_context?.enabled ?? true)
      setRecentLimit(nextExtra?.recent_context?.limit ?? 20)
      setRecentMinutes(nextExtra?.recent_context?.minutes ?? 60)
    } catch {
      setStatus({ text: t('groups_load_failed'), error: true })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [baseUrl])

  const dirty = useMemo(() => {
    const saved = extra
    if (!saved) return false
    return (
      !sameSet(selectedIds, saved.selected_room_ids || []) ||
      !sameSet(selectedNames, saved.selected_room_names || []) ||
      personaPrompt !== (saved.persona.prompt || '') ||
      recentEnabled !== (saved.recent_context?.enabled ?? true) ||
      recentLimit !== (saved.recent_context?.limit ?? 20) ||
      recentMinutes !== (saved.recent_context?.minutes ?? 60)
    )
  }, [extra, personaPrompt, recentEnabled, recentLimit, recentMinutes, selectedIds, selectedNames])

  const save = async () => {
    setBusy(true)
    setStatus(null)
    try {
      const selectableRooms = rooms.filter(isSelectableWechatGroupRoom)
      const selectableIds = new Set(selectableRooms.map((room) => room.id))
      const selectedStableRoomIds = selectedIds.filter((id) => selectableIds.has(id))
      const runtimeRoomIdByStableId = new Map(selectableRooms.map((room) => [room.id, room.runtime_room_id || room.id]))
      const selectedRuntimeRoomIds = selectedStableRoomIds.map((id) => runtimeRoomIdByStableId.get(id) || '').filter(Boolean)
      const res = await apiClient.channelAction('save', 'wechat_group', {
        wechat_group_stable_room_ids: selectedStableRoomIds,
        wechat_group_room_ids: selectedRuntimeRoomIds,
        wechat_group_names: selectedNames,
        wechat_group_persona_prompt: personaPrompt,
        wechat_group_persona_preset_id: WECHAT_GROUP_CUSTOM_PERSONA,
        wechat_group_recent_context_enabled: recentEnabled,
        wechat_group_recent_context_limit: recentLimit,
        wechat_group_recent_context_minutes: recentMinutes,
      })
      if (res.status !== 'success') {
        setStatus({ text: (res.message as string) || t('channels_save_error'), error: true })
        return
      }
      setStatus({ text: t('wechat_group_settings_saved'), error: false })
      await load()
    } catch {
      setStatus({ text: t('channels_save_error'), error: true })
    } finally {
      setBusy(false)
    }
  }

  const refreshRooms = async () => {
    setRefreshing(true)
    setStatus(null)
    try {
      const data = await apiClient.wechatGroupQrAction('refresh')
      if (data.status !== 'success') {
        setStatus({ text: (data.message as string) || t('wechat_group_rooms_refresh_failed'), error: true })
        return
      }
      const nextRooms = Array.isArray(data.rooms) ? (data.rooms as WechatGroupRoom[]) : rooms
      setRooms(nextRooms)
      setStatus({ text: t('wechat_group_rooms_refreshed'), error: false })
    } catch {
      setStatus({ text: t('wechat_group_rooms_refresh_failed'), error: true })
    } finally {
      setRefreshing(false)
    }
  }

  return (
    <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
      <div className="px-6 pt-5 pb-3 flex-shrink-0 flex items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-content">{t('groups_title')}</h2>
          <p className="text-xs text-content-tertiary mt-1">{t('groups_desc')}</p>
        </div>
        <div className="flex items-center gap-3">
          {status && (
            <span
              className={`text-xs max-w-[280px] truncate ${status.error ? 'text-danger' : 'text-accent'}`}
              title={status.text}
            >
              {status.text}
            </span>
          )}
          <Btn variant="primary" onClick={save} disabled={loading || busy || !dirty}>
            <span className="inline-flex items-center gap-1.5">
              {busy && <Loader2 size={14} className="animate-spin" />}
              {t('wechat_group_settings_save')}
            </span>
          </Btn>
        </div>
      </div>

      <div className="flex-1 min-h-0 border-t border-default overflow-hidden">
        {loading ? (
          <div className="h-full flex items-center justify-center text-content-tertiary">
            <Loader2 size={18} className="animate-spin mr-2" />
            {t('groups_loading')}
          </div>
        ) : (
          <div className="h-full flex min-h-0">
            <aside className="w-60 flex-shrink-0 border-r border-default p-3 space-y-1">
              <SectionButton
                icon={SlidersHorizontal}
                label={t('groups_nav_basic')}
                hint={t('groups_nav_basic_hint')}
                active={section === 'basic'}
                onClick={() => setSection('basic')}
              />
              <SectionButton
                icon={MessageCircle}
                label={t('groups_nav_rooms')}
                hint={t('groups_nav_rooms_hint')}
                active={section === 'rooms'}
                onClick={() => setSection('rooms')}
              />
              <SectionButton
                icon={UserRound}
                label={t('groups_nav_persona')}
                hint={t('groups_nav_persona_hint')}
                active={section === 'persona'}
                onClick={() => setSection('persona')}
              />
              <div className="pt-3 mt-3 border-t border-subtle">
                <div className="rounded-btn border border-default bg-inset px-3 py-2">
                  <div className="flex items-center gap-2 text-xs font-medium text-content">
                    <span className={`h-2 w-2 rounded-full ${active ? 'bg-accent' : 'bg-content-tertiary'}`} />
                    {active ? t('channels_connected') : t('channels_disconnected')}
                  </div>
                  <p className="text-[11px] text-content-tertiary mt-1 truncate" title={loginStatus || t('groups_status_idle')}>
                    {loginStatus || t('groups_status_idle')}
                  </p>
                </div>
              </div>
            </aside>

            <main className="flex-1 min-w-0 h-full overflow-y-auto px-6 py-5">
              {section === 'basic' && (
                <BasicSettings
                  enabled={recentEnabled}
                  limit={recentLimit}
                  minutes={recentMinutes}
                  onEnabled={setRecentEnabled}
                  onLimit={setRecentLimit}
                  onMinutes={setRecentMinutes}
                />
              )}
              {section === 'rooms' && (
                <RoomSettings
                  rooms={rooms}
                  selectedIds={selectedIds}
                  selectedNames={selectedNames}
                  refreshing={refreshing}
                  onRefresh={refreshRooms}
                  onSelectedIds={setSelectedIds}
                  onSelectedNames={setSelectedNames}
                />
              )}
              {section === 'persona' && (
                <PersonaSettings prompt={personaPrompt} maxLength={maxLength} onPrompt={setPersonaPrompt} />
              )}
            </main>
          </div>
        )}
      </div>
    </div>
  )
}

const SectionButton: React.FC<{
  icon: React.ComponentType<{ size?: number }>
  label: string
  hint: string
  active: boolean
  onClick: () => void
}> = ({ icon: Icon, label, hint, active, onClick }) => (
  <button
    type="button"
    onClick={onClick}
    className={`w-full text-left rounded-btn px-3 py-2.5 cursor-pointer transition-colors ${
      active ? 'bg-accent-soft text-accent' : 'text-content-secondary hover:bg-surface-2 hover:text-content'
    }`}
  >
    <span className="flex items-center gap-2 text-sm font-medium">
      <Icon size={15} />
      {label}
    </span>
    <span className="block text-xs text-content-tertiary mt-1 truncate">{hint}</span>
  </button>
)

const PanelTitle: React.FC<{ icon: React.ComponentType<{ size?: number }>; title: string; desc: string }> = ({
  icon: Icon,
  title,
  desc,
}) => (
  <div className="flex items-start gap-3 mb-5">
    <span className="w-9 h-9 rounded-btn bg-accent-soft text-accent flex items-center justify-center flex-shrink-0">
      <Icon size={17} />
    </span>
    <div className="min-w-0">
      <h3 className="text-base font-semibold text-content">{title}</h3>
      <p className="text-xs text-content-tertiary mt-1">{desc}</p>
    </div>
  </div>
)

const BasicSettings: React.FC<{
  enabled: boolean
  limit: number
  minutes: number
  onEnabled: (v: boolean) => void
  onLimit: (v: number) => void
  onMinutes: (v: number) => void
}> = ({ enabled, limit, minutes, onEnabled, onLimit, onMinutes }) => (
  <div className="h-full w-full">
    <PanelTitle icon={Settings2} title={t('groups_basic_title')} desc={t('groups_basic_desc')} />
    <div className="grid grid-cols-1 xl:grid-cols-[minmax(280px,1fr)_minmax(220px,0.7fr)_minmax(220px,0.7fr)] gap-4">
      <div className="rounded-card border border-default bg-surface p-4">
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <h4 className="text-sm font-medium text-content">{t('groups_recent_enabled')}</h4>
            <p className="text-xs text-content-tertiary mt-1">{t('groups_recent_enabled_hint')}</p>
          </div>
          <Toggle checked={enabled} onChange={onEnabled} />
        </div>
      </div>
      <NumberField
        label={t('groups_recent_limit')}
        hint={t('groups_recent_limit_hint')}
        value={limit}
        min={1}
        onChange={onLimit}
      />
      <NumberField
        label={t('groups_recent_minutes')}
        hint={t('groups_recent_minutes_hint')}
        value={minutes}
        min={1}
        onChange={onMinutes}
      />
    </div>
  </div>
)

const NumberField: React.FC<{
  label: string
  hint: string
  value: number
  min: number
  onChange: (v: number) => void
}> = ({ label, hint, value, min, onChange }) => (
  <label className="rounded-card border border-default bg-surface p-4 block">
    <span className="text-sm font-medium text-content">{label}</span>
    <span className="block text-xs text-content-tertiary mt-1">{hint}</span>
    <input
      type="number"
      min={min}
      value={value}
      onChange={(event) => onChange(Math.max(min, Number(event.target.value || min)))}
      className="mt-3 w-full px-3 py-2 rounded-btn border border-strong bg-inset text-sm text-content focus:outline-none focus:border-accent transition-colors"
    />
  </label>
)

const RoomSettings: React.FC<{
  rooms: WechatGroupRoom[]
  selectedIds: string[]
  selectedNames: string[]
  refreshing: boolean
  onRefresh: () => void
  onSelectedIds: (v: string[]) => void
  onSelectedNames: (v: string[]) => void
}> = ({ rooms, selectedIds, selectedNames, refreshing, onRefresh, onSelectedIds, onSelectedNames }) => {
  const roomNameById = useMemo(() => new Map(rooms.map((room) => [room.id, room.name || t('groups_room_unnamed')])), [rooms])
  const selectedLabels = selectedIds.map((id, index) => roomNameById.get(id) || t('groups_room_saved').replace('{n}', String(index + 1)))

  return (
    <div className="h-full w-full flex flex-col min-h-0">
      <div className="flex items-start justify-between gap-4 mb-5 flex-shrink-0">
        <PanelTitle icon={MessageCircle} title={t('groups_rooms_title')} desc={t('groups_rooms_desc')} />
        <Btn variant="ghost" onClick={onRefresh} disabled={refreshing}>
          <span className="flex items-center gap-1.5">
            <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
            {t('wechat_group_rooms_refresh')}
          </span>
        </Btn>
      </div>

      <div className="flex-1 min-h-0 grid grid-cols-1 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.65fr)] gap-4">
        <div className="rounded-card border border-default bg-surface p-4 flex flex-col gap-3 min-h-0">
          <label className="block text-sm font-medium text-content">{t('groups_rooms_select_label')}</label>
          <RoomMultiSelect rooms={rooms} selectedIds={selectedIds} onChange={onSelectedIds} />
          <div className="flex-1 min-h-[160px] max-h-[420px] overflow-y-auto rounded-btn border border-default bg-inset p-2">
            {selectedLabels.length ? (
              <div className="flex flex-wrap gap-1.5">
                {selectedLabels.map((label, idx) => (
                  <span
                    key={`${label}-${idx}`}
                    className="inline-flex items-center gap-1 rounded-md bg-surface-2 px-2 py-1 text-xs text-content-secondary max-w-full"
                  >
                    <span className="truncate">{label}</span>
                    <button
                      type="button"
                      onClick={() => onSelectedIds(selectedIds.filter((_, itemIdx) => itemIdx !== idx))}
                      className="text-content-tertiary hover:text-content cursor-pointer"
                      title={t('groups_rooms_remove')}
                    >
                      <X size={12} />
                    </button>
                  </span>
                ))}
              </div>
            ) : (
              <p className="text-xs text-content-tertiary">{t('groups_rooms_none_selected')}</p>
            )}
          </div>
        </div>

        <div className="rounded-card border border-default bg-surface p-4 flex flex-col min-h-0">
          <label className="block text-sm font-medium text-content mb-1.5">{t('wechat_group_room_names_label')}</label>
          <textarea
            value={selectedNames.join('\n')}
            onChange={(event) => onSelectedNames(splitLines(event.target.value))}
            rows={10}
            className="flex-1 min-h-[220px] w-full px-3 py-2 rounded-btn border border-strong bg-inset text-sm text-content placeholder:text-content-tertiary focus:outline-none focus:border-accent font-mono transition-colors resize-none"
            placeholder={t('wechat_group_room_names_placeholder')}
          />
          <p className="text-xs text-content-tertiary mt-2">{t('groups_rooms_fallback_hint')}</p>
        </div>
      </div>
    </div>
  )
}

const RoomMultiSelect: React.FC<{
  rooms: WechatGroupRoom[]
  selectedIds: string[]
  onChange: (ids: string[]) => void
}> = ({ rooms, selectedIds, onChange }) => {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onDoc = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [open])

  const visible = rooms.filter((room) => (room.name || '').toLowerCase().includes(query.trim().toLowerCase()))
  const label = selectedIds.length
    ? t('groups_rooms_selected_count').replace('{count}', String(selectedIds.length))
    : t('groups_rooms_select_placeholder')

  const toggle = (room: WechatGroupRoom) => {
    if (!isSelectableWechatGroupRoom(room)) return
    onChange(selectedIds.includes(room.id) ? selectedIds.filter((id) => id !== room.id) : [...selectedIds, room.id])
  }

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={`w-full h-10 px-3 rounded-btn border bg-inset text-sm text-content flex items-center justify-between gap-2 cursor-pointer transition-colors ${
          open ? 'border-accent ring-2 ring-accent/15' : 'border-strong hover:border-content-tertiary'
        }`}
      >
        <span className={selectedIds.length ? 'text-content' : 'text-content-tertiary'}>{label}</span>
        <ChevronDown size={14} className={`text-content-tertiary transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div className="absolute left-0 right-0 top-[calc(100%+4px)] z-50 rounded-btn border border-default bg-elevated shadow-lg p-2">
          <div className="relative mb-2">
            <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-content-tertiary" />
            <input
              autoFocus
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={t('groups_rooms_search_placeholder')}
              className="w-full pl-8 pr-3 py-2 rounded-btn border border-strong bg-inset text-sm text-content placeholder:text-content-tertiary focus:outline-none focus:border-accent transition-colors"
            />
          </div>
          <div className="max-h-64 overflow-y-auto space-y-1">
            {visible.length ? (
              visible.map((room) => {
                const selectable = isSelectableWechatGroupRoom(room)
                const checked = selectable && selectedIds.includes(room.id)
                return (
                  <button
                    type="button"
                    key={room.id}
                    disabled={!selectable}
                    onClick={() => toggle(room)}
                    className={`w-full flex items-center gap-2 px-2.5 py-2 rounded-md text-sm transition-colors ${
                      selectable ? 'cursor-pointer' : 'cursor-not-allowed opacity-60'
                    } ${
                      checked ? 'bg-accent-soft text-accent' : 'text-content-secondary hover:bg-surface-2'
                    }`}
                  >
                    <span className="flex-1 min-w-0 text-left">
                      <span className="block truncate">{room.name || t('groups_room_unnamed')}</span>
                      {(room.runtime_room_id || room.binding_status) && (
                        <span className="block text-[11px] text-content-tertiary truncate">
                          {room.binding_status || 'runtime'} · {room.runtime_room_id || room.id}
                        </span>
                      )}
                    </span>
                    {checked && <Check size={14} className="flex-shrink-0" />}
                  </button>
                )
              })
            ) : (
              <p className="px-2 py-4 text-center text-xs text-content-tertiary">
                {rooms.length ? t('groups_rooms_no_match') : t('wechat_group_rooms_empty')}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

const PersonaSettings: React.FC<{
  prompt: string
  maxLength: number
  onPrompt: (v: string) => void
}> = ({ prompt, maxLength, onPrompt }) => (
  <div className="h-full w-full flex flex-col min-h-0">
    <PanelTitle icon={UserRound} title={t('groups_persona_title')} desc={t('groups_persona_desc')} />
    <div className="rounded-card border border-default bg-surface p-4 flex flex-col flex-1 min-h-0">
      <label className="block text-sm font-medium text-content mb-1.5">{t('wechat_group_persona_prompt_label')}</label>
      <textarea
        value={prompt}
        maxLength={maxLength}
        onChange={(event) => onPrompt(event.target.value)}
        rows={16}
        className="flex-1 min-h-[360px] w-full px-3 py-2 rounded-btn border border-strong bg-inset text-sm text-content placeholder:text-content-tertiary focus:outline-none focus:border-accent transition-colors resize-none"
        placeholder={t('wechat_group_persona_prompt_placeholder')}
      />
      <div className="flex items-center justify-between gap-3 mt-2">
        <p className="text-xs text-content-tertiary">{t('wechat_group_persona_boundary')}</p>
        <span className="text-xs text-content-tertiary tabular-nums">
          {prompt.length}/{maxLength}
        </span>
      </div>
    </div>
  </div>
)

export default GroupsPage
