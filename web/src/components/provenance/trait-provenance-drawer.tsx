'use client';

/**
 * Trait Provenance Drawer
 *
 * Displays complete explainability information for a trait:
 * - Current resolved value and UCN
 * - Evidence timeline (all observations)
 * - Inference items (rule-based derivations)
 * - RR scoring status
 * - Resolver traces (dev mode only)
 * - Raw JSON (toggle)
 *
 * Actions:
 * - Confirm/Correct: Prefills composer with confirmation message
 * - Ask Follow-up: Prefills composer with question
 */

import React, { useEffect, useState } from 'react';
import {
  fetchProvenance,
  formatValue,
  formatTimestamp,
  extractTraitLabel,
  type Provenance,
  fetchWhyCards,
  type WhyCard,
  resolveCanonicalTraitId,
} from '@/lib/provenanceClient';
import { WhyCardPanel } from './why-card-panel';

interface TraitProvenanceDrawerProps {
  userId: string;
  traitId: string;
  traitLabel?: string;
  open: boolean;
  onClose: () => void;
  onCompose?: (text: string) => void;
  devMode?: boolean;
}

export default function TraitProvenanceDrawer({
  userId,
  traitId,
  traitLabel,
  open,
  onClose,
  onCompose,
  devMode = false,
}: TraitProvenanceDrawerProps) {
  const [prov, setProv] = useState<Provenance | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showRaw, setShowRaw] = useState(false);
  const [loading, setLoading] = useState(false);
  const [notFound, setNotFound] = useState(false);
  const [whyCard, setWhyCard] = useState<WhyCard | null>(null);
  const [whyTraitId, setWhyTraitId] = useState<string | undefined>(undefined);
  const [whyLoading, setWhyLoading] = useState(false);
  const [whyError, setWhyError] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Load provenance data when drawer opens
  useEffect(() => {
    if (!open) return;

    setProv(null);
    setError(null);
    setNotFound(false);
    setLoading(true);

    fetchProvenance(userId, traitId)
      .then((result) => {
        if (result === null) {
          setProv(null);
          setNotFound(true);
        } else {
          setProv(result);
        }
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [open, userId, traitId]);

  // Load Why-Card when drawer opens
  useEffect(() => {
    if (!open) return;

    let cancelled = false;
    setWhyCard(null);
    setWhyTraitId(undefined);
    setWhyError(null);
    setWhyLoading(true);

    (async () => {
      try {
        const canonical = await resolveCanonicalTraitId(traitId).catch(() => traitId);
        if (cancelled) return;

        if (process.env.NODE_ENV !== 'production') {
          console.debug('[why-card] fetching', {
            userId,
            traitId,
            canonical,
          });
        }

        const result = await fetchWhyCards(userId, canonical || traitId);
        if (cancelled) return;

        setWhyCard(result.card);
        setWhyTraitId(result.traitIdUsed || canonical || traitId);
      } catch (err) {
        if (cancelled) return;
        const message = err instanceof Error ? err.message : String(err);
        setWhyError(message);
        setToastMessage(message);
      } finally {
        if (!cancelled) {
          setWhyLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [open, userId, traitId]);

  // Auto-dismiss toast after 5 seconds
  useEffect(() => {
    if (!toastMessage) return;
    const timer = setTimeout(() => setToastMessage(null), 5000);
    return () => clearTimeout(timer);
  }, [toastMessage]);

  // Clear toast when drawer closes
  useEffect(() => {
    if (!open) {
      setToastMessage(null);
      setNotFound(false);
    }
  }, [open]);

  const displayLabel = traitLabel || extractTraitLabel(traitId);

  // Handlers for action buttons
  const handleConfirm = () => {
    if (!prov || !onCompose) return;
    const valueText = formatValue(prov.resolved?.value);
    const msg = `Confirm: my ${displayLabel.toLowerCase()} is ${valueText}`;
    onCompose(msg);
  };

  const handleAskFollowUp = () => {
    if (!prov || !onCompose) return;

    if (prov.inferences.length > 0) {
      const inferredValue = formatValue(prov.inferences[0]?.value);
      const msg = `Why did you infer ${displayLabel.toLowerCase()} as ${inferredValue}?`;
      onCompose(msg);
    } else {
      const msg = `Tell me more about my ${displayLabel.toLowerCase()}`;
      onCompose(msg);
    }
  };

  return (
    <>
      {/* Backdrop */}
      {open && (
        <div
          className="fixed inset-0 bg-black/20 z-40"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      {/* Drawer */}
      <div
        className={`fixed top-0 right-0 h-full w-full max-w-[480px] bg-white shadow-2xl border-l border-gray-200 z-50 transition-transform duration-300 ease-in-out ${
          open ? 'translate-x-0' : 'translate-x-full'
        }`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="provenance-title"
      >
        {/* Header */}
        <div className="p-4 border-b border-gray-200 bg-gradient-to-r from-blue-50 to-white">
          {toastMessage && (
            <div className="absolute top-4 right-4 max-w-[260px] rounded-md bg-red-50 border border-red-200 shadow-md px-3 py-2 text-sm text-red-700 flex items-start gap-2">
              <span className="flex-1">Why-Card failed to load: {toastMessage}</span>
              <button
                type="button"
                onClick={() => setToastMessage(null)}
                className="text-red-600 hover:text-red-800 leading-none text-lg"
                aria-label="Dismiss error"
              >
                ×
              </button>
            </div>
          )}
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm text-gray-500">Why this trait?</div>
              <div className="text-lg font-semibold text-gray-900" id="provenance-title">
                {displayLabel}
              </div>
              <div className="text-xs text-gray-500 mt-1">{traitId}</div>
            </div>
            <button
              onClick={onClose}
              className="text-gray-500 hover:text-gray-800 text-2xl leading-none"
              aria-label="Close"
            >
              ×
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="p-4 space-y-6 overflow-y-auto h-[calc(100%-80px)]">
          {/* Loading */}
          {loading && (
            <div className="text-sm text-gray-500 animate-pulse">Loading provenance...</div>
          )}

          {/* Error */}
          {error && (
            <div className="p-3 rounded-md bg-red-50 border border-red-200">
              <div className="text-sm text-red-800 font-medium">Error</div>
              <div className="text-xs text-red-600 mt-1">{error}</div>
            </div>
          )}

          {notFound && !loading && !error && (
            <div className="p-3 rounded-md border border-dashed border-gray-300 bg-gray-50 text-sm text-gray-600">
              No provenance available yet for this trait. Promote it or provide additional evidence to unlock an explanation.
            </div>
          )}

          <WhyCardPanel
            loading={whyLoading}
            card={whyCard}
            error={whyError}
            traitId={whyTraitId}
            value={prov?.resolved?.value}
          />

          {/* Provenance Data */}
          {prov && (
            <>
              {/* Current State */}
              <section>
                <div className="text-xs uppercase tracking-wide text-gray-500 font-semibold mb-2">
                  Current State
                </div>
                <div className="p-3 rounded-md bg-gradient-to-r from-blue-50 to-cyan-50 border border-blue-100">
                  <div className="flex items-baseline gap-2">
                    <span className="text-lg font-semibold text-gray-900">
                      {formatValue(prov.resolved?.value)}
                    </span>
                    <span className="text-xs px-2 py-1 rounded-full bg-white border border-gray-200 font-mono">
                      UCN {Number(prov.resolved?.ucn ?? 0).toFixed(2)}
                    </span>
                    {prov.resolved?.status && (
                      <span className="text-xs px-2 py-1 rounded-full bg-white border border-gray-200 capitalize">
                        {prov.resolved.status}
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-gray-600 mt-2">
                    <div>Updated: {formatTimestamp(prov.resolved?.last_updated)}</div>
                    <div>
                      Sources: {(prov.resolved?.sources || []).join(', ') || '—'}
                    </div>
                  </div>
                </div>
              </section>

              {/* Evidence Timeline */}
              <section>
                <div className="text-xs uppercase tracking-wide text-gray-500 font-semibold mb-2">
                  Evidence Timeline
                </div>
                {prov.direct_evidence.length > 0 ? (
                  <ul className="space-y-2">
                    {prov.direct_evidence.map((ev, i) => (
                      <li
                        key={i}
                        className="p-2 rounded-md border border-gray-200 bg-gray-50 text-sm"
                      >
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-gray-900">
                            {formatValue(ev.value)}
                          </span>
                          <span className="text-xs px-2 py-0.5 rounded-full bg-blue-100 text-blue-700">
                            {ev.source || 'unknown'}
                          </span>
                        </div>
                        <div className="text-xs text-gray-500 mt-1">
                          {formatTimestamp(ev.ts)}
                          {ev.ucn_prior != null && (
                            <span className="ml-2">· Prior UCN {ev.ucn_prior.toFixed(2)}</span>
                          )}
                          {ev.req_id && (
                            <span className="ml-2 font-mono">· {ev.req_id}</span>
                          )}
                        </div>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <div className="text-sm text-gray-500 italic">No direct evidence logged.</div>
                )}
              </section>

              {/* Inferences */}
              <section>
                <div className="text-xs uppercase tracking-wide text-gray-500 font-semibold mb-2">
                  Inferences
                </div>
                {prov.inferences.length > 0 ? (
                  <>
                    <ul className="space-y-2">
                      {prov.inferences.map((ev, i) => (
                        <li
                          key={i}
                          className="p-2 rounded-md border border-amber-200 bg-amber-50 text-sm"
                        >
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-gray-900">
                              {formatValue(ev.value)}
                            </span>
                            <span className="text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-700">
                              inferred
                            </span>
                          </div>
                          <div className="text-xs text-gray-600 mt-1">
                            {ev.provenance && <div>Rule: {ev.provenance}</div>}
                            {ev.ucn_prior != null && (
                              <div>Prior UCN: {ev.ucn_prior.toFixed(2)}</div>
                            )}
                          </div>
                        </li>
                      ))}
                    </ul>
                    <div className="mt-3 flex gap-2">
                      <button
                        onClick={handleConfirm}
                        className="text-xs px-3 py-1.5 rounded-md border border-blue-300 text-blue-700 hover:bg-blue-50 transition-colors"
                      >
                        Confirm / Correct…
                      </button>
                      <button
                        onClick={handleAskFollowUp}
                        className="text-xs px-3 py-1.5 rounded-md border border-gray-300 text-gray-700 hover:bg-gray-50 transition-colors"
                      >
                        Ask Follow-up…
                      </button>
                    </div>
                  </>
                ) : (
                  <div className="text-sm text-gray-500 italic">
                    No inferences for this trait.
                  </div>
                )}
              </section>

              {/* RR Scoring Status */}
              <section>
                <div className="text-xs uppercase tracking-wide text-gray-500 font-semibold mb-2">
                  RR Scoring
                </div>
                <div className="p-2 rounded-md border border-gray-200 bg-gray-50">
                  <div className="text-sm">
                    Status:{' '}
                    <span
                      className={`font-semibold ${
                        prov.rr_status === 'ok'
                          ? 'text-green-600'
                          : prov.rr_status === 'offline'
                          ? 'text-amber-600'
                          : 'text-gray-600'
                      }`}
                    >
                      {prov.rr_status === 'ok'
                        ? 'Online'
                        : prov.rr_status === 'offline'
                        ? 'Offline (using priors)'
                        : 'Unknown'}
                    </span>
                  </div>
                </div>
              </section>

              {/* Resolver Traces (Dev Mode) */}
              {devMode && (
                <section>
                  <div className="text-xs uppercase tracking-wide text-gray-500 font-semibold mb-2">
                    Resolver Traces (Dev)
                  </div>
                  {prov.traces.length > 0 ? (
                    <ul className="space-y-1">
                      {prov.traces.map((t, i) => (
                        <li
                          key={i}
                          className="p-2 rounded-md border border-gray-200 bg-gray-50 text-xs"
                        >
                          <div className="font-mono text-gray-700">
                            {t.req_id || '—'}
                          </div>
                          <div className="text-gray-500 mt-1">
                            RR: {t.rr_ok ? 'OK' : 'Error'}
                            {t.file && <span className="ml-2">· {t.file}</span>}
                          </div>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <div className="text-sm text-gray-500 italic">No trace references.</div>
                  )}
                </section>
              )}

              {/* Raw JSON Toggle */}
              <section>
                <label className="flex items-center gap-2 text-xs text-gray-600 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={showRaw}
                    onChange={(e) => setShowRaw(e.target.checked)}
                    className="rounded border-gray-300"
                  />
                  <span className="uppercase tracking-wide">Show Raw JSON</span>
                </label>
                {showRaw && (
                  <pre className="mt-2 p-3 bg-gray-900 text-green-400 text-xs overflow-x-auto rounded-md border border-gray-700 font-mono">
                    {JSON.stringify(prov, null, 2)}
                  </pre>
                )}
              </section>
            </>
          )}
        </div>
      </div>
    </>
  );
}
