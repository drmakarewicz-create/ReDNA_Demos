'use client';

import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, Filter, Loader2, Sparkles, Target } from 'lucide-react';

type PersonaKey = 'career' | 'relationship' | 'personality' | 'chat' | 'belief';

interface PersonaLensEntry {
  container_id: string;
  path: string;
  weight: number;
  trait_relevance: number;
  curiosity_boost: number;
}

interface PersonaLensResponse {
  ok: boolean;
  persona: PersonaKey;
  user_id: string;
  total_containers: number;
  returned_containers: number;
  containers: PersonaLensEntry[];
  error?: string;
  duration_ms?: number;
}

const PERSONA_METADATA: Record<
  PersonaKey,
  { title: string; description: string; gradient: string }
> = {
  career: {
    title: 'Career Navigator',
    description:
      'Maps professional momentum, strengths, and progression opportunities.',
    gradient: 'from-blue-500/30 via-blue-400/10 to-blue-500/5',
  },
  relationship: {
    title: 'Relationship Harmonizer',
    description:
      'Highlights interpersonal dynamics, trust signals, and support arcs.',
    gradient: 'from-pink-500/30 via-rose-400/10 to-pink-500/5',
  },
  personality: {
    title: 'Personality Signature',
    description:
      'Captures enduring traits, motivations, and adaptive behavior patterns.',
    gradient: 'from-purple-500/30 via-violet-400/10 to-purple-500/5',
  },
  chat: {
    title: 'Conversation Style',
    description:
      'Surfaces tone, cadence, and interaction preferences across sessions.',
    gradient: 'from-emerald-500/30 via-emerald-400/10 to-emerald-500/5',
  },
  belief: {
    title: 'Belief Anchor',
    description:
      'Tracks guiding values, philosophies, and decision-making heuristics.',
    gradient: 'from-amber-500/30 via-amber-400/10 to-amber-500/5',
  },
};

const personaOptions: PersonaKey[] = [
  'career',
  'relationship',
  'personality',
  'chat',
  'belief',
];

function weightToOverlay(weight: number): string {
  const clamped = Math.min(1, Math.max(0, weight));
  const alpha = 0.18 + clamped * 0.45;
  return `rgba(37, 99, 235, ${alpha})`;
}

function toPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export default function PersonaLens() {
  const [selectedPersona, setSelectedPersona] = useState<PersonaKey>('career');
  const [userId, setUserId] = useState<string>('demo-user');
  const [context, setContext] = useState<PersonaLensEntry[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [durationMs, setDurationMs] = useState<number | null>(null);

  const personaMeta = useMemo(
    () => PERSONA_METADATA[selectedPersona],
    [selectedPersona],
  );

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();
    const fetchContext = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(
          `http://localhost:8015/ui/persona/context/${selectedPersona}/${encodeURIComponent(
            userId || 'demo-user',
          )}?limit=40`,
          {
            signal: controller.signal,
          },
        );
        const payload: PersonaLensResponse = await res.json();

        if (cancelled) return;

        if (!payload.ok) {
          setError(payload.error || 'Persona context unavailable.');
          setContext([]);
          setDurationMs(payload.duration_ms ?? null);
          return;
        }

        setContext(payload.containers);
        setDurationMs(payload.duration_ms ?? null);
      } catch (err) {
        if (!cancelled) {
          setError('Failed to load persona context. Core API may be offline.');
          setContext([]);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    fetchContext();
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [selectedPersona, userId]);

  return (
    <div className="relative overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-inner">
      <div
        className={`pointer-events-none absolute inset-0 bg-gradient-to-br ${personaMeta.gradient}`}
        aria-hidden="true"
      />
      <div className="relative grid grid-cols-12 gap-6 p-6">
        <div className="col-span-3 space-y-6">
          <div>
            <div className="flex items-center gap-2 text-slate-700">
              <Filter className="h-5 w-5" />
              <span className="text-sm font-semibold uppercase tracking-wide">
                Persona Lens
              </span>
            </div>
            <p className="mt-2 text-sm text-slate-600">{personaMeta.description}</p>
          </div>

          <div className="flex flex-col gap-2">
            {personaOptions.map((persona) => {
              const isActive = persona === selectedPersona;
              return (
                <button
                  key={persona}
                  onClick={() => setSelectedPersona(persona)}
                  className={`flex items-center justify-between rounded-lg px-4 py-3 text-left text-sm transition-all ${
                    isActive
                      ? 'bg-blue-600 text-white shadow-md shadow-blue-600/20'
                      : 'bg-white/60 text-slate-700 hover:bg-slate-100'
                  }`}
                >
                  <div>
                    <div className="font-medium capitalize">{personaMetaFor(persona).title}</div>
                    <div className="text-xs opacity-75">{personaMetaFor(persona).description}</div>
                  </div>
                  {isActive && <Sparkles className="h-4 w-4 shrink-0" />}
                </button>
              );
            })}
          </div>

          <div>
            <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              User Context Anchor
            </label>
            <input
              value={userId}
              onChange={(event) => setUserId(event.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-200"
              placeholder="user-id (defaults to demo-user)"
            />
            <p className="mt-1 text-xs text-slate-500">
              Persona Lens adapts to active sessions. Use a known user id for deterministic results.
            </p>
          </div>

          {durationMs !== null && (
            <div className="rounded-lg border border-blue-100 bg-blue-50 px-3 py-2 text-xs text-blue-700">
              <div className="flex items-center gap-2">
                <Target className="h-3.5 w-3.5" />
                <span>
                  API responded in <strong>{durationMs} ms</strong> (target &lt; 20 ms)
                </span>
              </div>
            </div>
          )}
        </div>

        <div className="col-span-9 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-slate-900 flex items-center gap-2">
                <Sparkles className="h-5 w-5 text-blue-500" />
                {personaMeta.title}
              </h2>
              <p className="text-sm text-slate-500">
                Weighted overlay scaled by persona relevance, trait depth, and curiosity activation.
              </p>
            </div>
            {loading && (
              <div className="flex items-center gap-2 rounded-full bg-blue-100 px-3 py-1 text-xs font-medium text-blue-700">
                <Loader2 className="h-3 w-3 animate-spin" />
                Refreshing lens
              </div>
            )}
          </div>

          {error && (
            <div className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <div>
                <div className="font-semibold">Context unavailable</div>
                <p className="text-amber-700">{error}</p>
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {context.map((entry) => {
              const overlay = weightToOverlay(entry.weight);
              return (
                <div
                  key={entry.container_id}
                  className="relative overflow-hidden rounded-xl border border-blue-200/40 bg-white/70 p-4 shadow-sm backdrop-blur"
                  style={{
                    boxShadow: `0 20px 30px -15px rgba(37, 99, 235, ${entry.weight * 0.25})`,
                  }}
                >
                  <div
                    className="pointer-events-none absolute inset-0 opacity-80"
                    style={{ background: overlay }}
                    aria-hidden="true"
                  />
                  <div className="relative space-y-3">
                    <div>
                      <div className="text-xs font-semibold uppercase tracking-wide text-white/80">
                        {entry.container_id}
                      </div>
                      <div className="text-sm font-medium text-white">
                        {entry.path}
                      </div>
                    </div>
                    <div className="grid grid-cols-3 gap-2 text-xs text-white/90">
                      <div className="rounded-lg bg-white/10 px-2 py-1">
                        <div className="font-semibold">Weight</div>
                        <div>{toPercent(entry.weight)}</div>
                      </div>
                      <div className="rounded-lg bg-white/10 px-2 py-1">
                        <div className="font-semibold">Trait Depth</div>
                        <div>{toPercent(entry.trait_relevance)}</div>
                      </div>
                      <div className="rounded-lg bg-white/10 px-2 py-1">
                        <div className="font-semibold">Curiosity</div>
                        <div>{toPercent(entry.curiosity_boost)}</div>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {!loading && context.length === 0 && !error && (
            <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white/80 px-6 py-8 text-center text-sm text-slate-500">
              <Sparkles className="h-6 w-6 text-blue-400" />
              <p>
                No containers surfaced for this persona yet. Generate V6 registry and rerun the lens.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function personaMetaFor(persona: PersonaKey) {
  return PERSONA_METADATA[persona];
}
