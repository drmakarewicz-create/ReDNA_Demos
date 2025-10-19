import { useState, useEffect, useCallback } from 'react'
import { toast } from 'react-toastify'
import { coreUrl } from '@/lib/env'
import { getCapabilityToken } from '@/lib/capabilityClient'
import LifeProjectsCard from './LifeProjectsCard'
import { LifeInsightsPane } from './LifeInsightsPane'

interface NorthStar {
  identity: string
  purpose: string
  happiness_notes: string
}

interface Todo {
  id: string
  text: string
  when: 'today' | 'week' | 'backlog' | 'scheduled'
  priority: number
  status: 'open' | 'done' | 'snoozed'
  goal_id?: string
  tags: string[]
  created_at: string
  updated_at: string
}

interface Goal {
  id: string
  text: string
  owner: string
  why: string
  first_step: string
  confidence: number
  target_date?: string
  status: 'active' | 'completed' | 'archived'
  created_at: string
  updated_at: string
}

interface Link {
  id: string
  title: string
  url: string
  source: string
  est_time_minutes?: number
  created_at: string
}

interface Inspiration {
  id: string
  text: string
  source: string
  why_matters: string
  created_at: string
}

interface LifeSummary {
  north_star: NorthStar
  today_three: Todo[]
  inbox: Todo[]
  goals: Goal[]
  links: Link[]
  quote: Inspiration | null
}

interface LifeOSPaneProps {
  userId: string
  embedded?: boolean   // compact margins, inherit container scroll
  editable?: boolean   // enable/disable writes based on agency level
}

export default function LifeOSPane({ userId, embedded = false, editable = true }: LifeOSPaneProps) {
  const [loading, setLoading] = useState(true)
  const [summary, setSummary] = useState<LifeSummary | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [captureText, setCaptureText] = useState('')
  // Future: const [showAddGoal, setShowAddGoal] = useState(false)
  // Future: const [showAddLink, setShowAddLink] = useState(false)

  const loadSummary = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch(coreUrl(`/ui/hc/life/${userId}/summary`))
      if (response.status === 404) {
        // 404 = no data yet, treat as empty state (not an error)
        setSummary({
          north_star: { identity: '', purpose: '', happiness_notes: '' },
          today_three: [],
          inbox: [],
          goals: [],
          links: [],
          quote: null,
        })
      } else if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      } else {
        const data = await response.json()
        setSummary(data.summary)
      }
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Unknown error'
      console.error('Failed to load Life OS summary:', err)
      setError(errorMsg)
    } finally {
      setLoading(false)
    }
  }, [userId])

  useEffect(() => {
    loadSummary()
  }, [loadSummary])

  const handleQuickCapture = async () => {
    if (!captureText.trim()) return

    try {
      const token = await getCapabilityToken(userId, 'core.agent.config')
      const response = await fetch(coreUrl(`/ui/hc/life/${userId}/capture`), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Capability': token,
        },
        body: JSON.stringify({ text: captureText, when: 'backlog' }),
      })

      if (!response.ok) {
        throw new Error(`Capture failed: ${response.status}`)
      }

      toast.success('Task captured')
      setCaptureText('')
      loadSummary()
    } catch (error) {
      console.error('Quick capture failed:', error)
      toast.error('Failed to capture task')
    }
  }

  const handleToggleTodo = async (todoId: string, currentStatus: string) => {
    const newStatus = currentStatus === 'done' ? 'open' : 'done'

    try {
      const token = await getCapabilityToken(userId, 'core.agent.config')
      const response = await fetch(coreUrl(`/ui/hc/life/${userId}/todos/${todoId}`), {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'X-Capability': token,
        },
        body: JSON.stringify({ status: newStatus }),
      })

      if (!response.ok) {
        throw new Error(`Update failed: ${response.status}`)
      }

      loadSummary()
    } catch (error) {
      console.error('Toggle todo failed:', error)
      toast.error('Failed to update task')
    }
  }

  if (loading) {
    return (
      <div className="rounded-md border border-gray-200 bg-white px-6 py-10 text-center text-sm text-gray-500">
        Loading Life OS…
      </div>
    )
  }

  if (error) {
    return (
      <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3">
        <div className="flex items-center justify-between">
          <div className="text-sm text-amber-800">
            Unable to load Life OS data: {error}
          </div>
          <button
            onClick={loadSummary}
            className="ml-4 rounded-md bg-amber-600 px-3 py-1 text-sm font-medium text-white hover:bg-amber-700"
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  if (!summary) {
    return (
      <div className="rounded-md border border-gray-200 bg-white px-6 py-10 text-center text-sm text-gray-500">
        No Life OS data available
      </div>
    )
  }

  const containerClass = embedded ? "space-y-4" : "space-y-6"

  return (
    <div className={containerClass}>
      {!editable && (
        <div className="rounded-md bg-amber-50 border border-amber-200 px-3 py-2 text-xs text-amber-800">
          <span className="font-semibold">Read-only (L0/L1)</span> — Enable Autonomous mode (L2+) to edit
        </div>
      )}

      {/* North Star */}
      <section className="rounded-lg border border-gray-200 bg-white shadow-sm">
        <div className="border-b border-gray-200 px-6 py-4">
          <h3 className="text-lg font-semibold text-gray-900">North Star</h3>
          <p className="text-sm text-gray-600">Your core identity, purpose, and what makes you happy</p>
        </div>
        <div className="space-y-3 px-6 py-4">
          {summary.north_star.identity && (
            <div>
              <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">Identity</div>
              <div className="text-sm text-gray-800">{summary.north_star.identity}</div>
            </div>
          )}
          {summary.north_star.purpose && (
            <div>
              <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">Purpose</div>
              <div className="text-sm text-gray-800">{summary.north_star.purpose}</div>
            </div>
          )}
          {summary.north_star.happiness_notes && (
            <div>
              <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">Happiness Notes</div>
              <div className="text-sm text-gray-800">{summary.north_star.happiness_notes}</div>
            </div>
          )}
          {!summary.north_star.identity && !summary.north_star.purpose && (
            <div className="text-sm italic text-gray-400">
              No North Star yet — define your identity and purpose to guide your goals
            </div>
          )}
        </div>
      </section>

      {/* Today's 3 */}
      <section className="rounded-lg border border-gray-200 bg-white shadow-sm">
        <div className="border-b border-gray-200 px-6 py-4">
          <h3 className="text-lg font-semibold text-gray-900">Today's 3</h3>
          <p className="text-sm text-gray-600">Top 3 must-do tasks for today</p>
        </div>
        <div className="px-6 py-4">
          {summary.today_three.length === 0 ? (
            <div className="text-sm italic text-gray-400">
              No tasks scheduled for today — Quick Capture something important
            </div>
          ) : (
            <div className="space-y-2">
              {summary.today_three.map((todo) => (
                <div key={todo.id} className="flex items-start gap-3">
                  <input
                    type="checkbox"
                    checked={todo.status === 'done'}
                    onChange={() => editable && handleToggleTodo(todo.id, todo.status)}
                    disabled={!editable}
                    title={!editable ? "Enable Autonomous mode (L2) to edit" : ""}
                    className="mt-1 h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
                  />
                  <div className="flex-1">
                    <div className={`text-sm ${todo.status === 'done' ? 'line-through text-gray-500' : 'text-gray-800'}`}>
                      {todo.text}
                    </div>
                    {todo.tags.length > 0 && (
                      <div className="mt-1 flex flex-wrap gap-1">
                        {todo.tags.map((tag, idx) => (
                          <span key={idx} className="rounded bg-blue-50 px-2 py-0.5 text-xs text-blue-700">
                            {tag}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="text-xs text-gray-500">P{Math.round(todo.priority * 100)}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* Quick Capture */}
      <section className="rounded-lg border border-gray-200 bg-white shadow-sm">
        <div className="border-b border-gray-200 px-6 py-4">
          <h3 className="text-lg font-semibold text-gray-900">Quick Capture</h3>
          <p className="text-sm text-gray-600">Quickly capture a task or reminder</p>
        </div>
        <div className="px-6 py-4">
          <div className="flex gap-2">
            <input
              type="text"
              value={captureText}
              onChange={(e) => setCaptureText(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && editable && handleQuickCapture()}
              placeholder={editable ? "What needs to be done?" : "Enable L2+ to add tasks"}
              disabled={!editable}
              title={!editable ? "Enable Autonomous mode (L2) to edit" : ""}
              className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
            />
            <button
              onClick={handleQuickCapture}
              disabled={!editable || !captureText.trim()}
              title={!editable ? "Enable Autonomous mode (L2) to edit" : ""}
              className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Add
            </button>
          </div>
        </div>
      </section>

      {/* Inbox */}
      <section className="rounded-lg border border-gray-200 bg-white shadow-sm">
        <div className="border-b border-gray-200 px-6 py-4">
          <h3 className="text-lg font-semibold text-gray-900">Inbox</h3>
          <p className="text-sm text-gray-600">Unscheduled tasks</p>
        </div>
        <div className="px-6 py-4">
          {summary.inbox.length === 0 ? (
            <div className="text-sm italic text-gray-400">Inbox is empty</div>
          ) : (
            <div className="space-y-2">
              {summary.inbox.map((todo) => (
                <div key={todo.id} className="flex items-start gap-3">
                  <input
                    type="checkbox"
                    checked={todo.status === 'done'}
                    onChange={() => editable && handleToggleTodo(todo.id, todo.status)}
                    disabled={!editable}
                    title={!editable ? "Enable Autonomous mode (L2) to edit" : ""}
                    className="mt-1 h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
                  />
                  <div className="flex-1 text-sm text-gray-800">{todo.text}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* Goals */}
      <section className="rounded-lg border border-gray-200 bg-white shadow-sm">
        <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Goals</h3>
            <p className="text-sm text-gray-600">Quarter goals and long-term objectives</p>
          </div>
          {/* Future: Add Goal button
          <button
            className="rounded-md border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-100"
          >
            + Add Goal
          </button>
          */}
        </div>
        <div className="px-6 py-4">
          {summary.goals.length === 0 ? (
            <div className="text-sm italic text-gray-400">
              No goals yet — add goals to track progress toward your North Star
            </div>
          ) : (
            <div className="space-y-4">
              {summary.goals.map((goal) => (
                <div key={goal.id} className="space-y-2 rounded-lg border border-gray-200 bg-gray-50 p-4">
                  <div className="font-medium text-gray-900">{goal.text}</div>
                  <div className="grid gap-2 text-xs text-gray-600">
                    <div>
                      <span className="font-semibold">Why:</span> {goal.why}
                    </div>
                    <div>
                      <span className="font-semibold">First step:</span> {goal.first_step}
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="font-semibold">Confidence:</span>
                      <div className="flex-1">
                        <div className="h-2 w-full rounded-full bg-gray-200">
                          <div
                            className="h-2 rounded-full bg-blue-600"
                            style={{ width: `${goal.confidence * 100}%` }}
                          />
                        </div>
                      </div>
                      <span>{Math.round(goal.confidence * 100)}%</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* Insights - Phase 3 */}
      <section>
        <div className="mb-3">
          <h3 className="text-lg font-semibold text-gray-900">Insights & Analytics</h3>
          <p className="text-sm text-gray-600">Track your progress and patterns over time</p>
        </div>
        <LifeInsightsPane userId={userId} embedded={embedded} />
      </section>

      {/* Projects - Phase 2 */}
      <LifeProjectsCard userId={userId} baseUrl={coreUrl('')} />

      {/* Links */}
      <section className="rounded-lg border border-gray-200 bg-white shadow-sm">
        <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Reading & Links</h3>
            <p className="text-sm text-gray-600">Saved articles and resources</p>
          </div>
          {/* Future: Add Link button
          <button
            className="rounded-md border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-100"
          >
            + Add Link
          </button>
          */}
        </div>
        <div className="px-6 py-4">
          {summary.links.length === 0 ? (
            <div className="text-sm italic text-gray-400">
              No links saved yet — add articles and resources for later
            </div>
          ) : (
            <div className="space-y-3">
              {summary.links.map((link) => (
                <div key={link.id} className="space-y-1">
                  <a
                    href={link.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm font-medium text-blue-600 hover:underline"
                  >
                    {link.title}
                  </a>
                  <div className="text-xs text-gray-500">
                    {link.source && <span>{link.source}</span>}
                    {link.est_time_minutes && <span> · {link.est_time_minutes} min read</span>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* Inspiration */}
      <section className="rounded-lg border border-gray-200 bg-gradient-to-br from-blue-50 to-purple-50 shadow-sm">
        <div className="border-b border-gray-200 px-6 py-4">
          <h3 className="text-lg font-semibold text-gray-900">Inspiration</h3>
          <p className="text-sm text-gray-600">Quotes and wisdom to guide you</p>
        </div>
        <div className="px-6 py-4">
          {summary.quote ? (
            <blockquote className="space-y-3">
              <div className="text-base italic text-gray-800">&ldquo;{summary.quote.text}&rdquo;</div>
              <div className="text-sm text-gray-600">— {summary.quote.source}</div>
              {summary.quote.why_matters && (
                <div className="text-xs text-gray-500">{summary.quote.why_matters}</div>
              )}
            </blockquote>
          ) : (
            <div className="text-sm italic text-gray-400">
              No inspiration added yet — add a quote or wisdom that motivates you
            </div>
          )}
        </div>
      </section>
    </div>
  )
}
