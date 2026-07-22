import React, { useEffect, useState } from 'react'
import { Minus, Square, Copy, X } from 'lucide-react'

/**
 * Custom window controls for the frameless Windows titlebar.
 * On macOS the system renders traffic lights, so this returns null there.
 */
const WindowControls: React.FC = () => {
  const [maximized, setMaximized] = useState(false)
  const api = window.electronAPI

  useEffect(() => {
    api?.windowIsMaximized().then(setMaximized)
    const off = api?.onMaximizeChange(setMaximized)
    return off
  }, [api])

  if (api?.platform === 'darwin') return null

  const btn =
    'titlebar-no-drag inline-flex items-center justify-center w-11 h-full text-content-tertiary hover:text-content cursor-pointer transition-colors'

  return (
    <div className="flex items-stretch h-full">
      <button className={`${btn} hover:bg-surface-2`} onClick={() => api?.windowMinimize()} aria-label="Minimize">
        <Minus size={15} strokeWidth={2} />
      </button>
      <button className={`${btn} hover:bg-surface-2`} onClick={() => api?.windowMaximize()} aria-label="Maximize">
        {maximized ? <Copy size={12} strokeWidth={2} /> : <Square size={12} strokeWidth={2} />}
      </button>
      <button
        className={`${btn} hover:bg-danger hover:text-white`}
        onClick={() => api?.windowClose()}
        aria-label="Close"
      >
        <X size={16} strokeWidth={2} />
      </button>
    </div>
  )
}

export default WindowControls
