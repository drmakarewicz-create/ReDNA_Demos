export const CORE_BASE = process.env.NEXT_PUBLIC_CORE_API_BASE ?? 'http://127.0.0.1:8004';

export interface WhyCardEvidence {
  source?: string | null;
  text?: string | null;
  summary?: string | null;
}

export interface WhyCardResponse {
  trait_id: string;
  user_id?: string;
  value?: string | null;
  rr?: number | null;
  why?: string | null;
  ts?: string | null;
  created_at?: string | null;
  source?: string | null;
  event_id?: string | null;
  confidence?: {
    point_estimate?: number | null;
    interval_95?: [number | null, number | null];
  };
  evidence?: Array<WhyCardEvidence | string> | null;
}

export interface WhyCardNotFound {
  notFound: true;
}

export async function fetchWhyCard(userId: string, traitId: string): Promise<WhyCardResponse | WhyCardNotFound> {
  // Try to resolve aliases - attempt both PaDNA and BehaviorDNA namespaces
  const aliasCandidates = await resolveAliases(traitId);

  let lastError: Error | null = null;

  for (const candidate of aliasCandidates) {
    try {
      const url = `${CORE_BASE}/core/api/traits/${encodeURIComponent(candidate)}/why?user_id=${encodeURIComponent(userId)}`;
      const res = await fetch(url, { cache: 'no-store' });

      if (res.status === 404) {
        // Try next candidate
        continue;
      }

      if (!res.ok) {
        lastError = new Error(`WhyCard fetch failed: ${res.status}`);
        continue;
      }

      // Success! Return the card
      return res.json();
    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error));
    }
  }

  // If we get here, none of the aliases had a Why-Card
  return { notFound: true };
}

// Helper to resolve trait ID aliases (copied from provenanceClient pattern)
async function resolveAliases(traitId: string): Promise<string[]> {
  const candidates = [traitId];

  // Add BehaviorDNA variant if this is a PaDNA trait
  if (traitId.startsWith('PaDNA.')) {
    const suffix = traitId.substring('PaDNA.'.length);
    // Map common PaDNA traits to their BehaviorDNA equivalents
    const mapping: Record<string, string> = {
      'Chronotype': 'BehaviorDNA.Sleep.Chronotype',
      'EyeDNA.IrisColor': 'BehaviorDNA.Appearance.EyeColor',
      'HairDNA.NaturalColor': 'BehaviorDNA.Appearance.HairColor',
    };

    const behaviorDNA = mapping[suffix] || `BehaviorDNA.${suffix}`;
    candidates.push(behaviorDNA);
  } else if (traitId.startsWith('BehaviorDNA.')) {
    // Add PaDNA variant if this is a BehaviorDNA trait
    const suffix = traitId.substring('BehaviorDNA.'.length);
    const mapping: Record<string, string> = {
      'Sleep.Chronotype': 'PaDNA.Chronotype',
      'Appearance.EyeColor': 'PaDNA.EyeDNA.IrisColor',
      'Appearance.HairColor': 'PaDNA.HairDNA.NaturalColor',
    };

    const padna = mapping[suffix] || `PaDNA.${suffix}`;
    candidates.push(padna);
  }

  return candidates;
}
