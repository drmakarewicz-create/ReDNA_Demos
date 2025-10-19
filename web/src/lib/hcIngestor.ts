/**
 * Unified Core Ingestion Client for Northstar
 *
 * All user-origin data (onboarding, goals, chat, preferences, uploads) flows through
 * this single ingestion path to ensure consistent Core → UCN/RR → Core roundtrip.
 *
 * Architecture:
 * 1. Northstar collects user input
 * 2. Format as structured payload
 * 3. POST to Core ingestion endpoint
 * 4. Core logs provenance, routes to UCN/RR for scoring
 * 5. Core stores normalized traits
 * 6. Core returns updated snapshot bundle
 * 7. Northstar refreshes from snapshot
 *
 * NO direct trait writes. NO bypass APIs.
 */

import { CORE_API_BASE } from './api';

type NoticeTone = 'success' | 'info' | 'warning' | 'error';
type PushNoticeFn = (message: string, tone?: NoticeTone) => void;

interface IngestionError extends Error {
  status?: number;
  shouldQueue?: boolean;
}

function pushNotice(message: string, tone: NoticeTone = 'info'): void {
  if (typeof window !== 'undefined') {
    const fn = (window as typeof window & { __northstar_push_notice__?: PushNoticeFn })
      .__northstar_push_notice__;
    if (typeof fn === 'function') {
      fn(message, tone);
      return;
    }
  }
  console.debug(`[Northstar Notice][${tone}] ${message}`);
}

export interface IngestionPayload {
  user_id: string;
  text: string;
  source: string;
  metadata?: Record<string, any>;
}

export interface IngestionResponse {
  success: boolean;
  message?: string;
  snapshot?: any;
  error?: string;
}

/**
 * Ingest user-origin data through Core pipeline.
 *
 * @param userId - User identifier
 * @param payload - Natural language or structured text describing the data
 * @param source - Provenance tag: "onboarding", "goal", "chat", "preference", "upload"
 * @param metadata - Optional structured metadata for additional context
 * @returns Core's response including updated snapshot
 *
 * @example
 * ```typescript
 * // Onboarding
 * await ingestToCore(user.id, "[onboarding]\nName: Jackie\nAge: 47", "onboarding");
 *
 * // Goal
 * await ingestToCore(user.id, "[goal]\nGoal: Lose 15 lbs by January 15", "goal");
 *
 * // Chat message with fact
 * await ingestToCore(user.id, "I have brown eyes and prefer coffee", "chat");
 * ```
 */
export async function ingestToCore(
  userId: string,
  payload: string,
  source: string,
  metadata?: Record<string, any>
): Promise<IngestionResponse> {
  // Safeguard: Check if Core bypass is disabled
  const bypassAllowed = typeof process !== 'undefined'
    ? process.env.NEXT_PUBLIC_CORE_BYPASS_ALLOWED !== 'false'
    : true;
  if (!bypassAllowed) {
    console.warn(
      '[Northstar] Direct trait writes are disabled. All data must flow through Core ingestion.'
    );
  }

  // Log ingestion attempt (no sensitive values)
  console.log(`[Northstar Ingestion] source=${source} length=${payload.length} user=${userId}`);

  try {
    const evidenceEntry: Record<string, unknown> = {
      trait_id: 'FreeText',
      value: { text: payload },
      source: source || 'ui',
    };

    if (metadata) {
      evidenceEntry.metadata = metadata;
    }

    const requestPayload = {
      user_id: userId,
      source,
      evidence: [evidenceEntry],
    };

    console.debug(
      '[Northstar Ingestion] POST',
      `${CORE_API_BASE}/core/api/ingest_evidence`,
      {
        userId,
        source,
        count: requestPayload.evidence?.length ?? 0,
        sample: requestPayload.evidence?.slice(0, 1),
      }
    );

    const response = await fetch(`${CORE_API_BASE}/core/api/ingest_evidence`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(requestPayload),
    });

    const contentType = response.headers.get('content-type') ?? '';
    const isJson = contentType.includes('application/json');
    const body = isJson ? await response.json() : undefined;

    if (!response.ok) {
      const reason =
        body && typeof body === 'object' && body !== null && 'error' in body && typeof body.error === 'string'
          ? (body.error as string)
          : response.statusText || 'Unknown error';

      console.error('[Northstar Ingestion] HTTP error', response.status, reason, body);

      if (response.status >= 500) {
        pushNotice('Coach ingestion error (server). Check logs.', 'error');
        const error = new Error(`Core ingestion failed: ${reason}`) as IngestionError;
        error.status = response.status;
        error.shouldQueue = false;
        throw error;
      }

      if (response.status === 400) {
        const badCount = Array.isArray((body as { bad?: unknown })?.bad)
          ? ((body as { bad?: unknown[] }).bad?.length ?? 0)
          : 0;
        const suffix = badCount > 0 ? ` (${badCount} invalid items)` : '';
        pushNotice(`Coach rejected data${suffix}. Please try rephrasing.`, 'warning');
        const error = new Error(`Core validation failed: ${reason}`) as IngestionError;
        error.status = response.status;
        error.shouldQueue = false;
        throw error;
      }

      const error = new Error(`Core ingestion failed: ${reason}`) as IngestionError;
      error.status = response.status;
      throw error;
    }

    const raw = (body ?? {}) as Record<string, unknown>;
    const shaped = raw as {
      success?: boolean;
      ok?: boolean;
      message?: string;
      snapshot?: unknown;
      error?: string;
    };
    const result: IngestionResponse = {
      success: Boolean(shaped.success ?? shaped.ok),
      message: shaped.message,
      snapshot: shaped.snapshot,
      error: shaped.error,
    };

    console.log(`[Northstar Ingestion] Success: ${result.message || 'OK'}`);

    return result;
  } catch (error) {
    console.error('[Northstar Ingestion] Error:', error);

    const shouldQueue =
      !(error instanceof Error) || (error as IngestionError).shouldQueue !== false;
    if (shouldQueue) {
      // If Core is offline, queue locally (simple in-memory for now)
      // Future: implement persistent queue
      queueForRetry({ user_id: userId, text: payload, source, metadata });
    }

    return {
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

/**
 * Format onboarding data as natural language payload.
 */
export function formatOnboardingPayload(data: Record<string, any>): string {
  const lines = ['[onboarding]'];

  if (data.name) lines.push(`Name: ${data.name}`);
  if (data.age) lines.push(`Age: ${data.age}`);
  if (data.orientation) lines.push(`Orientation: ${data.orientation}`);
  if (data.wyrdChoice) lines.push(`Would you rather: ${data.wyrdChoice}`);

  // Add any additional fields
  Object.entries(data).forEach(([key, value]) => {
    if (!['name', 'age', 'orientation', 'wyrdChoice'].includes(key) && value) {
      lines.push(`${key}: ${value}`);
    }
  });

  return lines.join('\n');
}

/**
 * Format goal data as structured payload.
 */
export function formatGoalPayload(goal: {
  title: string;
  targetDate?: string;
  description?: string;
}): string {
  const lines = ['[goal]'];
  lines.push(`Goal: ${goal.title}`);

  if (goal.targetDate) {
    lines.push(`Target Date: ${goal.targetDate}`);
  }

  if (goal.description) {
    lines.push(`Description: ${goal.description}`);
  }

  return lines.join('\n');
}

/**
 * Simple in-memory queue for offline ingestion.
 * Future: implement persistent queue with IndexedDB or similar.
 */
const ingestionQueue: IngestionPayload[] = [];
const MAX_RETRY = 5;

function queueForRetry(payload: IngestionPayload): void {
  if (ingestionQueue.length >= MAX_RETRY) {
    console.warn('[Northstar] Pausing retries after many failures. Queue size:', ingestionQueue.length);
    pushNotice('Pausing coach ingestion retries after repeated failures.', 'warning');
    return;
  }

  ingestionQueue.push(payload);
  console.warn(`[Northstar] Core offline. Queued payload (queue size: ${ingestionQueue.length})`);

  // Attempt retry after 5 seconds
  setTimeout(() => retryQueue(), 5000);
}

async function retryQueue(): Promise<void> {
  if (ingestionQueue.length === 0) return;

  console.log(`[Northstar] Retrying queued ingestions (${ingestionQueue.length} items)`);

  while (ingestionQueue.length > 0) {
    const payload = ingestionQueue[0];

    try {
      const result = await ingestToCore(
        payload.user_id,
        payload.text,
        payload.source,
        payload.metadata
      );

      if (result.success) {
        // Success, remove from queue
        ingestionQueue.shift();
      } else {
        // Still failing, stop retrying for now
        break;
      }
    } catch {
      // Still failing, stop retrying
      break;
    }
  }
}

/**
 * Get queue status for debugging.
 */
export function getQueueStatus(): { pending: number; items: IngestionPayload[] } {
  return {
    pending: ingestionQueue.length,
    items: [...ingestionQueue],
  };
}
