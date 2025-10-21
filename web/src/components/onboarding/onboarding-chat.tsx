'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { CORE_API_BASE } from '@/lib/api';
import { fetchNextQuestions, type NextQuestionCandidate } from '@/lib/curiosityClient';
import { extractTraitLabel, formatTraitValue } from '@/lib/provenanceClient';
import { WhyCardModal } from '@/components/why/WhyCardModal';

type ChatMessage = {
  id: string;
  role: 'user' | 'system';
  text: string;
  createdAt: number;
  kind?: 'question' | 'note';
};

type TraitCard = {
  traitId: string;
  label: string;
  value: string;
  category: TraitCategoryKey;
  rrPct: number | null;
  curiosityPct: number | null;
  updatedAt: number;
};

type TraitState = Record<string, TraitCard>;

type TraitCategoryKey = 'PaDNA' | 'BehDNA' | 'CogDNA' | 'EmoDNA' | 'RelDNA' | 'Other';

type PersistedState = {
  version: number;
  messages: ChatMessage[];
  traits: TraitState;
  interactionCount: number;
  autoQuestion?: NextQuestionCandidate | null;
  autoQuestionThreshold?: number;
  lastSaved: number;
};

const AUTO_QUESTION_MIN = 3;
const AUTO_QUESTION_MAX = 5;
const STORAGE_VERSION = 1;

const CATEGORY_META: Record<
  TraitCategoryKey,
  { label: string; gradient: string; accent: string }
> = {
  PaDNA: { label: 'PaDNA', gradient: 'from-cyan-500 to-violet-500', accent: 'text-cyan-200' },
  BehDNA: { label: 'BehDNA', gradient: 'from-amber-500 to-rose-500', accent: 'text-amber-200' },
  CogDNA: { label: 'CogDNA', gradient: 'from-indigo-500 to-sky-500', accent: 'text-indigo-200' },
  EmoDNA: { label: 'EmoDNA', gradient: 'from-pink-500 to-purple-500', accent: 'text-pink-200' },
  RelDNA: { label: 'RelDNA', gradient: 'from-emerald-500 to-green-600', accent: 'text-emerald-200' },
  Other: { label: 'Other', gradient: 'from-slate-600 to-slate-800', accent: 'text-slate-200' },
};

function categoryForTrait(traitId: string): TraitCategoryKey {
  if (traitId.startsWith('PaDNA.')) return 'PaDNA';
  if (traitId.startsWith('BehaviorDNA.') || traitId.startsWith('BehDNA.')) return 'BehDNA';
  if (traitId.startsWith('CognitiveDNA.') || traitId.startsWith('CogDNA.')) return 'CogDNA';
  if (traitId.startsWith('EmotionDNA.') || traitId.startsWith('EmoDNA.')) return 'EmoDNA';
  if (traitId.startsWith('RelationshipDNA.') || traitId.startsWith('RelDNA.')) return 'RelDNA';
  return 'Other';
}

function makeId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function toDisplayValue(rawValue: unknown): string {
  if (rawValue === null || rawValue === undefined) {
    return '—';
  }

  if (typeof rawValue === 'object' && !Array.isArray(rawValue)) {
    const value = rawValue as Record<string, unknown>;
    return formatTraitValue(value as any) ?? '—';
  }

  if (typeof rawValue === 'string') {
    return rawValue.trim() || '—';
  }

  return String(rawValue);
}

function roundPct(value: number | null | undefined): number | null {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return null;
  }
  return Math.max(0, Math.min(100, Math.round(value * 10) / 10));
}

function persistKey(userId: string): string {
  return `onboarding-session-${userId}`;
}

function resolveAutoQuestionThreshold(seed?: number | null): number {
  if (typeof seed === 'number' && Number.isFinite(seed)) {
    const clamped = Math.round(seed);
    return Math.min(AUTO_QUESTION_MAX, Math.max(AUTO_QUESTION_MIN, clamped));
  }
  const span = AUTO_QUESTION_MAX - AUTO_QUESTION_MIN + 1;
  return AUTO_QUESTION_MIN + Math.floor(Math.random() * span);
}

function formatTraitSummaryLine(trait: TraitCard): string {
  const value = trait.value && trait.value !== '—' ? trait.value : '—';
  const metrics: string[] = [];
  if (typeof trait.rrPct === 'number') {
    metrics.push(`RR ${trait.rrPct.toFixed(1)}%`);
  }
  if (typeof trait.curiosityPct === 'number') {
    metrics.push(`Curiosity ${trait.curiosityPct.toFixed(1)}%`);
  }
  const metricsText = metrics.length > 0 ? ` (${metrics.join(', ')})` : '';
  return `${trait.label} – ${value}${metricsText}`;
}

function formatTraitMetrics(trait: TraitCard): string {
  const rrText =
    typeof trait.rrPct === 'number' ? `${trait.rrPct.toFixed(1)}%` : '—';
  const curiosityText =
    typeof trait.curiosityPct === 'number' ? `${trait.curiosityPct.toFixed(1)}%` : '—';
  return `RR ${rrText}, Curiosity ${curiosityText}`;
}

export interface OnboardingChatProps {
  userId: string;
  onComplete?: () => void;
}

export function OnboardingChat({ userId, onComplete }: OnboardingChatProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [pending, setPending] = useState(false);
  const [traits, setTraits] = useState<TraitState>({});
  const [interactionCount, setInteractionCount] = useState(0);
  const [autoQuestion, setAutoQuestion] = useState<NextQuestionCandidate | null>(null);
  const [autoQuestionThreshold, setAutoQuestionThreshold] = useState<number>(() =>
    resolveAutoQuestionThreshold()
  );
  const [whyTrait, setWhyTrait] = useState<TraitCard | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  const groupedTraits = useMemo(() => {
    const buckets: Record<TraitCategoryKey, TraitCard[]> = {
      PaDNA: [],
      BehDNA: [],
      CogDNA: [],
      EmoDNA: [],
      RelDNA: [],
      Other: [],
    };
    Object.values(traits)
      .sort((a, b) => b.updatedAt - a.updatedAt)
      .forEach((card) => {
        buckets[card.category].push(card);
      });
    return buckets;
  }, [traits]);

  // hydrate from localStorage
  useEffect(() => {
    if (!userId) return;
    try {
      const raw = window.localStorage.getItem(persistKey(userId));
      if (!raw) return;
      const parsed = JSON.parse(raw) as PersistedState;
      if (!parsed || parsed.version !== STORAGE_VERSION) return;
      setMessages(parsed.messages ?? []);
      setTraits(parsed.traits ?? {});
      setInteractionCount(parsed.interactionCount ?? 0);
      setAutoQuestion(parsed.autoQuestion ?? null);
      setAutoQuestionThreshold(resolveAutoQuestionThreshold(parsed.autoQuestionThreshold));
    } catch (err) {
      console.warn('[Onboarding] Failed to hydrate session', err);
    }
  }, [userId]);

  // persist whenever state changes
  useEffect(() => {
    if (!userId) return;
    const snapshot: PersistedState = {
      version: STORAGE_VERSION,
      messages,
      traits,
      interactionCount,
      autoQuestion,
      autoQuestionThreshold,
      lastSaved: Date.now(),
    };
    try {
      window.localStorage.setItem(persistKey(userId), JSON.stringify(snapshot));
    } catch (err) {
      console.warn('[Onboarding] Failed to persist session', err);
    }
  }, [autoQuestion, autoQuestionThreshold, interactionCount, messages, traits, userId]);

  const appendMessage = useCallback((message: Omit<ChatMessage, 'id' | 'createdAt'>) => {
    setMessages((prev) => [
      ...prev,
      {
        id: makeId(),
        createdAt: Date.now(),
        ...message,
      },
    ]);
  }, []);

  const applyIngestPayload = useCallback(
    (payload: any, options: { summary: boolean }) => {
      if (!payload || typeof payload !== 'object') {
        if (options.summary) {
          appendMessage({
            role: 'system',
            text: 'Got it. Logging that and continuing.',
            kind: 'note',
          });
        }
        return;
      }

      const snapshotTraits = Array.isArray(payload?.snapshot?.traits)
        ? (payload.snapshot.traits as any[])
        : [];
      const rrByTrait: Record<string, number> =
        (payload?.rescore?.rr_by_trait as Record<string, number>) ?? {};
      const curiosityByTrait: Record<string, number> =
        (payload?.rescore?.curiosity_by_trait as Record<string, number>) ?? {};

      if (snapshotTraits.length === 0 && Object.keys(rrByTrait).length === 0) {
        if (options.summary) {
          appendMessage({
            role: 'system',
            text: 'Got it. Logging that and continuing.',
            kind: 'note',
          });
        }
        return;
      }

      const updates: TraitState = {};
      const now = Date.now();

      snapshotTraits.forEach((trait: any) => {
        const traitId = String(trait?.trait_id ?? '').trim();
        if (!traitId) {
          return;
        }
        const label = extractTraitLabel(traitId);
        const category = categoryForTrait(traitId);
        const rawValue = trait?.value ?? trait?.normalized_value ?? trait?.resolved_value;
        const value = toDisplayValue(rawValue);
        const rr = roundPct(rrByTrait?.[traitId]);
        const curiosity = roundPct(curiosityByTrait?.[traitId]);

        updates[traitId] = {
          traitId,
          label,
          value,
          category,
          rrPct: rr,
          curiosityPct: curiosity,
          updatedAt: now,
        };
      });

      Object.entries(rrByTrait).forEach(([traitId, rrValue]) => {
        if (updates[traitId]) {
          return;
        }
        const label = extractTraitLabel(traitId);
        const category = categoryForTrait(traitId);
        const curiosity = roundPct(curiosityByTrait?.[traitId]);
        updates[traitId] = {
          traitId,
          label,
          value: '—',
          category,
          rrPct: roundPct(rrValue),
          curiosityPct: curiosity,
          updatedAt: now,
        };
      });

      if (Object.keys(updates).length === 0) {
        if (options.summary) {
          appendMessage({
            role: 'system',
            text: 'Captured that. No new traits yet.',
            kind: 'note',
          });
        }
        return;
      }

      setTraits((prev) => {
        const next: TraitState = { ...prev };
        Object.values(updates).forEach((card) => {
          const existing = prev[card.traitId];
          if (existing) {
            next[card.traitId] = {
              ...existing,
              ...card,
              value:
                card.value === '—' && existing.value && existing.value !== '—'
                  ? existing.value
                  : card.value,
              updatedAt: card.updatedAt,
            };
          } else {
            next[card.traitId] = card;
          }
        });
        return next;
      });

      if (options.summary) {
        const summaryText =
          Object.values(updates)
            .slice(0, 3)
            .map((trait) => formatTraitSummaryLine(trait))
            .join('\n') || 'Captured new insight.';

        appendMessage({
          role: 'system',
          text: summaryText,
          kind: 'note',
        });
      }
    },
    [appendMessage, setTraits]
  );

  const consumeIngestResponse = useCallback(
    async (response: Response) => {
      const contentType = response.headers.get('content-type') ?? '';
      if (contentType.includes('text/event-stream') && response.body) {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let lastPayload: any = null;

        while (true) {
          const { value, done } = await reader.read();
          if (done) {
            break;
          }
          buffer += decoder.decode(value, { stream: true });
          let boundary = buffer.indexOf('\n\n');
          while (boundary !== -1) {
            const rawEvent = buffer.slice(0, boundary);
            buffer = buffer.slice(boundary + 2);
            boundary = buffer.indexOf('\n\n');

            const dataPayload = rawEvent
              .split('\n')
              .filter((line) => line.trim().startsWith('data:'))
              .map((line) => line.replace(/^data:\s*/, ''))
              .join('\n')
              .trim();

            if (!dataPayload) {
              continue;
            }

            try {
              const parsed = JSON.parse(dataPayload);
              lastPayload = parsed;
              applyIngestPayload(parsed, { summary: false });
            } catch (error) {
              console.warn('[Onboarding] Failed to parse ingest event', error);
            }
          }
        }

        if (lastPayload) {
          applyIngestPayload(lastPayload, { summary: true });
          return lastPayload;
        }

        applyIngestPayload({}, { summary: true });
        return null;
      }

      let payload: any = null;
      try {
        payload = await response.json();
      } catch (error) {
        console.warn('[Onboarding] Failed to parse ingest response', error);
      }

      applyIngestPayload(payload ?? {}, { summary: true });
      return payload;
    },
    [applyIngestPayload]
  );

  const handleSubmit = useCallback(
    async (event?: React.FormEvent<HTMLFormElement>) => {
      event?.preventDefault();
      const trimmed = input.trim();
      if (!trimmed || pending) return;

      appendMessage({ role: 'user', text: trimmed });
      setInput('');
      setPending(true);
      setInteractionCount((count) => count + 1);

      try {
        const base = CORE_API_BASE.replace(/\/+$/, '');
        const response = await fetch(`${base}/core/api/ingest_text`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Accept: 'text/event-stream, application/json',
            'Cache-Control': 'no-store',
          },
          body: JSON.stringify({
            user_id: userId,
            text: trimmed,
            source: 'onboarding_chat',
            stream: true,
          }),
        });

        if (!response.ok) {
          let detailMessage: string | undefined;
          try {
            const detailPayload = await response.json();
            detailMessage =
              detailPayload?.errors?.[0] ||
              detailPayload?.error ||
              detailPayload?.detail ||
              undefined;
          } catch {
            detailMessage = undefined;
          }

          throw new Error(
            detailMessage || `Failed to ingest text (HTTP ${response.status})`
          );
        }

        await consumeIngestResponse(response);
      } catch (err) {
        console.error('[Onboarding] ingestion error', err);
        const detail =
          err instanceof Error ? err.message : 'Something went wrong recording that.';
        appendMessage({
          role: 'system',
          text: `Unable to record that just now (${detail}). Let's keep going.`,
          kind: 'note',
        });
      } finally {
        setPending(false);
        setTimeout(() => {
          textareaRef.current?.focus();
        }, 50);
      }
    },
    [appendMessage, consumeIngestResponse, input, pending, userId]
  );

  // Auto curiosity question after threshold
  useEffect(() => {
    if (autoQuestion || interactionCount < autoQuestionThreshold || !userId) {
      return;
    }

    let cancelled = false;

    (async () => {
      try {
        const candidates = await fetchNextQuestions(userId, 'auto', 1);
        const candidate = candidates[0];
        if (candidate && !cancelled) {
          setAutoQuestion(candidate);
          appendMessage({
            role: 'system',
            text: candidate.question_text,
            kind: 'question',
          });
        }
      } catch (err) {
        console.warn('[Onboarding] failed to fetch curiosity question', err);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [appendMessage, autoQuestion, autoQuestionThreshold, interactionCount, userId]);

  const handleWhy = useCallback((card: TraitCard) => {
    setWhyTrait(card);
  }, []);

  const handleComplete = useCallback(() => {
    if (onComplete) {
      onComplete();
    }
  }, [onComplete]);

  return (
    <div className="flex flex-col gap-6">
      <div className="rounded-lg border border-slate-800/60 bg-slate-900/40 px-4 py-3 text-sm text-slate-200">
        <p className="italic">
          “This isn’t a test; it’s discovery.” Share a few notes about yourself and we’ll surface
          the traits we detect in real time.
        </p>
      </div>

      <section className="space-y-4">
        {(
          Object.entries(groupedTraits) as Array<[TraitCategoryKey, TraitCard[]]>
        )
          .filter(([, items]) => items.length > 0)
          .map(([category, items]) => {
            const meta = CATEGORY_META[category];
            return (
              <div key={category} className="space-y-3">
                <div className={`inline-flex items-center gap-2 text-sm ${meta.accent}`}>
                  <span className={`inline-flex h-2 w-2 rounded-full bg-gradient-to-r ${meta.gradient}`} />
                  <span className="font-semibold uppercase tracking-wide">{meta.label}</span>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  {items.map((trait) => {
                    const valueDisplay =
                      trait.value && trait.value !== '—' ? trait.value : '—';
                    const metricsText = formatTraitMetrics(trait);
                    return (
                      <div
                        key={trait.traitId}
                        className="rounded-lg border border-slate-800/70 bg-slate-900/30 p-3 shadow-inner"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="space-y-1 text-sm text-slate-100">
                            <div className="leading-snug">
                              <span className="font-semibold">{trait.label}</span>
                              <span className="text-slate-300"> – {valueDisplay}</span>
                              <span className="ml-1 text-slate-400">({metricsText})</span>
                            </div>
                          </div>
                          <button
                            type="button"
                            className="text-xs text-cyan-300 hover:text-cyan-100 transition"
                            onClick={() => handleWhy(trait)}
                          >
                            Explain Why
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
      </section>

      <section className="flex-1 min-h-[320px] rounded-lg border border-slate-800/60 bg-slate-900/30 p-4">
        <div className="space-y-4">
          {messages.length === 0 ? (
            <p className="text-sm text-slate-400">
              Tell us something about yourself to get started. Mention habits, preferences, or goals
              — we’ll translate them into traits automatically.
            </p>
          ) : null}
          {messages.map((message) => (
            <div
              key={message.id}
              className={`flex ${
                message.role === 'user' ? 'justify-end' : 'justify-start'
              }`}
            >
              <div
                className={`max-w-[80%] rounded-lg px-3 py-2 text-sm shadow ${
                  message.role === 'user'
                    ? 'bg-gradient-to-r from-cyan-500/80 to-violet-500/80 text-white'
                    : message.kind === 'question'
                      ? 'bg-emerald-900/60 border border-emerald-700 text-emerald-100'
                      : 'bg-slate-800/70 border border-slate-700 text-slate-200'
                }`}
              >
                {message.text.split('\n').map((line, idx) => (
                  <p key={idx}>{line}</p>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>

 
      <form onSubmit={handleSubmit} className="space-y-3">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="Describe something about yourself..."
          className="w-full rounded-lg border border-slate-800 bg-slate-900/50 px-4 py-3 text-sm text-slate-100 focus:border-cyan-500 focus:outline-none focus:ring-2 focus:ring-cyan-500 disabled:opacity-50"
          rows={3}
          disabled={pending}
        />
        <div className="flex items-center justify-between">
          <button
            type="submit"
            disabled={pending || input.trim().length === 0}
            className="inline-flex items-center gap-2 rounded-md bg-gradient-to-r from-cyan-500 to-violet-600 px-4 py-2 text-sm font-semibold text-white shadow transition disabled:opacity-50"
          >
            {pending ? 'Listening…' : 'Share'}
          </button>
          <button
            type="button"
            onClick={handleComplete}
            className="text-sm text-slate-400 hover:text-slate-200 transition"
          >
            Finish onboarding
          </button>
        </div>
      </form>

      <WhyCardModal
        open={Boolean(whyTrait)}
        onClose={() => setWhyTrait(null)}
        userId={userId}
        traitId={whyTrait?.traitId ?? ''}
        traitLabel={whyTrait?.label}
        value={whyTrait?.value}
      />
    </div>
  );
}

export default OnboardingChat;
