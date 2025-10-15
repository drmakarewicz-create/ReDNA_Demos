import { useEffect, useState } from 'react'
import holisticApi, { HolisticHistoryEntry, HolisticResult } from '@/lib/holisticApi'

function getCountSafe(
  counts: Map<string, number> | Record<string, number> | undefined,
  key: string
): number | undefined {
  if (!counts) return undefined
  const possibleMap = counts as any
  if (typeof possibleMap?.get === 'function') {
    return (counts as Map<string, number>).get(key)
  }
  return (counts as Record<string, number>)[key]
}

function formatNumber(value: number | null | undefined, fallback = '—'): string {
  if (value === null || value === undefined || Number.isNaN(value)) return fallback
  return value.toFixed(2)
}

export default function HolisticSummary() {
  const [queryUserId, setQueryUserId] = useState('TEST')
  const [activeUserId, setActiveUserId] = useState<string | null>(null)
  const [result, setResult] = useState<HolisticResult | null>(null)
  const [history, setHistory] = useState<HolisticHistoryEntry[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [info, setInfo] = useState<string | null>(null)
  const [jobId, setJobId] = useState('')
  const [processing, setProcessing] = useState(false)

  const loadUser = async (userId: string) => {
    try {
      setLoading(true)
      setError(null)
      const [latest, historyPayload] = await Promise.all([
        holisticApi.getResult(userId).catch(() => null),
        holisticApi.getHistory(userId, 10),
      ])
      setResult(latest)
      setHistory(historyPayload.entries)
      setActiveUserId(userId)
      if (!latest) {
        setInfo('No holistic results found for this user. Queue a job in User Ops, then process it here.')
      } else {
        setInfo(null)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load holistic results.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadUser(queryUserId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleProcessJob = async () => {
    if (!jobId.trim()) return
    try {
      setProcessing(true)
      setError(null)
      const response = await holisticApi.processJob(jobId.trim())
      const okCount = response.results.filter((item) => item.status === 'ok').length
      setInfo(`Processed job ${response.job_id}: ${okCount} successful, ${response.results.length - okCount} errors.`)
      if (activeUserId) {
        await loadUser(activeUserId)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to process holistic job.')
    } finally {
      setProcessing(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold text-slate-900">Holistic Summary</h2>
        <p className="mt-2 text-sm text-slate-600">
          Compute and inspect holistic metrics derived from the user vault. Queue jobs via User Ops, then process and
          review them here.
        </p>
      </div>

      <div className="flex flex-col gap-4 sm:flex-row sm:items-end">
        <div className="flex-1">
          <label className="block text-sm font-medium text-slate-700">User ID</label>
          <input
            value={queryUserId}
            onChange={(event) => setQueryUserId(event.target.value)}
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            placeholder="Enter user id"
          />
        </div>
        <button
          type="button"
          onClick={() => loadUser(queryUserId)}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          {loading ? 'Loading…' : 'Load summary'}
        </button>
      </div>

      <div className="rounded-md border border-slate-200 bg-white p-4 text-sm text-slate-600">
        <h3 className="text-base font-semibold text-slate-800">Process queued holistic job</h3>
        <p className="mt-1 text-xs text-slate-500">
          After queueing a holistic batch via User Ops, paste the job ID here to run the processor immediately.
        </p>
        <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-center">
          <input
            value={jobId}
            onChange={(event) => setJobId(event.target.value)}
            className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm"
            placeholder="holistic_20251009_000101"
          />
          <button
            type="button"
            onClick={handleProcessJob}
            disabled={processing || !jobId.trim()}
            className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:bg-emerald-300"
          >
            {processing ? 'Processing…' : 'Process Job'}
          </button>
        </div>
      </div>

      {error && <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
      {info && !error && (
        <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">{info}</div>
      )}

      {result ? (
        <div className="space-y-6">
          <section className="grid gap-4 md:grid-cols-3">
            <div className="rounded-md border border-slate-200 bg-white p-4">
              <p className="text-xs uppercase text-slate-500">Overall RR</p>
              <p className="mt-2 text-3xl font-semibold text-slate-900">{formatNumber(result.rr.overall_rr)}</p>
              <p className="mt-1 text-xs text-slate-500">Generated {new Date(result.generated_at).toLocaleString()}</p>
            </div>
            <div className="rounded-md border border-slate-200 bg-white p-4">
              <p className="text-xs uppercase text-slate-500">Containers</p>
              <p className="mt-2 text-3xl font-semibold text-slate-900">{result.counts.containers}</p>
              <p className="mt-1 text-xs text-slate-500">Evidence {result.counts.evidence} • Derived {result.counts.derived}</p>
            </div>
            <div className="rounded-md border border-slate-200 bg-white p-4">
              <p className="text-xs uppercase text-slate-500">Notes</p>
              <p className="mt-2 text-sm text-slate-700">{result.notes || '—'}</p>
            </div>
          </section>

          <section className="grid gap-6 md:grid-cols-2">
            <div className="rounded-md border border-slate-200 bg-white p-4">
              <h4 className="text-sm font-semibold text-slate-800">RR by domain</h4>
              <ul className="mt-3 space-y-2 text-sm">
                {Object.entries(result.rr.by_domain).map(([domain, value]) => (
                  <li key={domain} className="flex items-center justify-between">
                    <span className="text-slate-600">{domain}</span>
                    <span className="text-slate-900 font-medium">{formatNumber(value)}</span>
                  </li>
                )) || <li className="text-xs text-slate-500">No domain metrics</li>}
              </ul>
            </div>
            <div className="rounded-md border border-slate-200 bg-white p-4">
              <h4 className="text-sm font-semibold text-slate-800">Lowest RR paths</h4>
              <table className="mt-3 w-full text-left text-sm">
                <thead className="text-xs uppercase text-slate-500">
                  <tr>
                    <th className="pb-1">Path</th>
                    <th className="pb-1 text-right">RR</th>
                  </tr>
                </thead>
                <tbody>
                  {result.top_low_rr_paths.length > 0 ? (
                    result.top_low_rr_paths.map((item) => (
                      <tr key={item.path} className="border-t border-slate-100">
                        <td className="py-1 text-slate-700">{item.path}</td>
                        <td className="py-1 text-right text-slate-900">{formatNumber(item.rr)}</td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={2} className="py-2 text-xs text-slate-500">
                        No container RR values available.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>

          <section className="rounded-md border border-slate-200 bg-white p-4">
            <h4 className="text-sm font-semibold text-slate-800">History</h4>
            {history.length === 0 ? (
              <p className="mt-2 text-xs text-slate-500">No previous snapshots recorded.</p>
            ) : (
              <ul className="mt-3 divide-y divide-slate-100 text-sm">
                {history.map((entry) => (
                  <li key={entry.path} className="py-2 flex items-center justify-between">
                    <div>
                      <p className="font-medium text-slate-700">{entry.generated_at || 'Unknown time'}</p>
                      <p className="text-xs text-slate-500">{entry.path}</p>
                    </div>
                    <div className="text-right text-xs text-slate-500">
                      Containers: {getCountSafe(entry.counts as any, 'containers') ?? '—'} · RR:{' '}
                      {formatNumber(Number((entry.rr as any)?.overall_rr))}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      ) : (
        !loading && <p className="text-sm text-slate-500">No holistic data available yet.</p>
      )}
    </div>
  )
}
