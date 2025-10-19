/**
 * Narrator API Client
 *
 * Provides access to Head Coach Narrator traces - transparent reasoning
 * about HC decision-making (coach switches, tone shifts, curiosity, Codex).
 *
 * Benchmark: 4.A2 - Narrator Mode
 */

import { CORE_API_BASE } from './env';

const API_BASE = CORE_API_BASE;

export interface NarratorTrace {
  ts: string;
  user_id: string;
  context_version: number;
  decision: string;
  reasoning: string[];
  confidence: number;
  impact: 'low' | 'medium' | 'high';
  duration_ms: number;
  session_id?: string;
  metadata?: {
    type?: string;
    from_coach?: string;
    to_coach?: string;
    tone_change?: string;
    trait_container?: string;
    priority?: number;
    action?: string;
    target_coach?: string;
  };
}

export interface NarratorNarrative {
  user_id: string;
  total_traces: number;
  sessions: Record<string, NarratorTrace[]>;
  session_count: number;
  avg_confidence: number;
  decision_types: Record<string, number>;
  latest_trace: NarratorTrace | null;
}

export interface NarratorResponse {
  ok: boolean;
  traces: NarratorTrace[];
  narrative: NarratorNarrative;
  duration_ms: number;
}

export interface AnnotatePayload {
  user_id: string;
  trace_ts: string;
  annotation: string;
  annotator: string;
}

export interface AnnotationResponse {
  ok: boolean;
  annotation: {
    ts: string;
    user_id: string;
    trace_ts: string;
    annotation: string;
    annotator: string;
  };
}

/**
 * Fetch narrator traces for a user
 */
function is404OrEmpty(error: Error): boolean {
  return error.message.includes('404') || error.message.includes('not found')
}

export async function fetchNarratorTraces(
  userId: string,
  options: {
    limit?: number;
    decisionType?: string;
    sessionId?: string;
    minConfidence?: number;
  } = {}
): Promise<NarratorResponse | null> {
  const params = new URLSearchParams({
    user_id: userId,
    limit: String(options.limit ?? 20),
  });

  if (options.decisionType) {
    params.append('decision_type', options.decisionType);
  }
  if (options.sessionId) {
    params.append('session_id', options.sessionId);
  }
  if (options.minConfidence !== undefined) {
    params.append('min_confidence', String(options.minConfidence));
  }

  try {
    const response = await fetch(`${API_BASE}/coach/narrator?${params}`);
    if (!response.ok) {
      if (response.status === 404) {
        return null
      }
      throw new Error(`Failed to fetch narrator traces: ${response.statusText}`);
    }

    return response.json();
  } catch (err) {
    if (err instanceof Error && is404OrEmpty(err)) {
      return null
    }
    throw err
  }
}

/**
 * Add annotation to a specific trace
 */
export async function annotateTrace(
  payload: AnnotatePayload
): Promise<AnnotationResponse> {
  const response = await fetch(`${API_BASE}/coach/narrator/annotate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Failed to annotate trace: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Export narrator traces
 */
export async function exportNarrative(
  userId: string,
  format: 'json' | 'markdown' = 'json',
  options: {
    limit?: number;
    sessionId?: string;
  } = {}
): Promise<string | object> {
  const params = new URLSearchParams({
    user_id: userId,
    format,
    limit: String(options.limit ?? 100),
  });

  if (options.sessionId) {
    params.append('session_id', options.sessionId);
  }

  const response = await fetch(`${API_BASE}/coach/narrator/export?${params}`);
  if (!response.ok) {
    throw new Error(`Failed to export narrative: ${response.statusText}`);
  }

  if (format === 'markdown') {
    return response.text();
  } else {
    return response.json();
  }
}
