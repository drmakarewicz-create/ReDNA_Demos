import { useEffect, useMemo, useState } from 'react'
import { adaptiveAnalyticsApi, OverviewItem, UserAnalyticsPayload } from '@/lib/adaptiveAnalyticsApi'

const REFRESH_INTERVAL_MS = 10_000

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`
}

function formatDateLabel(iso: string): string {
  try {
    const date = new Date(iso)
    return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
  } catch (e) {
    return iso
  }
}

export default function AdaptiveAnalyticsDashboard() {
  const [overview, setOverview] = useState<OverviewItem[]>([])
  const [selectedUser, setSelectedUser] = useState<string>('')
  const [payload, setPayload] = useState<UserAnalyticsPayload | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdated, setLastUpdated] = useState<string | null>(null)

  // Load overview once on mount
  useEffect(() => {
    let cancelled = false
    const loadOverview = async () => {
      try {
        const data = await adaptiveAnalyticsApi.getOverview()
        if (cancelled) return
        setOverview(data.users)
        if (!selectedUser && data.users.length > 0) {
          setSelectedUser(data.users[0].user_id)
        }
      } catch (err: any) {
        if (!cancelled) {
          setError(err.message || 'Failed to load adaptive analytics overview')
        }
      }
    }

    loadOverview()
    const interval = setInterval(loadOverview, REFRESH_INTERVAL_MS)

    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [selectedUser])

  // Load user analytics on selection + every REFRESH_INTERVAL_MS
  useEffect(() => {
    if (!selectedUser) return
    let cancelled = false

    const loadUser = async () => {
      setLoading(true)
      setError(null)
      try {
        const data = await adaptiveAnalyticsApi.getUserView(selectedUser)
        if (!cancelled) {
          setPayload(data)
          setLastUpdated(data.generated_at)
        }
      } catch (err: any) {
        if (!cancelled) {
          setError(err.message || `Failed to load analytics for ${selectedUser}`)
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    loadUser()
    const interval = setInterval(loadUser, REFRESH_INTERVAL_MS)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [selectedUser])

  const velocityPoints = useMemo(() => {
    if (!payload) return []
    return payload.learning_velocity.daily
  }, [payload])

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Adaptive Analytics</h1>
          <p className="text-sm text-gray-600">
            Live fusion of ontology telemetry and Life OS signals. Updates every 10 seconds.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <label className="text-sm text-gray-600" htmlFor="aai-user-select">
            User
          </label>
          <select
            id="aai-user-select"
            className="rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            value={selectedUser}
            onChange={(event) => setSelectedUser(event.target.value)}
          >
            {overview.map((item) => (
              <option key={item.user_id} value={item.user_id}>
                {item.user_id} — {formatPercent(item.rolling_avg_7d)}
              </option>
            ))}
          </select>
        </div>
      </header>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <section className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <div className="lg:col-span-8 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900">Learning Velocity (7d window)</h2>
            <span className="text-xs text-gray-500">
              {lastUpdated ? `Updated ${new Date(lastUpdated).toLocaleTimeString()}` : '—'}
            </span>
          </div>
          <div className="rounded-lg border border-gray-200 bg-white p-4">
            {velocityPoints.length === 0 ? (
              <p className="text-sm text-gray-500">No learning events recorded yet.</p>
            ) : (
              <LearningVelocityChart points={velocityPoints} loading={loading} />
            )}
          </div>
        </div>

        <div className="lg:col-span-4">
          <div className="rounded-lg border border-gray-200 bg-white p-4 space-y-4">
            <h2 className="text-lg font-semibold text-gray-900">Adaptive Confidence</h2>
            <ConfidenceGauge value={payload?.confidence.value ?? 0} sources={payload?.confidence.sources ?? {}} />
            <div>
              <p className="text-xs uppercase tracking-wide text-gray-500">Rolling Avg (7d)</p>
              <p className="text-xl font-semibold text-gray-900">
                {payload ? formatPercent(payload.learning_velocity.rolling_avg_7d) : '0.0%'}
              </p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-gray-500">Goal Confidence</p>
              <p className="text-xl font-semibold text-gray-900">
                {payload ? formatPercent(payload.learning_velocity.goal_confidence_avg) : '0.0%'}
              </p>
              <p className="text-xs text-gray-500">({payload?.learning_velocity.goals_total || 0} goals tracked)</p>
            </div>
          </div>
        </div>
      </section>

      <section className="rounded-lg border border-gray-200 bg-white p-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">Top Predicted Focus Areas</h2>
          {loading && <span className="text-xs text-gray-400">Refreshing…</span>}
        </div>
        {payload && payload.predictions.length > 0 ? (
          <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
            {payload.predictions.map((prediction) => (
              <article key={`${prediction.target}-${prediction.persona}`} className="rounded-md border border-blue-100 bg-blue-50/60 p-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-blue-800">{prediction.target}</span>
                  <span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700">
                    {prediction.persona}
                  </span>
                </div>
                <dl className="mt-3 space-y-1 text-xs text-blue-900">
                  <div className="flex items-center justify-between">
                    <dt>Composite Score</dt>
                    <dd className="font-semibold">{formatPercent(prediction.score)}</dd>
                  </div>
                  <div className="flex items-center justify-between">
                    <dt>Ontology Signal</dt>
                    <dd>{formatPercent(prediction.sources.ontology)}</dd>
                  </div>
                  <div className="flex items-center justify-between">
                    <dt>Correlation</dt>
                    <dd>{formatPercent(prediction.sources.correlation)}</dd>
                  </div>
                  <div className="flex items-center justify-between">
                    <dt>Life OS</dt>
                    <dd>{formatPercent(prediction.sources.life_os)}</dd>
                  </div>
                </dl>
              </article>
            ))}
          </div>
        ) : (
          <p className="mt-4 text-sm text-gray-500">Predictions will appear once telemetry and Life OS data accrue.</p>
        )}
      </section>
    </div>
  )
}

function LearningVelocityChart({
  points,
  loading,
}: {
  points: { date: string; value: number }[]
  loading: boolean
}) {
  const values = points.map((point) => point.value)
  const maxValue = Math.max(...values, 1)
  const minValue = Math.min(...values, 0)
  const range = maxValue - minValue || 1

  const svgPoints = points.map((point, index) => {
    const x = (index / (points.length - 1 || 1)) * 100
    const normalized = (point.value - minValue) / range
    const y = 100 - normalized * 100
    return `${x},${y}`
  })

  return (
    <div className="relative">
      <svg viewBox="0 0 100 100" className="h-40 w-full text-blue-500" preserveAspectRatio="none">
        <polyline fill="none" stroke="currentColor" strokeWidth="2" points={svgPoints.join(' ')} />
      </svg>
      <div className="absolute inset-0 flex items-end justify-between px-2 text-[10px] text-gray-500">
        {points.slice(-4).map((point) => (
          <span key={point.date}>{formatDateLabel(point.date)}</span>
        ))}
      </div>
      {loading && (
        <div className="absolute inset-0 flex items-center justify-center bg-white/60 text-sm text-gray-600">
          Refreshing…
        </div>
      )}
    </div>
  )
}

function ConfidenceGauge({ value, sources }: { value: number; sources: Partial<{ ontology: number; correlation: number; life_os: number }> }) {
  const pct = Math.max(0, Math.min(1, value)) * 100
  return (
    <div className="space-y-2">
      <div className="h-24 rounded-full border border-blue-200 bg-blue-50 flex flex-col items-center justify-center">
        <span className="text-xs text-blue-600 uppercase tracking-wide">Adaptive Confidence</span>
        <span className="text-2xl font-bold text-blue-800">{pct.toFixed(1)}%</span>
      </div>
      <div className="space-y-1 text-xs text-gray-600">
        <p>Ontology • {formatPercent(sources.ontology ?? 0)}</p>
        <p>Correlation • {formatPercent(sources.correlation ?? 0)}</p>
        <p>Life OS • {formatPercent(sources.life_os ?? 0)}</p>
      </div>
    </div>
  )
}
