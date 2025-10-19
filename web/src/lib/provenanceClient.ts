/**
 * Provenance client for trait explainability.
 *
 * Fetches complete provenance information for traits including:
 * - Current resolved value and UCN
 * - Evidence timeline
 * - Inference items
 * - Resolver trace references
 * - RR scoring status
 */

export type Value = {
  enum?: string;
  number?: number;
  text?: string;
};

export type Evidence = {
  source?: string;
  ts?: string;
  value?: Value;
  ucn_prior?: number;
  provenance?: string;
  req_id?: string;
};

export type TraceRef = {
  req_id?: string;
  file?: string;
  rr_ok?: boolean;
};

export type ResolvedState = {
  value?: Value;
  ucn?: number;
  status?: string;
  last_updated?: string;
  sources?: string[];
};

export type Provenance = {
  trait_id: string;
  resolved: ResolvedState;
  direct_evidence: Evidence[];
  inferences: Evidence[];
  traces: TraceRef[];
  rr_status: "ok" | "offline" | "unknown";
};

/**
 * Fetch complete provenance for a trait.
 *
 * @param userId - User identifier
 * @param traitId - Canonical trait ID (e.g., "PaDNA.EyeDNA.IrisColor")
 * @returns Promise resolving to provenance data
 * @throws Error if fetch fails
 */
export async function fetchProvenance(
  userId: string,
  traitId: string
): Promise<Provenance> {
  const url = `/core/api/user/${encodeURIComponent(userId)}/provenance/${encodeURIComponent(traitId)}`;

  const response = await fetch(url);

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(
      error.message || `Provenance fetch failed: ${response.status}`
    );
  }

  return response.json();
}

/**
 * Format a value for display.
 *
 * @param value - Value object
 * @returns Human-readable string
 */
export function formatValue(value?: Value): string {
  if (!value) return "—";
  if (value.enum) return value.enum;
  if (value.number !== undefined) return String(value.number);
  if (value.text) return value.text;
  return "—";
}

/**
 * Format a timestamp for display.
 *
 * @param ts - ISO timestamp
 * @returns Human-readable string
 */
export function formatTimestamp(ts?: string): string {
  if (!ts) return "—";
  try {
    const date = new Date(ts);
    return date.toLocaleString();
  } catch {
    return ts;
  }
}

/**
 * Extract a friendly label from a trait ID.
 *
 * @param traitId - Canonical trait ID
 * @returns Last component of trait ID
 */
export function extractTraitLabel(traitId: string): string {
  const parts = traitId.split(".");
  return parts[parts.length - 1] || traitId;
}
