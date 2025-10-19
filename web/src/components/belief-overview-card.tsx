'use client';

import { useEffect, useState } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_CORE_API_BASE ?? 'http://127.0.0.1:8000';

interface BeliefSnapshot {
  belief_rr: number;
  cog_rr: number;
  motivation_rr: number;
  top_curiosity: Array<{ trait: string; curiosity: number }>;
  dominant_moral_foundations: string[];
  active_intent: string;
}

interface BeliefOverviewCardProps {
  userId: string;
}

export function BeliefOverviewCard({ userId }: BeliefOverviewCardProps) {
  const [snapshot, setSnapshot] = useState<BeliefSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchSnapshot();
  }, [userId]);

  const fetchSnapshot = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${API_BASE}/api/coach/beliefdna_coach/panel?user_id=${userId}`);

      if (!response.ok) {
        throw new Error('Failed to fetch belief snapshot');
      }

      const data = await response.json();
      setSnapshot(data.snapshot);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="rounded-xl border border-purple-500/30 bg-gradient-to-br from-purple-950/40 to-slate-950/60 p-6">
        <div className="flex items-center gap-3 mb-4">
          <span className="text-2xl">🤔</span>
          <h3 className="text-lg font-semibold text-purple-200">Belief Profile</h3>
        </div>
        <p className="text-sm text-slate-400">Loading...</p>
      </div>
    );
  }

  if (error || !snapshot) {
    return (
      <div className="rounded-xl border border-red-500/30 bg-gradient-to-br from-red-950/40 to-slate-950/60 p-6">
        <p className="text-sm text-red-400">Error: {error || 'No data available'}</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-purple-500/30 bg-gradient-to-br from-purple-950/40 to-slate-950/60 p-6">
      <div className="flex items-center gap-3 mb-4">
        <span className="text-2xl">🤔</span>
        <h3 className="text-lg font-semibold text-purple-200">Belief Profile</h3>
      </div>

      {/* RR Scores */}
      <div className="grid grid-cols-3 gap-4 mb-4">
        <div className="text-center">
          <div className="text-2xl font-bold text-purple-300">{snapshot.belief_rr}</div>
          <div className="text-xs text-slate-400 mt-1">Belief RR</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-blue-300">{snapshot.cog_rr}</div>
          <div className="text-xs text-slate-400 mt-1">Cognitive RR</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-green-300">{snapshot.motivation_rr}</div>
          <div className="text-xs text-slate-400 mt-1">Motivation RR</div>
        </div>
      </div>

      {/* Dominant Moral Foundations */}
      {snapshot.dominant_moral_foundations.length > 0 && (
        <div className="mb-4">
          <div className="text-xs font-medium text-purple-300 mb-2">Moral Foundations</div>
          <div className="flex flex-wrap gap-2">
            {snapshot.dominant_moral_foundations.map((foundation) => (
              <span
                key={foundation}
                className="px-2 py-1 rounded-md bg-purple-500/20 text-purple-200 text-xs border border-purple-500/30"
              >
                {foundation}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Top Curiosity Areas */}
      {snapshot.top_curiosity.length > 0 && (
        <div>
          <div className="text-xs font-medium text-purple-300 mb-2">High Curiosity Areas</div>
          <div className="space-y-2">
            {snapshot.top_curiosity.slice(0, 3).map((item) => (
              <div key={item.trait} className="flex items-center justify-between">
                <span className="text-xs text-slate-300 truncate flex-1">{item.trait}</span>
                <span className="text-xs font-medium text-purple-400 ml-2">{item.curiosity}%</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Active Intent */}
      <div className="mt-4 pt-4 border-t border-purple-500/20">
        <div className="text-xs text-slate-400">
          Current mode: <span className="text-purple-300 font-medium">{snapshot.active_intent}</span>
        </div>
      </div>
    </div>
  );
}
