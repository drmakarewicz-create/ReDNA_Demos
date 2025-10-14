/**
 * Learning API Client
 * ===================
 *
 * TypeScript client for Self-Improvement learning backend API.
 */

const API_BASE = '/learning';

export interface Report {
  generated_at: string;
  telemetry_files_analyzed: number;
  total_entries: number;
  coaches: Record<string, CoachMetrics>;
  processing_time_ms: number;
  malformed_lines_skipped: number;
  defaults_injected: number;
  files_cleaned: number;
}

export interface CoachMetrics {
  entries_analyzed: number;
  avg_confidence?: number;
  sentiment_avg?: number;
  drift_detected?: boolean;
  patterns?: string[];
}

export interface Suggestion {
  suggestion_id: string;
  coach_id: string;
  confidence: number;
  suggested_change: string;
  evidence_count: number;
  evidence_samples: string[];
  rationale: string;
  sentiment_impact?: number;
  drift_magnitude?: number;
  estimated_improvement?: number;
}

export interface ApplyPayload {
  coach_id: string;
  suggestion_id: string;
  action: 'approve' | 'reject';
  user: string;
  reason?: string;
}

export interface ApplyResult {
  ok: boolean;
  action: string;
  backup_path?: string;
  old_hash?: string;
  new_hash?: string;
  message: string;
}

export interface HistoryEntry {
  timestamp: string;
  coach_id: string;
  suggestion_id: string;
  action: 'approve' | 'reject';
  confidence: number;
  user: string;
  reason?: string;
  old_hash?: string;
  new_hash?: string;
  backup_path?: string;
}

export interface Stats {
  total_suggestions: number;
  auto_eligible: number;
  needs_review: number;
  approved_count: number;
  rejected_count: number;
  coaches: Record<string, {
    suggestions: number;
    approved: number;
    rejected: number;
    avg_confidence: number;
  }>;
}

/**
 * Coerce confidence to a band label.
 */
export function coerceConfidenceBand(conf: number): 'auto' | 'review' | 'low' {
  if (conf >= 0.85) return 'auto';
  if (conf >= 0.70) return 'review';
  return 'low';
}

class LearningClient {
  /**
   * Trigger full telemetry analysis.
   */
  async runAnalysis(): Promise<Report> {
    const response = await fetch(`${API_BASE}/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: 'system' })
    });
    if (!response.ok) throw new Error(`Failed to run analysis: ${response.statusText}`);
    return response.json();
  }

  /**
   * Get latest analysis report.
   */
  async getReport(): Promise<Report> {
    const response = await fetch(`${API_BASE}/report`);
    if (!response.ok) throw new Error(`Failed to get report: ${response.statusText}`);
    return response.json();
  }

  /**
   * Get suggestions for a specific coach.
   */
  async getSuggestions(coachId: string): Promise<Suggestion[]> {
    const response = await fetch(`${API_BASE}/suggestions/${encodeURIComponent(coachId)}`);
    if (!response.ok) throw new Error(`Failed to get suggestions: ${response.statusText}`);
    const data = await response.json();
    return data.suggestions || [];
  }

  /**
   * Apply (approve/reject) a suggestion.
   */
  async applySuggestion(payload: ApplyPayload): Promise<ApplyResult> {
    const response = await fetch(`${API_BASE}/apply-suggestion`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!response.ok) throw new Error(`Failed to apply suggestion: ${response.statusText}`);
    return response.json();
  }

  /**
   * Get approval/rejection history.
   */
  async getHistory(params?: { coach_id?: string; limit?: number }): Promise<HistoryEntry[]> {
    const searchParams = new URLSearchParams();
    if (params?.coach_id) searchParams.append('coach_id', params.coach_id);
    if (params?.limit) searchParams.append('limit', params.limit.toString());

    const url = searchParams.toString()
      ? `${API_BASE}/history?${searchParams}`
      : `${API_BASE}/history`;

    const response = await fetch(url);
    if (!response.ok) throw new Error(`Failed to get history: ${response.statusText}`);
    const data = await response.json();
    return data.history || [];
  }

  /**
   * Get aggregated stats across all coaches.
   */
  async getStats(): Promise<Stats> {
    const response = await fetch(`${API_BASE}/stats`);
    if (!response.ok) throw new Error(`Failed to get stats: ${response.statusText}`);
    return response.json();
  }
}

export const learningApi = new LearningClient();
