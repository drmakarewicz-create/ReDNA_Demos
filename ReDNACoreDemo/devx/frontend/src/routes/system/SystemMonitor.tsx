import { useEffect, useMemo, useState } from 'react'
import healthApi, { HealthHistoryEntry, HealthStatusResponse } from '@/lib/healthApi'

type ServiceKey = 'devx' | 'consent' | 'core'

const serviceLabels: Record<ServiceKey, string> = {
  devx: 'DevX',
  consent: 'Consent',
  core: 'Core',
}

const statusStyles: Record<string, string> = {
  green: 'bg-emerald-100 text-emerald-700',
  yellow: 'bg-amber-100 text-amber-700',
  amber: 'bg-amber-100 text-amber-700',
  red: 'bg-red-100 text-red-700',
}

function computeLatencyPoints(entries: HealthHistoryEntry[], service: ServiceKey, width: number, height: number) {
  if (entries.length === 0) return ''
  const maxLatency = Math.max(
    ...entries.map((entry) => {
      const value = entry[service].ms
      return typeof value === 'number' ? value : 0
    }),
    1
  )
  return entries
    .map((entry, index) => {
      const value = entry[service].ms
      const normalized = typeof value === 'number' ? value / maxLatency : 0
      const x = (index / Math.max(entries.length - 1, 1)) * width
      const y = height - normalized * height
      return `${x},${y}`
    })
    .join(' ')
}

function computeAvailabilityRects(entries: HealthHistoryEntry[], service: ServiceKey, width: number, height: number) {
  if (entries.length === 0) return []
  const barWidth = width / entries.length
  return entries.map((entry, index) => ({
    x: index * barWidth,
    width: barWidth - 1,
    height: entry[service].ok ? height : height / 3,
    ok: entry[service].ok,
  }))
}

export default function SystemMonitor() {
  const [status, setStatus] = useState<HealthStatusResponse | null>(null)
  const [history, setHistory] = useState<HealthHistoryEntry[]>([])
  const [error, setError] = useState<string | null>(null)

  const loadData = async () => {
    try {
      const [statusPayload, historyPayload] = await Promise.all([
        healthApi.getStatus(),
        healthApi.getHistory(100),
      ])
      setStatus(statusPayload)
      setHistory(historyPayload.entries)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load health data.')
    }
  }

  useEffect(() => {
    loadData()
    const interval = setInterval(loadData, 20000)
    return () => clearInterval(interval)
  }, [])

  const chartHistory = useMemo(() => history.slice().reverse(), [history])

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold text-slate-900">System Monitor</h2>
        <p className="mt-2 text-sm text-slate-600">
          Live view of core service health and historical latency. Data refreshes every 20 seconds.
        </p>
      </div>

      {error && <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}

      {status && (
        <div className="flex flex-wrap gap-2">
          {(Object.keys(serviceLabels) as ServiceKey[]).map((service) => {
            const entry = status[service]
            const badgeClass = statusStyles[entry.status] || 'bg-gray-200 text-gray-700'
            const tooltipParts = [
              `${serviceLabels[service]} — ${entry.detail || entry.status}`,
              entry.warning ? `Warning: ${entry.warning}` : null,
              entry.checked_at ? `Checked: ${entry.checked_at}` : null,
            ].filter(Boolean)
            const tooltip = tooltipParts.join(' • ')
            return (
              <span
                key={service}
                className={`flex items-center gap-1 rounded-full px-3 py-1 text-xs font-medium ${badgeClass}`}
                title={tooltip}
              >
                <span className="inline-block h-2 w-2 rounded-full bg-current/70" />
                {serviceLabels[service]} ({entry.ms !== null ? `${entry.ms} ms` : 'n/a'})
              </span>
            )
          })}
        </div>
      )}

      <section className="grid gap-6 md:grid-cols-2">
        {(Object.keys(serviceLabels) as ServiceKey[]).map((service) => (
          <div key={service} className="rounded-md border border-slate-200 bg-white p-4">
            <h3 className="text-sm font-semibold text-slate-800">Latency — {serviceLabels[service]}</h3>
            {chartHistory.length === 0 ? (
              <p className="mt-2 text-xs text-slate-500">No history available yet.</p>
            ) : (
              <svg viewBox="0 0 320 120" className="mt-3 h-32 w-full">
                <polyline
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  className="text-blue-500"
                  points={computeLatencyPoints(chartHistory, service, 320, 120)}
                />
              </svg>
            )}
          </div>
        ))}
      </section>

      <section className="rounded-md border border-slate-200 bg-white p-4">
        <h3 className="text-sm font-semibold text-slate-800">Availability timeline</h3>
        {chartHistory.length === 0 ? (
          <p className="mt-2 text-xs text-slate-500">No history available yet.</p>
        ) : (
          <div className="mt-3 space-y-4">
            {(Object.keys(serviceLabels) as ServiceKey[]).map((service) => (
              <div key={service}>
                <p className="text-xs uppercase text-slate-500">{serviceLabels[service]}</p>
                <svg viewBox="0 0 320 40" className="h-10 w-full">
                  {computeAvailabilityRects(chartHistory, service, 320, 24).map((bar, index) => (
                    <rect
                      key={`${service}-${index}`}
                      x={bar.x}
                      y={bar.ok ? 0 : 16}
                      width={bar.width}
                      height={bar.height}
                      className={bar.ok ? 'fill-emerald-400' : 'fill-red-400'}
                      rx={1}
                    />
                  ))}
                </svg>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
