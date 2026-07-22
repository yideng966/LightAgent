import React, { useState } from 'react'
import { Copy, Check, RefreshCw, Pencil, Trash2, File as FileIcon, Sprout } from 'lucide-react'
import type { ChatMessage } from '../types'
import { t } from '../i18n'
import apiClient from '../api/client'
import Markdown from './Markdown'
import MessageSteps, { ThinkingStep } from './MessageSteps'

interface MessageBubbleProps {
  message: ChatMessage
  onRegenerate?: (id: string) => void
  onEdit?: (id: string) => void
  onDelete?: (msg: ChatMessage) => void
}

function fmtTime(ts: number): string {
  if (!ts) return ''
  const d = new Date(ts * 1000)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

const HoverAction: React.FC<{ onClick: () => void; title: string; danger?: boolean; children: React.ReactNode }> = ({
  onClick,
  title,
  danger,
  children,
}) => (
  <button
    onClick={onClick}
    title={title}
    className={`inline-flex items-center justify-center w-7 h-7 rounded-md cursor-pointer transition-colors text-content-tertiary ${
      danger ? 'hover:text-danger hover:bg-danger-soft' : 'hover:text-content hover:bg-surface-2'
    }`}
  >
    {children}
  </button>
)

const MessageBubble: React.FC<MessageBubbleProps> = ({ message, onRegenerate, onEdit, onDelete }) => {
  const isUser = message.role === 'user'
  const [copied, setCopied] = useState(false)

  const copy = () => {
    navigator.clipboard.writeText(message.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 1800)
  }

  if (isUser) {
    return (
      <div className="group flex flex-col items-end px-4 sm:px-6 py-2">
        {message.attachments && message.attachments.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-1.5 justify-end max-w-[75%]">
            {message.attachments.map((att, i) =>
              att.file_type === 'image' && att.preview_url ? (
                <img
                  key={i}
                  src={apiClient.getFileUrl(att.preview_url)}
                  alt={att.file_name}
                  className="max-w-[180px] max-h-[150px] rounded-xl object-cover border border-default"
                />
              ) : (
                <div key={i} className="flex items-center gap-1.5 px-3 py-2 bg-surface-2 rounded-xl text-xs text-content-secondary">
                  <FileIcon size={13} />
                  {att.file_name}
                </div>
              )
            )}
          </div>
        )}
        <div className="max-w-[75%] rounded-2xl rounded-br-md px-4 py-2.5 bg-accent text-white">
          <div className="text-sm whitespace-pre-wrap break-words">{message.content}</div>
        </div>
        <div className="flex items-center gap-0.5 mt-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <span className="text-[11px] text-content-tertiary mr-1">{fmtTime(message.timestamp)}</span>
          {onEdit && message.userSeq != null && (
            <HoverAction onClick={() => onEdit(message.id)} title={t('msg_edit')}>
              <Pencil size={13} />
            </HoverAction>
          )}
          {onDelete && message.userSeq != null && (
            <HoverAction onClick={() => onDelete(message)} title={t('msg_delete')} danger>
              <Trash2 size={13} />
            </HoverAction>
          )}
        </div>
      </div>
    )
  }

  // Assistant
  const showCursor = message.isStreaming && !message.content && (!message.steps || message.steps.length === 0)

  const hasSteps = !!(message.steps && message.steps.length > 0)
  const hasLiveReasoning = !!(message.reasoning && message.isStreaming)

  return (
    <div className="group flex gap-3 px-4 sm:px-6 py-2">
      <img src="./logo.jpg" alt="LightAgent" className="w-7 h-7 rounded-lg flex-shrink-0 mt-1" />
      <div className="flex-1 min-w-0 max-w-[calc(100%-2.5rem)]">
        <div className="inline-block w-full rounded-2xl border border-default bg-surface px-4 py-3">
          {message.kind === 'evolution' && (
            <div className="inline-flex items-center gap-1 mb-1.5 text-[11px] text-content-tertiary">
              <Sprout size={11} />
              {t('msg_self_learned')}
            </div>
          )}

          {/* Steps area (thinking / tools / intermediate content), web-aligned:
              muted, separated from the final answer by a dashed divider. */}
          {(hasSteps || hasLiveReasoning) && (
            <div className="mb-2.5 pb-2 border-b border-dashed border-default">
              {hasLiveReasoning && <ThinkingStep content={message.reasoning!} streaming />}
              {hasSteps && <MessageSteps steps={message.steps!} />}
            </div>
          )}

          {/* Final answer */}
          {message.content && <Markdown content={message.content} />}

          {showCursor && (
            <div className="flex items-center gap-1 py-0.5">
              <span className="typing-dot" />
              <span className="typing-dot" />
              <span className="typing-dot" />
            </div>
          )}

          {message.isStreaming && message.content && (
            <span className="inline-block w-[6px] h-[14px] bg-accent ml-0.5 align-middle animate-blink" />
          )}

          {message.isCancelled && <div className="text-xs text-warning mt-1">{t('msg_cancelled')}</div>}
          {message.error && <div className="text-xs text-danger mt-1">{message.error}</div>}
        </div>

        {/* Hover actions (only when finished) */}
        {!message.isStreaming && (message.content || message.error) && (
          <div className="flex items-center gap-0.5 mt-1 opacity-0 group-hover:opacity-100 transition-opacity">
            <span className="text-[11px] text-content-tertiary mr-1">{fmtTime(message.timestamp)}</span>
            <HoverAction onClick={copy} title={t('msg_copy')}>
              {copied ? <Check size={13} /> : <Copy size={13} />}
            </HoverAction>
            {onRegenerate && (
              <HoverAction onClick={() => onRegenerate(message.id)} title={t('msg_regenerate')}>
                <RefreshCw size={13} />
              </HoverAction>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export default MessageBubble
