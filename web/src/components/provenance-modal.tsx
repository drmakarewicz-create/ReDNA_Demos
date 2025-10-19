// web/src/components/provenance-modal.tsx
'use client';

import { useEffect, useRef, useState } from 'react';

import { CORE_API_BASE } from '../lib/api';

export interface ProvenanceModalProps {
  open: boolean;
  traitId: string;
  traitValue: any;
  userId: string;
  onClose: () => void;
}

interface ProvenanceData {
  trait_id: string;
  trait_value: any;
  ucn?: number;
  rr?: number;
  curiosity?: number;
  reasons?: string[];
  provenance?: {
    source?: string;
    ts?: string;
    from?: string;
  };
  notes?: {
    summary?: string;
    evidence?: string[];
    coach_instructions?: string[];
    data_gaps?: string[];
  };
}

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea, input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function ProvenanceModal({ open, traitId, traitValue, userId, onClose }: ProvenanceModalProps) {
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const previouslyFocused = useRef<Element | null>(null);

  const [provenance, setProvenance] = useState<ProvenanceData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    if (!open) return;

    previouslyFocused.current = document.activeElement;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }

      if (e.key === 'Tab') {
        const dialog = dialogRef.current;
        if (!dialog) return;

        const focusableElements = dialog.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR);
        const firstFocusable = focusableElements[0];
        const lastFocusable = focusableElements[focusableElements.length - 1];

        if (e.shiftKey) {
          if (document.activeElement === firstFocusable) {
            e.preventDefault();
            lastFocusable?.focus();
          }
        } else {
          if (document.activeElement === lastFocusable) {
            e.preventDefault();
            firstFocusable?.focus();
          }
        }
      }
    };

    document.addEventListener('keydown', handleKeyDown);

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      if (previouslyFocused.current instanceof HTMLElement) {
        previouslyFocused.current.focus();
      }
    };
  }, [open, onClose]);

  useEffect(() => {
    if (!open || !traitId || !userId) {
      setProvenance(null);
      setError(null);
      setNotFound(false);
      return;
    }

    setLoading(true);
    setError(null);
    setNotFound(false);

    // Fetch provenance from Core
    fetch(`${CORE_API_BASE}/ui/trait/provenance`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId, trait_id: traitId }),
    })
      .then(res => {
        if (res.status === 404) {
          setNotFound(true);
          setProvenance(null);
          setLoading(false);
          return null;
        }
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then(data => {
        if (data === null) {
          return;
        }
        setProvenance(data);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message || 'Failed to load provenance');
        setLoading(false);
        setNotFound(false);
      });
  }, [open, traitId, userId]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="provenance-title"
        className="bg-white dark:bg-slate-800 rounded-lg shadow-xl max-w-2xl w-full max-h-[80vh] overflow-hidden flex flex-col"
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-slate-200 dark:border-slate-700">
          <h2 id="provenance-title" className="text-lg font-semibold text-slate-900 dark:text-slate-100">
            Why is this trait &ldquo;{traitValue}&rdquo;?
          </h2>
          <button
            onClick={onClose}
            className="p-2 text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200 rounded-md hover:bg-slate-100 dark:hover:bg-slate-700"
            aria-label="Close"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4">
          {loading && (
            <div className="text-center py-8 text-slate-500 dark:text-slate-400">
              Loading provenance...
            </div>
          )}

          {notFound && (
            <div className="rounded-lg border border-orange-500/40 bg-orange-500/10 p-4">
              <p className="text-sm text-orange-200">
                No provenance available yet for this trait. Try generating more observations or rerunning ingestion.
              </p>
            </div>
          )}

          {error && !notFound && (
            <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
              <p className="text-sm text-red-800 dark:text-red-200">
                {error}
              </p>
            </div>
          )}

          {provenance && (
            <div className="space-y-4">
              {/* Trait Info */}
              <div className="bg-slate-50 dark:bg-slate-900 rounded-lg p-4">
                <div className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">Trait ID</div>
                <div className="font-mono text-sm text-slate-900 dark:text-slate-100">{provenance.trait_id}</div>
              </div>

              {/* Scores */}
              <div className="grid grid-cols-3 gap-3">
                {provenance.ucn !== undefined && (
                  <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-3">
                    <div className="text-xs text-blue-600 dark:text-blue-400 mb-1">UCN</div>
                    <div className="text-lg font-semibold text-blue-900 dark:text-blue-100">{provenance.ucn}</div>
                  </div>
                )}
                {provenance.rr !== undefined && (
                  <div className="bg-green-50 dark:bg-green-900/20 rounded-lg p-3">
                    <div className="text-xs text-green-600 dark:text-green-400 mb-1">RR</div>
                    <div className="text-lg font-semibold text-green-900 dark:text-green-100">{provenance.rr}</div>
                  </div>
                )}
                {provenance.curiosity !== undefined && (
                  <div className="bg-purple-50 dark:bg-purple-900/20 rounded-lg p-3">
                    <div className="text-xs text-purple-600 dark:text-purple-400 mb-1">Curiosity</div>
                    <div className="text-lg font-semibold text-purple-900 dark:text-purple-100">
                      {(provenance.curiosity * 100).toFixed(1)}%
                    </div>
                  </div>
                )}
              </div>

              {/* Summary */}
              {provenance.notes?.summary && (
                <div>
                  <div className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">Summary</div>
                  <p className="text-sm text-slate-600 dark:text-slate-400">{provenance.notes.summary}</p>
                </div>
              )}

              {/* Evidence */}
              {provenance.notes?.evidence && provenance.notes.evidence.length > 0 && (
                <div>
                  <div className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">Evidence</div>
                  <ul className="space-y-1">
                    {provenance.notes.evidence.map((item, idx) => (
                      <li key={idx} className="text-sm text-slate-600 dark:text-slate-400 flex items-start gap-2">
                        <span className="text-slate-400 dark:text-slate-500">•</span>
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Provenance */}
              {provenance.provenance && (
                <div>
                  <div className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">Source</div>
                  <div className="bg-slate-50 dark:bg-slate-900 rounded-lg p-3 space-y-1">
                    {provenance.provenance.source && (
                      <div className="text-sm">
                        <span className="text-slate-500 dark:text-slate-400">Type:</span>{' '}
                        <span className="text-slate-900 dark:text-slate-100">{provenance.provenance.source}</span>
                      </div>
                    )}
                    {provenance.provenance.from && (
                      <div className="text-sm">
                        <span className="text-slate-500 dark:text-slate-400">From:</span>{' '}
                        <span className="text-slate-900 dark:text-slate-100">{provenance.provenance.from}</span>
                      </div>
                    )}
                    {provenance.provenance.ts && (
                      <div className="text-sm">
                        <span className="text-slate-500 dark:text-slate-400">Timestamp:</span>{' '}
                        <span className="text-slate-900 dark:text-slate-100">{provenance.provenance.ts}</span>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Reasons */}
              {provenance.reasons && provenance.reasons.length > 0 && (
                <div>
                  <div className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">Reasons</div>
                  <div className="flex flex-wrap gap-2">
                    {provenance.reasons.map((reason, idx) => (
                      <span
                        key={idx}
                        className="px-2 py-1 bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300 text-xs rounded"
                      >
                        {reason}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Data Gaps */}
              {provenance.notes?.data_gaps && provenance.notes.data_gaps.length > 0 && (
                <div>
                  <div className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">Data Gaps</div>
                  <ul className="space-y-1">
                    {provenance.notes.data_gaps.map((gap, idx) => (
                      <li key={idx} className="text-sm text-amber-600 dark:text-amber-400 flex items-start gap-2">
                        <span>⚠️</span>
                        <span>{gap}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 p-4 border-t border-slate-200 dark:border-slate-700">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-slate-200 hover:bg-slate-300 dark:bg-slate-700 dark:hover:bg-slate-600 text-slate-900 dark:text-slate-100 rounded-md transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
