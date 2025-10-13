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
  const bypassAllowed = import.meta.env.VITE_CORE_BYPASS_ALLOWED !== 'false';
  if (!bypassAllowed) {
    console.warn(
      '[Northstar] Direct trait writes are disabled. All data must flow through Core ingestion.'
    );
  }

  // Log ingestion attempt (no sensitive values)
  console.log(`[Northstar Ingestion] source=${source} length=${payload.length} user=${userId}`);

  try {
    const response = await fetch(`${CORE_API_BASE}/ingest_text`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        user_id: userId,
        text: payload,
        source,
        metadata,
      }),
    });

    if (!response.ok) {
      throw new Error(`Core ingestion failed: ${response.statusText}`);
    }

    const data: IngestionResponse = await response.json();

    console.log(`[Northstar Ingestion] Success: ${data.message || 'OK'}`);

    return data;
  } catch (error) {
    console.error('[Northstar Ingestion] Error:', error);

    // If Core is offline, queue locally (simple in-memory for now)
    // Future: implement persistent queue
    queueForRetry({ user_id: userId, text: payload, source, metadata });

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

function queueForRetry(payload: IngestionPayload): void {
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
