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
  const url = `${CORE_BASE}/core/api/traits/${encodeURIComponent(traitId)}/why?user_id=${encodeURIComponent(userId)}`;
  const res = await fetch(url, { cache: 'no-store' });
  if (res.status === 404) {
    return { notFound: true };
  }
  if (!res.ok) {
    throw new Error(`WhyCard fetch failed: ${res.status}`);
  }
  return res.json();
}
