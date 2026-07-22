import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('electronAPI', {
  getBackendPort: () => ipcRenderer.invoke('get-backend-port'),
  getBackendStatus: () => ipcRenderer.invoke('get-backend-status'),
  restartBackend: () => ipcRenderer.invoke('restart-backend'),
  selectDirectory: () => ipcRenderer.invoke('select-directory'),
  selectFile: (filters?: Electron.FileFilter[]) => ipcRenderer.invoke('select-file', filters),

  // Each listener registrar returns an unsubscribe fn so renderers can clean
  // up on unmount / effect re-run and avoid accumulating duplicate handlers.
  onBackendStatus: (callback: (data: { status: string; port?: number; error?: string }) => void) => {
    const handler = (_event: unknown, data: { status: string; port?: number; error?: string }) => callback(data)
    ipcRenderer.on('backend-status', handler)
    return () => ipcRenderer.removeListener('backend-status', handler)
  },

  onBackendLog: (callback: (line: string) => void) => {
    const handler = (_event: unknown, line: string) => callback(line)
    ipcRenderer.on('backend-log', handler)
    return () => ipcRenderer.removeListener('backend-log', handler)
  },

  // Window controls (custom titlebar on Windows)
  windowMinimize: () => ipcRenderer.invoke('window-minimize'),
  windowMaximize: () => ipcRenderer.invoke('window-maximize'),
  windowClose: () => ipcRenderer.invoke('window-close'),
  windowIsMaximized: () => ipcRenderer.invoke('window-is-maximized'),
  onMaximizeChange: (callback: (maximized: boolean) => void) => {
    const handler = (_event: unknown, max: boolean) => callback(max)
    ipcRenderer.on('window-maximize-changed', handler)
    return () => ipcRenderer.removeListener('window-maximize-changed', handler)
  },

  // App menu / shortcut actions forwarded from the main process.
  onMenuAction: (callback: (action: string) => void) => {
    const handler = (_event: unknown, action: string) => callback(action)
    ipcRenderer.on('menu-action', handler)
    return () => ipcRenderer.removeListener('menu-action', handler)
  },

  // Current app version (e.g. "0.0.5"), shown in the NavRail footer.
  getAppVersion: () => ipcRenderer.invoke('get-app-version'),

  // Auto-update: trigger checks/download/install and subscribe to status.
  checkForUpdate: () => ipcRenderer.invoke('update-check'),
  downloadUpdate: () => ipcRenderer.invoke('update-download'),
  installUpdate: () => ipcRenderer.invoke('update-install'),
  onUpdateStatus: (callback: (status: unknown) => void) => {
    const handler = (_event: unknown, status: unknown) => callback(status)
    ipcRenderer.on('update-status', handler)
    return () => ipcRenderer.removeListener('update-status', handler)
  },

  platform: process.platform,
  // OS UI language (e.g. "zh-CN"), read synchronously so the renderer can pick
  // a default language on first run. Falls back to '' if unavailable.
  systemLocale: (() => {
    try {
      return ipcRenderer.sendSync('get-system-locale') as string
    } catch {
      return ''
    }
  })(),
})
