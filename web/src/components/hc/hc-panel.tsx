'use client';

/**
 * Head Coach Panel v2
 *
 * Shows:
 * - Today's Focus
 * - Open tasks with time estimates
 * - Curiosity hotspots
 * - Recent decisions/wins
 * - "Why?" buttons for explanations
 * - v2: Task queue panel
 *
 * Buttons:
 * - Plan my next hour
 * - Reduce uncertainty here
 * - Explain this plan
 */

import { useEffect, useState } from 'react';
import { fetchWithRetry } from '../../lib/utils';
import { HCTasks } from './hc-tasks';
import { HCPlaybooks } from './hc-playbooks';
import { HCConversation } from './hc-conversation';

export interface HCState {
  userId: string;
  hcName: string;
  goals: string[];
  openTasks: Array<{
    id?: string;
    title: string;
    etaMins: number;
    source?: string;
    action?: string;
    trait?: string;
    link?: string;
  }>;
  curiosityHotspots: Array<{
    trait: string;
    curiosity: number;
    ucn?: number;
    rr?: number;
    reason: string;
    resolved_value?: any;
  }>;
  recentDecisions: Array<{
    ts: string;
    summary: string;
    why?: string;
    provenance?: string[];
  }>;
  checkpoints: string[];
  relationship?: {
    tone: string;
    notifications: string;
  };
}

interface HCPanelProps {
  userId: string;
  className?: string;
}

export function HCPanel({ userId, className = '' }: HCPanelProps) {
  const [state, setState] = useState<HCState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showWhyModal, setShowWhyModal] = useState<string | null>(null);

  useEffect(() => {
    fetchHCState();
  }, [userId]);

  async function fetchHCState() {
    setLoading(true);
    setError(null);

    try {
      const response = await fetchWithRetry(`/api/hc/state?userId=${encodeURIComponent(userId)}`);

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || `HTTP ${response.status}`);
      }

      const data = await response.json();
      setState(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }

  function handleTaskClick(task: HCState['openTasks'][0]) {
    if (task.link) {
      window.location.href = task.link;
    }
  }

  function handleExplainClick(topic: string) {
    setShowWhyModal(topic);
  }

  if (loading) {
    return (
      <section className={`rounded-2xl border border-slate-800 bg-slate-950/60 p-4 shadow-sm ${className}`}>
        <p className="text-sm text-slate-400">Loading Head Coach...</p>
      </section>
    );
  }

  if (error) {
    return (
      <section className={`rounded-2xl border border-red-800 bg-red-950/40 p-4 shadow-sm ${className}`}>
        <h2 className="text-sm font-semibold text-red-400">Head Coach Unavailable</h2>
        <p className="mt-1 text-xs text-red-300">{error}</p>
        <button
          type="button"
          onClick={fetchHCState}
          className="mt-2 rounded-lg border border-red-700 px-3 py-1 text-xs text-red-200 transition hover:border-red-500"
        >
          Retry
        </button>
      </section>
    );
  }

  if (!state) {
    return null;
  }

  const { hcName, goals, openTasks, curiosityHotspots, recentDecisions } = state;

  return (
    <>
      <section className={`rounded-2xl border border-slate-800 bg-slate-950/60 p-4 shadow-sm ${className}`}>
        {/* Header */}
        <header className="flex items-center justify-between gap-2">
          <div>
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
              Head Coach · {hcName}
            </h2>
            <p className="text-xs text-slate-500">Your orchestrator and guide</p>
          </div>
          <button
            type="button"
            onClick={fetchHCState}
            className="rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-300 transition hover:border-slate-500 hover:text-slate-100"
            title="Refresh"
          >
            ↻
          </button>
        </header>

        {/* Today's Focus */}
        {curiosityHotspots.length > 0 && (
          <div className="mt-4 rounded-xl border border-amber-800/50 bg-amber-950/20 p-3">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-amber-400">
              Today's Focus
            </h3>
            <p className="mt-1 text-sm text-slate-200">
              {curiosityHotspots[0].trait.split('.').pop()} has high curiosity ({Math.round(curiosityHotspots[0].curiosity)})
            </p>
            <p className="mt-0.5 text-xs text-slate-400">
              {curiosityHotspots[0].reason}
            </p>
            <button
              type="button"
              onClick={() => handleExplainClick(curiosityHotspots[0].trait)}
              className="mt-2 text-xs text-amber-300 underline decoration-dotted hover:text-amber-200"
            >
              Why I'm suggesting this...
            </button>
          </div>
        )}

        {/* Goals */}
        {goals.length > 0 && (
          <div className="mt-4">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-400">
              Goals
            </h3>
            <ul className="mt-1 space-y-1">
              {goals.map((goal, idx) => (
                <li key={idx} className="text-sm text-slate-300">
                  • {goal}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Open Tasks */}
        {openTasks.length > 0 && (
          <div className="mt-4">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-400">
              Next Steps
            </h3>
            <ul className="mt-2 space-y-2">
              {openTasks.slice(0, 5).map((task, idx) => (
                <li
                  key={idx}
                  className="flex items-start justify-between gap-2 rounded-lg border border-slate-800 bg-slate-900/60 px-3 py-2"
                >
                  <div className="flex-1">
                    <p className="text-sm text-slate-200">{task.title}</p>
                    <p className="mt-0.5 text-xs text-slate-500">
                      {task.etaMins} min{task.etaMins !== 1 ? 's' : ''}
                      {task.source && ` · from ${task.source}`}
                    </p>
                  </div>
                  {task.link && (
                    <button
                      type="button"
                      onClick={() => handleTaskClick(task)}
                      className="rounded-md border border-slate-700 px-2 py-1 text-xs text-slate-300 transition hover:border-slate-500 hover:text-slate-100"
                    >
                      Go →
                    </button>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Curiosity Hotspots */}
        {curiosityHotspots.length > 1 && (
          <div className="mt-4">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-400">
              Curiosity Hotspots ({curiosityHotspots.length})
            </h3>
            <ul className="mt-2 space-y-1.5">
              {curiosityHotspots.slice(0, 5).map((hotspot, idx) => (
                <li
                  key={idx}
                  className="flex items-center justify-between gap-2 rounded-lg border border-slate-800 bg-slate-900/40 px-2 py-1.5"
                >
                  <div className="flex-1">
                    <p className="text-xs font-medium text-slate-200">
                      {hotspot.trait.split('.').pop()}
                    </p>
                    <p className="text-xs text-slate-500">{hotspot.reason}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono text-amber-400">
                      {Math.round(hotspot.curiosity)}
                    </span>
                    <button
                      type="button"
                      onClick={() => handleExplainClick(hotspot.trait)}
                      className="text-xs text-slate-400 underline decoration-dotted hover:text-slate-300"
                      title="Explain"
                    >
                      ?
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Recent Decisions */}
        {recentDecisions.length > 0 && (
          <div className="mt-4">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-400">
              Recent Wins
            </h3>
            <ul className="mt-2 space-y-1.5">
              {recentDecisions.slice(0, 3).map((decision, idx) => (
                <li key={idx} className="rounded-lg border border-slate-800 bg-slate-900/40 px-2 py-1.5">
                  <p className="text-xs text-slate-300">{decision.summary}</p>
                  {decision.why && (
                    <p className="mt-0.5 text-xs text-slate-500">{decision.why}</p>
                  )}
                  <p className="mt-0.5 text-xs text-slate-600">
                    {new Date(decision.ts).toLocaleString()}
                  </p>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Action Buttons */}
        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={fetchHCState}
            className="rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-300 transition hover:border-slate-500 hover:text-slate-100"
          >
            Plan my next hour
          </button>
          {curiosityHotspots.length > 0 && (
            <button
              type="button"
              onClick={() => handleExplainClick(curiosityHotspots[0].trait)}
              className="rounded-lg border border-amber-700 px-3 py-2 text-xs text-amber-300 transition hover:border-amber-500 hover:text-amber-200"
            >
              Reduce uncertainty here
            </button>
          )}
          <button
            type="button"
            onClick={() => setShowWhyModal('plan')}
            className="rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-300 transition hover:border-slate-500 hover:text-slate-100"
          >
            Explain this plan
          </button>
        </div>
      </section>

      {/* Tasks Panel (v2) */}
      <HCTasks userId={userId} className="mt-4" />

      {/* Playbooks Panel (v2 Sprint 1c) */}
      <HCPlaybooks userId={userId} className="mt-4" onPlaybookRun={fetchHCState} />

      {/* Conversation Panel (v2 Sprint 1c) */}
      <HCConversation userId={userId} className="mt-4" />

      {/* Why Modal */}
      {showWhyModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
          onClick={() => setShowWhyModal(null)}
        >
          <div
            className="max-w-lg rounded-xl border border-slate-700 bg-slate-900 p-6 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-lg font-semibold text-slate-100">
              Why this suggestion?
            </h3>
            <div className="mt-3 text-sm text-slate-300">
              {showWhyModal === 'plan' ? (
                <p>
                  I prioritize actions based on <strong>curiosity × impact</strong>.
                  Traits with high curiosity and low confidence give you the biggest
                  uncertainty reduction for the least effort.
                </p>
              ) : (
                <p>
                  Trait: <strong>{showWhyModal}</strong>
                  <br />
                  <br />
                  This has high curiosity, meaning it's either rare or uncertain.
                  Adding evidence here will improve confidence and reduce curiosity.
                </p>
              )}
            </div>
            <button
              type="button"
              onClick={() => setShowWhyModal(null)}
              className="mt-4 rounded-lg border border-slate-600 px-4 py-2 text-sm text-slate-200 transition hover:border-slate-500"
            >
              Got it
            </button>
          </div>
        </div>
      )}
    </>
  );
}
