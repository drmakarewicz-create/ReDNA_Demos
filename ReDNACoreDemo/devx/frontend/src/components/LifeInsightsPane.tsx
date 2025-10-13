import React, { useState, useEffect, useCallback } from 'react';
import { CORE_API_BASE } from '@/lib/env';

interface InsightMetrics {
  goals_total: number;
  goals_active: number;
  goals_completed: number;
  goal_completion_rate: number;
  goal_velocity: number;
  goals_at_risk: Array<{
    id: string;
    text: string;
    idle_days: number;
    confidence: number;
  }>;

  todos_completed: number;
  todos_created: number;
  todos_completion_rate: number;
  todays_three_success_rate: number;
  avg_completion_hour: number | null;

  quadrant_share: {
    important_urgent: number;
    important_not_urgent: number;
    not_important_urgent: number;
    neither: number;
  };

  current_streak: number;
  longest_streak: number;
  streak_days: string[];

  top_tags: Array<[string, number]>;
  focus_categories: Record<string, number>;

  nudge_acceptance_rate: number;
  nudge_completion_rate: number;

  projects_at_risk: Array<{
    id: string;
    title: string;
    reason: string;
    days_idle: number | null;
  }>;

  idle_days_threshold: number;
  window_days: number;
  computed_at: string;
}

interface TrendDataPoint {
  week_start: string;
  week_label: string;
  todos_completed: number;
  goals_progressed: number;
  avg_confidence: number;
  quadrant_share: Record<string, number>;
  top_tag: string | null;
}

interface TrendsData {
  weeks: number;
  start_date: string;
  end_date: string;
  data: TrendDataPoint[];
  computed_at: string;
}

interface LifeInsightsPaneProps {
  userId: string;
  embedded?: boolean;
}

type TrendDirection = 'up' | 'down' | 'steady';

interface EmpathyHistoryPoint {
  timestamp: string;
  emotional_state?: string | null;
  intensity: number;
  trust_score: number;
  rapport_score: number;
}

interface EmpathyLatestMetrics {
  timestamp: string;
  emotional_state?: string | null;
  intensity: number;
  confidence: number;
  primary_needs: string[];
  recommended_actions: string[];
  bonding_metrics: {
    trust_score: number;
    rapport_score: number;
    turns_observed: number;
    positive_turns: number;
  };
}

interface EmpathyTelemetry {
  latest: EmpathyLatestMetrics | null;
  trend: {
    direction: TrendDirection;
    trust_delta: number;
    rapport_delta: number;
    intensity_delta: number;
  };
  samples: number;
  window_days: number;
  history: EmpathyHistoryPoint[];
}

interface CuriosityTopGap {
  target?: string;
  namespace?: string;
  debt_score?: number;
  last_seen?: string | null;
}

interface CuriosityTrend {
  direction: TrendDirection;
  average_debt: number;
  delta: number;
  stale_targets: number;
}

interface CuriositySnapshotMetadata {
  total_records: number;
  generated_at?: string;
  prompt?: string | null;
  daily_questions: CuriosityTopGap[];
}

interface CuriosityTelemetry {
  top_gaps: CuriosityTopGap[];
  trend: CuriosityTrend;
  snapshot: CuriositySnapshotMetadata;
}

interface HumanIntelSnapshot {
  user_id: string;
  generated_at: string;
  window_days: number;
  empathy: EmpathyTelemetry;
  curiosity: CuriosityTelemetry;
}

interface HumanIntelApiResponse {
  ok: boolean;
  snapshot: HumanIntelSnapshot;
  duration_ms: number;
}

export function LifeInsightsPane({ userId, embedded = false }: LifeInsightsPaneProps) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [insights, setInsights] = useState<InsightMetrics | null>(null);
  const [trends, setTrends] = useState<TrendsData | null>(null);
  const [showDetails, setShowDetails] = useState(false);
  const [humanIntel, setHumanIntel] = useState<HumanIntelSnapshot | null>(null);
  const [humanIntelLoading, setHumanIntelLoading] = useState(true);
  const [humanIntelError, setHumanIntelError] = useState<string | null>(null);
  const [showHumanIntelModal, setShowHumanIntelModal] = useState(false);

  const loadInsights = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${CORE_API_BASE}/ui/hc/life/${userId}/insights?days=14`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = await response.json();
      setInsights(data.insights);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load insights');
      console.error('Failed to load insights:', err);
    } finally {
      setLoading(false);
    }
  }, [userId]);

  const loadTrends = useCallback(async () => {
    try {
      const response = await fetch(`${CORE_API_BASE}/ui/hc/life/${userId}/trends?weeks=8`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = await response.json();
      setTrends(data.trends);
    } catch (err) {
      console.error('Failed to load trends:', err);
    }
  }, [userId]);

  const loadHumanIntel = useCallback(async () => {
    setHumanIntelLoading(true);
    setHumanIntelError(null);
    try {
      const response = await fetch(`${CORE_API_BASE}/ui/hc/life/${userId}/human_intel?days=7`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data: HumanIntelApiResponse = await response.json();
      setHumanIntel(data.snapshot);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load telemetry';
      setHumanIntelError(message);
      console.error('Failed to load human intelligence telemetry:', err);
    } finally {
      setHumanIntelLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    loadInsights();
  }, [loadInsights]);

  useEffect(() => {
    loadHumanIntel();
  }, [loadHumanIntel]);

  const trendSymbols: Record<TrendDirection, string> = { up: '↑', down: '↓', steady: '→' };
  const trendColorMap: Record<TrendDirection, string> = {
    up: 'text-emerald-700 bg-emerald-100 border border-emerald-200',
    down: 'text-rose-700 bg-rose-100 border border-rose-200',
    steady: 'text-slate-600 bg-slate-100 border border-slate-200',
  };

  const formatDelta = (value: number): string => {
    const scaled = value * 100;
    if (Math.abs(scaled) < 0.05) {
      return '0.0 pts';
    }
    const prefix = scaled > 0 ? '+' : '';
    return `${prefix}${scaled.toFixed(1)} pts`;
  };

  const formatDebt = (value?: number): string => {
    if (value === undefined || Number.isNaN(value)) {
      return '—';
    }
    return value.toFixed(2);
  };

  const renderTrendChip = (direction: TrendDirection, label: string) => (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold ${trendColorMap[direction]}`}
    >
      {trendSymbols[direction]} {label}
    </span>
  );

  if (loading) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-6">
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-gray-300 border-t-blue-600" />
          <span>Loading insights...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4">
        <p className="text-sm text-red-700">Failed to load insights: {error}</p>
        <button
          onClick={loadInsights}
          className="mt-2 text-sm text-red-800 underline hover:no-underline"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!insights) {
    return null;
  }

  // Empty state - insufficient data
  if (insights.todos_completed === 0 && insights.goals_total === 0) {
    return (
      <div className="rounded-lg border border-gray-200 bg-gray-50 p-6">
        <div className="text-center">
          <div className="text-4xl mb-3">📊</div>
          <h3 className="text-sm font-semibold text-gray-700 mb-2">No insights yet</h3>
          <p className="text-xs text-gray-600 mb-4">
            Complete a few goals and todos to see your progress analytics
          </p>
          <div className="text-xs text-gray-500 space-y-1">
            <div>💡 Tip: Use "Today's 3" to track daily wins</div>
            <div>🎯 Tip: Set goals with confidence levels</div>
            <div>📅 Tip: Organize work by quadrant priority</div>
          </div>
        </div>
      </div>
    );
  }

  const { quadrant_share } = insights;
  const mostActiveQuadrant = Object.entries(quadrant_share).sort((a, b) => b[1] - a[1])[0];

  const openDetailsModal = () => {
    if (!trends) {
      loadTrends();
    }
    setShowDetails(true);
  };

  const empathyLatest = humanIntel?.empathy.latest;
  const empathyTrustScore = empathyLatest ? Math.round(empathyLatest.bonding_metrics.trust_score * 100) : null;
  const empathyDirection: TrendDirection = humanIntel?.empathy.trend.direction ?? 'steady';
  const curiosityDirection: TrendDirection = humanIntel?.curiosity.trend.direction ?? 'steady';
  const curiosityAverageDebt = humanIntel?.curiosity.trend.average_debt ?? 0;
  const curiosityTopGaps = humanIntel?.curiosity.top_gaps ?? [];
  const curiosityPromptItems = humanIntel?.curiosity.snapshot.daily_questions ?? [];

  return (
    <div className={embedded ? '' : 'space-y-4'}>
      {/* Human Intelligence */}
      <div className="rounded-lg border border-indigo-200 bg-gradient-to-br from-indigo-50 via-sky-50 to-white p-4 shadow-sm">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-indigo-900 flex items-center gap-2">
              <span>🧠</span>
              <span>Human Intelligence</span>
            </h3>
            <p className="text-xs text-indigo-700 mt-1">
              Empathy and curiosity telemetry for the last {humanIntel?.window_days ?? 7} days
            </p>
          </div>
          {!humanIntelLoading && !humanIntelError && humanIntel ? (
            <button
              onClick={() => setShowHumanIntelModal(true)}
              className="text-xs font-medium text-indigo-800 hover:text-indigo-900 underline decoration-indigo-400/70"
            >
              View more →
            </button>
          ) : null}
        </div>
        <div className="mt-3">
          {humanIntelLoading ? (
            <div className="flex items-center gap-2 text-xs text-indigo-600">
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-indigo-200 border-t-indigo-500" />
              <span>Loading telemetry…</span>
            </div>
          ) : humanIntelError ? (
            <div className="rounded border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
              Failed to load human intelligence telemetry ({humanIntelError}).
              <button
                onClick={loadHumanIntel}
                className="ml-2 font-semibold text-rose-700 underline underline-offset-2"
              >
                Retry
              </button>
            </div>
          ) : humanIntel ? (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <div className="rounded-lg border border-indigo-100 bg-white/80 p-3">
                <div className="text-xs font-semibold uppercase text-indigo-600">Empathy</div>
                {empathyLatest ? (
                  <>
                    <div className="mt-1 flex items-baseline gap-3">
                      <div className="text-2xl font-semibold text-indigo-900">
                        {empathyTrustScore !== null ? `${empathyTrustScore}` : '—'}
                        <span className="text-sm font-medium text-indigo-500 ml-1">trust</span>
                      </div>
                      {renderTrendChip(empathyDirection, formatDelta(humanIntel.empathy.trend.trust_delta))}
                    </div>
                    <div className="mt-1 text-xs text-indigo-700">
                      State:{' '}
                      <span className="font-semibold text-indigo-900">
                        {empathyLatest.emotional_state ?? 'neutral'}
                      </span>
                    </div>
                    {empathyLatest.primary_needs.length > 0 && (
                      <div className="mt-2 text-xs text-indigo-600">
                        Needs: {empathyLatest.primary_needs.slice(0, 2).join(', ')}
                      </div>
                    )}
                    {empathyLatest.recommended_actions.length > 0 && (
                      <div className="mt-2 rounded border border-indigo-100 bg-indigo-50 px-3 py-2 text-xs text-indigo-700">
                        <div className="font-semibold mb-1">Next action</div>
                        <div>{empathyLatest.recommended_actions[0]}</div>
                      </div>
                    )}
                  </>
                ) : (
                  <div className="mt-1 text-xs text-indigo-600">
                    No empathy signals captured yet — engage with the Head Coach to build rapport.
                  </div>
                )}
              </div>
              <div className="rounded-lg border border-sky-100 bg-white/80 p-3">
                <div className="text-xs font-semibold uppercase text-sky-700">Curiosity</div>
                <div className="mt-1 flex items-baseline gap-3">
                  <div className="text-2xl font-semibold text-sky-900">
                    {formatDebt(curiosityAverageDebt)}
                    <span className="text-sm font-medium text-sky-500 ml-1">avg debt</span>
                  </div>
                  {renderTrendChip(curiosityDirection, formatDelta(humanIntel.curiosity.trend.delta))}
                </div>
                {curiosityTopGaps.length > 0 ? (
                  <ul className="mt-2 space-y-1 text-xs text-sky-700">
                    {curiosityTopGaps.slice(0, 3).map((gap, index) => (
                      <li key={`${gap.target ?? index}`} className="flex items-center justify-between gap-2">
                        <span className="truncate">
                          {gap.namespace ?? gap.target ?? 'Unlabelled container'}
                        </span>
                        <span className="font-semibold text-sky-900">{formatDebt(gap.debt_score)}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <div className="mt-2 text-xs text-sky-600">No outstanding curiosity gaps.</div>
                )}
                {curiosityPromptItems.length > 0 && (
                  <div className="mt-3 text-xs text-sky-700">
                    Prompt of the day:{' '}
                    <span className="italic text-sky-900">
                      {curiosityPromptItems[0].target ?? curiosityPromptItems[0].namespace ?? 'Explore a new topic'}
                    </span>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="rounded border border-indigo-100 bg-white/70 px-3 py-2 text-xs text-indigo-600">
              No human intelligence telemetry yet — interact with the Head Coach to capture signals.
            </div>
          )}
        </div>
      </div>

      {/* This Week at a Glance */}
      <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
        <h3 className="text-sm font-semibold text-gray-800 mb-3 flex items-center gap-2">
          <span>📈</span>
          <span>This Week at a Glance</span>
        </h3>
        <div className="grid grid-cols-3 gap-3">
          <div className="text-center">
            <div className="text-2xl font-bold text-blue-600">{insights.todays_three_success_rate.toFixed(0)}%</div>
            <div className="text-xs text-gray-600 mt-1">Today's 3 Success</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-green-600">{insights.current_streak}</div>
            <div className="text-xs text-gray-600 mt-1">Day Streak</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-purple-600">{insights.todos_completed}</div>
            <div className="text-xs text-gray-600 mt-1">Tasks Done</div>
          </div>
        </div>
        {insights.avg_completion_hour !== null && (
          <div className="mt-3 pt-3 border-t border-gray-100 text-xs text-gray-600 text-center">
            Most productive around <span className="font-semibold">{Math.floor(insights.avg_completion_hour)}:00</span>
          </div>
        )}
      </div>

      {/* Quadrant Balance */}
      <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
        <h3 className="text-sm font-semibold text-gray-800 mb-3 flex items-center gap-2">
          <span>⚖️</span>
          <span>Quadrant Balance</span>
        </h3>
        <div className="grid grid-cols-2 gap-2 mb-3">
          <div className="border border-red-200 rounded p-2 bg-red-50">
            <div className="text-xs font-semibold text-red-700 mb-1">IU - Urgent</div>
            <div className="text-lg font-bold text-red-600">{quadrant_share.important_urgent.toFixed(0)}%</div>
          </div>
          <div className="border border-blue-200 rounded p-2 bg-blue-50">
            <div className="text-xs font-semibold text-blue-700 mb-1">IN - Plan</div>
            <div className="text-lg font-bold text-blue-600">{quadrant_share.important_not_urgent.toFixed(0)}%</div>
          </div>
          <div className="border border-yellow-200 rounded p-2 bg-yellow-50">
            <div className="text-xs font-semibold text-yellow-700 mb-1">NU - Delegate</div>
            <div className="text-lg font-bold text-yellow-600">{quadrant_share.not_important_urgent.toFixed(0)}%</div>
          </div>
          <div className="border border-gray-200 rounded p-2 bg-gray-50">
            <div className="text-xs font-semibold text-gray-700 mb-1">NN - Avoid</div>
            <div className="text-lg font-bold text-gray-600">{quadrant_share.neither.toFixed(0)}%</div>
          </div>
        </div>
        {mostActiveQuadrant[1] > 50 && (
          <div className="text-xs text-amber-700 bg-amber-50 rounded p-2 border border-amber-200">
            💡 <span className="font-semibold">{mostActiveQuadrant[1].toFixed(0)}%</span> in {mostActiveQuadrant[0].replace(/_/g, ' ')}.
            Consider rebalancing toward important/not-urgent work.
          </div>
        )}
      </div>

      {/* Goal Momentum */}
      {insights.goals_active > 0 && (
        <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
          <h3 className="text-sm font-semibold text-gray-800 mb-3 flex items-center gap-2">
            <span>🎯</span>
            <span>Goal Momentum</span>
          </h3>
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-700">Active goals</span>
              <span className="font-semibold text-gray-900">{insights.goals_active}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-700">Completion rate</span>
              <span className="font-semibold text-green-600">{(insights.goal_completion_rate * 100).toFixed(0)}%</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-700">Velocity</span>
              <span className="font-semibold text-blue-600">+{(insights.goal_velocity * 100).toFixed(1)}%/wk</span>
            </div>
          </div>
          {insights.goals_at_risk.length > 0 && (
            <div className="mt-3 pt-3 border-t border-gray-100">
              <div className="text-xs font-semibold text-orange-700 mb-2">⚠️ At Risk ({insights.goals_at_risk.length})</div>
              <div className="space-y-1">
                {insights.goals_at_risk.slice(0, 3).map(goal => (
                  <div key={goal.id} className="text-xs text-gray-700">
                    • {goal.text} <span className="text-gray-500">({goal.idle_days}d idle)</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Focus Clusters */}
      {insights.top_tags.length > 0 && (
        <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
          <h3 className="text-sm font-semibold text-gray-800 mb-3 flex items-center gap-2">
            <span>🔥</span>
            <span>Focus Clusters</span>
          </h3>
          <div className="flex flex-wrap gap-2">
            {insights.top_tags.map(([tag, count]) => (
              <div key={tag} className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-purple-100 border border-purple-200">
                <span className="text-xs font-medium text-purple-800">{tag}</span>
                <span className="text-xs text-purple-600">×{count}</span>
              </div>
            ))}
          </div>
          {Object.keys(insights.focus_categories).length > 0 && (
            <div className="mt-3 pt-3 border-t border-gray-100">
              <div className="text-xs text-gray-600 space-y-1">
                {Object.entries(insights.focus_categories)
                  .sort((a, b) => b[1] - a[1])
                  .slice(0, 3)
                  .map(([cat, count]) => (
                    <div key={cat} className="flex justify-between">
                      <span className="capitalize">{cat}</span>
                      <span className="font-semibold">{count}</span>
                    </div>
                  ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Nudge Impact */}
      {insights.nudge_acceptance_rate > 0 && (
        <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
          <h3 className="text-sm font-semibold text-gray-800 mb-3 flex items-center gap-2">
            <span>💌</span>
            <span>Nudge Impact</span>
          </h3>
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-700">Acceptance rate</span>
              <span className="font-semibold text-blue-600">{(insights.nudge_acceptance_rate * 100).toFixed(0)}%</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-700">Completion rate</span>
              <span className="font-semibold text-green-600">{(insights.nudge_completion_rate * 100).toFixed(0)}%</span>
            </div>
          </div>
        </div>
      )}

      {/* View Details Button */}
      <div className="text-center">
        <button
          onClick={openDetailsModal}
          className="text-sm text-blue-600 hover:text-blue-700 underline hover:no-underline"
        >
          View detailed trends →
        </button>
      </div>

      {/* Human Intelligence Modal */}
      {showHumanIntelModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-auto">
            <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-gray-900">Human Intelligence Telemetry</h2>
                <p className="text-sm text-gray-600">
                  Empathy & curiosity signals for the last {humanIntel?.window_days ?? 7} days
                </p>
              </div>
              <button
                onClick={() => setShowHumanIntelModal(false)}
                className="text-gray-500 hover:text-gray-700"
              >
                ✕
              </button>
            </div>
            <div className="grid gap-6 p-6 md:grid-cols-2">
              {humanIntel ? (
                <>
                  <div className="space-y-4">
                    <h3 className="text-sm font-semibold text-indigo-900 flex items-center gap-2">
                      <span>🧭</span>
                      <span>Empathy Signals</span>
                    </h3>
                    {empathyLatest ? (
                      <div className="space-y-3 text-sm text-indigo-800">
                        <div>
                          Current state:{' '}
                          <span className="font-semibold text-indigo-900">
                            {empathyLatest.emotional_state ?? 'neutral'}
                          </span>{' '}
                          • intensity {(empathyLatest.intensity * 100).toFixed(0)}%
                        </div>
                        <div className="text-xs text-indigo-600 space-y-1">
                          <div>Trust score: {(empathyLatest.bonding_metrics.trust_score * 100).toFixed(1)}%</div>
                          <div>Rapport score: {(empathyLatest.bonding_metrics.rapport_score * 100).toFixed(1)}%</div>
                          <div>Turns observed: {empathyLatest.bonding_metrics.turns_observed}</div>
                        </div>
                        {empathyLatest.recommended_actions.length > 0 && (
                          <div className="rounded border border-indigo-100 bg-indigo-50 px-3 py-2 text-xs text-indigo-700">
                            <div className="font-semibold mb-1">Recommended responses</div>
                            <ul className="list-disc list-inside space-y-1">
                              {empathyLatest.recommended_actions.slice(0, 3).map(action => (
                                <li key={action}>{action}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    ) : (
                      <div className="text-xs text-indigo-600">No empathy telemetry in the selected window.</div>
                    )}
                    <div>
                      <div className="text-xs font-semibold uppercase text-indigo-600 mb-2">Recent history</div>
                      {humanIntel.empathy.history.length === 0 ? (
                        <div className="text-xs text-indigo-500">No recent empathy events captured.</div>
                      ) : (
                        <div className="space-y-1 text-xs text-indigo-700">
                          {humanIntel.empathy.history.map(entry => (
                            <div key={entry.timestamp} className="flex justify-between gap-3">
                              <span>{new Date(entry.timestamp).toLocaleString()}</span>
                              <span className="font-medium">
                                {entry.emotional_state ?? 'neutral'} · {(entry.intensity * 100).toFixed(0)}%
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="space-y-4">
                    <h3 className="text-sm font-semibold text-sky-900 flex items-center gap-2">
                      <span>🔍</span>
                      <span>Curiosity Debt</span>
                    </h3>
                    <div className="text-sm text-sky-800 flex items-center gap-2">
                      <span>Average debt {formatDebt(curiosityAverageDebt)}</span>
                      {renderTrendChip(curiosityDirection, formatDelta(humanIntel.curiosity.trend.delta))}
                    </div>
                    {humanIntel.curiosity.snapshot.prompt && (
                      <div>
                        <div className="text-xs font-semibold uppercase text-sky-600 mb-1">Daily prompt</div>
                        <pre className="whitespace-pre-wrap rounded border border-sky-100 bg-sky-50 p-3 text-xs text-sky-700">
                          {humanIntel.curiosity.snapshot.prompt}
                        </pre>
                      </div>
                    )}
                    <div>
                      <div className="text-xs font-semibold uppercase text-sky-600 mb-2">Top gaps</div>
                      {curiosityTopGaps.length === 0 ? (
                        <div className="text-xs text-sky-600">No outstanding containers.</div>
                      ) : (
                        <div className="space-y-1 text-xs text-sky-700">
                          {curiosityTopGaps.map((gap, index) => (
                            <div key={`${gap.target ?? index}`} className="flex justify-between gap-3">
                              <span>{gap.namespace ?? gap.target ?? 'Unlabelled container'}</span>
                              <span className="font-semibold text-sky-900">{formatDebt(gap.debt_score)}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                    {curiosityPromptItems.length > 1 && (
                      <div>
                        <div className="text-xs font-semibold uppercase text-sky-600 mb-1">Daily questions</div>
                        <ul className="list-disc list-inside text-xs text-sky-700 space-y-1">
                          {curiosityPromptItems.slice(0, 3).map((item, index) => (
                            <li key={`${item.target ?? index}`}>
                              {item.target ?? item.namespace ?? 'Explore a new container'}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                </>
              ) : (
                <div className="col-span-2 text-sm text-gray-600">
                  No telemetry available yet for this user.
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Trends Modal */}
      {showDetails && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-auto">
            <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">8-Week Trends</h2>
              <button
                onClick={() => setShowDetails(false)}
                className="text-gray-500 hover:text-gray-700"
              >
                ✕
              </button>
            </div>
            <div className="p-6">
              {!trends ? (
                <div className="flex items-center justify-center py-12">
                  <div className="h-8 w-8 animate-spin rounded-full border-4 border-gray-300 border-t-blue-600" />
                </div>
              ) : (
                <div className="space-y-6">
                  {/* Todos Completed Chart */}
                  <div>
                    <h3 className="text-sm font-semibold text-gray-700 mb-3">Tasks Completed per Week</h3>
                    <div className="flex items-end gap-2 h-32">
                      {trends.data.map(week => {
                        const maxValue = Math.max(...trends.data.map(w => w.todos_completed), 1);
                        const height = (week.todos_completed / maxValue) * 100;
                        return (
                          <div key={week.week_start} className="flex-1 flex flex-col items-center">
                            <div className="w-full bg-blue-500 rounded-t hover:bg-blue-600 transition-colors" style={{ height: `${height}%` }} title={`${week.todos_completed} tasks`} />
                            <div className="text-xs text-gray-600 mt-2 whitespace-nowrap" style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)' }}>
                              {week.week_label.split(' of ')[1]}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {/* Goals Progressed Chart */}
                  <div>
                    <h3 className="text-sm font-semibold text-gray-700 mb-3">Goals Progressed per Week</h3>
                    <div className="flex items-end gap-2 h-32">
                      {trends.data.map(week => {
                        const maxValue = Math.max(...trends.data.map(w => w.goals_progressed), 1);
                        const height = (week.goals_progressed / maxValue) * 100;
                        return (
                          <div key={week.week_start} className="flex-1 flex flex-col items-center">
                            <div className="w-full bg-green-500 rounded-t hover:bg-green-600 transition-colors" style={{ height: `${height}%` }} title={`${week.goals_progressed} goals`} />
                            <div className="text-xs text-gray-600 mt-2 whitespace-nowrap" style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)' }}>
                              {week.week_label.split(' of ')[1]}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {/* Confidence Trend */}
                  <div>
                    <h3 className="text-sm font-semibold text-gray-700 mb-3">Average Goal Confidence</h3>
                    <div className="flex items-end gap-2 h-32">
                      {trends.data.map(week => {
                        const height = week.avg_confidence * 100;
                        return (
                          <div key={week.week_start} className="flex-1 flex flex-col items-center">
                            <div className="w-full bg-purple-500 rounded-t hover:bg-purple-600 transition-colors" style={{ height: `${height}%` }} title={`${(week.avg_confidence * 100).toFixed(0)}% confidence`} />
                            <div className="text-xs text-gray-600 mt-2 whitespace-nowrap" style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)' }}>
                              {week.week_label.split(' of ')[1]}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
