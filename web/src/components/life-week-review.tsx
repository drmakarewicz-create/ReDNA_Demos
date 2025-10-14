/**
 * Life OS Week in Review Component
 * Phase 4: Chat right rail card with narrator summary + insights
 */

'use client';

import { useState, useEffect } from 'react';
import { CORE_API_BASE } from '../lib/api';

// ============================================================================
// Types
// ============================================================================

interface WeekInsights {
  todays_three_success_rate: number;
  current_streak: number;
  todos_completed: number;
  top_tags: [string, number][];
  quadrant_share: {
    IU?: number;
    IN?: number;
    NU?: number;
    NN?: number;
  };
  goals_at_risk: any[];
  projects_at_risk: any[];
}

interface WeekReviewData {
  insights: WeekInsights;
  narrator_summary: string;
  audio_url?: string;  // Optional voice summary
  week_label: string;
}

interface LifeWeekReviewProps {
  userId: string;
  collapsed?: boolean;
}

// ============================================================================
// Helper Functions
// ============================================================================

function formatPercentage(value: number): string {
  return `${(value * 100).toFixed(0)}%`;
}

function getStreakEmoji(streak: number): string {
  if (streak >= 7) return '🔥🔥🔥';
  if (streak >= 3) return '🔥🔥';
  if (streak >= 1) return '🔥';
  return '💤';
}

function getQuadrantColor(quadrant: string): string {
  const colors: Record<string, string> = {
    IU: 'bg-red-500',
    IN: 'bg-blue-500',
    NU: 'bg-yellow-500',
    NN: 'bg-gray-400'
  };
  return colors[quadrant] || 'bg-gray-400';
}

// ============================================================================
// Main Component
// ============================================================================

export function LifeWeekReview({ userId, collapsed = false }: LifeWeekReviewProps) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reviewData, setReviewData] = useState<WeekReviewData | null>(null);
  const [playingAudio, setPlayingAudio] = useState(false);
  const [audioElement, setAudioElement] = useState<HTMLAudioElement | null>(null);

  useEffect(() => {
    loadWeekReview();
  }, [userId]);

  // Cleanup audio on unmount
  useEffect(() => {
    return () => {
      if (audioElement) {
        audioElement.pause();
        audioElement.src = '';
      }
    };
  }, [audioElement]);

  async function loadWeekReview() {
    setLoading(true);
    setError(null);

    try {
      // Fetch 7-day insights
      const insightsResponse = await fetch(`${CORE_API_BASE}/ui/hc/life/${userId}/insights?days=7`);
      if (!insightsResponse.ok) {
        throw new Error(`Failed to fetch insights: ${insightsResponse.status}`);
      }
      const insights = await insightsResponse.json();

      // Generate narrator summary
      const narratorResponse = await fetch(`${CORE_API_BASE}/coach/narrator?user_id=${userId}&type=life_weekly`);
      let narratorSummary = '';

      if (narratorResponse.ok) {
        const narratorData = await narratorResponse.json();
        narratorSummary = narratorData.summary || buildFallbackSummary(insights);
      } else {
        // Fallback: build from insights directly
        narratorSummary = buildFallbackSummary(insights);
      }

      // Check for audio (optional)
      const today = new Date();
      const weekNum = getWeekNumber(today);
      const year = today.getFullYear();
      const audioUrl = `${CORE_API_BASE}/ui/hc/life/${userId}/voice_summary?week=${year}-W${weekNum.toString().padStart(2, '0')}`;

      setReviewData({
        insights,
        narrator_summary: narratorSummary,
        audio_url: undefined,  // Audio endpoint not yet implemented
        week_label: `Week of ${getMonday(today).toLocaleDateString()}`
      });
    } catch (err: any) {
      setError(err.message || 'Failed to load week review');
    } finally {
      setLoading(false);
    }
  }

  function buildFallbackSummary(insights: WeekInsights): string {
    const parts: string[] = [];

    if (insights.todos_completed > 0) {
      parts.push(`You completed ${insights.todos_completed} tasks this week`);
    }

    if (insights.current_streak > 0) {
      parts.push(`maintained a ${insights.current_streak}-day streak`);
    }

    if (insights.top_tags && insights.top_tags.length > 0) {
      const topTag = insights.top_tags[0][0];
      parts.push(`focused on ${topTag}`);
    }

    if (parts.length === 0) {
      return 'No activity this week. Want to set some goals for the week ahead?';
    }

    let summary = parts.join(', ') + '.';

    // Add at-risk prompt
    const atRiskCount = (insights.goals_at_risk?.length || 0) + (insights.projects_at_risk?.length || 0);
    if (atRiskCount > 0) {
      const itemText = atRiskCount === 1 ? 'item needs' : 'items need';
      summary += ` ${atRiskCount} ${itemText} attention—want to plan next steps?`;
    }

    return summary;
  }

  function getMonday(date: Date): Date {
    const d = new Date(date);
    const day = d.getDay();
    const diff = d.getDate() - day + (day === 0 ? -6 : 1); // Adjust when day is Sunday
    return new Date(d.setDate(diff));
  }

  function getWeekNumber(date: Date): number {
    const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
    const dayNum = d.getUTCDay() || 7;
    d.setUTCDate(d.getUTCDate() + 4 - dayNum);
    const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
    return Math.ceil((((d.getTime() - yearStart.getTime()) / 86400000) + 1) / 7);
  }

  async function handlePlayAudio() {
    if (!reviewData?.audio_url) return;

    if (playingAudio && audioElement) {
      audioElement.pause();
      setPlayingAudio(false);
      return;
    }

    const audio = new Audio(reviewData.audio_url);
    audio.onended = () => setPlayingAudio(false);
    audio.onerror = () => {
      setError('Failed to play audio');
      setPlayingAudio(false);
    };

    setAudioElement(audio);
    audio.play();
    setPlayingAudio(true);
  }

  // Empty state check
  const hasEnoughData = reviewData && reviewData.insights.todos_completed > 0;

  if (collapsed) {
    return null;
  }

  return (
    <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-lg border border-blue-200 p-4 mb-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-2xl">📊</span>
          <div>
            <h3 className="text-sm font-semibold text-gray-900">Week in Review</h3>
            <p className="text-xs text-gray-600">{reviewData?.week_label || 'This week'}</p>
          </div>
        </div>
        <a
          href={`http://localhost:8100/life-dashboard`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-blue-600 hover:text-blue-800 font-medium"
        >
          DevX →
        </a>
      </div>

      {/* Loading State */}
      {loading && (
        <div className="text-center py-6">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto mb-2"></div>
          <p className="text-xs text-gray-600">Loading your week...</p>
        </div>
      )}

      {/* Error State */}
      {error && !loading && (
        <div className="bg-red-50 border border-red-200 rounded p-3">
          <p className="text-xs text-red-800">Failed to load week review</p>
          <button
            onClick={loadWeekReview}
            className="mt-2 text-xs text-red-600 hover:text-red-800 font-medium"
          >
            Retry
          </button>
        </div>
      )}

      {/* Empty State */}
      {!loading && !error && !hasEnoughData && (
        <div className="text-center py-4">
          <p className="text-sm text-gray-700 mb-1">📝 No activity yet</p>
          <p className="text-xs text-gray-500">
            Complete a few tasks to unlock your weekly summary.
          </p>
        </div>
      )}

      {/* Content */}
      {!loading && !error && hasEnoughData && reviewData && (
        <div className="space-y-3">
          {/* KPI Mini-Cards */}
          <div className="grid grid-cols-3 gap-2">
            {/* Streak */}
            <div className="bg-white rounded p-2 text-center">
              <div className="text-lg">{getStreakEmoji(reviewData.insights.current_streak)}</div>
              <div className="text-xs font-bold text-gray-900">{reviewData.insights.current_streak}d</div>
              <div className="text-[10px] text-gray-500">Streak</div>
            </div>

            {/* Success Rate */}
            <div className="bg-white rounded p-2 text-center">
              <div className="text-lg">✅</div>
              <div className="text-xs font-bold text-gray-900">
                {formatPercentage(reviewData.insights.todays_three_success_rate)}
              </div>
              <div className="text-[10px] text-gray-500">Success</div>
            </div>

            {/* Completed */}
            <div className="bg-white rounded p-2 text-center">
              <div className="text-lg">📋</div>
              <div className="text-xs font-bold text-gray-900">{reviewData.insights.todos_completed}</div>
              <div className="text-[10px] text-gray-500">Tasks</div>
            </div>
          </div>

          {/* Top Tag */}
          {reviewData.insights.top_tags && reviewData.insights.top_tags.length > 0 && (
            <div className="bg-white rounded p-2">
              <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Top Focus</p>
              <p className="text-xs font-medium text-gray-900">
                🏷️ {reviewData.insights.top_tags[0][0]} ({reviewData.insights.top_tags[0][1]})
              </p>
            </div>
          )}

          {/* Quadrant Balance Mini-Bars */}
          <div className="bg-white rounded p-2">
            <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Quadrant Balance</p>
            <div className="space-y-1">
              {(['IU', 'IN', 'NU', 'NN'] as const).map((q) => {
                const value = reviewData.insights.quadrant_share[q] || 0;
                const labels = {
                  IU: 'Important & Urgent',
                  IN: 'Important & Not Urgent',
                  NU: 'Not Important & Urgent',
                  NN: 'Neither'
                };
                return (
                  <div key={q} className="flex items-center gap-2">
                    <span className="text-[10px] font-medium text-gray-600 w-5">{q}</span>
                    <div className="flex-1 bg-gray-100 rounded-full h-1.5">
                      <div
                        className={`h-1.5 rounded-full ${getQuadrantColor(q)}`}
                        style={{ width: `${value * 100}%` }}
                      />
                    </div>
                    <span className="text-[10px] text-gray-500 w-8 text-right">
                      {formatPercentage(value)}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Narrator Summary */}
          <div className="bg-white rounded p-3">
            <p className="text-xs text-gray-700 leading-relaxed">{reviewData.narrator_summary}</p>
          </div>

          {/* Audio Player (Optional) */}
          {reviewData.audio_url && (
            <button
              onClick={handlePlayAudio}
              className="w-full bg-blue-600 hover:bg-blue-700 text-white rounded py-2 px-3 text-xs font-medium flex items-center justify-center gap-2"
            >
              {playingAudio ? '⏸' : '▶️'} {playingAudio ? 'Pause' : 'Listen'}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
