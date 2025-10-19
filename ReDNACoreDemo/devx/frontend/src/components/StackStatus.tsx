import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import clsx from 'clsx'
import { toast } from 'react-toastify'

import stackApi, {
  LogsResponse,
  StackServiceKey,
  StackServiceStatus,
  StackStatusResponse,
  StackReadyResponse,
  SupervisorRestartResponse,
} from '@/lib/stackApi'
import Troubleshooter from './Troubleshooter'

type ModalTab = 'health' | 'metrics' | 'logs'

const SERVICE_LABELS: Record<StackServiceKey, string> = {
  core: 'Core API',
  ucnrr: 'UCNRR',
  devx: 'DevX Backend',
}

const STATUS_CLASSES: Record<StackServiceStatus['status'], string> = {
  healthy: 'border-green-500 bg-green-50',
  degraded: 'border-amber-500 bg-amber-50',
  down: 'border-red-500 bg-red-50',
}

const STATUS_BADGES: Record<StackServiceStatus['status'], string> = {
  healthy: 'text-emerald-700 bg-emerald-100',
  degraded: 'text-amber-700 bg-amber-100',
  down: 'text-red-700 bg-red-100',
}

interface SelectedServiceState {
  status: StackServiceStatus
  logs: LogsResponse | null
  metrics: Record<string, unknown> | null
  metricsError: string | null
}

function formatRelative(timestamp: number | null): string {
  if (!timestamp) return 'n/a'
  const seconds = Math.floor((Date.now() - timestamp) / 1000)
  if (seconds < 5) return 'just now'
  if (seconds < 60) return `${seconds}s ago`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ${minutes % 60}m ago`
  const days = Math.floor(hours / 24)
  return `${days}d ${hours % 24}h ago`
}

function formatUptime(health?: Record<string, unknown>): string {
  const value = typeof health?.uptime_seconds === 'number' ? health.uptime_seconds : null
  if (value === null) return '—'
  const hours = Math.floor(value / 3600)
  const minutes = Math.floor((value % 3600) / 60)
  if (hours === 0 && minutes === 0) {
    return `${Math.floor(value)}s`
  }
  if (hours === 0) {
    return `${minutes}m`
  }
  return `${hours}h ${minutes}m`
}

function formatPromptSha(health?: Record<string, unknown>): string {
  const raw = typeof health?.prompt_sha256 === 'string' ? health.prompt_sha256 : ''
  return raw ? raw.slice(0, 8) : '—'
}

function rrBadge(health?: Record<string, unknown>): string | null {
  const mode = typeof health?.rr_mode === 'string' ? health.rr_mode : null
  if (!mode) return null

  const normalized = mode.toLowerCase()
  if (normalized === 'online') return '🟢 online'
  if (normalized === 'fallback') return '🟡 fallback'
  return '🔴 unavailable'
}

function formatVersion(value?: string | null): string {
  if (!value) return '—'
  return value
}

function formatPython(path?: string | null): { label: string; title: string } {
  if (!path) {
    return { label: '—', title: 'Interpreter path unavailable' }
  }
  const normalized = path.replace(/\\/g, '/')
  const parts = normalized.split('/')
  const label = parts.length > 3 ? `…/${parts.slice(-3).join('/')}` : normalized
  return { label, title: path }
}

function formatRelativeIso(iso?: string | null): string {
  if (!iso) return '—'
  const ts = Date.parse(iso)
  if (Number.isNaN(ts)) return iso
  return formatRelative(ts)
}

async function fetchMetricsFor(service: StackServiceStatus): Promise<Record<string, unknown> | null> {
  if (service.service !== 'core') return null
  const response = await fetch(`http://127.0.0.1:${service.port}/metrics`, { method: 'GET' })
  if (!response.ok) {
    throw new Error(`Metrics request failed: ${response.status}`)
  }
  return response.json() as Promise<Record<string, unknown>>
}

export default function StackStatus() {
  const isMountedRef = useRef(true)
  const [data, setData] = useState<StackStatusResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdated, setLastUpdated] = useState<number | null>(null)
  const [selected, setSelected] = useState<SelectedServiceState | null>(null)
  const [activeTab, setActiveTab] = useState<ModalTab>('health')
  const [troubleshooterTarget, setTroubleshooterTarget] = useState<StackServiceKey | null>(null)
  const [logsRefreshing, setLogsRefreshing] = useState(false)
  const [downloadingLogs, setDownloadingLogs] = useState(false)
  const lastErrorRef = useRef<string | null>(null)
  const logsRef = useRef<HTMLDivElement | null>(null)
  const [readiness, setReadiness] = useState<StackReadyResponse | null>(null)
  const [readinessError, setReadinessError] = useState<string | null>(null)
  const readinessErrorRef = useRef<string | null>(null)
  const [restartHistory, setRestartHistory] = useState<Array<Record<string, unknown>>>([])
  const [autoRecoverLoading, setAutoRecoverLoading] = useState(false)
  const [autoRecoverResult, setAutoRecoverResult] = useState<SupervisorRestartResponse | null>(null)

  useEffect(() => {
    return () => {
      isMountedRef.current = false
    }
  }, [])

  const loadStatus = useCallback(
    async (notifyReadyError: boolean) => {
      try {
        const payload = await stackApi.getStatus()
        if (!isMountedRef.current) {
          return
        }
        setData(payload)
        setError(null)
        lastErrorRef.current = null
        setLastUpdated(Date.now())
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to load stack status.'
        if (!isMountedRef.current) {
          return
        }
        setError(message)
        if (lastErrorRef.current !== message) {
          toast.error(message)
          lastErrorRef.current = message
        }
      }

      try {
        const readyPayload = await stackApi.getReady()
        if (!isMountedRef.current) {
          return
        }
        setReadiness(readyPayload)
        setReadinessError(null)
        readinessErrorRef.current = null
        try {
          const historyPayload = await stackApi.getRestartHistory(3)
          if (isMountedRef.current) {
            setRestartHistory(historyPayload.history)
          }
        } catch (historyError) {
          if (isMountedRef.current) {
            setRestartHistory([])
            if (notifyReadyError) {
              console.debug('Restart history fetch failed:', historyError)
            }
          }
        }
      } catch (err) {
        const message =
          err instanceof Error ? err.message : 'Failed to evaluate stack readiness.'
        if (!isMountedRef.current) {
          return
        }
        setReadiness(null)
        setReadinessError(message)
        setRestartHistory([])
        if (notifyReadyError && readinessErrorRef.current !== message) {
          toast.error(`Readiness check failed: ${message}`)
          readinessErrorRef.current = message
        } else if (!notifyReadyError) {
          readinessErrorRef.current = message
        }
      }
    },
    []
  )

  useEffect(() => {
    let cancelled = false

    const runInitial = async () => {
      setLoading(true)
      await loadStatus(false)
      if (!cancelled) {
        setLoading(false)
      }
    }

    void runInitial()
    const interval = setInterval(() => {
      void loadStatus(false)
    }, 5000)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [loadStatus])

  const refreshStatus = async () => {
    setLoading(true)
    try {
      await loadStatus(true)
    } finally {
      if (isMountedRef.current) {
        setLoading(false)
      }
    }
  }

  const handleAutoRecovery = useCallback(async () => {
    if (autoRecoverLoading) {
      return
    }
    setAutoRecoverLoading(true)
    try {
      const response = await stackApi.restartServices({
        services: ['core', 'ucnrr'],
        reason: 'stack_status_auto_recovery',
        force: false,
      })
      if (!isMountedRef.current) {
        return
      }
      setAutoRecoverResult(response)

      if (response.restarted.length > 0) {
        const names = response.restarted.map((entry) => entry.service).join(', ')
        toast.success(`Auto-recovery restarted ${names}`)
      } else if (response.rate_limited.length > 0) {
        toast.warn('Auto-recovery blocked: restart rate limited.')
      } else {
        toast.info('Auto-recovery executed but no services required restart.')
      }
    } catch (error) {
      if (isMountedRef.current) {
        const message = error instanceof Error ? error.message : 'Auto-recovery failed.'
        toast.error(message)
      }
    } finally {
      if (isMountedRef.current) {
        await loadStatus(true)
        setAutoRecoverLoading(false)
      }
    }
  }, [autoRecoverLoading, loadStatus])

  const isStale = useMemo(() => {
    if (!lastUpdated) return false
    return Date.now() - lastUpdated > 15000
  }, [lastUpdated])

  const openServiceDetail = async (status: StackServiceStatus) => {
    setActiveTab('health')
    setSelected({
      status,
      logs: null,
      metrics: null,
      metricsError: null,
    })
    try {
      const logsPayload = await stackApi.getLogs(status.service, 50)
      let metricsPayload: Record<string, unknown> | null = null
      let metricsError: string | null = null
      try {
        metricsPayload = await fetchMetricsFor(status)
      } catch (error) {
        metricsError = error instanceof Error ? error.message : 'Failed to load metrics.'
      }
      setSelected({
        status,
        logs: logsPayload,
        metrics: metricsPayload,
        metricsError,
      })
      if (status.status === 'down') {
        setTroubleshooterTarget(status.service)
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load service details.'
      setSelected({
        status,
        logs: null,
        metrics: null,
        metricsError: message,
      })
      toast.error(message)
    }
  }

  useEffect(() => {
    if (!selected) return
    setLogsRefreshing(true)
    let cancelled = false

    const refreshLogs = async () => {
      try {
        const logsPayload = await stackApi.getLogs(selected.status.service, 50)
        if (!cancelled) {
          setSelected((prev) =>
            prev && prev.status.service === selected.status.service
              ? { ...prev, logs: logsPayload }
              : prev
          )
        }
      } finally {
        if (!cancelled) {
          setLogsRefreshing(false)
        }
      }
    }

    refreshLogs()
    const interval = setInterval(refreshLogs, 5000)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [selected?.status.service])

  useEffect(() => {
    if (!selected?.logs || !logsRef.current) return
    logsRef.current.scrollTop = logsRef.current.scrollHeight
  }, [selected?.logs])

  const services = useMemo(() => data?.services ?? [], [data])

  const handleDownloadLogs = async () => {
    if (!selected) return
    setDownloadingLogs(true)
    try {
      const payload = await stackApi.getLogs(selected.status.service, 500)
      const blob = new Blob([JSON.stringify(payload, null, 2)], {
        type: 'application/json',
      })
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = `${selected.status.service}-logs.json`
      document.body.appendChild(anchor)
      anchor.click()
      document.body.removeChild(anchor)
      URL.revokeObjectURL(url)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to download logs.'
      toast.error(message)
    } finally {
      setDownloadingLogs(false)
    }
  }

  const lastUpdatedLabel = lastUpdated ? formatRelative(lastUpdated) : 'n/a'
  const readinessCheckedLabel = readiness?.checked_at
    ? formatRelativeIso(readiness.checked_at)
    : null
  const unreadyRelative = readiness?.unready_since
    ? formatRelativeIso(readiness.unready_since)
    : null
  const autoRecoverDisabled =
    !readiness ||
    readiness.status === 'ready' ||
    readiness.recovery_suggestions.length === 0 ||
    readiness.fail_conditions.some((code) => code.includes('rate_limited')) ||
    autoRecoverLoading

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold text-slate-900">Stack Status</h2>
          <p className="text-sm text-slate-500">
            Last updated: {lastUpdatedLabel}{' '}
            {isStale && <span className="font-medium text-amber-600">(stale)</span>}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {readiness && readiness.ready && (
            <span
              className="inline-flex items-center gap-2 rounded-full bg-emerald-100 px-3 py-1 text-sm font-semibold text-emerald-700"
              title={readinessCheckedLabel ? `Checked ${readinessCheckedLabel}` : undefined}
            >
              <span className="h-2 w-2 rounded-full bg-emerald-500" />
              System Ready
            </span>
          )}
          <button
            type="button"
            onClick={refreshStatus}
            className="inline-flex items-center rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50"
          >
            Refresh All
          </button>
        </div>
      </div>

      {readiness && readiness.status !== 'ready' && (
        <div className="space-y-3 rounded-md border border-amber-200 bg-amber-50 px-4 py-4 text-sm text-amber-800">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-base font-semibold">
                System status: {readiness.status.toUpperCase()}
              </p>
              <p className="text-xs text-amber-600">
                Checked {readinessCheckedLabel ?? 'n/a'}
                {unreadyRelative ? ` · Unready since ${unreadyRelative}` : ''}
              </p>
            </div>
            <button
              type="button"
              onClick={handleAutoRecovery}
              disabled={autoRecoverDisabled}
              className={clsx(
                'inline-flex items-center rounded-md px-3 py-1.5 text-sm font-medium shadow-sm transition',
                autoRecoverDisabled
                  ? 'cursor-not-allowed border border-amber-200 bg-amber-100 text-amber-400'
                  : 'border border-amber-300 bg-white text-amber-700 hover:bg-amber-100'
              )}
            >
              {autoRecoverLoading ? 'Attempting…' : 'Attempt Auto-Recovery'}
            </button>
          </div>

          <div>
            <p className="font-semibold">Reasons</p>
            <ul className="mt-1 list-disc space-y-1 pl-5 text-xs">
              {readiness.reasons.length > 0 ? (
                readiness.reasons.map((reason, index) => (
                  <li key={`${reason}-${index}`}>{reason}</li>
                ))
              ) : (
                <li>No readiness reasons reported.</li>
              )}
            </ul>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <p className="font-semibold">Fail Conditions</p>
              <ul className="mt-1 list-disc space-y-1 pl-5 text-xs">
                {readiness.fail_conditions.map((code) => (
                  <li key={code}>{code.replaceAll('_', ' ')}</li>
                ))}
              </ul>
            </div>
            <div>
              <p className="font-semibold">Rolling Window ({readiness.rolling_window_sec}s)</p>
              <ul className="mt-1 space-y-1 text-xs">
                <li>
                  Error rate (5m):{' '}
                  {typeof readiness.error_rate_5m === 'number'
                    ? `${(readiness.error_rate_5m * 100).toFixed(2)}%`
                    : 'n/a'}
                </li>
                <li>
                  P95 latency (5m):{' '}
                  {typeof readiness.p95_latency_ms_5m === 'number'
                    ? `${readiness.p95_latency_ms_5m.toFixed(0)} ms`
                    : 'n/a'}
                </li>
              </ul>
            </div>
          </div>

          {readiness.recovery_suggestions.length > 0 && (
            <div>
              <p className="font-semibold">Suggested Actions</p>
              <ul className="mt-1 list-disc space-y-1 pl-5 text-xs">
                {readiness.recovery_suggestions.map((suggestion) => (
                  <li key={`${suggestion.service}-${suggestion.reason}`}>
                    {suggestion.service.toUpperCase()} → {suggestion.reason}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {Object.values(readiness.rate_limit).some((info) => info.rate_limited) && (
            <div className="rounded-md border border-red-200 bg-red-100 px-3 py-2 text-xs text-red-700">
              Restart rate limit exceeded for{' '}
              {Object.entries(readiness.rate_limit)
                .filter(([, info]) => info.rate_limited)
                .map(([svc]) => svc.toUpperCase())
                .join(', ')}
              . Try again later.
            </div>
          )}

          {restartHistory.length > 0 && (
            <div>
              <p className="font-semibold">Recent Restart Attempts</p>
              <ul className="mt-1 space-y-1 text-xs text-amber-700">
                {restartHistory.slice(0, 3).map((entry, index) => (
                  <li key={typeof entry.ts === 'string' ? entry.ts : index}>
                    {typeof entry.ts === 'string' ? `${formatRelativeIso(entry.ts)} · ` : ''}
                    {String(entry.service ?? '—')} — {String(entry.status ?? 'unknown')} ({String(entry.reason ?? 'unspecified')})
                  </li>
                ))}
              </ul>
            </div>
          )}

          {autoRecoverResult && (
            <div className="rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-xs text-blue-700">
              Last auto-recovery: {autoRecoverResult.restarted.length} restarted ·{' '}
              {autoRecoverResult.rate_limited.length} rate limited · {autoRecoverResult.skipped.length} skipped.
            </div>
          )}
        </div>
      )}

      {readinessError && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          Readiness check failed: {readinessError}
        </div>
      )}

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {loading && (
        <div className="flex items-center gap-2 rounded-md border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600">
          <span className="h-3 w-3 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
          Loading stack status…
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {services.map((service) => (
          <button
            key={service.service}
            type="button"
            onClick={() => openServiceDetail(service)}
            className={clsx(
              'flex flex-col items-start gap-2 rounded-xl border p-4 text-left shadow-sm transition hover:-translate-y-0.5 hover:shadow',
              STATUS_CLASSES[service.status]
            )}
          >
            <div className="flex w-full items-center justify-between">
              <div>
                <p className="text-sm font-medium text-slate-500">{SERVICE_LABELS[service.service]}</p>
                <p className="text-lg font-semibold text-slate-900">{service.status.toUpperCase()}</p>
              </div>
              <span
                className={clsx(
                  'inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-medium',
                  STATUS_BADGES[service.status]
                )}
              >
                <span className="inline-block h-2 w-2 rounded-full bg-current/70" />
                {service.status}
              </span>
            </div>
            <dl className="grid w-full grid-cols-2 gap-2 text-xs text-slate-600">
              <div>
                <dt className="font-medium text-slate-500">Port</dt>
                <dd className="font-mono text-sm text-slate-700">{service.port}</dd>
              </div>
              <div>
                <dt className="font-medium text-slate-500">Uptime</dt>
                <dd className="text-sm text-slate-700">{formatUptime(service.health)}</dd>
              </div>
              <div>
                <dt className="font-medium text-slate-500">Prompt SHA</dt>
                <dd className="font-mono text-sm text-slate-700">{formatPromptSha(service.health)}</dd>
              </div>
              <div>
                <dt className="font-medium text-slate-500">RR Mode</dt>
                <dd className="text-sm text-slate-700">
                  {service.service === 'core' ? rrBadge(service.health) ?? '—' : '—'}
                </dd>
              </div>
              <div>
                <dt className="font-medium text-slate-500">Version</dt>
                <dd className="text-sm text-slate-700">{formatVersion(service.version)}</dd>
              </div>
              <div>
                <dt className="font-medium text-slate-500">Python</dt>
                <dd
                  className="text-sm text-slate-700"
                  title={formatPython(service.python).title}
                >
                  {formatPython(service.python).label}
                </dd>
              </div>
              <div className="col-span-2">
                <dt className="font-medium text-slate-500">Last check</dt>
                <dd className="text-sm text-slate-700">{formatRelativeIso(service.last_check)}</dd>
              </div>
            </dl>
            {service.error && (
              <p className="w-full rounded-md border border-red-200 bg-red-50 px-2 py-1 text-xs text-red-700">
                {service.error}
              </p>
            )}
          </button>
        ))}
      </div>

      {selected && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="relative flex h-full w-full max-w-5xl flex-col overflow-hidden rounded-xl bg-white shadow-xl">
            <div className="border-b border-slate-200 px-6 py-4">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h3 className="text-xl font-semibold text-slate-900">
                    {SERVICE_LABELS[selected.status.service]}
                  </h3>
                  {(() => {
                    const pythonMeta = formatPython(selected.status.python)
                    return (
                      <p className="text-sm text-slate-500">
                        Status: {selected.status.status} · Port {selected.status.port} · Version{' '}
                        {formatVersion(selected.status.version)} · Python{' '}
                        <span title={pythonMeta.title}>{pythonMeta.label}</span>
                      </p>
                    )
                  })()}
                  <p className="text-xs text-slate-400">
                    Last check: {formatRelativeIso(selected.status.last_check)}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setTroubleshooterTarget(selected.status.service)}
                    className="inline-flex items-center rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white shadow-sm hover:bg-blue-500"
                  >
                    Troubleshoot
                  </button>
                  <button
                    type="button"
                    onClick={() => setSelected(null)}
                    className="rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-50"
                  >
                    Close
                  </button>
                </div>
              </div>
              <div className="mt-4 flex border-b border-slate-200 text-sm">
                {(['health', 'metrics', 'logs'] as const).map((tab) => (
                  <button
                    key={tab}
                    type="button"
                    onClick={() => setActiveTab(tab)}
                    className={clsx(
                      'px-3 py-2 capitalize transition',
                      activeTab === tab
                        ? 'border-b-2 border-blue-600 text-blue-600'
                        : 'text-slate-500 hover:text-slate-700'
                    )}
                  >
                    {tab}
                  </button>
                ))}
              </div>
            </div>
            <div className="flex-1 overflow-y-auto px-6 py-4 text-sm text-slate-700">
              {activeTab === 'health' && (
                <pre className="max-h-[480px] overflow-auto rounded-md border border-slate-200 bg-slate-50 p-4 text-xs leading-relaxed text-slate-800">
                  {JSON.stringify(selected.status.health ?? { message: 'No health payload.' }, null, 2)}
                </pre>
              )}
              {activeTab === 'metrics' && (
                <div>
                  {selected.metricsError && (
                    <div className="mb-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-700">
                      {selected.metricsError}
                    </div>
                  )}
                  {selected.metrics ? (
                    <pre className="max-h-[480px] overflow-auto rounded-md border border-slate-200 bg-slate-50 p-4 text-xs leading-relaxed text-slate-800">
                      {JSON.stringify(selected.metrics, null, 2)}
                    </pre>
                  ) : (
                    <p className="text-slate-500">Metrics not available for this service.</p>
                  )}
                </div>
              )}
              {activeTab === 'logs' && (
                <div className="flex h-full flex-col">
                  <div className="flex items-center justify-between py-2 text-xs text-slate-500">
                    <div>
                      Showing last {selected.logs?.total_lines ?? 0} entries ·{' '}
                      <span className="font-mono">{selected.logs?.log_file ?? 'n/a'}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      {logsRefreshing && (
                        <span className="inline-flex items-center gap-1 text-slate-400">
                          <span className="h-2 w-2 animate-spin rounded-full border-2 border-blue-400 border-t-transparent" />
                          Refreshing…
                        </span>
                      )}
                      <button
                        type="button"
                        onClick={handleDownloadLogs}
                        disabled={downloadingLogs}
                        className={clsx(
                          'rounded-md border border-slate-200 bg-white px-2 py-1 text-xs font-medium text-slate-600 shadow-sm transition',
                          downloadingLogs ? 'cursor-not-allowed opacity-60' : 'hover:bg-slate-100'
                        )}
                      >
                        {downloadingLogs ? 'Preparing…' : 'Download'}
                      </button>
                    </div>
                  </div>
                  <div
                    ref={logsRef}
                    className="flex-1 overflow-y-auto rounded-md border border-slate-200 bg-slate-50 p-3 text-xs leading-relaxed text-slate-800"
                  >
                    {selected.logs?.lines.map((entry, index) => (
                      <div key={index} className="mb-2 whitespace-pre-wrap">
                        <span className="font-mono text-slate-500">{entry.ts ?? '—'}</span>
                        <span className="mx-2 rounded bg-slate-200 px-1 py-0.5 font-medium uppercase text-slate-600">
                          {entry.level ?? 'n/a'}
                        </span>
                        <span className="font-medium text-slate-700">{entry.event ?? entry.message ?? '—'}</span>
                        {entry.raw && <div className="text-slate-600">{entry.raw}</div>}
                        {Object.keys(entry.rest).length > 0 && (
                          <pre className="mt-1 overflow-x-auto rounded bg-white/70 p-2 text-[11px] text-slate-600 shadow-inner">
                            {JSON.stringify(entry.rest, null, 2)}
                          </pre>
                        )}
                      </div>
                    ))}
                    {(!selected.logs || selected.logs.total_lines === 0) && (
                      <p className="text-slate-500">No log entries available.</p>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {troubleshooterTarget && (
        <Troubleshooter
          service={troubleshooterTarget}
          onClose={() => setTroubleshooterTarget(null)}
          onSuccess={refreshStatus}
        />
      )}
    </div>
  )
}
