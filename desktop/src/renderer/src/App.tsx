import React, { useState, useCallback, useEffect } from 'react'
import { Routes, Route, useLocation, useNavigate } from 'react-router-dom'
import { History } from 'lucide-react'
import NavRail from './layout/NavRail'
import SessionList from './layout/SessionList'
import WindowControls from './layout/WindowControls'
import StatusScreen from './components/StatusScreen'
import { useBackend } from './hooks/useBackend'
import { usePlatform } from './hooks/usePlatform'
import { useUIStore } from './store/uiStore'
import { useSessionStore } from './store/sessionStore'
import { initUpdateListener } from './store/updateStore'
import { useOnboardingStore } from './store/onboardingStore'
import OnboardingWizard from './components/OnboardingWizard'
import apiClient from './api/client'
import { t } from './i18n'
import ChatPage from './pages/ChatPage'
import SettingsPage from './pages/SettingsPage'
import KnowledgePage from './pages/KnowledgePage'
import SkillsPage from './pages/SkillsPage'
import MemoryPage from './pages/MemoryPage'
import ChannelsPage from './pages/ChannelsPage'
import GroupsPage from './pages/GroupsPage'
import TasksPage from './pages/TasksPage'
import LogsPage from './pages/LogsPage'

const App: React.FC = () => {
  const backend = useBackend()
  const location = useLocation()
  const navigate = useNavigate()
  const { isWin, isMac } = usePlatform()
  const { sessionsCollapsed, toggleSessions, navCollapsed } = useUIStore()
  const onboardingOpen = useOnboardingStore((s) => s.open)
  const maybeOpenOnboarding = useOnboardingStore((s) => s.maybeOpen)
  const [, forceUpdate] = useState(0)

  useEffect(() => {
    if (backend.status === 'ready') apiClient.setBaseUrl(backend.baseUrl)
  }, [backend.status, backend.baseUrl])

  // First-run check: once the backend is ready, decide whether to show the
  // onboarding wizard. It's config-driven — shown whenever the chat model isn't
  // configured (and not dismissed earlier this session); no persisted flag.
  useEffect(() => {
    if (backend.status !== 'ready') return
    let cancelled = false
    apiClient
      .getModels()
      .then((data) => {
        if (cancelled) return
        const chat = data.capabilities?.chat
        // "Configured" needs a chat provider+model AND that provider's API key
        // set. A default config can ship a model name with no key, which
        // shouldn't count as ready — otherwise we'd skip onboarding for users
        // who still need to enter a key.
        const providerId = chat?.current_provider
        const provider = data.providers?.find((p) => p.id === providerId)
        const keyReady = !!provider && (provider.configured || (provider.is_custom && !!provider.custom_name))
        const configured = !!providerId && !!chat?.current_model && keyReady
        maybeOpenOnboarding(configured)
      })
      .catch(() => {
        // If models can't be loaded, fall back to the flag-only decision.
        if (!cancelled) maybeOpenOnboarding(false)
      })
    return () => {
      cancelled = true
    }
  }, [backend.status, maybeOpenOnboarding])

  // Subscribe to auto-update status from the main process (no-op in dev).
  useEffect(() => initUpdateListener(), [])

  // Handle app-menu / shortcut actions forwarded from the main process.
  useEffect(() => {
    const off = window.electronAPI?.onMenuAction?.((action) => {
      if (action === 'new-chat') {
        useSessionStore.getState().newSession()
        navigate('/')
      } else if (action === 'open-settings') {
        navigate('/settings')
      } else if (action === 'view-logs') {
        navigate('/logs')
      }
    })
    return off
  }, [navigate])

  const handleLangChange = useCallback(() => forceUpdate((n) => n + 1), [])

  if (backend.status !== 'ready') {
    return <StatusScreen status={backend.status} error={backend.error} onRetry={backend.restart} />
  }

  const isChat = location.pathname === '/'
  const showSessions = isChat && !sessionsCollapsed

  return (
    <div className="flex h-screen overflow-hidden bg-base text-content">
      {onboardingOpen && <OnboardingWizard onDone={handleLangChange} />}
      <NavRail onLangChange={handleLangChange} />

      {showSessions && <SessionList />}

      <div className="flex-1 flex flex-col min-w-0 h-screen">
        {/* Top titlebar strip — drag region + Windows controls */}
        <header className="h-[44px] flex items-center gap-1 px-2 flex-shrink-0 titlebar-drag bg-base border-b border-default">
          {isChat && sessionsCollapsed && (
            <button
              onClick={toggleSessions}
              title={t('session_history')}
              // Keep aligned with the SessionList history button: only nudge
              // right of the macOS traffic lights when the nav rail is collapsed
              // (otherwise the lights stay within the rail and don't overlap).
              className={`titlebar-no-drag inline-flex items-center justify-center w-7 h-7 rounded-btn text-content-tertiary hover:text-content hover:bg-surface-2 cursor-pointer transition-colors ${isMac ? 'mt-1' : ''} ${isMac && navCollapsed ? 'ml-2' : ''}`}
            >
              <History size={16} />
            </button>
          )}
          <div className="flex-1 min-w-0" />
          {isWin && <WindowControls />}
        </header>

        {/* Content */}
        <div className="flex-1 flex flex-col min-h-0 overflow-hidden bg-base">
          <Routes>
            <Route path="/" element={<ChatPage baseUrl={backend.baseUrl} />} />
            <Route path="/knowledge" element={<KnowledgePage baseUrl={backend.baseUrl} />} />
            <Route path="/memory" element={<MemoryPage baseUrl={backend.baseUrl} />} />
            <Route path="/skills" element={<SkillsPage baseUrl={backend.baseUrl} />} />
            <Route path="/channels" element={<ChannelsPage baseUrl={backend.baseUrl} />} />
            <Route path="/groups" element={<GroupsPage baseUrl={backend.baseUrl} />} />
            <Route path="/tasks" element={<TasksPage baseUrl={backend.baseUrl} />} />
            <Route path="/settings" element={<SettingsPage baseUrl={backend.baseUrl} onLangChange={handleLangChange} />} />
            {/* Legacy /models route now lives as a tab inside settings */}
            <Route path="/models" element={<SettingsPage baseUrl={backend.baseUrl} onLangChange={handleLangChange} />} />
            <Route path="/logs" element={<LogsPage baseUrl={backend.baseUrl} />} />
          </Routes>
        </div>
      </div>
    </div>
  )
}

export default App
