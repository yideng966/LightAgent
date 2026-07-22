import React, { useMemo, useRef, useCallback } from 'react'
import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'
import { t } from '../i18n'

/**
 * Markdown renderer aligned 1:1 with the web console (markdown-it + highlight.js
 * + GitHub themes). Using the same engine guarantees identical line-break,
 * linkify and code-highlight behavior across web and desktop.
 */

const md: MarkdownIt = new MarkdownIt({
  html: false,
  breaks: true,
  linkify: true,
  typographer: true,
  highlight(str, lang) {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return hljs.highlight(str, { language: lang }).value
      } catch {
        /* fall through */
      }
    }
    try {
      return hljs.highlightAuto(str).value
    } catch {
      return ''
    }
  },
})

// Open links in a new tab safely.
const defaultLinkOpen =
  md.renderer.rules.link_open ||
  function (tokens, idx, options, _env, self) {
    return self.renderToken(tokens, idx, options)
  }
md.renderer.rules.link_open = function (tokens, idx, options, env, self) {
  tokens[idx].attrPush(['target', '_blank'])
  tokens[idx].attrPush(['rel', 'noopener noreferrer'])
  return defaultLinkOpen(tokens, idx, options, env, self)
}

// Wrap fenced code blocks so we can render a header (lang + copy button).
const defaultFence =
  md.renderer.rules.fence ||
  function (tokens, idx, options, _env, self) {
    return self.renderToken(tokens, idx, options)
  }
md.renderer.rules.fence = function (tokens, idx, options, env, self) {
  const token = tokens[idx]
  const info = token.info ? token.info.trim().split(/\s+/)[0] : ''
  // Ensure the `hljs` class is present so the GitHub theme background/base
  // color applies (markdown-it only adds language-* by default).
  let rendered = defaultFence(tokens, idx, options, env, self)
  if (rendered.includes('<code class="')) {
    rendered = rendered.replace('<code class="', '<code class="hljs ')
  } else {
    rendered = rendered.replace('<code>', '<code class="hljs">')
  }
  return (
    `<div class="code-block-wrapper">` +
    `<div class="code-block-header">` +
    `<span class="code-block-lang">${info || 'text'}</span>` +
    `<button type="button" class="code-copy-btn" data-code-id="cb-${idx}" aria-label="Copy code">${t('msg_copy')}</button>` +
    `</div>` +
    rendered +
    `</div>`
  )
}

interface MarkdownProps {
  content: string
}

const Markdown: React.FC<MarkdownProps> = ({ content }) => {
  const rootRef = useRef<HTMLDivElement>(null)

  const html = useMemo(() => md.render(content || ''), [content])

  // Delegate copy clicks on code blocks (buttons are injected as raw HTML).
  const handleClick = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    const target = e.target as HTMLElement
    const btn = target.closest('.code-copy-btn') as HTMLElement | null
    if (!btn) return
    const pre = btn.closest('.code-block-wrapper')?.querySelector('pre')
    if (!pre) return
    navigator.clipboard.writeText(pre.textContent || '')
    const original = btn.textContent
    btn.textContent = t('msg_copied')
    btn.classList.add('copied')
    setTimeout(() => {
      btn.textContent = original
      btn.classList.remove('copied')
    }, 1600)
  }, [])

  return (
    <div
      ref={rootRef}
      className="msg-content text-sm text-content leading-relaxed break-words"
      onClick={handleClick}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  )
}

export default Markdown
