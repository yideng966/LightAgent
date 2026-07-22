import React, { useState } from 'react'
import { ChevronRight, Loader2, Check, X, Brain } from 'lucide-react'
import type { MessageStep } from '../types'
import Markdown from './Markdown'

/**
 * Assistant reasoning / tool steps, styled to match the web console: small,
 * muted, collapsible rows with an indented detail panel.
 */

const ThinkingStep: React.FC<{ content: string; streaming?: boolean }> = ({ content, streaming }) => {
  const [expanded, setExpanded] = useState(false)
  return (
    <div className="text-xs text-content-tertiary mb-1 last:mb-0">
      <div
        className="flex items-center gap-1.5 cursor-pointer hover:text-content-secondary select-none transition-colors"
        onClick={() => setExpanded((v) => !v)}
      >
        <Brain size={12} className="flex-shrink-0" />
        <span className="flex-1">{streaming ? 'Thinking…' : 'Thought for a moment'}</span>
        <ChevronRight size={11} className={`transition-transform opacity-50 ${expanded ? 'rotate-90' : ''}`} />
      </div>
      {expanded && (
        <pre className="mt-1.5 ml-4 p-2 rounded-md bg-inset border border-subtle whitespace-pre-wrap leading-relaxed max-h-[260px] overflow-y-auto font-sans text-content-tertiary">
          {content}
        </pre>
      )}
    </div>
  )
}

const ToolStep: React.FC<{ step: MessageStep }> = ({ step }) => {
  const [expanded, setExpanded] = useState(false)
  const running = step.status === 'running'
  const isError = step.is_error || (!!step.status && step.status !== 'success' && !running)

  const icon = running ? (
    <Loader2 size={12} className="text-accent animate-spin" />
  ) : isError ? (
    <X size={12} className="text-danger" />
  ) : (
    <Check size={12} className="text-accent" />
  )

  return (
    <div className="text-xs text-content-tertiary mb-1 last:mb-0">
      <div
        className="flex items-center gap-1.5 cursor-pointer hover:text-content-secondary select-none transition-colors"
        onClick={() => setExpanded((v) => !v)}
      >
        <span className="flex-shrink-0">{icon}</span>
        <span className={`font-medium ${isError ? 'text-danger' : ''}`}>{step.name}</span>
        {step.execution_time !== undefined && (
          <span className="opacity-60">{step.execution_time}s</span>
        )}
        <ChevronRight size={11} className={`ml-auto transition-transform opacity-50 ${expanded ? 'rotate-90' : ''}`} />
      </div>
      {expanded && (
        <div className="mt-1.5 ml-4 p-2 rounded-md bg-inset border border-subtle space-y-2">
          {step.arguments && Object.keys(step.arguments).length > 0 && (
            <div>
              <div className="text-[10px] font-semibold uppercase tracking-wide opacity-60 mb-1">Input</div>
              <pre className="font-mono text-[11px] whitespace-pre-wrap break-all max-h-[200px] overflow-y-auto leading-relaxed">
                {JSON.stringify(step.arguments, null, 2)}
              </pre>
            </div>
          )}
          {step.result && (
            <div>
              <div className="text-[10px] font-semibold uppercase tracking-wide opacity-60 mb-1">
                {isError ? 'Error' : 'Output'}
              </div>
              <pre
                className={`font-mono text-[11px] whitespace-pre-wrap break-all max-h-[240px] overflow-y-auto leading-relaxed ${
                  isError ? 'text-danger' : ''
                }`}
              >
                {step.result.length > 4000 ? step.result.slice(0, 4000) + '\n… (truncated)' : step.result}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

/** Renders an ordered list of assistant steps (thinking / content / tool). */
const MessageSteps: React.FC<{ steps: MessageStep[] }> = ({ steps }) => {
  if (!steps.length) return null
  return (
    <div>
      {steps.map((step, i) => {
        if (step.type === 'thinking') return <ThinkingStep key={i} content={step.content || ''} />
        if (step.type === 'tool') return <ToolStep key={i} step={step} />
        if (step.type === 'content' && step.content)
          return (
            <div key={i} className="mb-2 pb-2 border-b border-dashed border-default last:border-0 last:mb-0 last:pb-0">
              <Markdown content={step.content} />
            </div>
          )
        return null
      })}
    </div>
  )
}

export { ThinkingStep, ToolStep }
export default MessageSteps
