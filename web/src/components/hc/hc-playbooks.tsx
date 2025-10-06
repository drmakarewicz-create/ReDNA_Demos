'use client';

/**
 * Head Coach Playbooks Panel (HC v2 Sprint 1c)
 *
 * Displays available playbooks with buttons to run them.
 * - Curiosity Campaign
 * - Photo Refine
 * - Explain Change
 *
 * Features:
 * - One-click playbook execution
 * - Inline toast/result display
 * - Auto-refresh tasks after execution
 */

import { useState } from 'react';

interface HCPlaybooksProps {
  userId: string;
  className?: string;
  onPlaybookRun?: () => void;
}

interface PlaybookResult {
  type: 'success' | 'error';
  message: string;
}

export function HCPlaybooks({ userId, className = '', onPlaybookRun }: HCPlaybooksProps) {
  const [running, setRunning] = useState<string | null>(null);
  const [result, setResult] = useState<PlaybookResult | null>(null);

  async function handleRunPlaybook(playbookId: string, name: string) {
    setRunning(playbookId);
    setResult(null);

    try {
      const response = await fetch(`/api/hc/playbooks/run?userId=${encodeURIComponent(userId)}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ playbook_id: playbookId }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();
      const tasksCount = data.tasks_enqueued?.length || 0;

      setResult({
        type: 'success',
        message: `Enqueued ${tasksCount} task${tasksCount !== 1 ? 's' : ''} from ${name}`,
      });

      // Notify parent to refresh tasks
      if (onPlaybookRun) {
        onPlaybookRun();
      }

      // Clear result after 3 seconds
      setTimeout(() => setResult(null), 3000);
    } catch (err) {
      setResult({
        type: 'error',
        message: err instanceof Error ? err.message : 'Failed to run playbook',
      });
    } finally {
      setRunning(null);
    }
  }

  const playbooks = [
    { id: 'curiosity_campaign', name: 'Curiosity Campaign', color: 'amber' },
    { id: 'photo_refine', name: 'Photo Refine', color: 'blue' },
    { id: 'explain_change', name: 'Explain Change', color: 'purple' },
  ];

  return (
    <section className={`rounded-2xl border border-slate-800 bg-slate-950/60 p-4 shadow-sm ${className}`}>
      {/* Header */}
      <header>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">Playbooks</h2>
        <p className="text-xs text-slate-500">One-click workflows to reduce uncertainty</p>
      </header>

      {/* Result Toast */}
      {result && (
        <div
          className={`mt-3 rounded-lg border p-2 ${
            result.type === 'success'
              ? 'border-green-800 bg-green-950/40 text-green-300'
              : 'border-red-800 bg-red-950/40 text-red-300'
          }`}
        >
          <p className="text-xs">{result.message}</p>
        </div>
      )}

      {/* Playbook Buttons */}
      <div className="mt-3 flex flex-wrap gap-2">
        {playbooks.map((playbook) => (
          <button
            key={playbook.id}
            type="button"
            onClick={() => handleRunPlaybook(playbook.id, playbook.name)}
            disabled={running !== null}
            className={`rounded-lg border px-3 py-2 text-xs font-medium transition ${
              playbook.color === 'amber'
                ? 'border-amber-700 bg-amber-950/40 text-amber-300 hover:border-amber-500'
                : playbook.color === 'blue'
                ? 'border-blue-700 bg-blue-950/40 text-blue-300 hover:border-blue-500'
                : 'border-purple-700 bg-purple-950/40 text-purple-300 hover:border-purple-500'
            } disabled:border-slate-800 disabled:bg-slate-950/40 disabled:text-slate-600`}
          >
            {running === playbook.id ? 'Running...' : playbook.name}
          </button>
        ))}
      </div>
    </section>
  );
}
