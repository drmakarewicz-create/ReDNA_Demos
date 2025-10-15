import { useEffect, useMemo, useRef, useState } from 'react'
import clsx from 'clsx'
import { toast } from 'react-toastify'

import stackApi, {
  ChangePortResponse,
  DiagnoseResponse,
  LogsResponse,
  RestartResponse,
  SelfTestResult,
  StackServiceKey,
} from '@/lib/stackApi'

interface TroubleshooterProps {
  service: StackServiceKey
  onClose: () => void
  onSuccess?: () => void
}

type StepKey = 1 | 2 | 3 | 4
type StepState = 'pending' | 'active' | 'done'
type LogLevel = 'ALL' | 'INFO' | 'WARN' | 'ERROR'

const STEP_LABELS: Record<StepKey, string> = {
  1: 'Diagnose',
  2: 'Restart',
  3: 'Self-Test',
  4: 'Logs',
}

const SERVICE_LABELS: Record<StackServiceKey, string> = {
  core: 'Core API',
  ucnrr: 'UCNRR',
  devx: 'DevX Backend',
}

const LEVEL_OPTIONS: LogLevel[] = ['ALL', 'INFO', 'WARN', 'ERROR']

export default function Troubleshooter({ service, onClose, onSuccess }: TroubleshooterProps) {
  const [activeStep, setActiveStep] = useState<StepKey>(1)
  const [diagnostics, setDiagnostics] = useState<DiagnoseResponse | null>(null)
  const [diagnoseLoading, setDiagnoseLoading] = useState(true)
  const [diagnoseError, setDiagnoseError] = useState<string | null>(null)

  const [restartLoading, setRestartLoading] = useState(false)
  const [restartError, setRestartError] = useState<string | null>(null)
  const [restartResult, setRestartResult] = useState<RestartResponse | null>(null)
  const [changeResult, setChangeResult] = useState<ChangePortResponse | null>(null)
  const [startupLogs, setStartupLogs] = useState<Array<Record<string, unknown>>>([])
  const [customPort, setCustomPort] = useState<string>('')

  const [selfTestLoading, setSelfTestLoading] = useState(false)
  const [selfTestError, setSelfTestError] = useState<string | null>(null)
  const [selfTestResult, setSelfTestResult] = useState<SelfTestResult | null>(null)

  const [logsState, setLogsState] = useState<LogsResponse | null>(null)
  const [logsError, setLogsError] = useState<string | null>(null)
  const [logLevel, setLogLevel] = useState<LogLevel>('ALL')
  const [logSearch, setLogSearch] = useState('')
  const logsRef = useRef<HTMLDivElement | null>(null)
  const logsErrorRef = useRef<string | null>(null)

  const currentPort = diagnostics?.port ?? changeResult?.new_port ?? restartResult?.port ?? 0

  useEffect(() => {
    let cancelled = false
    setActiveStep(1)
    setDiagnostics(null)
    setDiagnoseLoading(true)
    setDiagnoseError(null)

    const loadDiagnostics = async () => {
      try {
        const payload = await stackApi.diagnose(service)
        if (!cancelled) {
          setDiagnostics(payload)
          setDiagnoseError(null)
        }
      } catch (error) {
        if (!cancelled) {
          const message = error instanceof Error ? error.message : 'Failed to run diagnostics.'
          setDiagnoseError(message)
          toast.error(message)
        }
      } finally {
        if (!cancelled) {
          setDiagnoseLoading(false)
        }
      }
    }

    loadDiagnostics()
    return () => {
      cancelled = true
    }
  }, [service])

  const handleRestart = async (port: number) => {
    setActiveStep(2)
    setRestartLoading(true)
    setRestartError(null)
    setStartupLogs([])
    setRestartResult(null)
    setChangeResult(null)
    setSelfTestResult(null)
    setSelfTestError(null)

    try {
      const result = await stackApi.restart(service, port)
      setRestartResult(result)
      setStartupLogs(result.startup_logs ?? [])
      setActiveStep(3)
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to restart service.'
      setRestartError(message)
      toast.error(message)
    } finally {
      setRestartLoading(false)
    }
  }

  const handleChangePort = async () => {
    setActiveStep(2)
    setRestartLoading(true)
    setRestartError(null)
    setStartupLogs([])
    setRestartResult(null)
    setSelfTestResult(null)
    setSelfTestError(null)

    try {
      const trimmed = customPort.trim()
      let requestedPort: number | undefined
      if (trimmed) {
        const parsed = Number.parseInt(trimmed, 10)
        if (!Number.isFinite(parsed) || parsed <= 0 || parsed > 65535) {
          throw new Error(`Invalid port: ${trimmed}`)
        }
        requestedPort = parsed
      }
      const result = await stackApi.changePort(service, requestedPort)
      setChangeResult(result)
      setCustomPort(String(result.new_port))
      if (result.status !== 'restarted') {
        throw new Error(`Change port returned status: ${result.status}`)
      }
      setActiveStep(3)
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to reassign port.'
      setRestartError(message)
      toast.error(message)
    } finally {
      setRestartLoading(false)
    }
  }

  useEffect(() => {
    if (activeStep !== 3) return
    if (selfTestLoading || selfTestResult || selfTestError) return

    let cancelled = false
    setSelfTestLoading(true)
    setSelfTestError(null)

    const runSelfTest = async () => {
      try {
        const result = await stackApi.selfTest(service)
        if (!cancelled) {
          setSelfTestResult(result)
          onSuccess?.()
        }
      } catch (error) {
        if (!cancelled) {
          const message = error instanceof Error ? error.message : 'Self-test failed.'
          setSelfTestError(message)
          toast.error(message)
        }
      } finally {
        if (!cancelled) {
          setSelfTestLoading(false)
        }
      }
    }

    runSelfTest()
    return () => {
      cancelled = true
    }
  }, [activeStep, service, selfTestError, selfTestLoading, selfTestResult, onSuccess])

  useEffect(() => {
    if (activeStep !== 4 && !selfTestResult && !selfTestError) return

    let cancelled = false
    let interval: ReturnType<typeof setInterval> | undefined

    const loadLogs = async () => {
      try {
        const response = await stackApi.getLogs(
          service,
          100,
          logLevel === 'ALL' ? undefined : logLevel
        )
        if (!cancelled) {
          setLogsState(response)
          setLogsError(null)
        }
      } catch (error) {
        if (!cancelled) {
          const message = error instanceof Error ? error.message : 'Failed to load logs.'
          setLogsError(message)
          if (logsErrorRef.current !== message) {
            toast.error(message)
            logsErrorRef.current = message
          }
        }
      }
    }

    loadLogs()
    interval = setInterval(loadLogs, 2000)

    return () => {
      cancelled = true
      if (interval) clearInterval(interval)
    }
  }, [activeStep, service, logLevel, selfTestResult, selfTestError])

  useEffect(() => {
    if (!logsError) {
      logsErrorRef.current = null
    }
  }, [logsError])

  useEffect(() => {
    if (!logsState || !logsRef.current) return
    logsRef.current.scrollTop = logsRef.current.scrollHeight
  }, [logsState])

  const filteredLogs = useMemo(() => {
    if (!logsState) return []
    const entries = logsState.lines
    if (!logSearch.trim()) return entries
    const term = logSearch.trim().toLowerCase()
    return entries.filter((entry) => {
      const blob = JSON.stringify(entry, null, 2).toLowerCase()
      return blob.includes(term)
    })
  }, [logsState, logSearch])

  const stepStates: Record<StepKey, StepState> = {
    1: !diagnoseLoading ? 'done' : activeStep === 1 ? 'active' : 'pending',
    2:
      restartLoading || activeStep === 2
        ? 'active'
        : restartResult || changeResult
          ? 'done'
          : 'pending',
    3:
      activeStep === 3 && (selfTestLoading || (!selfTestResult && !selfTestError))
        ? 'active'
        : selfTestResult || selfTestError
          ? 'done'
          : 'pending',
    4: activeStep === 4 ? 'active' : selfTestResult || selfTestError ? 'done' : 'pending',
  }

  const canClose = Boolean(selfTestResult || selfTestError)

  const renderDiagnose = () => (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-slate-900">Step 1: Diagnose</h3>
      {diagnoseLoading && (
        <div className="flex items-center gap-2 rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-500">
          <span className="h-3 w-3 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
          Running diagnostics…
        </div>
      )}
      {diagnoseError && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {diagnoseError}
        </div>
      )}
      {diagnostics && (
        <div className="space-y-3">
          <div className="grid gap-3 md:grid-cols-2">
            <StatusCard
              ok={diagnostics.port_available}
              label={`Port ${diagnostics.port} availability`}
              detail={diagnostics.port_available ? 'Port is available' : 'Port is in use'}
            />
            <StatusCard
              ok={diagnostics.process_running}
              label="Process status"
              detail={
                diagnostics.process_running
                  ? `Process running (PID ${diagnostics.pid ?? 'unknown'})`
                  : 'No active process detected'
              }
            />
            <StatusCard
              ok={diagnostics.log_file_exists}
              label="Log file"
              detail={diagnostics.log_file_exists ? 'Log file present' : 'Log file missing'}
            />
            <StatusCard
              ok={!diagnostics.last_log_entry || diagnostics.last_log_entry.level !== 'ERROR'}
              label="Last log entry"
              detail={
                diagnostics.last_log_entry
                  ? `${diagnostics.last_log_entry.level ?? 'INFO'} — ${diagnostics.last_log_entry.event ?? diagnostics.last_log_entry.message ?? 'entry'}`
                  : 'No logs recorded yet'
              }
            />
          </div>

          {diagnostics.listeners.length > 0 && (
            <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
              <p className="font-medium">Listeners detected on port {diagnostics.port}</p>
              <ul className="mt-2 space-y-1 font-mono text-xs">
                {diagnostics.listeners.map((listener) => (
                  <li key={listener.pid}>
                    PID {listener.pid} — <span className="text-slate-700">{listener.cmd}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <details className="rounded-md border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700">
            <summary className="cursor-pointer font-medium text-slate-900">View diagnostic payload</summary>
            <pre className="mt-3 overflow-auto rounded bg-slate-50 p-3 text-xs text-slate-800">
              {JSON.stringify(diagnostics, null, 2)}
            </pre>
          </details>
        </div>
      )}
      <div className="flex justify-end pt-4">
        <button
          type="button"
          onClick={() => setActiveStep(2)}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-blue-500"
          disabled={diagnoseLoading || !!diagnoseError}
        >
          Continue to Restart
        </button>
      </div>
    </div>
  )

  const renderRestart = () => (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-slate-900">Step 2: Restart Options</h3>
      {restartError && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {restartError}
        </div>
      )}
      <div className="flex flex-col gap-2 rounded-md border border-slate-200 bg-white p-4 text-sm text-slate-600">
        <label className="flex flex-col gap-1">
          <span className="font-medium text-slate-800">Custom Port (optional)</span>
          <input
            type="number"
            min={1}
            max={65535}
            value={customPort}
            onChange={(event) => setCustomPort(event.target.value)}
            className="w-full rounded border border-slate-200 px-2 py-1 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            placeholder="Auto-detect if empty"
            disabled={restartLoading}
          />
        </label>
        <p className="text-xs text-slate-500">
          Leave blank to auto-detect the next available port. Enter a specific port if you need to override.
        </p>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <button
          type="button"
          onClick={() => handleRestart(currentPort)}
          className="flex flex-col rounded-md border border-slate-200 bg-white p-4 text-left shadow-sm hover:border-blue-500 hover:shadow transition"
          disabled={restartLoading || currentPort <= 0}
        >
          <span className="text-sm font-semibold text-slate-900">Kill &amp; Restart on Port {currentPort}</span>
          <span className="mt-2 text-xs text-slate-600">
            Terminates any running process and starts a fresh instance on port {currentPort}.
          </span>
        </button>
        <button
          type="button"
          onClick={handleChangePort}
          className="flex flex-col rounded-md border border-slate-200 bg-white p-4 text-left shadow-sm hover:border-blue-500 hover:shadow transition"
          disabled={restartLoading}
        >
          <span className="text-sm font-semibold text-slate-900">Choose Different Port</span>
          <span className="mt-2 text-xs text-slate-600">
            Automatically selects the next available port and restarts the service using the new configuration.
          </span>
        </button>
      </div>
      {restartLoading && (
        <div className="flex items-center gap-2 rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-500">
          <span className="h-3 w-3 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
          Restarting service…
        </div>
      )}
      {restartResult && (
        <div className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          <p className="font-medium">Service restarted on port {restartResult.port}</p>
          <p>Health check {restartResult.health_check === 'passed' ? 'passed ✅' : 'failed ⚠️'}</p>
          {startupLogs.length > 0 && (
            <details className="mt-3">
              <summary className="cursor-pointer font-medium text-emerald-900">View startup logs</summary>
              <pre className="mt-2 max-h-48 overflow-auto rounded bg-white p-3 text-xs text-slate-700">
                {JSON.stringify(startupLogs, null, 2)}
              </pre>
            </details>
          )}
        </div>
      )}
      {changeResult && (
        <div className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          <p className="font-medium">
            Port reassigned: {changeResult.old_port} → {changeResult.new_port}
          </p>
          <p>Status: {changeResult.status === 'restarted' ? 'Service restarted successfully.' : 'Restart failed.'}</p>
        </div>
      )}
      <div className="flex justify-end pt-4">
        <button
          type="button"
          onClick={() => setActiveStep(3)}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-blue-500"
          disabled={restartLoading || (!restartResult && !changeResult)}
        >
          Continue to Self-Test
        </button>
      </div>
    </div>
  )

  const renderSelfTest = () => (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-slate-900">Step 3: Automated Self-Test</h3>
      {selfTestLoading && (
        <div className="flex items-center gap-2 rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-500">
          <span className="h-3 w-3 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
          Running self-test…
        </div>
      )}
      {selfTestError && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {selfTestError}
        </div>
      )}
      {selfTestResult && (
        <div className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          <p className="font-medium">
            {selfTestResult.passed ? '✅ Self-test passed' : '⚠️ Self-test detected issues'}
          </p>
          <p className="text-xs text-emerald-900">Test: {selfTestResult.test}</p>
          <details className="mt-3">
            <summary className="cursor-pointer font-medium text-emerald-900">View self-test details</summary>
            <pre className="mt-2 max-h-48 overflow-auto rounded bg-white p-3 text-xs text-slate-700">
              {JSON.stringify(selfTestResult.details, null, 2)}
            </pre>
          </details>
        </div>
      )}
      <div className="flex justify-end pt-4">
        <button
          type="button"
          onClick={() => setActiveStep(4)}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-blue-500"
          disabled={!selfTestResult && !selfTestError}
        >
          Continue to Logs
        </button>
      </div>
    </div>
  )

  const renderLogs = () => (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-slate-900">Step 4: Log Viewer</h3>
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <label className="flex items-center gap-2">
          Level
          <select
            value={logLevel}
            onChange={(event) => setLogLevel(event.target.value as LogLevel)}
            className="rounded border border-slate-200 px-2 py-1 text-sm"
          >
            {LEVEL_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-1 items-center gap-2 min-w-[200px]">
          Search
          <input
            type="text"
            value={logSearch}
            onChange={(event) => setLogSearch(event.target.value)}
            className="flex-1 rounded border border-slate-200 px-2 py-1 text-sm"
            placeholder="Filter text…"
          />
        </label>
        <span className="text-xs text-slate-500">
          {logsState ? `${filteredLogs.length} / ${logsState.total_lines} entries` : 'No logs'}
        </span>
      </div>
      {logsError && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {logsError}
        </div>
      )}
      <div
        ref={logsRef}
        className="max-h-[360px] overflow-y-auto rounded-md border border-slate-200 bg-slate-50 p-3 text-xs leading-relaxed text-slate-800"
      >
        {filteredLogs.map((entry, index) => (
          <div key={index} className="mb-2 whitespace-pre-wrap">
            <span className="font-mono text-slate-500">{entry.ts ?? '—'}</span>
            <span className="mx-2 rounded bg-slate-200 px-1 py-0.5 font-medium uppercase text-slate-600">
              {entry.level ?? 'n/a'}
            </span>
            <span className="font-medium text-slate-700">{entry.event ?? entry.message ?? '—'}</span>
            {entry.raw && <div className="text-slate-600">{entry.raw}</div>}
            {entry.rest && Object.keys(entry.rest).length > 0 && (
              <pre className="mt-1 overflow-x-auto rounded bg-white/70 p-2 text-[11px] text-slate-600 shadow-inner">
                {JSON.stringify(entry.rest, null, 2)}
              </pre>
            )}
          </div>
        ))}
        {filteredLogs.length === 0 && (
          <p className="text-slate-500">No log entries match the current filters.</p>
        )}
      </div>
    </div>
  )

  const renderStepContent = () => {
    if (activeStep === 1) return renderDiagnose()
    if (activeStep === 2) return renderRestart()
    if (activeStep === 3) return renderSelfTest()
    return renderLogs()
  }

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 p-4">
      <div className="flex h-full w-full max-w-6xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl md:flex-row">
        <aside className="w-full border-b border-slate-200 bg-slate-50 p-4 md:w-60 md:border-b-0 md:border-r">
          <div className="mb-4">
            <h2 className="text-lg font-semibold text-slate-900">Troubleshooter</h2>
            <p className="text-xs text-slate-500">{SERVICE_LABELS[service]}</p>
          </div>
          <ol className="space-y-3 text-sm">
            {(Object.keys(STEP_LABELS) as unknown as StepKey[]).map((step) => (
              <li key={step}>
                <button
                  type="button"
                  onClick={() => setActiveStep(step)}
                  className={clsx(
                    'flex w-full items-center gap-2 rounded-md px-3 py-2 text-left transition',
                    stepStates[step] === 'active' && 'bg-blue-100 text-blue-700',
                    stepStates[step] === 'done' && 'text-emerald-600 hover:bg-emerald-50',
                    stepStates[step] === 'pending' && 'text-slate-500 hover:bg-slate-100'
                  )}
                >
                  <span className="inline-flex h-5 w-5 items-center justify-center rounded-full border text-xs">
                    {stepStates[step] === 'done' ? '✓' : step}
                  </span>
                  <span>{STEP_LABELS[step]}</span>
                </button>
              </li>
            ))}
          </ol>
        </aside>
        <main className="flex-1 overflow-y-auto p-6 text-sm text-slate-700">{renderStepContent()}</main>
        <footer className="flex items-center justify-between border-t border-slate-200 bg-white px-4 py-3 text-sm text-slate-600 md:flex-col md:items-stretch md:gap-3 md:border-l md:border-t-0 md:px-6 md:py-4">
          <div className="text-xs text-slate-500 md:text-sm">
            Close enabled after self-test completes.
          </div>
          <div className="flex items-center gap-2 md:flex-col md:items-stretch">
            <button
              type="button"
              onClick={onClose}
              className={clsx(
                'rounded-md px-3 py-2 text-sm font-medium shadow-sm',
                canClose
                  ? 'bg-emerald-600 text-white hover:bg-emerald-500'
                  : 'bg-slate-200 text-slate-500 cursor-not-allowed'
              )}
              disabled={!canClose}
            >
              Close
            </button>
            <button
              type="button"
              onClick={onClose}
              className="text-xs text-slate-400 underline-offset-2 hover:underline"
            >
              Force close
            </button>
          </div>
        </footer>
      </div>
    </div>
  )
}

interface StatusCardProps {
  ok: boolean
  label: string
  detail: string
}

function StatusCard({ ok, label, detail }: StatusCardProps) {
  return (
    <div
      className={clsx(
        'rounded-md border px-3 py-2 text-sm shadow-sm',
        ok ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : 'border-red-200 bg-red-50 text-red-800'
      )}
    >
      <p className="font-medium">{ok ? '✅' : '⚠️'} {label}</p>
      <p className="mt-1 text-xs">{detail}</p>
    </div>
  )
}
