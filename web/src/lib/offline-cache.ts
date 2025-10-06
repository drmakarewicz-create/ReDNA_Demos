'use client';

const STORAGE_PREFIX = '_hc_cache_v1';

type CachePanel = 'asks' | 'nudges' | 'snapshots';

function makeKey(panel: CachePanel, user: string): string {
  return `${STORAGE_PREFIX}:${panel}:${user.trim().toLowerCase()}`;
}

export function readCache<T>(panel: CachePanel, user: string): T | null {
  if (typeof window === 'undefined') {
    return null;
  }
  const key = makeKey(panel, user);
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) {
      return null;
    }
    return JSON.parse(raw) as T;
  } catch (error) {
    console.warn('Failed to read cached panel payload', panel, user, error);
    return null;
  }
}

export function writeCache<T>(panel: CachePanel, user: string, data: T): void {
  if (typeof window === 'undefined') {
    return;
  }
  const key = makeKey(panel, user);
  try {
    window.localStorage.setItem(key, JSON.stringify(data));
  } catch (error) {
    console.warn('Failed to persist panel payload cache', panel, user, error);
  }
}
