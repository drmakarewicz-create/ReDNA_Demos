'use client';

import { useCallback, useEffect, useRef, useState, type CSSProperties } from 'react';

export interface TourStep {
  id: string;
  title: string;
  description: string;
  targetId?: string;
}

interface IntroTourProps {
  open: boolean;
  steps: TourStep[];
  onRequestClose: (dismissed: boolean) => void;
}

const HIGHLIGHT_PADDING = 12;
const MIN_CALLOUT_WIDTH = 240;
const MAX_CALLOUT_WIDTH = 360;

function buildDefaultCalloutStyle(): CSSProperties {
  return {
    top: window.innerHeight / 2,
    left: window.innerWidth / 2,
    transform: 'translate(-50%, -50%)',
    width: Math.min(MAX_CALLOUT_WIDTH, window.innerWidth - 48)
  };
}

export function IntroTour({ open, steps, onRequestClose }: IntroTourProps) {
  const [stepIndex, setStepIndex] = useState(0);
  const [highlightStyle, setHighlightStyle] = useState<CSSProperties | null>(null);
  const [calloutStyle, setCalloutStyle] = useState<CSSProperties>(() =>
    typeof window === 'undefined'
      ? { top: '50%', left: '50%', transform: 'translate(-50%, -50%)', width: MAX_CALLOUT_WIDTH }
      : buildDefaultCalloutStyle()
  );
  const lastTargetIdRef = useRef<string | null>(null);

  const totalSteps = steps.length;
  const activeStep = steps[Math.min(stepIndex, totalSteps - 1)] ?? steps[0];

  const retreat = useCallback(() => {
    setStepIndex((prev) => Math.max(prev - 1, 0));
  }, []);

  const advance = useCallback(() => {
    setStepIndex((prev) => {
      if (prev >= totalSteps - 1) {
        onRequestClose(true);
        return prev;
      }
      return prev + 1;
    });
  }, [onRequestClose, totalSteps]);

  const updatePositions = useCallback(() => {
    if (typeof window === 'undefined') {
      return;
    }
    const step = steps[Math.min(stepIndex, totalSteps - 1)];
    if (!step) {
      setHighlightStyle(null);
      setCalloutStyle(buildDefaultCalloutStyle());
      return;
    }
    const targetId = step.targetId?.trim();
    const target = targetId ? document.getElementById(targetId) : null;
    if (!target) {
      setHighlightStyle(null);
      setCalloutStyle(buildDefaultCalloutStyle());
      return;
    }

    if (targetId && lastTargetIdRef.current !== targetId) {
      target.scrollIntoView({ block: 'center', inline: 'center', behavior: 'smooth' });
      lastTargetIdRef.current = targetId;
    }

    const rect = target.getBoundingClientRect();
    const paddedTop = Math.max(rect.top - HIGHLIGHT_PADDING, 8);
    const paddedLeft = Math.max(rect.left - HIGHLIGHT_PADDING, 8);
    const paddedWidth = Math.min(rect.width + HIGHLIGHT_PADDING * 2, window.innerWidth - paddedLeft - 8);
    const paddedHeight = Math.min(rect.height + HIGHLIGHT_PADDING * 2, window.innerHeight - paddedTop - 8);

    setHighlightStyle({
      top: paddedTop,
      left: paddedLeft,
      width: paddedWidth,
      height: paddedHeight
    });

    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;
    const margin = 16;
    const calloutWidth = Math.max(
      MIN_CALLOUT_WIDTH,
      Math.min(MAX_CALLOUT_WIDTH, viewportWidth - 48)
    );

    let top = rect.bottom + margin;
    let translateY = '0';
    if (top + 220 > viewportHeight) {
      top = rect.top - margin;
      translateY = '-100%';
    }
    top = Math.min(Math.max(top, 24), viewportHeight - 24);

    let left = rect.left + rect.width / 2;
    left = Math.min(Math.max(left, 24), viewportWidth - 24);

    setCalloutStyle({
      top,
      left,
      transform: `translate(-50%, ${translateY})`,
      width: calloutWidth
    });
  }, [stepIndex, steps, totalSteps]);

  useEffect(() => {
    if (!open) {
      return;
    }
    setStepIndex(0);
    lastTargetIdRef.current = null;
  }, [open]);

  useEffect(() => {
    if (!open) {
      return;
    }
    const handler = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        onRequestClose(true);
      } else if (event.key === 'ArrowRight' || event.key === 'Enter') {
        event.preventDefault();
        advance();
      } else if (event.key === 'ArrowLeft') {
        event.preventDefault();
        retreat();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, onRequestClose, advance, retreat]);

  useEffect(() => {
    if (!open) {
      return;
    }
    const cleanupList: Array<() => void> = [];

    const sync = () => updatePositions();
    sync();
    const resizeListener = () => sync();
    const scrollListener = () => sync();
    window.addEventListener('resize', resizeListener);
    window.addEventListener('scroll', scrollListener, true);
    cleanupList.push(() => window.removeEventListener('resize', resizeListener));
    cleanupList.push(() => window.removeEventListener('scroll', scrollListener, true));

    const timer = window.setTimeout(sync, 120);
    cleanupList.push(() => window.clearTimeout(timer));

    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    cleanupList.push(() => {
      document.body.style.overflow = originalOverflow;
    });

    return () => {
      cleanupList.forEach((fn) => {
        try {
          fn();
        } catch (error) {
          console.warn('Failed to cleanup tour listener', error);
        }
      });
    };
  }, [open, stepIndex, updatePositions]);

  if (!open || !activeStep) {
    return null;
  }

  const stepNumber = Math.min(stepIndex + 1, totalSteps);
  const isLastStep = stepNumber === totalSteps;

  return (
    <div className="fixed inset-0 z-[80]" role="dialog" aria-modal="true" aria-label="Head Coach guided tour">
      <div className="absolute inset-0 bg-slate-950/70 backdrop-blur-sm" />
      {highlightStyle ? (
        <div
          className="pointer-events-none fixed z-[81] rounded-2xl border-2 border-cyan-400/80 shadow-[0_0_0_9999px_rgba(15,23,42,0.65)] transition-all duration-200"
          style={highlightStyle}
          aria-hidden="true"
        />
      ) : null}
      <div
        className="pointer-events-auto fixed z-[82] max-w-sm rounded-2xl border border-cyan-400/60 bg-slate-900/95 p-5 text-slate-100 shadow-2xl"
        style={calloutStyle}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-wide text-cyan-300">Step {stepNumber} of {totalSteps}</p>
            <h2 className="mt-1 text-lg font-semibold text-slate-50">{activeStep.title}</h2>
          </div>
          <button
            type="button"
            className="rounded-full border border-slate-700 px-2 py-1 text-xs text-slate-300 hover:border-slate-500"
            onClick={() => onRequestClose(true)}
          >
            Skip
          </button>
        </div>
        <p className="mt-3 text-sm text-slate-300">{activeStep.description}</p>
        <div className="mt-4 flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="rounded-full border border-slate-700 px-3 py-1 text-xs font-semibold text-slate-200 hover:border-slate-500 disabled:opacity-40"
              onClick={retreat}
              disabled={stepIndex === 0}
            >
              Back
            </button>
            <button
              type="button"
              className="rounded-full border border-cyan-500/70 bg-cyan-500/10 px-3 py-1 text-xs font-semibold text-cyan-200 hover:bg-cyan-500/20"
              onClick={advance}
            >
              {isLastStep ? 'Finish' : 'Next'}
            </button>
          </div>
          <span className="text-[11px] uppercase tracking-wide text-slate-500">Press Esc to close</span>
        </div>
      </div>
    </div>
  );
}
