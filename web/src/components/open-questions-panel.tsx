'use client';

import React, { useEffect, useState } from 'react';
import { PanelSkeleton } from './panel-skeleton';
import { PanelError } from './panel-error';
import type { NextQuestionCandidate } from '@/lib/curiosityClient';

interface OpenQuestionsPanelProps {
  userId: string;
  questions: NextQuestionCandidate[];
  loading: boolean;
  error: string | null;
  onRetry?: () => void;
  onAsk: (question: NextQuestionCandidate) => void;
}

const formatConfidence = (value: number | undefined): string => {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return '—';
  }
  const percentage = Math.max(0, Math.min(1, value)) * 100;
  return `${Math.round(percentage)}%`;
};

export function OpenQuestionsPanel({
  userId,
  questions,
  loading,
  error,
  onRetry,
  onAsk,
}: OpenQuestionsPanelProps) {
  const [expanded, setExpanded] = useState(true);

  useEffect(() => {
    if (questions.length > 0) {
      setExpanded(true);
    }
  }, [questions.length]);

  const handleAsk = (question: NextQuestionCandidate) => {
    if (!question?.question_text?.trim()) return;
    onAsk(question);
  };

  const graphPathLabel = (question: NextQuestionCandidate) => {
    if (!Array.isArray(question.graph_path) || question.graph_path.length === 0) {
      return undefined;
    }
    return question.graph_path.join(' → ');
  };

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4 shadow-lg">
      <div className="mb-3 flex items-center justify-between gap-2">
        <button
          type="button"
          onClick={() => setExpanded((prev) => !prev)}
          className="flex flex-1 items-center justify-between gap-3 text-left"
        >
          <div>
            <div className="text-sm font-semibold text-cyan-200">Open Questions</div>
            <div className="text-xs text-slate-400">
              Graph-driven follow-ups for <span className="font-semibold text-slate-200">{userId || '—'}</span>
            </div>
          </div>
          <span className="text-lg text-cyan-200" aria-hidden>
            {expanded ? '▾' : '▸'}
          </span>
        </button>
        {onRetry ? (
          <button
            type="button"
            onClick={onRetry}
            className="rounded-md border border-cyan-600/60 px-3 py-1 text-xs font-medium text-cyan-200 transition hover:bg-cyan-500/10"
          >
            Refresh
          </button>
        ) : null}
      </div>

      {expanded && (
        <>
          {loading ? (
            <PanelSkeleton rows={3} columns={1} />
          ) : error ? (
            <PanelError message={error} onRetry={onRetry} />
          ) : questions.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-700 bg-slate-900/60 p-4 text-sm text-slate-400">
              No open questions right now. Keep exploring—new evidence will unlock follow-ups.
            </div>
          ) : (
            <ul className="space-y-3">
              {questions.map((question) => (
                <li
                  key={`${question.target_trait_id}-${question.question_text}`}
                  className="rounded-xl border border-slate-800 bg-slate-900/50 p-3 transition hover:border-cyan-500/50"
                  title={graphPathLabel(question)}
                >
                  <div className="flex items-start gap-3">
                    <div className="flex-1">
                      <div className="text-sm text-slate-200">{question.question_text}</div>
                      <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-400">
                        {question.target_trait_id ? (
                          <span className="rounded-full border border-slate-700 px-2 py-0.5 text-[11px] uppercase tracking-wide text-slate-300">
                            {question.target_trait_id}
                          </span>
                        ) : null}
                        {question.rationale ? (
                          <span className="text-[11px] text-slate-500">{question.rationale}</span>
                        ) : null}
                      </div>
                    </div>
                    <div className="flex flex-col items-end gap-2">
                      <span className="text-xs font-mono text-slate-400">{formatConfidence(question.confidence)}</span>
                      <button
                        type="button"
                        onClick={() => handleAsk(question)}
                        className="rounded-md border border-cyan-500/50 px-3 py-1 text-xs font-semibold text-cyan-200 transition hover:bg-cyan-500/10"
                      >
                        Ask
                      </button>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}

OpenQuestionsPanel.displayName = 'OpenQuestionsPanel';
