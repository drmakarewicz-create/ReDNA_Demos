'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';

import { listSnapshots, snapshotUser, type SnapshotItem } from '../../lib/api';
import { readCache, writeCache } from '../../lib/offline-cache';
import { PanelError } from '../panel-error';
import { useI18n } from '../../i18n/context';

interface SnapshotsPanelProps {
  userId: string;
  onNotify?: (message: string, tone?: 'success' | 'info' | 'warning' | 'error') => void;
  refreshToken?: number;
  onCachedChange?: (cached: boolean) => void;
}

const CORE_API_BASE = (process.env.NEXT_PUBLIC_CORE_API_BASE ?? '').replace(/\/$/, '');
const PROVENANCE_LAB_BASE = process.env.NEXT_PUBLIC_PROVENANCE_LAB_URL ?? 'http://127.0.0.1:8501/?tab=provenance';

function CachedBadge() {
  const { t } = useI18n();
  return (
    <span className="ml-2 inline-flex items-center rounded-full border border-amber-400/50 bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-200">
      {t('badge.cached')}
    </span>
  );
}

export function SnapshotsPanel({ userId, onNotify, refreshToken = 0, onCachedChange }: SnapshotsPanelProps) {
  const [snapshots, setSnapshots] = useState<SnapshotItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [cached, setCached] = useState(false);

  const resolvedUser = userId.trim();

  const refreshSnapshots = useCallback(() => {
    if (!resolvedUser) {
      setSnapshots([]);
      setError(null);
      setCached(false);
      onCachedChange?.(false);
      setLoading(false);
      return () => {};
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    setCached(false);
    onCachedChange?.(false);
    void listSnapshots(resolvedUser)
      .then((items) => {
        if (!cancelled) {
          setSnapshots(items);
          setCached(false);
          onCachedChange?.(false);
          writeCache('snapshots', resolvedUser, items);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          const cachedPayload = readCache<SnapshotItem[]>('snapshots', resolvedUser);
          if (cachedPayload !== null) {
            setSnapshots(cachedPayload);
            setError(null);
            setCached(true);
            onCachedChange?.(true);
          } else {
            const message = err instanceof Error ? err.message : 'Unable to load snapshots.';
            setError(message);
            setCached(false);
            onCachedChange?.(false);
          }
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [resolvedUser]);

  useEffect(() => {
    const cleanup = refreshSnapshots();
    return () => {
      if (typeof cleanup === 'function') {
        cleanup();
      }
      setCached(false);
      onCachedChange?.(false);
    };
  }, [onCachedChange, refreshSnapshots, refreshToken]);

  const handleCreateSnapshot = useCallback(async () => {
    if (!resolvedUser) {
      return;
    }
    setCreating(true);
    setError(null);
    try {
      const result = await snapshotUser(resolvedUser);
      const versionLabel = result.version ? ` (v${result.version})` : '';
      const message = `Created snapshot${versionLabel}.`;
      onNotify?.(message, 'success');

      if (result.bundle) {
        const jsonText = JSON.stringify(result.bundle, null, 2);
        const filename = result.filename ?? `snapshot_${resolvedUser}_${Date.now()}.json`;
        downloadText(filename, jsonText, 'application/json');
      }

      refreshSnapshots();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Snapshot creation failed.';
      setError(message);
      onNotify?.(message, 'error');
    } finally {
      setCreating(false);
    }
  }, [onNotify, refreshSnapshots, resolvedUser]);

  const ready = Boolean(resolvedUser);
  const totalSnapshots = snapshots.length;

  const itemsWithDiff = useMemo(() => {
    return snapshots.map((item, index) => {
      const downloadUrl = item.download_url ? `${CORE_API_BASE}${item.download_url}` : undefined;
      const diffUrl = `${PROVENANCE_LAB_BASE}&user_id=${encodeURIComponent(resolvedUser)}&snapshot=${encodeURIComponent(item.filename)}`;
      return {
        ...item,
        downloadUrl,
        diffUrl,
        isLatest: index === 0
      };
    });
  }, [snapshots, resolvedUser]);

  return (
    <section className="rounded-3xl border border-slate-800 bg-slate-900/70 p-6 text-slate-100">
      <header className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">
            Snapshots
            {cached ? <CachedBadge /> : null}
          </h2>
          <p className="text-sm text-slate-400">
            Create checkpoint bundles and download them for Explorer / provenance comparisons.
          </p>
        </div>
        <button
          type="button"
          onClick={handleCreateSnapshot}
          className="rounded-full border border-cyan-500/60 px-3 py-2 text-xs font-semibold text-cyan-200 hover:bg-cyan-500/10 disabled:opacity-40"
          disabled={!ready || creating}
        >
          {creating ? 'Creating…' : 'Create new snapshot'}
        </button>
      </header>
      {!ready ? (
        <p className="text-sm text-slate-500">Pick a user to manage snapshots.</p>
      ) : (
        <>
          {error ? <PanelError message={error} onRetry={refreshSnapshots} /> : null}
          {loading ? <p className="text-sm text-slate-400">Loading snapshots…</p> : null}
          {!loading && totalSnapshots === 0 ? (
            <p className="text-sm text-slate-400">No snapshots yet. Create one to capture the user&apos;s current state.</p>
          ) : null}
          <div className="mt-4 space-y-3">
            {itemsWithDiff.map((snapshot) => (
              <article
                key={snapshot.filename}
                className="flex flex-col gap-3 rounded-2xl border border-slate-800 bg-slate-950/50 p-4 text-sm text-slate-200 shadow-sm"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="font-semibold text-slate-100">{snapshot.filename}</p>
                    <p className="text-xs text-slate-400">
                      {snapshot.version ? `Version ${snapshot.version}` : 'Version unknown'} ·{' '}
                      {snapshot.generated_at ? formatRelative(snapshot.generated_at) : 'time unknown'}
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
                    <span>{formatSize(snapshot.size)}</span>
                  </div>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  {snapshot.downloadUrl ? (
                    <a
                      href={snapshot.downloadUrl}
                      className="inline-flex items-center gap-2 rounded-full border border-slate-700 px-3 py-1 text-xs font-semibold text-slate-200 hover:bg-slate-800"
                    >
                      Download
                    </a>
                  ) : null}
                  {!snapshot.isLatest ? (
                    <a
                      href={snapshot.diffUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-2 rounded-full border border-slate-700 px-3 py-1 text-xs font-semibold text-slate-200 hover:bg-slate-800"
                    >
                      Diff with latest
                    </a>
                  ) : null}
                </div>
              </article>
            ))}
          </div>
        </>
      )}
    </section>
  );
}

function formatRelative(value: string): string {
  try {
    const epoch = Date.parse(value);
    if (Number.isNaN(epoch)) {
      return value;
    }
    const now = Date.now();
    const diff = epoch - now;
    const formatter = new Intl.RelativeTimeFormat('en', { numeric: 'auto' });
    const minutes = Math.round(diff / (1000 * 60));
    if (Math.abs(minutes) < 1) {
      return 'just now';
    }
    if (Math.abs(minutes) < 60) {
      return formatter.format(minutes, 'minutes');
    }
    const hours = Math.round(diff / (1000 * 60 * 60));
    if (Math.abs(hours) < 24) {
      return formatter.format(hours, 'hours');
    }
    const days = Math.round(diff / (1000 * 60 * 60 * 24));
    return formatter.format(days, 'days');
  } catch (error) {
    return value;
  }
}

function formatSize(size: number | null | undefined): string {
  if (typeof size !== 'number' || Number.isNaN(size) || size <= 0) {
    return '—';
  }
  if (size < 1024) {
    return `${size} B`;
  }
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

function downloadText(filename: string, content: string, mime: string): void {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
