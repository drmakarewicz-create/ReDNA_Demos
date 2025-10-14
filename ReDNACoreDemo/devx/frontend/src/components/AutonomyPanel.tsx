/**
 * Autonomy Panel - Phase 5.A
 *
 * Visualization and controls for Head Coach autonomy policy, scheduler, and governance.
 */

import { useCallback, useEffect, useState } from 'react'
import { toast } from 'react-toastify'

interface AutonomyPolicy {
  level: number
  self_schedule: boolean
  self_reflect: boolean
  self_narrate: boolean
  rsc_enabled: boolean
  consent_scope: string[]
  guardrails: {
    max_self_actions_per_day: number
    tone_shift_bounds: number
    creativity_shift_bounds: number
    max_learning_delta_per_week: number
    require_consent_for: string[]
    prohibited_actions: string[]
  }
  last_updated: string
  version: string
}

interface PolicyEvaluation {
  readiness: number
  compliance: boolean
  warnings: string[]
  recommendations: string[]
}

interface ScheduleTask {
  task_type: string
  interval_days: number
  last_run: string | null
  next_run: string | null
  enabled: boolean
  run_count: number
  failure_count: number
}

interface ScheduleState {
  user_id: string
  tasks: Record<string, ScheduleTask>
  actions_today: number
  last_reset: string
  total_actions: number
}

interface AutonomyPanelProps {
  userId: string
  agencyLevel: number
  readonly?: boolean
}

const LEVEL_NAMES = ['Dormant', 'Semi', 'Supervised', 'Trusted', 'Full']

const TASK_LABELS: Record<string, string> = {
  life_weekly_review: 'Weekly Life Review',
  narrator_weekly_summary: 'Narrator Summary',
  learning_update: 'Learning Update',
  life_voice_summary: 'Voice Summary',
}

export default function AutonomyPanel({ userId, agencyLevel, readonly = false }: AutonomyPanelProps) {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [policy, setPolicy] = useState<AutonomyPolicy | null>(null)
  const [evaluation, setEvaluation] = useState<PolicyEvaluation | null>(null)
  const [schedule, setSchedule] = useState<ScheduleState | null>(null)
  const [quota, setQuota] = useState<{ actions_today: number; max_actions_per_day: number } | null>(null)
  const [isRunningTask, setIsRunningTask] = useState<string | null>(null)
  const [lastRefresh, setLastRefresh] = useState(0)

  const loadAutonomyData = useCallback(async () => {
    setLoading(true)
    setError(null)

    try {
      const [policyRes, scheduleRes] = await Promise.all([
        fetch(`http://localhost:8015/ui/hc/autonomy/${userId}/policy`),
        fetch(`http://localhost:8015/ui/hc/autonomy/${userId}/schedule`),
      ])

      if (!policyRes.ok || !scheduleRes.ok) {
        throw new Error('Failed to load autonomy data')
      }

      const policyData = await policyRes.json()
      const scheduleData = await scheduleRes.json()

      setPolicy(policyData.policy)
      setEvaluation(policyData.evaluation)
      setSchedule(scheduleData.schedule)
      setQuota(scheduleData.quota)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load autonomy data'
      setError(message)
      toast.error(message)
    } finally {
      setLoading(false)
    }
  }, [userId])

  useEffect(() => {
    loadAutonomyData()
  }, [loadAutonomyData, lastRefresh])

  const handleToggleSelfSchedule = async () => {
    if (readonly || !policy) return

    try {
      const res = await fetch(`http://localhost:8015/ui/hc/autonomy/${userId}/policy`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          self_schedule: !policy.self_schedule,
        }),
      })

      if (!res.ok) throw new Error('Failed to update policy')

      const data = await res.json()

      if (data.ok) {
        toast.success(`Self-scheduling ${!policy.self_schedule ? 'enabled' : 'disabled'}`)
        setLastRefresh(Date.now())
      } else {
        toast.error(data.errors?.join(', ') ?? 'Update failed')
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to toggle self-schedule'
      toast.error(message)
    }
  }

  const handleRunTask = async (taskType: string) => {
    if (readonly) return

    setIsRunningTask(taskType)

    try {
      const res = await fetch(`http://localhost:8015/ui/hc/autonomy/${userId}/run/${taskType}`, {
        method: 'POST',
      })

      if (!res.ok) throw new Error('Failed to run task')

      const data = await res.json()

      if (data.ok) {
        toast.success(`Task executed: ${TASK_LABELS[taskType] ?? taskType}`)
        setLastRefresh(Date.now())
      } else {
        toast.error(data.error ?? 'Task failed')
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Task execution failed'
      toast.error(message)
    } finally {
      setIsRunningTask(null)
    }
  }

  if (loading) {
    return (
      <div className="rounded-md bg-gray-50 px-6 py-10 text-center text-sm text-gray-500">
        Loading autonomy configuration…
      </div>
    )
  }

  if (error || !policy || !evaluation || !schedule || !quota) {
    return (
      <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
        {error ?? 'Failed to load autonomy data'}
      </div>
    )
  }

  const levelName = LEVEL_NAMES[policy.level] ?? `Level ${policy.level}`
  const readinessPercent = Math.round(evaluation.readiness * 100)
  const quotaPercent = quota.max_actions_per_day > 0
    ? Math.round((quota.actions_today / quota.max_actions_per_day) * 100)
    : 0

  return (
    <div className="space-y-6">
      {/* Policy Overview */}
      <div className="grid gap-6 md:grid-cols-2">
        {/* Autonomy Level & Capabilities */}
        <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
          <h4 className="text-sm font-semibold text-gray-900 mb-3">Autonomy Configuration</h4>

          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">Autonomy Level</span>
              <span className="inline-flex items-center rounded-full bg-blue-100 px-3 py-1 text-sm font-medium text-blue-800">
                L{policy.level} · {levelName}
              </span>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">Self-scheduling</span>
              <button
                onClick={handleToggleSelfSchedule}
                disabled={readonly || policy.level < 2}
                className={[
                  'relative inline-flex h-6 w-11 items-center rounded-full transition',
                  policy.self_schedule ? 'bg-blue-600' : 'bg-gray-300',
                  readonly || policy.level < 2 ? 'cursor-not-allowed opacity-50' : 'cursor-pointer',
                ].join(' ')}
              >
                <span
                  className={[
                    'inline-block h-4 w-4 rounded-full bg-white transition',
                    policy.self_schedule ? 'translate-x-6' : 'translate-x-1',
                  ].join(' ')}
                />
              </button>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">Self-reflection</span>
              <span className="text-sm font-medium text-gray-900">
                {policy.self_reflect ? 'Enabled' : 'Disabled'}
              </span>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">Self-narration</span>
              <span className="text-sm font-medium text-gray-900">
                {policy.self_narrate ? 'Enabled' : 'Disabled'}
              </span>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">RSC Collaboration</span>
              <span className="text-sm font-medium text-gray-900">
                {policy.rsc_enabled ? 'Enabled' : 'Disabled'}
              </span>
            </div>
          </div>
        </div>

        {/* Readiness & Compliance */}
        <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
          <h4 className="text-sm font-semibold text-gray-900 mb-3">Readiness & Compliance</h4>

          <div className="space-y-3">
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-gray-600">Readiness</span>
                <span className="text-sm font-semibold text-gray-900">{readinessPercent}%</span>
              </div>
              <div className="h-2 w-full rounded-full bg-gray-200">
                <div
                  className={[
                    'h-2 rounded-full transition-all',
                    readinessPercent >= 80 ? 'bg-green-500' :
                    readinessPercent >= 50 ? 'bg-yellow-500' :
                    'bg-orange-500',
                  ].join(' ')}
                  style={{ width: `${readinessPercent}%` }}
                />
              </div>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">Compliance</span>
              <span
                className={[
                  'inline-flex items-center rounded-full px-2 py-1 text-xs font-medium',
                  evaluation.compliance
                    ? 'bg-green-100 text-green-800'
                    : 'bg-red-100 text-red-800',
                ].join(' ')}
              >
                {evaluation.compliance ? '✓ Compliant' : '✗ Non-compliant'}
              </span>
            </div>

            {evaluation.warnings.length > 0 && (
              <div className="space-y-1">
                <span className="text-xs font-semibold uppercase text-gray-500">Warnings</span>
                {evaluation.warnings.slice(0, 2).map((warning, idx) => (
                  <p key={idx} className="text-xs text-yellow-700">• {warning}</p>
                ))}
              </div>
            )}

            {evaluation.recommendations.length > 0 && (
              <div className="space-y-1">
                <span className="text-xs font-semibold uppercase text-gray-500">Recommendations</span>
                {evaluation.recommendations.slice(0, 2).map((rec, idx) => (
                  <p key={idx} className="text-xs text-blue-700">• {rec}</p>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Guardrails */}
      <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
        <h4 className="text-sm font-semibold text-gray-900 mb-3">Guardrails</h4>

        <div className="grid gap-3 md:grid-cols-2">
          <div className="space-y-1">
            <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">Daily Action Limit</div>
            <div className="text-sm text-gray-800">
              {quota.actions_today} / {quota.max_actions_per_day} actions today
              <span className="ml-2 text-xs text-gray-500">({quotaPercent}%)</span>
            </div>
          </div>

          <div className="space-y-1">
            <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">Learning Delta Bounds</div>
            <div className="text-sm text-gray-800">
              ±{policy.guardrails.max_learning_delta_per_week.toFixed(2)} per week
            </div>
          </div>

          <div className="space-y-1">
            <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">Tone Shift Bounds</div>
            <div className="text-sm text-gray-800">
              ±{policy.guardrails.tone_shift_bounds.toFixed(2)}
            </div>
          </div>

          <div className="space-y-1">
            <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">Creativity Shift Bounds</div>
            <div className="text-sm text-gray-800">
              ±{policy.guardrails.creativity_shift_bounds.toFixed(2)}
            </div>
          </div>
        </div>

        <div className="mt-4 space-y-2">
          <div className="space-y-1">
            <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">Prohibited Actions</div>
            <div className="flex flex-wrap gap-2">
              {policy.guardrails.prohibited_actions.map((action) => (
                <span
                  key={action}
                  className="inline-flex items-center rounded-full bg-red-50 px-2 py-1 text-xs text-red-700"
                >
                  {action}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Scheduled Tasks */}
      <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <h4 className="text-sm font-semibold text-gray-900">Scheduled Tasks</h4>
          <button
            onClick={() => setLastRefresh(Date.now())}
            className="text-xs text-blue-600 hover:text-blue-700"
          >
            Refresh
          </button>
        </div>

        <div className="space-y-3">
          {Object.values(schedule.tasks).map((task) => (
            <div
              key={task.task_type}
              className="flex items-center justify-between rounded-lg border border-gray-200 bg-gray-50 px-4 py-3"
            >
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-gray-900">
                    {TASK_LABELS[task.task_type] ?? task.task_type}
                  </span>
                  {!task.enabled && (
                    <span className="text-xs text-gray-500">(disabled)</span>
                  )}
                </div>

                <div className="mt-1 flex items-center gap-4 text-xs text-gray-600">
                  <span>Interval: {task.interval_days}d</span>
                  {task.last_run && (
                    <span>Last: {new Date(task.last_run).toLocaleDateString()}</span>
                  )}
                  {task.next_run && (
                    <span>Next: {new Date(task.next_run).toLocaleDateString()}</span>
                  )}
                  <span>Runs: {task.run_count}</span>
                  {task.failure_count > 0 && (
                    <span className="text-red-600">Failures: {task.failure_count}</span>
                  )}
                </div>
              </div>

              {!readonly && task.enabled && (
                <button
                  onClick={() => handleRunTask(task.task_type)}
                  disabled={isRunningTask === task.task_type || quota.actions_today >= quota.max_actions_per_day}
                  className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {isRunningTask === task.task_type ? 'Running...' : 'Run Now'}
                </button>
              )}
            </div>
          ))}
        </div>

        {Object.keys(schedule.tasks).length === 0 && (
          <p className="text-center text-sm text-gray-500 py-4">No scheduled tasks</p>
        )}
      </div>

      {/* Footer Info */}
      <div className="rounded-md bg-gray-50 px-4 py-3 text-xs text-gray-600">
        <div className="flex items-center justify-between">
          <span>Policy version: {policy.version}</span>
          <span>Last updated: {new Date(policy.last_updated).toLocaleString()}</span>
          <span>Total actions: {schedule.total_actions}</span>
        </div>
      </div>
    </div>
  )
}
