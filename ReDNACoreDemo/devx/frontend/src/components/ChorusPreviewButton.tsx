import { useEffect, useMemo, useState } from 'react'
import { ChorusPayload, getChorus } from '../lib/coachInsightsApi'

interface ChorusPreviewButtonProps {
  userId: string
  contextVersion?: number
  buttonVariant?: 'primary' | 'secondary' | 'ghost'
  className?: string
  label?: string
}

type ChorusTab = 'head' | 'augment' | 'runtime' | 'merged'

interface TabMeta {
  id: ChorusTab
  label: string
  accent: string
  header: string
  border: string
}

const TAB_STYLES: TabMeta[] = [
  {
    id: 'head',
    label: 'Head Coach',
    accent: 'text-blue-600',
    header: 'bg-blue-50',
    border: 'border-blue-200',
  },
  {
    id: 'augment',
    label: 'Augment',
    accent: 'text-orange-600',
    header: 'bg-orange-50',
    border: 'border-orange-200',
  },
  {
    id: 'runtime',
    label: 'Runtime',
    accent: 'text-green-600',
    header: 'bg-green-50',
    border: 'border-green-200',
  },
  {
    id: 'merged',
    label: 'Merged',
    accent: 'text-purple-600',
    header: 'bg-purple-50',
    border: 'border-purple-200',
  },
]

const VARIANT_CLASSES: Record<NonNullable<ChorusPreviewButtonProps['buttonVariant']>, string> = {
  primary: 'px-3 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm font-medium',
  secondary:
    'px-3 py-2 bg-white text-blue-600 border border-blue-200 rounded-md hover:bg-blue-50 text-sm font-medium',
  ghost: 'px-3 py-2 text-blue-600 rounded-md hover:bg-blue-50 text-sm font-medium',
}

export default function ChorusPreviewButton({
  userId,
  contextVersion,
  buttonVariant = 'secondary',
  className,
  label = 'Chorus Preview',
}: ChorusPreviewButtonProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [payload, setPayload] = useState<ChorusPayload | null>(null)
  const [activeTab, setActiveTab] = useState<ChorusTab>('merged')
  const [copied, setCopied] = useState(false)

  const openModal = () => {
    setIsOpen(true)
  }

  useEffect(() => {
    if (!isOpen) {
      setError(null)
      setPayload(null)
      setActiveTab('merged')
      return
    }

    let cancelled = false
    const fetchChorus = async () => {
      setLoading(true)
      setError(null)
      try {
        const data = await getChorus(userId, contextVersion)
        if (!cancelled) {
          setPayload(data)
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load chorus preview')
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    fetchChorus()
    return () => {
      cancelled = true
    }
  }, [isOpen, userId, contextVersion])

  const mergedText = payload?.merged?.text ?? ''

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(mergedText || '')
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch (err) {
      setError('Failed to copy to clipboard')
    }
  }

  const handleExport = () => {
    if (!payload) return
    const fileSafeUser = userId.replace(/[^A-Za-z0-9_-]+/g, '_') || 'user'
    const version = payload.context_version ?? 'latest'
    const blob = new Blob([mergedText || ''], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `chorus_${fileSafeUser}_v${version}.md`
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  }

  const runtimeJson = useMemo(() => {
    if (!payload) return '{}'
    try {
      return JSON.stringify(payload.runtime.json ?? {}, null, 2)
    } catch {
      return '{}'
    }
  }, [payload])

  const variantClass = VARIANT_CLASSES[buttonVariant]

  return (
    <>
      <button
        onClick={openModal}
        className={[variantClass, className].filter(Boolean).join(' ')}
        type="button"
      >
        🎶 {label}
      </button>

      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
          <div className="bg-white w-full max-w-4xl rounded-lg shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
            <div className="flex items-start justify-between px-6 py-4 border-b border-gray-200">
              <div>
                <h2 className="text-xl font-semibold text-gray-900">Chorus Preview</h2>
                <p className="text-sm text-gray-500">
                  {payload
                    ? `User ${userId} • Context v${payload.context_version ?? '—'}`
                    : `User ${userId}`}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={handleCopy}
                  disabled={!payload || loading}
                  className="px-3 py-1.5 bg-blue-50 text-blue-700 rounded-md hover:bg-blue-100 text-sm font-medium disabled:opacity-50"
                >
                  {copied ? 'Copied ✓' : 'Copy Merged'}
                </button>
                <button
                  onClick={handleExport}
                  disabled={!payload || loading}
                  className="px-3 py-1.5 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm font-medium disabled:opacity-50"
                >
                  Export .md
                </button>
                <button
                  onClick={() => setIsOpen(false)}
                  className="px-2 py-1 text-gray-500 hover:text-gray-800 text-sm"
                  aria-label="Close"
                >
                  ✕
                </button>
              </div>
            </div>

            <div className="px-6 pt-4">
              <div className="flex gap-2 border-b border-gray-200">
                {TAB_STYLES.map((tab) => {
                  const labelText = tab.id === 'augment' && payload?.augment?.label
                    ? `Augment (${payload.augment.label})`
                    : tab.label
                  const isActive = activeTab === tab.id
                  return (
                    <button
                      key={tab.id}
                      onClick={() => setActiveTab(tab.id)}
                      className={[
                        'px-3 py-2 text-sm font-medium rounded-t-md transition-colors',
                        isActive ? `${tab.accent} bg-white border-x border-t ${tab.border}` : 'text-gray-500 hover:text-gray-700',
                      ].join(' ')}
                    >
                      {labelText}
                    </button>
                  )
                })}
              </div>
            </div>

            <div className="flex-1 overflow-auto px-6 py-4 bg-gray-50">
              {loading && (
                <div className="flex items-center justify-center h-64 text-gray-500 text-sm">
                  Loading chorus preview…
                </div>
              )}

              {error && !loading && (
                <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md text-sm">
                  {error}
                </div>
              )}

              {!loading && !error && payload && (
                <div className="space-y-4">
                  {activeTab === 'head' && (
                    <section className="bg-white border border-blue-200 rounded-md shadow-sm">
                      <header className="px-4 py-2 border-b border-blue-100 bg-blue-50">
                        <h3 className="text-sm font-semibold text-blue-700">Head Coach Mandate</h3>
                        <p className="text-xs text-blue-500 font-mono">hash {payload.head_coach.hash}</p>
                      </header>
                      <pre className="p-4 text-sm text-gray-800 whitespace-pre-wrap font-mono overflow-x-auto">
                        {payload.head_coach.text || '—'}
                      </pre>
                    </section>
                  )}

                  {activeTab === 'augment' && (
                    <section className="bg-white border border-orange-200 rounded-md shadow-sm">
                      <header className="px-4 py-2 border-b border-orange-100 bg-orange-50">
                        <h3 className="text-sm font-semibold text-orange-700">
                          Augmentation — {payload.augment.label || 'Head Coach'}
                        </h3>
                        <p className="text-xs text-orange-500 font-mono">hash {payload.augment.hash}</p>
                      </header>
                      <pre className="p-4 text-sm text-gray-800 whitespace-pre-wrap font-mono overflow-x-auto">
                        {payload.augment.text ? payload.augment.text : 'No augmentation loaded'}
                      </pre>
                    </section>
                  )}

                  {activeTab === 'runtime' && (
                    <section className="bg-white border border-green-200 rounded-md shadow-sm">
                      <header className="px-4 py-2 border-b border-green-100 bg-green-50">
                        <h3 className="text-sm font-semibold text-green-700">Runtime Behavior Context</h3>
                        <p className="text-xs text-green-500 font-mono">hash {payload.runtime.hash}</p>
                      </header>
                      <pre className="p-4 text-xs text-gray-800 whitespace-pre font-mono overflow-x-auto">
                        {runtimeJson}
                      </pre>
                    </section>
                  )}

                  {activeTab === 'merged' && (
                    <section className="bg-white border border-purple-200 rounded-md shadow-sm">
                      <header className="px-4 py-2 border-b border-purple-100 bg-purple-50">
                        <h3 className="text-sm font-semibold text-purple-700">Merged Prompt</h3>
                        <p className="text-xs text-purple-500 font-mono">hash {payload.merged.hash}</p>
                      </header>
                      <pre className="p-4 text-sm text-gray-800 whitespace-pre-wrap font-mono overflow-x-auto">
                        {mergedText || '—'}
                      </pre>
                    </section>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  )
}
