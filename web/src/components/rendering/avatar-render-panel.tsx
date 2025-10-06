'use client';

import { useCallback, useState } from 'react';
import { renderAvatar, type AvatarRenderJob } from '../../lib/api';

interface AvatarRenderPanelProps {
  userId: string;
}

const CORE_API_BASE = (process.env.NEXT_PUBLIC_CORE_API_BASE ?? '').replace(/\/$/, '');

export function AvatarRenderPanel({ userId }: AvatarRenderPanelProps) {
  const [rendering, setRendering] = useState(false);
  const [renderJob, setRenderJob] = useState<AvatarRenderJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const resolvedUserId = userId.trim();
  const canRender = Boolean(resolvedUserId);

  const handleRenderAvatar = useCallback(async () => {
    if (!resolvedUserId) {
      return;
    }

    setRendering(true);
    setError(null);
    setToast(null);

    try {
      const result = await renderAvatar(resolvedUserId);
      setRenderJob(result.job);
      setToast('Avatar rendered successfully!');
      setTimeout(() => setToast(null), 5000);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unable to render avatar.';
      setError(message);
      setToast(message);
      setTimeout(() => setToast(null), 5000);
    } finally {
      setRendering(false);
    }
  }, [resolvedUserId]);

  if (!resolvedUserId) {
    return (
      <section className="rounded-3xl border border-slate-800 bg-slate-900/70 p-6 text-slate-300">
        <header className="mb-3">
          <h2 className="text-lg font-semibold text-slate-100">Rendering Coach</h2>
          <p className="text-sm text-slate-400">Generate avatar renders from PaDNA traits.</p>
        </header>
        <p className="text-sm text-slate-500">No active user selected.</p>
      </section>
    );
  }

  const downloadUrl = renderJob?.download_url ? `${CORE_API_BASE}${renderJob.download_url}` : null;
  const traitCount = renderJob ? Object.keys(renderJob.rendering_traits || {}).length : 0;

  return (
    <section className="rounded-3xl border border-slate-800 bg-slate-900/70 p-6 text-slate-100">
      <header className="mb-4">
        <h2 className="text-lg font-semibold">Rendering Coach</h2>
        <p className="text-sm text-slate-400">Generate avatar renders based on your PaDNA traits.</p>
      </header>

      <div className="mb-6 rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
        <h3 className="text-sm font-semibold text-slate-200">Avatar Renderer</h3>
        <p className="mt-1 text-xs text-slate-500">
          Creates a stub avatar render from your current PaDNA trait set. This is a placeholder implementation.
        </p>

        <div className="mt-4 flex items-center gap-3">
          <button
            type="button"
            onClick={handleRenderAvatar}
            disabled={!canRender || rendering}
            className="rounded-full border border-emerald-500/60 px-4 py-2 text-sm font-semibold text-emerald-200 hover:bg-emerald-500/10 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {rendering ? 'Rendering…' : 'Render avatar'}
          </button>

          {renderJob && !rendering ? (
            <span className="text-xs text-slate-400">
              Last render: {new Date(renderJob.created_at).toLocaleString()}
            </span>
          ) : null}
        </div>

        {error ? <p className="mt-3 text-xs text-rose-300">{error}</p> : null}
      </div>

      {renderJob ? (
        <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
          <header className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-slate-200">Render Result</h3>
              <p className="mt-1 text-xs text-slate-500">
                Job ID: {renderJob.job_id} • {traitCount} trait{traitCount === 1 ? '' : 's'} used
              </p>
            </div>
            {downloadUrl ? (
              <a
                href={downloadUrl}
                download="avatar-render.png"
                target="_blank"
                rel="noreferrer"
                className="rounded-full border border-cyan-500/60 px-3 py-2 text-xs font-semibold text-cyan-200 hover:bg-cyan-500/10"
              >
                Download PNG
              </a>
            ) : null}
          </header>

          {downloadUrl ? (
            <div className="mt-4 rounded-xl border border-slate-800 bg-slate-900/40 p-3">
              <img
                src={downloadUrl}
                alt="Avatar render"
                className="mx-auto max-h-64 rounded-lg"
                style={{ imageRendering: 'pixelated' }}
              />
              <p className="mt-2 text-center text-xs text-slate-500">
                Stub render (1×1 pixel placeholder). Replace with actual rendering service.
              </p>
            </div>
          ) : null}

          {renderJob.rendering_traits && Object.keys(renderJob.rendering_traits).length > 0 ? (
            <details className="mt-4 rounded-xl border border-slate-800 bg-slate-900/40 p-3">
              <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-slate-400">
                Traits Used ({traitCount})
              </summary>
              <div className="mt-2 space-y-1 text-xs">
                {Object.entries(renderJob.rendering_traits)
                  .slice(0, 10)
                  .map(([traitId, data]) => (
                    <div key={traitId} className="flex items-center justify-between gap-2 border-t border-slate-800 pt-1">
                      <span className="font-mono text-[11px] text-slate-400">{traitId}</span>
                      <span className="text-slate-300">{String(data.value ?? '—')}</span>
                    </div>
                  ))}
                {Object.keys(renderJob.rendering_traits).length > 10 ? (
                  <p className="pt-1 text-slate-500">
                    … and {Object.keys(renderJob.rendering_traits).length - 10} more
                  </p>
                ) : null}
              </div>
            </details>
          ) : null}
        </div>
      ) : null}

      {toast ? (
        <div
          className={`fixed bottom-4 right-4 rounded-lg border px-4 py-3 text-sm shadow-xl ${
            error
              ? 'border-rose-500/60 bg-slate-950/90 text-rose-200'
              : 'border-emerald-500/60 bg-slate-950/90 text-emerald-200'
          }`}
        >
          {toast}
        </div>
      ) : null}
    </section>
  );
}
