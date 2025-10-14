'use client';

import { useEffect, useState } from 'react';

interface ChatDNASnapshot {
  languagestyle_rr: number;
  interaction_rr: number;
  top_traits: string[];
  writing_samples: number;
  active_mode: string;
}

interface ChatDNASnapshotCardProps {
  userId: string;
}

const MODE_LABELS: Record<string, string> = {
  casual: 'Casual Conversation',
  professional: 'Professional Writing',
  creative: 'Creative Expression',
  analysis: 'Analysis & Insight'
};

const MODE_ICONS: Record<string, string> = {
  casual: '💬',
  professional: '📝',
  creative: '✨',
  analysis: '🔍'
};

export function ChatDNASnapshotCard({ userId }: ChatDNASnapshotCardProps) {
  const [snapshot, setSnapshot] = useState<ChatDNASnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchSnapshot() {
      try {
        const baseUrl = process.env.NEXT_PUBLIC_CORE_API_BASE || 'http://127.0.0.1:8000';
        const response = await fetch(`${baseUrl}/api/coach/chatdna_coach/panel?user_id=${encodeURIComponent(userId)}`);

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
          setError(err instanceof Error ? err.message : 'Failed to load ChatDNA snapshot');
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
      <div className="rounded-2xl border border-purple-500/30 bg-gradient-to-br from-purple-950/40 to-slate-950/60 p-6 animate-pulse">
        <div className="h-6 w-32 bg-purple-500/20 rounded mb-4"></div>
        <div className="space-y-3">
          <div className="h-4 w-full bg-purple-500/10 rounded"></div>
          <div className="h-4 w-5/6 bg-purple-500/10 rounded"></div>
        </div>
      </div>
    );
  }

  if (error || !snapshot) {
    return (
      <div className="rounded-2xl border border-red-500/30 bg-gradient-to-br from-red-950/40 to-slate-950/60 p-6">
        <div className="flex items-center gap-3 mb-2">
          <span className="text-2xl">⚠️</span>
          <h3 className="text-lg font-semibold text-red-200">ChatDNA Snapshot Unavailable</h3>
        </div>
        <p className="text-sm text-slate-400">{error || 'No data available'}</p>
      </div>
    );
  }

  const modeIcon = MODE_ICONS[snapshot.active_mode] || '💬';
  const modeLabel = MODE_LABELS[snapshot.active_mode] || snapshot.active_mode;

  // Color coding for RR scores
  const getRRColor = (rr: number) => {
    if (rr >= 70) return 'text-green-400';
    if (rr >= 50) return 'text-yellow-400';
    return 'text-orange-400';
  };

  return (
    <div className="rounded-2xl border border-purple-500/30 bg-gradient-to-br from-purple-950/40 to-slate-950/60 p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <span className="text-3xl">🎯</span>
          <h3 className="text-xl font-semibold text-purple-200">ChatDNA Profile</h3>
        </div>
        <div className="flex items-center gap-2 rounded-full bg-purple-500/10 px-3 py-1 border border-purple-500/20">
          <span className="text-lg">{modeIcon}</span>
          <span className="text-xs font-medium text-purple-300">{modeLabel}</span>
        </div>
      </div>

      {/* RR Metrics */}
      <div className="grid grid-cols-2 gap-4 mb-6">
        <div className="rounded-lg bg-slate-950/60 p-4 border border-slate-700/50">
          <p className="text-xs text-slate-400 uppercase tracking-wide mb-1">Language Style</p>
          <p className={`text-2xl font-bold ${getRRColor(snapshot.languagestyle_rr)}`}>
            {snapshot.languagestyle_rr}
            <span className="text-sm text-slate-500 ml-1">RR</span>
          </p>
        </div>
        <div className="rounded-lg bg-slate-950/60 p-4 border border-slate-700/50">
          <p className="text-xs text-slate-400 uppercase tracking-wide mb-1">Interaction Style</p>
          <p className={`text-2xl font-bold ${getRRColor(snapshot.interaction_rr)}`}>
            {snapshot.interaction_rr}
            <span className="text-sm text-slate-500 ml-1">RR</span>
          </p>
        </div>
      </div>

      {/* Top Traits */}
      {snapshot.top_traits.length > 0 && (
        <div className="mb-4">
          <p className="text-xs text-slate-400 uppercase tracking-wide mb-2">Speaking Style Traits</p>
          <div className="flex flex-wrap gap-2">
            {snapshot.top_traits.map((trait, idx) => (
              <span
                key={idx}
                className="rounded-full bg-purple-500/10 border border-purple-500/30 px-3 py-1 text-xs text-purple-300"
              >
                {trait}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Writing Samples Counter */}
      <div className="rounded-lg bg-slate-950/60 p-3 border border-slate-700/50">
        <div className="flex items-center justify-between">
          <span className="text-xs text-slate-400 uppercase tracking-wide">Writing Samples</span>
          <span className="text-lg font-semibold text-purple-300">{snapshot.writing_samples}</span>
        </div>
      </div>
    </div>
  );
}
