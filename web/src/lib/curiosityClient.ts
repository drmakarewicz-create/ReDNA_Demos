export type NextQuestionCandidate = {
  question_text: string;
  target_trait_id: string;
  confidence: number;
  graph_path: string[];
  rationale?: string;
};

type NextQuestionSingleResponse = {
  question_text?: string;
  target_trait_id?: string;
  confidence?: number;
  graph_path?: string[];
  rationale?: string;
};

type NextQuestionListResponse = {
  candidates?: NextQuestionSingleResponse[];
};

import { CORE_API_BASE } from './api';

function normalizeCandidates(
  data: NextQuestionSingleResponse | NextQuestionListResponse | null | undefined
): NextQuestionCandidate[] {
  if (!data || typeof data !== 'object') {
    return [];
  }

  if ('candidates' in data && Array.isArray(data.candidates)) {
    return data.candidates
      .map((candidate) => ({
        question_text: candidate?.question_text ?? '',
        target_trait_id: candidate?.target_trait_id ?? '',
        confidence:
          typeof candidate?.confidence === 'number' && Number.isFinite(candidate.confidence)
            ? candidate.confidence
            : 0,
        graph_path: Array.isArray(candidate?.graph_path)
          ? (candidate?.graph_path as string[])
          : [],
        rationale: candidate?.rationale,
      }))
      .filter((item) => item.question_text.trim().length > 0);
  }

  const single = data as NextQuestionSingleResponse;
  if (single.question_text && single.question_text.trim().length > 0) {
    return [
      {
        question_text: single.question_text,
        target_trait_id: single.target_trait_id ?? '',
        confidence:
          typeof single.confidence === 'number' && Number.isFinite(single.confidence)
            ? single.confidence
            : 0,
        graph_path: Array.isArray(single.graph_path) ? single.graph_path : [],
        rationale: single.rationale,
      },
    ];
  }

  return [];
}

export async function fetchNextQuestions(
  userId: string,
  strategy = 'auto',
  max = 5
): Promise<NextQuestionCandidate[]> {
  if (!userId.trim()) {
    return [];
  }

  const encodedUser = encodeURIComponent(userId);
  const query = new URLSearchParams({
    strategy,
    max_candidates: String(Math.max(1, Math.min(max, 20))),
  });

  const base = CORE_API_BASE.replace(/\/+$/, '');
  const getUrl = `${base}/core/graph/user/${encodedUser}/next_question?${query.toString()}`;
  const postUrl = `${base}/core/graph/user/${encodedUser}/next_question`;

  let response = await fetch(getUrl);

  if (response.status === 404 || response.status === 405) {
    response = await fetch(postUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        strategy,
        max_candidates: max,
      }),
    });
  }

  if (!response.ok) {
    let detail: string | undefined;
    try {
      const data = await response.json();
      detail =
        typeof data?.detail === 'string'
          ? data.detail
          : typeof data?.error === 'string'
            ? data.error
            : undefined;
    } catch {
      // Ignore parse errors and fall back to status text
    }
    throw new Error(detail || `Failed to load next questions (HTTP ${response.status})`);
  }

  const raw = await response.json().catch(() => null);
  return normalizeCandidates(raw);
}
