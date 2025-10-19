import { devxUrl } from './env'

const STACK_ROOT = devxUrl('/stack')

async function handleJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const text = await response.text()
    throw new Error(text || `Stack API error (${response.status})`)
  }
  return response.json() as Promise<T>
}

export type StackServiceKey = 'core' | 'ucnrr' | 'devx'

export interface StackServiceStatus {
  service: StackServiceKey
  status: 'healthy' | 'degraded' | 'down'
  port: number
  health?: Record<string, unknown>
  error?: string
  last_check: string
  version?: string | null
  python?: string | null
}

export interface StackStatusResponse {
  services: StackServiceStatus[]
  timestamp: string
}

export interface RecoverySuggestion {
  service: 'core' | 'ucnrr'
  action: string
  reason: string
}

export interface RateLimitStatus {
  rate_limited: boolean
  recent_restarts: number
  remaining: number
}

export interface StackReadyResponse {
  ready: boolean
  status: 'ready' | 'warming' | 'unready'
  reasons: string[]
  fail_conditions: string[]
  recovery_suggestions: RecoverySuggestion[]
  checked_at: string
  unready_since?: string | null
  rolling_window_sec: number
  error_rate_5m?: number | null
  p95_latency_ms_5m?: number | null
  failures_by_service: Record<string, string[]>
  rate_limit: Record<string, RateLimitStatus>
}

export interface DiagnoseResponse {
  service: StackServiceKey
  port: number
  port_available: boolean
  listeners: Array<{ pid: number; cmd: string }>
  process_running: boolean
  pid?: number | null
  log_file_exists: boolean
  last_log_entry?: Record<string, unknown> | null
}

export interface RestartResponse {
  service: StackServiceKey
  status: 'started' | 'failed'
  port: number
  pid?: number | null
  health_check: 'passed' | 'failed'
  startup_logs: Array<Record<string, unknown>>
  last_health?: Record<string, unknown> | null
}

export interface ChangePortResponse {
  service: StackServiceKey
  old_port: number
  new_port: number
  status: 'restarted' | 'error'
  config_updated: boolean
}

export interface RestartAction {
  service: 'core' | 'ucnrr'
  status: 'restarted' | 'skipped' | 'rate_limited' | 'unknown_service' | 'not_eligible'
  pid?: number | null
}

export interface SupervisorRestartRequest {
  services: Array<'core' | 'ucnrr'>
  reason: string
  force?: boolean
}

export interface SupervisorRestartResponse {
  force: boolean
  reason: string
  grace_seconds: number
  requested: Array<'core' | 'ucnrr'>
  eligible: Array<'core' | 'ucnrr'>
  restarted: RestartAction[]
  skipped: RestartAction[]
  rate_limited: RestartAction[]
  history: Array<Record<string, unknown>>
}

export interface RestartHistoryResponse {
  history: Array<Record<string, unknown>>
}

export interface SelfTestResult {
  service: StackServiceKey
  test: string
  passed: boolean
  details: Record<string, unknown>
}

export interface LogEntry {
  ts?: string | null
  level?: string | null
  event?: string | null
  message?: string | null
  raw?: string | null
  rest: Record<string, unknown>
}

export interface LogsResponse {
  service: StackServiceKey
  log_file: string
  total_lines: number
  lines: LogEntry[]
}

export const stackApi = {
  async getStatus(): Promise<StackStatusResponse> {
    const response = await fetch(`${STACK_ROOT}/status`)
    return handleJson<StackStatusResponse>(response)
  },

  async getReady(): Promise<StackReadyResponse> {
    const response = await fetch(`${STACK_ROOT}/ready`)
    return handleJson<StackReadyResponse>(response)
  },

  async diagnose(service: StackServiceKey): Promise<DiagnoseResponse> {
    const response = await fetch(`${STACK_ROOT}/diagnose`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ service }),
    })
    return handleJson<DiagnoseResponse>(response)
  },

  async restart(service: StackServiceKey, port: number): Promise<RestartResponse> {
    const response = await fetch(`${STACK_ROOT}/restart`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ service, port }),
    })
    return handleJson<RestartResponse>(response)
  },

  async changePort(service: StackServiceKey, newPort?: number): Promise<ChangePortResponse> {
    const response = await fetch(`${STACK_ROOT}/change_port`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ service, new_port: newPort }),
    })
    return handleJson<ChangePortResponse>(response)
  },

  async selfTest(service: StackServiceKey): Promise<SelfTestResult> {
    const response = await fetch(`${STACK_ROOT}/selftest/${service}`)
    return handleJson<SelfTestResult>(response)
  },

  async restartServices(body: SupervisorRestartRequest): Promise<SupervisorRestartResponse> {
    const response = await fetch(`${STACK_ROOT}/restart`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    return handleJson<SupervisorRestartResponse>(response)
  },

  async getLogs(service: StackServiceKey, lines = 100, level?: string): Promise<LogsResponse> {
    const params = new URLSearchParams({ lines: String(lines) })
    if (level) params.set('level', level)
    const response = await fetch(`${STACK_ROOT}/logs/${service}?${params.toString()}`)
    return handleJson<LogsResponse>(response)
  },

  async getRestartHistory(limit = 50): Promise<RestartHistoryResponse> {
    const params = new URLSearchParams({ limit: String(limit) })
    const response = await fetch(`${STACK_ROOT}/restart/history?${params.toString()}`)
    return handleJson<RestartHistoryResponse>(response)
  },
}

/**
 * Guardrail helpers for other DevX surfaces that initiate ingestion / chat flows.
 * Future work: wire these into chat send + ingest buttons to disable when Core is unhealthy.
 */
export const stackStatusGuards = {
  isCoreOnline(status?: StackServiceStatus): boolean {
    if (!status) return false
    if (status.status !== 'healthy') return false
    const rrMode =
      status.health && typeof status.health === 'object' && 'rr_mode' in status.health
        ? String((status.health as Record<string, unknown>)['rr_mode'] ?? '')
        : null
    return !rrMode || rrMode.toLowerCase() === 'online'
  },
}

export default stackApi
