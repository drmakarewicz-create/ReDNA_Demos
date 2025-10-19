import { DEVX_API_BASE } from './env'
import { authorizedFetch } from './capabilityClient'
import type { AutonomyLevel } from './agentApi'
import type { HolisticResult, HolisticHistoryEntry as CoreHolisticHistoryEntry } from './holisticApi'

const API_ROOT = `${DEVX_API_BASE}/users`

async function handleResponse(response: Response) {
  if (!response.ok) {
    const text = await response.text()
    throw new Error(text || `UserOps API error (${response.status})`)
  }
  return response.json()
}

export interface UserListItem {
  user_id: string
  has_vault: boolean
  last_updated?: string | null
  size_bytes: number
  quarantine_status?: string | null
  review_until?: string | null
}

export interface ListUsersResponse {
  users: UserListItem[]
  total: number
}

export interface UserSummary {
  user_id: string
  counts: {
    evidence: number
    derived: number
    containers: number
  }
  last_updated?: string | null
  size_bytes: number
}

export interface DryRunEntry {
  user_id: string
  bytes_to_quarantine?: number
  vault_paths?: string[]
  capability_count?: number | null
  warnings?: string[]
  has_open_tickets?: boolean
  error?: string
}

export interface DryRunResponse {
  users: Record<string, DryRunEntry>
  totals: {
    bytes_to_quarantine: number
    users: number
  }
}

export interface DeletePayload {
  user_ids: string[]
  reason: string
  grace_days: number
  confirm: string
}

export interface BatchDeleteResponse {
  job_id: string
  accepted: string[]
  errors: { user_id: string; message: string }[]
}

export interface JobStatusUserEntry {
  status: string
  warnings?: string[]
  errors?: string[]
  review_until?: string
  restored_at?: string
  purged_at?: string
  quarantine_path?: string
}

export interface JobStatusResponse {
  job_id: string
  action: string
  created_at: string
  users: Record<string, JobStatusUserEntry>
}

export interface UndoPayload {
  job_id: string
  user_ids: string[]
  confirm: string
}

export interface UndoResponse {
  job_id: string
  restored: string[]
  errors: { user_id: string; message: string }[]
}

export interface PurgePayload {
  user_ids: string[]
  confirm: string
}

export interface PurgeResponse {
  purged: string[]
  errors: { user_id: string; message: string }[]
}

export interface RevokeCapsResult {
  user_id: string
  revoked: number
  warnings?: string[]
}

export interface RevokeCapsResponse {
  job_id: string
  status: string
  total_revoked: number
  results: RevokeCapsResult[]
}

export interface ExportResultEntry {
  user_id: string
  status: string
  download?: string
  reason?: string
}

export interface ExportBatchResponse {
  ts: string
  results: ExportResultEntry[]
}

export interface HolisticHistoryEntry extends CoreHolisticHistoryEntry {
  path: string
  size_bytes?: number | null
}

export interface HolisticLatestResponse {
  user_id: string
  latest: HolisticResult | null
  history: HolisticHistoryEntry[]
  history_limit: number
}

export interface PermissionScopeEntry {
  granted_at: string
  expiry?: string
  [key: string]: any
}

export interface CapabilityTokenRecord {
  capability_id: string
  scope: string
  status: string
  issued_at?: string
  expires_at?: string
  token?: string
  ttl_minutes?: number
  [key: string]: any
}

export interface UserPermissionsResponse {
  user_id: string
  namespaces: Record<string, Record<string, PermissionScopeEntry>>
  capabilities: {
    local: CapabilityTokenRecord[]
    consent: any[]
    consent_error?: string | null
  }
}

export interface RenameResponse {
  status: string
  from: string
  to: string
  summary: Record<string, unknown>
}

export interface RenamePayload {
  new_user_id: string
  reason?: string
  confirm?: string
}

export interface GrantPermissionPayload {
  namespace: string
  scope: string
  expiry?: string
}

export interface RevokePermissionPayload {
  namespace?: string
  scope?: string
  capability_id?: string
}

export interface IssueCapabilityPayload {
  scope: string
  ttl_minutes: number
}

export interface ConfigureAgentPayload {
  level: number
  apply_defaults?: boolean
  confirm?: string
}

export interface ConfigureAgentResponse {
  ok: boolean
  user_id: string
  agent_id: string
  agent_level: number
  policy: {
    autonomy: AutonomyLevel | null
    quotas: Record<string, number>
    features?: Record<string, any>
    permissions?: Record<string, any>
  }
  schedule: Record<string, any>
  quotas: Record<string, number>
  capabilities: {
    issued: CapabilityTokenRecord[]
    revoked: CapabilityTokenRecord[]
  }
  rsc_enabled: boolean
  workflow_toggles?: Record<string, boolean>
  audit_id: string
  archived_state?: string | null
}

export interface TriggerFileWatcherConfig {
  enabled: boolean
  paths: string[]
  dedupe_minutes: number
  max_events_per_minute: number
}

export interface TriggerCalendarConfig {
  enabled: boolean
  shared_secret?: string | null
  lead_minutes: number
  max_events_per_day: number
}

export interface TriggerTelemetryConfig {
  enabled: boolean
  event_count: number
  window_hours: number
  sentiment_threshold: number
  max_events_per_day: number
}

export interface TriggerConflictConfig {
  enabled: boolean
  threshold: number
  max_events_per_day: number
}

export interface TriggerConfig {
  file_watcher: TriggerFileWatcherConfig
  calendar: TriggerCalendarConfig
  telemetry_threshold: TriggerTelemetryConfig
  conflict_backlog: TriggerConflictConfig
  updated_at?: string
}

export interface TriggerEvent {
  id?: string
  type: string
  source?: string
  key?: string
  timestamp?: string
  payload?: Record<string, any>
  [key: string]: any
}

export interface DeleteUserPayload {
  mode?: 'retire' | 'purge'
  confirm: string
  reason?: string
  grace_days?: number
}

export interface DeleteUserResponse {
  status: string
  user_id: string
  [key: string]: any
}

export interface AuditEntry {
  event: string
  timestamp: string
  [key: string]: any
}

export interface AuditLogResponse {
  user_id: string
  entries: AuditEntry[]
  limit: number
}

export const userOpsApi = {
  async listUsers(
    params: { query?: string; limit?: number; offset?: number; includeSynthetic?: boolean } = {},
  ): Promise<ListUsersResponse> {
    const query = new URLSearchParams()
    if (params.query) query.append('query', params.query)
    if (params.limit !== undefined) query.append('limit', String(params.limit))
    if (params.offset !== undefined) query.append('offset', String(params.offset))
    if (params.includeSynthetic) query.append('include_synthetic', '1')
    const response = await fetch(`${API_ROOT}/list?${query.toString()}`)
    return handleResponse(response)
  },

  async getUserSummary(user_id: string): Promise<UserSummary> {
    const response = await fetch(`${API_ROOT}/summary?user_id=${encodeURIComponent(user_id)}`)
    return handleResponse(response)
  },

  async dryRunDelete(user_ids: string[]): Promise<DryRunResponse> {
    const response = await fetch(`${API_ROOT}/batch/dry-run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_ids }),
    })
    return handleResponse(response)
  },

  async submitDelete(payload: DeletePayload): Promise<BatchDeleteResponse> {
    const response = await fetch(`${API_ROOT}/batch/delete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    return handleResponse(response)
  },

  async jobStatus(job_id: string): Promise<JobStatusResponse> {
    const response = await fetch(`${API_ROOT}/batch/status?job_id=${encodeURIComponent(job_id)}`)
    return handleResponse(response)
  },

  async undoDelete(payload: UndoPayload): Promise<UndoResponse> {
    const response = await fetch(`${API_ROOT}/batch/undo`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    return handleResponse(response)
  },

  async purgeUsers(payload: PurgePayload): Promise<PurgeResponse> {
    const response = await fetch(`${API_ROOT}/batch/purge`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    return handleResponse(response)
  },

  async runHolistic(userIds: string[], reason?: string): Promise<{ job_id: string; status: string; count: number }> {
    const body: Record<string, any> = { user_ids: userIds }
    if (reason && reason.trim().length > 0) {
      body.reason = reason.trim()
    }
    const response = await fetch(`${API_ROOT}/batch/run-holistic`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    return handleResponse(response)
  },

  async runHolisticForUser(userId: string, reason?: string): Promise<{ job_id: string; status: string; count: number; user_id: string }> {
    const payload = reason && reason.trim().length > 0 ? { reason: reason.trim() } : {}
    const response = await fetch(`${API_ROOT}/${encodeURIComponent(userId)}/holistic/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    return handleResponse(response)
  },

  async getHolisticLatest(userId: string, limit = 5): Promise<HolisticLatestResponse> {
    const response = await fetch(
      `${API_ROOT}/${encodeURIComponent(userId)}/holistic/latest?history_limit=${limit}`
    )
    return handleResponse(response)
  },

  async renameUser(userId: string, payload: RenamePayload): Promise<RenameResponse> {
    const response = await fetch(`${API_ROOT}/${encodeURIComponent(userId)}/rename`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    return handleResponse(response)
  },

  async deleteUser(userId: string, payload: DeleteUserPayload): Promise<DeleteUserResponse> {
    const response = await fetch(`${API_ROOT}/${encodeURIComponent(userId)}`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    return handleResponse(response)
  },

  async getAudit(userId: string, limit = 10): Promise<AuditLogResponse> {
    const response = await fetch(
      `${API_ROOT}/${encodeURIComponent(userId)}/audit?limit=${limit}`
    )
    return handleResponse(response)
  },

  async configureAgent(userId: string, payload: ConfigureAgentPayload): Promise<ConfigureAgentResponse> {
    const response = await fetch(`${API_ROOT}/${encodeURIComponent(userId)}/agent/configure`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    return handleResponse(response)
  },

  async getTriggerConfig(userId: string): Promise<TriggerConfig> {
    const response = await authorizedFetch(
      userId,
      'core.agent.config',
      `${API_ROOT}/${encodeURIComponent(userId)}/triggers/config`
    )
    const payload = await handleResponse(response)
    return payload.config as TriggerConfig
  },

  async saveTriggerConfig(userId: string, config: TriggerConfig): Promise<{ ok: boolean }> {
    const response = await authorizedFetch(
      userId,
      'core.agent.config',
      `${API_ROOT}/${encodeURIComponent(userId)}/triggers/config`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          file_watcher: config.file_watcher,
          calendar: config.calendar,
          telemetry_threshold: config.telemetry_threshold,
          conflict_backlog: config.conflict_backlog,
        }),
      }
    )
    return handleResponse(response)
  },

  async sendTestTrigger(userId: string, type: string, payload?: any): Promise<{ ok: boolean; event?: TriggerEvent }> {
    const response = await authorizedFetch(
      userId,
      'core.agent.config',
      `${API_ROOT}/${encodeURIComponent(userId)}/triggers/test`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type, payload }),
      }
    )
    return handleResponse(response)
  },

  async getRecentTriggers(userId: string, limit = 20): Promise<TriggerEvent[]> {
    const response = await authorizedFetch(
      userId,
      'core.agent.config',
      `${API_ROOT}/${encodeURIComponent(userId)}/triggers/recent?limit=${encodeURIComponent(String(limit))}`
    )
    const payload = await handleResponse(response)
    return payload.events as TriggerEvent[]
  },

  async getPermissions(userId: string): Promise<UserPermissionsResponse> {
    const response = await fetch(`${API_ROOT}/${encodeURIComponent(userId)}/permissions`)
    return handleResponse(response)
  },

  async grantPermission(userId: string, payload: GrantPermissionPayload): Promise<any> {
    const response = await authorizedFetch(
      userId,
      'core.agent.config',
      `${API_ROOT}/${encodeURIComponent(userId)}/permissions/grant`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      }
    )
    return handleResponse(response)
  },

  async revokePermission(userId: string, payload: RevokePermissionPayload): Promise<any> {
    const response = await authorizedFetch(
      userId,
      'core.agent.config',
      `${API_ROOT}/${encodeURIComponent(userId)}/permissions/revoke`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      }
    )
    return handleResponse(response)
  },

  async issueCapability(userId: string, payload: IssueCapabilityPayload): Promise<CapabilityTokenRecord> {
    const response = await authorizedFetch(
      userId,
      'core.agent.config',
      `${API_ROOT}/${encodeURIComponent(userId)}/capability/issue`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      }
    )
    return handleResponse(response)
  },

  async revokeCapability(userId: string, capabilityId: string): Promise<any> {
    const response = await authorizedFetch(
      userId,
      'core.agent.config',
      `${API_ROOT}/${encodeURIComponent(userId)}/capability/revoke`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ capability_id: capabilityId }),
      }
    )
    return handleResponse(response)
  },

  async revokeCaps(userIds: string[], reason?: string): Promise<RevokeCapsResponse> {
    const response = await fetch(`${API_ROOT}/batch/revoke-caps`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_ids: userIds, reason }),
    })
    return handleResponse(response)
  },

  async exportUsers(userIds: string[]): Promise<ExportBatchResponse> {
    const response = await fetch(`/devx/api/privacy/export-json-batch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_ids: userIds }),
    })
    return handleResponse(response)
  },
}

export default userOpsApi
