'use client';

import { useState, useEffect, useRef } from 'react';
import { CORE_API_BASE } from '../../lib/api';

interface TraitSnapshot {
  ts: string;
  trait_id: string;
  value: any;
  rr: number;
  ucn: number;
}

interface TraitTimelineData {
  trait_id: string;
  snapshots: TraitSnapshot[];
}

interface TraitTimelineProps {
  userId: string;
  traitId?: string;
  autoPlay?: boolean;
}

export function TraitTimeline({
  userId,
  traitId = 'Conscientiousness',
  autoPlay = false,
}: TraitTimelineProps) {
  const [data, setData] = useState<TraitTimelineData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [playing, setPlaying] = useState(autoPlay);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  const fetchTraitTimeline = async () => {
    try {
      const response = await fetch(
        `${CORE_API_BASE}/ui/trait_timeline?user_id=${userId}&trait_id=${traitId}`
      );
      const json = await response.json();

      if (json.ok && json.timeline) {
        setData({
          trait_id: traitId,
          snapshots: json.timeline,
        });
        setError(null);
      } else {
        setError(json.detail || 'Failed to load trait timeline');
      }
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTraitTimeline();
  }, [userId, traitId]);

  useEffect(() => {
    if (playing && data && data.snapshots.length > 0) {
      intervalRef.current = setInterval(() => {
        setCurrentIndex((prev) => {
          if (prev >= data.snapshots.length - 1) {
            setPlaying(false);
            return prev;
          }
          return prev + 1;
        });
      }, 1000);
    } else if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [playing, data]);

  const handleScrub = (index: number) => {
    setCurrentIndex(index);
    setPlaying(false);
  };

  const togglePlayPause = () => {
    if (currentIndex >= (data?.snapshots.length || 0) - 1) {
      setCurrentIndex(0);
    }
    setPlaying(!playing);
  };

  const resetTimeline = () => {
    setCurrentIndex(0);
    setPlaying(false);
  };

  if (loading) {
    return (
      <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6">
        <h2 className="mb-4 text-lg font-semibold text-slate-200">
          Time-Lapse Self Portrait
        </h2>
        <div className="flex h-96 items-center justify-center">
          <div className="text-slate-500">Loading timeline...</div>
        </div>
      </div>
    );
  }

  if (error || !data || data.snapshots.length === 0) {
    return (
      <div className="rounded-2xl border border-red-800/30 bg-red-950/20 p-6">
        <h2 className="mb-4 text-lg font-semibold text-red-400">
          Time-Lapse Self Portrait
        </h2>
        <div className="text-red-300">
          {error || 'No timeline data available for this trait'}
        </div>
      </div>
    );
  }

  const currentSnapshot = data.snapshots[currentIndex];
  const maxRR = Math.max(...data.snapshots.map((s) => s.rr));
  const maxUCN = Math.max(...data.snapshots.map((s) => s.ucn));

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-200">
          Time-Lapse Self Portrait
        </h2>
        <div className="text-xs text-slate-500">
          Trait: <span className="font-semibold text-slate-300">{data.trait_id}</span>
        </div>
      </div>

      {/* Current Snapshot Display */}
      <div className="mb-6 rounded-lg border border-slate-700 bg-slate-950/50 p-6">
        <div className="mb-4 grid grid-cols-3 gap-4 text-center">
          <div>
            <div className="mb-1 text-xs text-slate-400">Value</div>
            <div className="text-2xl font-bold text-blue-400">
              {typeof currentSnapshot.value === 'number'
                ? currentSnapshot.value.toFixed(2)
                : currentSnapshot.value}
            </div>
          </div>
          <div>
            <div className="mb-1 text-xs text-slate-400">RR (Resolve Ratio)</div>
            <div className="text-2xl font-bold text-green-400">
              {currentSnapshot.rr.toFixed(0)}
            </div>
          </div>
          <div>
            <div className="mb-1 text-xs text-slate-400">UCN (Uncertainty)</div>
            <div className="text-2xl font-bold text-yellow-400">
              {currentSnapshot.ucn.toFixed(0)}
            </div>
          </div>
        </div>

        <div className="text-center text-xs text-slate-500">
          {new Date(currentSnapshot.ts).toLocaleString()}
        </div>
      </div>

      {/* Chart Visualization */}
      <div className="mb-6 rounded-lg border border-slate-700 bg-slate-950/50 p-4">
        <div className="mb-3 text-sm font-medium text-slate-400">Trait Evolution</div>
        <svg viewBox="0 0 600 200" className="w-full">
          {/* Grid lines */}
          {[0, 25, 50, 75, 100].map((y) => (
            <line
              key={`grid-${y}`}
              x1="40"
              y1={180 - y * 1.6}
              x2="580"
              y2={180 - y * 1.6}
              stroke="rgba(148, 163, 184, 0.1)"
              strokeWidth="1"
            />
          ))}

          {/* RR Line */}
          <polyline
            points={data.snapshots
              .map((s, idx) => {
                const x = 40 + (idx / (data.snapshots.length - 1)) * 540;
                const y = 180 - (s.rr / maxRR) * 160;
                return `${x},${y}`;
              })
              .join(' ')}
            fill="none"
            stroke="rgb(34, 197, 94)"
            strokeWidth="2"
          />

          {/* UCN Line */}
          <polyline
            points={data.snapshots
              .map((s, idx) => {
                const x = 40 + (idx / (data.snapshots.length - 1)) * 540;
                const y = 180 - (s.ucn / maxUCN) * 160;
                return `${x},${y}`;
              })
              .join(' ')}
            fill="none"
            stroke="rgb(251, 191, 36)"
            strokeWidth="2"
            strokeDasharray="5,5"
          />

          {/* Current position marker */}
          {data.snapshots.length > 0 && (
            <>
              <line
                x1={40 + (currentIndex / (data.snapshots.length - 1)) * 540}
                y1="20"
                x2={40 + (currentIndex / (data.snapshots.length - 1)) * 540}
                y2="180"
                stroke="rgb(59, 130, 246)"
                strokeWidth="2"
                opacity="0.5"
              />
              <circle
                cx={40 + (currentIndex / (data.snapshots.length - 1)) * 540}
                cy={180 - (currentSnapshot.rr / maxRR) * 160}
                r="5"
                fill="rgb(34, 197, 94)"
              />
              <circle
                cx={40 + (currentIndex / (data.snapshots.length - 1)) * 540}
                cy={180 - (currentSnapshot.ucn / maxUCN) * 160}
                r="5"
                fill="rgb(251, 191, 36)"
              />
            </>
          )}

          {/* Legend */}
          <g transform="translate(480, 10)">
            <line x1="0" y1="0" x2="20" y2="0" stroke="rgb(34, 197, 94)" strokeWidth="2" />
            <text x="25" y="5" fill="rgb(226, 232, 240)" fontSize="11">
              RR
            </text>
            <line
              x1="0"
              y1="15"
              x2="20"
              y2="15"
              stroke="rgb(251, 191, 36)"
              strokeWidth="2"
              strokeDasharray="5,5"
            />
            <text x="25" y="20" fill="rgb(226, 232, 240)" fontSize="11">
              UCN
            </text>
          </g>
        </svg>
      </div>

      {/* Playback Controls */}
      <div className="space-y-3">
        {/* Scrubber */}
        <div className="flex items-center gap-3">
          <input
            type="range"
            min="0"
            max={data.snapshots.length - 1}
            value={currentIndex}
            onChange={(e) => handleScrub(parseInt(e.target.value))}
            className="flex-1"
            style={{
              accentColor: 'rgb(59, 130, 246)',
            }}
          />
          <div className="w-16 text-right text-xs text-slate-400">
            {currentIndex + 1} / {data.snapshots.length}
          </div>
        </div>

        {/* Control Buttons */}
        <div className="flex items-center justify-center gap-2">
          <button
            onClick={resetTimeline}
            className="rounded-lg bg-slate-800 px-4 py-2 text-sm font-medium text-slate-300 hover:bg-slate-700"
          >
            ⏮ Reset
          </button>
          <button
            onClick={togglePlayPause}
            className="rounded-lg bg-blue-900/50 px-6 py-2 text-sm font-medium text-blue-300 hover:bg-blue-800/50"
          >
            {playing ? '⏸ Pause' : '▶ Play'}
          </button>
          <button
            onClick={() => handleScrub(Math.min(currentIndex + 1, data.snapshots.length - 1))}
            className="rounded-lg bg-slate-800 px-4 py-2 text-sm font-medium text-slate-300 hover:bg-slate-700"
            disabled={currentIndex >= data.snapshots.length - 1}
          >
            ⏭ Next
          </button>
        </div>
      </div>

      {/* Progress Indicator */}
      <div className="mt-4 h-1 overflow-hidden rounded-full bg-slate-800">
        <div
          className="h-full bg-blue-500 transition-all duration-300"
          style={{
            width: `${((currentIndex + 1) / data.snapshots.length) * 100}%`,
          }}
        />
      </div>
    </div>
  );
}
