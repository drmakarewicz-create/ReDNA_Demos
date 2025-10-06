// web/src/lib/user-history.ts
/**
 * User history utilities for localStorage persistence and deep-linking
 */

const USER_HISTORY_KEY = 'redna_recent_users';
const MAX_RECENT_USERS = 3;

export interface RecentUser {
  id: string;
  label?: string;
  lastUsed: number;
}

/**
 * Get recent users from localStorage
 */
export function getRecentUsers(): RecentUser[] {
  if (typeof window === 'undefined') return [];

  try {
    const stored = localStorage.getItem(USER_HISTORY_KEY);
    if (!stored) return [];

    const parsed = JSON.parse(stored);
    if (!Array.isArray(parsed)) return [];

    return parsed.filter((item): item is RecentUser =>
      item && typeof item === 'object' && typeof item.id === 'string'
    );
  } catch {
    return [];
  }
}

/**
 * Add or update a user in recent history
 */
export function addRecentUser(userId: string, label?: string): void {
  if (typeof window === 'undefined') return;

  try {
    const recent = getRecentUsers();

    // Remove if already exists
    const filtered = recent.filter(u => u.id !== userId);

    // Add to front
    const updated: RecentUser[] = [
      { id: userId, label, lastUsed: Date.now() },
      ...filtered
    ].slice(0, MAX_RECENT_USERS);

    localStorage.setItem(USER_HISTORY_KEY, JSON.stringify(updated));
  } catch {
    // Ignore localStorage errors
  }
}

/**
 * Clear recent users history
 */
export function clearRecentUsers(): void {
  if (typeof window === 'undefined') return;

  try {
    localStorage.removeItem(USER_HISTORY_KEY);
  } catch {
    // Ignore errors
  }
}

/**
 * Get user ID from URL query parameter
 */
export function getUserFromUrl(): string | null {
  if (typeof window === 'undefined') return null;

  try {
    const params = new URLSearchParams(window.location.search);
    return params.get('user');
  } catch {
    return null;
  }
}

/**
 * Update URL with user ID (without page reload)
 */
export function setUserInUrl(userId: string | null): void {
  if (typeof window === 'undefined') return;

  try {
    const url = new URL(window.location.href);

    if (userId) {
      url.searchParams.set('user', userId);
    } else {
      url.searchParams.delete('user');
    }

    window.history.replaceState({}, '', url.toString());
  } catch {
    // Ignore errors
  }
}
