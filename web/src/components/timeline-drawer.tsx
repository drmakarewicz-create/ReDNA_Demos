'use client';

import { useMemo } from 'react';
import type { TraitTimelineEntry } from '../lib/api';

interface TimelineDrawerProps {
  open: boolean;
  traitId: string | null;
  entries: TraitTimelineEntry[];
  loading?: boolean;
  error?: string | null;
  onClose: () => void;
  userId: string;
}

export function TimelineDrawer({ open, traitId, entries, loading, error, onClose, userId }: TimelineDrawerProps) {
  const csvText = useMemo(() => buildCsv(entries), [entries]);
  const jsonText = useMemo(() => JSON.stringify(entries, null, 2), [entries]);

  if (!open || !traitId) {
    return null;
  }

  const filenameBase = `${userId || 'user'}_${traitId.replace(/[^A-Za-z0-9._-]/g, '_')}_${Date.now()}`;

  return (
    <div className="fixed inset-0 z-50 flex" role="dialog" aria-modal="true" aria-label={`Timeline for ${traitId}`}>
      <div className="flex-1 bg-slate-950/40" onClick={onClose} aria-hidden="true" />
      <aside className="w-full max-w-md transform bg-slate-950/95 text-slate-100 shadow-2xl">
        <header className="flex items-center justify-between border-b border-slate-800 px-5 py-4">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">Trait Timeline</p>
            <h3 className="text-base font-semibold text-slate-100 break-all">{traitId}</h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-300 hover:border-cyan-400 hover:text-cyan-200"
          >
            Close
          </button>
        </header>
        <div className="flex items-center gap-2 border-b border-slate-800 px-5 py-3 text-xs text-slate-300">
          <button
            type="button"
            onClick={() => downloadText(`${filenameBase}.json`, jsonText, 'application/json')}
            className="rounded-full border border-cyan-400/60 px-3 py-1 font-semibold text-cyan-200 hover:bg-cyan-400/10"
          >
            Export JSON
          </button>
          <button
            type="button"
            onClick={() => downloadText(`${filenameBase}.csv`, csvText, 'text/csv')}
            className="rounded-full border border-emerald-400/60 px-3 py-1 font-semibold text-emerald-200 hover:bg-emerald-400/10"
          >
            Export CSV
          </button>
        </div>
        <div className="max-h-[75vh] overflow-y-auto px-5 py-4 text-sm">
          {loading ? <p className="text-slate-400">Loading timeline…</p> : null}
          {error ? <p className="text-rose-300">{error}</p> : null}
          {!loading && !error && entries.length === 0 ? (
            <p className="text-slate-400">No timeline events found for this trait.</p>
          ) : null}
          <ul className="space-y-4">
            {entries.map((entry, index) => (
              <li key={`${entry.ts ?? index}-${index}`} className="rounded border border-slate-800 bg-slate-900/60 p-3">
                <p className="text-xs uppercase tracking-wide text-slate-500">{entry.ts ?? 'unknown timestamp'}</p>
                <p className="mt-1 text-sm font-semibold text-slate-100">Source: {entry.source}</p>
                {entry.reason ? <p className="mt-1 text-xs text-slate-400">Reason: {entry.reason}</p> : null}
                {entry.value !== undefined ? (
                  <p className="mt-1 text-xs text-slate-300">Value: {formatValue(entry.value)}</p>
                ) : null}
                {entry.ucn !== undefined && entry.ucn !== null ? (
                  <p className="mt-1 text-xs text-slate-300">UCN: {entry.ucn}</p>
                ) : null}
                {entry.delta_ucn !== undefined && entry.delta_ucn !== null ? (
                  <p className="mt-1 text-xs text-slate-300">Δ UCN: {entry.delta_ucn}</p>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      </aside>
    </div>
  );
}

function downloadText(filename: string, content: string, mime: string) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) {
    return '—';
  }
  if (Array.isArray(value)) {
    return value.map((entry) => formatValue(entry)).join(', ');
  }
  if (typeof value === 'object') {
    try {
      return JSON.stringify(value);
    } catch (err) {
      return String(value);
    }
  }
  return String(value);
}

function buildCsv(entries: TraitTimelineEntry[]): string {
  const header = ['ts', 'source', 'reason', 'value', 'ucn', 'delta_ucn'];
  const rows = entries.map((entry) => [
    entry.ts ?? '',
    entry.source ?? '',
    entry.reason ?? '',
    serializeValue(entry.value),
    entry.ucn ?? '',
    entry.delta_ucn ?? ''
  ]);
  return [header, ...rows]
    .map((row) => row.map((cell) => escapeCsv(String(cell ?? ''))).join(','))
    .join('\n');
}

function serializeValue(value: unknown): string {
  if (value === null || value === undefined) {
    return '';
  }
  if (typeof value === 'object') {
    try {
      return JSON.stringify(value);
    } catch (err) {
      return String(value);
    }
  }
  return String(value);
}

function escapeCsv(value: string): string {
  if (value.includes(',') || value.includes('"') || value.includes('\n')) {
    return `"${value.replace(/"/g, '""')}"`;
  }
  return value;
}
