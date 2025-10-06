'use client';

import { useEffect, useMemo, useState } from 'react';
import type { CSSProperties, ReactNode } from 'react';
import Lottie from 'lottie-react';
import { useFeatureFlags } from '../../lib/feature-flags';

export type CoachAvatarState = 'idle' | 'listening' | 'thinking' | 'speaking' | 'error';

type PersonaKey = 'head_coach' | 'rc' | 'rendering' | 'photo' | 'padna';  // padna kept for backward compat

interface CoachAvatarProps {
  personaKey: PersonaKey;
  state: CoachAvatarState;
  className?: string;
  size?: number;
  ariaLabel?: string;
}

const STATE_TO_FILENAME: Record<CoachAvatarState, string> = {
  idle: 'idle',
  listening: 'idle',
  thinking: 'idle',
  speaking: 'speak',
  error: 'error'
};

const PERSONA_ACCENT: Record<PersonaKey, string> = {
  head_coach: '#22d3ee',   // Cyan (compass/nav theme)
  rc: '#ec4899',           // Pink (heart icon)
  rendering: '#10b981',    // Green accent
  photo: '#f59e0b',        // Amber/orange (camera icon)
  padna: '#10b981'         // Backward compatibility → rendering
};

const PERSONA_ICON: Record<PersonaKey, string> = {
  head_coach: '🧭',        // Compass for navigation/orchestration
  rc: '💖',                // Heart for Relationship Coach
  rendering: '🎨',         // Art palette for Rendering Coach
  photo: '📷',             // Camera for Photo Coach
  padna: '🎨'              // Backward compatibility → rendering
};

const animationCache = new Map<string, unknown>();
const FALLBACK_PERSONA: PersonaKey = 'head_coach';

const STATE_LABELS: Record<CoachAvatarState, string> = {
  idle: 'Idle',
  listening: 'Listening',
  thinking: 'Thinking',
  speaking: 'Speaking',
  error: 'Error'
};

function hexToRgb(hex: string): [number, number, number] {
  const normalized = hex.replace('#', '');
  const bigint = Number.parseInt(normalized, 16);
  const r = (bigint >> 16) & 255;
  const g = (bigint >> 8) & 255;
  const b = bigint & 255;
  return [r, g, b];
}

function rgba([r, g, b]: [number, number, number], alpha: number): string {
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function resolveAssetPath(persona: PersonaKey, state: CoachAvatarState): string {
  const file = STATE_TO_FILENAME[state];
  return `/avatars/${persona}/${file}.json`;
}

function buildCandidatePaths(persona: PersonaKey, state: CoachAvatarState): string[] {
  const file = STATE_TO_FILENAME[state];
  const candidates = [resolveAssetPath(persona, state)];
  const sharedPath = `/avatars/${file}.json`;
  if (!candidates.includes(sharedPath)) {
    candidates.push(sharedPath);
  }
  const fallbackPersonaPath = resolveAssetPath(FALLBACK_PERSONA, state);
  if (!candidates.includes(fallbackPersonaPath)) {
    candidates.push(fallbackPersonaPath);
  }
  return candidates;
}

function buildCacheKey(persona: PersonaKey, state: CoachAvatarState): string {
  return `${persona}:${state}`;
}

export function CoachAvatar({
  personaKey,
  state,
  className,
  size = 56,
  ariaLabel
}: CoachAvatarProps): JSX.Element | null {
  const [animationData, setAnimationData] = useState<unknown | null>(null);
  const [loading, setLoading] = useState(false);
  const [hydrated, setHydrated] = useState(false);
  const { flags, hydrated: flagsHydrated } = useFeatureFlags();

  const effectiveAccent = PERSONA_ACCENT[personaKey] ?? PERSONA_ACCENT[FALLBACK_PERSONA];
  const resolvedAriaLabel = ariaLabel ?? `Coach avatar: ${state}`;

  const dimensionStyle = useMemo(() => ({
    width: `${size}px`,
    height: `${size}px`
  }), [size]);

  const accentRgb = useMemo(() => hexToRgb(effectiveAccent), [effectiveAccent]);

  const stateVisuals = useMemo((): {
    containerClass: string;
    containerStyle?: CSSProperties;
    overlayClass: string;
    overlayStyle?: CSSProperties;
    badge: ReactNode;
    centerOverlay: ReactNode;
  } => {
    const ringStyle: CSSProperties = {
      '--tw-ring-color': effectiveAccent
    } as CSSProperties;

    switch (state) {
      case 'listening': {
        return {
          containerClass: 'ring-2 shadow-lg transition-shadow',
          containerStyle: {
            ...ringStyle,
            boxShadow: `0 0 0 2px ${rgba(accentRgb, 0.35)}, 0 0 20px ${rgba(accentRgb, 0.45)}`
          },
          overlayClass: 'animate-pulse-slow',
          overlayStyle: {
            backgroundColor: rgba(accentRgb, 0.15)
          },
          badge: null,
          centerOverlay: null
        };
      }
      case 'speaking': {
        return {
          containerClass: 'ring-2 shadow-lg transition-shadow',
          containerStyle: {
            ...ringStyle,
            boxShadow: `0 0 0 2px ${rgba(accentRgb, 0.45)}, 0 0 28px ${rgba(accentRgb, 0.6)}`
          },
          overlayClass: 'animate-pulse-fast',
          overlayStyle: {
            backgroundColor: rgba(accentRgb, 0.22)
          },
          badge: (
            <span
              className="absolute -bottom-1 -right-1 z-20 flex h-6 w-6 items-center justify-center rounded-full text-sm text-slate-950 shadow-lg"
              style={{ backgroundColor: rgba(accentRgb, 0.95) }}
            >
              💬
            </span>
          ),
          centerOverlay: null
        };
      }
      case 'error':
        return {
          containerClass: 'ring-2 shadow-lg transition-shadow',
          containerStyle: {
            '--tw-ring-color': '#f87171',
            boxShadow: '0 0 0 2px rgba(248, 113, 113, 0.4), 0 0 26px rgba(248, 113, 113, 0.6)'
          } as CSSProperties,
          overlayClass: '',
          overlayStyle: { backgroundColor: 'rgba(248, 113, 113, 0.18)' },
          badge: null,
          centerOverlay: (
            <div className="pointer-events-none absolute inset-0 z-20 flex items-center justify-center text-2xl text-rose-200">
              ❗
            </div>
          )
        };
      case 'idle':
      default:
        return {
          containerClass: 'ring shadow transition-shadow',
          containerStyle: {
            '--tw-ring-color': rgba(accentRgb, 0.35),
            boxShadow: `0 0 0 2px ${rgba(accentRgb, 0.2)}, 0 0 12px rgba(15, 23, 42, 0.6)`
          } as CSSProperties,
          overlayClass: '',
          overlayStyle: { backgroundColor: 'rgba(15, 23, 42, 0.65)' },
          badge: (
            <span
              className="absolute -bottom-1 -right-1 z-20 flex h-7 w-7 items-center justify-center rounded-full text-base shadow-lg border-2 border-slate-900"
              style={{ backgroundColor: effectiveAccent }}
              title={`${personaKey} coach`}
            >
              {PERSONA_ICON[personaKey] ?? PERSONA_ICON[FALLBACK_PERSONA]}
            </span>
          ),
          centerOverlay: null
        };
    }
  }, [state, accentRgb, effectiveAccent, personaKey]);

  useEffect(() => {
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) {
      return;
    }

    let cancelled = false;
    const cacheKey = buildCacheKey(personaKey, state);
    const candidatePaths = buildCandidatePaths(personaKey, state);

    const applyData = (data: unknown) => {
      if (!cancelled) {
        setAnimationData(data);
        setLoading(false);
      }
    };

    const load = async (): Promise<void> => {
      const cached = animationCache.get(cacheKey);
      if (cached) {
        applyData(cached);
        return;
      }

      setLoading(true);
      let lastError: unknown = null;

      for (const path of candidatePaths) {
        const cachedCandidate = animationCache.get(path);
        if (cachedCandidate) {
          animationCache.set(cacheKey, cachedCandidate);
          applyData(cachedCandidate);
          return;
        }

        try {
          const response = await fetch(path);
          if (!response.ok) {
            throw new Error(`Asset fetch failed with status ${response.status}`);
          }

          const payload = await response.json();
          if (!cancelled) {
            animationCache.set(path, payload);
            animationCache.set(cacheKey, payload);
            applyData(payload);
          }
          return;
        } catch (error) {
          lastError = error;
        }
      }

      if (!cancelled) {
        setAnimationData(null);
        setLoading(false);
        console.warn(
          `[CoachAvatar] Failed to load animation for persona="${personaKey}" state="${state}". Tried: ${candidatePaths.join(
            ', '
          )}`,
          lastError ?? undefined
        );
      }
    };

    void load();

    return () => {
      cancelled = true;
    };
  }, [hydrated, personaKey, state]);
  return (
    <div className={`flex flex-col items-center ${className ?? ''}`} style={{ width: `${size}px` }}>
      <div
        className={`relative flex shrink-0 items-center justify-center rounded-full transition-all duration-300 ${stateVisuals.containerClass}`}
        style={{ ...dimensionStyle, ...(stateVisuals.containerStyle ?? {}) }}
        role="img"
        aria-label={resolvedAriaLabel}
        data-testid="coach-avatar"
      >
        <div
          className={`absolute inset-0 rounded-full transition ${
            hydrated && stateVisuals.overlayClass ? stateVisuals.overlayClass : ''
          }`}
          style={hydrated ? stateVisuals.overlayStyle : { backgroundColor: 'rgba(15, 23, 42, 0.6)' }}
        />
        <div className="relative z-10 flex h-[96%] w-[96%] items-center justify-center overflow-hidden rounded-full bg-slate-950/80">
          {hydrated && animationData ? (
            <Lottie
              animationData={animationData}
              loop={state !== 'error'}
              autoplay
              style={{ width: '100%', height: '100%' }}
            />
          ) : (
            <div className="flex h-full w-full items-center justify-center text-slate-400">
              {hydrated && loading ? (
                <span className="animate-pulse text-xs">Loading…</span>
              ) : (
                <span className="text-base">🙂</span>
              )}
            </div>
          )}
        </div>
        {hydrated ? stateVisuals.centerOverlay : null}
        {hydrated ? stateVisuals.badge : null}
      </div>
      {flagsHydrated && hydrated && flags.avatarDebug ? (
        <span className="mt-1 text-[10px] font-mono uppercase tracking-wide text-slate-400">
          {STATE_LABELS[state]}
        </span>
      ) : null}
    </div>
  );
}
