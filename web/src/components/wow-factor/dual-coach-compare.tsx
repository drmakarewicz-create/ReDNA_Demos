'use client';

import { useState } from 'react';
import { CORE_API_BASE } from '../../lib/api';

interface CoachResponse {
  coach_id: string;
  mandate_length: number;
  prompt_preview: string;
  tone_hints: string | null;
  creativity_bias: number | null;
  response: string;
}

interface ComparisonResult {
  coach_a: CoachResponse;
  coach_b: CoachResponse;
  differences: {
    mandate_length_delta: number;
    tone_divergence: boolean;
  };
}

interface DualCoachCompareProps {
  userId: string;
  availableCoaches?: string[];
}

const DEFAULT_COACHES = [
  'head_coach',
  'career_coach',
  'relationship_coach',
  'padna_coach',
  'chatdna_coach',
  'beliefdna_coach',
];

export function DualCoachCompare({
  userId,
  availableCoaches = DEFAULT_COACHES,
}: DualCoachCompareProps) {
  const [coachA, setCoachA] = useState(availableCoaches[0]);
  const [coachB, setCoachB] = useState(availableCoaches[1] || availableCoaches[0]);
  const [prompt, setPrompt] = useState('');
  const [comparison, setComparison] = useState<ComparisonResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCompare = async () => {
    if (!prompt.trim()) {
      setError('Please enter a prompt');
      return;
    }

    if (coachA === coachB) {
      setError('Please select two different coaches');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(
        `${CORE_API_BASE}/ui/hc/dual_coach_compare?user_id=${userId}&coach_a=${coachA}&coach_b=${coachB}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ prompt }),
        }
      );

      const json = await response.json();

      if (json.ok && json.comparison) {
        setComparison(json.comparison);
      } else {
        setError(json.detail || 'Comparison failed');
      }
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  };

  const formatCoachName = (coachId: string) =>
    coachId
      .replace('_coach', '')
      .replace('_', ' ')
      .split(' ')
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(' ');

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6">
      <h2 className="mb-4 text-lg font-semibold text-slate-200">
        Dual-Coach Comparison
      </h2>

      {/* Coach Selection */}
      <div className="mb-4 grid grid-cols-2 gap-4">
        <div>
          <label className="mb-2 block text-xs font-medium text-slate-400">
            Coach A
          </label>
          <select
            value={coachA}
            onChange={(e) => setCoachA(e.target.value)}
            className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-300 focus:border-blue-500 focus:outline-none"
          >
            {availableCoaches.map((coach) => (
              <option key={coach} value={coach}>
                {formatCoachName(coach)}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-2 block text-xs font-medium text-slate-400">
            Coach B
          </label>
          <select
            value={coachB}
            onChange={(e) => setCoachB(e.target.value)}
            className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-300 focus:border-blue-500 focus:outline-none"
          >
            {availableCoaches.map((coach) => (
              <option key={coach} value={coach}>
                {formatCoachName(coach)}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Prompt Input */}
      <div className="mb-4">
        <label className="mb-2 block text-xs font-medium text-slate-400">
          Prompt
        </label>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="Enter a prompt to send to both coaches..."
          rows={3}
          className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-300 placeholder-slate-500 focus:border-blue-500 focus:outline-none"
        />
      </div>

      {/* Compare Button */}
      <button
        onClick={handleCompare}
        disabled={loading || !prompt.trim()}
        className="w-full rounded-lg bg-blue-900/50 px-4 py-2.5 text-sm font-medium text-blue-300 hover:bg-blue-800/50 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading ? 'Comparing...' : 'Compare Coaches'}
      </button>

      {/* Error Display */}
      {error && (
        <div className="mt-4 rounded-lg border border-red-800/30 bg-red-950/20 p-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {/* Comparison Results */}
      {comparison && (
        <div className="mt-6 space-y-4">
          {/* Differences Summary */}
          <div className="rounded-lg border border-yellow-800/30 bg-yellow-950/20 p-4">
            <h3 className="mb-3 text-sm font-semibold text-yellow-300">
              Key Differences
            </h3>
            <div className="space-y-2 text-xs">
              <div className="flex justify-between">
                <span className="text-slate-400">Mandate Length Delta:</span>
                <span className="font-semibold text-slate-300">
                  {comparison.differences.mandate_length_delta} chars
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Tone Divergence:</span>
                <span className="font-semibold text-slate-300">
                  {comparison.differences.tone_divergence ? 'Yes' : 'No'}
                </span>
              </div>
            </div>
          </div>

          {/* Split View */}
          <div className="grid grid-cols-2 gap-4">
            {/* Coach A */}
            <div className="rounded-lg border border-blue-800/30 bg-blue-950/20 p-4">
              <h3 className="mb-3 text-sm font-semibold text-blue-300">
                {formatCoachName(comparison.coach_a.coach_id)}
              </h3>
              <div className="space-y-3">
                <div>
                  <div className="mb-1 text-xs text-slate-400">Mandate Length</div>
                  <div className="font-semibold text-slate-300">
                    {comparison.coach_a.mandate_length} chars
                  </div>
                </div>
                {comparison.coach_a.tone_hints && (
                  <div>
                    <div className="mb-1 text-xs text-slate-400">Tone</div>
                    <div className="rounded bg-blue-900/30 px-2 py-1 text-xs font-medium text-blue-300">
                      {comparison.coach_a.tone_hints}
                    </div>
                  </div>
                )}
                {comparison.coach_a.creativity_bias !== null && (
                  <div>
                    <div className="mb-1 text-xs text-slate-400">Creativity Bias</div>
                    <div className="font-mono text-sm text-slate-300">
                      {comparison.coach_a.creativity_bias.toFixed(2)}
                    </div>
                  </div>
                )}
                <div>
                  <div className="mb-1 text-xs text-slate-400">Prompt Preview</div>
                  <div className="max-h-32 overflow-y-auto rounded bg-slate-950/50 p-2 font-mono text-xs text-slate-400">
                    {comparison.coach_a.prompt_preview}
                  </div>
                </div>
                <div>
                  <div className="mb-1 text-xs text-slate-400">Response (Demo)</div>
                  <div className="rounded bg-slate-950/50 p-2 text-xs italic text-slate-400">
                    {comparison.coach_a.response}
                  </div>
                </div>
              </div>
            </div>

            {/* Coach B */}
            <div className="rounded-lg border border-purple-800/30 bg-purple-950/20 p-4">
              <h3 className="mb-3 text-sm font-semibold text-purple-300">
                {formatCoachName(comparison.coach_b.coach_id)}
              </h3>
              <div className="space-y-3">
                <div>
                  <div className="mb-1 text-xs text-slate-400">Mandate Length</div>
                  <div className="font-semibold text-slate-300">
                    {comparison.coach_b.mandate_length} chars
                  </div>
                </div>
                {comparison.coach_b.tone_hints && (
                  <div>
                    <div className="mb-1 text-xs text-slate-400">Tone</div>
                    <div className="rounded bg-purple-900/30 px-2 py-1 text-xs font-medium text-purple-300">
                      {comparison.coach_b.tone_hints}
                    </div>
                  </div>
                )}
                {comparison.coach_b.creativity_bias !== null && (
                  <div>
                    <div className="mb-1 text-xs text-slate-400">Creativity Bias</div>
                    <div className="font-mono text-sm text-slate-300">
                      {comparison.coach_b.creativity_bias.toFixed(2)}
                    </div>
                  </div>
                )}
                <div>
                  <div className="mb-1 text-xs text-slate-400">Prompt Preview</div>
                  <div className="max-h-32 overflow-y-auto rounded bg-slate-950/50 p-2 font-mono text-xs text-slate-400">
                    {comparison.coach_b.prompt_preview}
                  </div>
                </div>
                <div>
                  <div className="mb-1 text-xs text-slate-400">Response (Demo)</div>
                  <div className="rounded bg-slate-950/50 p-2 text-xs italic text-slate-400">
                    {comparison.coach_b.response}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
