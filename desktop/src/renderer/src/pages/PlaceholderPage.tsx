import React from 'react'
import { Construction } from 'lucide-react'

interface PlaceholderPageProps {
  title: string
  hint?: string
}

/** Temporary page for routes that will be implemented in later phases. */
const PlaceholderPage: React.FC<PlaceholderPageProps> = ({ title, hint }) => (
  <div className="flex flex-col items-center justify-center h-full text-center px-8">
    <div className="w-14 h-14 rounded-2xl bg-surface-2 flex items-center justify-center mb-4">
      <Construction size={26} className="text-content-tertiary" />
    </div>
    <h2 className="text-lg font-semibold text-content mb-1">{title}</h2>
    <p className="text-sm text-content-tertiary max-w-sm">{hint || 'Coming soon in this iteration.'}</p>
  </div>
)

export default PlaceholderPage
