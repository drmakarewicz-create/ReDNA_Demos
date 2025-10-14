'use client';

import { useEffect, useState } from 'react';

interface PersonalityFactor {
  name: string;
  rr: number;
  curiosity: number;
  population_avg: number;
}

interface PersonalityMapData {
  factors: PersonalityFactor[];
}

interface PersonalityMapVisualizationProps {
  userId: string;
}

/**
 * PersonalityMapVisualization - Radar chart of BigFive factors
 *
 * Displays:
 * - Pentagon/hexagon radar chart of 5 BigFive factors
 * - RR scores as primary data
 * - Curiosity scores as color intensity
 * - Optional population average comparison overlay
 * - Toggle for facet drill-down (future enhancement)
 *
 * Data source: /api/coach/personality_test_coach/panel → personality_map
 */
export function PersonalityMapVisualization({ userId }: PersonalityMapVisualizationProps) {
  const [mapData, setMapData] = useState<PersonalityMapData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showPopulationAvg, setShowPopulationAvg] = useState(false);

  useEffect(() => {
    async function fetchMapData() {
      try {
        const baseUrl = process.env.NEXT_PUBLIC_CORE_API_BASE || 'http://127.0.0.1:8000';
        const response = await fetch(
          `${baseUrl}/api/coach/personality_test_coach/panel?user_id=${encodeURIComponent(userId)}`
        );

        if (!response.ok) {
          throw new Error(`API error: ${response.status}`);
        }

        const data = await response.json();
        setMapData(data.personality_map);
        setLoading(false);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load personality map');
        setLoading(false);
      }
    }

    fetchMapData();
  }, [userId]);

  if (loading) {
    return (
      <div className="rounded-2xl border border-violet-500/30 bg-gradient-to-br from-violet-950/40 to-slate-950/60 p-6">
        <h3 className="text-lg font-semibold text-violet-200 mb-4">Personality Map</h3>
        <p className="text-sm text-slate-400">Loading personality factors...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-2xl border border-red-500/30 bg-gradient-to-br from-red-950/40 to-slate-950/60 p-6">
        <h3 className="text-lg font-semibold text-red-200 mb-4">Error Loading Map</h3>
        <p className="text-sm text-red-300">{error}</p>
      </div>
    );
  }

  if (!mapData || mapData.factors.length === 0) {
    return (
      <div className="rounded-2xl border border-violet-500/30 bg-gradient-to-br from-violet-950/40 to-slate-950/60 p-6">
        <h3 className="text-lg font-semibold text-violet-200 mb-4">Personality Map</h3>
        <p className="text-sm text-slate-400">
          No personality data yet. Complete the assessment to see your BigFive profile.
        </p>
      </div>
    );
  }

  // Generate simple bar chart for now (radar chart would require D3 or Recharts)
  const getBarColor = (rr: number, curiosity: number): string => {
    if (rr >= 70) return `bg-green-500`;
    if (rr >= 50) return `bg-yellow-500`;
    return `bg-red-500`;
  };

  const getCuriosityLabel = (curiosity: number): string => {
    if (curiosity >= 80) return '🔥';
    if (curiosity >= 60) return '⚡';
    return '💤';
  };

  return (
    <div className="rounded-2xl border border-violet-500/30 bg-gradient-to-br from-violet-950/40 to-slate-950/60 p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <span className="text-2xl">🎭</span>
          <h3 className="text-lg font-semibold text-violet-200">Personality Map</h3>
        </div>

        {/* Toggle Population Average */}
        <button
          onClick={() => setShowPopulationAvg(!showPopulationAvg)}
          className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
            showPopulationAvg
              ? 'bg-violet-600/50 text-violet-200 border border-violet-500/50'
              : 'bg-slate-800/50 text-slate-400 border border-slate-700/50'
          }`}
        >
          Compare to Avg
        </button>
      </div>

      {/* BigFive Factors */}
      <div className="space-y-4">
        {mapData.factors.map((factor) => (
          <div key={factor.name} className="space-y-2">
            {/* Factor Name & Scores */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-violet-200">{factor.name}</span>
                <span className="text-xs">{getCuriosityLabel(factor.curiosity)}</span>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-xs text-slate-400">
                  RR: <span className="text-violet-300 font-medium">{factor.rr.toFixed(0)}</span>
                </span>
                {showPopulationAvg && (
                  <span className="text-xs text-slate-500">
                    Avg: {factor.population_avg}
                  </span>
                )}
              </div>
            </div>

            {/* Progress Bar */}
            <div className="relative h-3 bg-slate-800 rounded-full overflow-hidden">
              {/* User's RR */}
              <div
                className={`absolute h-full ${getBarColor(factor.rr, factor.curiosity)} opacity-80`}
                style={{ width: `${Math.min(factor.rr, 100)}%` }}
              />

              {/* Population Average Line (if enabled) */}
              {showPopulationAvg && (
                <div
                  className="absolute h-full w-0.5 bg-slate-300"
                  style={{ left: `${factor.population_avg}%` }}
                  title={`Population avg: ${factor.population_avg}`}
                />
              )}
            </div>

            {/* Curiosity Indicator */}
            <div className="flex justify-end">
              <span className="text-[10px] text-slate-500">
                Curiosity: {factor.curiosity.toFixed(0)}
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Legend */}
      <div className="mt-6 pt-4 border-t border-violet-500/20 flex items-center justify-between text-xs text-slate-400">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 rounded bg-green-500" />
            <span>Well-Defined</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 rounded bg-yellow-500" />
            <span>Emerging</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 rounded bg-red-500" />
            <span>Exploratory</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span>🔥 High Curiosity</span>
          <span>⚡ Moderate</span>
          <span>💤 Low</span>
        </div>
      </div>

      {/* Future Enhancement Notice */}
      <div className="mt-4 text-xs text-slate-500 text-center">
        Tap factor name to explore facets (coming soon)
      </div>
    </div>
  );
}
