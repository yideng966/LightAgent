import { ChildProcess, spawn } from 'child_process'
import { EventEmitter } from 'events'
import path from 'path'
import os from 'os'
import fs from 'fs'
import http from 'http'
import net from 'net'

// Writable data dir for the packaged app (config.json, run.log, user data).
// Lives in the user's home so it survives app updates and avoids writing into
// the read-only app bundle. Source/dev runs keep using the repo CWD instead.
const LIGHTAGENT_DATA_DIR = path.join(os.homedir(), '.lightagent')

// Fixed port for the desktop backend. Deliberately not 9899 (the web console's
// default) so a source-run `python app.py` never collides with the packaged
// app. This is a SINGLE SOURCE OF TRUTH shared with the renderer (see
// useBackend.ts BACKEND_PORT): the backend is always told to bind exactly here
// via LIGHTAGENT_WEB_PORT, and the renderer always talks to exactly here. We do NOT
// fall back to an OS-random port, because the renderer could never guess it —
// instead we proactively free this port before launch (see freePort()).
export const DESKTOP_BACKEND_PORT = 9876

export class PythonBackend extends EventEmitter {
  private process: ChildProcess | null = null
  private backendPath: string
  private port: number = DESKTOP_BACKEND_PORT
  private status: 'stopped' | 'starting' | 'ready' | 'error' = 'stopped'

  constructor(backendPath: string) {
    super()
    this.backendPath = backendPath
  }

  getPort(): number {
    return this.port
  }

  getStatus(): string {
    return this.status
  }

  /**
   * Locate the packaged onedir backend executable shipped with the app.
   * Returns null when not present (e.g. during local development), so we can
   * fall back to running app.py with a system/venv Python.
   */
  private findBundledBackend(): string | null {
    const exeName = process.platform === 'win32' ? 'lightagent-backend.exe' : 'lightagent-backend'
    const candidates = [
      path.join(this.backendPath, 'lightagent-backend', exeName),
      path.join(this.backendPath, exeName),
    ]
    for (const p of candidates) {
      if (fs.existsSync(p)) {
        return p
      }
    }
    return null
  }

  private findPython(): string {
    const venvPaths = [
      path.join(this.backendPath, '.venv', 'bin', 'python'),
      path.join(this.backendPath, '.venv', 'Scripts', 'python.exe'),
      path.join(this.backendPath, 'venv', 'bin', 'python'),
      path.join(this.backendPath, 'venv', 'Scripts', 'python.exe'),
    ]

    for (const p of venvPaths) {
      if (fs.existsSync(p)) {
        return p
      }
    }

    return process.platform === 'win32' ? 'python' : 'python3'
  }

  /**
   * Read an explicit `web_port` from config.json, if the user pinned one. The
   * packaged build keeps config in LIGHTAGENT_DATA_DIR (~/.lightagent); dev reads it from the
   * repo path. Returns null when unset, so the caller can auto-pick a free port
   * instead of fighting over a fixed one.
   */
  private readConfiguredPort(dataDir: string): number | null {
    try {
      const configPath = path.join(dataDir, 'config.json')
      if (fs.existsSync(configPath)) {
        const config = JSON.parse(fs.readFileSync(configPath, 'utf-8'))
        const p = Number(config.web_port)
        if (Number.isInteger(p) && p > 0 && p < 65536) {
          return p
        }
      }
    } catch {
      // ignore — fall through to auto-selection
    }
    return null
  }

  /**
   * Resolve the port to bind. The whole point is determinism: the renderer must
   * be able to reach the backend WITHOUT guessing, so we use exactly one fixed
   * port (DESKTOP_BACKEND_PORT) unless the user explicitly pinned a web_port.
   * We never auto-roll to a random port — instead start() proactively frees the
   * fixed port. The returned value is the single source of truth handed to both
   * the backend (LIGHTAGENT_WEB_PORT) and the renderer (getBackendPort IPC).
   */
  private resolvePort(dataDir: string): number {
    const pinned = this.readConfiguredPort(dataDir)
    return pinned !== null ? pinned : DESKTOP_BACKEND_PORT
  }

  /** True if we can bind 127.0.0.1:port right now (i.e. it's free). */
  private isPortFree(port: number): Promise<boolean> {
    return new Promise((resolve) => {
      const tester = net
        .createServer()
        .once('error', () => resolve(false))
        .once('listening', () => {
          tester.close(() => resolve(true))
        })
        .listen(port, '127.0.0.1')
    })
  }

  /**
   * Make sure our fixed port is usable before launch by killing whatever is
   * holding it (almost always a stale backend from a previous run that didn't
   * shut down cleanly). We only ever target a process actually listening on
   * 127.0.0.1:<port>, so we won't touch unrelated apps. Best-effort: if we
   * can't free it we still try to bind and let the backend surface EADDRINUSE.
   */
  private async freePort(port: number): Promise<void> {
    if (await this.isPortFree(port)) {
      return
    }
    this.emit('log', `Port ${port} is busy — clearing stale process before launch`)
    const pids = await this.findListenerPids(port)
    for (const pid of pids) {
      // Never signal ourselves (Electron could, in theory, be the listener).
      if (pid === process.pid) continue
      try {
        process.kill(pid, 'SIGTERM')
      } catch {
        // already gone / no permission — ignore
      }
    }
    // Give the OS a beat to release the socket, then force-kill leftovers.
    await new Promise((r) => setTimeout(r, 600))
    if (!(await this.isPortFree(port))) {
      for (const pid of await this.findListenerPids(port)) {
        if (pid === process.pid) continue
        try {
          process.kill(pid, 'SIGKILL')
        } catch {
          // ignore
        }
      }
      await new Promise((r) => setTimeout(r, 400))
    }
  }

  /** PIDs listening on 127.0.0.1:<port>, via lsof (POSIX) / netstat (Windows). */
  private findListenerPids(port: number): Promise<number[]> {
    return new Promise((resolve) => {
      const isWin = process.platform === 'win32'
      const cmd = isWin ? 'netstat' : 'lsof'
      const args = isWin
        ? ['-ano', '-p', 'tcp']
        : ['-nP', `-iTCP:${port}`, '-sTCP:LISTEN', '-t']
      let out = ''
      try {
        const child = spawn(cmd, args)
        child.stdout?.on('data', (d: Buffer) => (out += d.toString()))
        child.on('error', () => resolve([]))
        child.on('close', () => {
          const pids = new Set<number>()
          if (isWin) {
            // Match lines like: TCP 127.0.0.1:9876 ... LISTENING  12345
            for (const line of out.split('\n')) {
              if (!/LISTENING/i.test(line)) continue
              if (!new RegExp(`[:.]${port}\\b`).test(line)) continue
              const pid = Number(line.trim().split(/\s+/).pop())
              if (Number.isInteger(pid) && pid > 0) pids.add(pid)
            }
          } else {
            for (const tok of out.split(/\s+/)) {
              const pid = Number(tok)
              if (Number.isInteger(pid) && pid > 0) pids.add(pid)
            }
          }
          resolve([...pids])
        })
      } catch {
        resolve([])
      }
    })
  }

  async start(): Promise<void> {
    if (this.status === 'ready' || this.status === 'starting') {
      return
    }

    this.status = 'starting'

    // Prefer the packaged self-contained backend (production); fall back to
    // running app.py with a Python interpreter (local development).
    const bundled = this.findBundledBackend()
    // Packaged app stores writable data in ~/.lightagent; dev keeps it in the repo.
    const dataDir = bundled ? LIGHTAGENT_DATA_DIR : this.backendPath

    // Always launch our OWN backend (re-entrancy is guarded above by the status
    // check, so we never double-spawn for this instance). We don't reuse
    // whatever happens to be on the port: that's how the app previously attached
    // to a source-run web console and read the wrong config. The port is fixed
    // (or the user's pinned web_port) — never random — so the renderer always
    // knows it. We then proactively free that port (kill stale listeners)
    // before spawning, so a leftover process from a previous run can't block us.
    this.port = this.resolvePort(dataDir)
    await this.freePort(this.port)

    let command: string
    let args: string[]
    let cwd: string

    if (bundled) {
      command = bundled
      args = []
      // Run from the writable data dir (~/.lightagent), NOT the install dir. When the
      // app is installed under Program Files, a non-admin user has no write
      // permission to the executable's folder, so any relative-path write
      // during startup would crash the backend (works only as admin). The
      // bundle reads its read-only resources via sys._MEIPASS, so cwd is free
      // to point elsewhere.
      try {
        fs.mkdirSync(LIGHTAGENT_DATA_DIR, { recursive: true })
      } catch {
        // ignore — get_data_root() also ensures the dir on the Python side
      }
      cwd = LIGHTAGENT_DATA_DIR
      this.emit('log', `Starting bundled backend: ${bundled} (cwd=${cwd})`)
    } else {
      const pythonPath = this.findPython()
      const appPath = path.join(this.backendPath, 'app.py')
      if (!fs.existsSync(appPath)) {
        this.status = 'error'
        this.emit('error', `app.py not found at ${appPath}`)
        return
      }
      command = pythonPath
      args = [appPath]
      cwd = this.backendPath
      this.emit('log', `Starting Python backend: ${pythonPath} ${appPath}`)
    }

    this.process = spawn(command, args, {
      cwd,
      // LIGHTAGENT_DESKTOP enables the lighter desktop runtime (no plugins, no MCP).
      // LIGHTAGENT_DATA_DIR (packaged only) redirects writable data to ~/.lightagent so the
      // app bundle stays read-only; dev runs omit it and keep using the repo.
      env: {
        ...process.env,
        PYTHONUNBUFFERED: '1',
        LIGHTAGENT_DESKTOP: '1',
        // The shell owns the port: tell the backend to bind exactly here so the
        // two sides can never disagree (and we avoid the 9899 web-console clash).
        LIGHTAGENT_WEB_PORT: String(this.port),
        ...(bundled ? { LIGHTAGENT_DATA_DIR } : {}),
      },
      stdio: ['pipe', 'pipe', 'pipe'],
    })

    this.process.stdout?.on('data', (data: Buffer) => {
      const lines = data.toString().split('\n').filter(Boolean)
      for (const line of lines) {
        this.emit('log', line)
      }
    })

    this.process.stderr?.on('data', (data: Buffer) => {
      const lines = data.toString().split('\n').filter(Boolean)
      for (const line of lines) {
        this.emit('log', line)
      }
    })

    this.process.on('exit', (code) => {
      // If the backend dies before it ever became ready, surface an error now
      // instead of letting waitForReady spin for the full timeout. A clean exit
      // (code 0/null, e.g. our own stop()) just marks stopped.
      const wasReady = this.status === 'ready'
      this.status = 'stopped'
      this.emit('log', `Python process exited with code ${code}`)
      if (!wasReady && code !== 0 && code !== null) {
        this.status = 'error'
        this.emit('error', `Backend exited during startup (code ${code})`)
      }
    })

    this.process.on('error', (err) => {
      this.status = 'error'
      this.emit('error', `Failed to start Python: ${err.message}`)
    })

    await this.waitForReady()
  }

  private waitForReady(): Promise<void> {
    return new Promise((resolve) => {
      // Wall-clock deadline rather than an attempt counter: if the machine
      // sleeps/suspends, the 1s timers stretch out and a counter would give up
      // far too early. Time-based bounding tracks real elapsed time instead.
      const timeoutMs = 120_000
      const startedAt = Date.now()

      const check = () => {
        const req = http.get(`http://127.0.0.1:${this.port}/config`, (res) => {
          if (res.statusCode === 200) {
            this.status = 'ready'
            this.emit('log', `Backend ready on port ${this.port}`)
            this.emit('ready', this.port)
            resolve()
          } else {
            retry()
          }
        })

        req.on('error', () => retry())
        req.setTimeout(2000, () => {
          req.destroy()
          retry()
        })
      }

      const retry = () => {
        // Backend already settled: ready (done), or stopped/errored by the exit
        // handler (don't keep polling a dead process — the error was emitted).
        if (this.status === 'ready' || this.status === 'stopped' || this.status === 'error') {
          resolve()
          return
        }
        if (Date.now() - startedAt >= timeoutMs) {
          this.status = 'error'
          this.emit('error', `Backend failed to start within ${Math.round(timeoutMs / 1000)} seconds`)
          resolve()
          return
        }
        setTimeout(check, 1000)
      }

      setTimeout(check, 2000)
    })
  }

  stop(): void {
    const proc = this.process
    if (proc) {
      proc.kill('SIGTERM')
      // Keep a local ref so the SIGKILL fallback can still reach the process
      // even after we clear `this.process`; otherwise a stuck backend would
      // never be force-killed and leak as a zombie.
      setTimeout(() => {
        if (!proc.killed) {
          proc.kill('SIGKILL')
        }
      }, 5000)
      this.process = null
    }
    this.status = 'stopped'
  }

  async restart(): Promise<void> {
    this.stop()
    await new Promise((resolve) => setTimeout(resolve, 2000))
    await this.start()
  }
}
