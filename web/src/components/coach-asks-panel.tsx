'use client';

import { useMemo, useState } from 'react';

import type { PlannerAsk, AskAction } from '../lib/api';
import { PanelError } from './panel-error';
import { PanelSkeleton } from './panel-skeleton';
import { useI18n } from '../i18n/context';

interface CoachAsksPanelProps {
  asks: PlannerAsk[];
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  onAction?: (ask: PlannerAsk, action: AskAction, options?: { minutes?: number }) => void;
  actionPending?: Record<string, boolean>;
  actionErrors?: Record<string, string | null>;
  cached?: boolean;
}

type AskSort = 'recent' | 'confidence' | 'policy';
type AskStatusFilter = 'all' | 'pending' | 'completed';

function CachedBadge() {
  const { t } = useI18n();
  return (
    <span className="ml-2 inline-flex items-center rounded-full border border-amber-400/50 bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-200">
      {t('badge.cached')}
    </span>
  );
}

function parseSnoozeUntilMs(ask: PlannerAsk): number | null {
  const metaSource = ask.metadata?.snooze_until as unknown;
  const fallbackSource = (ask as unknown as Record<string, unknown>).snooze_until as unknown;
  const metaValue = (metaSource ?? fallbackSource) as string | number | undefined;
  if (typeof metaValue === 'number' && Number.isFinite(metaValue)) {
    return metaValue;
  }
  if (typeof metaValue === 'string') {
    const trimmed = metaValue.trim();
    if (trimmed) {
      const parsed = Date.parse(trimmed);
      if (!Number.isNaN(parsed)) {
        return parsed;
      }
    }
  }
  return null;
}

function snoozeBadgeLabel(ask: PlannerAsk): string | null {
  const minutesRaw = ask.metadata?.snoozed_minutes;
  if (typeof minutesRaw === 'number' && Number.isFinite(minutesRaw) && minutesRaw > 0) {
    return `+${minutesRaw}m`;
  }
  return null;
}

export function CoachAsksPanel({
  asks,
  loading,
  error,
  onRetry,
  onAction,
  actionPending,
  actionErrors,
  cached
}: CoachAsksPanelProps) {
  const [sortKey, setSortKey] = useState<AskSort>('recent');
  const [statusFilter, setStatusFilter] = useState<AskStatusFilter>('all');

  const rows = useMemo(() => {
    const filtered = asks.filter((ask) => {
      if (statusFilter === 'all') return true;
      const status = (ask.status || 'pending').toLowerCase();
      if (statusFilter === 'pending') {
        return status === 'pending';
      }
      return status !== 'pending';
    });

    const nowMs = Date.now();
    const sorted = [...filtered].sort((a, b) => {
      const aSnoozeMs = parseSnoozeUntilMs(a);
      const bSnoozeMs = parseSnoozeUntilMs(b);
      const aSnoozed = aSnoozeMs != null && aSnoozeMs > nowMs;
      const bSnoozed = bSnoozeMs != null && bSnoozeMs > nowMs;
      if (aSnoozed !== bSnoozed) {
        return aSnoozed ? 1 : -1;
      }
      if (aSnoozed && bSnoozed && aSnoozeMs !== bSnoozeMs) {
        return aSnoozeMs - bSnoozeMs;
      }
      if (sortKey === 'confidence') {
        return b.confidence - a.confidence;
      }
      if (sortKey === 'policy') {
        const aNeedsReview = a.policy?.approve?.allowed === false ? 1 : 0;
        const bNeedsReview = b.policy?.approve?.allowed === false ? 1 : 0;
        if (aNeedsReview !== bNeedsReview) {
          return bNeedsReview - aNeedsReview;
        }
        return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
      }
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
    });

    return sorted;
  }, [asks, sortKey, statusFilter]);

  const hasRows = rows.length > 0;
  const showSkeleton = loading && !error;

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/60 shadow-xl" aria-live="polite">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 px-5 py-4">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
            Coach Asks
            {cached ? <CachedBadge /> : null}
          </h2>
          {!hasRows && !loading && !error ? (
            <p className="text-xs text-slate-500">Planner is caught up. No outstanding asks right now.</p>
          ) : null}
        </div>
        <div className="flex items-center gap-2 text-xs">
          <label className="flex items-center gap-1 text-slate-400">
            Sort
            <select
              className="rounded-md border border-slate-700 bg-slate-900 px-2 py-1 text-xs text-slate-100"
              value={sortKey}
              onChange={(event) => setSortKey(event.target.value as AskSort)}
            >
              <option value="recent">Newest first</option>
              <option value="confidence">Highest confidence</option>
              <option value="policy">Needs approval first</option>
            </select>
          </label>
          <label className="flex items-center gap-1 text-slate-400">
            Status
            <select
              className="rounded-md border border-slate-700 bg-slate-900 px-2 py-1 text-xs text-slate-100"
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value as AskStatusFilter)}
            >
              <option value="all">All</option>
              <option value="pending">Pending</option>
              <option value="completed">Completed</option>
            </select>
          </label>
          {loading ? <span className="text-xs text-slate-500">Refreshing…</span> : null}
        </div>
      </header>
      <div className="max-h-80 overflow-auto px-5 py-5 text-sm">
        {error ? <PanelError message={error} onRetry={onRetry} /> : null}
        {showSkeleton ? <PanelSkeleton rows={4} columns={3} className="py-2" /> : null}
        {!hasRows && !showSkeleton ? <p className="text-slate-500">No asks match the current filters.</p> : null}
        {hasRows ? (
          <table className="min-w-full divide-y divide-slate-800 text-left text-sm text-slate-100" role="table">
            <thead className="bg-slate-950/70 text-xs uppercase tracking-wide text-slate-400">
              <tr>
                <th scope="col" className="px-3 py-3">Container</th>
                <th scope="col" className="px-3 py-3">Ask</th>
                <th scope="col" className="px-3 py-3">Confidence</th>
                <th scope="col" className="px-3 py-3">TTL</th>
                <th scope="col" className="px-3 py-3">Snooze</th>
                <th scope="col" className="px-3 py-3">Governance</th>
                <th scope="col" className="px-3 py-3">Status</th>
                <th scope="col" className="px-3 py-3">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {rows.map((ask) => {
                const detail = typeof ask.metadata?.body === 'string' ? ask.metadata.body : '';
                const originalStatus = typeof ask.metadata?.original_status === 'string' ? ask.metadata.original_status : null;
                const snoozeLabel = snoozeBadgeLabel(ask);
                const snoozeUntilMs = parseSnoozeUntilMs(ask);
                const snoozeUntilText =
                  snoozeUntilMs != null
                    ? new Date(snoozeUntilMs).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                    : null;
                const statusToken = (ask.status || 'pending').toLowerCase();
                const isCompleted = statusToken !== 'pending';
                const pending = Boolean(actionPending?.[ask.id]);
                const errorMessage = actionErrors?.[ask.id] ?? null;
                return (
                  <tr key={ask.id} className="hover:bg-slate-900/60" data-testid="ask-row" data-ask-id={ask.id}>
                  <td className="px-3 py-3 text-slate-300">{ask.container || '—'}</td>
                  <td className="px-3 py-3">
                    <div className="font-medium text-slate-100">{ask.phrasing_stub || 'Untitled ask'}</div>
                    <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-400">
                      <span className="rounded-full bg-slate-800 px-2 py-0.5 uppercase tracking-wide">
                        {ask.ask_type}
                      </span>
                      {ask.gap ? (
                        <span className="rounded-full bg-slate-800 px-2 py-0.5">Gap: {ask.gap}</span>
                      ) : null}
                    </div>
                    {detail ? (
                      <p className="mt-2 whitespace-pre-line text-xs text-slate-400">{detail}</p>
                    ) : null}
                    {originalStatus && originalStatus !== ask.status ? (
                      <p className="mt-1 text-[11px] uppercase tracking-wide text-slate-500">
                        Source status: {originalStatus}
                      </p>
                    ) : null}
                  </td>
                  <td className="px-3 py-3 text-slate-200">{(ask.confidence * 100).toFixed(0)}%</td>
                  <td className="px-3 py-3">
                    <span className="inline-flex items-center gap-1 rounded-full bg-slate-800 px-2 py-0.5 text-xs text-slate-300">
                      ⏱ {ask.ttl_minutes || 0}m
                    </span>
                  </td>
                  <td className="px-3 py-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="inline-flex items-center gap-1 rounded-full bg-slate-800 px-2 py-0.5 text-xs text-slate-300">
                        😴 {ask.snooze_minutes || ask.default_snooze_minutes || 0}m
                      </span>
                      {snoozeLabel ? (
                        <span className="inline-flex items-center gap-1 rounded-full border border-cyan-500/40 bg-cyan-500/10 px-2 py-0.5 text-xs text-cyan-100">
                          {snoozeLabel}
                        </span>
                      ) : null}
                      {snoozeUntilText ? (
                        <span className="inline-flex items-center gap-1 rounded-full border border-cyan-500/30 bg-slate-800 px-2 py-0.5 text-xs text-cyan-200">
                          until {snoozeUntilText}
                        </span>
                      ) : null}
                    </div>
                  </td>
                  <td className="px-3 py-3">
                    {ask.policy?.approve?.allowed === false ? (
                      <PolicyBadge
                        label="🔒 Needs approval"
                        reason={ask.policy?.approve?.reason ?? 'Requires manual approval'}
                        tone="danger"
                      />
                    ) : ask.sensitivity ? (
                      <PolicyBadge label="🔒 Sensitive" tone="danger" />
                    ) : (
                      <span className="text-xs text-slate-500">—</span>
                    )}
                  </td>
                  <td className="px-3 py-3">
                    <span className="inline-flex items-center gap-1 rounded-full bg-slate-800 px-2 py-0.5 text-xs text-slate-300">
                      {ask.status ? ask.status : 'pending'}
                    </span>
                  </td>
                  <td className="px-3 py-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <button
                        type="button"
                        className="rounded-full border border-cyan-500/40 bg-cyan-500/10 px-3 py-1 text-[11px] text-cyan-100 shadow-sm transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-400 hover:bg-cyan-500/20 disabled:cursor-not-allowed disabled:opacity-60"
                        disabled={pending || isCompleted}
                        onClick={() => onAction?.(ask, 'approve')}
                      >
                        Approve
                      </button>
                      <button
                        type="button"
                        className="rounded-full border border-slate-700 px-3 py-1 text-[11px] text-slate-200 transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-400 hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
                        disabled={pending || isCompleted}
                        onClick={() => onAction?.(ask, 'snooze', { minutes: 15 })}
                      >
                        Snooze 15m
                      </button>
                      <button
                        type="button"
                        className="rounded-full border border-slate-700 px-3 py-1 text-[11px] text-slate-200 transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-400 hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
                        disabled={pending || isCompleted}
                        onClick={() => onAction?.(ask, 'snooze', { minutes: 60 })}
                      >
                        Snooze 60m
                      </button>
                      <button
                        type="button"
                        className="rounded-full border border-slate-700 px-3 py-1 text-[11px] text-slate-200 transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-400 hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
                        disabled={pending || isCompleted}
                        onClick={() => onAction?.(ask, 'skip')}
                      >
                        Skip
                      </button>
                      {onRetry ? (
                        <button
                          type="button"
                          onClick={onRetry}
                          className="rounded-full border border-slate-700 px-3 py-1 text-[11px] text-slate-200 transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-400 hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
                          disabled={pending}
                        >
                          Refresh
                        </button>
                      ) : null}
                    </div>
                    {pending ? (
                      <p className="mt-2 flex items-center gap-2 text-[11px] text-cyan-200">
                        <RowSpinner />
                        Processing…
                      </p>
                    ) : null}
                    {errorMessage ? (
                      <p className="mt-2 text-xs text-rose-300">{errorMessage}</p>
                    ) : null}
                  </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        ) : null}
      </div>
    </section>
  );
}

function PolicyBadge({ label, reason, tone }: { label: string; reason?: string; tone: 'danger' | 'neutral' }) {
  const baseClass = tone === 'danger' ? 'bg-rose-500/15 text-rose-200' : 'bg-slate-800 text-slate-300';
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs ${baseClass}`}
      title={reason}
      aria-label={reason ? `${label}. ${reason}` : label}
    >
      {label}
    </span>
  );
}

function RowSpinner() {
  return <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-cyan-400 border-t-transparent" />;
}
