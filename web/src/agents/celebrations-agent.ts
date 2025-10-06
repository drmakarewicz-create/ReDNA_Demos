import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import type { PlannerAsk, UnabridgedSnapshot } from '../lib/api';

type NoticeTone = 'success' | 'info' | 'warning' | 'error';

type NoticeCallback = (message: string, tone?: NoticeTone) => void;

export type MilestoneKind =
  | 'ask_approved'
  | 'photo_extracted'
  | 'padna_render'
  | 'onboarding_init';

export interface MilestoneItem {
  id: string;
  type: MilestoneKind;
  message: string;
  detail?: string;
  ts: number;
}

interface StorageState {
  triggered: Record<MilestoneKind, boolean>;
}

const STORAGE_MILESTONES_PREFIX = '_hc_milestones:';
const STORAGE_STATE_PREFIX = '_hc_milestones_state:';
const MAX_MILESTONES = 20;

const DEFAULT_TRIGGERED: Record<MilestoneKind, boolean> = {
  ask_approved: false,
  photo_extracted: false,
  padna_render: false,
  onboarding_init: false
};

const MESSAGE_BY_KIND: Record<MilestoneKind, string> = {
  ask_approved: 'Nice! Planner is flowing.',
  photo_extracted: 'PaDNA traits captured.',
  padna_render: 'Visual preview generated.',
  onboarding_init: 'Containers created.'
};

const MILESTONE_TYPES: MilestoneKind[] = Object.keys(DEFAULT_TRIGGERED) as MilestoneKind[];

function storageKeyFor(userId: string): string {
  return `${STORAGE_MILESTONES_PREFIX}${userId}`;
}

function stateKeyFor(userId: string): string {
  return `${STORAGE_STATE_PREFIX}${userId}`;
}

function safeParse<T>(value: string | null, fallback: T): T {
  if (!value) {
    return fallback;
  }
  try {
    const parsed = JSON.parse(value) as T;
    return parsed ?? fallback;
  } catch (error) {
    console.warn('Failed to parse stored celebrations data', error);
    return fallback;
  }
}

function createMilestoneId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `ms_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
}

function normalizeState(raw: unknown): StorageState {
  if (!raw || typeof raw !== 'object') {
    return { triggered: { ...DEFAULT_TRIGGERED } };
  }
  const candidate = raw as Partial<StorageState & { lastPriorityCelebration?: number; unlocks?: unknown }>; // legacy guard
  const triggered: Record<MilestoneKind, boolean> = { ...DEFAULT_TRIGGERED };
  if (candidate.triggered && typeof candidate.triggered === 'object') {
    for (const [key, value] of Object.entries(candidate.triggered)) {
      if (MILESTONE_TYPES.includes(key as MilestoneKind) && typeof value === 'boolean') {
        triggered[key as MilestoneKind] = value;
      }
    }
  }
  return { triggered };
}

function normalizeMilestones(items: MilestoneItem[]): MilestoneItem[] {
  return items
    .map((item) => {
      if (!item || typeof item !== 'object') {
        return null;
      }
      const kind = item.type as MilestoneKind;
      if (!MILESTONE_TYPES.includes(kind)) {
        return null;
      }
      return {
        id: item.id ?? createMilestoneId(),
        type: kind,
        message: item.message ?? MESSAGE_BY_KIND[kind],
        detail: item.detail ?? undefined,
        ts: typeof item.ts === 'number' ? item.ts : Date.now()
      } satisfies MilestoneItem;
    })
    .filter(Boolean) as MilestoneItem[];
}

export function useCelebrationsAgent(params: {
  activeUserId: string;
  asks: PlannerAsk[];
  unabridged: UnabridgedSnapshot | null;
  onNotify: NoticeCallback;
}) {
  const { activeUserId, asks, unabridged, onNotify } = params;
  void asks; // props retained for backwards compatibility
  void unabridged;

  const [milestones, setMilestones] = useState<MilestoneItem[]>([]);

  const stateRef = useRef<StorageState>({ triggered: { ...DEFAULT_TRIGGERED } });
  const activeUserTrimmed = activeUserId.trim();

  const persistMilestones = useCallback(
    (next: MilestoneItem[]) => {
      if (!activeUserTrimmed || typeof window === 'undefined') {
        return;
      }
      try {
        window.localStorage.setItem(storageKeyFor(activeUserTrimmed), JSON.stringify(next));
      } catch (error) {
        console.warn('Failed to persist milestones', error);
      }
    },
    [activeUserTrimmed]
  );

  const persistState = useCallback(() => {
    if (!activeUserTrimmed || typeof window === 'undefined') {
      return;
    }
    const triggered = { ...DEFAULT_TRIGGERED, ...stateRef.current.triggered };
    stateRef.current = { triggered };
    try {
      window.localStorage.setItem(stateKeyFor(activeUserTrimmed), JSON.stringify({ triggered }));
    } catch (error) {
      console.warn('Failed to persist milestone state', error);
    }
  }, [activeUserTrimmed]);

  const clearAllMilestones = useCallback(() => {
    setMilestones(() => {
      persistMilestones([]);
      return [];
    });
  }, [persistMilestones]);

  const clearMilestone = useCallback(
    (id: string) => {
      setMilestones((prev) => {
        const next = prev.filter((item) => item.id !== id);
        persistMilestones(next);
        return next;
      });
    },
    [persistMilestones]
  );

  const pushMilestone = useCallback(
    (input: { type: MilestoneKind; message?: string; detail?: string }) => {
      const finalItem: MilestoneItem = {
        id: createMilestoneId(),
        ts: Date.now(),
        type: input.type,
        message: input.message ?? MESSAGE_BY_KIND[input.type],
        detail: input.detail
      };
      setMilestones((prev) => {
        const next = [finalItem, ...prev.filter((existing) => existing.message !== finalItem.message)];
        if (next.length > MAX_MILESTONES) {
          next.length = MAX_MILESTONES;
        }
        persistMilestones(next);
        return next;
      });
      onNotify(finalItem.message, 'success');
    },
    [onNotify, persistMilestones]
  );

  const markTriggered = useCallback(
    (kind: MilestoneKind) => {
      const current = stateRef.current.triggered ?? DEFAULT_TRIGGERED;
      if (current[kind]) {
        return false;
      }
      stateRef.current = {
        triggered: { ...DEFAULT_TRIGGERED, ...current, [kind]: true }
      };
      persistState();
      return true;
    },
    [persistState]
  );

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }
    if (!activeUserTrimmed) {
      setMilestones([]);
      stateRef.current = { triggered: { ...DEFAULT_TRIGGERED } };
      return;
    }

    const storedMilestonesRaw = safeParse<MilestoneItem[]>(
      window.localStorage.getItem(storageKeyFor(activeUserTrimmed)),
      []
    );
    const storedStateRaw = safeParse<unknown>(
      window.localStorage.getItem(stateKeyFor(activeUserTrimmed)),
      { triggered: { ...DEFAULT_TRIGGERED } }
    );

    const normalizedMilestones = normalizeMilestones(storedMilestonesRaw).slice(0, MAX_MILESTONES);
    const normalizedState = normalizeState(storedStateRaw);

    setMilestones(normalizedMilestones);
    stateRef.current = normalizedState;
  }, [activeUserTrimmed]);

  const handleAskApproved = useCallback(
    (event: Event) => {
      if (!activeUserTrimmed) {
        return;
      }
      const custom = event as CustomEvent<{ userId?: string; askId?: string }>;
      if (custom.detail?.userId?.trim() !== activeUserTrimmed) {
        return;
      }
      if (!markTriggered('ask_approved')) {
        return;
      }
      pushMilestone({ type: 'ask_approved', detail: custom.detail.askId });
    },
    [activeUserTrimmed, markTriggered, pushMilestone]
  );

  const handlePhotoExtracted = useCallback(
    (event: Event) => {
      if (!activeUserTrimmed) {
        return;
      }
      const custom = event as CustomEvent<{ userId?: string; mediaId?: string; traitCount?: number }>;
      if (custom.detail?.userId?.trim() !== activeUserTrimmed) {
        return;
      }
      if (!markTriggered('photo_extracted')) {
        return;
      }
      pushMilestone({ type: 'photo_extracted', detail: custom.detail.mediaId ?? undefined });
    },
    [activeUserTrimmed, markTriggered, pushMilestone]
  );

  const handlePadnaRender = useCallback(
    (event: Event) => {
      if (!activeUserTrimmed) {
        return;
      }
      const custom = event as CustomEvent<{ userId?: string; jobId?: string; resultFilename?: string | null }>;
      if (custom.detail?.userId?.trim() !== activeUserTrimmed) {
        return;
      }
      if (!markTriggered('padna_render')) {
        return;
      }
      const detail = custom.detail?.resultFilename ?? custom.detail?.jobId ?? undefined;
      pushMilestone({ type: 'padna_render', detail });
    },
    [activeUserTrimmed, markTriggered, pushMilestone]
  );

  const handleOnboardingInit = useCallback(
    (event: Event) => {
      if (!activeUserTrimmed) {
        return;
      }
      const custom = event as CustomEvent<{ userId?: string; label?: string | null }>;
      if (custom.detail?.userId?.trim() !== activeUserTrimmed) {
        return;
      }
      if (!markTriggered('onboarding_init')) {
        return;
      }
      pushMilestone({ type: 'onboarding_init', detail: custom.detail?.label ?? undefined });
    },
    [activeUserTrimmed, markTriggered, pushMilestone]
  );

  useEffect(() => {
    if (!activeUserTrimmed || typeof window === 'undefined') {
      return;
    }

    window.addEventListener('hc-ask-approved', handleAskApproved as EventListener);
    window.addEventListener('hc-photo-extracted', handlePhotoExtracted as EventListener);
    window.addEventListener('hc-padna-render-complete', handlePadnaRender as EventListener);
    window.addEventListener('hc-onboarding-init', handleOnboardingInit as EventListener);

    return () => {
      window.removeEventListener('hc-ask-approved', handleAskApproved as EventListener);
      window.removeEventListener('hc-photo-extracted', handlePhotoExtracted as EventListener);
      window.removeEventListener('hc-padna-render-complete', handlePadnaRender as EventListener);
      window.removeEventListener('hc-onboarding-init', handleOnboardingInit as EventListener);
    };
  }, [activeUserTrimmed, handleAskApproved, handlePhotoExtracted, handlePadnaRender, handleOnboardingInit]);

  return useMemo(
    () => ({
      milestones,
      clearMilestone,
      clearAllMilestones
    }),
    [milestones, clearMilestone, clearAllMilestones]
  );
}
