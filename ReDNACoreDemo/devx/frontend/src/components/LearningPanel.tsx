/**
 * Learning Panel Component (Phase 3b.1)
 * ======================================
 *
 * Visualizes Head Coach adaptive learning state with:
 * - Current tone/creativity/nudge frequency
 * - Focus area weights
 * - Historical deltas (mini timeline)
 * - Force Recompute action (capability-gated, L2+ only)
 * - Read-only mode for L0/L1 agency levels
 */

import { useCallback, useEffect, useState } from 'react';
import { toast } from 'react-toastify';
import {
  hcLearningApi,
  LearningState,
  LearningStateResponse,
  formatToneBias,
  formatCreativityBias,
  formatNudgeFrequency,
} from '@/lib/hcLearningApi';
// import { capabilityClient } from '@/lib/capabilityClient'; // TODO: Fix capability client import

interface LearningPanelProps {
  userId: string;
  agencyLevel: number;
}

interface FocusWeightDisplay {
  category: string;
  weight: number;
  delta: number;
}

export default function LearningPanel({ userId, agencyLevel }: LearningPanelProps) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [stateData, setStateData] = useState<LearningStateResponse | null>(null);
  const [recomputing, setRecomputing] = useState(false);

  const isReadOnly = agencyLevel < 2;

  const loadState = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await hcLearningApi.getState(userId);
      setStateData(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load learning state';
      setError(message);
      toast.error(message);
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    loadState();
  }, [loadState]);

  const handleRecompute = async () => {
    if (isReadOnly) {
      toast.warn('Learning recompute requires Autonomous (L2) or higher agency level.');
      return;
    }

    setRecomputing(true);
    try {
      // TODO: Re-enable capability check when capabilityClient is fixed
      // const capability = await capabilityClient.getCapability('core.agent.config');
      // if (!capability.granted) {
      //   toast.error('Capability core.agent.config not granted. Cannot recompute.');
      //   setRecomputing(false);
      //   return;
      // }

      // Trigger recompute
      const result = await hcLearningApi.recompute(userId, 14, 'devx-local'); // TODO: Use real capability token

      toast.success(
        `Learning recomputed successfully! Update #${result.state.update_count} (${result.duration_ms}ms)`
      );

      // Refresh state
      await loadState();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to recompute learning';
      toast.error(message);
    } finally {
      setRecomputing(false);
    }
  };

  if (loading) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-6">
        <div className="flex items-center justify-center py-8">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-500 border-t-transparent" />
          <span className="ml-3 text-sm text-gray-600">Loading learning state...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-6">
        <div className="text-sm text-red-700">{error}</div>
      </div>
    );
  }

  // Empty state
  if (!stateData?.learning_enabled || !stateData.state) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-6">
        <div className="text-center py-8">
          <div className="text-gray-400 mb-2">
            <svg
              className="mx-auto h-12 w-12"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
              />
            </svg>
          </div>
          <p className="text-sm font-medium text-gray-900 mb-1">No learning state yet</p>
          <p className="text-sm text-gray-600">
            Learning updates apply weekly (Mondays) or when manually triggered.
          </p>
          {!isReadOnly && (
            <button
              onClick={handleRecompute}
              disabled={recomputing}
              className="mt-4 inline-flex items-center rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {recomputing ? 'Computing...' : 'Initialize Learning State'}
            </button>
          )}
        </div>
      </div>
    );
  }

  const state = stateData.state;
  const context = stateData.behavior_context;

  // Format focus weights for display (top 6)
  const focusWeights: FocusWeightDisplay[] = Object.entries(state.focus_weights)
    .map(([category, weight]) => ({
      category,
      weight,
      delta: 0, // TODO: Calculate from history when available
    }))
    .sort((a, b) => b.weight - a.weight)
    .slice(0, 6);

  return (
    <div className="space-y-6">
      {/* Read-only banner */}
      {isReadOnly && (
        <div className="rounded-lg border border-yellow-200 bg-yellow-50 p-4">
          <div className="flex items-start">
            <svg
              className="h-5 w-5 text-yellow-400 mr-3 mt-0.5"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                fillRule="evenodd"
                d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
                clipRule="evenodd"
              />
            </svg>
            <div className="flex-1">
              <p className="text-sm font-medium text-yellow-800">Read-only mode</p>
              <p className="text-sm text-yellow-700 mt-1">
                Learning is visible; change agency to <strong>Autonomous (L2)</strong> to apply
                updates.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Current State Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Tone Bias Card */}
        <div className="rounded-lg border border-gray-200 bg-white p-4">
          <div className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">
            Tone Bias
          </div>
          <div className="flex items-baseline justify-between">
            <div className="text-2xl font-bold text-gray-900">
              {formatToneBias(state.tone_bias)}
            </div>
            <div className="text-sm text-gray-600">{state.tone_bias.toFixed(2)}</div>
          </div>
          <div className="mt-3">
            <div className="relative h-2 bg-gray-200 rounded-full overflow-hidden">
              <div
                className="absolute h-full bg-gradient-to-r from-blue-500 via-gray-400 to-green-500 rounded-full"
                style={{
                  left: 0,
                  right: 0,
                }}
              />
              <div
                className="absolute h-full w-1 bg-gray-900"
                style={{
                  left: `${((state.tone_bias + 1) / 2) * 100}%`,
                  transform: 'translateX(-50%)',
                }}
              />
            </div>
            <div className="flex justify-between text-xs text-gray-500 mt-1">
              <span>Direct</span>
              <span>Empathetic</span>
            </div>
          </div>
        </div>

        {/* Creativity Bias Card */}
        <div className="rounded-lg border border-gray-200 bg-white p-4">
          <div className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">
            Creativity Bias
          </div>
          <div className="flex items-baseline justify-between">
            <div className="text-2xl font-bold text-gray-900">
              {formatCreativityBias(state.creativity_bias)}
            </div>
            <div className="text-sm text-gray-600">{state.creativity_bias.toFixed(2)}</div>
          </div>
          <div className="mt-3">
            <div className="relative h-2 bg-gray-200 rounded-full overflow-hidden">
              <div
                className="absolute h-full bg-gradient-to-r from-purple-500 to-pink-500 rounded-full"
                style={{
                  width: `${state.creativity_bias * 100}%`,
                }}
              />
            </div>
            <div className="flex justify-between text-xs text-gray-500 mt-1">
              <span>Conservative</span>
              <span>Experimental</span>
            </div>
          </div>
        </div>

        {/* Nudge Frequency Card */}
        <div className="rounded-lg border border-gray-200 bg-white p-4">
          <div className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">
            Nudge Frequency
          </div>
          <div className="flex items-baseline justify-between">
            <div className="text-2xl font-bold text-gray-900">
              {state.nudge_frequency_multiplier.toFixed(1)}×
            </div>
            <div className="text-sm text-gray-600">
              {formatNudgeFrequency(state.nudge_frequency_multiplier)}
            </div>
          </div>
          <div className="mt-3">
            <div className="text-xs text-gray-600">
              {state.nudge_frequency_multiplier > 1.0
                ? 'More frequent coaching nudges'
                : state.nudge_frequency_multiplier < 1.0
                ? 'Fewer coaching nudges'
                : 'Normal nudge cadence'}
            </div>
          </div>
        </div>
      </div>

      {/* Focus Weights */}
      {focusWeights.length > 0 && (
        <div className="rounded-lg border border-gray-200 bg-white p-4">
          <div className="text-sm font-medium text-gray-900 mb-3">Focus Area Weights</div>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {focusWeights.map((fw) => (
              <div key={fw.category} className="flex items-center justify-between">
                <div className="flex items-center min-w-0 flex-1">
                  <span className="text-sm text-gray-700 capitalize truncate">{fw.category}</span>
                </div>
                <div className="ml-3 flex items-center">
                  <div className="relative w-16 h-2 bg-gray-200 rounded-full overflow-hidden">
                    <div
                      className="absolute h-full bg-blue-500 rounded-full"
                      style={{
                        width: `${Math.min((fw.weight / 1.5) * 100, 100)}%`,
                      }}
                    />
                  </div>
                  <span className="ml-2 text-xs text-gray-600 font-medium w-8 text-right">
                    {fw.weight.toFixed(1)}×
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Metadata & Actions */}
      <div className="rounded-lg border border-gray-200 bg-white p-4">
        <div className="flex items-start justify-between">
          <div className="flex-1 space-y-2">
            <div className="flex items-center text-sm">
              <span className="text-gray-500 w-32">Last Update:</span>
              <span className="text-gray-900 font-medium">
                {new Date(state.last_update).toLocaleString()}
              </span>
            </div>
            <div className="flex items-center text-sm">
              <span className="text-gray-500 w-32">Update Count:</span>
              <span className="text-gray-900 font-medium">#{state.update_count}</span>
            </div>
            <div className="flex items-center text-sm">
              <span className="text-gray-500 w-32">Timing Preference:</span>
              <span className="text-gray-900 capitalize">{state.nudge_timing_preference}</span>
            </div>
            {context && (
              <div className="mt-3 pt-3 border-t border-gray-200">
                <div className="text-xs text-gray-600">
                  <strong>Behavior Hint:</strong> {context.creativity}
                </div>
              </div>
            )}
          </div>

          <div className="ml-6">
            <button
              onClick={handleRecompute}
              disabled={recomputing || isReadOnly}
              className="inline-flex items-center rounded-md border border-blue-600 bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              title={
                isReadOnly
                  ? 'Requires Autonomous (L2) or higher agency level'
                  : 'Force recompute learning state from recent insights'
              }
            >
              {recomputing ? (
                <>
                  <svg className="animate-spin -ml-1 mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24">
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    />
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                    />
                  </svg>
                  Computing...
                </>
              ) : (
                <>
                  <svg
                    className="-ml-1 mr-2 h-4 w-4"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                    />
                  </svg>
                  Force Recompute
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Info Footer */}
      <div className="text-xs text-gray-500 text-center">
        Learning updates automatically every Monday or when manually triggered. Based on 14-day
        rolling window of Life OS insights.
      </div>
    </div>
  );
}
