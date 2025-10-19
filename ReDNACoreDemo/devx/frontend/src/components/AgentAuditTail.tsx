import { useCallback, useEffect, useState } from 'react'

interface AuditEntry {
  audit_id?: string
  event: string
  timestamp: string
  user_id: string
  agent_id?: string
  old_level?: number
  new_level?: number
  by?: string
  job_id?: string
  kind?: string
  source?: string
  reason?: string
  changes?: Record<string, any>
}

interface AgentAuditTailProps {
  userId: string
  limit?: number
  refreshKey?: number
}

function formatTimestamp(iso: string): string {
  const date = new Date(iso)
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function formatEventLabel(event: string): string {
  const labels: Record<string, string> = {
    agent_configured: 'Config Change',
    agent_run: 'Agent Run',
    job_enqueued: 'Job Enqueued',
    job_completed: 'Job Done',
    job_failed: 'Job Failed',
    capability_issued: 'Token Issued',
    capability_revoked: 'Token Revoked',
  }
  return labels[event] || event
}

function eventColor(event: string): string {
  const colors: Record<string, string> = {
    agent_configured: 'text-blue-700 bg-blue-50',
    agent_run: 'text-gray-700 bg-gray-100',
    job_enqueued: 'text-indigo-700 bg-indigo-50',
    job_completed: 'text-green-700 bg-green-50',
    job_failed: 'text-red-700 bg-red-50',
    capability_issued: 'text-purple-700 bg-purple-50',
    capability_revoked: 'text-orange-700 bg-orange-50',
  }
  return colors[event] || 'text-gray-700 bg-gray-100'
}

export default function AgentAuditTail({ userId, limit = 20, refreshKey = 0 }: AgentAuditTailProps) {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [entries, setEntries] = useState<AuditEntry[]>([])

  const loadAudit = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const url = `/devx/api/agents/${encodeURIComponent(userId)}/audit?limit=${limit}`
      const response = await fetch(url)
      if (!response.ok) {
        throw new Error(`Failed to load audit: ${response.statusText}`)
      }
      const data = await response.json()
      setEntries(data.audit || [])
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load audit log.'
      setError(message)
    } finally {
      setLoading(false)
    }
  }, [userId, limit])

  useEffect(() => {
    loadAudit()
  }, [loadAudit, refreshKey])

  if (loading) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-6 text-center text-sm text-gray-500">
        Loading audit log…
      </div>
    )
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
        {error}
      </div>
    )
  }

  if (entries.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-gray-300 bg-white p-6 text-center text-sm text-gray-500">
        No audit entries yet. Agent activity will appear here once the agent is active.
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {entries.map((entry, idx) => (
        <div
          key={entry.audit_id || `${entry.event}-${entry.timestamp}-${idx}`}
          className="flex items-start gap-3 rounded-md border border-gray-200 bg-white px-4 py-3 text-sm hover:bg-gray-50"
        >
          <div className="flex-shrink-0">
            <span className={`inline-flex rounded-full px-2 py-1 text-xs font-medium ${eventColor(entry.event)}`}>
              {formatEventLabel(entry.event)}
            </span>
          </div>
          <div className="flex-1 space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-xs text-gray-500">{formatTimestamp(entry.timestamp)}</span>
              {entry.audit_id && (
                <span className="text-xs font-mono text-gray-400" title={entry.audit_id}>
                  {entry.audit_id.slice(0, 8)}
                </span>
              )}
            </div>
            {entry.event === 'agent_configured' && (
              <div className="text-sm text-gray-700">
                Level {entry.old_level ?? '?'} → {entry.new_level ?? '?'}
                {entry.by && <span className="text-gray-500"> by {entry.by}</span>}
              </div>
            )}
            {(entry.event === 'job_enqueued' || entry.event === 'job_completed' || entry.event === 'job_failed') && (
              <div className="text-sm text-gray-700">
                <span className="font-medium">{entry.kind || 'job'}</span>
                {entry.source && <span className="text-gray-500"> from {entry.source}</span>}
                {entry.reason && <span className="text-xs text-gray-400"> ({entry.reason})</span>}
              </div>
            )}
            {entry.event === 'agent_run' && (
              <div className="text-sm text-gray-700">
                Agent run completed
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
