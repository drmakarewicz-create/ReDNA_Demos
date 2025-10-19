import { useState, useEffect } from 'react'
import { DEVX_API_BASE } from '@/lib/env'

const API_BASE = DEVX_API_BASE

interface LayerCheck {
  layer: string
  label: string
  required: boolean
  pass: boolean
  details: string
}

interface ChecklistResponse {
  id: string
  ready: boolean
  layers: LayerCheck[]
  summary: {
    required_passed: number
    required_total: number
    optional_passed: number
    optional_total: number
  }
}

interface ChecklistTabProps {
  coachId: string
  coachLabel: string
}

const HOW_TO_FIX: Record<string, string> = {
  coach_registry:
    'Add coach definition to ReDNACoreDemo/core/coach_registry.yaml under coaches: section with full metadata.',
  mode_manager:
    'Update ReDNACoreDemo/core/coach_mode_manager.py: Add to VALID_MODES, MODE_DISPLAY_NAMES, and MODE_CAPABILITIES.',
  ui_readonly:
    'Update ReDNACoreDemo/core/ui_readonly.py: Add icon to _DEFAULT_ICONS and entry to _FALLBACK_PERSONAS.',
  api_ts:
    'Update web/src/lib/api.ts: Add to CANONICAL_ORDER, CANONICAL_DEFAULTS, and PERSONA_ALIASES. This is the most critical layer!',
  page_client:
    'Update web/src/app/page-client.tsx: Add to normalizePersonaKey return type, switch statement, shouldShowCoachToolsPane, and renderRightPane.',
  core_api_prompts:
    'Update ReDNACoreDemo/core/api.py: Add coach to SYSTEM_PROMPT, PERSONA_PROMPTS, and PERSONA_RUBRICS (3 locations).',
  hc_llm_agent:
    'Update ReDNACoreDemo/core/hc_llm_agent.py: Add coach to _build_system_message function with description and capabilities.'
}

export default function ChecklistTab({ coachId, coachLabel }: ChecklistTabProps) {
  const [checklist, setChecklist] = useState<ChecklistResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [scanning, setScanning] = useState(false)

  useEffect(() => {
    loadChecklist()
  }, [coachId])

  const loadChecklist = async () => {
    setLoading(true)
    try {
      const response = await fetch(`${API_BASE}/coaches/${encodeURIComponent(coachId)}/checklist`)
      if (!response.ok) throw new Error(`HTTP ${response.status}`)

      const data = await response.json()
      setChecklist(data)
    } catch (error) {
      console.error('Failed to load checklist:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleRescan = async () => {
    setScanning(true)
    await loadChecklist()
    setScanning(false)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12">
        <div className="text-gray-500">Loading checklist...</div>
      </div>
    )
  }

  if (!checklist) {
    return (
      <div className="flex items-center justify-center p-12">
        <div className="text-gray-500">No checklist data available</div>
      </div>
    )
  }

  const allPassed = checklist.ready
  const requiredPassed = checklist.summary.required_passed
  const requiredTotal = checklist.summary.required_total
  const optionalPassed = checklist.summary.optional_passed
  const optionalTotal = checklist.summary.optional_total

  return (
    <div className="space-y-6">
      {/* Coach Name Header */}
      <div className="pb-3 border-b border-gray-200">
        <h2 className="text-xl font-bold text-gray-900">{coachLabel}</h2>
        <p className="text-sm text-gray-500 mt-1">7-layer integration verification</p>
      </div>

      {/* Header with status badge and rescan button */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <h3 className="text-lg font-semibold text-gray-900">Integration Status</h3>
          <span
            className={`px-3 py-1 rounded-full text-sm font-medium ${
              allPassed
                ? 'bg-green-100 text-green-800'
                : 'bg-amber-100 text-amber-800'
            }`}
          >
            {allPassed ? '✅ Ready' : '⚠️ Incomplete'}
          </span>
        </div>
        <button
          onClick={handleRescan}
          disabled={scanning}
          className="px-4 py-2 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
        >
          {scanning ? 'Scanning...' : '🔄 Re-scan'}
        </button>
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-blue-50 border border-blue-200 rounded-md p-4">
          <div className="text-sm text-blue-600 font-medium">Required Layers</div>
          <div className="text-2xl font-bold text-blue-900">
            {requiredPassed} / {requiredTotal}
          </div>
          <div className="text-xs text-blue-600 mt-1">
            {requiredPassed === requiredTotal ? 'All passed!' : 'Some required layers missing'}
          </div>
        </div>

        <div className="bg-gray-50 border border-gray-200 rounded-md p-4">
          <div className="text-sm text-gray-600 font-medium">Optional Layers</div>
          <div className="text-2xl font-bold text-gray-900">
            {optionalPassed} / {optionalTotal}
          </div>
          <div className="text-xs text-gray-600 mt-1">
            {optionalPassed === optionalTotal ? 'All passed!' : 'Some optional layers missing'}
          </div>
        </div>
      </div>

      {/* Layer status grid */}
      <div className="space-y-2">
        {checklist.layers.map((layer) => (
          <div
            key={layer.layer}
            className={`flex items-start justify-between p-4 rounded-md border ${
              layer.pass
                ? 'bg-green-50 border-green-200'
                : layer.required
                ? 'bg-red-50 border-red-200'
                : 'bg-amber-50 border-amber-200'
            }`}
          >
            <div className="flex-1">
              <div className="flex items-center space-x-2">
                <span className="text-lg">{layer.pass ? '✅' : '❌'}</span>
                <div>
                  <div className="font-medium text-gray-900">
                    {layer.label}
                    {layer.required && (
                      <span className="ml-2 text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded">
                        Required
                      </span>
                    )}
                  </div>
                  <div
                    className={`text-sm ${
                      layer.pass ? 'text-green-700' : 'text-gray-700'
                    }`}
                  >
                    {layer.details}
                  </div>
                </div>
              </div>
            </div>

            {!layer.pass && HOW_TO_FIX[layer.layer] && (
              <div className="ml-4">
                <details className="text-xs text-gray-600">
                  <summary className="cursor-pointer hover:text-blue-600 font-medium">
                    How to fix
                  </summary>
                  <div className="mt-2 p-2 bg-white border border-gray-200 rounded text-gray-700 max-w-md">
                    {HOW_TO_FIX[layer.layer]}
                  </div>
                </details>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Protocol reference */}
      <div className="bg-blue-50 border border-blue-200 rounded-md p-4">
        <div className="text-sm font-medium text-blue-900">📚 Protocol Reference</div>
        <div className="text-xs text-blue-700 mt-1">
          For detailed integration instructions, see{' '}
          <code className="bg-blue-100 px-1 py-0.5 rounded">
            docs/ADDING_NEW_COACH_PROTOCOL.md
          </code>
        </div>
      </div>
    </div>
  )
}
