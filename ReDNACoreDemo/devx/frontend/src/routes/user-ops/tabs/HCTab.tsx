import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'react-toastify'

import AgentControlPanel from '@/routes/agent-control/AgentControlPanel'
import RSCConsole from '@/routes/agent-control/RSCConsole'
import AgentAuditTail from '@/components/AgentAuditTail'
import LifeOSPane from '@/components/LifeOSPane'
import LearningPanel from '@/components/LearningPanel'
import AutonomyPanel from '@/components/AutonomyPanel'
import { agentApi, AgentDetail } from '@/lib/agentApi'
import userOpsApi, { ConfigureAgentPayload, ConfigureAgentResponse } from '@/lib/userOpsApi'
import { FEATURE_FLAGS } from '@/lib/featureFlags'
import CapabilityTokenModal from '@/routes/coach-workshop/components/CapabilityTokenModal'

interface HCTabProps {
  userId: string
}

interface LevelOption {
  level: number
  name: string
  summary: string
}

const LEVEL_OPTIONS: LevelOption[] = [
  { level: 0, name: 'Manual', summary: 'Agent disabled; manual Head Coach only.' },
  { level: 1, name: 'Background', summary: 'Agent proposes every 12h; 10 jobs/day limit.' },
  { level: 2, name: 'Autonomous', summary: 'Auto execution every 4h; 50 jobs/day; auto-apply trivial improvements.' },
  { level: 3, name: 'Collaborative', summary: 'Autonomous + RSC messaging enabled for operators.' },
  { level: 4, name: 'Delegated', summary: 'Collaborative + workflow drafts, 2h cadence, circuit breaker safeguards.' },
]

function inferAgencyLevel(detail: AgentDetail | null): number {
  if (!detail) return 0
  const metadata = detail.record.metadata || {}
  if (typeof metadata.agency_level === 'number') {
    return metadata.agency_level
  }
  if (metadata.workflow_toggles?.calendar) return 4
  if (metadata.rsc_enabled) return 3
  if (detail.policy.autonomy === 'auto' || detail.record.autonomy === 'auto') return 2
  if (detail.record.status === 'disabled' || detail.policy.autonomy === null || detail.record.autonomy === 'manual') {
    return 0
  }
  return 1
}

function formatInterval(hours?: number): string {
  if (!hours || Number.isNaN(hours)) return '—'
  if (hours < 1) {
    const minutes = Math.round(hours * 60)
    return `${minutes} min`
  }
  return `${hours} h`
}

function formatList(values?: string[]): string {
  if (!values || values.length === 0) return '—'
  return values.join(', ')
}

export default function HCTab({ userId }: HCTabProps) {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [detail, setDetail] = useState<AgentDetail | null>(null)
  const [level, setLevel] = useState(0)
  const [latestConfig, setLatestConfig] = useState<ConfigureAgentResponse | null>(null)
  const [isSaving, setIsSaving] = useState(false)
  const [panelKey, setPanelKey] = useState(0)
  const [pendingDowngrade, setPendingDowngrade] = useState<number | null>(null)
  const [capModalOpen, setCapModalOpen] = useState(false)

  const showCapabilityModal = (import.meta as any)?.env?.VITE_DEVX_SHOW_CAP_MODAL === 'true'

  const loadAgent = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const payload = await agentApi.getAgent(userId)
      setDetail(payload)
      setLevel(inferAgencyLevel(payload))
      setLatestConfig(null)
    } catch (err) {
      if (err instanceof Error && err.message.includes('Agent not found')) {
        setDetail(null)
        setLevel(0)
        setLatestConfig(null)
      } else {
        const message = err instanceof Error ? err.message : 'Failed to load agent.'
        setError(message)
      }
    } finally {
      setLoading(false)
    }
  }, [userId])

  useEffect(() => {
    loadAgent()
  }, [loadAgent])

  const configSummary: ConfigureAgentResponse | null = useMemo(() => {
    if (latestConfig) return latestConfig
    if (!detail) return null
    const metadata = detail.record.metadata ?? {}
    return {
      ok: true,
      user_id: detail.record.user_id,
      agent_id: detail.record.agent_id,
      agent_level: inferAgencyLevel(detail),
      policy: {
        autonomy: detail.policy.autonomy,
        quotas: detail.policy.quotas,
        features: detail.policy.features,
        permissions: detail.policy.permissions,
      },
      schedule: metadata.schedule ?? {},
      quotas: detail.policy.quotas,
      capabilities: { issued: [], revoked: [] },
      rsc_enabled: Boolean(metadata.rsc_enabled),
      workflow_toggles: metadata.workflow_toggles ?? {},
      audit_id: metadata.preset_audit_id ?? '',
      archived_state: metadata.last_archived_state,
    }
  }, [detail, latestConfig])

  const handleConfigure = useCallback(
    async (targetLevel: number, options: { force?: boolean; confirm?: boolean; applyDefaults?: boolean } = {}) => {
      if (!options.force && targetLevel === level) return
      if (isSaving) return

      const isDowngrade = targetLevel < level
      if (isDowngrade && !options.confirm) {
        setPendingDowngrade(targetLevel)
        return
      }

      setError(null)
      setIsSaving(true)
      setPendingDowngrade(null)

      const payload: ConfigureAgentPayload = {
        level: targetLevel,
        apply_defaults: options.applyDefaults ?? true,
      }
      if (isDowngrade) {
        payload.confirm = 'apply'
      }

      try {
        const response = await userOpsApi.configureAgent(userId, payload)
        setLatestConfig(response)
        setLevel(response.agent_level)
        toast.success(`Agency level set to L${response.agent_level} · ${LEVEL_OPTIONS.find(opt => opt.level === response.agent_level)?.name ?? ''}`)
        const refreshed = await agentApi.getAgent(userId).catch(() => null)
        if (refreshed) {
          setDetail(refreshed)
        }
        setPanelKey(prev => prev + 1)
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Configuration failed.'
        toast.error(message)
        setError(message)
      } finally {
        setIsSaving(false)
      }
    },
    [isSaving, level, userId]
  )

  const sensitiveScopes = useMemo(() => {
    if (configSummary?.policy.permissions?.sensitive) {
      return configSummary.policy.permissions.sensitive
    }
    return detail?.policy.permissions?.sensitive
  }, [configSummary, detail])

  const issuedScopes = (configSummary?.capabilities.issued ?? []).map(entry => entry.scope)
  const scheduleHours =
    typeof configSummary?.schedule?.interval_hours === 'number'
      ? configSummary?.schedule?.interval_hours
      : detail?.record.metadata?.schedule?.interval_hours

  const workflowToggles = configSummary?.workflow_toggles ?? {}
  const isManual = level === 0

  return (
    <div className="space-y-6">
      {loading && (
        <div className="rounded-md border border-gray-200 bg-white px-6 py-10 text-center text-sm text-gray-500">
          Loading Head Coach configuration…
        </div>
      )}

      {!loading && error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
      )}

      {!loading && !error && (
        <>
          <section className="rounded-lg border border-gray-200 bg-white shadow-sm">
            <div className="flex flex-col gap-4 border-b border-gray-200 px-6 py-5 md:flex-row md:items-center md:justify-between">
              <div>
                <h2 className="text-lg font-semibold text-gray-900">Agency Level</h2>
                <p className="text-sm text-gray-600">
                  Choose the automation envelope for the user’s Head Coach agent. Changes apply immediately and are
                  fully audited.
                </p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  className="rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-700 hover:bg-gray-100 disabled:opacity-60"
                  disabled={isSaving}
                  onClick={() => handleConfigure(level, { force: true, applyDefaults: true })}
                >
                  Apply level defaults
                </button>
                <button
                  className="rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-700 hover:bg-gray-100 disabled:opacity-60"
                  onClick={() => navigate('../permissions')}
                >
                  View permissions
                </button>
              </div>
            </div>
            <div className="grid gap-3 px-6 py-5 md:grid-cols-5">
              {LEVEL_OPTIONS.map(option => {
                const isActive = option.level === level
                return (
                  <button
                    key={option.level}
                    type="button"
                    disabled={isSaving}
                    onClick={() => handleConfigure(option.level)}
                    className={[
                      'flex flex-col gap-2 rounded-lg border px-4 py-4 text-left transition focus:outline-none focus:ring-2 focus:ring-blue-500',
                      isActive
                        ? 'border-blue-600 bg-blue-50 text-blue-700'
                        : 'border-gray-200 bg-white text-gray-700 hover:border-blue-400 hover:bg-blue-50',
                    ].join(' ')}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-semibold">L{option.level}</span>
                      <span className="text-xs uppercase tracking-wide text-gray-500">{option.name}</span>
                    </div>
                    <p className="text-xs text-gray-600">{option.summary}</p>
                  </button>
                )
              })}
            </div>
          </section>

          <section className="rounded-lg border border-gray-200 bg-white shadow-sm">
            <div className="grid gap-4 px-6 py-6 md:grid-cols-3">
              <div className="space-y-2">
                <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">Schedule</div>
                <div className="text-sm text-gray-800">
                  Interval: <span className="font-semibold">{formatInterval(scheduleHours)}</span>
                </div>
                <div className="text-xs text-gray-500">
                  Next run updates immediately after applying a new level. Pending timers cancel on downgrades.
                </div>
              </div>
              <div className="space-y-2">
                <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">Quotas</div>
                <div className="text-sm text-gray-800">
                  Jobs per day:{' '}
                  <span className="font-semibold">
                    {configSummary?.quotas?.jobs_per_day ?? detail?.policy.quotas?.jobs_per_day ?? '—'}
                  </span>
                </div>
                <div className="text-xs text-gray-500">Quota changes enforce immediately for new jobs.</div>
              </div>
              <div className="space-y-2">
                <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">Capabilities</div>
                <div className="text-sm text-gray-800">
                  Issued:{' '}
                  <span className="font-semibold">
                    {issuedScopes.length > 0 ? formatList(issuedScopes) : 'None (per-job tokens only)'}
                  </span>
                </div>
                <div className="text-xs text-gray-500">
                  Downgrades revoke existing tokens automatically and log the audit trail.
                </div>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-3 border-t border-gray-200 px-6 py-4 text-xs text-gray-600">
              <span className="inline-flex items-center rounded-full bg-blue-50 px-3 py-1 text-blue-700">
                Consent scopes: {formatList(sensitiveScopes)}
              </span>
              <span className="inline-flex items-center rounded-full bg-emerald-50 px-3 py-1 text-emerald-700">
                RSC: {configSummary?.rsc_enabled ? 'Enabled' : 'Disabled'}
              </span>
              {Object.keys(workflowToggles).length > 0 && (
                <span className="inline-flex items-center rounded-full bg-purple-50 px-3 py-1 text-purple-700">
                  Workflows:{' '}
                  {formatList(
                    Object.entries(workflowToggles)
                      .filter(([_, value]) => Boolean(value))
                      .map(([key]) => key),
                  )}
                </span>
              )}
              {configSummary?.audit_id && (
                <span className="inline-flex items-center rounded-full bg-gray-100 px-3 py-1 text-gray-700">
                  Audit ID: {configSummary.audit_id}
                </span>
              )}
              {configSummary?.archived_state && (
                <span className="inline-flex items-center rounded-full bg-gray-100 px-3 py-1 text-gray-700">
                  Archived state: {configSummary.archived_state}
                </span>
              )}
            </div>
          </section>

          {isManual ? (
            <div className="rounded-lg border border-dashed border-gray-300 bg-white px-6 py-10 text-center text-gray-600">
              <h3 className="text-lg font-semibold text-gray-900">Manual Head Coach only</h3>
              <p className="mt-2 text-sm">
                No background agent is active. Create a Background agent to enable autonomous proposals.
              </p>
              <button
                className="mt-4 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60"
                disabled={isSaving}
                onClick={() => handleConfigure(1, { force: true })}
              >
                Create Background Agent (L1)
              </button>
            </div>
          ) : (
            <>
              <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
                <div className="border-b border-gray-200 px-6 py-4">
                  <h3 className="text-lg font-semibold text-gray-900">Agent Control Center</h3>
                  <p className="text-sm text-gray-600">
                    Embedded view reflects the active presets, quotas, and capability tokens for this user.
                  </p>
                </div>
                <div className="px-2 py-4">
                  <AgentControlPanel key={panelKey} focusUserId={userId} embedded />
                </div>
              </div>

              <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
                <div className="border-b border-gray-200 px-6 py-4">
                  <h3 className="text-lg font-semibold text-gray-900">Activity Audit</h3>
                  <p className="text-sm text-gray-600">
                    Last 20 configuration, job, and capability events for this agent.
                  </p>
                </div>
                <div className="px-6 py-4">
                  <AgentAuditTail userId={userId} limit={20} refreshKey={panelKey} />
                </div>
              </div>

              {configSummary?.rsc_enabled && (
                <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
                  <div className="border-b border-gray-200 px-6 py-4">
                    <h3 className="text-lg font-semibold text-gray-900">RSC Collaboration</h3>
                    <p className="text-sm text-gray-600">
                      Agent-to-agent messaging for collaborative workflows. Send invites, exchange briefs, and coordinate with other Head Coach agents.
                    </p>
                  </div>
                  <div className="px-6 py-4">
                    <RSCConsole userId={userId} />
                  </div>
                </div>
              )}

              {/* Autonomy Section (Phase 5.A) */}
              <section className="rounded-lg border border-gray-200 bg-white shadow-sm">
                <div className="border-b border-gray-200 px-6 py-4">
                  <h3 className="text-lg font-semibold text-gray-900">Autonomy (Phase 5.A)</h3>
                  <p className="text-sm text-gray-600">
                    Self-scheduling, governance guardrails, and autonomous task execution for Head Coach agents.
                  </p>
                </div>
                <div className="px-6 py-4">
                  <AutonomyPanel userId={userId} agencyLevel={level} readonly={level < 2} />
                </div>
              </section>

              {/* Learning Section (Phase 3b.1) */}
              <section className="rounded-lg border border-gray-200 bg-white shadow-sm">
                <div className="border-b border-gray-200 px-6 py-4">
                  <h3 className="text-lg font-semibold text-gray-900">Learning (Adaptive)</h3>
                  <p className="text-sm text-gray-600">
                    Automatic behavior tuning based on Life OS insights: tone, creativity, nudge frequency, and focus areas.
                  </p>
                </div>
                <div className="px-6 py-4">
                  <LearningPanel userId={userId} agencyLevel={level} />
                </div>
              </section>

              {/* Life OS Section */}
              {FEATURE_FLAGS.LIFE_OS_IN_USER_OPS && (
                <section className="rounded-lg border border-gray-200 bg-white shadow-sm">
                  <div className="border-b border-gray-200 px-6 py-4">
                    <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                      <div>
                        <h3 className="text-lg font-semibold text-gray-900">Life OS</h3>
                        <p className="text-sm text-gray-600">
                          Personal productivity: goals, todos, quick capture, and inspiration.
                        </p>
                      </div>
                      {showCapabilityModal && (
                        <button
                          type="button"
                          onClick={() => setCapModalOpen(true)}
                          className="self-start rounded-md border border-blue-200 px-3 py-1.5 text-xs font-medium text-blue-700 hover:bg-blue-50"
                        >
                          Generate Capability Token
                        </button>
                      )}
                    </div>
                  </div>
                  <div className="px-6 py-4">
                    <LifeOSPane userId={userId} embedded editable={level >= 2} />
                  </div>
                </section>
              )}
            </>
          )}
        </>
      )}

      {pendingDowngrade !== null && (
        <div className="fixed inset-0 z-20 flex items-center justify-center bg-gray-900/50 p-4">
          <div className="w-full max-w-md rounded-lg border border-gray-200 bg-white shadow-xl">
            <div className="border-b border-gray-200 px-5 py-4">
              <h3 className="text-lg font-semibold text-gray-900">Confirm downgrade</h3>
            </div>
            <div className="space-y-3 px-5 py-4 text-sm text-gray-700">
              <p>
                Downgrading to <span className="font-semibold">L{pendingDowngrade}</span> revokes capability tokens,
                cancels scheduled jobs, and archives the current agent state. This action is immediate.
              </p>
              <p>Proceed and revoke tokens now?</p>
            </div>
            <div className="flex justify-end gap-3 border-t border-gray-200 px-5 py-4">
              <button
                className="rounded-md border border-gray-300 px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 disabled:opacity-60"
                onClick={() => setPendingDowngrade(null)}
                disabled={isSaving}
              >
                Cancel
              </button>
              <button
                className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-60"
                disabled={isSaving}
                onClick={() => handleConfigure(pendingDowngrade, { confirm: true })}
              >
                Apply downgrade
              </button>
            </div>
          </div>
        </div>
      )}

      {showCapabilityModal && (
        <CapabilityTokenModal userId={userId} open={capModalOpen} onClose={() => setCapModalOpen(false)} />
      )}
    </div>
  )
}
