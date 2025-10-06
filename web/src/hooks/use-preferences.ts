'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';

const PREFERENCES_STORAGE_KEY = '_hc_preferences_v1';

export type ThemePreference = 'dark' | 'light';
export type LocalePreference = 'en';

export interface UserPreferences {
  streaming: boolean;
  enterToSend: boolean;
  autoScrollTranscript: boolean;
  compactDensity: boolean;
  showCoachAvatar: boolean;
  theme: ThemePreference;
  locale: LocalePreference;
  providerModel: string;
  providerTemperature: number | null;
  providerMaxTokens: number | null;
  holisticReview: boolean;
}

const DEFAULT_PREFERENCES: UserPreferences = {
  streaming: true,
  enterToSend: true,
  autoScrollTranscript: true,
  compactDensity: false,
  showCoachAvatar: true,
  theme: 'dark',
  locale: 'en',
  providerModel: '',
  providerTemperature: null,
  providerMaxTokens: null,
  holisticReview: false
};

function readPreferences(): UserPreferences {
  if (typeof window === 'undefined') {
    return DEFAULT_PREFERENCES;
  }
  try {
    const raw = window.localStorage.getItem(PREFERENCES_STORAGE_KEY);
    if (!raw) {
      return DEFAULT_PREFERENCES;
    }
    const parsed = JSON.parse(raw) as Partial<UserPreferences> | null;
    const merged = { ...DEFAULT_PREFERENCES, ...(parsed ?? {}) };
    if (typeof merged.providerModel !== 'string') {
      merged.providerModel = DEFAULT_PREFERENCES.providerModel;
    }
    const tempCandidate = merged.providerTemperature;
    if (typeof tempCandidate === 'number' && Number.isFinite(tempCandidate)) {
      merged.providerTemperature = tempCandidate;
    } else {
      merged.providerTemperature = DEFAULT_PREFERENCES.providerTemperature;
    }
    const maxTokensCandidate = merged.providerMaxTokens;
    if (typeof maxTokensCandidate === 'number' && Number.isFinite(maxTokensCandidate) && maxTokensCandidate > 0) {
      merged.providerMaxTokens = Math.trunc(maxTokensCandidate);
    } else {
      merged.providerMaxTokens = DEFAULT_PREFERENCES.providerMaxTokens;
    }
    if (typeof merged.showCoachAvatar !== 'boolean') {
      merged.showCoachAvatar = DEFAULT_PREFERENCES.showCoachAvatar;
    }
    return merged;
  } catch (error) {
    console.warn('Failed to parse preferences from localStorage', error);
    return DEFAULT_PREFERENCES;
  }
}

export function usePreferences(): {
  preferences: UserPreferences;
  updatePreference: (patch: Partial<UserPreferences>) => void;
  resetPreferences: () => void;
  hydrated: boolean;
} {
  const [preferences, setPreferences] = useState<UserPreferences>(DEFAULT_PREFERENCES);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }
    const loaded = readPreferences();
    setPreferences(loaded);
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated || typeof window === 'undefined') {
      return;
    }
    try {
      window.localStorage.setItem(PREFERENCES_STORAGE_KEY, JSON.stringify(preferences));
    } catch (error) {
      console.warn('Failed to persist preferences', error);
    }
  }, [preferences, hydrated]);

  useEffect(() => {
    if (!hydrated || typeof document === 'undefined') {
      return;
    }
    document.body.dataset.hcTheme = preferences.theme;
  }, [preferences.theme, hydrated]);

  useEffect(() => {
    if (!hydrated || typeof document === 'undefined') {
      return;
    }
    document.body.dataset.hcDensity = preferences.compactDensity ? 'compact' : 'comfortable';
  }, [preferences.compactDensity, hydrated]);

  useEffect(() => {
    if (!hydrated || typeof document === 'undefined') {
      return;
    }
    document.documentElement.lang = preferences.locale;
  }, [preferences.locale, hydrated]);

  const updatePreference = useCallback((patch: Partial<UserPreferences>) => {
    setPreferences((prev) => ({ ...prev, ...patch }));
  }, []);

  const resetPreferences = useCallback(() => {
    setPreferences(DEFAULT_PREFERENCES);
  }, []);

  const memoized = useMemo(
    () => ({ preferences, updatePreference, resetPreferences, hydrated }),
    [preferences, updatePreference, resetPreferences, hydrated]
  );

  return memoized;
}

export { DEFAULT_PREFERENCES };
