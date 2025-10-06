'use client';

import { useCallback, useEffect, useMemo, useRef, useState, type ChangeEvent } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  fetchDraftChat,
  importDraftChatEntries,
  clearDraftChat,
  type DraftChatItem,
  type DraftImportEntry
} from '../../lib/api';

interface DraftChatPanelProps {
  userId: string;
}

type TimeframeKey = '7d' | '30d' | '90d' | 'all';

const TIMEFRAME_OPTIONS: Array<{ key: TimeframeKey; label: string; days?: number }> = [
  { key: '7d', label: 'Last 7 days', days: 7 },
  { key: '30d', label: 'Last 30 days', days: 30 },
  { key: '90d', label: 'Last 90 days', days: 90 },
  { key: 'all', label: 'All drafts' },
];

const DRAFT_TIME_FORMAT = new Intl.DateTimeFormat(undefined, {
  dateStyle: 'medium',
  timeStyle: 'short',
});

// strip one trailing slash if present
const PROVENANCE_LAB_BASE = (process.env.NEXT_PUBLIC_PROVENANCE_LAB_URL ?? '')
  .trim()
  .replace(/\/$/, '');

export function DraftChatPanel({ userId }: DraftChatPanelProps) {
  const resolvedUserId = userId.trim();
  const hasUser = Boolean(resolvedUserId);

  const [timeframe, setTimeframe] = useState<TimeframeKey>('30d');
  const [drafts, setDrafts] = useState<DraftChatItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastFetchedAt, setLastFetchedAt] = useState<number | null>(null);
  const [refreshNonce, setRefreshNonce] = useState(0);
  const [importing, setImporting] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [importSummary, setImportSummary] = useState<{ count: number; ts: number } | null>(null);
  const [clearSummary, setClearSummary] = useState<{ removed: number; ts: number } | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const sinceIso = useMemo(() => {
    if (!hasUser) return undefined;
    const option = TIMEFRAME_OPTIONS.find((entry) => entry.key === timeframe);
    if (!option || option.key === 'all' || !option.days) return undefined;
    const cutoff = Date.now() - option.days * 24 * 60 * 60 * 1000;
    return new Date(cutoff).toISOString();
  }, [hasUser, timeframe]);

  useEffect(() => {
    if (!hasUser) {
      setDrafts([]);
      setError(null);
      setLoading(false);
      setLastFetchedAt(null);
      setImportSummary(null);
      setClearSummary(null);
      setActionError(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    void fetchDraftChat(resolvedUserId, { limit: 50, since: sinceIso })
      .then((items) => {
        if (cancelled) return;
        setDrafts(items);
        setLastFetchedAt(Date.now());
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : 'Unable to load draft chat.');
        setDrafts([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [hasUser, resolvedUserId, sinceIso, refreshNonce]);

  const provenanceHref = useMemo(() => {
    if (!hasUser || !PROVENANCE_LAB_BASE) return null;
    const joiner = PROVENANCE_LAB_BASE.includes('?') ? '&' : '?';
    return `${PROVENANCE_LAB_BASE}${joiner}user_id=${encodeURIComponent(resolvedUserId)}`;
  }, [hasUser, resolvedUserId]);

  const handleRefresh = useCallback(() => {
    setRefreshNonce((v) => v + 1);
  }, []);

  const handleSelectImport = useCallback(() => {
    if (!hasUser) {
      return;
    }
    fileInputRef.current?.click();
  }, [hasUser]);

  const handleImportFile = useCallback(
    async (event: ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0] ?? null;
      event.target.value = '';
      if (!file || !hasUser) {
        return;
      }
      setImporting(true);
      setActionError(null);
      try {
        const text = await file.text();
        let parsed: unknown;
        try {
          parsed = JSON.parse(text);
        } catch (err) {
          throw new Error('Import file must be valid JSON.');
        }
        const sourceArray = Array.isArray(parsed) ? parsed : [parsed];
        const normalized: DraftImportEntry[] = [];
        sourceArray.forEach((item, index) => {
          if (!item || typeof item !== 'object') {
            return;
          }
          const record = item as Record<string, unknown>;
          const titleValue = record.title ?? record.summary ?? record.label;
          const rawContent =
            record.content ?? record.body ?? record.text ?? record.draft ?? record.markdown;
          let contentText: string;
          if (typeof rawContent === 'string') {
            contentText = rawContent;
          } else if (rawContent != null) {
            try {
              contentText = JSON.stringify(rawContent, null, 2);
            } catch {
              contentText = String(rawContent);
            }
          } else {
            contentText = '';
          }
          if (!contentText.trim()) {
            return;
          }
          const sourcePathValue = record.source_path ?? record.path;
          const entry: DraftImportEntry = {
            title: typeof titleValue === 'string' ? titleValue : undefined,
            content: contentText,
            ts:
              typeof record.ts === 'string' || typeof record.ts === 'number'
                ? (record.ts as string | number)
                : typeof (record as any).timestamp === 'string' || typeof (record as any).timestamp === 'number'
                ? ((record as any).timestamp as string | number)
                : typeof (record as any).created_at === 'string' || typeof (record as any).created_at === 'number'
                ? ((record as any).created_at as string | number)
                : null,
            source_path: typeof sourcePathValue === 'string' ? sourcePathValue : undefined
          };
          entry.title = entry.title?.trim() ? entry.title : undefined;
          normalized.push(entry);
        });

        if (normalized.length === 0) {
          throw new Error('No valid drafts found in import file.');
        }

        const imported = await importDraftChatEntries(resolvedUserId, normalized);
        setImportSummary({ count: imported, ts: Date.now() });
        setClearSummary(null);
        setActionError(imported === 0 ? 'Import completed but no drafts were added.' : null);
        setRefreshNonce((v) => v + 1);
      } catch (err) {
        setActionError(err instanceof Error ? err.message : 'Failed to import drafts.');
      } finally {
        setImporting(false);
      }
    },
    [hasUser, resolvedUserId]
  );

  const handleClearDrafts = useCallback(async () => {
    if (!hasUser) {
      return;
    }
    const confirmClear = window.confirm('Clear all draft chat entries for this user?');
    if (!confirmClear) {
      return;
    }
    setClearing(true);
    setActionError(null);
    try {
      const removed = await clearDraftChat(resolvedUserId);
      setClearSummary({ removed, ts: Date.now() });
      setImportSummary(null);
      setDrafts([]);
      setLastFetchedAt(Date.now());
      setRefreshNonce((v) => v + 1);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to clear drafts.');
    } finally {
      setClearing(false);
    }
  }, [hasUser, resolvedUserId]);

  const timestampLabel = useCallback((value: string | null | undefined) => {
    if (!value) return 'Unknown time';
    try {
      return DRAFT_TIME_FORMAT.format(new Date(value));
    } catch {
      return value;
    }
  }, []);

  return (
    <section className="rounded-3xl border border-slate-800 bg-slate-900/70 p-6 text-slate-100">
      <input
        type="file"
        ref={fileInputRef}
        accept="application/json"
        className="hidden"
        onChange={handleImportFile}
      />
      <header className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">Draft Chat</h2>
          <p className="text-sm text-slate-400">
            Planner-authored drafts queued for upcoming coaching turns.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
          <label className="flex items-center gap-2">
            <span className="uppercase tracking-wide text-slate-500">Window</span>
            <select
              value={timeframe}
              onChange={(e) => setTimeframe(e.target.value as TimeframeKey)}
              className="rounded-full border border-slate-700 bg-slate-900 px-2 py-1 text-xs text-slate-200 focus:border-cyan-400 focus:outline-none"
            >
              {TIMEFRAME_OPTIONS.map((option) => (
                <option key={option.key} value={option.key}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            onClick={handleRefresh}
            className="rounded-full border border-slate-700 px-3 py-1 font-semibold text-slate-200 hover:bg-slate-800 disabled:opacity-50"
            disabled={!hasUser || loading}
          >
            {loading ? 'Refreshing…' : 'Refresh'}
          </button>
          <button
            type="button"
            onClick={handleSelectImport}
            className="rounded-full border border-slate-700 px-3 py-1 font-semibold text-slate-200 hover:bg-slate-800 disabled:opacity-50"
            disabled={!hasUser || importing}
          >
            {importing ? 'Importing…' : 'Import (.json)'}
          </button>
          <button
            type="button"
            onClick={handleClearDrafts}
            className="rounded-full border border-rose-500/60 px-3 py-1 font-semibold text-rose-200 hover:bg-rose-500/15 disabled:opacity-50"
            disabled={!hasUser || clearing}
          >
            {clearing ? 'Clearing…' : 'Clear drafts'}
          </button>
          {provenanceHref ? (
            <a
              href={provenanceHref}
              target="_blank"
              rel="noreferrer"
              className="rounded-full border border-cyan-500/60 px-3 py-1 font-semibold text-cyan-200 hover:bg-cyan-500/10"
            >
              Open in Provenance Lab
            </a>
          ) : (
            <span className="hidden text-xs text-slate-600 md:inline">
              Set NEXT_PUBLIC_PROVENANCE_LAB_URL to enable deep link.
            </span>
          )}
        </div>
      </header>

      {hasUser && (importSummary || clearSummary || actionError) ? (
        <div className="mb-4 space-y-1 text-xs text-slate-400">
          {importSummary ? (
            <p>
              Last import: {importSummary.count}{' '}
              {importSummary.count === 1 ? 'draft' : 'drafts'} ·{' '}
              {timestampLabel(new Date(importSummary.ts).toISOString())}
            </p>
          ) : null}
          {clearSummary ? (
            <p>
              Last clear: removed {clearSummary.removed}{' '}
              {clearSummary.removed === 1 ? 'file' : 'files'} ·{' '}
              {timestampLabel(new Date(clearSummary.ts).toISOString())}
            </p>
          ) : null}
          {actionError ? <p className="text-rose-300">{actionError}</p> : null}
        </div>
      ) : null}

      {!hasUser ? (
        <p className="text-sm text-slate-500">Pick a user to load draft context.</p>
      ) : (
        <div className="space-y-4">
          {error ? <p className="text-sm text-rose-300">{error}</p> : null}
          {!error && drafts.length === 0 && !loading ? (
            <p className="text-sm text-slate-400">No planner drafts in this window yet.</p>
          ) : null}
          {loading ? <p className="text-sm text-slate-400">Syncing drafts…</p> : null}

          {drafts.map((draft) => (
            <article key={draft.id} className="space-y-3 rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
              <header className="flex flex-wrap items-baseline justify-between gap-2">
                <div>
                  <h3 className="text-sm font-semibold text-slate-200">{draft.title || 'Untitled draft'}</h3>
                  <p className="text-xs text-slate-500">{timestampLabel(draft.ts)}</p>
                </div>
                <code className="rounded-full bg-slate-900 px-2 py-1 text-[10px] text-slate-500">{draft.id}</code>
              </header>
              <div className="prose prose-invert max-w-none text-sm">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {draft.content || '_Empty draft._'}
                </ReactMarkdown>
              </div>
              {draft.source_path ? (
                <p className="text-[11px] text-slate-500">Source: {draft.source_path}</p>
              ) : null}
            </article>
          ))}

          {lastFetchedAt && drafts.length > 0 ? (
            <p className="text-[11px] text-slate-500">
              Updated {timestampLabel(new Date(lastFetchedAt).toISOString())}
            </p>
          ) : null}
        </div>
      )}
    </section>
  );
}
