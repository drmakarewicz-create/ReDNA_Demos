'use client';

import { useState, useEffect } from 'react';
import { CORE_API_BASE } from '../lib/api';

interface CuriosityItem {
  path: string;
  curiosity: number;
  rr: number;
  ucn: number;
  container_type: string;
  priority_score: number;
  reason: string;
  children_count: number;
  missing_count: number;
}

interface CuriosityMapData {
  user_id: string;
  total_items: number;
  high_curiosity_count: number;
  missing_containers_count: number;
  top_priorities: CuriosityItem[];
  by_namespace: Record<string, CuriosityItem[]>;
  stats: {
    mean_curiosity: number;
    mean_rr: number;
  };
}

interface CuriosityMapPanelProps {
  userId: string;
}

function getCuriosityColor(curiosity: number): string {
  if (curiosity >= 80) return 'text-red-400';
  if (curiosity >= 60) return 'text-orange-400';
  if (curiosity >= 40) return 'text-yellow-400';
  if (curiosity >= 20) return 'text-green-400';
  return 'text-slate-500';
}

function getCuriosityBg(curiosity: number): string {
  if (curiosity >= 80) return 'bg-red-950/20 border-red-800/30';
  if (curiosity >= 60) return 'bg-orange-950/20 border-orange-800/30';
  if (curiosity >= 40) return 'bg-yellow-950/20 border-yellow-800/30';
  if (curiosity >= 20) return 'bg-green-950/20 border-green-800/30';
  return 'bg-slate-950/20 border-slate-800/30';
}

function getCuriosityIcon(curiosity: number): string {
  if (curiosity >= 80) return '🔥';
  if (curiosity >= 60) return '⚡';
  if (curiosity >= 40) return '💡';
  if (curiosity >= 20) return '✓';
  return '·';
}

export function CuriosityMapPanel({ userId }: CuriosityMapPanelProps) {
  const [data, setData] = useState<CuriosityMapData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedNamespace, setSelectedNamespace] = useState<string | null>(null);

  useEffect(() => {
    const fetchCuriosityMap = async () => {
      try {
        setLoading(true);
        const response = await fetch(`${CORE_API_BASE}/curiosity/${userId}/map`);
        const json = await response.json();

        if (json.ok) {
          setData(json);
          setError(null);
        } else {
          setError(json.detail || 'Failed to load curiosity map');
        }
      } catch (err) {
        setError(String(err));
      } finally {
        setLoading(false);
      }
    };

    if (userId) {
      fetchCuriosityMap();
    }
  }, [userId]);

  if (loading) {
    return (
      <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6">
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-400">
          Curiosity Map
        </h2>
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-16 animate-pulse rounded-lg bg-slate-800/50" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6">
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-400">
          Curiosity Map
        </h2>
        <div className="text-center text-sm text-red-400">{error}</div>
      </div>
    );
  }

  if (!data) {
    return null;
  }

  const namespaces = Object.keys(data.by_namespace).sort();

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 shadow-xl">
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
          Curiosity Map - Dev Mode
        </h2>
        <div className="rounded-lg bg-violet-950/40 px-3 py-1 text-xs font-semibold text-violet-300">
          {data.user_id}
        </div>
      </div>

      {/* Stats Grid */}
      <div className="mb-6 grid grid-cols-4 gap-3">
        <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3 text-center">
          <div className="text-xs text-slate-500">Total Items</div>
          <div className="mt-1 text-lg font-semibold text-slate-200">{data.total_items}</div>
        </div>
        <div className="rounded-lg border border-orange-800/50 bg-orange-950/20 p-3 text-center">
          <div className="text-xs text-orange-400">High Curiosity</div>
          <div className="mt-1 text-lg font-semibold text-orange-300">{data.high_curiosity_count}</div>
        </div>
        <div className="rounded-lg border border-red-800/50 bg-red-950/20 p-3 text-center">
          <div className="text-xs text-red-400">Missing</div>
          <div className="mt-1 text-lg font-semibold text-red-300">{data.missing_containers_count}</div>
        </div>
        <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3 text-center">
          <div className="text-xs text-slate-500">Avg Curiosity</div>
          <div className={`mt-1 text-lg font-semibold ${getCuriosityColor(data.stats.mean_curiosity)}`}>
            {data.stats.mean_curiosity.toFixed(1)}
          </div>
        </div>
      </div>

      {/* Top Priorities */}
      <div className="mb-6">
        <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">
          Top Priorities
        </h3>
        <div className="space-y-2">
          {data.top_priorities.slice(0, 5).map((item, index) => (
            <div
              key={item.path}
              className={`flex items-center justify-between rounded-lg border p-3 ${getCuriosityBg(item.curiosity)}`}
            >
              <div className="flex items-center gap-3">
                <div className="flex h-6 w-6 items-center justify-center rounded-full bg-slate-800 text-xs font-semibold text-slate-400">
                  {index + 1}
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-slate-200">{item.path}</span>
                    <span
                      className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${
                        item.container_type === 'missing'
                          ? 'bg-red-950/40 text-red-400'
                          : item.container_type === 'container'
                            ? 'bg-blue-950/40 text-blue-400'
                            : 'bg-slate-800 text-slate-400'
                      }`}
                    >
                      {item.container_type}
                    </span>
                  </div>
                  <div className="mt-0.5 text-xs text-slate-500">{item.reason}</div>
                </div>
              </div>
              <div className="flex items-center gap-3 text-right">
                <div>
                  <div className="text-[10px] text-slate-500">Curiosity</div>
                  <div className={`text-sm font-semibold ${getCuriosityColor(item.curiosity)}`}>
                    {getCuriosityIcon(item.curiosity)} {item.curiosity.toFixed(0)}
                  </div>
                </div>
                <div>
                  <div className="text-[10px] text-slate-500">Priority</div>
                  <div className="text-sm font-semibold text-violet-400">{item.priority_score.toFixed(1)}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Namespace Breakdown */}
      <div>
        <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">
          By Namespace
        </h3>
        <div className="grid grid-cols-3 gap-2">
          {namespaces.map((namespace) => {
            const items = data.by_namespace[namespace];
            const avgCuriosity =
              items.reduce((sum, item) => sum + item.curiosity, 0) / items.length;
            const isSelected = selectedNamespace === namespace;

            return (
              <button
                key={namespace}
                onClick={() => setSelectedNamespace(isSelected ? null : namespace)}
                className={`rounded-lg border p-3 text-left transition ${
                  isSelected
                    ? 'border-violet-600 bg-violet-950/40'
                    : 'border-slate-800 bg-slate-950/60 hover:bg-slate-800/40'
                }`}
              >
                <div className="text-xs font-semibold text-slate-300">{namespace}</div>
                <div className="mt-1 flex items-center justify-between">
                  <span className="text-[10px] text-slate-500">{items.length} items</span>
                  <span className={`text-xs font-semibold ${getCuriosityColor(avgCuriosity)}`}>
                    {avgCuriosity.toFixed(0)}
                  </span>
                </div>
              </button>
            );
          })}
        </div>

        {/* Selected Namespace Details */}
        {selectedNamespace && (
          <div className="mt-4 rounded-lg border border-violet-800 bg-violet-950/20 p-4">
            <h4 className="mb-3 text-xs font-semibold uppercase tracking-wide text-violet-300">
              {selectedNamespace} Details
            </h4>
            <div className="space-y-2">
              {data.by_namespace[selectedNamespace].slice(0, 10).map((item) => (
                <div
                  key={item.path}
                  className="flex items-center justify-between rounded border border-slate-800/50 bg-slate-900/40 px-3 py-2 text-xs"
                >
                  <span className="truncate text-slate-300">{item.path.split('.').pop()}</span>
                  <div className="ml-3 flex items-center gap-3">
                    <span className="text-slate-500">RR: {item.rr.toFixed(1)}</span>
                    <span className={`font-semibold ${getCuriosityColor(item.curiosity)}`}>
                      C: {item.curiosity.toFixed(0)}
                    </span>
                  </div>
                </div>
              ))}
              {data.by_namespace[selectedNamespace].length > 10 && (
                <div className="pt-1 text-center text-[10px] text-slate-500">
                  ...and {data.by_namespace[selectedNamespace].length - 10} more
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
