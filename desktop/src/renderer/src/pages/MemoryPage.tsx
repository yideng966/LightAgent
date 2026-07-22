import React, { useCallback, useEffect, useState } from 'react'
import { Loader2, ArrowLeft, Brain, Sprout, FileText, ChevronLeft, ChevronRight } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { t } from '../i18n'
import apiClient from '../api/client'
import type { MemoryItem, MemoryCategory } from '../types'
import Markdown from '../components/Markdown'

interface MemoryPageProps {
  baseUrl: string
}

type Tab = 'files' | 'evolution'
const PAGE_SIZE = 10

const formatSize = (bytes: number): string => {
  if (bytes < 1024) return bytes + ' B'
  return (bytes / 1024).toFixed(1) + ' KB'
}

// Map a file's `type` to its display badge.
const typeBadge = (type: string): { label: string; cls: string } => {
  switch (type) {
    case 'global':
      return { label: t('memory_type_global'), cls: 'bg-accent-soft text-accent' }
    case 'evolution':
      return { label: t('memory_type_evolution'), cls: 'bg-inset text-success' }
    case 'dream':
      return { label: t('memory_type_dream'), cls: 'bg-inset text-info' }
    default:
      return { label: t('memory_type_daily'), cls: 'bg-inset text-content-secondary' }
  }
}

const MemoryPage: React.FC<MemoryPageProps> = ({ baseUrl }) => {
  const [tab, setTab] = useState<Tab>('files')
  const [items, setItems] = useState<MemoryItem[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)

  const [viewing, setViewing] = useState<string | null>(null)
  const [content, setContent] = useState('')
  const [docLoading, setDocLoading] = useState(false)

  const category: MemoryCategory = tab === 'evolution' ? 'evolution' : 'memory'

  const loadList = useCallback(
    async (cat: MemoryCategory, p: number) => {
      try {
        setLoading(true)
        const data = await apiClient.getMemoryList(p, PAGE_SIZE, cat)
        setItems(data.list || [])
        setTotal(data.total || 0)
        setPage(data.page || p)
      } catch (err) {
        console.error('Failed to load memory:', err)
        setItems([])
        setTotal(0)
      } finally {
        setLoading(false)
      }
    },
    []
  )

  useEffect(() => {
    apiClient.setBaseUrl(baseUrl)
    void loadList(category, 1)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [baseUrl, tab])

  const openFile = async (item: MemoryItem) => {
    // In the evolution tab a file lives in its own dir (dream vs evolution).
    const fileCategory: MemoryCategory =
      item.type === 'dream' || item.type === 'evolution' ? (item.type as MemoryCategory) : category
    setViewing(item.filename)
    setDocLoading(true)
    setContent('')
    try {
      const text = await apiClient.getMemoryContent(item.filename, fileCategory)
      setContent(text)
    } catch {
      setContent(`> ${t('memory_doc_load_error')}`)
    } finally {
      setDocLoading(false)
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div className="flex-1 flex flex-col min-h-0">
      {/* Header */}
      <div className="flex items-center justify-between px-6 pt-5 pb-3 flex-shrink-0">
        <div>
          <h2 className="text-xl font-bold text-content">{t('memory_title')}</h2>
          <p className="text-xs text-content-tertiary mt-1">{t('memory_desc')}</p>
        </div>
        {!viewing && (
          <div className="flex items-center gap-1 bg-inset rounded-btn p-0.5">
            <TabBtn icon={Brain} label={t('memory_tab_files')} active={tab === 'files'} onClick={() => setTab('files')} />
            <TabBtn
              icon={Sprout}
              label={t('memory_tab_dreams')}
              active={tab === 'evolution'}
              onClick={() => setTab('evolution')}
            />
          </div>
        )}
      </div>

      {viewing ? (
        /* File viewer */
        <div className="flex-1 flex flex-col min-h-0 border-t border-default">
          <div className="flex items-center gap-3 px-6 py-3 flex-shrink-0 border-b border-subtle">
            <button
              onClick={() => setViewing(null)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-btn text-sm text-content-secondary hover:bg-inset border border-strong transition-colors cursor-pointer"
            >
              <ArrowLeft size={14} />
              {t('memory_back')}
            </button>
            <h3 className="text-sm font-semibold text-content font-mono truncate">{viewing}</h3>
          </div>
          <div className="flex-1 overflow-y-auto">
            <div className="max-w-3xl mx-auto px-6 py-6">
              {docLoading ? (
                <div className="flex items-center text-content-tertiary py-8">
                  <Loader2 size={16} className="animate-spin mr-2" />
                </div>
              ) : (
                <Markdown content={content} />
              )}
            </div>
          </div>
        </div>
      ) : (
        /* List */
        <div className="flex-1 overflow-y-auto border-t border-default">
          <div className="max-w-4xl mx-auto px-6 py-5">
            {loading ? (
              <div className="flex items-center justify-center py-20 text-content-tertiary">
                <Loader2 size={18} className="animate-spin mr-2" />
                {t('memory_loading')}
              </div>
            ) : items.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-20 text-content-tertiary">
                {tab === 'evolution' ? <Sprout size={28} className="mb-3 opacity-60" /> : <Brain size={28} className="mb-3 opacity-60" />}
                <p className="text-sm">{tab === 'evolution' ? t('memory_empty_evolution') : t('memory_empty_files')}</p>
              </div>
            ) : (
              <>
                <div className="rounded-card border border-default overflow-hidden bg-surface">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-default">
                        <Th>{t('memory_col_name')}</Th>
                        <Th>{t('memory_col_type')}</Th>
                        <Th>{t('memory_col_size')}</Th>
                        <Th>{t('memory_col_updated')}</Th>
                      </tr>
                    </thead>
                    <tbody>
                      {items.map((item) => {
                        const badge = typeBadge(item.type)
                        return (
                          <tr
                            key={item.filename}
                            onClick={() => openFile(item)}
                            className="border-b border-subtle last:border-0 hover:bg-inset cursor-pointer transition-colors"
                          >
                            <td className="px-4 py-3 text-sm font-mono text-content-secondary">
                              <span className="inline-flex items-center gap-2">
                                <FileText size={13} className="text-content-tertiary flex-shrink-0" />
                                {item.filename}
                              </span>
                            </td>
                            <td className="px-4 py-3">
                              <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${badge.cls}`}>{badge.label}</span>
                            </td>
                            <td className="px-4 py-3 text-sm text-content-tertiary">{formatSize(item.size)}</td>
                            <td className="px-4 py-3 text-sm text-content-tertiary">{item.updated_at}</td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>

                {totalPages > 1 && (
                  <div className="flex items-center justify-between mt-4 text-sm text-content-tertiary">
                    <span>
                      {page} / {totalPages}
                    </span>
                    <div className="flex gap-2">
                      <PageBtn icon={ChevronLeft} label={t('memory_prev')} disabled={page <= 1} onClick={() => loadList(category, page - 1)} />
                      <PageBtn
                        icon={ChevronRight}
                        label={t('memory_next')}
                        disabled={page >= totalPages}
                        onClick={() => loadList(category, page + 1)}
                        iconRight
                      />
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

const Th: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <th className="text-left px-4 py-2.5 text-xs font-semibold uppercase tracking-wider text-content-tertiary">{children}</th>
)

const TabBtn: React.FC<{ icon: LucideIcon; label: string; active: boolean; onClick: () => void }> = ({
  icon: Icon,
  label,
  active,
  onClick,
}) => (
  <button
    onClick={onClick}
    className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-[6px] text-sm font-medium cursor-pointer transition-colors ${
      active ? 'bg-surface text-content shadow-sm' : 'text-content-tertiary hover:text-content-secondary'
    }`}
  >
    <Icon size={14} />
    {label}
  </button>
)

const PageBtn: React.FC<{
  icon: LucideIcon
  label: string
  disabled: boolean
  onClick: () => void
  iconRight?: boolean
}> = ({ icon: Icon, label, disabled, onClick, iconRight }) => (
  <button
    onClick={onClick}
    disabled={disabled}
    className="inline-flex items-center gap-1 px-3 py-1 rounded-btn border border-strong text-xs text-content-secondary hover:bg-inset disabled:opacity-40 disabled:cursor-not-allowed transition-colors cursor-pointer"
  >
    {!iconRight && <Icon size={13} />}
    {label}
    {iconRight && <Icon size={13} />}
  </button>
)

export default MemoryPage
