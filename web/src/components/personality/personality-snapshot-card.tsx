'use client';

import { useEffect, useState } from 'react';

interface PersonalitySnapshot {
  psydna_rr: number;
  top_strengths: string[];
  top_curiosity: string[];
  active_intent: string;
  factors_assessed: number;
}

interface PersonalitySnapshotCardProps {
  userId: string;
}

const INTENT_LABELS: Record<string, string> = {
  discover_self: "Discover Self",
  track_growth: "Track Growth",
  compare_over_time: "Compare Over Time"
};

const INTENT_COLORS: Record<string, string> = {
  discover_self: "bg-violet-500/20 text-violet-200 border-violet-500/30",
  track_growth: "bg-indigo-500/20 text-indigo-200 border-indigo-500/30",
  compare_over_time: "bg-purple-500/20 text-purple-200 border-purple-500/30"
};

/**
 * PersonalitySnapshotCard - Header widget for PTC
 *
 * Displays:
 * - Overall PsyDNA RR score
 * - Top 3 personality strengths (high RR traits)
 * - Top 3 high-curiosity areas (traits to explore)
 * - Active intent badge (discover/track/compare)
 * - Assessment progress (X/5 BigFive factors assessed)
 *
 * Data source: /api/coach/personality_test_coach/panel
 */
export function PersonalitySnapshotCard({ userId }: PersonalitySnapshotCardProps) {
  const [snapshot, setSnapshot] = useState<PersonalitySnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchSnapshot() {
      try {
        const baseUrl = process.env.NEXT_PUBLIC_CORE_API_BASE || 'http://127.0.0.1:8000';
        const response = await fetch(
          `${baseUrl}/api/coach/personality_test_coach/panel?user_id=${encodeURIComponent(userId)}`
        );

        if (!response.ok) {
          throw new Error(`API error: ${response.status}`);
        }

        const data = await response.json();
        setSnapshot(data.snapshot);
        setLoading(false);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load personality snapshot');
        setLoading(false);
      }
    }

    fetchSnapshot();
  }, [userId]);

  if (loading) {
    return (
      <div className="rounded-2xl border border-violet-500/30 bg-gradient-to-br from-violet-950/40 to-slate-950/60 p-6">
        <div className="flex items-center gap-2 mb-4">
          <span className="text-2xl">🧠</span>
          <h3 className="text-lg font-semibold text-violet-200">Personality Overview</h3>
        </div>
        <p className="text-sm text-slate-400">Loading personality data...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-2xl border border-red-500/30 bg-gradient-to-br from-red-950/40 to-slate-950/60 p-6">
        <div className="flex items-center gap-2 mb-4">
          <span className="text-2xl">⚠️</span>
          <h3 className="text-lg font-semibold text-red-200">Error Loading Personality</h3>
        </div>
        <p className="text-sm text-red-300">{error}</p>
      </div>
    );
  }

  if (!snapshot) return null;

  // Determine RR color coding
  const getRRColor = (rr: number): string => {
    if (rr >= 70) return 'text-green-400';
    if (rr >= 50) return 'text-yellow-400';
    return 'text-red-400';
  };

  const getRRLabel = (rr: number): string => {
    if (rr >= 70) return 'Well-Defined';
    if (rr >= 50) return 'Emerging';
    return 'Exploratory';
  };

  return (
    <div className="rounded-2xl border border-violet-500/30 bg-gradient-to-br from-violet-950/40 to-slate-950/60 p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <span className="text-3xl">🧠</span>
          <div>
            <h2 className="text-xl font-semibold text-violet-200">Personality Overview</h2>
            <p className="text-xs text-slate-400">
              {snapshot.factors_assessed}/5 BigFive Factors Assessed
            </p>
          </div>
        </div>

        {/* Intent Badge */}
        <div className={`px-3 py-1.5 rounded-lg border text-xs font-medium ${INTENT_COLORS[snapshot.active_intent]}`}>
          {INTENT_LABELS[snapshot.active_intent]}
        </div>
      </div>

      {/* PsyDNA RR Score */}
      <div className="mb-6">
        <div className="flex items-baseline gap-2 mb-1">
          <span className="text-sm text-slate-300">PsyDNA Resolution:</span>
          <span className={`text-2xl font-bold ${getRRColor(snapshot.psydna_rr)}`}>
            {snapshot.psydna_rr.toFixed(1)}
          </span>
          <span className="text-xs text-slate-400">({getRRLabel(snapshot.psydna_rr)})</span>
        </div>

        {/* RR Progress Bar */}
        <div className="w-full h-2 bg-slate-800 rounded-full overflow-hidden">
          <div
            className={`h-full transition-all ${
              snapshot.psydna_rr >= 70 ? 'bg-green-500' :
              snapshot.psydna_rr >= 50 ? 'bg-yellow-500' :
              'bg-red-500'
            }`}
            style={{ width: `${snapshot.psydna_rr}%` }}
          />
        </div>
      </div>

      {/* Top Strengths & Curiosity Grid */}
      <div className="grid grid-cols-2 gap-4">
        {/* Top Strengths */}
        <div>
          <h4 className="text-xs font-semibold text-violet-300 mb-2 flex items-center gap-1">
            <span>✨</span> Top Strengths
          </h4>
          <div className="space-y-1">
            {snapshot.top_strengths.length > 0 ? (
              snapshot.top_strengths.map((strength, idx) => (
                <div
                  key={idx}
                  className="text-xs px-2 py-1 rounded bg-green-900/30 text-green-200 border border-green-600/30"
                >
                  {strength.replace('DNA', '')}
                </div>
              ))
            ) : (
              <p className="text-xs text-slate-500 italic">Complete assessment to identify strengths</p>
            )}
          </div>
        </div>

        {/* High Curiosity Areas */}
        <div>
          <h4 className="text-xs font-semibold text-violet-300 mb-2 flex items-center gap-1">
            <span>🔍</span> High Curiosity
          </h4>
          <div className="space-y-1">
            {snapshot.top_curiosity.length > 0 ? (
              snapshot.top_curiosity.map((curious, idx) => (
                <div
                  key={idx}
                  className="text-xs px-2 py-1 rounded bg-amber-900/30 text-amber-200 border border-amber-600/30"
                >
                  {curious.replace('DNA', '')}
                </div>
              ))
            ) : (
              <p className="text-xs text-slate-500 italic">No high-curiosity areas detected</p>
            )}
          </div>
        </div>
      </div>

      {/* CTA if low assessment */}
      {snapshot.factors_assessed < 3 && (
        <div className="mt-4 pt-4 border-t border-violet-500/20">
          <button className="w-full px-4 py-2 rounded-lg bg-violet-600/30 hover:bg-violet-600/50 text-violet-200 text-sm font-medium transition-colors border border-violet-500/30">
            Start Personality Assessment →
          </button>
        </div>
      )}
    </div>
  );
}
