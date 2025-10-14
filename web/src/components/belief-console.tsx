'use client';

import { useState } from 'react';
import { BeliefReasonMap } from './belief-reason-map';
import { EvidenceLinks } from './evidence-links';

const API_BASE = process.env.NEXT_PUBLIC_CORE_API_BASE ?? 'http://127.0.0.1:8000';

interface BeliefResponse {
  output: string;
  reason_map: Array<{
    trait: string;
    rr: number;
    weight: number;
    influence: string;
  }>;
  similarity: {
    conceptual: number;
    linguistic: number;
    overall: number;
  };
  relevant_containers: Array<{
    path: string;
    similarity: number;
    rr: number;
  }>;
  rr_summary: {
    BeliefValueDNA?: number;
    CogDNA?: number;
    MotivationDNA?: number;
    PsyDNA?: number;
    EmDNA?: number;
  };
}

interface PromptTemplate {
  id: string;
  prompt: string;
}

interface BeliefConsoleProps {
  userId: string;
  templates: PromptTemplate[];
}

export function BeliefConsole({ userId, templates }: BeliefConsoleProps) {
  const [prompt, setPrompt] = useState('');
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<BeliefResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [rating, setRating] = useState<number | null>(null);

  const handleSubmit = async (questionText?: string) => {
    const finalPrompt = questionText || prompt;
    if (!finalPrompt.trim()) return;

    try {
      setLoading(true);
      setError(null);
      setRating(null);

      const res = await fetch(`${API_BASE}/api/coach/beliefdna_coach/render`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          prompt: finalPrompt,
          intent: 'moral'
        })
      });

      if (!res.ok) {
        throw new Error('Failed to generate response');
      }

      const data = await res.json();
      setResponse(data);
      setPrompt('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const handleRating = async (stars: number) => {
    if (!response || !prompt) return;

    setRating(stars);

    try {
      await fetch(`${API_BASE}/api/coach/beliefdna_coach/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          prompt: prompt,
          output: response.output,
          user_rating: stars,
          notes: ''
        })
      });
    } catch (err) {
      console.error('Failed to submit feedback:', err);
    }
  };

  const handleTemplateClick = (template: PromptTemplate) => {
    handleSubmit(template.prompt);
  };

  return (
    <div className="space-y-4">
      {/* Prompt Templates */}
      {templates && templates.length > 0 && !response && (
        <div className="rounded-xl border border-purple-500/20 bg-slate-950/40 p-6">
          <h4 className="text-sm font-semibold text-purple-200 mb-3">Question Starters</h4>
          <div className="grid grid-cols-2 gap-2">
            {templates.slice(0, 6).map((template) => (
              <button
                key={template.id}
                onClick={() => handleTemplateClick(template)}
                className="px-3 py-2 rounded-lg bg-purple-500/10 hover:bg-purple-500/20 border border-purple-500/30 text-left text-sm text-slate-300 transition-colors"
                disabled={loading}
              >
                {template.prompt}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Chat Input */}
      <div className="rounded-xl border border-purple-500/30 bg-gradient-to-br from-purple-950/40 to-slate-950/60 p-6">
        <div className="flex items-center gap-3 mb-4">
          <span className="text-2xl">🤔</span>
          <h3 className="text-lg font-semibold text-purple-200">Ask a Philosophical Question</h3>
        </div>

        <div className="space-y-3">
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSubmit();
              }
            }}
            placeholder="e.g., Do humans have free will? Is lying ever morally acceptable?"
            className="w-full px-4 py-3 rounded-lg bg-slate-900/60 border border-purple-500/30 text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500/50 resize-none"
            rows={3}
            disabled={loading}
          />

          <div className="flex items-center justify-between">
            <div className="text-xs text-slate-500">
              Press Enter to submit, Shift+Enter for new line
            </div>
            <button
              onClick={() => handleSubmit()}
              disabled={loading || !prompt.trim()}
              className="px-4 py-2 rounded-lg bg-purple-600 hover:bg-purple-500 disabled:bg-slate-700 disabled:text-slate-500 text-white font-medium transition-colors"
            >
              {loading ? 'Thinking...' : 'Ask'}
            </button>
          </div>
        </div>

        {error && (
          <div className="mt-3 p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-sm">
            {error}
          </div>
        )}
      </div>

      {/* Response */}
      {response && (
        <div className="space-y-4">
          {/* Answer */}
          <div className="rounded-xl border border-purple-500/30 bg-gradient-to-br from-purple-950/40 to-slate-950/60 p-6">
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-sm font-semibold text-purple-200">Your Belief Simulation</h4>
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-400">Overall Match:</span>
                <span className="text-sm font-medium text-purple-300">
                  {Math.round(response.similarity.overall * 100)}%
                </span>
              </div>
            </div>

            <p className="text-base text-slate-200 leading-relaxed mb-4">
              {response.output}
            </p>

            {/* Rating */}
            <div className="pt-4 border-t border-purple-500/20">
              <div className="flex items-center gap-3">
                <span className="text-xs text-slate-400">How accurate is this?</span>
                <div className="flex gap-1">
                  {[1, 2, 3, 4, 5].map((stars) => (
                    <button
                      key={stars}
                      onClick={() => handleRating(stars)}
                      className={`text-lg transition-all ${
                        rating !== null && stars <= rating
                          ? 'text-yellow-400 scale-110'
                          : 'text-slate-600 hover:text-yellow-500'
                      }`}
                    >
                      ★
                    </button>
                  ))}
                </div>
                {rating !== null && (
                  <span className="text-xs text-green-400 ml-2">
                    Thanks! Your ReDNA will be updated.
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Transparency Panels */}
          <BeliefReasonMap reasonMap={response.reason_map} rr_summary={response.rr_summary} />
          <EvidenceLinks containers={response.relevant_containers} />

          {/* Ask Another */}
          <button
            onClick={() => setResponse(null)}
            className="w-full px-4 py-2 rounded-lg border border-purple-500/30 text-purple-300 hover:bg-purple-500/10 transition-colors"
          >
            Ask Another Question
          </button>
        </div>
      )}
    </div>
  );
}
