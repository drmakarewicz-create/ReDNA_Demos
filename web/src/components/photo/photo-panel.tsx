'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import {
  createPhotoRenderJob,
  deleteUserMedia,
  extractPhotoTraits,
  fetchPhotoRenderStatus,
  listPhotoRenderJobs,
  listUserMedia,
  uploadUserMedia,
  applyPhotoFix,
  type PhotoExtractedTrait,
  type PhotoExtractSummary,
  type PhotoExtractFix,
  type PhotoRenderJob,
  type PhotoRenderJobState,
  type UserMediaItem
} from '../../lib/api';
import { PanelError } from '../panel-error';
import { ProvenanceModal } from '../provenance-modal';
import { RRBadge, CuriosityBadge } from '../rr-curiosity-badges';
import { PhotoImportPanel } from './photo-import-panel';

interface PhotoPanelProps {
  userId: string;
}

const CORE_API_BASE = (process.env.NEXT_PUBLIC_CORE_API_BASE ?? '').replace(/\/$/, '');
const ACTIVE_RENDER_STATES: Set<PhotoRenderJobState> = new Set(['queued', 'running']);
const JOB_TIME_FORMAT = new Intl.DateTimeFormat(undefined, {
  month: 'short',
  day: 'numeric',
  hour: '2-digit',
  minute: '2-digit'
});

export function PhotoPanel({ userId }: PhotoPanelProps) {
  const [mediaItems, setMediaItems] = useState<UserMediaItem[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [jobs, setJobs] = useState<PhotoRenderJob[]>([]);
  const [jobsLoading, setJobsLoading] = useState(false);
  const [jobsError, setJobsError] = useState<string | null>(null);
  const [jobActionError, setJobActionError] = useState<string | null>(null);
  const [creatingJob, setCreatingJob] = useState(false);
  const [renderMode, setRenderMode] = useState<'preview' | 'final'>('preview');
  const [rotationState, setRotationState] = useState<Record<string, number>>({});
  const [cropFocusId, setCropFocusId] = useState<string | null>(null);
  const [exifOpen, setExifOpen] = useState(false);
  const [extractingTraits, setExtractingTraits] = useState(false);
  const [extractError, setExtractError] = useState<string | null>(null);
  const [extractedTraits, setExtractedTraits] = useState<PhotoExtractedTrait[]>([]);
  const [summaryFixes, setSummaryFixes] = useState<PhotoExtractSummary | PhotoExtractFix[] | null>(null);
  const [fixesExpanded, setFixesExpanded] = useState(true);
  const [extractToast, setExtractToast] = useState<string | null>(null);
  const [applyingFix, setApplyingFix] = useState<Set<string>>(new Set());
  const [provenanceTraitId, setProvenanceTraitId] = useState<string | null>(null);
  const [provenanceTraitValue, setProvenanceTraitValue] = useState<string>('');
  const inputRef = useRef<HTMLInputElement | null>(null);

  const resolvedUserId = userId.trim();
  const canInteract = Boolean(resolvedUserId);

  const refreshMedia = useCallback(() => {
    if (!resolvedUserId) {
      setMediaItems([]);
      setError(null);
      setLoading(false);
      setSelectedIds(new Set());
      return () => {};
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    void listUserMedia(resolvedUserId)
      .then((items) => {
        if (!cancelled) {
          const imagesOnly = items.filter((entry) => entry.content_type?.startsWith('image/'));
          setMediaItems(imagesOnly);
          setSelectedIds((prev) => {
            const next = new Set<string>();
            for (const entry of imagesOnly) {
              if (prev.has(entry.id)) {
                next.add(entry.id);
              }
            }
            return next;
          });
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Unable to load photo references.');
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
  }, [resolvedUserId]);

  useEffect(() => {
    return refreshMedia();
  }, [refreshMedia]);

  useEffect(() => {
    setRotationState((prev) => {
      const allowed = new Set(mediaItems.map((item) => item.id));
      let changed = false;
      const next: Record<string, number> = {};
      for (const key of Object.keys(prev)) {
        if (allowed.has(key)) {
          next[key] = prev[key];
        } else {
          changed = true;
        }
      }
      if (!changed && Object.keys(next).length === Object.keys(prev).length) {
        return prev;
      }
      return next;
    });
    setCropFocusId((prev) => (prev && mediaItems.some((item) => item.id === prev) ? prev : null));
  }, [mediaItems]);

  useEffect(() => {
    if (!resolvedUserId) {
      setJobs([]);
      setJobsError(null);
      setJobsLoading(false);
      setJobActionError(null);
      return;
    }
    let cancelled = false;
    setJobsLoading(true);
    setJobsError(null);
    setJobActionError(null);
    void listPhotoRenderJobs(resolvedUserId, 20)
      .then((items) => {
        if (!cancelled) {
          setJobs(sortJobs(items));
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setJobsError(err instanceof Error ? err.message : 'Unable to load render jobs.');
          setJobs([]);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setJobsLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [resolvedUserId]);

  const mediaLookup = useMemo(() => {
    const map = new Map<string, UserMediaItem>();
    for (const entry of mediaItems) {
      map.set(entry.id, entry);
    }
    return map;
  }, [mediaItems]);

  const selectedMediaId = useMemo(() => {
    if (selectedIds.size !== 1) {
      return null;
    }
    const [onlyId] = Array.from(selectedIds);
    return onlyId ?? null;
  }, [selectedIds]);

  const focusedMedia = useMemo(() => {
    if (!selectedMediaId) {
      return null;
    }
    return mediaLookup.get(selectedMediaId) ?? null;
  }, [mediaLookup, selectedMediaId]);

  useEffect(() => {
    setExtractingTraits(false);
    setExtractError(null);
    setExtractedTraits([]);
  }, [selectedMediaId, resolvedUserId]);

  const focusedRenderJob = useMemo(() => {
    if (!selectedMediaId) {
      return null;
    }
    const candidates = jobs.filter((job) => job.media_id === selectedMediaId && job.state === 'done');
    if (candidates.length === 0) {
      return null;
    }
    return candidates.sort((a, b) => {
      const aTs = Date.parse(a.updated_at ?? a.created_at ?? '') || 0;
      const bTs = Date.parse(b.updated_at ?? b.created_at ?? '') || 0;
      return bTs - aTs;
    })[0];
  }, [jobs, selectedMediaId]);

  const rotationDegrees = focusedMedia ? rotationState[focusedMedia.id] ?? 0 : 0;
  const cropActive = focusedMedia ? cropFocusId === focusedMedia.id : false;
  const originalHref = focusedMedia?.download_url ? `${CORE_API_BASE}${focusedMedia.download_url}` : null;
  const resultHref = focusedRenderJob?.result_url ? `${CORE_API_BASE}${focusedRenderJob.result_url}` : null;

  const exifEntries = useMemo(() => {
    if (!focusedMedia?.metadata || typeof focusedMedia.metadata !== 'object') {
      return [] as Array<{ key: string; value: string }>;
    }
    const candidate = focusedMedia.metadata as Record<string, unknown>;
    const exifLike = candidate.exif && typeof candidate.exif === 'object' ? (candidate.exif as Record<string, unknown>) : candidate.EXIF && typeof candidate.EXIF === 'object' ? (candidate.EXIF as Record<string, unknown>) : candidate;
    const entries: Array<{ key: string; value: string }> = [];
    for (const [key, value] of Object.entries(exifLike)) {
      if (value === null || value === undefined) {
        continue;
      }
      let rendered: string;
      if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
        rendered = String(value);
      } else {
        try {
          rendered = JSON.stringify(value);
        } catch (error) {
          rendered = String(value);
        }
      }
      entries.push({ key, value: rendered });
      if (entries.length >= 8) {
        break;
      }
    }
    return entries;
  }, [focusedMedia]);

  useEffect(() => {
    if (!focusedMedia) {
      setExifOpen(false);
    }
  }, [focusedMedia]);

  const handleUpload = useCallback(
    async (file: File | null) => {
      if (!file || !resolvedUserId) {
        return;
      }
      setUploading(true);
      setError(null);
      try {
        const item = await uploadUserMedia(resolvedUserId, file);
        if (item.content_type?.startsWith('image/')) {
          setMediaItems((prev) => [item, ...prev.filter((entry) => entry.id !== item.id)]);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Upload failed.');
      } finally {
        setUploading(false);
      }
    },
    [resolvedUserId]
  );

  const handleDeleteSelection = useCallback(async () => {
    if (!resolvedUserId || selectedIds.size === 0) {
      return;
    }
    const ids = Array.from(selectedIds);
    setDeleting(true);
    setJobActionError(null);
    try {
      await Promise.all(ids.map((mediaId) => deleteUserMedia(resolvedUserId, mediaId)));
      setMediaItems((prev) => prev.filter((entry) => !ids.includes(entry.id)));
      setJobs((prev) => prev.filter((job) => !ids.includes(job.media_id)));
      setSelectedIds(new Set());
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unable to delete media.';
      setJobActionError(message);
    } finally {
      setDeleting(false);
    }
  }, [resolvedUserId, selectedIds]);

  const toggleSelection = useCallback((mediaId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(mediaId)) {
        next.delete(mediaId);
      } else {
        next.add(mediaId);
      }
      return next;
    });
  }, []);

  const handleRotate = useCallback(
    (amount: number) => {
      if (!focusedMedia) {
        return;
      }
      setRotationState((prev) => {
        const current = prev[focusedMedia.id] ?? 0;
        const updated = ((current + amount) % 360 + 360) % 360;
        const next = { ...prev };
        next[focusedMedia.id] = updated;
        return next;
      });
    },
    [focusedMedia]
  );

  const handleResetTransforms = useCallback(() => {
    if (!focusedMedia) {
      return;
    }
    setRotationState((prev) => {
      if (!(focusedMedia.id in prev)) {
        return prev;
      }
      const next = { ...prev };
      delete next[focusedMedia.id];
      return next;
    });
    setCropFocusId((prev) => (prev === focusedMedia.id ? null : prev));
  }, [focusedMedia]);

  const handleToggleCrop = useCallback(() => {
    if (!focusedMedia) {
      return;
    }
    setCropFocusId((prev) => (prev === focusedMedia.id ? null : focusedMedia.id));
  }, [focusedMedia]);

  const triggerUpload = useCallback(() => {
    inputRef.current?.click();
  }, []);

  const upsertJobs = useCallback((updates: PhotoRenderJob[]) => {
    if (updates.length === 0) {
      return;
    }
    setJobs((prev) => {
      const map = new Map<string, PhotoRenderJob>();
      for (const job of prev) {
        map.set(job.id, job);
      }
      for (const job of updates) {
        map.set(job.id, job);
      }
      return sortJobs(Array.from(map.values()));
    });
  }, []);

  const handleExtractTraits = useCallback(() => {
    if (!resolvedUserId || selectedIds.size !== 1) {
      setExtractError('Select a single reference before extracting traits.');
      return;
    }
    const [targetId] = Array.from(selectedIds);
    setExtractingTraits(true);
    setExtractError(null);
    setExtractedTraits([]);
    setSummaryFixes(null);
    setExtractToast(null);
    void extractPhotoTraits(resolvedUserId, targetId)
      .then((result) => {
        setExtractedTraits(result.traits);
        setSummaryFixes(result.summary_fixes || null);
        setFixesExpanded(true);
        setExtractToast(`Extracted ${result.traits.length} trait${result.traits.length === 1 ? '' : 's'}`);
        setTimeout(() => setExtractToast(null), 5000);
        try {
          window.dispatchEvent(
            new CustomEvent('hc-photo-extracted', {
              detail: {
                userId: resolvedUserId,
                mediaId: targetId,
                traitCount: result.traits.length
              }
            })
          );
        } catch (eventError) {
          console.warn('Failed to dispatch photo extraction event', eventError);
        }
      })
      .catch((err) => {
        const message = err instanceof Error ? err.message : 'Unable to extract traits.';
        setExtractError(message);
        setExtractedTraits([]);
        setSummaryFixes(null);
        setExtractToast(message);
        setTimeout(() => setExtractToast(null), 5000);
      })
      .finally(() => {
        setExtractingTraits(false);
      });
  }, [resolvedUserId, selectedIds]);

  const handleApplyFix = useCallback(async (fix: PhotoExtractFix) => {
    if (!resolvedUserId) return;

    setApplyingFix(prev => new Set(prev).add(fix.trait_id));

    try {
      await applyPhotoFix({
        user_id: resolvedUserId,
        trait_id: fix.trait_id,
        value: fix.value,
        reason: 'photo_fix_applied_from_ui'
      });

      setExtractToast(`Applied fix for ${fix.trait_id}`);
      setTimeout(() => setExtractToast(null), 3000);

      // Dispatch event to refresh panels
      try {
        window.dispatchEvent(
          new CustomEvent('hc-traits-changed', {
            detail: { userId: resolvedUserId }
          })
        );
      } catch (eventError) {
        console.warn('Failed to dispatch traits changed event', eventError);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to apply fix.';
      setExtractToast(message);
      setTimeout(() => setExtractToast(null), 5000);
    } finally {
      setApplyingFix(prev => {
        const next = new Set(prev);
        next.delete(fix.trait_id);
        return next;
      });
    }
  }, [resolvedUserId]);

  const handleCreateRender = useCallback(() => {
    if (!resolvedUserId) {
      return;
    }
    const ids = Array.from(selectedIds);
    if (ids.length === 0) {
      setJobActionError('Select at least one reference before rendering.');
      return;
    }
    const targetId = ids[0];
    setCreatingJob(true);
    setJobActionError(null);
    void createPhotoRenderJob(resolvedUserId, targetId, { mode: renderMode })
      .then((job) => {
        upsertJobs([job]);
      })
      .catch((err) => {
        setJobActionError(err instanceof Error ? err.message : 'Unable to start render job.');
      })
      .finally(() => {
        setCreatingJob(false);
      });
  }, [renderMode, resolvedUserId, selectedIds, upsertJobs]);

  const pollingKey = useMemo(() => {
    if (jobs.length === 0) {
      return '';
    }
    return jobs
      .filter((job) => ACTIVE_RENDER_STATES.has(job.state))
      .map((job) => job.id)
      .sort()
      .join('|');
  }, [jobs]);

  useEffect(() => {
    if (!resolvedUserId || !pollingKey) {
      return;
    }
    const activeIds = pollingKey.split('|').filter(Boolean);
    if (activeIds.length === 0) {
      return;
    }
    let cancelled = false;

    const poll = () => {
      Promise.all(
        activeIds.map((id) =>
          fetchPhotoRenderStatus(id, resolvedUserId).catch(() => null)
        )
      ).then((entries) => {
        if (cancelled) {
          return;
        }
        const valid = entries.filter((entry): entry is PhotoRenderJob => Boolean(entry));
        if (valid.length > 0) {
          upsertJobs(valid);
        }
      });
    };

    const timer = window.setInterval(poll, 1500);
    poll();
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [pollingKey, resolvedUserId, upsertJobs]);

  const selectedCount = selectedIds.size;
  const canStartRender = canInteract && selectedCount > 0 && !creatingJob;
  const canDeleteSelection = canInteract && selectedCount > 0 && !deleting;
  const canExtractTraits = canInteract && selectedIds.size === 1 && !extractingTraits;

  if (!resolvedUserId) {
    return (
      <section className="rounded-3xl border border-slate-800 bg-slate-900/70 p-6 text-slate-300">
        <header className="mb-3">
          <h2 className="text-lg font-semibold text-slate-100">Photo Coach Refinement</h2>
          <p className="text-sm text-slate-400">Select a user to curate photo references and plan render passes.</p>
        </header>
        <p className="text-sm text-slate-500">No active user selected.</p>
      </section>
    );
  }

  return (
    <section className="rounded-3xl border border-slate-800 bg-slate-900/70 p-6 text-slate-100">
      <header className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">Photo Coach Refinement</h2>
          <p className="text-sm text-slate-400">Upload session references, then pick frames to refine.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <input
            ref={inputRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0] ?? null;
              event.target.value = '';
              void handleUpload(file);
            }}
          />
          <button
            type="button"
            onClick={triggerUpload}
            className="rounded-full border border-cyan-500/60 px-3 py-2 text-xs font-semibold text-cyan-200 hover:bg-cyan-500/10 disabled:opacity-40"
            disabled={uploading || !canInteract}
            data-testid="photo-upload-button"
          >
            {uploading ? 'Uploading…' : 'Upload reference'}
          </button>
          <button
            type="button"
            onClick={handleDeleteSelection}
            className="rounded-full border border-rose-500/60 px-3 py-2 text-xs font-semibold text-rose-200 hover:bg-rose-500/10 disabled:opacity-40"
            disabled={!canDeleteSelection}
            data-testid="photo-delete-button"
          >
            {deleting ? 'Removing…' : 'Delete reference'}
          </button>
        </div>
      </header>
      <PhotoPersonaToolbar
        hasSelection={Boolean(focusedMedia)}
        disabled={!canInteract || !focusedMedia}
        cropActive={cropActive}
        rotationDegrees={rotationDegrees}
        onRotateLeft={() => handleRotate(-90)}
        onRotateRight={() => handleRotate(90)}
        onReset={handleResetTransforms}
        onToggleCrop={handleToggleCrop}
        onToggleExif={() => setExifOpen((prev) => !prev)}
        originalHref={originalHref}
        resultHref={resultHref}
        exifEntries={exifEntries}
        exifOpen={exifOpen}
      />
      {error ? <PanelError message={error} onRetry={() => void refreshMedia()} /> : null}
      {loading ? <p className="text-sm text-slate-400">Loading photo references…</p> : null}
      {!loading && mediaItems.length === 0 ? (
        <p className="text-sm text-slate-400">No photo references yet. Upload a few to start a refinement plan.</p>
      ) : null}
      <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {mediaItems.map((item) => (
          <PhotoCard
            key={item.id}
            item={item}
            selected={selectedIds.has(item.id)}
            onToggle={() => toggleSelection(item.id)}
            rotation={rotationState[item.id] ?? 0}
            cropActive={cropFocusId === item.id}
            dataTestId="photo-card"
          />
        ))}
      </div>
      <footer className="mt-6 flex flex-col gap-3 border-t border-slate-800 pt-4 text-sm text-slate-400">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <span className="font-semibold text-slate-200">Selected:</span> {selectedCount} frame{selectedCount === 1 ? '' : 's'}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <label className="flex items-center gap-2 text-xs text-slate-400">
              <span className="uppercase tracking-wide text-slate-500">Mode</span>
              <select
                value={renderMode}
                onChange={(event) => setRenderMode(event.target.value as 'preview' | 'final')}
                className="rounded-full border border-slate-700 bg-slate-900 px-2 py-1 text-xs text-slate-200 focus:border-cyan-400 focus:outline-none"
              >
                <option value="preview">Preview (stub)</option>
                <option value="final">Final (stub)</option>
              </select>
            </label>
            <button
              type="button"
              onClick={handleCreateRender}
              className="rounded-full border border-cyan-500/60 px-3 py-2 text-xs font-semibold text-cyan-200 hover:bg-cyan-500/10 disabled:opacity-40"
              disabled={!canStartRender}
            >
              {creatingJob ? 'Starting…' : 'Render image'}
            </button>
            <button
              type="button"
              onClick={handleExtractTraits}
              className="rounded-full border border-emerald-500/50 px-3 py-2 text-xs font-semibold text-emerald-200 hover:bg-emerald-500/10 disabled:opacity-40"
              disabled={!canExtractTraits}
            >
              {extractingTraits ? 'Extracting…' : 'Extract traits'}
            </button>
          </div>
        </div>
        {jobActionError ? <p className="text-xs text-rose-300">{jobActionError}</p> : null}
      </footer>
      <section className="mt-6 rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-slate-200">Three Fixes for this Photo</h3>
            <p className="text-xs text-slate-500">Suggested improvements and extracted traits with RR/Curiosity metrics.</p>
          </div>
          <div className="flex items-center gap-2">
            {extractingTraits ? <span className="text-xs text-emerald-200">Working…</span> : null}
            {extractedTraits.length > 0 ? (
              <button
                type="button"
                onClick={() => setFixesExpanded(!fixesExpanded)}
                className="rounded-full border border-slate-700 px-2 py-1 text-xs text-slate-400 hover:border-slate-600 hover:text-slate-300"
                aria-label={fixesExpanded ? 'Collapse' : 'Expand'}
              >
                {fixesExpanded ? '▼' : '▶'}
              </button>
            ) : null}
          </div>
        </header>
        {extractError ? <p className="mt-3 text-xs text-rose-300">{extractError}</p> : null}
        {!extractingTraits && !extractError && extractedTraits.length === 0 ? (
          <p className="mt-3 text-xs text-slate-500">Run an extraction to populate this card.</p>
        ) : null}
        {extractedTraits.length > 0 && fixesExpanded ? (
          <div className="mt-4 space-y-4">
            {/* Three Fixes Section */}
            {summaryFixes && Array.isArray(summaryFixes) && summaryFixes.length > 0 ? (
              <div className="rounded-xl border border-slate-700 bg-slate-900/40 p-3">
                <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-400">Suggested Fixes (Top 3)</h4>
                <ul className="mt-2 space-y-2 text-xs">
                  {summaryFixes.slice(0, 3).map((fix: PhotoExtractFix) => (
                    <li key={fix.trait_id} className="flex items-start justify-between gap-2 rounded border border-slate-800 bg-slate-950/50 p-2">
                      <div className="flex-1 text-slate-300">
                        <span className="font-mono text-[10px] text-emerald-400">{fix.trait_id}</span>
                        <div className="mt-0.5 text-xs">
                          {fix.value} <span className="text-slate-500">(RR: {Math.round(fix.rr)})</span>
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleApplyFix(fix)}
                        disabled={applyingFix.has(fix.trait_id)}
                        className="rounded border border-emerald-500/60 px-2 py-1 text-[10px] font-semibold text-emerald-200 hover:bg-emerald-500/10 disabled:opacity-40 disabled:cursor-not-allowed"
                        title="Apply this fix"
                      >
                        {applyingFix.has(fix.trait_id) ? 'Applying...' : 'Apply'}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            ) : summaryFixes && typeof summaryFixes === 'object' && 'top_fix_1' in summaryFixes ? (
              <div className="rounded-xl border border-slate-700 bg-slate-900/40 p-3">
                <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-400">Suggested Fixes</h4>
                <ul className="mt-2 space-y-1.5 text-xs text-slate-300">
                  {summaryFixes.top_fix_1 ? (
                    <li className="flex gap-2">
                      <span className="text-emerald-400">•</span>
                      <span>{summaryFixes.top_fix_1}</span>
                    </li>
                  ) : null}
                  {summaryFixes.top_fix_2 ? (
                    <li className="flex gap-2">
                      <span className="text-emerald-400">•</span>
                      <span>{summaryFixes.top_fix_2}</span>
                    </li>
                  ) : null}
                  {summaryFixes.top_fix_3 ? (
                    <li className="flex gap-2">
                      <span className="text-emerald-400">•</span>
                      <span>{summaryFixes.top_fix_3}</span>
                    </li>
                  ) : null}
                </ul>
              </div>
            ) : (
              <div className="rounded-xl border border-slate-700 bg-slate-900/40 p-3">
                <p className="text-xs text-slate-500">No suggested fixes from this run.</p>
              </div>
            )}

            {/* Extracted Traits Table */}
            {extractedTraits.length > 0 ? (
              <div>
                <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">Extracted Traits</h4>
                <div className="overflow-hidden rounded-xl border border-slate-800">
                  <table className="min-w-full text-left text-xs text-slate-200">
                    <thead className="bg-slate-900/80 text-[11px] uppercase tracking-wide text-slate-500">
                      <tr>
                        <th className="px-3 py-2">Trait</th>
                        <th className="px-3 py-2">Value</th>
                        <th className="px-3 py-2 text-center">RR</th>
                        <th className="px-3 py-2 text-center">Curiosity</th>
                        <th className="px-3 py-2 text-center"></th>
                      </tr>
                    </thead>
                    <tbody>
                      {extractedTraits.map((trait) => (
                        <tr key={trait.trait} className="odd:bg-slate-900/40">
                          <td className="px-3 py-2 font-mono text-[11px] text-slate-400">{trait.trait}</td>
                          <td className="px-3 py-2 text-slate-200">{trait.value}</td>
                          <td className="px-3 py-2 text-center">
                            {trait.rr !== undefined ? (
                              <RRBadge rr={trait.rr} />
                            ) : (
                              <span className="text-slate-600">—</span>
                            )}
                          </td>
                          <td className="px-3 py-2 text-center">
                            {trait.curiosity !== undefined ? (
                              <CuriosityBadge curiosity={trait.curiosity} />
                            ) : (
                              <span className="text-slate-600">—</span>
                            )}
                          </td>
                          <td className="px-3 py-2 text-center">
                            <button
                              type="button"
                              onClick={() => {
                                setProvenanceTraitId(trait.trait);
                                setProvenanceTraitValue(String(trait.value ?? ''));
                              }}
                              className="rounded-full border border-cyan-500/60 px-2 py-0.5 text-[10px] font-semibold text-cyan-200 hover:bg-cyan-500/10"
                              title={`View provenance for ${trait.trait}`}
                            >
                              Why?
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : (
              <p className="text-xs text-slate-500">No traits extracted.</p>
            )}
          </div>
        ) : null}
      </section>
      <PhotoImportPanel
        userId={userId}
        onImportComplete={refreshMedia}
      />
      <section className="mt-6 rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-slate-200">Render jobs</h3>
            <p className="text-xs text-slate-500">Queued renders process asynchronously; previews appear once complete.</p>
          </div>
          {jobsLoading ? <span className="text-xs text-slate-500">Syncing…</span> : null}
        </header>
        {jobsError ? <p className="mt-3 text-xs text-rose-300">{jobsError}</p> : null}
        {!jobsLoading && jobs.length === 0 && !jobsError ? (
          <p className="mt-3 text-xs text-slate-500">No renders yet. Start one above to watch progress here.</p>
        ) : null}
        <div className="mt-3 space-y-3">
          {jobs.map((job) => (
            <RenderJobRow key={job.id} job={job} media={mediaLookup.get(job.media_id)} />
          ))}
        </div>
      </section>
      <ProvenanceModal
        open={!!provenanceTraitId}
        traitId={provenanceTraitId || ''}
        traitValue={provenanceTraitValue}
        userId={resolvedUserId}
        onClose={() => {
          setProvenanceTraitId(null);
          setProvenanceTraitValue('');
        }}
      />
      {extractToast ? (
        <div
          className={`fixed bottom-4 right-4 rounded-lg border px-4 py-3 text-sm shadow-xl ${
            extractError
              ? 'border-rose-500/60 bg-slate-950/90 text-rose-200'
              : 'border-emerald-500/60 bg-slate-950/90 text-emerald-200'
          }`}
        >
          {extractToast}
        </div>
      ) : null}
    </section>
  );
}

function PhotoCard({
  item,
  selected,
  onToggle,
  rotation,
  cropActive,
  dataTestId
}: {
  item: UserMediaItem;
  selected: boolean;
  onToggle: () => void;
  rotation: number;
  cropActive: boolean;
  dataTestId?: string;
}) {
  const downloadHref = item.download_url ? `${CORE_API_BASE}${item.download_url}` : undefined;
  const transformStyle = rotation ? { transform: `rotate(${rotation}deg)` } : undefined;
  return (
    <article
      className={`relative flex flex-col gap-2 rounded-2xl border ${
        selected ? 'border-cyan-500/60 bg-cyan-500/10' : 'border-slate-800 bg-slate-950/60'
      } p-3 transition`}
      data-testid={dataTestId}
      data-media-id={item.id}
    >
      <button
        type="button"
        onClick={onToggle}
        className="relative h-40 overflow-hidden rounded-xl border border-slate-800 focus:outline-none focus:ring-2 focus:ring-cyan-400"
        aria-pressed={selected}
      >
        {downloadHref ? (
          <img
            src={downloadHref}
            alt={item.original_name}
            className="h-full w-full object-cover transition-transform duration-200"
            style={transformStyle}
          />
        ) : (
          <span className="flex h-full items-center justify-center text-xs text-slate-400">Preview unavailable</span>
        )}
        {cropActive ? (
          <span className="pointer-events-none absolute inset-3 rounded-xl border-2 border-dashed border-amber-400/80" aria-hidden="true" />
        ) : null}
        <span
          className={`absolute left-2 top-2 inline-flex items-center rounded-full px-2 py-1 text-[10px] font-semibold ${
            selected ? 'bg-cyan-500 text-slate-900' : 'bg-slate-900/80 text-slate-200'
          }`}
        >
          {selected ? 'Selected' : 'Tap to select'}
        </span>
      </button>
      <div className="flex items-center justify-between gap-2 text-xs text-slate-400">
        <span className="truncate" title={item.original_name}>
          {item.original_name}
        </span>
        <span>{formatSize(item.size)}</span>
      </div>
      {downloadHref ? (
        <a
          href={downloadHref}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center justify-center rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-200 hover:bg-slate-800"
        >
          Preview
        </a>
      ) : null}
      {rotation ? (
        <span className="self-end rounded-full border border-slate-700 px-2 py-0.5 text-[10px] uppercase tracking-wide text-slate-400">
          Rotated {rotation}°
        </span>
      ) : null}
    </article>
  );
}

function PhotoPersonaToolbar({
  hasSelection,
  disabled,
  cropActive,
  rotationDegrees,
  onRotateLeft,
  onRotateRight,
  onReset,
  onToggleCrop,
  onToggleExif,
  originalHref,
  resultHref,
  exifEntries,
  exifOpen
}: {
  hasSelection: boolean;
  disabled: boolean;
  cropActive: boolean;
  rotationDegrees: number;
  onRotateLeft: () => void;
  onRotateRight: () => void;
  onReset: () => void;
  onToggleCrop: () => void;
  onToggleExif: () => void;
  originalHref: string | null;
  resultHref: string | null;
  exifEntries: Array<{ key: string; value: string }>;
  exifOpen: boolean;
}) {
  const nothingSelected = !hasSelection;
  const noTransforms = rotationDegrees === 0 && !cropActive;
  const hasExif = exifEntries.length > 0;

  return (
    <section className="mb-4 rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-slate-200">Photo persona tools</h3>
          <p className="text-xs text-slate-500">
            Apply quick adjustments or inspect metadata for the current selection.
          </p>
        </div>
        <div className="text-xs uppercase tracking-wide text-slate-500">
          {hasSelection ? 'Frame selected' : 'Select a frame to enable tools'}
        </div>
      </header>
      <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
        <button
          type="button"
          onClick={onRotateLeft}
          className="rounded-full border border-slate-700 px-3 py-1 font-semibold text-slate-200 hover:bg-slate-800 disabled:opacity-40"
          disabled={disabled || nothingSelected}
        >
          Rotate left
        </button>
        <button
          type="button"
          onClick={onRotateRight}
          className="rounded-full border border-slate-700 px-3 py-1 font-semibold text-slate-200 hover:bg-slate-800 disabled:opacity-40"
          disabled={disabled || nothingSelected}
        >
          Rotate right
        </button>
        <button
          type="button"
          onClick={onReset}
          className="rounded-full border border-slate-700 px-3 py-1 font-semibold text-slate-200 hover:bg-slate-800 disabled:opacity-40"
          disabled={disabled || nothingSelected || noTransforms}
        >
          Reset view
        </button>
        <button
          type="button"
          onClick={onToggleCrop}
          className={`rounded-full border px-3 py-1 font-semibold transition ${
            cropActive ? 'border-amber-400 text-amber-200 bg-amber-500/10' : 'border-slate-700 text-slate-200 hover:bg-slate-800'
          }`}
          disabled={disabled || nothingSelected}
        >
          {cropActive ? 'Crop box on' : 'Toggle crop stub'}
        </button>
        {originalHref ? (
          <a
            href={originalHref}
            target="_blank"
            rel="noreferrer"
            className="rounded-full border border-cyan-500/60 px-3 py-1 font-semibold text-cyan-200 hover:bg-cyan-500/10"
          >
            Download original
          </a>
        ) : (
          <button
            type="button"
            className="rounded-full border border-slate-700 px-3 py-1 font-semibold text-slate-400 opacity-40"
            disabled
          >
            Download original
          </button>
        )}
        {resultHref ? (
          <a
            href={resultHref}
            target="_blank"
            rel="noreferrer"
            className="rounded-full border border-emerald-500/60 px-3 py-1 font-semibold text-emerald-200 hover:bg-emerald-500/10"
          >
            Download result
          </a>
        ) : (
          <button
            type="button"
            className="rounded-full border border-slate-700 px-3 py-1 font-semibold text-slate-400 opacity-40"
            disabled
          >
            Download result
          </button>
        )}
        <button
          type="button"
          onClick={onToggleExif}
          className={`rounded-full border px-3 py-1 font-semibold transition ${
            hasExif ? 'border-cyan-500/60 text-cyan-200 hover:bg-cyan-500/10' : 'border-slate-700 text-slate-200 hover:bg-slate-800'
          }`}
          disabled={disabled || nothingSelected}
        >
          {exifOpen ? 'Hide metadata' : hasExif ? 'Show EXIF' : 'Show metadata'}
        </button>
      </div>
      {rotationDegrees !== 0 ? (
        <p className="mt-2 text-[11px] text-slate-500">Current rotation: {rotationDegrees}°</p>
      ) : null}
      {exifOpen ? (
        <div className="mt-3 rounded-xl border border-slate-800 bg-slate-900/70 p-3 text-xs text-slate-300">
          {exifEntries.length === 0 ? (
            <p>No EXIF metadata detected for this asset. Stub values only.</p>
          ) : (
            <dl className="grid gap-2 sm:grid-cols-2">
              {exifEntries.map((entry) => (
                <div key={entry.key} className="rounded-lg border border-slate-800/60 bg-slate-950/60 p-2">
                  <dt className="text-[10px] uppercase tracking-wide text-slate-500">{entry.key}</dt>
                  <dd className="mt-1 break-words text-slate-200">{entry.value}</dd>
                </div>
              ))}
            </dl>
          )}
        </div>
      ) : null}
    </section>
  );
}

function RenderJobRow({ job, media }: { job: PhotoRenderJob; media?: UserMediaItem }): JSX.Element {
  const stateLabel: Record<PhotoRenderJobState, string> = {
    queued: 'Queued',
    running: 'Rendering',
    done: 'Complete',
    error: 'Error'
  };
  const badgeStyles: Record<PhotoRenderJobState, string> = {
    queued: 'bg-slate-800 text-slate-200',
    running: 'bg-cyan-500/20 text-cyan-200',
    done: 'bg-emerald-500/20 text-emerald-200',
    error: 'bg-rose-500/20 text-rose-200'
  };
  const progressStyles: Record<PhotoRenderJobState, string> = {
    queued: 'bg-slate-700',
    running: 'bg-cyan-500/70',
    done: 'bg-emerald-500/70',
    error: 'bg-rose-500/70'
  };
  const progressPercent = (() => {
    if (typeof job.progress === 'number' && Number.isFinite(job.progress)) {
      return Math.max(0, Math.min(100, Math.round(job.progress * 100)));
    }
    if (job.state === 'done') {
      return 100;
    }
    if (job.state === 'error') {
      return 0;
    }
    return job.state === 'running' ? 60 : 10;
  })();
  const previewHref = job.result_url ? `${CORE_API_BASE}${job.result_url}` : undefined;
  const modeLabel = typeof job.params?.mode === 'string' ? job.params.mode : 'preview';
  const mediaLabel = media?.original_name ?? `Media ${job.media_id.slice(0, 8)}`;

  return (
    <article className="rounded-xl border border-slate-800 bg-slate-900/60 p-3 text-xs text-slate-300">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-[11px] uppercase tracking-wide text-slate-500">Job {job.id.slice(0, 8)}</p>
          <p className="text-sm font-semibold text-slate-200">{mediaLabel}</p>
          <p className="text-[11px] text-slate-500">Mode: {modeLabel}</p>
        </div>
        <span className={`inline-flex items-center rounded-full px-3 py-1 text-[11px] font-semibold ${badgeStyles[job.state]}`}>
          {stateLabel[job.state]}
        </span>
      </header>
      <div className="mt-3">
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-800">
          <div
            className={`h-full ${progressStyles[job.state]}`}
            style={{ width: `${progressPercent}%` }}
          />
        </div>
        <div className="mt-1 flex flex-wrap items-center justify-between gap-2 text-[11px] text-slate-500">
          <span>{progressPercent}%</span>
          {job.updated_at ? <span>Updated {formatTimestamp(job.updated_at)}</span> : null}
        </div>
      </div>
      {job.state === 'error' && job.error ? (
        <p className="mt-2 text-[11px] text-rose-300">{job.error}</p>
      ) : null}
      {job.state === 'done' && previewHref ? (
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <img
            src={previewHref}
            alt={`Render preview for job ${job.id}`}
            className="h-20 w-20 rounded-lg border border-slate-700 object-cover"
          />
          <a
            href={previewHref}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center rounded-full border border-cyan-500/60 px-3 py-1 font-semibold text-cyan-200 hover:bg-cyan-500/10"
          >
            Download result
          </a>
        </div>
      ) : null}
    </article>
  );
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

function sortJobs(list: PhotoRenderJob[]): PhotoRenderJob[] {
  return [...list].sort((a, b) => {
    const aTs = a.created_at ?? '';
    const bTs = b.created_at ?? '';
    if (aTs && bTs) {
      return bTs.localeCompare(aTs);
    }
    if (bTs) {
      return 1;
    }
    if (aTs) {
      return -1;
    }
    return a.id.localeCompare(b.id);
  });
}

function formatTimestamp(value: string | null): string {
  if (!value) {
    return '';
  }
  try {
    return JOB_TIME_FORMAT.format(new Date(value));
  } catch (err) {
    return value;
  }
}
