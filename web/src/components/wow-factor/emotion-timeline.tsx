'use client';

import { useState, useEffect } from 'react';
import { CORE_API_BASE } from '../../lib/api';

interface EmotionEntry {
  ts: string;
  turn_id: string;
  emotion: string;
  sentiment: string;
  intensity: number;
}

interface EmotionTimelineProps {
  userId: string;
  limit?: number;
  autoRefresh?: boolean;
  refreshInterval?: number;
}

const EMOTION_COLORS: Record<string, string> = {
  joy: 'rgb(34, 197, 94)', // green
  calm: 'rgb(59, 130, 246)', // blue
  concern: 'rgb(251, 191, 36)', // yellow
  neutral: 'rgb(148, 163, 184)', // slate
};

const EMOTION_EMOJIS: Record<string, string> = {
  joy: '😊',
  calm: '😌',
  concern: '😟',
  neutral: '😐',
};

export function EmotionTimeline({
  userId,
  limit = 50,
  autoRefresh = false,
  refreshInterval = 10000,
}: EmotionTimelineProps) {
  const [timeline, setTimeline] = useState<EmotionEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchEmotionTimeline = async () => {
    try {
      const response = await fetch(
        `${CORE_API_BASE}/ui/hc/emotion_timeline/${userId}?limit=${limit}`
      );
      const json = await response.json();

      if (json.ok && json.timeline) {
        setTimeline(json.timeline);
        setError(null);
      } else {
        setError(json.detail || 'Failed to load emotion timeline');
      }
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEmotionTimeline();

    if (autoRefresh) {
      const interval = setInterval(fetchEmotionTimeline, refreshInterval);
      return () => clearInterval(interval);
    }
  }, [userId, limit, autoRefresh, refreshInterval]);

  if (loading) {
    return (
      <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6">
        <h2 className="mb-4 text-lg font-semibold text-slate-200">
          Emotion Timeline
        </h2>
        <div className="flex h-64 items-center justify-center">
          <div className="text-slate-500">Loading emotion data...</div>
        </div>
      </div>
    );
  }

  if (error || timeline.length === 0) {
    return (
      <div className="rounded-2xl border border-red-800/30 bg-red-950/20 p-6">
        <h2 className="mb-4 text-lg font-semibold text-red-400">
          Emotion Timeline
        </h2>
        <div className="text-red-300">
          {error || 'No emotion data available'}
        </div>
      </div>
    );
  }

  // Aggregate emotion counts
  const emotionCounts = timeline.reduce((acc, entry) => {
    acc[entry.emotion] = (acc[entry.emotion] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  const totalEntries = timeline.length;

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6">
      <h2 className="mb-4 text-lg font-semibold text-slate-200">
        Emotion Timeline
      </h2>

      {/* Emotion Distribution */}
      <div className="mb-6 rounded-lg border border-slate-700 bg-slate-950/50 p-4">
        <h3 className="mb-3 text-sm font-semibold text-slate-400">
          Emotion Distribution
        </h3>
        <div className="space-y-2">
          {Object.entries(emotionCounts)
            .sort(([, a], [, b]) => b - a)
            .map(([emotion, count]) => {
              const percentage = (count / totalEntries) * 100;
              const color = EMOTION_COLORS[emotion] || EMOTION_COLORS.neutral;

              return (
                <div key={emotion} className="flex items-center gap-3">
                  <div className="flex w-16 items-center gap-1.5">
                    <span className="text-base">{EMOTION_EMOJIS[emotion]}</span>
                    <span className="text-xs capitalize text-slate-400">
                      {emotion}
                    </span>
                  </div>
                  <div className="flex-1">
                    <div className="h-6 overflow-hidden rounded-full bg-slate-800">
                      <div
                        className="h-full transition-all duration-500"
                        style={{
                          width: `${percentage}%`,
                          backgroundColor: color,
                        }}
                      />
                    </div>
                  </div>
                  <div className="w-16 text-right text-xs text-slate-400">
                    {percentage.toFixed(1)}%
                  </div>
                </div>
              );
            })}
        </div>
      </div>

      {/* Waveform Visualization */}
      <div className="mb-6 rounded-lg border border-slate-700 bg-slate-950/50 p-4">
        <h3 className="mb-3 text-sm font-semibold text-slate-400">
          Emotion Waveform
        </h3>
        <svg viewBox="0 0 600 150" className="w-full">
          {/* Baseline */}
          <line
            x1="20"
            y1="75"
            x2="580"
            y2="75"
            stroke="rgba(148, 163, 184, 0.2)"
            strokeWidth="1"
            strokeDasharray="5,5"
          />

          {/* Waveform */}
          {timeline.slice(-50).map((entry, idx, arr) => {
            const x = 20 + (idx / (arr.length - 1)) * 560;
            const y = 75 - entry.intensity * 50 * (entry.emotion === 'joy' ? 1 : -1);
            const color = EMOTION_COLORS[entry.emotion] || EMOTION_COLORS.neutral;

            return (
              <g key={entry.turn_id}>
                {/* Connect to previous point */}
                {idx > 0 && (
                  <line
                    x1={20 + ((idx - 1) / (arr.length - 1)) * 560}
                    y1={
                      75 -
                      arr[idx - 1].intensity *
                        50 *
                        (arr[idx - 1].emotion === 'joy' ? 1 : -1)
                    }
                    x2={x}
                    y2={y}
                    stroke={color}
                    strokeWidth="2"
                    opacity="0.6"
                  />
                )}

                {/* Data point */}
                <circle
                  cx={x}
                  cy={y}
                  r="3"
                  fill={color}
                  opacity="0.8"
                >
                  <title>
                    {new Date(entry.ts).toLocaleString()} - {entry.emotion}
                  </title>
                </circle>
              </g>
            );
          })}

          {/* Legend */}
          <g transform="translate(20, 140)">
            <text x="0" y="0" fill="rgb(226, 232, 240)" fontSize="10">
              Positive emotions above baseline, concerns below
            </text>
          </g>
        </svg>
      </div>

      {/* Recent Emotions */}
      <div className="rounded-lg border border-slate-700 bg-slate-950/50 p-4">
        <h3 className="mb-3 text-sm font-semibold text-slate-400">
          Recent Emotions
        </h3>
        <div className="space-y-2 max-h-48 overflow-y-auto">
          {timeline.slice(-20).reverse().map((entry) => {
            const timestamp = new Date(entry.ts);

            return (
              <div
                key={entry.turn_id}
                className="flex items-center gap-3 rounded-lg bg-slate-800/30 p-2 text-xs"
              >
                <div className="text-base">{EMOTION_EMOJIS[entry.emotion]}</div>
                <div className="flex-1">
                  <div className="font-medium capitalize text-slate-300">
                    {entry.emotion}
                  </div>
                  <div className="text-slate-500">
                    {timestamp.toLocaleString()}
                  </div>
                </div>
                <div className="text-slate-400">
                  Intensity: {Math.round(entry.intensity * 100)}%
                </div>
                <div
                  className="rounded px-2 py-0.5 text-xs font-medium"
                  style={{
                    backgroundColor: `${EMOTION_COLORS[entry.emotion]}20`,
                    color: EMOTION_COLORS[entry.emotion],
                  }}
                >
                  {entry.sentiment}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Footer Stats */}
      <div className="mt-4 flex items-center justify-between text-xs text-slate-400">
        <div>
          Total Entries: <span className="font-semibold text-slate-300">{totalEntries}</span>
        </div>
        <div>
          Showing: <span className="font-semibold text-slate-300">Last {Math.min(limit, totalEntries)}</span>
        </div>
      </div>
    </div>
  );
}
