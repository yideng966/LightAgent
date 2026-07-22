import React, { useEffect, useState } from 'react'
import { Download, RefreshCw, X, Loader2 } from 'lucide-react'
import { t } from '../i18n'
import { useUpdateStore, hasPendingUpdate } from '../store/updateStore'

// Compact update panel anchored to the NavRail footer. Only mounts content
// when there's a pending update; otherwise renders nothing so it stays out of
// the way until electron-updater reports a new version.
const UpdateBanner: React.FC = () => {
  const state = useUpdateStore()
  const [open, setOpen] = useState(false)

  const pending = hasPendingUpdate(state)
  const status = state.status

  // Auto-open the panel the moment a new version is first detected.
  useEffect(() => {
    if (status?.state === 'available') setOpen(true)
  }, [status?.state])

  if (!pending) return null

  const version = state.version
  const downloading = status?.state === 'downloading'
  const downloaded = status?.state === 'downloaded'

  return (
    <div className="absolute bottom-14 left-2 right-2 z-40">
      {/* Collapsed pill: a red-dotted button that re-opens the panel. */}
      {!open && (
        <button
          onClick={() => setOpen(true)}
          className="relative w-full flex items-center gap-2 rounded-btn bg-accent-soft text-accent px-3 py-2 text-[13px] font-medium cursor-pointer hover:bg-accent-soft/80 transition-colors"
        >
          <span className="absolute -top-1 -left-1 h-2 w-2 rounded-full bg-danger" />
          <Download size={15} />
          <span className="truncate">{t('update_available')}</span>
        </button>
      )}

      {open && (
        <div className="rounded-lg border border-default bg-elevated shadow-lg p-3 space-y-2.5">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <p className="text-[13px] font-semibold text-content">{t('update_available')}</p>
              {version && <p className="text-xs text-content-tertiary mt-0.5">v{version}</p>}
            </div>
            <button
              onClick={() => {
                setOpen(false)
                state.dismiss()
              }}
              className="text-content-tertiary hover:text-content cursor-pointer flex-shrink-0"
              title={t('update_later')}
            >
              <X size={15} />
            </button>
          </div>

          {downloading && (
            <div className="space-y-1">
              <div className="flex items-center gap-2 text-xs text-content-secondary">
                <Loader2 size={13} className="animate-spin" />
                <span>{t('update_downloading')} {state.percent}%</span>
              </div>
              <div className="h-1.5 w-full rounded-full bg-surface-2 overflow-hidden">
                <div className="h-full bg-accent transition-[width] duration-200" style={{ width: `${state.percent}%` }} />
              </div>
            </div>
          )}

          {!downloading && !downloaded && (
            <button
              onClick={() => state.download()}
              className="w-full inline-flex items-center justify-center gap-2 rounded-btn bg-accent text-accent-contrast hover:bg-accent-hover px-3 py-2 text-[13px] font-medium cursor-pointer transition-colors"
            >
              <Download size={15} />
              {t('update_download')}
            </button>
          )}

          {downloaded && (
            <button
              onClick={() => state.install()}
              className="w-full inline-flex items-center justify-center gap-2 rounded-btn bg-accent text-accent-contrast hover:bg-accent-hover px-3 py-2 text-[13px] font-medium cursor-pointer transition-colors"
            >
              <RefreshCw size={15} />
              {t('update_restart')}
            </button>
          )}
        </div>
      )}
    </div>
  )
}

export default UpdateBanner
