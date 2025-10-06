'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { RefObject } from 'react';
import type React from 'react';
import { fetchUsers, type UserSummary } from '../lib/api';
import { useI18n } from '../i18n/context';
import { getRecentUsers, type RecentUser } from '../lib/user-history';

export interface UserSwitcherProps {
  activeUserId: string;
  activeUserLabel?: string | null;
  onSelectUser: (user: UserSummary) => void;
  onCreateUser: (proposedId: string) => void;
  busy?: boolean;
  refreshToken?: number;
  inputRef?: RefObject<HTMLInputElement>;
  id?: string;
  className?: string;
}

const DEBOUNCE_MS = 250;

export function UserSwitcher({
  activeUserId,
  activeUserLabel,
  onSelectUser,
  onCreateUser,
  busy,
  refreshToken,
  inputRef,
  id,
  className
}: UserSwitcherProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const internalInputRef = useRef<HTMLInputElement | null>(null);
  const [inputValue, setInputValue] = useState<string>(activeUserLabel ?? activeUserId ?? '');
  const [query, setQuery] = useState<string>('');
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<UserSummary[]>([]);
  const [recentUsers, setRecentUsers] = useState<RecentUser[]>([]);
  const [highlightIndex, setHighlightIndex] = useState<number>(-1);
  const debounceTimerRef = useRef<number | null>(null);
  const pendingFetchRef = useRef<number>(0);
  const { t } = useI18n();

  useEffect(() => {
    setInputValue(activeUserLabel ?? activeUserId ?? '');
  }, [activeUserId, activeUserLabel]);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      setRecentUsers(getRecentUsers());
    }
  }, [refreshToken]);

  useEffect(() => {
    if (!inputRef) {
      return;
    }
    const mutableRef = inputRef as unknown as React.MutableRefObject<HTMLInputElement | null>;
    mutableRef.current = internalInputRef.current;
    return () => {
      if (mutableRef.current === internalInputRef.current) {
        mutableRef.current = null;
      }
    };
  }, [inputRef]);

  const loadSuggestions = useCallback(
    async (term: string) => {
      const ticket = Date.now();
      pendingFetchRef.current = ticket;
      setLoading(true);
      setError(null);
      try {
        const users = await fetchUsers(term);
        if (pendingFetchRef.current === ticket) {
          setSuggestions(users);
        }
      } catch (err) {
        if (pendingFetchRef.current === ticket) {
          setError(describeError(err));
          setSuggestions([]);
        }
      } finally {
        if (pendingFetchRef.current === ticket) {
          setLoading(false);
        }
      }
    },
    []
  );

  useEffect(() => {
    void loadSuggestions('');
  }, [loadSuggestions, refreshToken]);

  useEffect(() => {
    if (!open) {
      return;
    }
    const raw = query.trim();
    if (debounceTimerRef.current) {
      window.clearTimeout(debounceTimerRef.current);
    }
    debounceTimerRef.current = window.setTimeout(() => {
      void loadSuggestions(raw);
    }, DEBOUNCE_MS);
    return () => {
      if (debounceTimerRef.current) {
        window.clearTimeout(debounceTimerRef.current);
        debounceTimerRef.current = null;
      }
    };
  }, [loadSuggestions, open, query]);

  useEffect(() => {
    function handleClick(event: MouseEvent) {
      if (!containerRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    window.addEventListener('mousedown', handleClick);
    return () => window.removeEventListener('mousedown', handleClick);
  }, []);

  const trimmedQuery = query.trim();

  const optionsToRender = useMemo(() => {
    if (!trimmedQuery && recentUsers.length > 0) {
      // Show recent users when no query
      return recentUsers.map(ru => ({ id: ru.id, label: ru.label || ru.id, created_ts: '' }));
    }
    return suggestions.slice(0, 8);
  }, [suggestions, recentUsers, trimmedQuery]);

  const showRecentLabel = !trimmedQuery && recentUsers.length > 0 && optionsToRender.length > 0;
  const totalOptions = optionsToRender.length + 1;
  const createRowIndex = totalOptions - 1;
  const createHint = trimmedQuery
    ? t('userSwitcher.createHint', { query: trimmedQuery })
    : t('userSwitcher.createDefault');
  const showCreateSeparator = optionsToRender.length > 0 || loading || !!error;

  const handleSelect = useCallback(
    (entry: UserSummary) => {
      setInputValue(entry.label || entry.id);
      setQuery('');
      setOpen(false);
      setHighlightIndex(-1);
      onSelectUser(entry);
    },
    [onSelectUser]
  );

  const handleCreate = useCallback(() => {
    setOpen(false);
    setHighlightIndex(-1);
    onCreateUser(trimmedQuery);
  }, [onCreateUser, trimmedQuery]);

  const containerClassName = ['relative w-full sm:w-64', className]
    .filter(Boolean)
    .join(' ');

  return (
    <div id={id} ref={containerRef} className={containerClassName}>
      <div className="flex flex-col gap-1">
        <label
          id="user-switcher-label"
          htmlFor="user-switcher-input"
          className="text-[11px] uppercase tracking-wide text-slate-400"
        >
          {t('userSwitcher.label')}
        </label>
        <div className="relative flex items-center rounded-2xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 focus-within:border-cyan-400 focus-within:ring-1 focus-within:ring-cyan-400/40">
          <input
            id="user-switcher-input"
            role="combobox"
            ref={(node) => {
              internalInputRef.current = node;
              if (inputRef) {
                (inputRef as unknown as React.MutableRefObject<HTMLInputElement | null>).current = node;
              }
            }}
            className="w-full bg-transparent text-sm text-slate-100 placeholder-slate-500 focus:outline-none"
            placeholder={t('userSwitcher.placeholder')}
            value={open ? query : inputValue}
            aria-expanded={open}
            aria-controls="user-switcher-listbox"
            aria-autocomplete="list"
            aria-haspopup="listbox"
            aria-activedescendant={
              highlightIndex >= 0 && highlightIndex < totalOptions
                ? buildOptionId(highlightIndex, highlightIndex === createRowIndex)
                : undefined
            }
            onFocus={() => {
              setOpen(true);
              setQuery((prev) => (prev ? prev : inputValue));
              const startIndex = optionsToRender.length ? 0 : createRowIndex;
              setHighlightIndex(startIndex);
            }}
            onChange={(event) => {
              const value = event.target.value;
              setOpen(true);
              setQuery(value);
              setHighlightIndex(0);
            }}
            onKeyDown={(event) => {
              if (!open && (event.key === 'ArrowDown' || event.key === 'ArrowUp')) {
                setOpen(true);
                const startIndex = optionsToRender.length ? 0 : createRowIndex;
                setHighlightIndex(startIndex);
              }
              if (!open) {
                return;
              }
              if (event.key === 'ArrowDown') {
                event.preventDefault();
                setHighlightIndex((prev) => {
                  const maxIndex = totalOptions - 1;
                  const next = prev + 1;
                  return Math.min(next, maxIndex);
                });
              } else if (event.key === 'ArrowUp') {
                event.preventDefault();
                setHighlightIndex((prev) => Math.max(prev - 1, 0));
              } else if (event.key === 'Enter') {
                event.preventDefault();
                if (highlightIndex >= 0 && highlightIndex < optionsToRender.length) {
                  handleSelect(optionsToRender[highlightIndex]);
                } else if (highlightIndex === createRowIndex) {
                  handleCreate();
                }
              } else if (event.key === 'Escape') {
                event.preventDefault();
                setOpen(false);
              } else if (event.key === 'Tab') {
                setOpen(false);
              }
            }}
            disabled={busy}
            autoComplete="off"
          />
          <span className="ml-2 text-xs text-slate-500" aria-hidden="true">
            {busy ? '…' : ''}
          </span>
        </div>
      </div>
      {open ? (
        <div className="absolute z-30 mt-1 w-full rounded-2xl border border-slate-800 bg-slate-950/95 shadow-2xl">
          <div
            id="user-switcher-listbox"
            className="max-h-72 overflow-y-auto py-1"
            role="listbox"
            aria-labelledby="user-switcher-label"
          >
            {loading ? (
              <div className="px-4 py-2 text-xs text-slate-500" role="status" aria-live="polite">
                Searching…
              </div>
            ) : null}
            {!loading && error ? (
              <div className="px-4 py-2 text-xs text-rose-300" role="alert" aria-live="assertive">
                {error}
              </div>
            ) : null}
            {!loading && !error && optionsToRender.length === 0 ? (
              <div className="px-4 py-2 text-xs text-slate-500" role="status" aria-live="polite">
                No users found.
              </div>
            ) : null}
            {showRecentLabel ? (
              <div className="px-4 py-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                Recent Users
              </div>
            ) : null}
            {optionsToRender.map((user, index) => {
              const optionId = buildOptionId(index, false);
              return (
                <button
                  key={user.id}
                  id={optionId}
                  type="button"
                  role="option"
                  aria-selected={highlightIndex === index}
                  className={`flex w-full flex-col items-start gap-0.5 px-4 py-3 text-left text-sm transition ${
                    highlightIndex === index ? 'bg-cyan-500/10 text-cyan-100' : 'hover:bg-slate-800/60'
                  }`}
                  onMouseEnter={() => setHighlightIndex(index)}
                  onFocus={() => setHighlightIndex(index)}
                  onClick={() => handleSelect(user)}
                >
                  <span className="font-medium">{user.label || user.id}</span>
                  <span className="text-xs text-slate-400">{user.id}</span>
                </button>
              );
            })}
            {showCreateSeparator ? <div className="border-t border-slate-800" /> : null}
            <button
              id={buildOptionId(createRowIndex, true)}
              type="button"
              role="option"
              aria-selected={highlightIndex === createRowIndex}
              className={`flex w-full items-start justify-between gap-2 px-4 py-3 text-sm transition ${
                highlightIndex === createRowIndex ? 'bg-cyan-500/10 text-cyan-100' : 'hover:bg-cyan-500/10 text-cyan-200'
              }`}
              onMouseEnter={() => setHighlightIndex(createRowIndex)}
              onFocus={() => setHighlightIndex(createRowIndex)}
              onClick={handleCreate}
            >
              <span className="flex items-center gap-2 font-medium">
                <span aria-hidden="true">➕</span>
                Create new user...
              </span>
              <span className="text-xs text-cyan-300">{createHint}</span>
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function describeError(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return 'Unable to load users.';
}

function buildOptionId(index: number, isCreate: boolean): string {
  const suffix = isCreate ? 'create' : String(index);
  return `user-switcher-option-${suffix}`;
}
