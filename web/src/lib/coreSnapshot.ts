/**
 * Core Snapshot Refresh Pipeline for Northstar
 *
 * Central snapshot management that ensures Northstar always displays
 * the latest Core-normalized data after any ingestion.
 *
 * Flow:
 * 1. User action triggers ingestion via hcIngestor
 * 2. Core processes through UCN/RR pipeline
 * 3. refreshSnapshot() fetches updated data from Core
 * 4. Updates are propagated to all Northstar components
 * 5. UI re-renders with fresh data
 */

import { CORE_API_BASE } from './api';

export interface UserSnapshot {
  user_id: string;
  traits: Record<string, any>;
  dnas: Record<string, any>;
  metrics: {
    confidence?: number;
    curiosity?: number;
    [key: string]: any;
  };
  timestamp: string;
  version: number;
}

export interface SnapshotResponse {
  success: boolean;
  snapshot?: UserSnapshot;
  error?: string;
}

// Global snapshot cache
let currentSnapshot: UserSnapshot | null = null;
let snapshotVersion = 0;
const snapshotListeners: Array<(snapshot: UserSnapshot) => void> = [];

/**
 * Refresh user snapshot from Core.
 *
 * Call this after any ingestion to get the latest Core-normalized data.
 *
 * @param userId - User identifier
 * @param options - Refresh options
 * @returns Updated snapshot from Core
 */
export async function refreshSnapshot(
  userId: string,
  options: {
    silent?: boolean; // Don't show loading indicators
    force?: boolean; // Force refresh even if recent
  } = {}
): Promise<SnapshotResponse> {
  const { silent = false, force = false } = options;

  if (!silent) {
    console.log('[Northstar] Refreshing snapshot from Core...');
  }

  try {
    const response = await fetch(`${CORE_API_BASE}/user/${userId}/snapshot`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch snapshot: ${response.statusText}`);
    }

    const data = await response.json();

    // Update global snapshot
    const newSnapshot: UserSnapshot = {
      ...data,
      version: ++snapshotVersion,
    };

    currentSnapshot = newSnapshot;

    // Notify all listeners
    notifyListeners(newSnapshot);

    if (!silent) {
      console.log(`[Northstar] Snapshot refreshed (v${snapshotVersion})`);
    }

    return {
      success: true,
      snapshot: newSnapshot,
    };
  } catch (error) {
    console.error('[Northstar] Snapshot refresh failed:', error);

    return {
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

/**
 * Get current cached snapshot without fetching from Core.
 */
export function getCurrentSnapshot(): UserSnapshot | null {
  return currentSnapshot;
}

/**
 * Get current snapshot version number.
 * Components can compare against this to detect updates.
 */
export function getSnapshotVersion(): number {
  return snapshotVersion;
}

/**
 * Subscribe to snapshot updates.
 * Callback will be invoked whenever snapshot is refreshed.
 *
 * @param callback - Function to call with updated snapshot
 * @returns Unsubscribe function
 */
export function subscribeToSnapshot(
  callback: (snapshot: UserSnapshot) => void
): () => void {
  snapshotListeners.push(callback);

  // Return unsubscribe function
  return () => {
    const index = snapshotListeners.indexOf(callback);
    if (index > -1) {
      snapshotListeners.splice(index, 1);
    }
  };
}

/**
 * Notify all listeners of snapshot update.
 */
function notifyListeners(snapshot: UserSnapshot): void {
  snapshotListeners.forEach((callback) => {
    try {
      callback(snapshot);
    } catch (error) {
      console.error('[Northstar] Snapshot listener error:', error);
    }
  });
}

/**
 * Clear snapshot cache.
 * Useful for logout or user switch.
 */
export function clearSnapshot(): void {
  currentSnapshot = null;
  snapshotVersion = 0;
  console.log('[Northstar] Snapshot cache cleared');
}

/**
 * Get snapshot metrics for display.
 */
export function getSnapshotMetrics(): {
  confidence: number;
  curiosity: number;
  lastUpdate: string | null;
} {
  if (!currentSnapshot) {
    return {
      confidence: 0,
      curiosity: 0,
      lastUpdate: null,
    };
  }

  return {
    confidence: currentSnapshot.metrics?.confidence || 0,
    curiosity: currentSnapshot.metrics?.curiosity || 0,
    lastUpdate: currentSnapshot.timestamp,
  };
}

/**
 * Helper: Ingest and refresh in one call.
 * Most common pattern for Northstar components.
 */
export async function ingestAndRefresh(
  userId: string,
  payload: string,
  source: string,
  metadata?: Record<string, any>
): Promise<{
  ingestion: any;
  snapshot: SnapshotResponse;
}> {
  // Import dynamically to avoid circular dependency
  const { ingestToCore } = await import('./hcIngestor');

  // Step 1: Ingest to Core
  const ingestionResult = await ingestToCore(userId, payload, source, metadata);

  // Step 2: Refresh snapshot
  const snapshotResult = await refreshSnapshot(userId);

  return {
    ingestion: ingestionResult,
    snapshot: snapshotResult,
  };
}
