import { app, BrowserWindow } from 'electron'
// electron-updater is CommonJS: its members live on module.exports, with no
// meaningful default export. Under module=commonjs + esModuleInterop, a named
// import compiles to `electron_updater_1.autoUpdater` and resolves correctly,
// whereas `import pkg from 'electron-updater'` yields undefined.
import { autoUpdater } from 'electron-updater'

// Status payloads pushed to the renderer over the 'update-status' channel.
// The renderer drives the NavRail badge + update panel from these.
export type UpdateStatus =
  | { state: 'checking' }
  | { state: 'available'; version: string; notes?: string }
  | { state: 'not-available' }
  | { state: 'downloading'; percent: number }
  | { state: 'downloaded'; version: string }
  | { state: 'error'; message: string }

let getWindow: () => BrowserWindow | null = () => null

function send(status: UpdateStatus) {
  getWindow()?.webContents.send('update-status', status)
}

export function initUpdater(windowGetter: () => BrowserWindow | null): void {
  getWindow = windowGetter

  // In dev (not packaged) there's no update feed; skip wiring entirely so
  // electron-updater doesn't throw on the missing app-update.yml.
  if (!app.isPackaged) {
    return
  }

  // User-driven flow: we surface "available" and let the user opt in to the
  // download, rather than pulling bytes silently in the background.
  autoUpdater.autoDownload = false
  autoUpdater.autoInstallOnAppQuit = true

  autoUpdater.on('checking-for-update', () => send({ state: 'checking' }))
  autoUpdater.on('update-available', (info) =>
    send({ state: 'available', version: info.version, notes: typeof info.releaseNotes === 'string' ? info.releaseNotes : undefined })
  )
  autoUpdater.on('update-not-available', () => send({ state: 'not-available' }))
  autoUpdater.on('download-progress', (p) =>
    send({ state: 'downloading', percent: Math.round(p.percent) })
  )
  autoUpdater.on('update-downloaded', (info) =>
    send({ state: 'downloaded', version: info.version })
  )
  autoUpdater.on('error', (err) =>
    send({ state: 'error', message: err == null ? 'unknown' : (err.message || String(err)) })
  )
}

// Silent check shortly after launch. When not packaged there's no update feed,
// but a manual click should still get visible feedback instead of looking dead:
// reply "not-available" so the menu can show "up to date".
export function checkForUpdates(): void {
  if (!app.isPackaged) {
    send({ state: 'not-available' })
    return
  }
  autoUpdater.checkForUpdates().catch((err) => {
    send({ state: 'error', message: err?.message || String(err) })
  })
}

export function startDownload(): void {
  if (!app.isPackaged) return
  autoUpdater.downloadUpdate().catch((err) => {
    send({ state: 'error', message: err?.message || String(err) })
  })
}

export function quitAndInstall(): void {
  if (!app.isPackaged) return
  // isSilent=false (show installer), isForceRunAfter=true (relaunch after).
  autoUpdater.quitAndInstall(false, true)
}
