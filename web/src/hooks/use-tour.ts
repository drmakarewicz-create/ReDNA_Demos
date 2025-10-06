'use client';

import { useCallback, useEffect, useState } from 'react';

const TOUR_STORAGE_KEY = 'hc_intro_seen';
const LEGACY_STORAGE_KEY = '_hc_intro_tour_v1';

type StoredTourState = {
  dismissed: boolean;
  dismissedAt?: string;
};

type TourState = {
  dismissed: boolean;
  hydrated: boolean;
};

function readTourState(): TourState {
  if (typeof window === 'undefined') {
    return { dismissed: false, hydrated: false };
  }
  try {
    const raw = window.localStorage.getItem(TOUR_STORAGE_KEY);
    if (raw != null) {
      const normalized = raw.trim().toLowerCase();
      return {
        dismissed: normalized === 'true' || normalized === '1',
        hydrated: true
      };
    }

    const legacy = window.localStorage.getItem(LEGACY_STORAGE_KEY);
    if (legacy) {
      let dismissed = false;
      try {
        const parsed = JSON.parse(legacy) as Partial<StoredTourState> | null;
        dismissed = Boolean(parsed?.dismissed);
      } catch (legacyError) {
        console.warn('Failed to parse legacy tour state', legacyError);
      }
      window.localStorage.removeItem(LEGACY_STORAGE_KEY);
      if (dismissed) {
        window.localStorage.setItem(TOUR_STORAGE_KEY, 'true');
      }
      return { dismissed, hydrated: true };
    }

    return { dismissed: false, hydrated: true };
  } catch (error) {
    console.warn('Failed to load tour state from localStorage', error);
    return { dismissed: false, hydrated: true };
  }
}

export function useTourState(): {
  dismissed: boolean;
  hydrated: boolean;
  markDismissed: () => void;
  reset: () => void;
} {
  const [state, setState] = useState<TourState>({ dismissed: false, hydrated: false });

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }
    const loaded = readTourState();
    setState(loaded);
  }, []);

  const markDismissed = useCallback(() => {
    setState((prev) => ({ dismissed: true, hydrated: prev.hydrated || true }));
    if (typeof window !== 'undefined') {
      try {
        window.localStorage.setItem(TOUR_STORAGE_KEY, 'true');
        window.localStorage.removeItem(LEGACY_STORAGE_KEY);
      } catch (error) {
        console.warn('Failed to persist tour dismissal', error);
      }
    }
  }, []);

  const reset = useCallback(() => {
    setState((prev) => ({ dismissed: false, hydrated: prev.hydrated || true }));
    if (typeof window !== 'undefined') {
      try {
        window.localStorage.removeItem(TOUR_STORAGE_KEY);
        window.localStorage.removeItem(LEGACY_STORAGE_KEY);
      } catch (error) {
        console.warn('Failed to reset tour state', error);
      }
    }
  }, []);

  return { dismissed: state.dismissed, hydrated: state.hydrated, markDismissed, reset };
}
