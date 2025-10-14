'use client';

import { useState, useEffect } from 'react';
import { CORE_API_BASE } from '../../lib/api';

interface ToneState {
  tone_target: string;
  tone_score: number;
  formality_bias: number;
  empathy_bias: number;
  confidence: number;
  signals: Record<string, any>;
}

interface ToneHistoryEntry {
  ts: string;
  tone_score: number;
  formality: number;
  empathy_cue: string;
}

interface ToneAnalysisData {
  current: ToneState;
  history: ToneHistoryEntry[];
  config: Record<string, any>;
}

interface ToneEchoProps {
  userId: string;
  autoRefresh?: boolean;
  refreshInterval?: number;
}

function getToneLabel(score: number): string {
  if (score >= 0.7) return 'Casual & Warm';
  if (score >= 0.3) return 'Balanced';
  return 'Formal & Concise';
}

function getToneColor(score: number): string {
  if (score >= 0.7) return 'rgb(251, 191, 36)'; // yellow
  if (score >= 0.3) return 'rgb(59, 130, 246)'; // blue
  return 'rgb(148, 163, 184)'; // slate
}

function getEmpathyEmoji(bias: number): string {
  if (bias > 0.2) return '💖';
  if (bias < -0.2) return '🤖';
  return '🙂';
}

export function ToneEcho({
  userId,
  autoRefresh = true,
  refreshInterval = 3000,
}: ToneEchoProps) {
  const [data, setData] = useState<ToneAnalysisData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchToneAnalysis = async () => {
    try {
      const response = await fetch(`${CORE_API_BASE}/ui/hc/tone_analysis/${userId}?limit=20`);
      const json = await response.json();

      if (json.ok) {
        setData(json);
        setError(null);
      } else {
        setError(json.detail || 'Failed to load tone analysis');
      }
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchToneAnalysis();

    if (autoRefresh) {
      const interval = setInterval(fetchToneAnalysis, refreshInterval);
      return () => clearInterval(interval);
    }
  }, [userId, autoRefresh, refreshInterval]);

  if (loading) {
    return (
      <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6">
        <h2 className="mb-4 text-lg font-semibold text-slate-200">
          Adaptive Tone Echo
        </h2>
        <div className="flex h-64 items-center justify-center">
          <div className="text-slate-500">Loading tone analysis...</div>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="rounded-2xl border border-red-800/30 bg-red-950/20 p-6">
        <h2 className="mb-4 text-lg font-semibold text-red-400">
          Adaptive Tone Echo
        </h2>
        <div className="text-red-300">{error || 'No tone data available'}</div>
      </div>
    );
  }

  const { current, history } = data;

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6">
      <h2 className="mb-4 text-lg font-semibold text-slate-200">
        Adaptive Tone Echo
      </h2>

      {/* Current Tone State */}
      <div className="mb-6 rounded-lg border border-slate-700 bg-slate-950/50 p-4">
        <div className="mb-3 text-sm font-medium text-slate-400">Current Tone</div>

        {/* Tone Scale Visualization */}
        <div className="relative mb-6 h-8 overflow-hidden rounded-full bg-slate-800">
          {/* Gradient background */}
          <div
            className="absolute inset-0"
            style={{
              background: 'linear-gradient(to right, rgb(148, 163, 184), rgb(59, 130, 246), rgb(251, 191, 36))',
            }}
          />
          {/* Current position indicator */}
          <div
            className="absolute top-0 h-full w-1 bg-white shadow-lg transition-all duration-500"
            style={{ left: `${current.tone_score * 100}%` }}
          >
            <div className="absolute -top-8 left-1/2 -translate-x-1/2 whitespace-nowrap text-xs font-semibold text-white">
              {getToneLabel(current.tone_score)}
            </div>
          </div>
        </div>

        {/* Tone Score */}
        <div className="mb-4 flex items-center justify-between text-sm">
          <span className="text-slate-400">Tone Score:</span>
          <span
            className="font-mono text-lg font-bold"
            style={{ color: getToneColor(current.tone_score) }}
          >
            {current.tone_score.toFixed(2)}
          </span>
        </div>

        {/* Formality & Empathy Indicators */}
        <div className="grid grid-cols-2 gap-4">
          {/* Formality Bias */}
          <div className="rounded-lg bg-slate-800/50 p-3">
            <div className="mb-2 text-xs text-slate-400">Formality Bias</div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-500">Casual</span>
              <div className="mx-2 h-2 flex-1 overflow-hidden rounded-full bg-slate-700">
                <div
                  className="h-full bg-blue-500 transition-all duration-500"
                  style={{
                    width: `${Math.abs(current.formality_bias) * 100}%`,
                    marginLeft: current.formality_bias < 0 ? '0' : 'auto',
                  }}
                />
              </div>
              <span className="text-xs text-slate-500">Formal</span>
            </div>
            <div className="mt-1 text-center font-mono text-sm font-semibold text-slate-300">
              {current.formality_bias > 0 ? '+' : ''}{current.formality_bias.toFixed(2)}
            </div>
          </div>

          {/* Empathy Bias */}
          <div className="rounded-lg bg-slate-800/50 p-3">
            <div className="mb-2 text-xs text-slate-400">Empathy Bias</div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-500">Concise</span>
              <div className="mx-2 h-2 flex-1 overflow-hidden rounded-full bg-slate-700">
                <div
                  className="h-full bg-pink-500 transition-all duration-500"
                  style={{
                    width: `${Math.abs(current.empathy_bias) * 100}%`,
                    marginLeft: current.empathy_bias < 0 ? '0' : 'auto',
                  }}
                />
              </div>
              <span className="text-xs text-slate-500">Empathetic</span>
            </div>
            <div className="mt-1 text-center text-2xl">
              {getEmpathyEmoji(current.empathy_bias)}
            </div>
          </div>
        </div>

        {/* Confidence */}
        <div className="mt-4 flex items-center justify-between text-xs">
          <span className="text-slate-400">Adaptation Confidence:</span>
          <span className="font-semibold text-slate-300">
            {Math.round(current.confidence * 100)}%
          </span>
        </div>
      </div>

      {/* Tone History */}
      {history.length > 0 && (
        <div className="rounded-lg border border-slate-700 bg-slate-950/50 p-4">
          <div className="mb-3 text-sm font-medium text-slate-400">Tone History</div>
          <div className="space-y-2">
            {history.slice(-10).reverse().map((entry, idx) => {
              const timestamp = new Date(entry.ts);
              const toneColor = getToneColor(entry.tone_score);

              return (
                <div
                  key={idx}
                  className="flex items-center gap-3 rounded-lg bg-slate-800/30 p-2 text-xs"
                >
                  <div className="w-16 text-slate-500">
                    {timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </div>
                  <div className="flex-1">
                    <div className="h-2 overflow-hidden rounded-full bg-slate-700">
                      <div
                        className="h-full transition-all"
                        style={{
                          width: `${entry.tone_score * 100}%`,
                          backgroundColor: toneColor,
                        }}
                      />
                    </div>
                  </div>
                  <div className="w-12 text-right font-mono text-slate-400">
                    {entry.tone_score.toFixed(2)}
                  </div>
                  <div className="w-20 text-slate-500">
                    {entry.formality > 0.6 ? 'Formal' : entry.formality < 0.4 ? 'Casual' : 'Balanced'}
                  </div>
                  <div className="text-base">
                    {entry.empathy_cue === 'high' ? '💖' : entry.empathy_cue === 'low' ? '🤖' : '🙂'}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Target & Signals */}
      <div className="mt-4 flex items-center justify-between text-xs text-slate-400">
        <div>
          Target: <span className="font-semibold text-slate-300">{current.tone_target}</span>
        </div>
        {Object.keys(current.signals).length > 0 && (
          <div>
            Signals: <span className="font-semibold text-slate-300">{Object.keys(current.signals).length}</span>
          </div>
        )}
      </div>
    </div>
  );
}
