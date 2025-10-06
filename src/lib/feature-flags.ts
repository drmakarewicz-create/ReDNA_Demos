'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';

export type FeatureFlagKey = 'avatar' | 'offlineCache' | 'optimistic' | 'dragDrop';

export type FeatureFlags = Record<FeatureFlagKey, boolean>;

const STORAGE_KEY = '_hc_flags';
const FLAG_EVENT = 'hc-flags-updated';

const DEFAULT_FLAGS: FeatureFlags = {
  avatar: false,
  offlineCache: false,
  optimistic: false,
  dragDrop: false
};

export const FEATURE_FLAG_ORDER: FeatureFlagKey[] = ['avatar', 'offlineCache', 'optimistic', 'dragDrop'];

let cachedFlags: FeatureFlags = { ...DEFAULT_FLAGS };
let cachedHydrated = false;

function mergeFlags(
  base: FeatureFlags,
  overrides: Partial<Record<FeatureFlagKey, boolean>>
): FeatureFlags {
  return {
    ...base,
    ...overrides
  };
}

function readFlagsFromEnv(): Partial<Record<FeatureFlagKey, boolean>> {
  if (typeof process === 'undefined') {
    return {};
  }
  const raw = process.env.NEXT_PUBLIC_FLAGS;
  if (!raw) {
    return {};
  }
  return raw
    .split(',')
    .map((token) => token.trim())
    .filter(Boolean)
    .reduce<Partial<Record<FeatureFlagKey, boolean>>>((acc, token) => {
      const [key, value] = token.includes('=') ? token.split('=') : [token, '1'];
      const normalizedKey = key.trim() as FeatureFlagKey;
      if (normalizedKey in DEFAULT_FLAGS) {
        const normalizedValue = value.trim().toLowerCase();
        const enabled = !normalizedValue || normalizedValue === '1' || normalizedValue === 'true' || normalizedValue === 'on';
        acc[normalizedKey] = enabled;
      }
      return acc;
    }, {});
}

function readFlagsFromStorage(): Partial<Record<FeatureFlagKey, boolean>> {
  if (typeof window === 'undefined') {
    return {};
  }
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return {};
    }
    const parsed = JSON.parse(raw) as Record<string, unknown> | null;
    if (!parsed || typeof parsed !== 'object') {
      return {};
    }
    return Object.keys(parsed).reduce<Partial<Record<FeatureFlagKey, boolean>>>((acc, key) => {
      if (key in DEFAULT_FLAGS) {
        acc[key as FeatureFlagKey] = Boolean((parsed as Record<string, unknown>)[key]);
      }
      return acc;
    }, {});
  } catch (error) {
    console.warn('Failed to parse feature flags from localStorage', error);
    return {};
  }
}

function hydrateFlags() {
  if (cachedHydrated) {
    return;
  }
  cachedFlags = mergeFlags(cachedFlags, readFlagsFromEnv());
  cachedFlags = mergeFlags(cachedFlags, readFlagsFromStorage());
  cachedHydrated = true;
}

function persistFlags() {
  if (typeof window === 'undefined') {
    return;
  }
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(cachedFlags));
  } catch (error) {
    console.warn('Failed to persist feature flags', error);
  }
}

function broadcastChange() {
  if (typeof window === 'undefined') {
    return;
  }
  window.dispatchEvent(new Event(FLAG_EVENT));
}

export function useFeatureFlags(): {
  flags: FeatureFlags;
  hydrated: boolean;
  setFlag: (key: FeatureFlagKey, value: boolean) => void;
  resetFlags: () => void;
  activeKeys: FeatureFlagKey[];
} {
  hydrateFlags();

  const [flags, setFlags] = useState<FeatureFlags>({ ...cachedFlags });
  const [hydrated, setHydrated] = useState<boolean>(cachedHydrated);

  useEffect(() => {
    hydrateFlags();
    setFlags({ ...cachedFlags });
    setHydrated(cachedHydrated);
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }
    const handler = () => {
      setFlags({ ...cachedFlags });
      setHydrated(cachedHydrated);
    };
    window.addEventListener(FLAG_EVENT, handler);
    return () => window.removeEventListener(FLAG_EVENT, handler);
  }, []);

  const setFlag = useCallback((key: FeatureFlagKey, value: boolean) => {
    hydrateFlags();
    cachedFlags = {
      ...cachedFlags,
      [key]: value
    };
    persistFlags();
    broadcastChange();
  }, []);

  const resetFlags = useCallback(() => {
    cachedFlags = mergeFlags({ ...DEFAULT_FLAGS }, readFlagsFromEnv());
    cachedHydrated = true;
    persistFlags();
    broadcastChange();
  }, []);

  const activeKeys = useMemo(
    () => (Object.keys(flags) as FeatureFlagKey[]).filter((key) => flags[key]),
    [flags]
  );

  return { flags, hydrated, setFlag, resetFlags, activeKeys };
}

export { DEFAULT_FLAGS };
