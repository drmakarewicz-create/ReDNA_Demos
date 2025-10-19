import { useState, useEffect } from 'react'
import { DEVX_API_BASE } from '@/lib/env'

const API_BASE = DEVX_API_BASE

interface InsightsTabProps {
  coachId: string
  coachLabel: string
}

interface InsightsData {
  coach_id: string
  items: any[]
  total: number
  message?: string
}

type FilterKind = 'all' | 'summary' | 'metric' | 'telemetry'

export default function InsightsTab({ coachId, coachLabel }: InsightsTabProps) {
  const [insights, setInsights] = useState<InsightsData | null>(null)
  const [loading, setLoading] = useState(false)
  const [appending, setAppending] = useState(false)
  const [filterKind, setFilterKind] = useState<FilterKind>('all')
  const [expandedItems, setExpandedItems] = useState<Set<number>>(new Set())

  useEffect(() => {
    loadInsights()
  }, [coachId, filterKind])

  const loadInsights = async () => {
    setLoading(true)
    try {
      const kindsParam = filterKind === 'all' ? '' : `?kinds=${filterKind}`
      const response = await fetch(`${API_BASE}/coaches/${encodeURIComponent(coachId)}/insights${kindsParam}`)
      if (response.ok) {
        const data = await response.json()
        setInsights(data)
      }
    } catch (error) {
      console.error('Failed to load insights:', error)
    } finally {
      setLoading(false)
    }
  }

  const toggleExpanded = (idx: number) => {
    const newExpanded = new Set(expandedItems)
    if (newExpanded.has(idx)) {
      newExpanded.delete(idx)
    } else {
      newExpanded.add(idx)
    }
    setExpandedItems(newExpanded)
  }

  const handleAppendTest = async () => {
    setAppending(true)
    try {
      const testInsight = {
        kind: 'note',
        data: {
          message: 'Test insight appended from Coach Workshop',
          timestamp: new Date().toISOString()
        }
      }

      const response = await fetch(`${API_BASE}/coaches/${encodeURIComponent(coachId)}/insights/append`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(testInsight)
      })

      if (response.ok) {
        await loadInsights()
      }
    } catch (error) {
      console.error('Failed to append insight:', error)
    } finally {
      setAppending(false)
    }
  }

  const formatTimestamp = (ts: string) => {
    try {
      return new Date(ts).toLocaleString()
    } catch {
      return ts
    }
  }

  const renderTelemetryCard = (item: any, idx: number) => {
    const hints = item.data?.hints || {}
    const outcome = item.data?.outcome || {}
    const isExpanded = expandedItems.has(idx)

    return (
      <div key={idx} className="border border-indigo-200 rounded-md p-4 bg-indigo-50">
        {/* Header */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center space-x-2">
            <span className="inline-flex px-2 py-0.5 rounded text-xs font-medium bg-indigo-100 text-indigo-800">
              telemetry
            </span>
            <span className="text-xs text-gray-600">{item.user_id || 'unknown'}</span>
            <span className="text-xs text-gray-400">•</span>
            <span className="text-xs text-gray-500">{formatTimestamp(item.ts)}</span>
          </div>
          <div className="flex items-center space-x-2">
            {hints.tone && (
              <span className="inline-flex px-2 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-700">
                {hints.tone}
              </span>
            )}
            {hints.creativity_bias !== undefined && (
              <span className="inline-flex px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-700">
                {Math.round(hints.creativity_bias * 100)}% creative
              </span>
            )}
          </div>
        </div>

        {/* Body - Outcome Summary */}
        <div className="space-y-2">
          <div className="grid grid-cols-3 gap-3 text-sm">
            <div className="bg-white rounded px-3 py-2 border border-gray-200">
              <div className="text-xs text-gray-500 uppercase tracking-wide">Length</div>
              <div className="text-base font-semibold text-gray-900">{outcome.length || 0}</div>
            </div>
            <div className="bg-white rounded px-3 py-2 border border-gray-200">
              <div className="text-xs text-gray-500 uppercase tracking-wide">Sentiment</div>
              <div className={`text-base font-semibold ${
                outcome.sentiment === 'positive' ? 'text-green-600' :
                outcome.sentiment === 'negative' ? 'text-red-600' :
                'text-gray-600'
              }`}>
                {outcome.sentiment || 'N/A'}
              </div>
            </div>
            <div className="bg-white rounded px-3 py-2 border border-gray-200">
              <div className="text-xs text-gray-500 uppercase tracking-wide">Tokens</div>
              <div className="text-base font-semibold text-gray-900">{outcome.tokens_used || 0}</div>
            </div>
          </div>
        </div>

        {/* Footer - View Raw */}
        <div className="mt-3 pt-3 border-t border-indigo-200">
          <button
            onClick={() => toggleExpanded(idx)}
            className="text-xs text-indigo-700 hover:text-indigo-900 font-medium"
          >
            {isExpanded ? '▼ Hide raw JSON' : '▶ View raw JSON'}
          </button>
          {isExpanded && (
            <div className="mt-2">
              <pre className="bg-white p-3 rounded text-xs overflow-x-auto border border-gray-200">
                {JSON.stringify(item, null, 2)}
              </pre>
            </div>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Coach Header */}
      <div className="pb-3 border-b border-gray-200">
        <h2 className="text-xl font-bold text-gray-900">{coachLabel}</h2>
        <p className="text-sm text-gray-500 mt-1">Accumulated learnings and session summaries</p>
      </div>

      {/* Filter Pills */}
      <div className="flex items-center space-x-2">
        <span className="text-sm font-medium text-gray-700">Filter:</span>
        {(['all', 'summary', 'metric', 'telemetry'] as FilterKind[]).map(kind => (
          <button
            key={kind}
            onClick={() => setFilterKind(kind)}
            className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
              filterKind === kind
                ? 'bg-indigo-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            {kind.charAt(0).toUpperCase() + kind.slice(1)}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <div className="text-gray-500">Loading insights...</div>
        </div>
      ) : insights && insights.total === 0 ? (
        <>
          {/* Empty State */}
          <div className="border-2 border-dashed border-gray-300 rounded-lg p-12 text-center">
            <div className="text-gray-400 text-5xl mb-4">💡</div>
            <h3 className="text-lg font-medium text-gray-900 mb-2">
              {filterKind === 'telemetry' ? 'No Telemetry Entries Yet' : 'No Insights Yet'}
            </h3>
            <p className="text-sm text-gray-600 max-w-md mx-auto mb-4">
              {filterKind === 'telemetry'
                ? 'Telemetry entries will appear here once users interact with this coach and generate responses with active feature states.'
                : 'This tab will accumulate role-specific learnings and summaries from coaching sessions. As users interact with this coach, insights will appear here automatically.'}
            </p>
            <button
              onClick={handleAppendTest}
              disabled={appending}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed text-sm font-medium"
            >
              {appending ? 'Appending...' : '+ Append Test Insight'}
            </button>
          </div>

          {/* Info Card */}
          <div className="bg-blue-50 border border-blue-200 rounded-md p-4">
            <div className="flex items-start space-x-2">
              <span className="text-blue-600 text-lg">ℹ️</span>
              <div className="flex-1">
                <div className="text-sm font-medium text-blue-900">What are Insights?</div>
                <div className="text-xs text-blue-700 mt-1 space-y-1">
                  <div>• <strong>Learnings:</strong> Patterns discovered during conversations</div>
                  <div>• <strong>Summaries:</strong> Key topics and outcomes from sessions</div>
                  <div>• <strong>Improvements:</strong> Suggestions for prompt refinement</div>
                  <div>• <strong>Usage Metrics:</strong> Delegation frequency, user satisfaction</div>
                </div>
              </div>
            </div>
          </div>
        </>
      ) : insights && insights.total > 0 ? (
        <>
          {/* Controls */}
          <div className="flex items-center justify-between">
            <div className="text-sm text-gray-600">
              Showing {insights.items.length} of {insights.total} insights
            </div>
            <button
              onClick={handleAppendTest}
              disabled={appending}
              className="px-3 py-1.5 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed text-sm font-medium"
            >
              {appending ? 'Appending...' : '+ Append Test'}
            </button>
          </div>

          {/* Insights List */}
          <div className="space-y-3">
            {insights.items.map((item, idx) => {
              // Use telemetry card for telemetry items
              if (item.kind === 'telemetry') {
                return renderTelemetryCard(item, idx)
              }

              // Default card for other items
              return (
                <div key={idx} className="border border-gray-200 rounded-md p-4 bg-white">
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center space-x-2">
                      <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${
                        item.kind === 'summary' ? 'bg-blue-100 text-blue-800' :
                        item.kind === 'metric' ? 'bg-green-100 text-green-800' :
                        'bg-gray-100 text-gray-800'
                      }`}>
                        {item.kind}
                      </span>
                      <span className="text-xs text-gray-500 font-mono">{item.prompt_hash}</span>
                    </div>
                    <span className="text-xs text-gray-500">{formatTimestamp(item.ts)}</span>
                  </div>
                  <div className="text-sm text-gray-700">
                    <pre className="bg-gray-50 p-2 rounded text-xs overflow-x-auto">
                      {JSON.stringify(item.data, null, 2)}
                    </pre>
                  </div>
                </div>
              )
            })}
          </div>
        </>
      ) : (
        <div className="text-center py-12 text-gray-500">No insights data available</div>
      )}

      {insights?.message && (
        <div className="text-sm text-gray-600 bg-gray-50 p-3 rounded border border-gray-200">{insights.message}</div>
      )}
    </div>
  )
}
