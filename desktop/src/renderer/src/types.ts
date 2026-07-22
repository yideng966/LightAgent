// ============================================================
// Electron bridge
// ============================================================

export interface ElectronAPI {
  getBackendPort: () => Promise<number | null>
  getBackendStatus: () => Promise<string>
  restartBackend: () => Promise<boolean>
  selectDirectory: () => Promise<string | null>
  selectFile: (filters?: { name: string; extensions: string[] }[]) => Promise<string | null>
  // Listener registrars return an unsubscribe fn for cleanup.
  onBackendStatus: (callback: (data: BackendStatusEvent) => void) => () => void
  onBackendLog: (callback: (line: string) => void) => () => void
  windowMinimize: () => Promise<void>
  windowMaximize: () => Promise<boolean>
  windowClose: () => Promise<void>
  windowIsMaximized: () => Promise<boolean>
  onMaximizeChange: (callback: (maximized: boolean) => void) => () => void
  onMenuAction?: (callback: (action: string) => void) => () => void
  // Current app version string (e.g. "0.0.5").
  getAppVersion?: () => Promise<string>
  // Auto-update
  checkForUpdate?: () => Promise<void>
  downloadUpdate?: () => Promise<void>
  installUpdate?: () => Promise<void>
  onUpdateStatus?: (callback: (status: UpdateStatus) => void) => () => void
  platform: string
  // OS UI language (e.g. "zh-CN"); used to default the language on first run.
  systemLocale?: string
}

// Mirrors UpdateStatus in src/main/updater.ts.
export type UpdateStatus =
  | { state: 'checking' }
  | { state: 'available'; version: string; notes?: string }
  | { state: 'not-available' }
  | { state: 'downloading'; percent: number }
  | { state: 'downloaded'; version: string }
  | { state: 'error'; message: string }

export interface BackendStatusEvent {
  status: 'ready' | 'error' | 'starting'
  port?: number
  error?: string
}

// ============================================================
// Chat / messages / streaming
// ============================================================

export type Role = 'user' | 'assistant'

/** A single ordered step inside an assistant turn (matches backend history). */
export interface MessageStep {
  type: 'thinking' | 'content' | 'tool'
  content?: string
  // tool step fields
  id?: string
  name?: string
  arguments?: Record<string, unknown>
  result?: string
  is_error?: boolean
  status?: string
  execution_time?: number
}

/** Local UI message model (superset of backend history message). */
export interface ChatMessage {
  id: string
  role: Role
  content: string
  /** Unix seconds. Backend history uses `created_at`; we normalize to `timestamp`. */
  timestamp: number
  attachments?: Attachment[]
  /** Ordered steps (thinking / content / tool). Preferred over legacy toolCalls. */
  steps?: MessageStep[]
  /** Legacy live-stream tool events (kept for backward compat during streaming). */
  toolCalls?: ToolCall[]
  /** Reasoning text streamed via `reasoning` SSE events. */
  reasoning?: string
  /** Sequence numbers from backend (for delete/regenerate). */
  userSeq?: number
  botSeq?: number
  /** Self-evolution bubble flag. */
  kind?: 'evolution'
  extras?: Record<string, unknown>
  isStreaming?: boolean
  isCancelled?: boolean
  error?: string
}

export interface Attachment {
  file_path: string
  file_name: string
  file_type: 'image' | 'video' | 'file' | 'directory'
  preview_url?: string
}

/** Live tool event during SSE streaming. */
export interface ToolCall {
  type: 'tool_start' | 'tool_end' | 'tool_progress'
  tool: string
  tool_call_id?: string
  arguments?: Record<string, unknown>
  result?: string
  status?: string
  execution_time?: number
}

/** All SSE event types emitted on /stream. */
export type StreamEventType =
  | 'delta'
  | 'reasoning'
  | 'tool_start'
  | 'tool_progress'
  | 'tool_end'
  | 'message_end'
  | 'phase'
  | 'file_to_send'
  | 'image'
  | 'video'
  | 'file'
  | 'text'
  | 'done'
  | 'cancelled'
  | 'voice_attach'
  | 'error'

export interface StreamEvent {
  type: StreamEventType
  content?: string
  tool?: string
  tool_call_id?: string
  arguments?: Record<string, unknown>
  status?: string
  result?: string
  execution_time?: number
  has_tool_calls?: boolean
  path?: string
  file_name?: string
  file_type?: string
  web_url?: string
  audio_url?: string
  request_id?: string
  timestamp?: number
  user_seq?: number
  bot_seq?: number
  message?: string
}

// ============================================================
// Sessions / history
// ============================================================

export interface SessionItem {
  session_id: string
  title: string
  created_at: number
  last_active: number
  msg_count: number
}

export interface SessionsPage {
  sessions: SessionItem[]
  total: number
  page: number
  page_size: number
  has_more: boolean
}

/** Backend history message (as returned by /api/history). */
export interface HistoryMessage {
  role: Role
  content: string
  created_at: number
  steps?: MessageStep[]
  tool_calls?: Array<{ id?: string; name: string; arguments?: Record<string, unknown>; result?: string }>
  reasoning?: string
  kind?: 'evolution'
  extras?: Record<string, unknown>
  /** Per-message sequence number used by delete/regenerate APIs. */
  _seq?: number
}

export interface HistoryPage {
  messages: HistoryMessage[]
  total: number
  page: number
  page_size: number
  has_more: boolean
  context_start_seq?: number
}

// ============================================================
// Config
// ============================================================

/** A label that may be localized (some providers/channels return {zh,en}). */
export type LocalizedLabel = string | { zh: string; en: string }

export interface ProviderMeta {
  label: LocalizedLabel
  models: string[]
  api_base_key?: string | null
  api_base_default?: string | null
  api_base_placeholder?: string
  api_key_field?: string | null
  [k: string]: unknown
}

export interface ConfigData {
  use_agent: boolean
  title: string
  model: string
  bot_type: string
  use_linkai: boolean
  channel_type: string
  agent_max_context_tokens: number
  agent_max_context_turns: number
  agent_max_steps: number
  enable_thinking?: boolean
  self_evolution_enabled?: boolean
  api_bases: Record<string, string>
  api_keys: Record<string, string>
  providers: Record<string, ProviderMeta>
  web_password_masked?: string
}

// ============================================================
// Models console (/api/models)
// ============================================================

// A model/voice entry can be a bare id or an annotated {value, hint} object.
export interface ModelOption {
  value: string
  hint?: string
}
export type ModelEntry = string | ModelOption

export interface ModelProvider {
  id: string
  label: LocalizedLabel
  configured: boolean
  is_custom: boolean
  custom_id?: string
  custom_name?: string
  active?: boolean
  api_key_field?: string | null
  api_base_field?: string | null
  api_key_masked?: string
  api_base?: string
  api_base_default?: string
  api_base_placeholder?: string
  models: ModelEntry[]
}

export type CapabilityKey = 'chat' | 'vision' | 'asr' | 'tts' | 'embedding' | 'image' | 'search'

// Search providers are described as objects (unlike other capabilities which
// list provider ids only).
export interface SearchProviderMeta {
  id: string
  label: LocalizedLabel
  configured: boolean
  needs_dedicated_key: boolean
  api_key_masked?: string
}

export interface CapabilityState {
  editable?: boolean
  current_provider?: string
  current_model?: string
  current_voice?: string
  current_dim?: number | null
  suggested_provider?: string
  providers?: string[]
  // provider_models entries are string | {value,hint}
  provider_models?: Record<string, ModelEntry[]>
  // tts only: voices keyed by provider; linkai keyed further by model id
  provider_voices?: Record<string, ModelEntry[] | Record<string, ModelEntry[]>>
  // vision/image
  strategy?: string
  user_specified_model?: string
  fallback_provider?: string
  fallback_model?: string
  // tts
  reply_mode?: 'off' | 'voice_if_voice' | 'always'
  use_linkai?: boolean
  // image
  runtime_active?: boolean
  note?: string
  // search
  fixed_provider?: string
  configured_providers?: string[]
  available?: boolean
  [k: string]: unknown
}

export interface SearchCapabilityState {
  editable?: boolean
  providers: SearchProviderMeta[]
  strategy?: 'auto' | 'fixed' | string
  current_provider?: string
  fixed_provider?: string
  configured_providers?: string[]
  available?: boolean
}

export interface ModelsData {
  status?: string
  providers: ModelProvider[]
  capabilities: {
    chat: CapabilityState
    vision: CapabilityState
    asr: CapabilityState
    tts: CapabilityState
    embedding: CapabilityState
    image: CapabilityState
    // search has a richer providers[] shape
    search: SearchCapabilityState
  }
}

export type ModelsAction =
  | { action: 'set_provider'; provider_id: string; api_key?: string; api_base?: string }
  | { action: 'delete_provider'; provider_id: string }
  | { action: 'set_custom_provider'; name: string; id?: string; api_base: string; api_key?: string; model?: string; make_active?: boolean }
  | { action: 'delete_custom_provider'; id: string }
  | { action: 'set_active_custom_provider'; id: string }
  | { action: 'set_capability'; capability: CapabilityKey; provider_id?: string; model?: string; voice?: string; strategy?: string; provider?: string }
  | { action: 'set_voice_reply_mode'; mode: 'off' | 'voice_if_voice' | 'always' }
  | { action: 'set_search_credential'; api_key: string }

// ============================================================
// Channels
// ============================================================

export interface ChannelField {
  key: string
  label: string
  type: 'text' | 'secret' | 'number' | 'bool'
  value?: string | number | boolean
  default?: string | number | boolean
}

export interface WechatGroupRoom {
  id: string
  name: string
  stable_room_id?: string
  runtime_room_id?: string
  binding_status?: string
  identity_requires_confirmation?: boolean
}

export interface WechatGroupPersonaPreset {
  id: string
  name: string
  badge?: string
  summary?: string
  prompt: string
}

export interface WechatGroupExtra {
  rooms: WechatGroupRoom[]
  identity_recovery?: {
    requires_confirmation: boolean
    pending_count: number
    pending_rooms: Array<{
      stable_room_id: string
      runtime_room_id?: string
      room_name?: string
      binding_status?: string
    }>
  }
  selected_room_ids: string[]
  stable_selected_room_ids?: string[]
  runtime_selected_room_ids?: string[]
  selected_room_names: string[]
  persona: {
    preset_id: string
    prompt: string
    max_length: number
  }
  persona_presets: WechatGroupPersonaPreset[]
  recent_context: {
    enabled: boolean
    limit: number
    minutes: number
  }
}

export interface ChannelInfo {
  name: string
  label: { zh: string; en: string }
  icon: string
  color: string
  active: boolean
  fields: ChannelField[]
  login_status?: string
  extra?: WechatGroupExtra
}

export type ChannelAction = 'save' | 'connect' | 'disconnect'

// ============================================================
// Tools / skills
// ============================================================

export interface ToolInfo {
  name: string
  description: string
}

export interface SkillInfo {
  name: string
  display_name?: string
  description: string
  source?: string
  enabled: boolean
  category?: string
}

// ============================================================
// Memory
// ============================================================

export type MemoryCategory = 'memory' | 'dream' | 'evolution'

export interface MemoryItem {
  filename: string
  type: string // global | daily | dream | evolution
  size: number
  updated_at: string
}

export interface MemoryPage {
  list: MemoryItem[]
  total: number
  page: number
  page_size: number
}

// ============================================================
// Knowledge
// ============================================================

export interface KnowledgeFile {
  name: string
  title: string
  size: number
}

// A directory node in the knowledge tree (recursive).
export interface KnowledgeDir {
  dir: string
  files: KnowledgeFile[]
  children: KnowledgeDir[]
}

export interface KnowledgeList {
  root_files?: KnowledgeFile[]
  tree: KnowledgeDir[]
  stats: { pages: number; size: number }
  enabled: boolean
}

export interface KnowledgeGraph {
  nodes: Array<{ id: string; label: string; category?: string }>
  links: Array<{ source: string; target: string }>
}

export type KnowledgeAction =
  | { action: 'create_category'; payload: { path: string } }
  | { action: 'create_document'; payload: { path: string; content: string; overwrite?: boolean } }
  | { action: 'rename_category'; payload: { path: string; new_path: string } }
  | { action: 'delete_category'; payload: { path: string; confirm?: boolean } }
  | { action: 'delete_documents'; payload: { paths: string[] } }
  | { action: 'move_documents'; payload: { paths: string[]; target_category: string } }

// Result row from a bulk import (one per uploaded file).
export interface KnowledgeImportResult {
  status: 'imported' | 'skipped' | 'failed'
  path?: string
  name?: string
  message?: string
}

export interface KnowledgeImportPayload {
  imported: number
  skipped: number
  failed: number
  results: KnowledgeImportResult[]
}

// ============================================================
// Scheduler
// ============================================================

export interface TaskSchedule {
  type: 'cron' | 'interval' | 'once'
  expression?: string
  seconds?: number
  run_at?: string
}

export interface TaskAction {
  type: 'send_message' | 'agent_task'
  content?: string
  task_description?: string
  receiver?: string
  receiver_name?: string
  is_group?: boolean
  channel_type?: string
}

export interface SchedulerTask {
  id: string
  name: string
  enabled: boolean
  created_at: string
  updated_at: string
  schedule: TaskSchedule
  action: TaskAction
  next_run_at?: string
}

// ============================================================
// Logs
// ============================================================

export interface LogEvent {
  type: 'init' | 'line' | 'error'
  content?: string
  message?: string
}

declare global {
  interface Window {
    electronAPI?: ElectronAPI
  }
}
