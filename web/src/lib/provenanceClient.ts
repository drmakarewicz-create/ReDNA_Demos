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

export type RRReferenceMeta = {
  source?: string | null;
  universe?: string | null;
  cohort_keys?: string[] | null;
  cohort_values?: Record<string, unknown> | null;
  n_samples?: number | null;
  generated_at?: string | null;
};

export type RRMeta = {
  rr_raw?: number;
  scale?: '0_100' | '0_1000' | 'reference_percentile' | string;
  method?: string | null;
  source?: string | null;
  fallback_reason?: string | null;
  reference?: RRReferenceMeta | null;
};

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function isNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

export function adaptRR(rr?: number | null, rr_meta?: RRMeta | null): number | undefined {
  if (isNumber(rr)) {
    return clamp(rr, 0, 100);
  }
  const raw = rr_meta?.rr_raw;
  if (!isNumber(raw)) {
    return undefined;
  }
  if (rr_meta?.scale === '0_1000') {
    return clamp(raw / 10, 0, 100);
  }
  if (rr_meta?.scale === '0_100' || rr_meta?.scale === 'reference_percentile') {
    return clamp(raw, 0, 100);
  }
  return undefined;
}

export function adaptCuriosity(curiosity?: number | null, rrPct?: number): number | undefined {
  if (isNumber(curiosity)) {
    return clamp(curiosity, 0, 100);
  }
  if (isNumber(rrPct)) {
    return clamp(100 - rrPct, 0, 100);
  }
  return undefined;
}

export function formatPercent(value?: number | null, fractionDigits = 1): string {
  if (!isNumber(value)) {
    return '—';
  }
  return `${value.toFixed(fractionDigits)}%`;
}

export type Provenance = {
  trait_id: string;
  resolved: ResolvedState;
  direct_evidence: Evidence[];
  inferences: Evidence[];
  traces: TraceRef[];
  rr_status: "ok" | "offline" | "unknown";
};

export type WhyCard = {
  id: string;
  user_id: string;
  trait_id: string;
  what: string;
  why: string;
  next: string;
  rr?: number | null;
  rr_meta?: RRMeta | null;
  curiosity?: number | null;
  ucn?: Record<string, number> | null | number;
  created_at?: string | null;
  ts?: string | null;
  metadata?: Record<string, unknown>;
  source?: string | null;
  evidence?: Array<string | { text?: string | null; summary?: string | null } | null> | null;
};

type WhyCardResponse = {
  status?: string;
  user_id: string;
  trait_id?: string | null;
  count: number;
  why_cards: WhyCard[];
};

type WhyCardFetchResult = {
  card: WhyCard | null;
  traitIdUsed: string;
};

const LOCAL_ALIAS_MAP: Record<string, string[]> = {
  "PaDNA.Chronotype": ["BehaviorDNA.Sleep.Chronotype"],
  "BehaviorDNA.Sleep.Chronotype": ["PaDNA.Chronotype"],
};

const CANONICAL_CACHE = new Map<string, string>();
type NullableNumber = number | null | undefined;

export type ShapedWhyCard = {
  what: string;
  why: string;
  next: string;
  rr: NullableNumber;
  rrMeta: RRMeta | null;
  curiosity: NullableNumber;
  ucn: {
    u?: NullableNumber;
    c?: NullableNumber;
    n?: NullableNumber;
    raw?: NullableNumber;
  };
  createdAt: string | null;
  source: string | null;
  isFallback: boolean;
};

const formatValueFromTypedObject = (value: Record<string, unknown>): string | null => {
  if ('enum' in value && typeof value.enum === 'string') {
    return value.enum;
  }
  if ('text' in value && typeof value.text === 'string') {
    return value.text;
  }
  if ('number' in value && typeof value.number === 'number') {
    return String(value.number);
  }
  return null;
};

export function formatTraitValue(value: unknown): string {
  if (value === null || value === undefined) {
    return '—';
  }
  if (typeof value === 'string') {
    return value;
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  if (Array.isArray(value)) {
    const rendered = value
      .map((item) => formatTraitValue(item))
      .filter((item) => item && item !== '—');
    return rendered.length ? rendered.join(', ') : '—';
  }
  if (typeof value === 'object') {
    const typed = formatValueFromTypedObject(value as Record<string, unknown>);
    if (typed) {
      return typed;
    }
    return JSON.stringify(value);
  }
  return String(value);
}

function coalesceString(...values: Array<unknown>): string | null {
  for (const value of values) {
    if (typeof value === 'string') {
      const trimmed = value.trim();
      if (trimmed) {
        return trimmed;
      }
    }
  }
  return null;
}

function extractEvidenceSnippet(card?: WhyCard | null): string | null {
  if (!card) return null;
  const evidence = card.evidence;
  if (!Array.isArray(evidence)) return null;

  for (const entry of evidence) {
    if (!entry) continue;
    if (typeof entry === 'string') {
      const trimmed = entry.trim();
      if (trimmed) return trimmed;
    } else if (typeof entry === 'object') {
      const text = coalesceString((entry as any).summary, (entry as any).text);
      if (text) {
        return text;
      }
    }
  }

  return null;
}

export function shapeWhyCard(card: WhyCard | null, fallbackValue?: unknown): ShapedWhyCard {
  if (!card) {
    return {
      what: '—',
      why: '—',
      next: 'More corroborating observations would increase confidence.',
      rr: null,
      ucn: { raw: null },
      createdAt: null,
      source: null,
      isFallback: true,
    };
  }

  const metadata = (card.metadata ?? {}) as Record<string, unknown>;
  const evidenceSnippet = extractEvidenceSnippet(card);
  const fallbackValueText = formatTraitValue(fallbackValue);

  const rrMetaFromMetadata = metadata && typeof metadata === 'object' && metadata.rr_meta && typeof metadata.rr_meta === 'object'
    ? (metadata.rr_meta as RRMeta)
    : null;
  const rrMeta = card.rr_meta ?? rrMetaFromMetadata ?? null;
  const rrPct = adaptRR(card.rr, rrMeta);
  const curiositySource =
    card.curiosity ??
    (typeof metadata.curiosity === 'number' ? metadata.curiosity : undefined) ??
    (typeof metadata.curiosity_percent === 'number' ? metadata.curiosity_percent : undefined);
  const curiosityPct = adaptCuriosity(curiositySource, rrPct);

  const what =
    coalesceString(
      card.what,
      metadata.what,
      metadata.observation_text,
      metadata.primary_evidence,
      evidenceSnippet,
      metadata.first_observation,
      fallbackValueText
    ) ?? '—';

  const why =
    coalesceString(
      card.why,
      metadata.why,
      metadata.rationale,
      metadata.reason
    ) ?? '—';

  const next =
    coalesceString(
      card.next,
      metadata.next,
      metadata.recommendation,
      metadata.follow_up
    ) ?? 'More corroborating observations would increase confidence.';

  const isFallback = !(card.what && card.what.trim()) || !(card.next && card.next.trim());

  const rawUcn = card.ucn as unknown;
  let ucnPayload: { u?: NullableNumber; c?: NullableNumber; n?: NullableNumber; raw?: NullableNumber } = {
    raw: null,
  };

  if (rawUcn && typeof rawUcn === 'object' && !Array.isArray(rawUcn)) {
    const obj = rawUcn as Record<string, unknown>;
    const u = typeof obj.u === 'number' ? obj.u : null;
    const c = typeof obj.c === 'number' ? obj.c : null;
    const n = typeof obj.n === 'number' ? obj.n : null;
    ucnPayload = { u, c, n, raw: null };
  } else if (typeof rawUcn === 'number') {
    ucnPayload = { raw: rawUcn };
  }

  const createdAt = coalesceString(card.created_at, card.ts) ?? null;
  const source = coalesceString(card.source, metadata.source as string | undefined) ?? null;

  return {
    what,
    why,
    next,
    rr: rrPct ?? null,
    rrMeta,
    curiosity: curiosityPct ?? null,
    ucn: ucnPayload,
    createdAt,
    source,
    isFallback,
  };
}

async function requestWhyCards(userId: string, traitId: string): Promise<WhyCardResponse> {
  const url = `/core/graph/user/${encodeURIComponent(
    userId
  )}/why_cards?trait_id=${encodeURIComponent(traitId)}`;

  const response = await fetch(url);

  if (response.status === 404) {
    return { user_id: userId, trait_id: traitId, status: 'not_found', count: 0, why_cards: [] };
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || error.message || `Why-Card fetch failed: ${response.status}`);
  }

  return response.json();
}

async function resolveAliases(traitId: string): Promise<string[]> {
  const seen = new Set<string>();
  const candidates: string[] = [];

  const appendCandidate = (candidate: string | null | undefined) => {
    if (!candidate) return;
    if (seen.has(candidate)) return;
    seen.add(candidate);
    candidates.push(candidate);
  };

  appendCandidate(traitId);

  // Attempt to fetch aliases from API if available
  try {
    const aliasUrl = `/core/graph/aliases?trait_id=${encodeURIComponent(traitId)}`;
    const resp = await fetch(aliasUrl);
    if (resp.ok) {
      const data = await resp.json();
      const aliases = Array.isArray(data?.aliases) ? (data.aliases as string[]) : [];
      aliases.forEach((alias) => appendCandidate(alias));
    }
  } catch {
    // Silent fallback to local alias map
  }

  (LOCAL_ALIAS_MAP[traitId] ?? []).forEach((alias) => appendCandidate(alias));

  return candidates;
}

export async function fetchWhyCards(userId: string, traitId: string): Promise<WhyCardFetchResult> {
  const aliasCandidates = await resolveAliases(traitId);

  let lastError: Error | null = null;

  for (const candidate of aliasCandidates) {
    try {
      const data = await requestWhyCards(userId, candidate);
      if (Array.isArray(data?.why_cards) && data.why_cards.length > 0) {
        // Instruction specifies `.why_cards | last`
        const lastCard = data.why_cards[data.why_cards.length - 1] ?? null;
        return {
          card: lastCard,
          traitIdUsed: candidate,
        };
      }
    } catch (error) {
      if (error instanceof Error) {
        lastError = error;
      } else {
        lastError = new Error(String(error));
      }
    }
  }

  if (lastError) {
    throw lastError;
  }

  return {
    card: null,
    traitIdUsed: traitId,
  };
}

function localCanonicalTraitId(traitId: string): string {
  if (!traitId) {
    return traitId;
  }
  if (traitId.startsWith('PaDNA.')) {
    return traitId;
  }

  const direct = LOCAL_ALIAS_MAP[traitId];
  if (direct) {
    const preferred = direct.find((alias) => alias.startsWith('PaDNA.'));
    if (preferred) {
      return preferred;
    }
  }

  for (const [key, aliases] of Object.entries(LOCAL_ALIAS_MAP)) {
    if (aliases.includes(traitId)) {
      if (key.startsWith('PaDNA.')) {
        return key;
      }
      const preferred = aliases.find((alias) => alias.startsWith('PaDNA.'));
      if (preferred) {
        return preferred;
      }
    }
  }

  return traitId;
}

export async function resolveCanonicalTraitId(traitId: string): Promise<string> {
  if (!traitId) {
    return traitId;
  }
  if (CANONICAL_CACHE.has(traitId)) {
    return CANONICAL_CACHE.get(traitId)!;
  }

  let canonical = localCanonicalTraitId(traitId);

  try {
    const resp = await fetch(`/core/graph/aliases?trait_id=${encodeURIComponent(traitId)}`);
    if (resp.ok) {
      const data = await resp.json();
      const candidate = typeof data?.canonical === 'string' ? data.canonical : undefined;
      const aliases = Array.isArray(data?.aliases) ? (data.aliases as string[]) : [];

      canonical =
        candidate?.trim() ||
        aliases.find((alias) => typeof alias === 'string' && alias.startsWith('PaDNA.')) ||
        canonical;

      if (!canonical && aliases.length) {
        canonical = aliases[0];
      }
    }
  } catch {
    // ignore failures and fall back to local mapping
  }

  if (!canonical) {
    canonical = traitId;
  }

  CANONICAL_CACHE.set(traitId, canonical);
  return canonical;
}

/**
 * Fetch complete provenance for a trait.
 *
 * @param userId - User identifier
 * @param traitId - Canonical trait ID (e.g., "PaDNA.EyeDNA.IrisColor")
 * @returns Promise resolving to provenance data
 * @throws Error if fetch fails
 */
async function requestProvenance(userId: string, traitId: string): Promise<Provenance | null> {
  const url = `/core/user/${encodeURIComponent(userId)}/provenance/${encodeURIComponent(traitId)}`;
  const response = await fetch(url);

  if (response.status === 404) {
    return null;
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.message || `Provenance fetch failed: ${response.status}`);
  }

  return response.json();
}

export async function fetchProvenance(userId: string, traitId: string): Promise<Provenance | null> {
  const aliasCandidates = await resolveAliases(traitId);
  let lastError: Error | null = null;

  for (const candidate of aliasCandidates) {
    try {
      const data = await requestProvenance(userId, candidate);
      if (data) {
        return data;
      }
    } catch (err) {
      const error = err instanceof Error ? err : new Error(String(err));
      lastError = error;
    }
  }

  if (lastError) {
    throw lastError;
  }

  return null;
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
