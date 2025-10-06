import { useMemo } from 'react';

import type { MilestoneItem } from '../agents/celebrations-agent';

interface MilestonesPanelProps {
  items: MilestoneItem[];
  onClearAll: () => void;
  onDismiss: (id: string) => void;
}

function formatRelativeTime(timestamp: number): string {
  const now = Date.now();
  const delta = now - timestamp;
  if (!Number.isFinite(delta)) {
    return '';
  }
  const minutes = Math.round(delta / 60000);
  if (Math.abs(minutes) < 1) {
    return 'just now';
  }
  if (Math.abs(minutes) < 60) {
    return `${minutes} min${Math.abs(minutes) === 1 ? '' : 's'} ago`;
  }
  const hours = Math.round(minutes / 60);
  if (Math.abs(hours) < 24) {
    return `${hours} hour${Math.abs(hours) === 1 ? '' : 's'} ago`;
  }
  const days = Math.round(hours / 24);
  return `${days} day${Math.abs(days) === 1 ? '' : 's'} ago`;
}

function iconFor(type: MilestoneItem['type']): string {
  switch (type) {
    case 'ask_approved':
      return '📝';
    case 'photo_extracted':
      return '📷';
    case 'padna_render':
      return '🎨';
    case 'onboarding_init':
      return '📦';
    default:
      return '🎉';
  }
}

export function MilestonesPanel({ items, onClearAll, onDismiss }: MilestonesPanelProps) {
  const sorted = useMemo(() => [...items].sort((a, b) => b.ts - a.ts), [items]);

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4 shadow-sm">
      <header className="flex items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">Milestones</h2>
          <p className="text-xs text-slate-500">Moments we should celebrate.</p>
        </div>
        <button
          type="button"
          onClick={onClearAll}
          className="rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-300 transition hover:border-slate-500 hover:text-slate-100 disabled:opacity-40"
          disabled={sorted.length === 0}
        >
          Clear all
        </button>
      </header>

      {sorted.length === 0 ? (
        <p className="mt-4 text-xs text-slate-500">No milestones yet. Head Coach will highlight wins here.</p>
      ) : (
        <ul className="mt-3 space-y-3">
          {sorted.map((item) => (
            <li
              key={item.id}
              className="flex items-start justify-between gap-3 rounded-xl border border-slate-800 bg-slate-900/60 px-3 py-2"
            >
              <div className="flex flex-1 items-start gap-2">
                <span className="text-lg" aria-hidden>
                  {iconFor(item.type)}
                </span>
                <div className="flex-1">
                  <p className="text-sm text-slate-100">{item.message}</p>
                  {item.detail ? (
                    <p className="mt-1 text-xs text-slate-400">{item.detail}</p>
                  ) : null}
                  <p className="mt-1 text-[11px] uppercase tracking-wide text-slate-500">
                    {formatRelativeTime(item.ts)}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => onDismiss(item.id)}
                className="rounded-full border border-slate-700 px-2 py-1 text-[11px] text-slate-300 transition hover:border-slate-500 hover:text-slate-100"
                aria-label="Dismiss milestone"
              >
                Dismiss
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
