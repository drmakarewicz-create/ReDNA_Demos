'use client';

/**
 * Head Coach Tasks Panel (HC v2)
 *
 * Displays task queue with state transitions:
 * - Queued tasks (ready to execute)
 * - Running tasks (in progress)
 * - Done tasks (completed)
 * - Failed tasks (errors)
 *
 * Features:
 * - Manual tick button to execute next task
 * - Task state badges with colors
 * - Provenance tooltips (who enqueued, why)
 * - ETA estimates
 * - Real-time updates
 */

import { useEffect, useState } from 'react';
import { fetchWithRetry } from '../../lib/utils';

export interface HCTask {
  id: string;
  title: string;
  action: string;
  args: Record<string, any>;
  state: 'queued' | 'running' | 'done' | 'failed' | 'snoozed';
  priority?: 'low' | 'normal' | 'high';
  created_ts: string;
  updated_ts: string;
  eta_mins: number;
  provenance: {
    source?: string;
    source_coach?: string;
    reason?: string;
    reminder_id?: string;
  };
  error?: string;
}

export interface HCReminder {
  id: string;
  title: string;
  when_iso: string;
  action: string;
  args: Record<string, any>;
  created_ts: string;
  completed_ts?: string;
  cancelled_ts?: string;
}

interface HCTasksProps {
  userId: string;
  className?: string;
}

export function HCTasks({ userId, className = '' }: HCTasksProps) {
  const [tasks, setTasks] = useState<HCTask[]>([]);
  const [reminders, setReminders] = useState<HCReminder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [ticking, setTicking] = useState(false);
  const [showProvenance, setShowProvenance] = useState<string | null>(null);

  useEffect(() => {
    fetchTasks();
    fetchReminders();
  }, [userId]);

  async function fetchTasks() {
    try {
      const response = await fetchWithRetry(`/api/hc/tasks/list?userId=${encodeURIComponent(userId)}`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = await response.json();
      setTasks(data.tasks || []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch tasks');
    } finally {
      setLoading(false);
    }
  }

  async function fetchReminders() {
    try {
      const response = await fetchWithRetry(`/api/hc/reminders/list?userId=${encodeURIComponent(userId)}`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = await response.json();
      setReminders(data.reminders || []);
    } catch (err) {
      console.error('Failed to fetch reminders:', err);
    }
  }

  async function handleTick() {
    setTicking(true);
    try {
      const response = await fetchWithRetry(`/api/hc/tasks/tick?userId=${encodeURIComponent(userId)}`, {
        method: 'POST',
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      await response.json();
      // Refresh tasks after tick
      await fetchTasks();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to execute task');
    } finally {
      setTicking(false);
    }
  }

  function getStateBadgeColor(state: HCTask['state']) {
    switch (state) {
      case 'queued':
        return 'bg-blue-950/40 border-blue-800 text-blue-300';
      case 'running':
        return 'bg-amber-950/40 border-amber-800 text-amber-300';
      case 'done':
        return 'bg-green-950/40 border-green-800 text-green-300';
      case 'failed':
        return 'bg-red-950/40 border-red-800 text-red-300';
      case 'snoozed':
        return 'bg-purple-950/40 border-purple-800 text-purple-300';
      default:
        return 'bg-slate-950/40 border-slate-800 text-slate-300';
    }
  }

  function getPriorityBadgeColor(priority?: 'low' | 'normal' | 'high') {
    switch (priority) {
      case 'high':
        return 'bg-red-950/40 border-red-700 text-red-300';
      case 'low':
        return 'bg-slate-950/40 border-slate-700 text-slate-400';
      case 'normal':
      default:
        return 'bg-slate-950/40 border-slate-700 text-slate-300';
    }
  }

  function formatTimestamp(ts: string) {
    try {
      const date = new Date(ts);
      return date.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
      });
    } catch {
      return ts;
    }
  }

  function isPendingReminder(reminder: HCReminder) {
    return !reminder.completed_ts && !reminder.cancelled_ts;
  }

  const queuedTasks = tasks.filter((t) => t.state === 'queued');
  const runningTasks = tasks.filter((t) => t.state === 'running');
  const doneTasks = tasks.filter((t) => t.state === 'done');
  const failedTasks = tasks.filter((t) => t.state === 'failed');
  const pendingReminders = reminders.filter(isPendingReminder);

  if (loading) {
    return (
      <section className={`rounded-2xl border border-slate-800 bg-slate-950/60 p-4 shadow-sm ${className}`}>
        <p className="text-sm text-slate-400">Loading tasks...</p>
      </section>
    );
  }

  return (
    <section className={`rounded-2xl border border-slate-800 bg-slate-950/60 p-4 shadow-sm ${className}`}>
      {/* Header */}
      <header className="flex items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">Task Queue</h2>
          <p className="text-xs text-slate-500">
            {queuedTasks.length} queued · {runningTasks.length} running · {doneTasks.length} done
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={handleTick}
            disabled={queuedTasks.length === 0 || ticking}
            className="rounded-lg border border-cyan-700 bg-cyan-950/40 px-3 py-1 text-xs text-cyan-300 transition hover:border-cyan-500 hover:text-cyan-100 disabled:border-slate-800 disabled:bg-slate-950/40 disabled:text-slate-600"
            title="Execute next queued task"
          >
            {ticking ? 'Executing...' : '▶ Tick'}
          </button>
          <button
            type="button"
            onClick={fetchTasks}
            className="rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-300 transition hover:border-slate-500 hover:text-slate-100"
            title="Refresh"
          >
            ↻
          </button>
        </div>
      </header>

      {error && (
        <div className="mt-3 rounded-lg border border-red-800 bg-red-950/40 p-2">
          <p className="text-xs text-red-300">{error}</p>
        </div>
      )}

      {/* Queued Tasks */}
      {queuedTasks.length > 0 && (
        <div className="mt-4">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-blue-400">
            Queued ({queuedTasks.length})
          </h3>
          <ul className="mt-2 space-y-2">
            {queuedTasks.map((task) => (
              <li
                key={task.id}
                className="rounded-lg border border-blue-800/50 bg-blue-950/20 p-2 transition hover:bg-blue-950/30"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1">
                    <p className="text-sm font-medium text-slate-200">{task.title}</p>
                    <p className="mt-0.5 text-xs text-slate-400">
                      {task.action} · ~{task.eta_mins}min
                    </p>
                    {task.provenance?.reason && (
                      <p className="mt-1 text-xs text-slate-500">{task.provenance.reason}</p>
                    )}
                  </div>
                  <div className="flex flex-col gap-1">
                    {task.priority && task.priority !== 'normal' && (
                      <span className={`rounded-md border px-2 py-0.5 text-xs font-medium ${getPriorityBadgeColor(task.priority)}`}>
                        {task.priority}
                      </span>
                    )}
                    <span className={`rounded-md border px-2 py-0.5 text-xs font-medium ${getStateBadgeColor(task.state)}`}>
                      {task.state}
                    </span>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Running Tasks */}
      {runningTasks.length > 0 && (
        <div className="mt-4">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-amber-400">
            Running ({runningTasks.length})
          </h3>
          <ul className="mt-2 space-y-2">
            {runningTasks.map((task) => (
              <li
                key={task.id}
                className="rounded-lg border border-amber-800/50 bg-amber-950/20 p-2"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1">
                    <p className="text-sm font-medium text-slate-200">{task.title}</p>
                    <p className="mt-0.5 text-xs text-slate-400">{task.action}</p>
                  </div>
                  <span className={`rounded-md border px-2 py-0.5 text-xs font-medium ${getStateBadgeColor(task.state)}`}>
                    {task.state}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Failed Tasks */}
      {failedTasks.length > 0 && (
        <div className="mt-4">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-red-400">
            Failed ({failedTasks.length})
          </h3>
          <ul className="mt-2 space-y-2">
            {failedTasks.slice(0, 3).map((task) => (
              <li
                key={task.id}
                className="rounded-lg border border-red-800/50 bg-red-950/20 p-2"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1">
                    <p className="text-sm font-medium text-slate-200">{task.title}</p>
                    <p className="mt-0.5 text-xs text-slate-400">{task.action}</p>
                    {task.error && (
                      <p className="mt-1 text-xs text-red-400">{task.error}</p>
                    )}
                  </div>
                  <span className={`rounded-md border px-2 py-0.5 text-xs font-medium ${getStateBadgeColor(task.state)}`}>
                    {task.state}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Done Tasks (last 3) */}
      {doneTasks.length > 0 && (
        <div className="mt-4">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-green-400">
            Recently Completed
          </h3>
          <ul className="mt-2 space-y-2">
            {doneTasks.slice(-3).reverse().map((task) => (
              <li
                key={task.id}
                className="rounded-lg border border-green-800/50 bg-green-950/20 p-2"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1">
                    <p className="text-sm font-medium text-slate-300">{task.title}</p>
                    <p className="mt-0.5 text-xs text-slate-500">
                      {formatTimestamp(task.updated_ts)}
                    </p>
                  </div>
                  <span className={`rounded-md border px-2 py-0.5 text-xs font-medium ${getStateBadgeColor(task.state)}`}>
                    ✓
                  </span>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Pending Reminders */}
      {pendingReminders.length > 0 && (
        <div className="mt-4">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-purple-400">
            Scheduled Reminders ({pendingReminders.length})
          </h3>
          <ul className="mt-2 space-y-2">
            {pendingReminders.slice(0, 3).map((reminder) => (
              <li
                key={reminder.id}
                className="rounded-lg border border-purple-800/50 bg-purple-950/20 p-2"
              >
                <div className="flex-1">
                  <p className="text-sm font-medium text-slate-200">{reminder.title}</p>
                  <p className="mt-0.5 text-xs text-slate-400">
                    Due: {formatTimestamp(reminder.when_iso)}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Empty State */}
      {queuedTasks.length === 0 && runningTasks.length === 0 && doneTasks.length === 0 && (
        <div className="mt-4 rounded-lg border border-slate-800 bg-slate-950/40 p-4 text-center">
          <p className="text-sm text-slate-400">No tasks yet</p>
          <p className="mt-1 text-xs text-slate-500">Tasks will appear here when Head Coach schedules work</p>
        </div>
      )}
    </section>
  );
}
