'use client';

import { useEffect, useMemo, useRef, useState } from 'react';

import { PanelSkeleton } from '@/components/panel-skeleton';
import { fetchWhyCard, type WhyCardResponse } from '../../lib/coreApi';
import { formatTraitValue, shapeWhyCard } from '../../lib/provenanceClient';
import { WhyCardDetails } from '../provenance/why-card-panel';

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea, input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

interface WhyCardModalProps {
  userId: string;
  traitId: string;
  traitLabel?: string;
  value?: unknown;
  open: boolean;
  onClose: () => void;
}

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
    const metadata = card?.metadata ?? {};
    const metadataValue =
      (metadata as Record<string, unknown>)?.trait_value ??
      (metadata as Record<string, unknown>)?.value ??
      (metadata as Record<string, unknown>)?.resolved_value ??
      null;

    if (metadataValue !== null && metadataValue !== undefined) {
      return formatTraitValue(metadataValue);
    }

    if (card?.value !== undefined && card?.value !== null) {
      return formatTraitValue(card.value);
    }

    if (value !== undefined) {
      return formatTraitValue(value);
    }

    return '—';
  }, [card?.metadata, card?.value, value]);

  const shapedCard = useMemo(() => shapeWhyCard(card as any, value), [card, value]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      role="dialog"
      aria-modal="true"
    >
      <div
        ref={dialogRef}
        className="w-full max-w-3xl rounded-2xl bg-white p-6 shadow-2xl"
      >
        <header className="mb-4 flex items-start justify-between gap-4">
          <div>
            <div className="text-xs uppercase tracking-wide text-gray-500">Why-Card</div>
            <h2 className="text-lg font-semibold text-gray-900">{traitLabel || traitId}</h2>
            <div className="mt-1 text-sm text-gray-500">
              <span className="font-medium text-gray-700">Value:</span>{' '}
              <span className="text-gray-900">{displayValue}</span>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-gray-200 px-3 py-1 text-sm text-gray-500 hover:bg-gray-100"
          >
            Close
          </button>
        </header>

        {state === 'loading' && <PanelSkeleton rows={4} columns={1} className="rounded-md border border-gray-200 p-3" />}

        {state === 'error' && error && (
          <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            {error}
          </div>
        )}

        {state === 'not-found' && (
          <div className="rounded-md border border-amber-200 bg-amber-50 p-4 text-sm text-amber-700">
            No Why-Card yet for this trait. Try interacting more or providing a clarification.
          </div>
        )}

        {state === 'success' && <WhyCardDetails shaped={shapedCard} />}
      </div>
    </div>
  );
}
