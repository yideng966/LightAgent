import React, { useState, useRef, useCallback, useEffect, forwardRef, useImperativeHandle } from 'react'
import { Plus, Paperclip, Square, X, File as FileIcon, Loader2, Trash2 } from 'lucide-react'
import { t } from '../i18n'
import type { Attachment } from '../types'
import apiClient from '../api/client'
import { PaperPlaneIcon } from './icons'

export type ChatInputHandle = (text: string, attachments: Attachment[]) => void

interface SlashCommand {
  cmd: string
  desc: string
  // 'new'/'clear' run a local action; 'send' (default) is a completion that
  // gets sent to the backend as a normal message (handled by command plugins).
  action?: 'new' | 'clear'
}

interface ChatInputProps {
  onSend: (message: string, attachments: Attachment[]) => void
  onNewChat: () => void
  onStop: () => void
  onClearContext: () => void
  isStreaming: boolean
  sessionId: string
}

const ChatInput = forwardRef<ChatInputHandle, ChatInputProps>(function ChatInput(
  { onSend, onNewChat, onStop, onClearContext, isStreaming, sessionId },
  ref
) {
  const [text, setText] = useState('')
  const [attachments, setAttachments] = useState<Attachment[]>([])
  const [uploading, setUploading] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const [slashOpen, setSlashOpen] = useState(false)
  const [slashIndex, setSlashIndex] = useState(0)
  const composingRef = useRef(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Local actions ('new'/'clear') plus completion commands handled by backend
  // command plugins (lightagent_cli/godcmd). Commands ending with a space expect an
  // argument, so selecting them keeps focus in the input instead of sending.
  const slashCommands: SlashCommand[] = [
    { cmd: '/new', desc: t('slash_new'), action: 'new' },
    { cmd: '/clear', desc: t('slash_clear'), action: 'clear' },
    { cmd: '/help', desc: t('slash_help') },
    { cmd: '/status', desc: t('slash_status') },
    { cmd: '/context', desc: t('slash_context') },
    { cmd: '/skill list', desc: t('slash_skill_list') },
    { cmd: '/skill search ', desc: t('slash_skill_search') },
    { cmd: '/skill install ', desc: t('slash_skill_install') },
    { cmd: '/memory dream ', desc: t('slash_memory_dream') },
    { cmd: '/knowledge', desc: t('slash_knowledge') },
    { cmd: '/knowledge list', desc: t('slash_knowledge_list') },
    { cmd: '/config', desc: t('slash_config') },
    { cmd: '/cancel', desc: t('slash_cancel') },
    { cmd: '/logs', desc: t('slash_logs') },
    { cmd: '/version', desc: t('slash_version') },
  ]
  const filtered = slashCommands.filter((c) => c.cmd.startsWith(text.trim().toLowerCase()))

  // Resize the textarea to fit its content (single line = 42px, capped at
  // 180px). Keep overflow hidden until we hit the cap, so an empty/short input
  // never shows a scrollbar (matches the web console behavior).
  const autoSize = (el: HTMLTextAreaElement | null) => {
    if (!el) return
    el.style.height = '42px'
    const h = Math.min(el.scrollHeight, 180)
    el.style.height = h + 'px'
    el.style.overflowY = el.scrollHeight > 180 ? 'auto' : 'hidden'
  }

  const resetHeight = () => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = '42px'
    el.style.overflowY = 'hidden'
  }

  // Sync the height once on mount so the very first render matches the 42px
  // single-line height instead of the browser's default textarea size.
  useEffect(() => {
    autoSize(textareaRef.current)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Allow the parent to load a draft (e.g. when editing a past user message).
  useImperativeHandle(ref, () => (draft: string, atts: Attachment[]) => {
    setText(draft)
    setAttachments(atts)
    requestAnimationFrame(() => {
      const el = textareaRef.current
      if (el) {
        el.focus()
        autoSize(el)
      }
    })
  })

  const runSlash = (c: SlashCommand) => {
    setSlashOpen(false)
    if (c.action === 'new') {
      setText('')
      resetHeight()
      onNewChat()
      return
    }
    if (c.action === 'clear') {
      setText('')
      resetHeight()
      onClearContext()
      return
    }
    // Completion command. If it expects an argument (trailing space), keep it
    // in the input so the user can type the argument; otherwise send it now.
    const needsArg = c.cmd.endsWith(' ')
    if (needsArg) {
      setText(c.cmd)
      requestAnimationFrame(() => textareaRef.current?.focus())
    } else {
      onSend(c.cmd.trim(), [])
      setText('')
      resetHeight()
    }
  }

  const handleSubmit = useCallback(() => {
    const trimmed = text.trim()
    if (!trimmed && attachments.length === 0) return
    if (isStreaming) return
    onSend(trimmed, attachments)
    setText('')
    setAttachments([])
    setSlashOpen(false)
    resetHeight()
  }, [text, attachments, isStreaming, onSend])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    // Slash menu navigation
    if (slashOpen && filtered.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setSlashIndex((i) => (i + 1) % filtered.length)
        return
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault()
        setSlashIndex((i) => (i - 1 + filtered.length) % filtered.length)
        return
      }
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        runSlash(filtered[slashIndex])
        return
      }
      if (e.key === 'Escape') {
        setSlashOpen(false)
        return
      }
    }
    // Don't submit while IME is composing (Chinese input)
    if (e.key === 'Enter' && !e.shiftKey && !composingRef.current) {
      e.preventDefault()
      handleSubmit()
    }
  }

  const handleTextChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const v = e.target.value
    setText(v)
    autoSize(e.target)
    // open slash menu when the input starts with "/" and has no space
    setSlashOpen(v.startsWith('/') && !v.includes(' '))
    setSlashIndex(0)
  }

  const uploadFiles = async (files: File[]) => {
    if (!files.length) return
    setUploading(true)
    try {
      for (const file of files) {
        const result = await apiClient.uploadFile(file, sessionId)
        if (result.status === 'success') {
          setAttachments((prev) => [
            ...prev,
            {
              file_path: result.file_path,
              file_name: result.file_name,
              file_type: result.file_type as Attachment['file_type'],
              preview_url: result.preview_url,
            },
          ])
        }
      }
    } catch (err) {
      console.error('Upload failed:', err)
    } finally {
      setUploading(false)
    }
  }

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (files) await uploadFiles(Array.from(files))
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const files = Array.from(e.dataTransfer.files || [])
    if (files.length) uploadFiles(files)
  }

  const handlePaste = (e: React.ClipboardEvent) => {
    const items = e.clipboardData?.items
    if (!items) return
    const files: File[] = []
    for (const item of Array.from(items)) {
      if (item.kind === 'file') {
        const f = item.getAsFile()
        if (f) files.push(f)
      }
    }
    if (files.length) {
      e.preventDefault()
      uploadFiles(files)
    }
  }

  const removeAttachment = (index: number) => {
    setAttachments((prev) => prev.filter((_, i) => i !== index))
  }

  // keep slash index in range
  useEffect(() => {
    if (slashIndex >= filtered.length) setSlashIndex(0)
  }, [filtered.length, slashIndex])

  const canSend = !isStreaming && (!!text.trim() || attachments.length > 0)

  return (
    <div className="flex-shrink-0 border-t border-default bg-surface px-4 py-3">
      <div
        className={`max-w-3xl mx-auto relative rounded-2xl transition-all ${
          dragOver ? 'ring-2 ring-accent ring-offset-2 ring-offset-surface' : ''
        }`}
        onDragOver={(e) => {
          e.preventDefault()
          setDragOver(true)
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
      >
        {dragOver && (
          <div className="absolute inset-0 z-20 flex items-center justify-center rounded-2xl bg-accent-soft text-accent text-sm font-medium pointer-events-none">
            {t('input_placeholder')}
          </div>
        )}

        {/* Slash command menu */}
        {slashOpen && filtered.length > 0 && (
          <div className="absolute bottom-full left-0 right-0 mb-1.5 max-h-80 overflow-y-auto rounded-xl border border-default bg-elevated shadow-xl z-30 p-1.5">
            <div className="px-2.5 pt-1 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-content-tertiary">
              {t('slash_menu_title')}
            </div>
            {filtered.map((c, i) => (
              <button
                key={c.cmd}
                onMouseEnter={() => setSlashIndex(i)}
                onClick={() => runSlash(c)}
                className={`w-full flex items-center justify-between gap-3 px-2.5 py-2 rounded-lg text-left cursor-pointer transition-colors ${
                  i === slashIndex ? 'bg-accent-soft' : 'hover:bg-surface-2'
                }`}
              >
                <span
                  className={`text-[13px] font-medium font-mono whitespace-nowrap ${
                    i === slashIndex ? 'text-accent' : 'text-content-secondary'
                  }`}
                >
                  {c.cmd}
                </span>
                <span className="text-xs text-content-tertiary whitespace-nowrap truncate">{c.desc}</span>
              </button>
            ))}
          </div>
        )}

        {/* Attachment preview */}
        {attachments.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-2">
            {attachments.map((att, i) => (
              <div key={i} className="relative">
                {att.file_type === 'image' && att.preview_url ? (
                  <div className="relative">
                    <img
                      src={apiClient.getFileUrl(att.preview_url)}
                      alt={att.file_name}
                      className="w-16 h-16 rounded-lg object-cover border border-default"
                    />
                    <button
                      onClick={() => removeAttachment(i)}
                      className="absolute -top-1 -right-1 w-[18px] h-[18px] rounded-full bg-danger text-white flex items-center justify-center cursor-pointer"
                    >
                      <X size={10} />
                    </button>
                  </div>
                ) : (
                  <div className="flex items-center gap-1.5 px-2.5 py-1.5 bg-inset border border-default rounded-lg text-xs text-content-secondary max-w-[180px] relative pr-7">
                    <FileIcon size={12} />
                    <span className="truncate">{att.file_name}</span>
                    <button
                      onClick={() => removeAttachment(i)}
                      className="absolute -top-1 -right-1 w-[18px] h-[18px] rounded-full bg-danger text-white flex items-center justify-center cursor-pointer"
                    >
                      <X size={10} />
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        <div className="flex items-end gap-2">
          <div className="flex items-center flex-shrink-0 gap-0.5 pb-0.5">
            <button
              onClick={onNewChat}
              className="w-9 h-9 flex items-center justify-center rounded-btn text-content-secondary hover:text-accent hover:bg-accent-soft cursor-pointer transition-colors"
              title={t('session_new')}
            >
              <Plus size={18} />
            </button>
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              className="w-9 h-9 flex items-center justify-center rounded-btn text-content-secondary hover:text-accent hover:bg-accent-soft cursor-pointer transition-colors disabled:opacity-50"
              title={t('chat_attach')}
            >
              {uploading ? <Loader2 size={18} className="animate-spin" /> : <Paperclip size={18} />}
            </button>
            <button
              onClick={onClearContext}
              className="w-9 h-9 flex items-center justify-center rounded-btn text-content-secondary hover:text-danger hover:bg-danger-soft cursor-pointer transition-colors"
              title={t('chat_clear_context')}
            >
              <Trash2 size={18} />
            </button>
          </div>
          <input
            ref={fileInputRef}
            type="file"
            className="hidden"
            multiple
            onChange={handleFileSelect}
            accept="image/*,.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.csv,.json,.xml,.zip,.py,.js,.ts,.java,.c,.cpp,.go,.rs,.md"
          />

          <textarea
            ref={textareaRef}
            id="chat-input"
            value={text}
            onChange={handleTextChange}
            onKeyDown={handleKeyDown}
            onPaste={handlePaste}
            onCompositionStart={() => (composingRef.current = true)}
            onCompositionEnd={() => (composingRef.current = false)}
            placeholder={t('input_placeholder')}
            rows={1}
            className="flex-1 min-w-0 px-4 py-[10px] rounded-xl border border-strong bg-inset text-content placeholder:text-content-tertiary focus:outline-none focus:border-accent text-sm leading-relaxed transition-colors resize-none overflow-y-hidden"
          />

          {isStreaming ? (
            <button
              onClick={onStop}
              className="flex-shrink-0 w-10 h-10 flex items-center justify-center rounded-btn bg-surface-2 text-content hover:bg-inset cursor-pointer transition-colors"
              title={t('msg_stop')}
            >
              <Square size={15} className="fill-current" />
            </button>
          ) : (
            <button
              onClick={handleSubmit}
              disabled={!canSend}
              className="flex-shrink-0 w-[42px] h-[42px] flex items-center justify-center rounded-btn bg-accent text-white hover:bg-accent-hover disabled:bg-surface-2 disabled:text-content-disabled disabled:cursor-not-allowed cursor-pointer transition-none [&_*]:transition-none"
              title={t('chat_send')}
            >
              <PaperPlaneIcon size={15} />
            </button>
          )}
        </div>
      </div>
    </div>
  )
})

export default ChatInput
