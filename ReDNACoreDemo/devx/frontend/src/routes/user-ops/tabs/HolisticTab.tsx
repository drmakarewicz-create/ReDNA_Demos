import { useEffect, useMemo, useState } from 'react'
import userOpsApi, { HolisticHistoryEntry, HolisticLatestResponse } from '@/lib/userOpsApi'
import type { HolisticResult } from '@/lib/holisticApi'

interface HolisticTabProps {
  userId: string
}

export default function HolisticTab({ userId }: HolisticTabProps) {
  const [latest, setLatest] = useState<HolisticResult | null>(null)
  const [history, setHistory] = useState<HolisticHistoryEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [reason, setReason] = useState('')

  const refresh = async () => {
    try {
      setLoading(true)
      setError(null)
      const payload: HolisticLatestResponse = await userOpsApi.getHolisticLatest(userId, 6)
      setLatest(payload.latest ?? null)
      setHistory(payload.history ?? [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load holistic overview.')
      setLatest(null)
      setHistory([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    refresh()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId])

  const handleRun = async () => {
    try {
      setRunning(true)
      setError(null)
      setMessage(null)
      await userOpsApi.runHolisticForUser(userId, reason)
      setMessage('Holistic review job queued. Results will appear once processing completes.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to queue holistic review job.')
    } finally {
      setRunning(false)
      await refresh()
    }
  }

  const domainSummary = useMemo(() => {
    if (!latest?.rr?.by_domain) return []
    return Object.entries(latest.rr.by_domain).map(([domain, value]) => ({
      domain,
      value: typeof value === 'number' ? value : Number(value),
    }))
  }, [latest])

  return (
    <div className="space-y-6">
      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}
      {message && (
        <div className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
          {message}
        </div>
      )}

      <section className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h3 className="text-sm font-semibold text-gray-900">Holistic Review</h3>
            <p className="mt-1 text-sm text-gray-600">
              Trigger a fresh holistic analysis for{' '}
              <span className="font-medium text-gray-900">{userId}</span>.
            </p>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <input
              type="text"
              value={reason}
              onChange={event => setReason(event.target.value)}
              placeholder="Optional reason"
              className="w-full min-w-[220px] rounded-md border border-gray-300 px-3 py-2 text-sm"
            />
            <button
              type="button"
              onClick={handleRun}
              disabled={running}
              className="inline-flex items-center justify-center rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60"
            >
              {running ? 'Queueing…' : 'Run Holistic Review'}
            </button>
            <button
              type="button"
              onClick={refresh}
              className="text-sm text-blue-600 hover:text-blue-800"
            >
              Refresh
            </button>
          </div>
        </div>
      </section>

      <section className="rounded-lg border border-gray-200 bg-white shadow-sm">
        <div className="border-b border-gray-200 px-4 py-3">
          <h3 className="text-sm font-semibold text-gray-900">Latest Summary</h3>
          <p className="mt-1 text-xs text-gray-500">
            Snapshot of the most recent holistic run. History and full JSON export are shown below.
          </p>
        </div>
        <div className="space-y-4 p-4">
          {loading ? (
            <div className="text-sm text-gray-500">Loading holistic results…</div>
          ) : latest ? (
            <>
              <div className="flex flex-col gap-4 md:flex-row">
                <div className="rounded-lg border border-gray-200 bg-blue-50 px-4 py-3 md:w-1/3">
                  <div className="text-xs uppercase tracking-wide text-blue-700">Generated</div>
                  <div className="mt-1 text-base font-semibold text-blue-900">
                    {formatTimestamp(latest.generated_at)}
                  </div>
                  {latest.notes && (
                    <div className="mt-2 text-xs text-blue-700/80">{latest.notes}</div>
                  )}
                </div>
                <div className="grid flex-1 grid-cols-3 gap-3">
                  <MetricCard label="Containers" value={latest.counts.containers} />
                  <MetricCard label="Evidence" value={latest.counts.evidence} />
                  <MetricCard label="Derived" value={latest.counts.derived} />
                </div>
              </div>
              <div className="grid gap-4 lg:grid-cols-2">
                <div className="rounded-lg border border-gray-200 bg-gray-50 px-4 py-3">
                  <div className="text-xs uppercase tracking-wide text-gray-500">Overall RR</div>
                  <div className="mt-1 text-2xl font-semibold text-gray-900">
                    {latest.rr?.overall_rr.toFixed(2)}
                  </div>
                </div>
                <div className="rounded-lg border border-gray-200 bg-gray-50 px-4 py-3">
                  <div className="text-xs uppercase tracking-wide text-gray-500">Lowest RR Paths</div>
                  <ul className="mt-2 space-y-1 text-sm text-gray-600">
                    {latest.top_low_rr_paths.length === 0 ? (
                      <li>No RR data available</li>
                    ) : (
                      latest.top_low_rr_paths.map(item => (
                        <li key={item.path} className="flex items-center justify-between gap-2">
                          <span className="truncate">{item.path}</span>
                          <span className="font-medium text-gray-900">
                            {item.rr.toFixed(2)}
                          </span>
                        </li>
                      ))
                    )}
                  </ul>
                </div>
              </div>
              {domainSummary.length > 0 && (
                <div className="rounded-lg border border-gray-200 bg-white px-4 py-3 shadow-sm">
                  <div className="text-xs uppercase tracking-wide text-gray-500">
                    Domain Snapshot
                  </div>
                  <div className="mt-2 grid gap-3 md:grid-cols-2 lg:grid-cols-3">
                    {domainSummary.map(entry => (
                      <div
                        key={entry.domain}
                        className="rounded-md border border-gray-100 bg-gray-50 px-3 py-2"
                      >
                        <div className="text-xs text-gray-500">{entry.domain}</div>
                        <div className="text-sm font-semibold text-gray-900">
                          {entry.value.toFixed(2)}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="rounded-md border border-dashed border-gray-300 bg-gray-50 px-4 py-3 text-sm text-gray-600">
              No holistic run has been recorded for this user yet.
            </div>
          )}
        </div>
      </section>

      <section className="rounded-lg border border-gray-200 bg-white shadow-sm">
        <div className="border-b border-gray-200 px-4 py-3">
          <h3 className="text-sm font-semibold text-gray-900">History</h3>
          <p className="mt-1 text-xs text-gray-500">
            Recent holistic snapshots (most recent first). Use the file path to inspect JSON on disk.
          </p>
        </div>
        <div className="divide-y divide-gray-200">
          {history.length === 0 ? (
            <div className="px-4 py-12 text-center text-sm text-gray-500">No history entries.</div>
          ) : (
            history.map(entry => (
              <div key={`${entry.path}-${entry.generated_at}`} className="px-4 py-3 text-sm">
                <div className="flex flex-col gap-1 md:flex-row md:items-center md:justify-between">
                  <div>
                    <div className="text-xs uppercase tracking-wide text-gray-500">
                      {formatTimestamp(entry.generated_at)}
                    </div>
                    {entry.path && (
                      <div className="text-xs text-blue-700">{entry.path}</div>
                    )}
                  </div>
                  {entry.size_bytes !== undefined && entry.size_bytes !== null && (
                    <div className="text-xs text-gray-500">
                      {formatBytes(entry.size_bytes)}
                    </div>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </section>
    </div>
  )
}

function MetricCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-gray-200 bg-gray-50 px-4 py-3">
      <div className="text-xs uppercase tracking-wide text-gray-500">{label}</div>
      <div className="mt-1 text-lg font-semibold text-gray-900">{value}</div>
    </div>
  )
}

function formatTimestamp(value?: string | null): string {
  if (!value) return '—'
  try {
    return new Date(value).toLocaleString()
  } catch {
    return value
  }
}

function formatBytes(bytes?: number | null): string {
  if (bytes === null || bytes === undefined) return '—'
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const index = Math.floor(Math.log(bytes) / Math.log(1024))
  const value = bytes / Math.pow(1024, index)
  return `${value.toFixed(1)} ${units[index]}`
}
