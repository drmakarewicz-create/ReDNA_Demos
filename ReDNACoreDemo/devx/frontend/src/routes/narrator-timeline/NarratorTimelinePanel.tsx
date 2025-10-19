import { useEffect, useState } from 'react';
import {
  fetchNarratorTraces,
  exportNarrative,
  NarratorResponse,
} from '../../lib/narratorApi';
import ChorusPreviewButton from '../../components/ChorusPreviewButton';
import { userOpsHC } from '../../lib/routes';
import { Link } from 'react-router-dom';

interface FilterState {
  decisionType: string;
  sessionId: string;
  minConfidence: number | undefined;
}

const DECISION_TYPE_LABELS: Record<string, string> = {
  all: 'All',
  coach_switch: 'Coach Switches',
  tone_shift: 'Tone Shifts',
  curiosity_trigger: 'Curiosity',
  codex_action: 'Codex Actions',
  delegation: 'Delegations',
};

function NarratorTimelinePanel() {
  const [userId, setUserId] = useState<string>('TEST');
  const [data, setData] = useState<NarratorResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<FilterState>({
    decisionType: 'all',
    sessionId: '',
    minConfidence: undefined,
  });
  const [limit, setLimit] = useState<number>(20);

  const loadTraces = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetchNarratorTraces(userId, {
        limit,
        decisionType: filters.decisionType === 'all' ? undefined : filters.decisionType,
        sessionId: filters.sessionId || undefined,
        minConfidence: filters.minConfidence,
      });
      setData(response);
    } catch (err) {
      // Only show error for real failures, not 404/empty
      setError(err instanceof Error ? err.message : 'Failed to load traces');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTraces();
  }, [userId, filters, limit]);

  const handleExport = async (format: 'json' | 'markdown') => {
    try {
      const content = await exportNarrative(userId, format, {
        limit: 100,
        sessionId: filters.sessionId || undefined,
      });

      // Download file
      const blob = new Blob(
        [typeof content === 'string' ? content : JSON.stringify(content, null, 2)],
        { type: format === 'markdown' ? 'text/markdown' : 'application/json' }
      );
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `narrator_${userId}.${format === 'markdown' ? 'md' : 'json'}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export failed');
    }
  };

  const getConfidenceBadgeClass = (confidence: number): string => {
    if (confidence >= 0.8) return 'bg-green-100 text-green-800 border-green-300';
    if (confidence >= 0.6) return 'bg-amber-100 text-amber-800 border-amber-300';
    return 'bg-red-100 text-red-800 border-red-300';
  };

  const getImpactBadgeClass = (impact: string): string => {
    if (impact === 'high') return 'bg-purple-100 text-purple-800 border-purple-300';
    if (impact === 'medium') return 'bg-blue-100 text-blue-800 border-blue-300';
    return 'bg-gray-100 text-gray-800 border-gray-300';
  };

  const formatTimestamp = (ts: string): string => {
    try {
      const date = new Date(ts);
      return date.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      });
    } catch {
      return ts;
    }
  };

  const groupedTraces = data?.narrative?.sessions || {};
  const sessions = Object.keys(groupedTraces);
  const hasData = data !== null

  return (
    <div className="p-6 bg-white min-h-screen">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900 mb-2 flex items-center gap-2">
          🗣 Narrator Timeline
        </h1>
        <p className="text-gray-600">
          Transparent reasoning traces for Head Coach decisions
        </p>
      </div>

      {/* Controls */}
      <div className="mb-6 p-4 bg-gray-50 rounded-lg border border-gray-200">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
          {/* User ID */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              User ID
            </label>
            <input
              type="text"
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>

          {/* Limit */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Limit
            </label>
            <input
              type="number"
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value))}
              min={1}
              max={100}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>

          {/* Session ID */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Session ID (optional)
            </label>
            <input
              type="text"
              value={filters.sessionId}
              onChange={(e) => setFilters({ ...filters, sessionId: e.target.value })}
              placeholder="Filter by session"
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>

          {/* Min Confidence */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Min Confidence
            </label>
            <input
              type="number"
              value={filters.minConfidence ?? ''}
              onChange={(e) =>
                setFilters({
                  ...filters,
                  minConfidence: e.target.value ? Number(e.target.value) : undefined,
                })
              }
              min={0}
              max={1}
              step={0.1}
              placeholder="0.0 - 1.0"
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
        </div>

        {/* Filter Chips */}
        <div className="flex flex-wrap gap-2 mb-4">
          {Object.entries(DECISION_TYPE_LABELS).map(([type, label]) => (
            <button
              key={type}
              onClick={() => setFilters({ ...filters, decisionType: type })}
              className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${
                filters.decisionType === type
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Action Buttons */}
        <div className="flex flex-wrap gap-2">
          <button
            onClick={loadTraces}
            disabled={loading}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed font-medium"
          >
            {loading ? 'Loading...' : 'Refresh'}
          </button>
          <button
            onClick={() => handleExport('json')}
            disabled={!data}
            className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed font-medium"
          >
            Export JSON
          </button>
          <button
            onClick={() => handleExport('markdown')}
            disabled={!data}
            className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed font-medium"
          >
            Export Markdown
          </button>
        </div>
      </div>

      {/* Stats Summary */}
      {data?.narrative && (
        <div className="mb-6 grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
            <div className="text-2xl font-bold text-blue-900">
              {data.narrative.total_traces}
            </div>
            <div className="text-sm text-blue-700">Total Traces</div>
          </div>
          <div className="p-4 bg-purple-50 rounded-lg border border-purple-200">
            <div className="text-2xl font-bold text-purple-900">
              {data.narrative.session_count}
            </div>
            <div className="text-sm text-purple-700">Sessions</div>
          </div>
          <div className="p-4 bg-green-50 rounded-lg border border-green-200">
            <div className="text-2xl font-bold text-green-900">
              {(data.narrative.avg_confidence * 100).toFixed(0)}%
            </div>
            <div className="text-sm text-green-700">Avg Confidence</div>
          </div>
          <div className="p-4 bg-amber-50 rounded-lg border border-amber-200">
            <div className="text-2xl font-bold text-amber-900">{data.duration_ms}ms</div>
            <div className="text-sm text-amber-700">Query Time</div>
          </div>
        </div>
      )}

      {/* Error Display */}
      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-red-800 font-medium">Error: {error}</p>
        </div>
      )}

      {/* Empty State */}
      {!hasData && !loading && !error && (
        <div className="flex items-center justify-center py-20 bg-gradient-to-br from-purple-50 to-indigo-50 border border-purple-200 rounded-lg shadow-sm">
          <div className="text-center max-w-md px-6">
            <div className="text-6xl mb-4">🗣️</div>
            <p className="text-lg font-semibold text-gray-900 mb-2">No narrator traces yet</p>
            <p className="text-sm text-gray-600 mb-4">
              After a Head Coach decision (coach switch, tone shift, curiosity, or Codex action), traces will appear here.
            </p>
            <p className="text-xs text-gray-500 mb-6 italic">
              💡 Tip: Run the HC daemon once to generate a trace
            </p>
            <Link
              to={userOpsHC(userId)}
              className="inline-block px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm font-medium transition-colors"
            >
              Open Head Coach settings
            </Link>
          </div>
        </div>
      )}

      {/* Timeline */}
      {hasData && (
        <div className="space-y-6">
          {sessions.length === 0 && (
            <div className="p-8 text-center bg-gray-50 rounded-lg border border-gray-200">
              <p className="text-gray-600">No traces found for the selected filters.</p>
            </div>
          )}

          {sessions.map((sessionId) => {
            const traces = groupedTraces[sessionId];
            return (
              <div key={sessionId} className="bg-white rounded-lg border border-gray-200 p-4">
                <h3 className="text-lg font-bold text-gray-900 mb-4">
                  Session: {sessionId || 'Unknown'}
                </h3>

                <div className="space-y-4">
                  {traces.map((trace, idx) => (
                    <div
                      key={`${trace.ts}-${idx}`}
                      className="p-4 bg-gray-50 rounded-lg border border-gray-200 hover:shadow-md transition-shadow"
                    >
                      {/* Trace Header */}
                      <div className="flex items-start justify-between mb-3">
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="text-xs font-mono text-gray-500">
                              {formatTimestamp(trace.ts)}
                            </span>
                            <span className="px-2 py-0.5 bg-indigo-100 text-indigo-800 text-xs font-medium rounded border border-indigo-300">
                              v{trace.context_version}
                            </span>
                            <span
                              className={`px-2 py-0.5 text-xs font-medium rounded border ${getImpactBadgeClass(
                                trace.impact
                              )}`}
                            >
                              {trace.impact}
                            </span>
                          </div>
                          <h4 className="text-base font-bold text-gray-900">
                            {trace.decision}
                          </h4>
                        </div>
                        <span
                          className={`px-3 py-1 text-sm font-bold rounded-full border ${getConfidenceBadgeClass(
                            trace.confidence
                          )}`}
                        >
                          {(trace.confidence * 100).toFixed(0)}%
                        </span>
                      </div>

                      {/* Reasoning */}
                      <div className="mb-3">
                        <p className="text-xs font-semibold text-gray-700 uppercase mb-1">
                          Reasoning:
                        </p>
                        <ul className="list-disc list-inside space-y-1">
                          {trace.reasoning.map((reason, ridx) => (
                            <li key={ridx} className="text-sm text-gray-700">
                              {reason}
                            </li>
                          ))}
                        </ul>
                      </div>

                      {/* Metadata */}
                      {trace.metadata && Object.keys(trace.metadata).length > 0 && (
                        <div className="mb-3">
                          <p className="text-xs font-semibold text-gray-700 uppercase mb-1">
                            Metadata:
                          </p>
                          <div className="flex flex-wrap gap-2">
                            {Object.entries(trace.metadata).map(([key, value]) => (
                              <span
                                key={key}
                                className="px-2 py-1 bg-gray-200 text-gray-800 text-xs rounded"
                              >
                                <span className="font-semibold">{key}:</span>{' '}
                                {typeof value === 'number'
                                  ? value.toFixed(2)
                                  : String(value)}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Actions */}
                      <div className="flex items-center gap-2 pt-2 border-t border-gray-300">
                        <ChorusPreviewButton
                          userId={trace.user_id}
                          contextVersion={trace.context_version}
                        />
                        <span className="text-xs text-gray-500">
                          {trace.duration_ms}ms
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default NarratorTimelinePanel;
