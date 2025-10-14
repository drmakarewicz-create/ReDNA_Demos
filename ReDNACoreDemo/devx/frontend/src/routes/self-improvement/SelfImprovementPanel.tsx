import { useState, useEffect } from 'react'
import { learningApi, Report, Suggestion, HistoryEntry, Stats, coerceConfidenceBand } from '../../lib/learningApi'
import ChorusPreviewButton from '../../components/ChorusPreviewButton'

type TabView = 'suggestions' | 'history'
type ConfidenceFilter = 'all' | 'auto' | 'review'
type SortBy = 'confidence' | 'recent' | 'impact'

interface ToastMessage {
  type: 'success' | 'warning' | 'error'
  message: string
}

export default function SelfImprovementPanel() {
  const [activeTab, setActiveTab] = useState<TabView>('suggestions')
  const [selectedCoachId, setSelectedCoachId] = useState<string | null>(null)
  const [report, setReport] = useState<Report | null>(null)
  const [stats, setStats] = useState<Stats | null>(null)
  const [suggestions, setSuggestions] = useState<Suggestion[]>([])
  const [history, setHistory] = useState<HistoryEntry[]>([])
  const [loading, setLoading] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [toast, setToast] = useState<ToastMessage | null>(null)

  // Filters
  const [confidenceFilter, setConfidenceFilter] = useState<ConfidenceFilter>('all')
  const [sortBy, setSortBy] = useState<SortBy>('confidence')

  useEffect(() => {
    loadInitialData()
  }, [])

  useEffect(() => {
    if (selectedCoachId) {
      loadSuggestions()
      loadHistory()
    }
  }, [selectedCoachId])

  const loadInitialData = async () => {
    setLoading(true)
    try {
      const [reportData, statsData] = await Promise.all([
        learningApi.getReport().catch(() => null),
        learningApi.getStats().catch(() => null)
      ])
      setReport(reportData)
      setStats(statsData)

      // Auto-select first coach if available
      if (reportData && Object.keys(reportData.coaches).length > 0) {
        setSelectedCoachId(Object.keys(reportData.coaches)[0])
      }
    } catch (error) {
      showToast('error', 'Failed to load initial data')
    } finally {
      setLoading(false)
    }
  }

  const loadSuggestions = async () => {
    if (!selectedCoachId) return
    try {
      const data = await learningApi.getSuggestions(selectedCoachId)
      setSuggestions(data)
    } catch (error) {
      showToast('error', 'Failed to load suggestions')
    }
  }

  const loadHistory = async () => {
    if (!selectedCoachId) return
    try {
      const data = await learningApi.getHistory({ coach_id: selectedCoachId, limit: 50 })
      setHistory(data)
    } catch (error) {
      console.error('Failed to load history:', error)
    }
  }

  const handleRunAnalysis = async () => {
    setAnalyzing(true)
    try {
      const newReport = await learningApi.runAnalysis()
      setReport(newReport)
      showToast('success', 'Analysis complete')

      // Refresh stats and suggestions
      const newStats = await learningApi.getStats()
      setStats(newStats)
      if (selectedCoachId) {
        await loadSuggestions()
      }
    } catch (error) {
      showToast('error', 'Analysis failed')
    } finally {
      setAnalyzing(false)
    }
  }

  const handleApplySuggestion = async (suggestion: Suggestion, action: 'approve' | 'reject', reason?: string) => {
    try {
      const result = await learningApi.applySuggestion({
        coach_id: suggestion.coach_id,
        suggestion_id: suggestion.suggestion_id,
        action,
        user: 'devx-operator',
        reason
      })

      if (result.ok) {
        const backupMsg = result.backup_path ? ` Backed up to ${result.backup_path}` : ''
        showToast('success', `${action === 'approve' ? 'Approved' : 'Rejected'} suggestion.${backupMsg}`)

        // Optimistic update
        setSuggestions(prev => prev.filter(s => s.suggestion_id !== suggestion.suggestion_id))

        // Refresh history
        await loadHistory()
      }
    } catch (error) {
      showToast('error', `Failed to ${action} suggestion`)
    }
  }

  const showToast = (type: ToastMessage['type'], message: string) => {
    setToast({ type, message })
    setTimeout(() => setToast(null), 4000)
  }

  const filteredSuggestions = suggestions
    .filter(s => {
      if (confidenceFilter === 'all') return true
      const band = coerceConfidenceBand(s.confidence)
      if (confidenceFilter === 'auto') return band === 'auto'
      if (confidenceFilter === 'review') return band === 'review'
      return false
    })
    .sort((a, b) => {
      if (sortBy === 'confidence') return b.confidence - a.confidence
      if (sortBy === 'impact') return (b.estimated_improvement || 0) - (a.estimated_improvement || 0)
      return 0 // 'recent' would need timestamp
    })

  const coachList = report ? Object.keys(report.coaches) : []

  return (
    <div className="h-screen flex flex-col bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Self-Improvement</h1>
            <p className="text-sm text-gray-500 mt-1">Telemetry analysis and prompt tuning suggestions</p>
          </div>
          <div className="flex items-center gap-4">
            <ChorusPreviewButton userId="TEST" />
            {/* Telemetry Health Widget */}
            {report && (
              <div className="flex items-center gap-2 px-4 py-2 bg-gray-50 rounded-md border border-gray-200">
                <span className="text-xs font-medium text-gray-600">Telemetry:</span>
                {report.files_cleaned > 0 && (
                  <span className="text-xs text-green-600">✓ Clean</span>
                )}
                {report.defaults_injected > 0 && (
                  <span className="text-xs text-amber-600">Defaults: {report.defaults_injected}</span>
                )}
                {report.malformed_lines_skipped > 0 && (
                  <span className="text-xs text-red-600">Malformed: {report.malformed_lines_skipped}</span>
                )}
              </div>
            )}
            <button
              onClick={handleRunAnalysis}
              disabled={analyzing}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium"
            >
              {analyzing ? 'Analyzing...' : '▶️ Run Analysis'}
            </button>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Coach List Sidebar */}
        <div className="w-64 bg-white border-r border-gray-200 overflow-y-auto">
          <div className="p-4">
            <h2 className="text-sm font-semibold text-gray-700 mb-3">Coaches</h2>
            {loading ? (
              <div className="text-sm text-gray-500">Loading...</div>
            ) : coachList.length === 0 ? (
              <div className="text-sm text-gray-500">No coaches analyzed</div>
            ) : (
              <div className="space-y-1">
                {coachList.map(coachId => {
                  const coachStats = stats?.coaches[coachId]
                  return (
                    <button
                      key={coachId}
                      onClick={() => setSelectedCoachId(coachId)}
                      className={`w-full text-left px-3 py-2 rounded-md text-sm transition-colors ${
                        selectedCoachId === coachId
                          ? 'bg-blue-50 text-blue-700 font-medium'
                          : 'text-gray-700 hover:bg-gray-50'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="truncate">{coachId.replace('_', ' ')}</span>
                        {coachStats && (
                          <span className="ml-2 text-xs font-medium text-gray-500">
                            {coachStats.suggestions}
                          </span>
                        )}
                      </div>
                      {coachStats && coachStats.avg_confidence && (
                        <div className="mt-1 flex gap-1">
                          <span className={`inline-block px-2 py-0.5 rounded text-xs ${
                            coachStats.avg_confidence >= 0.85
                              ? 'bg-green-100 text-green-700'
                              : coachStats.avg_confidence >= 0.70
                              ? 'bg-amber-100 text-amber-700'
                              : 'bg-gray-100 text-gray-700'
                          }`}>
                            {(coachStats.avg_confidence * 100).toFixed(0)}%
                          </span>
                        </div>
                      )}
                    </button>
                  )
                })}
              </div>
            )}
          </div>
        </div>

        {/* Main Panel */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {!selectedCoachId ? (
            <div className="flex-1 flex items-center justify-center text-gray-500">
              Select a coach to view suggestions
            </div>
          ) : (
            <>
              {/* Tabs */}
              <div className="bg-white border-b border-gray-200 px-6">
                <div className="flex gap-6">
                  <button
                    onClick={() => setActiveTab('suggestions')}
                    className={`py-3 px-1 border-b-2 text-sm font-medium transition-colors ${
                      activeTab === 'suggestions'
                        ? 'border-blue-600 text-blue-600'
                        : 'border-transparent text-gray-600 hover:text-gray-900'
                    }`}
                  >
                    💡 Suggestions
                  </button>
                  <button
                    onClick={() => setActiveTab('history')}
                    className={`py-3 px-1 border-b-2 text-sm font-medium transition-colors ${
                      activeTab === 'history'
                        ? 'border-blue-600 text-blue-600'
                        : 'border-transparent text-gray-600 hover:text-gray-900'
                    }`}
                  >
                    📜 History
                  </button>
                </div>
              </div>

              {/* Tab Content */}
              <div className="flex-1 overflow-y-auto p-6">
                {activeTab === 'suggestions' ? (
                  <SuggestionsView
                    suggestions={filteredSuggestions}
                    confidenceFilter={confidenceFilter}
                    setConfidenceFilter={setConfidenceFilter}
                    sortBy={sortBy}
                    setSortBy={setSortBy}
                    onApprove={(s, reason) => handleApplySuggestion(s, 'approve', reason)}
                    onReject={(s, reason) => handleApplySuggestion(s, 'reject', reason)}
                  />
                ) : (
                  <HistoryView history={history} />
                )}
              </div>
            </>
          )}
        </div>
      </div>

      {/* Toast Notification */}
      {toast && (
        <div className={`fixed bottom-6 right-6 px-4 py-3 rounded-md shadow-lg ${
          toast.type === 'success' ? 'bg-green-600 text-white' :
          toast.type === 'warning' ? 'bg-amber-600 text-white' :
          'bg-red-600 text-white'
        }`}>
          {toast.message}
        </div>
      )}
    </div>
  )
}

// Suggestions View Component
function SuggestionsView({
  suggestions,
  confidenceFilter,
  setConfidenceFilter,
  sortBy,
  setSortBy,
  onApprove,
  onReject
}: {
  suggestions: Suggestion[]
  confidenceFilter: ConfidenceFilter
  setConfidenceFilter: (f: ConfidenceFilter) => void
  sortBy: SortBy
  setSortBy: (s: SortBy) => void
  onApprove: (s: Suggestion, reason?: string) => void
  onReject: (s: Suggestion, reason?: string) => void
}) {
  const [expandedDiffs, setExpandedDiffs] = useState<Set<string>>(new Set())

  const toggleDiff = (id: string) => {
    const newSet = new Set(expandedDiffs)
    if (newSet.has(id)) {
      newSet.delete(id)
    } else {
      newSet.add(id)
    }
    setExpandedDiffs(newSet)
  }

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex items-center justify-between">
        <div className="flex gap-2">
          <button
            onClick={() => setConfidenceFilter('all')}
            className={`px-3 py-1 rounded-md text-sm ${
              confidenceFilter === 'all'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            All
          </button>
          <button
            onClick={() => setConfidenceFilter('auto')}
            className={`px-3 py-1 rounded-md text-sm ${
              confidenceFilter === 'auto'
                ? 'bg-green-600 text-white'
                : 'bg-green-100 text-green-700 hover:bg-green-200'
            }`}
          >
            Auto-Eligible ≥85%
          </button>
          <button
            onClick={() => setConfidenceFilter('review')}
            className={`px-3 py-1 rounded-md text-sm ${
              confidenceFilter === 'review'
                ? 'bg-amber-600 text-white'
                : 'bg-amber-100 text-amber-700 hover:bg-amber-200'
            }`}
          >
            Needs Review 70-84%
          </button>
        </div>
        <select
          value={sortBy}
          onChange={e => setSortBy(e.target.value as SortBy)}
          className="px-3 py-1 border border-gray-300 rounded-md text-sm"
        >
          <option value="confidence">Sort by: Confidence</option>
          <option value="recent">Sort by: Recent</option>
          <option value="impact">Sort by: Impact</option>
        </select>
      </div>

      {/* Suggestions List */}
      {suggestions.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          No suggestions match the current filter
        </div>
      ) : (
        <div className="space-y-4">
          {suggestions.map(suggestion => {
            const band = coerceConfidenceBand(suggestion.confidence)
            const isExpanded = expandedDiffs.has(suggestion.suggestion_id)

            return (
              <div key={suggestion.suggestion_id} className="bg-white border border-gray-200 rounded-md p-4">
                {/* Header */}
                <div className="flex items-start justify-between mb-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <h3 className="font-medium text-gray-900">Prompt Improvement</h3>
                      <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
                        band === 'auto' ? 'bg-green-100 text-green-700' :
                        band === 'review' ? 'bg-amber-100 text-amber-700' :
                        'bg-gray-100 text-gray-700'
                      }`}>
                        {(suggestion.confidence * 100).toFixed(0)}% confidence
                      </span>
                      <span className="text-xs text-gray-500">
                        {suggestion.evidence_count} evidence
                      </span>
                    </div>
                    <p className="text-sm text-gray-600 mt-1">{suggestion.rationale}</p>
                  </div>
                </div>

                {/* Diff Preview Toggle */}
                <button
                  onClick={() => toggleDiff(suggestion.suggestion_id)}
                  className="text-sm text-blue-600 hover:text-blue-700 mb-2"
                >
                  {isExpanded ? '▼ Hide diff' : '▶ View diff'}
                </button>

                {/* Diff View */}
                {isExpanded && (
                  <div className="mb-3 bg-gray-50 rounded-md p-3 border border-gray-200">
                    <pre className="text-xs font-mono whitespace-pre-wrap text-gray-800">
                      {suggestion.suggested_change}
                    </pre>
                  </div>
                )}

                {/* Actions */}
                <div className="flex gap-2">
                  <button
                    onClick={() => onApprove(suggestion)}
                    className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 text-sm font-medium"
                  >
                    ✓ Approve
                  </button>
                  <button
                    onClick={() => onReject(suggestion)}
                    className="px-4 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 text-sm font-medium"
                  >
                    ✗ Reject
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

// History View Component
function HistoryView({ history }: { history: HistoryEntry[] }) {
  const [copiedHash, setCopiedHash] = useState<string | null>(null)

  const copyHash = (hash: string) => {
    navigator.clipboard.writeText(hash)
    setCopiedHash(hash)
    setTimeout(() => setCopiedHash(null), 2000)
  }

  return (
    <div className="space-y-3">
      {history.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          No history available
        </div>
      ) : (
        history.map((entry, idx) => (
          <div key={idx} className="bg-white border border-gray-200 rounded-md p-4">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-2">
                  <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
                    entry.action === 'approve'
                      ? 'bg-green-100 text-green-700'
                      : 'bg-gray-100 text-gray-700'
                  }`}>
                    {entry.action}
                  </span>
                  <span className="text-xs text-gray-500">
                    {(entry.confidence * 100).toFixed(0)}% confidence
                  </span>
                  <span className="text-xs text-gray-500">by {entry.user}</span>
                </div>
                <div className="text-xs text-gray-600">
                  {new Date(entry.timestamp).toLocaleString()}
                </div>
                {entry.reason && (
                  <p className="text-sm text-gray-700 mt-2">{entry.reason}</p>
                )}
              </div>
              <div className="text-right text-xs">
                {entry.old_hash && (
                  <div className="mb-1">
                    <button
                      onClick={() => copyHash(entry.old_hash!)}
                      className="text-gray-500 hover:text-gray-700 font-mono"
                    >
                      {entry.old_hash.slice(0, 8)}
                      {copiedHash === entry.old_hash ? ' ✓' : ' 📋'}
                    </button>
                  </div>
                )}
                {entry.new_hash && (
                  <div>
                    <button
                      onClick={() => copyHash(entry.new_hash!)}
                      className="text-gray-500 hover:text-gray-700 font-mono"
                    >
                      {entry.new_hash.slice(0, 8)}
                      {copiedHash === entry.new_hash ? ' ✓' : ' 📋'}
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        ))
      )}
    </div>
  )
}
