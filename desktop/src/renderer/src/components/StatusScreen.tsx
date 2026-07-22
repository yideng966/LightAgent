import React from 'react'
import { t } from '../i18n'

interface StatusScreenProps {
  status: 'connecting' | 'error'
  error?: string
  onRetry: () => void
}

const StatusScreen: React.FC<StatusScreenProps> = ({ status, error, onRetry }) => {
  return (
    <div className="h-screen w-screen flex items-center justify-center bg-gray-50 dark:bg-[#111111]">
      <div className="text-center space-y-6 max-w-md px-8">
        <img src="./logo.jpg" alt="LightAgent" className="w-16 h-16 rounded-2xl mx-auto shadow-lg shadow-primary-500/20" />

        {status === 'connecting' && (
          <>
            <div className="space-y-2">
              <h1 className="text-xl font-bold text-slate-800 dark:text-slate-100">
                {t('status_starting')}
              </h1>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                {t('status_starting_desc')}
              </p>
            </div>
            <div className="flex justify-center gap-1">
              <span className="w-2 h-2 rounded-full bg-primary-400 animate-pulse-dot" style={{ animationDelay: '0s' }} />
              <span className="w-2 h-2 rounded-full bg-primary-400 animate-pulse-dot" style={{ animationDelay: '0.2s' }} />
              <span className="w-2 h-2 rounded-full bg-primary-400 animate-pulse-dot" style={{ animationDelay: '0.4s' }} />
            </div>
          </>
        )}

        {status === 'error' && (
          <>
            <div className="space-y-2">
              <h1 className="text-xl font-bold text-slate-800 dark:text-slate-100">
                {t('status_error')}
              </h1>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                {error || t('status_error_desc')}
              </p>
            </div>
            <button
              onClick={onRetry}
              className="inline-flex items-center gap-2 px-4 py-2 bg-primary-500 hover:bg-primary-600 text-white rounded-lg transition-colors text-sm font-medium cursor-pointer"
            >
              <i className="fas fa-rotate-right text-xs" />
              {t('status_retry')}
            </button>
          </>
        )}
      </div>
    </div>
  )
}

export default StatusScreen
