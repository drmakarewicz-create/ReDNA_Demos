'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import {
  buildPadnaResultUrl,
  createPadnaRenderJob,
  fetchPadnaRenderStatus,
  listPadnaRenderJobs,
  listUserMedia,
  uploadUserMedia,
  type PadnaRenderJob,
  type PadnaRenderJobState,
  type UserMediaItem
} from '../../lib/api';
import { PanelError } from '../panel-error';

interface PadnaPanelProps {
  userId: string;
  refreshToken?: number;
}

const CORE_API_BASE = (process.env.NEXT_PUBLIC_CORE_API_BASE ?? '').replace(/\/$/, '');

export function PadnaPanel({ userId, refreshToken = 0 }: PadnaPanelProps) {
  const [mediaItems, setMediaItems] = useState<UserMediaItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [selectedMediaId, setSelectedMediaId] = useState<string | null>(null);
  const [showMappingPreview, setShowMappingPreview] = useState(false);
  const [showMetadataPreview, setShowMetadataPreview] = useState(false);
  const [renderJob, setRenderJob] = useState<PadnaRenderJob | null>(null);
  const [renderPreviewUrl, setRenderPreviewUrl] = useState<string | null>(null);
  const [renderError, setRenderError] = useState<string | null>(null);
  const [rendering, setRendering] = useState(false);
  const [renderHistory, setRenderHistory] = useState<PadnaRenderJob[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const inputImageRef = useRef<HTMLInputElement | null>(null);
  const inputJsonRef = useRef<HTMLInputElement | null>(null);
  const pollTimerRef = useRef<number | null>(null);
  const padnaAnnouncedRef = useRef<Set<string>>(new Set());

  const clearPollTimer = useCallback(() => {
    if (pollTimerRef.current != null) {
      window.clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, []);

  const resetRenderState = useCallback(() => {
    clearPollTimer();
    setRenderJob(null);
    setRenderPreviewUrl(null);
    setRenderError(null);
    setRendering(false);
  }, [clearPollTimer]);

  const resolvedUserId = userId.trim();
  const canInteract = Boolean(resolvedUserId);

  useEffect(() => () => clearPollTimer(), [clearPollTimer]);

  useEffect(() => {
    if (!resolvedUserId) {
      resetRenderState();
    }
    padnaAnnouncedRef.current.clear();
  }, [resolvedUserId, resetRenderState]);

  const refreshMedia = useCallback(() => {
    if (!resolvedUserId) {
      setMediaItems([]);
      setError(null);
      setLoading(false);
      setSelectedMediaId(null);
      setShowMappingPreview(false);
      setShowMetadataPreview(false);
      resetRenderState();
      return () => {};
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    void listUserMedia(resolvedUserId)
      .then((items) => {
        if (!cancelled) {
          setMediaItems(items);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Unable to load media.');
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
  }, [resolvedUserId, resetRenderState]);

  const loadHistory = useCallback(
    async (cancelState?: { cancelled: boolean }) => {
      if (!resolvedUserId) {
        if (!cancelState?.cancelled) {
          setRenderHistory([]);
          setHistoryError(null);
          setHistoryLoading(false);
        }
        return;
      }

      if (!cancelState?.cancelled) {
        setHistoryLoading(true);
        setHistoryError(null);
      }

      try {
        const items = await listPadnaRenderJobs(resolvedUserId, 10);
        if (cancelState?.cancelled) {
          return;
        }
        setRenderHistory(items);
      } catch (err) {
        if (cancelState?.cancelled) {
          return;
        }
        setHistoryError(err instanceof Error ? err.message : 'Unable to load render history.');
      } finally {
        if (cancelState?.cancelled) {
          return;
        }
        setHistoryLoading(false);
      }
    },
    [resolvedUserId]
  );

  useEffect(() => {
    return refreshMedia();
  }, [refreshMedia, refreshToken]);

  useEffect(() => {
    const cancelState = { cancelled: false };
    void loadHistory(cancelState);
    return () => {
      cancelState.cancelled = true;
    };
  }, [loadHistory, refreshToken]);

  useEffect(() => {
    setSelectedMediaId((prev) => (prev && mediaItems.some((item) => item.id === prev) ? prev : null));
  }, [mediaItems]);

  useEffect(() => {
    setShowMappingPreview(false);
    setShowMetadataPreview(false);
    clearPollTimer();
    setRenderJob(null);
    setRenderPreviewUrl(null);
    setRenderError(null);
    setRendering(false);
  }, [selectedMediaId, clearPollTimer]);

  const handleUpload = useCallback(
    async (file: File | null) => {
      if (!file || !resolvedUserId) {
        return;
      }
      setUploading(true);
      setError(null);
      try {
        const item = await uploadUserMedia(resolvedUserId, file);
        setMediaItems((prev) => [item, ...prev.filter((entry) => entry.id !== item.id)]);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Upload failed.');
      } finally {
        setUploading(false);
      }
    },
    [resolvedUserId]
  );

  const triggerImageUpload = useCallback(() => {
    inputImageRef.current?.click();
  }, []);

  const triggerJsonUpload = useCallback(() => {
    inputJsonRef.current?.click();
  }, []);

  const announcePadnaCompletion = useCallback(
    (job: PadnaRenderJob) => {
      if (job.state !== 'done') {
        return;
      }
      const key = job.id || `${job.user_id}-${job.created_at ?? ''}`;
      if (!key) {
        return;
      }
      const announced = padnaAnnouncedRef.current;
      if (announced.has(key)) {
        return;
      }
      announced.add(key);
      try {
        window.dispatchEvent(
          new CustomEvent('hc-padna-render-complete', {
            detail: {
              userId: job.user_id ?? resolvedUserId,
              jobId: job.id,
              resultFilename: job.result_filename ?? null
            }
          })
        );
      } catch (eventError) {
        console.warn('Failed to dispatch PaDNA render completion event', eventError);
      }
    },
    [resolvedUserId]
  );

  const pollPadnaStatus = useCallback(
    async (jobId: string) => {
      try {
        const status = await fetchPadnaRenderStatus(jobId, resolvedUserId);
        setRenderJob(status);
        if (status.state === 'done') {
          clearPollTimer();
          setRendering(false);
          setRenderError(null);
          setRenderPreviewUrl(buildPadnaResultUrl(status));
          announcePadnaCompletion(status);
          void loadHistory();
        } else if (status.state === 'error') {
          clearPollTimer();
          setRendering(false);
          setRenderPreviewUrl(null);
          setRenderError(status.error ?? 'Render failed.');
          void loadHistory();
        } else {
          setRenderPreviewUrl(null);
          clearPollTimer();
          pollTimerRef.current = window.setTimeout(() => {
            void pollPadnaStatus(status.id);
          }, 900);
        }
      } catch (err) {
        clearPollTimer();
        setRendering(false);
        setRenderPreviewUrl(null);
        setRenderError(err instanceof Error ? err.message : 'Unable to check render status.');
      }
    },
    [announcePadnaCompletion, clearPollTimer, loadHistory, resolvedUserId]
  );

  const handleRender = useCallback(async () => {
    if (!resolvedUserId || !selectedMediaId) {
      return;
    }
    const selected = mediaItems.find((entry) => entry.id === selectedMediaId) ?? null;
    if (!selected) {
      return;
    }

    const metadata =
      selected.metadata && typeof selected.metadata === 'object'
        ? (selected.metadata as Record<string, unknown>)
        : {};

    const bundle = {
      profile: {
        label: selected.label ?? selected.original_name ?? 'PaDNA preview',
        source_media_id: selected.id ?? null,
        content_type: selected.content_type ?? null
      },
      palette: {
        primary: typeof metadata.palette === 'string' ? metadata.palette : 'demo-neutral',
        accent: typeof metadata.accent === 'string' ? metadata.accent : 'cyan'
      },
      notes: {
        filename: selected.original_name ?? null,
        uploaded_ts: selected.uploaded_ts ?? null
      }
    };

    setRendering(true);
    setRenderError(null);
    setRenderPreviewUrl(null);
    clearPollTimer();

    try {
      const job = await createPadnaRenderJob(resolvedUserId, bundle);
      setRenderJob(job);
      if (job.state === 'done') {
        setRenderPreviewUrl(buildPadnaResultUrl(job));
        setRendering(false);
        announcePadnaCompletion(job);
      } else if (job.state === 'error') {
        setRendering(false);
        setRenderError(job.error ?? 'Render failed.');
      } else {
        pollTimerRef.current = window.setTimeout(() => {
          void pollPadnaStatus(job.id);
        }, 400);
      }
      void loadHistory();
    } catch (err) {
      setRendering(false);
      setRenderError(err instanceof Error ? err.message : 'Unable to start render.');
    }
  }, [announcePadnaCompletion, resolvedUserId, selectedMediaId, mediaItems, clearPollTimer, loadHistory, pollPadnaStatus]);

  const previewItems = useMemo(() => mediaItems.slice(0, 12), [mediaItems]);
  const selectedItem = useMemo(
    () => (selectedMediaId ? mediaItems.find((entry) => entry.id === selectedMediaId) ?? null : null),
    [mediaItems, selectedMediaId]
  );
  const isJsonSelected = Boolean(selectedItem?.content_type?.toLowerCase().includes('json'));
  const renderProgress = renderJob?.progress != null ? Math.round((renderJob.progress || 0) * 100) : null;
  const renderButtonLabel = rendering ? 'Rendering…' : renderJob?.state === 'done' ? 'Re-render bundle' : 'Render bundle';
  const renderDisabled = !canInteract || !selectedItem || rendering;
  const renderDownloadName = renderJob?.result_filename ?? 'padna-render.png';
  const renderStatusMessage = useMemo(() => {
    if (renderError) {
      return `Render failed: ${renderError}`;
    }
    if (!renderJob) {
      return 'Generate a PaDNA preview bundle from the selected asset.';
    }
    if (renderJob.state === 'done') {
      return 'Render complete. Preview available below.';
    }
    if (renderJob.state === 'error') {
      return 'Render failed. Try again.';
    }
    return `Rendering… ${renderProgress ?? 0}%`;
  }, [renderError, renderJob, renderProgress]);
  const renderStorageHint = useMemo(() => {
    if (renderJob?.state !== 'done') {
      return null;
    }
    if (renderJob.storage_path && renderJob.storage_path.trim()) {
      return renderJob.storage_path;
    }
    return renderJob.id ? `renders/${renderJob.id}/` : null;
  }, [renderJob]);

  if (!resolvedUserId) {
    return (
      <section className="rounded-3xl border border-slate-800 bg-slate-900/70 p-6 text-slate-300">
        <header className="mb-3">
          <h2 className="text-lg font-semibold text-slate-100">PaDNA Media Tools</h2>
          <p className="text-sm text-slate-400">Pick a user to upload reference imagery or bundle JSON for PaDNA refinement.</p>
        </header>
        <p className="text-sm text-slate-500">No active user selected.</p>
      </section>
    );
  }

  return (
    <section className="rounded-3xl border border-slate-800 bg-slate-900/70 p-6 text-slate-100">
      <header className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">PaDNA Media Tools</h2>
          <p className="text-sm text-slate-400">Upload imagery or bundle JSON, then hand off to the visual DNA pipeline.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <input
            ref={inputImageRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0] ?? null;
              event.target.value = '';
              void handleUpload(file);
            }}
          />
          <input
            ref={inputJsonRef}
            type="file"
            accept="application/json,.json"
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0] ?? null;
              event.target.value = '';
              void handleUpload(file);
            }}
          />
          <button
            type="button"
            onClick={triggerImageUpload}
            className="rounded-full border border-cyan-500/60 px-3 py-2 text-xs font-semibold text-cyan-200 hover:bg-cyan-500/10 disabled:opacity-40"
            disabled={uploading || !canInteract}
          >
            {uploading ? 'Uploading…' : 'Upload image'}
          </button>
          <button
            type="button"
            onClick={triggerJsonUpload}
            className="rounded-full border border-slate-700 px-3 py-2 text-xs font-semibold text-slate-200 hover:bg-slate-800 disabled:opacity-40"
            disabled={uploading || !canInteract}
          >
            Upload JSON
          </button>
        </div>
      </header>
      <PadnaToolbar
        hasSelection={Boolean(selectedItem)}
        selectedItem={selectedItem}
        isJsonSelected={isJsonSelected}
        showMapping={showMappingPreview}
        showMetadata={showMetadataPreview}
        onToggleMapping={() => setShowMappingPreview((prev) => !prev)}
        onToggleMetadata={() => setShowMetadataPreview((prev) => !prev)}
      />
      {error ? <PanelError message={error} onRetry={() => void refreshMedia()} /> : null}
      {loading ? <p className="text-sm text-slate-400">Loading media…</p> : null}
      {!loading && previewItems.length === 0 ? (
        <p className="text-sm text-slate-400">No media uploaded yet. Start by adding imagery or JSON bundles.</p>
      ) : null}
      <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {previewItems.map((item) => (
          <MediaCard
            key={item.id}
            item={item}
            selected={selectedMediaId === item.id}
            onSelect={() => setSelectedMediaId(item.id)}
          />
        ))}
      </div>
      {showMappingPreview && selectedItem ? <PadnaMappingPreview item={selectedItem} /> : null}
      {showMetadataPreview && selectedItem ? <PadnaMetadataGrid item={selectedItem} /> : null}
      <footer className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-slate-800 pt-4 text-sm text-slate-400">
        <div className="flex flex-1 flex-col gap-1">
          <span className="font-semibold text-slate-200">Render:</span>
          <span>{renderStatusMessage}</span>
          {renderStorageHint ? (
            <span className="text-xs text-slate-500">Saved to {renderStorageHint}</span>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={handleRender}
            className={`rounded-full border px-3 py-2 text-xs font-semibold transition ${
              renderJob?.state === 'done'
                ? 'border-emerald-400/60 text-emerald-200 hover:bg-emerald-400/10'
                : 'border-slate-700 text-slate-200 hover:bg-slate-800'
            } disabled:cursor-not-allowed disabled:opacity-40`}
            disabled={renderDisabled}
          >
            {renderButtonLabel}
          </button>
          {renderPreviewUrl ? (
            <>
              <a
                href={renderPreviewUrl}
                target="_blank"
                rel="noreferrer"
                className="rounded-full border border-cyan-500/60 px-3 py-2 text-xs font-semibold text-cyan-200 hover:bg-cyan-500/10"
              >
                Preview
              </a>
              <a
                href={renderPreviewUrl}
                download={renderDownloadName}
                className="rounded-full border border-slate-700 px-3 py-2 text-xs font-semibold text-slate-200 hover:bg-slate-800"
              >
                Download
              </a>
            </>
          ) : null}
        </div>
      </footer>
      {renderPreviewUrl ? (
        <section className="mt-4 rounded-2xl border border-slate-800 bg-slate-950/70 p-4 text-sm text-slate-100">
          <h3 className="text-sm font-semibold text-slate-100">Render preview</h3>
          <p className="mt-1 text-xs text-slate-500">
            Placeholder output from the simulated PaDNA renderer. Swap in the production bundle renderer when ready.
          </p>
          {renderStorageHint ? (
            <p className="mt-1 text-xs text-slate-500">Saved to {renderStorageHint}</p>
          ) : null}
          <img
            src={renderPreviewUrl}
            alt="PaDNA render preview"
            className="mt-3 max-h-64 w-full rounded-xl object-cover"
          />
        </section>
      ) : null}
      <PadnaRenderHistory
        jobs={renderHistory}
        loading={historyLoading}
        error={historyError}
        onRefresh={() => {
          void loadHistory();
        }}
      />
    </section>
  );
}

function MediaCard({ item, selected, onSelect }: { item: UserMediaItem; selected: boolean; onSelect: () => void }) {
  const downloadHref = item.download_url ? `${CORE_API_BASE}${item.download_url}` : undefined;
  const isImage = typeof item.content_type === 'string' && item.content_type.startsWith('image/');

  return (
    <article
      role="button"
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          onSelect();
        }
      }}
      aria-pressed={selected}
      className={`flex flex-col gap-3 rounded-2xl border ${
        selected ? 'border-cyan-500/60 bg-cyan-500/10' : 'border-slate-800 bg-slate-950/60'
      } p-3 transition hover:border-cyan-500/40 focus:outline-none focus:ring-2 focus:ring-cyan-400`}
    >
      <div className="flex items-center justify-between gap-2">
        <strong className="truncate text-sm text-slate-100" title={item.original_name}>
          {item.original_name}
        </strong>
        <span className="text-[10px] uppercase tracking-wide text-slate-500">
          {new Date(item.uploaded_ts ?? Date.now()).toLocaleString()}
        </span>
      </div>
      <div className="flex-1 overflow-hidden rounded-xl border border-slate-800 bg-slate-900/70">
        {isImage && downloadHref ? (
          <img src={downloadHref} alt={item.original_name} className="h-40 w-full object-cover" />
        ) : (
          <pre className="h-40 overflow-auto whitespace-pre-wrap break-all p-3 text-xs text-slate-300">
            {item.content_type?.includes('json') ? 'JSON bundle uploaded.' : item.content_type ?? 'binary'}
          </pre>
        )}
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-400">
        <span>{item.content_type ?? 'unknown type'}</span>
        <span>{formatSize(item.size)}</span>
      </div>
      {downloadHref ? (
        <a
          href={downloadHref}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center justify-center rounded-full border border-cyan-500/60 px-3 py-1 text-xs font-semibold text-cyan-200 hover:bg-cyan-500/10"
        >
          Preview / Download
        </a>
      ) : null}
    </article>
  );
}

function PadnaToolbar({
  hasSelection,
  selectedItem,
  isJsonSelected,
  showMapping,
  showMetadata,
  onToggleMapping,
  onToggleMetadata
}: {
  hasSelection: boolean;
  selectedItem: UserMediaItem | null;
  isJsonSelected: boolean;
  showMapping: boolean;
  showMetadata: boolean;
  onToggleMapping: () => void;
  onToggleMetadata: () => void;
}) {
  return (
    <section className="mb-4 rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-slate-200">PaDNA toolkit</h3>
          <p className="text-xs text-slate-500">Map JSON payloads or review media metadata before handing off.</p>
        </div>
        <span className="text-xs uppercase tracking-wide text-slate-500">
          {selectedItem ? selectedItem.original_name : 'Select an asset'}
        </span>
      </header>
      <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
        <button
          type="button"
          onClick={onToggleMapping}
          className={`rounded-full border px-3 py-1 font-semibold transition ${
            showMapping ? 'border-emerald-400/70 bg-emerald-400/10 text-emerald-200' : 'border-slate-700 text-slate-200 hover:bg-slate-800'
          }`}
          disabled={!hasSelection || !isJsonSelected}
        >
          {showMapping ? 'Hide field map' : 'Assign JSON fields'}
        </button>
        <button
          type="button"
          onClick={onToggleMetadata}
          className={`rounded-full border px-3 py-1 font-semibold transition ${
            showMetadata ? 'border-cyan-400/70 bg-cyan-400/10 text-cyan-200' : 'border-slate-700 text-slate-200 hover:bg-slate-800'
          }`}
          disabled={!hasSelection}
        >
          {showMetadata ? 'Hide metadata' : 'Metadata preview'}
        </button>
        <span className="ml-auto text-[11px] text-slate-500">
          {isJsonSelected
            ? 'JSON bundle detected — map fields below.'
            : 'Tip: upload a PaDNA JSON to enable field mapping.'}
        </span>
      </div>
    </section>
  );
}

function PadnaMappingPreview({ item }: { item: UserMediaItem }) {
  const [rows, setRows] = useState<Array<{ trait: string; path: string; value: string }>>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const cancelState = { cancelled: false };

    const run = async () => {
      setRows(buildMappingRows(item, null));
      setError(null);

      const downloadPath = item.download_url ? `${CORE_API_BASE}${item.download_url}` : null;
      const isJson = typeof item.content_type === 'string' && item.content_type.toLowerCase().includes('json');
      if (!downloadPath || !isJson) {
        setLoading(false);
        return;
      }

      setLoading(true);
      try {
        const response = await fetch(downloadPath, { headers: { Accept: 'application/json' } });
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const payload = await response.json();
        if (cancelState.cancelled) {
          return;
        }
        setRows(buildMappingRows(item, payload));
      } catch (err) {
        if (cancelState.cancelled) {
          return;
        }
        setError(err instanceof Error ? err.message : 'Unable to read JSON mapping.');
        setRows(buildMappingRows(item, null));
      } finally {
        if (!cancelState.cancelled) {
          setLoading(false);
        }
      }
    };

    void run();
    return () => {
      cancelState.cancelled = true;
    };
  }, [item]);

  return (
    <section className="mt-6 rounded-2xl border border-emerald-500/40 bg-emerald-500/5 p-4 text-sm text-emerald-50">
      <h3 className="text-sm font-semibold text-emerald-200">Field mapping preview</h3>
      <p className="mt-1 text-xs text-emerald-100/80">
        Quick look at how PaDNA JSON keys feed downstream traits. Edit the bundle to override these defaults.
      </p>
      {loading ? <p className="mt-2 text-xs text-emerald-100/70">Loading JSON bundle…</p> : null}
      {error ? <p className="mt-2 text-xs text-amber-200">Fallback preview shown: {error}</p> : null}
      <div className="mt-3 overflow-hidden rounded-xl border border-emerald-500/30">
        <table className="min-w-full divide-y divide-emerald-500/20">
          <thead className="bg-emerald-500/10 text-[11px] uppercase tracking-wide text-emerald-200">
            <tr>
              <th className="px-3 py-2 text-left">Trait</th>
              <th className="px-3 py-2 text-left">JSON path</th>
              <th className="px-3 py-2 text-left">Value</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-emerald-500/10">
            {rows.map((entry) => (
              <tr key={`${entry.trait}-${entry.path}`} className="bg-slate-950/60">
                <td className="px-3 py-2 text-emerald-100">{entry.trait}</td>
                <td className="px-3 py-2 font-mono text-[11px] text-emerald-200/80">{entry.path}</td>
                <td className="px-3 py-2 text-emerald-100/90">{entry.value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function PadnaMetadataGrid({ item }: { item: UserMediaItem }) {
  const rows: Array<{ label: string; value: string }> = [
    { label: 'Filename', value: item.original_name },
    { label: 'Content type', value: item.content_type ?? '—' },
    { label: 'Size', value: formatSize(item.size) },
    { label: 'Uploaded', value: item.uploaded_ts ? new Date(item.uploaded_ts).toLocaleString() : '—' },
    { label: 'Label', value: item.label ?? '—' }
  ];

  if (item.metadata && typeof item.metadata === 'object') {
    rows.push({
      label: 'Metadata keys',
      value: Object.keys(item.metadata).slice(0, 5).join(', ') || '—'
    });
  }

  return (
    <section className="mt-6 rounded-2xl border border-slate-800 bg-slate-950/70 p-4 text-sm text-slate-200">
      <h3 className="text-sm font-semibold text-slate-100">Metadata preview</h3>
      <p className="mt-1 text-xs text-slate-500">Quick glance at the selected asset before pushing to the renderer.</p>
      <dl className="mt-3 grid gap-3 sm:grid-cols-2">
        {rows.map((row) => (
          <div key={row.label} className="rounded-xl border border-slate-800 bg-slate-900/70 p-3">
            <dt className="text-[10px] uppercase tracking-wide text-slate-500">{row.label}</dt>
            <dd className="mt-1 break-words text-slate-100">{row.value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function PadnaRenderHistory({
  jobs,
  loading,
  error,
  onRefresh
}: {
  jobs: PadnaRenderJob[];
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
}) {
  const hasJobs = jobs.length > 0;

  return (
    <section className="mt-6 rounded-2xl border border-slate-800 bg-slate-950/60 p-4 text-sm text-slate-200">
      <header className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-slate-100">Render history</h3>
          <p className="text-xs text-slate-500">Recent PaDNA bundles (most recent first).</p>
        </div>
        <button
          type="button"
          onClick={onRefresh}
          className="rounded-full border border-slate-700 px-3 py-1 text-xs font-semibold text-slate-200 hover:bg-slate-800 disabled:opacity-40"
          disabled={loading}
        >
          {loading ? 'Refreshing…' : 'Refresh'}
        </button>
      </header>
      {error ? <p className="mb-2 text-xs text-amber-300">{error}</p> : null}
      {hasJobs ? (
        <div className="overflow-hidden rounded-xl border border-slate-800">
          <table className="min-w-full divide-y divide-slate-800 text-xs">
            <thead className="bg-slate-900/80 text-[11px] uppercase tracking-wide text-slate-400">
              <tr>
                <th className="px-3 py-2 text-left">Created</th>
                <th className="px-3 py-2 text-left">Status</th>
                <th className="px-3 py-2 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {jobs.map((job) => {
                const created = job.created_at ? new Date(job.created_at).toLocaleString() : '—';
                const progressPercent =
                  typeof job.progress === 'number' && Number.isFinite(job.progress)
                    ? Math.round(job.progress * 100)
                    : null;
                const stateLabel = formatPadnaState(job.state);
                const resultUrl = job.result_url ? buildPadnaResultUrl(job) : null;
                const filename = job.result_filename ? String(job.result_filename) : 'padna-render.png';
                const storageHint = job.storage_path ?? (job.id ? `renders/${job.id}/` : null);
                return (
                  <tr key={job.id} className="bg-slate-950/60 text-slate-200">
                    <td className="px-3 py-2 align-top">{created}</td>
                    <td className="px-3 py-2 align-top">
                      <span className="font-semibold text-slate-100">{stateLabel}</span>
                      {progressPercent != null && job.state !== 'done' && job.state !== 'error' ? (
                        <span className="ml-2 text-slate-500">{progressPercent}%</span>
                      ) : null}
                      {job.error ? <div className="text-amber-300">{job.error}</div> : null}
                      {storageHint ? (
                        <div className="mt-1 text-[11px] text-slate-500">Saved to {storageHint}</div>
                      ) : null}
                    </td>
                    <td className="px-3 py-2 align-top">
                      {resultUrl ? (
                        <div className="flex justify-end gap-2">
                          <a
                            href={resultUrl}
                            target="_blank"
                            rel="noreferrer"
                            className="rounded-full border border-cyan-500/60 px-3 py-1 font-semibold text-cyan-200 hover:bg-cyan-500/10"
                          >
                            Preview
                          </a>
                          <a
                            href={resultUrl}
                            download={filename}
                            className="rounded-full border border-slate-700 px-3 py-1 font-semibold text-slate-200 hover:bg-slate-800"
                          >
                            Download
                          </a>
                        </div>
                      ) : (
                        <div className="flex justify-end text-slate-500">No output yet</div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-xs text-slate-500">No renders yet. Kick off a bundle to populate history.</p>
      )}
    </section>
  );
}

function buildMappingRows(item: UserMediaItem, data: unknown): Array<{ trait: string; path: string; value: string }> {
  const hints = deriveMappingHints(item);
  const targets: Array<{ trait: string; paths: string[]; fallback: string }> = [
    {
      trait: 'Overall Vibe',
      paths: ['bundle.profile.theme', 'profile.theme', 'profile.overall_vibe'],
      fallback: hints.primary
    },
    {
      trait: 'Palette Anchor',
      paths: ['bundle.palette.primary', 'palette.primary', 'style.palette'],
      fallback: hints.palette
    },
    {
      trait: 'Pose Cue',
      paths: ['bundle.notes.pose', 'notes.pose', 'visual.pose'],
      fallback: hints.pose
    },
    {
      trait: 'Lighting Note',
      paths: ['bundle.notes.lighting', 'notes.lighting', 'visual.lighting'],
      fallback: hints.lighting
    }
  ];

  return targets.map((target) => {
    const resolved = findFirstValue(data, target.paths);
    const path = resolved?.path ?? target.paths[0];
    const value = formatMappingValue(resolved?.value ?? target.fallback);
    return { trait: target.trait, path, value };
  });
}

function deriveMappingHints(item: UserMediaItem): { primary: string; palette: string; pose: string; lighting: string } {
  const baseName = item.original_name.replace(/\.[^/.]+$/, '');
  const tokens = baseName.split(/[_-]/).filter((part) => part.length > 0);
  const primary = (item.label ?? tokens[0] ?? 'hero').replace(/\s+/g, ' ');
  const palette = tokens[1] ?? 'warm neutrals';
  const pose = tokens[2] ?? 'relaxed shoulders';
  return {
    primary,
    palette,
    pose,
    lighting: 'Soft key with subtle rim'
  };
}

function findFirstValue(data: unknown, paths: string[]): { path: string; value: unknown } | null {
  if (!data || typeof data !== 'object') {
    return null;
  }
  for (const path of paths) {
    const value = getValueAtPath(data, path);
    if (value !== undefined && value !== null && !(typeof value === 'string' && value.trim() === '')) {
      return { path, value };
    }
  }
  return null;
}

function getValueAtPath(data: unknown, path: string): unknown {
  if (!path) {
    return undefined;
  }
  const segments = path.split('.');
  let current: any = data;
  for (const segment of segments) {
    if (!current || typeof current !== 'object') {
      return undefined;
    }
    current = current[segment];
  }
  return current;
}

function formatMappingValue(value: unknown): string {
  if (typeof value === 'string') {
    return value.trim() || '—';
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  if (Array.isArray(value)) {
    return value.slice(0, 3).map((entry) => formatMappingValue(entry)).join(', ');
  }
  if (value && typeof value === 'object') {
    try {
      return JSON.stringify(value);
    } catch (error) {
      return '[object]';
    }
  }
  return '—';
}

function formatPadnaState(state: PadnaRenderJobState): string {
  switch (state) {
    case 'done':
      return 'Completed';
    case 'running':
      return 'Running';
    case 'error':
      return 'Error';
    default:
      return 'Queued';
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
