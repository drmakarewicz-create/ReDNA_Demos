import { useState, useEffect } from 'react'
import DynamicCoachPanes from '@/components/dynamic-coach-panes'
import { DEVX_API_BASE } from '@/lib/env'

const API_BASE = DEVX_API_BASE

interface FeaturesConfig {
  version: string
  showInUI: boolean
  panes: PaneConfig[]
}

interface PaneConfig {
  title: string
  type: 'slider' | 'switch' | 'text' | 'select' | 'meter'
  path: string
  min?: number
  max?: number
  options?: string[]
  defaultValue?: any
}

interface FeaturesTabProps {
  coachId: string
  coachLabel: string
}

export default function FeaturesTab({ coachId, coachLabel }: FeaturesTabProps) {
  const [config, setConfig] = useState<FeaturesConfig | null>(null)
  const [jsonText, setJsonText] = useState('')
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [hasChanges, setHasChanges] = useState(false)
  const [previewValues, setPreviewValues] = useState<Record<string, any>>({})

  useEffect(() => {
    loadFeatures()
  }, [coachId])

  const loadFeatures = async () => {
    setLoading(true)
    setMessage(null)
    try {
      const response = await fetch(`${API_BASE}/coaches/${encodeURIComponent(coachId)}/features`)
      if (!response.ok) throw new Error(`HTTP ${response.status}`)

      const data = await response.json()
      setConfig(data.config)
      setJsonText(JSON.stringify(data.config, null, 2))
      setHasChanges(false)
    } catch (error) {
      setMessage({ type: 'error', text: `Failed to load features: ${error}` })
    } finally {
      setLoading(false)
    }
  }

  const handleJsonChange = (newText: string) => {
    setJsonText(newText)
    setHasChanges(true)

    // Try to parse and update preview
    try {
      const parsed = JSON.parse(newText)
      setConfig(parsed)
      setMessage(null)
    } catch (error) {
      // Invalid JSON - don't update preview
      setMessage({ type: 'error', text: 'Invalid JSON syntax' })
    }
  }

  const handleSave = async () => {
    try {
      const parsed = JSON.parse(jsonText)

      setSaving(true)
      setMessage(null)

      const response = await fetch(
        `${API_BASE}/coaches/${encodeURIComponent(coachId)}/features`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ config: parsed })
        }
      )

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || `HTTP ${response.status}`)
      }

      const result = await response.json()
      setMessage({
        type: 'success',
        text: `Saved! ${result.backup_created ? '(Backup created)' : ''}`
      })
      setHasChanges(false)
      setConfig(parsed)
    } catch (error) {
      setMessage({ type: 'error', text: `Failed to save: ${error}` })
    } finally {
      setSaving(false)
    }
  }

  const handleRevert = () => {
    if (config) {
      setJsonText(JSON.stringify(config, null, 2))
      setHasChanges(false)
      setMessage(null)
    }
  }

  const handleDownload = () => {
    const blob = new Blob([jsonText], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${coachId}_features.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12">
        <div className="text-gray-500">Loading features...</div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Coach Name Header */}
      <div className="pb-3 border-b border-gray-200">
        <h2 className="text-xl font-bold text-gray-900">{coachLabel}</h2>
        <p className="text-sm text-gray-500 mt-1">Configure UI features and controls</p>
      </div>

      <div className="grid grid-cols-2 gap-6 h-full">
        {/* Left: JSON Editor */}
        <div className="flex flex-col space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-gray-900">Features JSON</h3>
          <div className="flex gap-2">
            <button
              onClick={handleRevert}
              disabled={!hasChanges}
              className="px-3 py-1 text-sm border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Revert
            </button>
            <button
              onClick={handleDownload}
              className="px-3 py-1 text-sm border border-gray-300 rounded-md hover:bg-gray-50"
            >
              Download
            </button>
            <button
              onClick={handleSave}
              disabled={saving || !hasChanges}
              className="px-3 py-1 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {saving ? 'Saving...' : 'Save'}
            </button>
          </div>
        </div>

        <textarea
          value={jsonText}
          onChange={(e) => handleJsonChange(e.target.value)}
          className="flex-1 p-4 font-mono text-sm border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          spellCheck={false}
        />

        {message && (
          <div
            className={`p-3 rounded-md text-sm ${
              message.type === 'success'
                ? 'bg-green-50 text-green-800 border border-green-200'
                : 'bg-red-50 text-red-800 border border-red-200'
            }`}
          >
            {message.text}
          </div>
        )}
      </div>

      {/* Right: Live Preview */}
      <div className="flex flex-col space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-gray-900">Live Preview</h3>
          {config && (
            <div className="text-sm text-gray-600">
              <span className="font-medium">Version:</span> {config.version} |{' '}
              <span className="font-medium">Show in UI:</span>{' '}
              <span className={config.showInUI ? 'text-green-600' : 'text-gray-400'}>
                {config.showInUI ? 'Yes' : 'No'}
              </span>
            </div>
          )}
        </div>

        {config ? (
          config.panes.length === 0 ? (
            <div className="flex-1 p-12 bg-gray-50 rounded-md border-2 border-dashed border-gray-300 text-center">
              <div className="text-gray-400 text-4xl mb-3">🎛️</div>
              <div className="text-sm text-gray-500 italic">No panes configured</div>
              <div className="text-xs text-gray-400 mt-2">
                Add panes in the JSON editor to see them here
              </div>
            </div>
          ) : (
            <div className="flex-1 p-6 bg-gray-50 rounded-md border border-gray-200">
              <div className="max-w-md">
                <div className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-3">
                  {coachLabel} Features (Preview)
                </div>
                <DynamicCoachPanes
                  coachId={coachId}
                  panes={config.panes}
                  featureState={previewValues}
                  onChange={(partial) => {
                    setPreviewValues(prev => ({ ...prev, ...partial }))
                  }}
                  onWarning={(msg) => console.warn('Preview warning:', msg)}
                />
                <div className="mt-4 pt-4 border-t border-gray-300">
                  <div className="text-xs font-medium text-gray-500 mb-2">Current Values:</div>
                  <pre className="text-xs bg-white p-2 rounded border border-gray-200 overflow-x-auto">
                    {JSON.stringify(previewValues, null, 2)}
                  </pre>
                </div>
              </div>
            </div>
          )
        ) : (
          <div className="flex-1 p-12 bg-gray-50 rounded-md border border-gray-200 text-center">
            <div className="text-sm text-gray-500 italic">No preview available</div>
          </div>
        )}
      </div>
      </div>
    </div>
  )
}
