/**
 * HC Learning API Client (Phase 3b.1)
 * ====================================
 *
 * TypeScript client for Head Coach adaptive learning API.
 * Provides access to learning state, recompute triggers, and historical deltas.
 */

const API_BASE = '/ui/hc/learning';

export interface LearningState {
  nudge_frequency_multiplier: number;
  nudge_timing_preference: string;
  tone_bias: number;
  formality_bias: number;
  creativity_bias: number;
  focus_weights: Record<string, number>;
  last_update: string;
  update_count: number;
  baseline_metrics: Record<string, number>;
  version: string;
  computed_at: string;
}

export interface BehaviorContext {
  learning_enabled: boolean;
  update_count: number;
  last_update: string;
  tone: string;
  timing: string;
  creativity: string;
  focus: string;
  nudge_frequency_multiplier: number;
  raw_state: LearningState;
}

export interface LearningStateResponse {
  ok: boolean;
  state: LearningState | null;
  learning_enabled: boolean;
  behavior_context?: BehaviorContext;
  message?: string;
  duration_ms: number;
}

export interface LearningDeltas {
  nudge_frequency_multiplier: number;
  nudge_timing_preference: string;
  tone_bias: number;
  formality_bias: number;
  creativity_bias: number;
  focus_weights: Record<string, number>;
  insights_snapshot: {
    completion_rate?: number;
    current_streak?: number;
    nudge_acceptance?: number;
    projects_at_risk_count?: number;
    goals_at_risk_count?: number;
  };
  computed_at: string;
}

export interface RecomputeResponse {
  ok: boolean;
  recomputed: boolean;
  state: LearningState;
  deltas: LearningDeltas;
  duration_ms: number;
}

/**
 * Format tone bias to human-readable label.
 */
export function formatToneBias(bias: number): string {
  if (bias > 0.3) return 'Empathetic';
  if (bias < -0.2) return 'Direct';
  return 'Balanced';
}

/**
 * Format creativity bias to human-readable label.
 */
export function formatCreativityBias(bias: number): string {
  if (bias > 0.6) return 'Experimental';
  if (bias < 0.4) return 'Conservative';
  return 'Balanced';
}

/**
 * Format nudge frequency multiplier to description.
 */
export function formatNudgeFrequency(multiplier: number): string {
  if (multiplier >= 1.3) return 'High (more frequent)';
  if (multiplier <= 0.7) return 'Low (less frequent)';
  return 'Normal';
}

/**
 * Calculate delta value with sign.
 */
export function calculateDelta(current: number, previous: number): number {
  return current - previous;
}

/**
 * Format delta with + or - sign and color hint.
 */
export function formatDelta(delta: number, decimals: number = 2): { text: string; color: string } {
  const formatted = delta >= 0 ? `+${delta.toFixed(decimals)}` : delta.toFixed(decimals);
  const color = delta > 0 ? 'text-green-600' : delta < 0 ? 'text-red-600' : 'text-gray-600';
  return { text: formatted, color };
}

class HCLearningClient {
  /**
   * Get current learning state for a user.
   */
  async getState(userId: string): Promise<LearningStateResponse> {
    const response = await fetch(`${API_BASE}/${encodeURIComponent(userId)}/state`);
    if (!response.ok) {
      throw new Error(`Failed to get learning state: ${response.statusText}`);
    }
    return response.json();
  }

  /**
   * Force recompute of learning state (requires capability).
   *
   * @param userId - User identifier
   * @param days - Rolling window for insight computation (default: 14)
   * @param capabilityToken - X-Capability header value (if required)
   */
  async recompute(userId: string, days: number = 14, capabilityToken?: string): Promise<RecomputeResponse> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    if (capabilityToken) {
      headers['X-Capability'] = capabilityToken;
    }

    const response = await fetch(
      `${API_BASE}/${encodeURIComponent(userId)}/recompute?days=${days}`,
      {
        method: 'POST',
        headers,
      }
    );

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Failed to recompute learning: ${response.statusText} - ${errorText}`);
    }

    return response.json();
  }
}

export const hcLearningApi = new HCLearningClient();
