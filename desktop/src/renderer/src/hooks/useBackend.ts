import { useState, useEffect, useCallback, useRef } from 'react'

// Fixed default port — MUST match DESKTOP_BACKEND_PORT in main/python-manager.ts.
// The backend is launched on exactly this port (the main process frees it first
// and passes it via LIGHTAGENT_WEB_PORT), so probing it works even before the
// getBackendPort IPC resolves. Keeping both sides on one constant means the
// renderer can never end up talking to the wrong port.
const BACKEND_PORT = 9876

interface BackendState {
  status: 'connecting' | 'ready' | 'error'
  port: number
  error?: string
}

export function useBackend() {
  const [state, setState] = useState<BackendState>({
    status: 'connecting',
    port: BACKEND_PORT,
  })
  const pollingRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const probeBackend = useCallback(async (port: number): Promise<boolean> => {
    try {
      const res = await fetch(`http://127.0.0.1:${port}/config`, {
        signal: AbortSignal.timeout(3000),
      })
      return res.ok
    } catch {
      return false
    }
  }, [])

  // True once the backend has answered at least once. After this we never flip
  // back to "error" from polling — a hidden/backgrounded window throttles JS
  // timers, so attempt counters are unreliable and would otherwise produce a
  // false "failed to start" even though the backend is alive.
  const readyRef = useRef(false)
  // Holds the latest resolved port so the visibility handler (registered once)
  // always probes the correct port without re-running the effect.
  const portRef = useRef(BACKEND_PORT)

  useEffect(() => {
    let cancelled = false
    let offStatus: (() => void) | undefined
    const api = window.electronAPI

    // Use a wall-clock deadline instead of an attempt counter so timer
    // throttling (when the window is in the background) can't fast-forward us
    // into a false failure. Only give up if we genuinely can't reach the
    // backend for this long.
    const startPolling = async (port: number) => {
      portRef.current = port
      const deadline = Date.now() + 90_000

      const poll = async () => {
        if (cancelled) return

        const ready = await probeBackend(port)
        if (cancelled) return

        if (ready) {
          readyRef.current = true
          setState({ status: 'ready', port })
          return
        }

        // Backend already answered before but is briefly unreachable (e.g.
        // window was asleep): keep retrying, never surface an error.
        if (!readyRef.current && Date.now() >= deadline) {
          // Leave error undefined so StatusScreen shows the localized,
          // user-friendly message instead of a raw technical string.
          setState({ status: 'error', port })
          return
        }

        pollingRef.current = setTimeout(poll, 1000)
      }

      await poll()
    }

    if (api) {
      // Always start polling, even if getBackendPort rejects or the ready event
      // was already emitted before we subscribed: polling /config is the
      // self-sufficient path to "ready" and must never depend on the IPC round
      // trip succeeding (otherwise the app can hang forever on "connecting").
      api
        .getBackendPort()
        .then((port) => {
          const p = port || BACKEND_PORT
          portRef.current = p
          setState((prev) => ({ ...prev, port: p }))
          startPolling(p)
        })
        .catch(() => {
          startPolling(BACKEND_PORT)
        })

      offStatus = api.onBackendStatus((data) => {
        if (data.status === 'ready' && data.port) {
          readyRef.current = true
          portRef.current = data.port
          setState({ status: 'ready', port: data.port })
          if (pollingRef.current) {
            clearTimeout(pollingRef.current)
            pollingRef.current = null
          }
        } else if (data.status === 'error' && !readyRef.current) {
          // Ignore late "error" from the main process once we've been ready —
          // it usually means the window was backgrounded, not a real failure.
          // Drop the raw technical message; StatusScreen shows a localized one.
          setState((prev) => ({ ...prev, status: 'error' }))
        }
      })
    } else {
      startPolling(BACKEND_PORT)
    }

    // When the window comes back to the foreground, re-probe immediately so a
    // user returning after a while sees the real (ready) state right away
    // instead of waiting for the throttled timer to catch up.
    const onVisible = () => {
      if (cancelled || document.visibilityState !== 'visible') return
      probeBackend(portRef.current).then((ready) => {
        if (cancelled || !ready) return
        readyRef.current = true
        setState((prev) => ({ ...prev, status: 'ready' }))
      })
    }
    document.addEventListener('visibilitychange', onVisible)

    return () => {
      cancelled = true
      if (pollingRef.current) {
        clearTimeout(pollingRef.current)
      }
      offStatus?.()
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [probeBackend])

  const restart = useCallback(async () => {
    setState((prev) => ({ ...prev, status: 'connecting', error: undefined }))
    if (window.electronAPI) {
      await window.electronAPI.restartBackend()
    }
  }, [])

  const baseUrl = `http://127.0.0.1:${state.port}`

  return { ...state, baseUrl, restart }
}
