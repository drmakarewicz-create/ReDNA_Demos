'use client';

import { useEffect, useState } from 'react';

interface LanguageTraitEntry {
  trait_name: string;
  rr: number;
  curiosity: number;
  sample_count: number;
}

interface LanguageStylePanelProps {
  userId: string;
  minCuriosity?: number;
}

export function LanguageStylePanel({ userId, minCuriosity = 50 }: LanguageStylePanelProps) {
  const [traits, setTraits] = useState<LanguageTraitEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchTraits() {
      try {
        const baseUrl = process.env.NEXT_PUBLIC_CORE_API_BASE || 'http://127.0.0.1:8000';
        const response = await fetch(
          `${baseUrl}/api/coach/chatdna_coach/traits?user_id=${encodeURIComponent(userId)}&min_curiosity=${minCuriosity}`
        );

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();

        if (!cancelled) {
          setTraits(data.traits || []);
          setLoading(false);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load language traits');
          setLoading(false);
        }
      }
    }

    fetchTraits();

    return () => {
      cancelled = true;
    };
  }, [userId, minCuriosity]);

  if (loading) {
    return (
      <div className="rounded-2xl border border-purple-500/30 bg-gradient-to-br from-purple-950/40 to-slate-950/60 p-6 animate-pulse">
        <div className="h-6 w-40 bg-purple-500/20 rounded mb-4"></div>
        <div className="space-y-3">
          <div className="h-16 bg-purple-500/10 rounded"></div>
          <div className="h-16 bg-purple-500/10 rounded"></div>
          <div className="h-16 bg-purple-500/10 rounded"></div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-2xl border border-red-500/30 bg-gradient-to-br from-red-950/40 to-slate-950/60 p-6">
        <div className="flex items-center gap-3 mb-2">
          <span className="text-2xl">⚠️</span>
          <h3 className="text-lg font-semibold text-red-200">Language Traits Unavailable</h3>
        </div>
        <p className="text-sm text-slate-400">{error}</p>
      </div>
    );
  }

  if (traits.length === 0) {
    return (
      <div className="rounded-2xl border border-purple-500/30 bg-gradient-to-br from-purple-950/40 to-slate-950/60 p-6">
        <div className="flex items-center gap-3 mb-3">
          <span className="text-3xl">🎯</span>
          <h3 className="text-xl font-semibold text-purple-200">Language Style Traits</h3>
        </div>
        <div className="rounded-lg bg-slate-950/60 p-4 border border-slate-700/50">
          <p className="text-sm text-slate-400 text-center">
            No high-curiosity language traits yet. Chat more to build your style profile!
          </p>
        </div>
      </div>
    );
  }

  // Get curiosity color
  const getCuriosityColor = (curiosity: number) => {
    if (curiosity >= 80) return 'bg-orange-500';
    if (curiosity >= 60) return 'bg-yellow-500';
    return 'bg-blue-500';
  };

  const getCuriosityTextColor = (curiosity: number) => {
    if (curiosity >= 80) return 'text-orange-300';
    if (curiosity >= 60) return 'text-yellow-300';
    return 'text-blue-300';
  };

  return (
    <div className="rounded-2xl border border-purple-500/30 bg-gradient-to-br from-purple-950/40 to-slate-950/60 p-6">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <span className="text-3xl">🎯</span>
        <h3 className="text-xl font-semibold text-purple-200">Language Style Traits</h3>
      </div>

      {/* Traits List */}
      <div className="space-y-3">
        {traits.map((trait, idx) => (
          <div
            key={idx}
            className="rounded-lg bg-slate-950/60 p-4 border border-slate-700/50 hover:border-purple-500/50 transition-colors"
          >
            <div className="flex items-start justify-between mb-3">
              <div className="flex-1">
                <h4 className="text-sm font-semibold text-slate-200 mb-1">{trait.trait_name}</h4>
                <div className="flex items-center gap-3 text-xs text-slate-400">
                  <span>RR: <span className="text-purple-300 font-medium">{trait.rr}</span></span>
                  <span>•</span>
                  <span>Samples: <span className="text-slate-300">{trait.sample_count}</span></span>
                </div>
              </div>
              <div className={`rounded-full px-3 py-1 text-xs font-medium ${getCuriosityColor(trait.curiosity)}/10 border border-${getCuriosityColor(trait.curiosity)}/30 ${getCuriosityTextColor(trait.curiosity)}`}>
                {trait.curiosity}% curious
              </div>
            </div>

            {/* Curiosity Bar */}
            <div className="w-full bg-slate-800/50 rounded-full h-2 overflow-hidden">
              <div
                className={`h-full ${getCuriosityColor(trait.curiosity)} transition-all duration-500 ease-out`}
                style={{ width: `${trait.curiosity}%` }}
              />
            </div>
          </div>
        ))}
      </div>

      {/* Footer */}
      <div className="mt-4 pt-4 border-t border-slate-700/50">
        <p className="text-xs text-slate-500 text-center">
          Showing traits with curiosity ≥ {minCuriosity}%
        </p>
      </div>
    </div>
  );
}
