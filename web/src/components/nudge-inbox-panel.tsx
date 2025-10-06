'use client';

import { useMemo, useState } from 'react';

import type { NudgeAction, NudgeItem } from '../lib/api';
import { PanelError } from './panel-error';
import { PanelSkeleton } from './panel-skeleton';
import { useI18n } from '../i18n/context';

interface NudgeInboxPanelProps {
  nudges: NudgeItem[];
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  onAction?: (nudge: NudgeItem, action: NudgeAction) => void;
  actionPending?: Record<string, boolean>;
  actionErrors?: Record<string, string | null>;
  cached?: boolean;
}

type NudgeStatusFilter = 'all' | 'pending' | 'completed';

function CachedBadge() {
  const { t } = useI18n();
  return (
    <span className="ml-2 inline-flex items-center rounded-full border border-amber-400/50 bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-200">
      {t('badge.cached')}
    </span>
  );
}

export function NudgeInboxPanel({
  nudges,
  loading,
  error,
  onRetry,
  onAction,
  actionPending,
  actionErrors,
  cached
}: NudgeInboxPanelProps) {
  const [statusFilter, setStatusFilter] = useState<NudgeStatusFilter>('all');

  const rows = useMemo(() => {
    const filtered = nudges.filter((nudge) => {
      if (statusFilter === 'all') return true;
      const status = (nudge.status || 'pending').toLowerCase();
      if (statusFilter === 'pending') return status === 'pending';
      return status !== 'pending';
    });

    return [...filtered].sort((a, b) => {
      const aTs = Date.parse(a.created_ts || '') || 0;
      const bTs = Date.parse(b.created_ts || '') || 0;
      return bTs - aTs;
    });
  }, [nudges, statusFilter]);

  const hasRows = rows.length > 0;
  const showSkeleton = loading && !error;

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/60 shadow-xl" aria-live="polite">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 px-5 py-4">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
            Nudge Inbox
            {cached ? <CachedBadge /> : null}
          </h2>
          {!hasRows && !loading && !error ? (
            <p className="text-xs text-slate-500">No nudges waiting. Coach is up to date.</p>
          ) : null}
        </div>
        <div className="flex items-center gap-2 text-xs text-slate-400">
          <label className="flex items-center gap-1">
            Status
            <select
              className="rounded-md border border-slate-700 bg-slate-900 px-2 py-1 text-xs text-slate-100"
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value as NudgeStatusFilter)}
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
        {!hasRows && !showSkeleton ? <p className="text-slate-500">No nudges match the current filters.</p> : null}
        {hasRows ? (
          <ul className="space-y-4">
            {rows.map((nudge) => {
              const pending = Boolean(actionPending?.[nudge.id]);
              const errorMessage = actionErrors?.[nudge.id] ?? null;
              const acceptAllowed = nudge.policy?.accept?.allowed ?? true;
              const dismissAllowed = nudge.policy?.dismiss?.allowed ?? true;
              const undoAllowed = nudge.policy?.undo?.allowed ?? false;
              const detail = typeof nudge.metadata?.body === 'string' ? nudge.metadata.body : '';
              const originalStatus = typeof nudge.metadata?.original_status === 'string' ? nudge.metadata.original_status : null;

              return (
                <li key={nudge.id} className="rounded-xl border border-slate-800 bg-slate-950/50 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-slate-100">{nudge.text || 'Nudge details unavailable'}</p>
                      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-400">
                        <span className="rounded-full bg-slate-800 px-2 py-0.5 uppercase tracking-wide">{nudge.kind}</span>
                        <PolicyBadge
                          label={`TTL ${nudge.ttl_minutes ?? 0}m`}
                          className="inline-flex items-center gap-1 bg-slate-800 text-slate-300"
                        />
                        <PolicyBadge
                          label={`Snooze ${nudge.snooze_minutes ?? 0}m`}
                          className="inline-flex items-center gap-1 bg-slate-800 text-slate-300"
                        />
                        <PolicyBadge
                          label={`Status: ${nudge.status ?? 'pending'}`}
                          className="inline-flex items-center gap-1 bg-slate-800 text-slate-300"
                        />
                      </div>
                      {detail ? (
                        <p className="mt-2 whitespace-pre-line text-xs text-slate-400">{detail}</p>
                      ) : null}
                      <p className="mt-1 text-xs text-slate-500">Created {nudge.created_ts || '—'}</p>
                      {originalStatus && originalStatus !== nudge.status ? (
                        <p className="text-[11px] uppercase tracking-wide text-slate-500">
                          Source status: {originalStatus}
                        </p>
                      ) : null}
                    </div>
                    <div className="flex flex-col items-end gap-2">
                      <PolicyButton
                        label="Accept"
                        disabled={pending || !acceptAllowed}
                        pending={pending}
                        reason={acceptAllowed ? undefined : nudge.policy?.accept?.reason ?? undefined}
                        tone="success"
                        onClick={() => onAction?.(nudge, 'accept')}
                      />
                      <PolicyButton
                        label="Dismiss"
                        disabled={pending || !dismissAllowed}
                        pending={pending}
                        reason={dismissAllowed ? undefined : nudge.policy?.dismiss?.reason ?? undefined}
                        tone="neutral"
                        onClick={() => onAction?.(nudge, 'dismiss')}
                      />
                      <PolicyButton
                        label="Undo"
                        disabled={pending || !undoAllowed}
                        pending={pending}
                        reason={undoAllowed ? undefined : nudge.policy?.undo?.reason ?? undefined}
                        tone="info"
                        onClick={() => onAction?.(nudge, 'undo')}
                      />
                    </div>
                  </div>
                  {pending ? (
                    <p className="mt-3 flex items-center gap-2 text-[11px] text-cyan-200">
                      <RowSpinner />
                      Processing…
                    </p>
                  ) : null}
                  {errorMessage ? (
                    <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-rose-300">
                      <span>{errorMessage}</span>
                      {onRetry ? (
                        <button
                          type="button"
                          onClick={onRetry}
                          className="rounded-full border border-rose-400/60 px-2 py-1 text-[11px] font-semibold text-rose-100 hover:bg-rose-500/10"
                        >
                          Retry fetch
                        </button>
                      ) : null}
                    </div>
                  ) : null}
                </li>
              );
            })}
          </ul>
        ) : null}
      </div>
    </section>
  );
}

function PolicyBadge({ label, className }: { label: string; className?: string }) {
  return <span className={`rounded-full px-2 py-0.5 ${className ?? 'bg-slate-800 text-slate-300'}`}>{label}</span>;
}

function PolicyButton({
  label,
  disabled,
  pending,
  reason,
  tone,
  onClick
}: {
  label: string;
  disabled: boolean;
  pending: boolean;
  reason?: string;
  tone: 'success' | 'neutral' | 'info';
  onClick: () => void;
}) {
  const baseStyle =
    tone === 'success'
      ? 'border-emerald-400/60 text-emerald-200 hover:bg-emerald-400/10'
      : tone === 'info'
        ? 'border-cyan-400/60 text-cyan-200 hover:bg-cyan-400/10'
        : 'border-slate-500 text-slate-200 hover:bg-slate-700/40';
  const tooltip = disabled ? (pending ? 'Action in progress' : reason ?? 'Action disabled by policy') : undefined;
  const ariaLabel = tooltip ? `${label}. ${tooltip}` : label;

  return (
    <button
      type="button"
      className={`rounded-full border px-3 py-1 text-xs font-semibold transition disabled:cursor-not-allowed disabled:opacity-40 ${baseStyle}`}
      disabled={disabled}
      title={tooltip}
      aria-label={ariaLabel}
      onClick={onClick}
    >
      {pending ? 'Working…' : label}
    </button>
  );
}

function RowSpinner() {
  return <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-cyan-400 border-t-transparent" />;
}
