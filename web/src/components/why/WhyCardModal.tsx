'use client';

import { useEffect, useMemo, useRef, useState } from 'react';

import { fetchWhyCard, type WhyCardResponse } from '../../lib/coreApi';

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea, input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

interface WhyCardModalProps {
  userId: string;
  traitId: string;
  traitLabel?: string;
  value?: string | null;
  open: boolean;
  onClose: () => void;
}

const formatPercent = (value?: number | null): string | null => {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return null;
  }
  const scaled = Math.abs(value) <= 1 ? value * 100 : value;
  return `${scaled.toFixed(1)}%`;
};

const formatInterval = (interval?: [number | null, number | null]): string | null => {
  if (!interval) return null;
  const [low, high] = interval;
  const formattedLow = formatPercent(low);
  const formattedHigh = formatPercent(high);
  if (!formattedLow || !formattedHigh) return null;
  return `${formattedLow} - ${formattedHigh}`;
};

const formatRelativeTime = (timestamp?: string | null): string | null => {
  if (!timestamp) return null;
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return null;

  const diffMs = Date.now() - date.getTime();
  const divisions: Array<[number, Intl.RelativeTimeFormatUnit]> = [
    [60, 'seconds'],
    [60, 'minutes'],
    [24, 'hours'],
    [7, 'days'],
    [4.345, 'weeks'],
    [12, 'months'],
    [Number.POSITIVE_INFINITY, 'years'],
  ];

  let duration = Math.round(diffMs / 1000);
  let unit: Intl.RelativeTimeFormatUnit = 'seconds';
  for (const [amount, nextUnit] of divisions) {
    if (Math.abs(duration) < amount) {
      unit = nextUnit;
      break;
    }
    duration = Math.round(duration / amount);
  }

  const formatter = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' });
  return formatter.format(-duration, unit);
};

export function WhyCardModal({ userId, traitId, traitLabel, value, open, onClose }: WhyCardModalProps) {
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const previousFocus = useRef<Element | null>(null);

  const [state, setState] = useState<'idle' | 'loading' | 'success' | 'not-found' | 'error'>('idle');
  const [card, setCard] = useState<WhyCardResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;

    previousFocus.current = document.activeElement;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose();
      }

      if (event.key === 'Tab') {
        const dialog = dialogRef.current;
        if (!dialog) return;
        const focusable = dialog.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR);
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey) {
          if (document.activeElement === first) {
            event.preventDefault();
            last?.focus();
          }
        } else if (document.activeElement === last) {
          event.preventDefault();
          first?.focus();
        }
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      if (previousFocus.current instanceof HTMLElement) {
        previousFocus.current.focus();
      }
    };
  }, [open, onClose]);

  useEffect(() => {
    if (!open) {
      setState('idle');
      setCard(null);
      setError(null);
      return;
    }

    if (!userId || !traitId) {
      setState('error');
      setError('Missing user or trait identifier.');
      return;
    }

    let cancelled = false;
    setState('loading');
    setCard(null);
    setError(null);

    fetchWhyCard(userId, traitId)
      .then((result) => {
        if (cancelled) return;
        if ('notFound' in result) {
          setState('not-found');
          setCard(null);
          return;
        }
        setCard(result);
        setState('success');
      })
      .catch((err: Error) => {
        if (cancelled) return;
        setError(err.message || 'Failed to fetch Why-Card.');
        setState('error');
      });

    return () => {
      cancelled = true;
    };
  }, [open, userId, traitId]);

  const displayValue = useMemo(() => {
    if (card?.value && typeof card.value === 'string' && card.value.trim()) {
      return card.value;
    }
    if (value) return value;
    return '—';
  }, [card?.value, value]);

  const narrative = useMemo(() => {
    if (card?.why) {
      const trimmed = card.why.trim();
      if (trimmed) return trimmed;
    }
    return null;
  }, [card?.why]);

  const confidenceDisplay = useMemo(() => {
    const base = formatPercent(card?.confidence?.point_estimate ?? card?.rr ?? null);
    if (!base) return null;
    const interval = formatInterval(card?.confidence?.interval_95);
    return interval ? `${base} (95% ${interval})` : base;
  }, [card?.confidence, card?.rr]);

  const evidenceItems = useMemo(() => {
    if (!card?.evidence || !Array.isArray(card.evidence)) return [];
    return card.evidence
      .map((entry) => {
        if (!entry) return null;
        if (typeof entry === 'string') {
          return { text: entry, source: null };
        }
        if (typeof entry === 'object') {
          return {
            text: entry.summary ?? entry.text ?? null,
            source: entry.source ?? null,
          };
        }
        return null;
      })
      .filter((entry): entry is { text: string | null; source: string | null } => Boolean(entry && (entry.text || entry.source)))
      .slice(0, 3);
  }, [card?.evidence]);

  const timestamp = card?.ts ?? card?.created_at;
  const relativeTime = formatRelativeTime(timestamp ?? undefined);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[120] flex items-center justify-center bg-slate-950/80 p-4">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="whycard-title"
        aria-describedby="whycard-content"
        className="flex max-h-[85vh] w-full max-w-2xl flex-col overflow-hidden rounded-xl border border-slate-800 bg-slate-950 shadow-2xl"
      >
        <div className="flex items-start justify-between border-b border-slate-800 px-5 py-4">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">Why-Card</p>
            <h2 id="whycard-title" className="mt-1 text-lg font-semibold text-slate-100">
              {traitLabel || traitId}
            </h2>
            <p className="mt-1 text-sm text-slate-400">
              Value: <span className="font-medium text-slate-200">{displayValue}</span>
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-md p-2 text-slate-400 hover:bg-slate-800 hover:text-slate-200 focus:outline-none focus-visible:ring focus-visible:ring-cyan-500"
            aria-label="Close Why-Card modal"
          >
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div id="whycard-content" className="flex-1 overflow-y-auto px-5 py-4">
          {state === 'loading' && (
            <div className="flex flex-col items-center justify-center gap-3 py-10 text-sm text-slate-400">
              <svg className="h-6 w-6 animate-spin text-cyan-400" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
              </svg>
              <span>Fetching Why-Card…</span>
            </div>
          )}

          {state === 'error' && (
            <div className="rounded-lg border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-200">
              Couldn&apos;t fetch explanation. {error || 'Please try again.'}
            </div>
          )}

          {state === 'not-found' && (
            <div className="space-y-4 text-sm text-slate-300">
              <p>No Why-Card yet for this trait. Try interacting more or providing a clarification.</p>
              <button
                onClick={onClose}
                className="rounded-md border border-slate-700 px-3 py-2 text-xs font-medium text-slate-200 hover:bg-slate-800"
              >
                Suggest a follow-up question
              </button>
            </div>
          )}

          {state === 'success' && card && (
            <div className="space-y-6">
              <section>
                <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-400">Summary</h3>
                <p className="mt-2 whitespace-pre-line text-sm leading-relaxed text-slate-200">
                  {narrative ?? 'No narrative available.'}
                </p>
              </section>

              <section className="grid gap-3 sm:grid-cols-2">
                {confidenceDisplay && (
                  <div className="rounded-lg border border-cyan-500/40 bg-cyan-500/10 p-3">
                    <p className="text-xs uppercase tracking-wide text-cyan-300">Confidence</p>
                    <p className="mt-1 text-sm font-semibold text-cyan-100">{confidenceDisplay}</p>
                  </div>
                )}
                {card.rr !== undefined && card.rr !== null && (
                  <div className="rounded-lg border border-slate-700 bg-slate-900/60 p-3">
                    <p className="text-xs uppercase tracking-wide text-slate-400">Readiness Score</p>
                    <p className="mt-1 text-sm font-semibold text-slate-100">{card.rr.toFixed(1)}</p>
                  </div>
                )}
              </section>

              {evidenceItems.length > 0 && (
                <section>
                  <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-400">Evidence</h3>
                  <ul className="mt-2 list-disc space-y-2 pl-5 text-sm text-slate-200">
                    {evidenceItems.map((item, index) => (
                      <li key={index}>
                        {item.source ? <span className="text-slate-400">{item.source}: </span> : null}
                        <span>{item.text ?? 'No evidence text provided.'}</span>
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              <section className="text-xs text-slate-500">
                <p>
                  Source: <span className="text-slate-300">{card.source ?? 'Unknown'}</span>
                </p>
                {timestamp && (
                  <p className="mt-1">
                    Created{' '}
                    <span className="text-slate-300">
                      {relativeTime ?? '—'}
                      {relativeTime ? ` (${new Date(timestamp).toLocaleString()})` : null}
                    </span>
                  </p>
                )}
              </section>
            </div>
          )}
        </div>

        <div className="flex justify-end border-t border-slate-800 px-5 py-3">
          <button
            onClick={onClose}
            className="rounded-md border border-slate-700 px-4 py-2 text-sm font-medium text-slate-200 hover:bg-slate-800 focus:outline-none focus-visible:ring focus-visible:ring-cyan-500"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

