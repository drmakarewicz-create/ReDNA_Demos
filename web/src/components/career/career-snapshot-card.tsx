'use client';

import { useEffect, useState } from 'react';

interface CareerSnapshot {
  profdna_rr: number;
  skilldna_rr: number;
  top_strengths: string[];
  top_curiosity: string[];
  active_intent: string;
}

interface CareerSnapshotCardProps {
  userId: string;
}

const INTENT_LABELS: Record<string, string> = {
  current_role_growth: 'Growing in Current Role',
  career_change: 'Exploring Career Change',
  organization_mode: 'Organizing & Planning'
};

const INTENT_ICONS: Record<string, string> = {
  current_role_growth: '📈',
  career_change: '🔄',
  organization_mode: '📋'
};

export function CareerSnapshotCard({ userId }: CareerSnapshotCardProps) {
  const [snapshot, setSnapshot] = useState<CareerSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchSnapshot() {
      try {
        const baseUrl = process.env.NEXT_PUBLIC_CORE_API_BASE || 'http://127.0.0.1:8000';
        const response = await fetch(`${baseUrl}/api/coach/career_coach/panel?user_id=${encodeURIComponent(userId)}`);

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();

        if (!cancelled) {
          setSnapshot(data.snapshot);
          setLoading(false);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load career snapshot');
          setLoading(false);
        }
      }
    }

    fetchSnapshot();

    return () => {
      cancelled = true;
    };
  }, [userId]);

  if (loading) {
    return (
      <div className="rounded-2xl border border-blue-500/30 bg-gradient-to-br from-blue-950/40 to-slate-950/60 p-6 animate-pulse">
        <div className="h-6 w-32 bg-blue-500/20 rounded mb-4"></div>
        <div className="space-y-3">
          <div className="h-4 w-full bg-blue-500/10 rounded"></div>
          <div className="h-4 w-5/6 bg-blue-500/10 rounded"></div>
        </div>
      </div>
    );
  }

  if (error || !snapshot) {
    return (
      <div className="rounded-2xl border border-red-500/30 bg-gradient-to-br from-red-950/40 to-slate-950/60 p-6">
        <div className="flex items-center gap-3 mb-2">
          <span className="text-2xl">⚠️</span>
          <h3 className="text-lg font-semibold text-red-200">Career Snapshot Unavailable</h3>
        </div>
        <p className="text-sm text-slate-400">{error || 'No data available'}</p>
      </div>
    );
  }

  const intentIcon = INTENT_ICONS[snapshot.active_intent] || '📊';
  const intentLabel = INTENT_LABELS[snapshot.active_intent] || snapshot.active_intent;

  // Color coding for RR scores
  const getRRColor = (rr: number) => {
    if (rr >= 70) return 'text-green-400';
    if (rr >= 50) return 'text-yellow-400';
    return 'text-orange-400';
  };

  return (
    <div className="rounded-2xl border border-blue-500/30 bg-gradient-to-br from-blue-950/40 to-slate-950/60 p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <span className="text-3xl">💼</span>
          <h3 className="text-xl font-semibold text-blue-200">Career Overview</h3>
        </div>
        <div className="flex items-center gap-2 rounded-full bg-blue-500/10 px-3 py-1 border border-blue-500/20">
          <span className="text-lg">{intentIcon}</span>
          <span className="text-xs font-medium text-blue-300">{intentLabel}</span>
        </div>
      </div>

      {/* RR Metrics */}
      <div className="grid grid-cols-2 gap-4 mb-6">
        <div className="rounded-lg bg-slate-950/60 p-4 border border-slate-700/50">
          <p className="text-xs text-slate-400 uppercase tracking-wide mb-1">Professional DNA</p>
          <p className={`text-2xl font-bold ${getRRColor(snapshot.profdna_rr)}`}>
            {snapshot.profdna_rr}
            <span className="text-sm text-slate-500 ml-1">RR</span>
          </p>
        </div>
        <div className="rounded-lg bg-slate-950/60 p-4 border border-slate-700/50">
          <p className="text-xs text-slate-400 uppercase tracking-wide mb-1">Skill DNA</p>
          <p className={`text-2xl font-bold ${getRRColor(snapshot.skilldna_rr)}`}>
            {snapshot.skilldna_rr}
            <span className="text-sm text-slate-500 ml-1">RR</span>
          </p>
        </div>
      </div>

      {/* Top Strengths */}
      {snapshot.top_strengths.length > 0 && (
        <div className="mb-4">
          <p className="text-xs text-slate-400 uppercase tracking-wide mb-2">Top Strengths</p>
          <div className="flex flex-wrap gap-2">
            {snapshot.top_strengths.map((strength, idx) => (
              <span
                key={idx}
                className="rounded-full bg-green-500/10 border border-green-500/30 px-3 py-1 text-xs text-green-300"
              >
                {strength}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* High Curiosity Areas */}
      {snapshot.top_curiosity.length > 0 && (
        <div>
          <p className="text-xs text-slate-400 uppercase tracking-wide mb-2">High Curiosity</p>
          <div className="flex flex-wrap gap-2">
            {snapshot.top_curiosity.map((area, idx) => (
              <span
                key={idx}
                className="rounded-full bg-orange-500/10 border border-orange-500/30 px-3 py-1 text-xs text-orange-300"
              >
                {area}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
