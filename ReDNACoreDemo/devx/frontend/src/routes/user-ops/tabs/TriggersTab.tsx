import { useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'react-toastify'
import userOpsApi, {
  TriggerConfig,
  TriggerEvent,
  TriggerFileWatcherConfig,
  TriggerCalendarConfig,
  TriggerTelemetryConfig,
  TriggerConflictConfig,
} from '@/lib/userOpsApi'

interface TriggersTabProps {
  userId: string
}

const STATUS_COLORS: Record<string, string> = {
  completed: 'bg-emerald-100 text-emerald-700 border border-emerald-200',
  blocked: 'bg-amber-100 text-amber-800 border border-amber-200',
  failed: 'bg-red-100 text-red-700 border border-red-200',
  queued: 'bg-blue-100 text-blue-700 border border-blue-200',
  proposed: 'bg-slate-100 text-slate-700 border border-slate-200',
}

const prettyStatus = (raw?: string | null) => {
  if (!raw) return null
  const value = raw.toString().toLowerCase()
  return value
}

const defaultFileWatcher = (): TriggerFileWatcherConfig => ({
  enabled: true,
  paths: ['watched'],
  dedupe_minutes: 5,
  max_events_per_minute: 5,
})

const defaultCalendar = (): TriggerCalendarConfig => ({
  enabled: false,
  shared_secret: null,
  lead_minutes: 120,
  max_events_per_day: 10,
})

const defaultTelemetry = (): TriggerTelemetryConfig => ({
  enabled: true,
  event_count: 3,
  window_hours: 6,
  sentiment_threshold: -0.5,
  max_events_per_day: 12,
})

const defaultConflict = (): TriggerConflictConfig => ({
  enabled: true,
  threshold: 5,
  max_events_per_day: 8,
})

export default function TriggersTab({ userId }: TriggersTabProps) {
  const [config, setConfig] = useState<TriggerConfig | null>(null)
  const [pathsText, setPathsText] = useState('')
  const [recent, setRecent] = useState<TriggerEvent[]>([])
  const [loadingConfig, setLoadingConfig] = useState(true)
  const [loadingRecent, setLoadingRecent] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [recentError, setRecentError] = useState<string | null>(null)
  const [payloadModal, setPayloadModal] = useState<TriggerEvent | null>(null)

  const loadConfig = async () => {
    try {
      setLoadingConfig(true)
      setError(null)
      const cfg = await userOpsApi.getTriggerConfig(userId)
      const normalized = normalizeConfig(cfg)
      setConfig(normalized)
      setPathsText(normalized.file_watcher.paths.join('\n'))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load trigger configuration.')
      setConfig(null)
      setPathsText('')
    } finally {
      setLoadingConfig(false)
    }
  }

  const loadRecent = async (limit = 20) => {
    try {
      setLoadingRecent(true)
      setRecentError(null)
      const events = await userOpsApi.getRecentTriggers(userId, limit)
      setRecent(events ?? [])
    } catch (err) {
      setRecentError(err instanceof Error ? err.message : 'Failed to load recent triggers.')
      setRecent([])
    } finally {
      setLoadingRecent(false)
    }
  }

  useEffect(() => {
    loadConfig()
    loadRecent()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId])

  const handleToggle =
    <K extends keyof TriggerConfig>(section: K, key: keyof TriggerConfig[K], coerce?: (value: any) => any) =>
    (value: any) => {
      setConfig(prev => {
        if (!prev) return prev
        const nextSection = {
          ...(prev[section] as Record<string, any>),
          [key]: coerce ? coerce(value) : value,
        }
        return {
          ...prev,
          [section]: nextSection,
        }
      })
    }

  const handleSave = async () => {
    if (!config) return
    try {
      setSaving(true)
      const sanitized = {
        ...config,
        file_watcher: {
          ...config.file_watcher,
          paths: pathsText
            .split(/\r?\n/)
            .map(path => path.trim())
            .filter(Boolean),
        },
      }
      await userOpsApi.saveTriggerConfig(userId, sanitized)
      toast.success('Trigger configuration saved.')
      await loadConfig()
      await loadRecent()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to save trigger configuration.')
    } finally {
      setSaving(false)
    }
  }

  const sendTest = async (type: string, payload: Record<string, any>) => {
    try {
      const result = await userOpsApi.sendTestTrigger(userId, type, payload)
      const eventId = result.event?.id ?? '(no id)'
      const timestamp = result.event?.timestamp ?? ''
      toast.success(`Test trigger sent (${eventId}${timestamp ? ` @ ${formatTimestamp(timestamp)}` : ''})`)
      await loadRecent()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to send test trigger.')
    }
  }

  const fileWatcher = config?.file_watcher
  const telemetryCfg = config?.telemetry_threshold
  const conflictCfg = config?.conflict_backlog
  const calendarCfg = config?.calendar

  const recentRows = useMemo(() => {
    return recent.map(event => {
      const status =
        event.payload?.status ??
        event.status ??
        event.payload?.result?.status ??
        event.action ??
        null
      return {
        ...event,
        _status: prettyStatus(status),
        _payloadPreview: summarizePayload(event.payload),
      }
    })
  }, [recent])

  return (
    <div className="space-y-6">
      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <section className="rounded-lg border border-gray-200 bg-white shadow-sm">
        <div className="flex flex-col gap-4 border-b border-gray-200 px-6 py-5 md:flex-row md:items-center md:justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Trigger Configuration</h2>
            <p className="text-sm text-gray-600">
              Control event sources for <span className="font-medium text-gray-900">{userId}</span>. Consents for
              sensitive namespaces live in{' '}
              <Link to="../permissions" className="text-blue-600 hover:text-blue-800">
                Permissions
              </Link>
              .
            </p>
          </div>
          <button
            type="button"
            onClick={handleSave}
            disabled={saving || loadingConfig || !config}
            className="inline-flex items-center justify-center rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60"
          >
            {saving ? 'Saving…' : 'Save configuration'}
          </button>
        </div>

        <div className="grid gap-6 p-6 lg:grid-cols-2">
          <Card title="File Watcher" description="Monitor paths for new bundles or notes to analyze automatically.">
            {loadingConfig ? (
              <Skeleton />
            ) : (
              <>
                <label className="flex items-center gap-2 text-sm text-gray-700">
                  <input
                    type="checkbox"
                    className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    checked={fileWatcher?.enabled ?? false}
                    onChange={event => handleToggle('file_watcher', 'enabled')(event.target.checked)}
                  />
                  Enable file watcher
                </label>
                <label className="mt-4 block text-xs font-semibold uppercase tracking-wide text-gray-500">
                  Watched paths (one per line)
                </label>
                <textarea
                  value={pathsText}
                  onChange={event => {
                    setPathsText(event.target.value)
                  }}
                  rows={3}
                  className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  placeholder="watched"
                />
                <div className="mt-4 grid grid-cols-2 gap-3">
                  <NumberInput
                    label="Dedupe window (minutes)"
                    value={fileWatcher?.dedupe_minutes ?? 5}
                    min={1}
                    onChange={value => handleToggle('file_watcher', 'dedupe_minutes', Number)(value)}
                  />
                  <NumberInput
                    label="Max events per minute"
                    value={fileWatcher?.max_events_per_minute ?? 5}
                    min={1}
                    onChange={value => handleToggle('file_watcher', 'max_events_per_minute', Number)(value)}
                  />
                </div>
              </>
            )}
          </Card>

          <Card
            title="Telemetry Threshold"
            description="Alert when telemetry counts spike or sentiment dips."
          >
            {loadingConfig ? (
              <Skeleton />
            ) : (
              <>
                <label className="flex items-center gap-2 text-sm text-gray-700">
                  <input
                    type="checkbox"
                    className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    checked={telemetryCfg?.enabled ?? false}
                    onChange={event => handleToggle('telemetry_threshold', 'enabled')(event.target.checked)}
                  />
                  Enable telemetry threshold trigger
                </label>
                <div className="mt-4 grid grid-cols-2 gap-3">
                  <NumberInput
                    label="Events"
                    value={telemetryCfg?.event_count ?? 3}
                    min={1}
                    onChange={value => handleToggle('telemetry_threshold', 'event_count', Number)(value)}
                  />
                  <NumberInput
                    label="Within (hours)"
                    value={telemetryCfg?.window_hours ?? 6}
                    min={1}
                    onChange={value => handleToggle('telemetry_threshold', 'window_hours', Number)(value)}
                  />
                </div>
                <NumberInput
                  className="mt-3"
                  label="Sentiment threshold"
                  value={telemetryCfg?.sentiment_threshold ?? -0.5}
                  step={0.1}
                  onChange={value => handleToggle('telemetry_threshold', 'sentiment_threshold', Number)(value)}
                />
                <NumberInput
                  className="mt-3"
                  label="Max events per day"
                  value={telemetryCfg?.max_events_per_day ?? 12}
                  min={1}
                  onChange={value => handleToggle('telemetry_threshold', 'max_events_per_day', Number)(value)}
                />
              </>
            )}
          </Card>

          <Card
            title="Conflict Backlog"
            description="Escalate when unresolved refinement conflicts exceed a threshold."
          >
            {loadingConfig ? (
              <Skeleton />
            ) : (
              <>
                <label className="flex items-center gap-2 text-sm text-gray-700">
                  <input
                    type="checkbox"
                    className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    checked={conflictCfg?.enabled ?? false}
                    onChange={event => handleToggle('conflict_backlog', 'enabled')(event.target.checked)}
                  />
                  Enable conflict backlog trigger
                </label>
                <div className="mt-4 grid grid-cols-2 gap-3">
                  <NumberInput
                    label="Threshold (unresolved)"
                    value={conflictCfg?.threshold ?? 5}
                    min={1}
                    onChange={value => handleToggle('conflict_backlog', 'threshold', Number)(value)}
                  />
                  <NumberInput
                    label="Max per day"
                    value={conflictCfg?.max_events_per_day ?? 8}
                    min={1}
                    onChange={value => handleToggle('conflict_backlog', 'max_events_per_day', Number)(value)}
                  />
                </div>
              </>
            )}
          </Card>

          <Card title="Calendar Webhook" description="Incoming events for prep nudges. Webhook secrets stay server-side.">
            {loadingConfig ? (
              <Skeleton />
            ) : (
              <>
                <label className="flex items-center gap-2 text-sm text-gray-700">
                  <input
                    type="checkbox"
                    className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    checked={calendarCfg?.enabled ?? false}
                    onChange={event => handleToggle('calendar', 'enabled')(event.target.checked)}
                  />
                  Accept calendar webhook events
                </label>
                <div className="mt-4 grid grid-cols-2 gap-3">
                  <NumberInput
                    label="Lead minutes"
                    value={calendarCfg?.lead_minutes ?? 120}
                    min={15}
                    step={5}
                    onChange={value => handleToggle('calendar', 'lead_minutes', Number)(value)}
                  />
                  <NumberInput
                    label="Max events per day"
                    value={calendarCfg?.max_events_per_day ?? 10}
                    min={1}
                    onChange={value => handleToggle('calendar', 'max_events_per_day', Number)(value)}
                  />
                </div>
                <div className="mt-4 rounded-md border border-dashed border-gray-200 bg-gray-50 px-3 py-2 text-xs text-gray-600">
                  Webhook Secret:{' '}
                  {calendarCfg?.shared_secret ? (
                    <code className="break-all text-gray-900">{calendarCfg.shared_secret}</code>
                  ) : (
                    <span className="italic text-gray-500">Not configured</span>
                  )}
                </div>
              </>
            )}
          </Card>
        </div>
      </section>

      <section className="rounded-lg border border-gray-200 bg-white shadow-sm">
        <div className="flex flex-col gap-3 border-b border-gray-200 px-6 py-5 md:flex-row md:items-center md:justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Test Events</h2>
            <p className="text-sm text-gray-600">
              Emit synthetic triggers for this user. Events respect rate limits and appear in the recent list below.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={() =>
                sendTest('trigger.file_added', {
                  path: `watched/${userId}/test.txt`,
                  sensitive_namespaces: [],
                })
              }
              className="inline-flex items-center justify-center rounded-md border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100"
            >
              Send file_added
            </button>
            <button
              type="button"
              onClick={() =>
                sendTest('trigger.telemetry_threshold', {
                  metric: 'sentiment',
                  count: telemetryCfg?.event_count ?? 3,
                  window_hours: telemetryCfg?.window_hours ?? 6,
                })
              }
              className="inline-flex items-center justify-center rounded-md border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100"
            >
              Send telemetry_threshold
            </button>
            <button
              type="button"
              onClick={() =>
                sendTest('trigger.conflict_backlog', {
                  backlog_size: conflictCfg?.threshold ?? 5,
                })
              }
              className="inline-flex items-center justify-center rounded-md border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100"
            >
              Send conflict_backlog
            </button>
          </div>
        </div>
      </section>

      <section className="rounded-lg border border-gray-200 bg-white shadow-sm">
        <div className="flex items-center justify-between border-b border-gray-200 px-6 py-5">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Recent Trigger Events</h2>
            <p className="text-sm text-gray-600">
              Tail of the last 20 trigger entries from the agent inbox. Use Refresh to pull the latest snapshot.
            </p>
          </div>
          <div className="flex items-center gap-3">
            {recentError && <span className="text-xs text-red-600">{recentError}</span>}
            <button
              type="button"
              onClick={() => loadRecent()}
              className="text-sm text-blue-600 hover:text-blue-800"
            >
              Refresh
            </button>
          </div>
        </div>
        <div className="overflow-x-auto">
          {loadingRecent ? (
            <div className="px-6 py-6 text-sm text-gray-500">Loading recent triggers…</div>
          ) : recentRows.length === 0 ? (
            <div className="px-6 py-6 text-sm text-gray-500">No trigger events recorded yet.</div>
          ) : (
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <Th>Time</Th>
                  <Th>Type</Th>
                  <Th>Source</Th>
                  <Th>Status</Th>
                  <Th>Payload</Th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 bg-white">
                {recentRows.map(event => (
                  <tr key={event.id ?? `${event.type}-${event.timestamp}-${event.key}`}>
                    <Td className="whitespace-nowrap text-sm text-gray-600">
                      {event.timestamp ? formatTimestamp(event.timestamp) : '—'}
                    </Td>
                    <Td className="whitespace-nowrap text-sm font-medium text-gray-900">{event.type}</Td>
                    <Td className="whitespace-nowrap text-sm text-gray-600">{event.source ?? '—'}</Td>
                    <Td className="whitespace-nowrap text-sm">
                      {event._status ? (
                        <span className={`inline-flex rounded-full px-2 py-1 text-xs ${STATUS_COLORS[event._status] ?? 'bg-gray-100 text-gray-700 border border-gray-200'}`}>
                          {event._status}
                        </span>
                      ) : (
                        <span className="text-gray-400">—</span>
                      )}
                    </Td>
                    <Td className="text-sm text-gray-600">
                      {!event._payloadPreview ? (
                        <span className="text-gray-400">—</span>
                      ) : (
                        <button
                          type="button"
                          className="flex items-center gap-2 text-left text-blue-600 hover:text-blue-800"
                          onClick={() => setPayloadModal(event)}
                        >
                          <span className="truncate">{event._payloadPreview}</span>
                          <span className="text-xs">(view)</span>
                        </button>
                      )}
                    </Td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>

      {payloadModal && (
        <PayloadModal
          event={payloadModal}
          onClose={() => setPayloadModal(null)}
        />
      )}
    </div>
  )
}

function normalizeConfig(config: TriggerConfig | null | undefined): TriggerConfig {
  if (!config) {
    return {
      file_watcher: defaultFileWatcher(),
      calendar: defaultCalendar(),
      telemetry_threshold: defaultTelemetry(),
      conflict_backlog: defaultConflict(),
    }
  }
  return {
    file_watcher: {
      ...defaultFileWatcher(),
      ...config.file_watcher,
      paths: (config.file_watcher?.paths ?? []).length > 0 ? config.file_watcher.paths : defaultFileWatcher().paths,
    },
    calendar: { ...defaultCalendar(), ...config.calendar },
    telemetry_threshold: { ...defaultTelemetry(), ...config.telemetry_threshold },
    conflict_backlog: { ...defaultConflict(), ...config.conflict_backlog },
    updated_at: config.updated_at,
  }
}

function summarizePayload(payload: Record<string, any> | undefined): string {
  if (!payload || Object.keys(payload).length === 0) return ''
  try {
    const serialized = JSON.stringify(payload)
    if (serialized.length <= 72) return serialized
    return `${serialized.slice(0, 69)}…`
  } catch {
    return String(payload)
  }
}

function formatTimestamp(input: string): string {
  const date = new Date(input)
  if (Number.isNaN(date.getTime())) return input
  return date.toLocaleString()
}

function Skeleton() {
  return (
    <div className="space-y-3">
      <div className="h-4 w-32 animate-pulse rounded bg-gray-200" />
      <div className="h-20 animate-pulse rounded bg-gray-100" />
      <div className="h-4 w-24 animate-pulse rounded bg-gray-200" />
    </div>
  )
}

function Card({
  title,
  description,
  children,
}: {
  title: string
  description: string
  children: ReactNode
}) {
  return (
    <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 shadow-sm">
      <h3 className="text-sm font-semibold text-gray-900">{title}</h3>
      <p className="mt-1 text-xs text-gray-600">{description}</p>
      <div className="mt-4 space-y-3">{children}</div>
    </div>
  )
}

function NumberInput({
  label,
  value,
  onChange,
  min,
  max,
  step = 1,
  className = '',
}: {
  label: string
  value: number
  onChange: (value: number) => void
  min?: number
  max?: number
  step?: number
  className?: string
}) {
  return (
    <label className={`block text-xs font-semibold uppercase tracking-wide text-gray-500 ${className}`}>
      {label}
      <input
        type="number"
        value={Number.isFinite(value) ? value : 0}
        min={min}
        max={max}
        step={step}
        onChange={event => onChange(Number(event.target.value))}
        className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
      />
    </label>
  )
}

function PayloadModal({ event, onClose }: { event: TriggerEvent; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/50 p-4" role="dialog" aria-modal="true">
      <div className="max-h-[90vh] w-full max-w-2xl overflow-hidden rounded-lg bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Trigger Payload</h3>
            <p className="text-xs text-gray-500">
              {event.type} &middot; {event.timestamp ? formatTimestamp(event.timestamp) : 'No timestamp'}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-sm text-gray-500 hover:text-gray-700"
          >
            Close
          </button>
        </div>
        <div className="max-h-[70vh] overflow-y-auto px-6 py-4">
          <pre className="whitespace-pre-wrap break-words text-sm text-gray-800">
            {JSON.stringify(event.payload ?? {}, null, 2)}
          </pre>
        </div>
      </div>
    </div>
  )
}

function Th({ children }: { children: ReactNode }) {
  return (
    <th scope="col" className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
      {children}
    </th>
  )
}

function Td({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <td className={`px-6 py-4 align-top ${className}`}>{children}</td>
}
