'use client';

import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import type { RefObject } from 'react';
import type React from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import { submitTopicPreference, type ObservationAggregates } from '../lib/api';
import { updateVirtualizerMetrics, removeVirtualizerMetrics } from '../lib/perf-hud';
import { useI18n } from '../i18n/context';

export type TranscriptEntry = {
  role: 'assistant' | 'member';
  text: string;
  persona?: string;
  ts: number;
  clientMessageId?: string;
  pending?: boolean;
  streaming?: boolean;
  cancelled?: boolean;
  source?: 'client-cache' | 'live';
};

type CachedTranscriptEntry = {
  role: TranscriptEntry['role'];
  text: string;
  persona?: string;
  ts: number;
  clientMessageId?: string;
  source: 'client-cache';
};

type CachedTranscriptPayload = {
  version: number;
  entries: CachedTranscriptEntry[];
};

const COOL_IT_TTL_DAYS = 7;

type CoolItRule = {
  key: string;
  pattern: RegExp;
};

const COOL_IT_RULES: CoolItRule[] = [
  { key: 'topic.padna.hair', pattern: /\bhair|bangs?|fringe|curls?\b/i },
  { key: 'topic.photo.angles', pattern: /\bangle|angles|pose|posing|framing\b/i },
  { key: 'topic.padna.palette', pattern: /\bpalette|color|colour|tone|hue\b/i },
  { key: 'topic.core.boundary', pattern: /\bpush\s?back|too\s+much|ease\s+up|slow\s+down\b/i },
];

const COOL_IT_PERSONA_DEFAULTS: { match: RegExp; key: string }[] = [
  { match: /photo/, key: 'topic.photo.general' },
  { match: /padna|visual|style/, key: 'topic.padna.general' },
  { match: /relationship|rc/, key: 'topic.relationship.general' },
  { match: /coach/, key: 'topic.head_coach.general' },
];

function shouldOfferCoolIt(turn: TranscriptEntry): boolean {
  if (turn.role !== 'assistant') return false;
  if (!turn.text || !turn.text.trim()) return false;
  if (turn.pending || turn.cancelled || turn.streaming) return false;
  return /[?]/.test(turn.text) || /\b(can|could|would|should)\b/i.test(turn.text);
}

function inferCoolItTopicKey(turn: TranscriptEntry): string {
  const text = turn.text ?? '';
  for (const rule of COOL_IT_RULES) {
    if (rule.pattern.test(text)) {
      return rule.key;
    }
  }
  const persona = turn.persona?.toLowerCase() ?? '';
  for (const personaRule of COOL_IT_PERSONA_DEFAULTS) {
    if (personaRule.match.test(persona)) {
      return personaRule.key;
    }
  }
  return 'topic.head_coach.general';
}

const CACHE_STORAGE_PREFIX = '_hc_transcript_cache:';
const CACHE_STORAGE_VERSION = 1;
const CACHE_MAX_ENTRIES = 50;

function storageKey(userId: string): string {
  return `${CACHE_STORAGE_PREFIX}${userId}`;
}

function buildDefaultTranscript(): TranscriptEntry[] {
  // NORTHSTAR PHASE 2: Empty transcript by default
  // No more "keep momentum going" message for new users
  // Let users start naturally or have onboarding populate their profile silently
  return [];
}

function loadCachedTranscript(userId: string): TranscriptEntry[] | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(storageKey(userId));
    if (!raw) return null;
    const payload: CachedTranscriptPayload = JSON.parse(raw);
    if (!payload || payload.version !== CACHE_STORAGE_VERSION || !Array.isArray(payload.entries)) return null;
    return payload.entries.map((entry) => ({
      role: entry.role,
      text: entry.text,
      persona: entry.persona,
      ts: entry.ts,
      clientMessageId: entry.clientMessageId,
      pending: false,
      streaming: false,
      cancelled: false,
      source: 'client-cache',
    }));
  } catch (error) {
    console.warn('Failed to read transcript cache', error);
    return null;
  }
}

function saveCachedTranscript(userId: string, entries: TranscriptEntry[]): void {
  if (typeof window === 'undefined') return;
  try {
    const trimmed = userId.trim();
    if (!trimmed) return;
    const sanitized = entries
      .slice(-CACHE_MAX_ENTRIES)
      .map<CachedTranscriptEntry>((entry) => ({
        role: entry.role,
        text: entry.text,
        persona: entry.persona,
        ts: entry.ts,
        clientMessageId: entry.clientMessageId,
        source: 'client-cache',
      }));
    const payload: CachedTranscriptPayload = { version: CACHE_STORAGE_VERSION, entries: sanitized };
    window.localStorage.setItem(storageKey(trimmed), JSON.stringify(payload));
  } catch (error) {
    console.warn('Failed to persist transcript cache', error);
  }
}

function clearCachedTranscript(userId: string): void {
  if (typeof window === 'undefined') return;
  try {
    const trimmed = userId.trim();
    if (!trimmed) return;
    window.localStorage.removeItem(storageKey(trimmed));
  } catch (error) {
    console.warn('Failed to clear transcript cache', error);
  }
}

const PIN_STORAGE_PREFIX = '_hc_transcript_pins:';
const PIN_STORAGE_VERSION = 1;

type StoredPinsPayload = {
  version: number;
  pins: string[];
};

function pinStorageKey(userId: string): string {
  return `${PIN_STORAGE_PREFIX}${userId}`;
}

function loadPinnedEntries(userId: string): Set<string> {
  if (typeof window === 'undefined') return new Set();
  try {
    const raw = window.localStorage.getItem(pinStorageKey(userId));
    if (!raw) return new Set();
    const payload = JSON.parse(raw) as StoredPinsPayload;
    if (!payload || payload.version !== PIN_STORAGE_VERSION || !Array.isArray(payload.pins)) return new Set();
    return new Set(payload.pins.filter((pin) => typeof pin === 'string' && pin.trim().length > 0));
  } catch (error) {
    console.warn('Failed to load transcript pins', error);
    return new Set();
  }
}

function savePinnedEntries(userId: string, pins: Set<string>): void {
  if (typeof window === 'undefined') return;
  try {
    const trimmed = userId.trim();
    if (!trimmed) return;
    const payload: StoredPinsPayload = { version: PIN_STORAGE_VERSION, pins: Array.from(pins) };
    window.localStorage.setItem(pinStorageKey(trimmed), JSON.stringify(payload));
  } catch (error) {
    console.warn('Failed to persist transcript pins', error);
  }
}

function transcriptEntryKey(entry: TranscriptEntry): string {
  const baseId = entry.clientMessageId ?? '';
  const ts = typeof entry.ts === 'number' ? entry.ts : Number(entry.ts ?? 0);
  const persona = entry.persona ?? entry.role ?? 'turn';
  if (baseId) return `${baseId}|${persona}`;
  return `${persona}|${ts}|${(entry.text ?? '').slice(0, 32)}`;
}

type StreamDetail = {
  clientMessageId: string;
  delta: string;
  personaLabel: string;
};

interface TranscriptPanelProps {
  aggregates: ObservationAggregates | null;
  loading?: boolean;
  activeUserId: string;
  onClearChat?: (userId: string) => void;
  autoScroll?: boolean;
  density?: 'comfortable' | 'compact';
  searchInputRef?: RefObject<HTMLInputElement>;
  onQuickSnapshot?: (userId: string) => Promise<void> | void;
  quickSnapshotPending?: boolean;
  resetToken?: number;
  fillHeight?: boolean; // When true, uses flex-1 instead of h-[60vh]
}

export interface TranscriptPanelHandle {
  focusSearch: () => boolean;
  togglePinFocused: () => 'pinned' | 'unpinned' | null;
  togglePinnedFilter: () => boolean;
  scrollToBottom: () => void;
}

export const TranscriptPanel = forwardRef<TranscriptPanelHandle, TranscriptPanelProps>(function TranscriptPanel(
  {
    aggregates,
    loading,
    activeUserId,
    onClearChat,
    autoScroll = true,
    density = 'comfortable',
    searchInputRef,
    onQuickSnapshot,
    quickSnapshotPending = false,
    resetToken = 0,
    fillHeight = false,
  }: TranscriptPanelProps,
  ref
) {
  const { t } = useI18n();
  const [entries, setEntries] = useState<TranscriptEntry[]>(() => buildDefaultTranscript());
  const [cacheNotice, setCacheNotice] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [pinnedKeys, setPinnedKeys] = useState<Set<string>>(() => new Set());
  const [showPinnedOnly, setShowPinnedOnly] = useState(false);
  const [searchInput, setSearchInput] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [activeMatchIndex, setActiveMatchIndex] = useState<number | null>(null);
  const [focusedIndex, setFocusedIndex] = useState<number | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [headerStatus, setHeaderStatus] = useState<{ message: string; tone: 'info' | 'success' | 'error' } | null>(null);
  const [coolItPending, setCoolItPending] = useState<string | null>(null);
  const [coolItApplied, setCoolItApplied] = useState<Set<string>>(() => new Set());
  const [copiedCodeBlockId, setCopiedCodeBlockId] = useState<string | null>(null);
  const [isHydrated, setIsHydrated] = useState(false);
  const [isAtBottom, setIsAtBottom] = useState(true);

  const copyTimerRef = useRef<number | null>(null);
  const codeCopyTimerRef = useRef<number | null>(null);
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);
  const headerRef = useRef<HTMLElement | null>(null);
  const searchInputInternalRef = useRef<HTMLInputElement | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const headerStatusTimerRef = useRef<number | null>(null);
  const codeBlockIndexRef = useRef(0);
  const lastResetTokenRef = useRef<number | null>(null);
  const initialScrollDoneRef = useRef(false);

  const compact = density === 'compact';
  const estimateSize = useCallback(() => (compact ? 108 : 134), [compact]);
  const hasActiveUser = activeUserId.trim().length > 0;

  // ⚠️ LEFT PANE SANCTITY RULE ⚠️
  // Disable virtualization in fillHeight mode to prevent blinking/doubling
  // DO NOT change this logic without reading LEFT_PANE_SANCTITY_RULE.md
  const shouldVirtualize = !fillHeight;

  const isNearBottom = useCallback(() => {
    const element = scrollContainerRef.current;
    if (!element) return true;
    let composerH = Number.parseFloat(
      getComputedStyle(element).getPropertyValue('--composer-h')
    );
    if (!Number.isFinite(composerH)) {
      composerH = Number.parseFloat(
        getComputedStyle(document.documentElement).getPropertyValue('--composer-h')
      );
    }
    if (!Number.isFinite(composerH)) {
      composerH = 72;
    }
    const cushion = 24;
    return element.scrollHeight - element.scrollTop - element.clientHeight <= composerH + cushion;
  }, []);

  const handleQuickSnapshotAction = useCallback(async () => {
    if (!onQuickSnapshot || quickSnapshotPending || !hasActiveUser) {
      return;
    }
    setMenuOpen(false);
    try {
      await onQuickSnapshot(activeUserId);
    } catch (error) {
      console.warn('Quick snapshot failed', error);
    }
  }, [activeUserId, hasActiveUser, onQuickSnapshot, quickSnapshotPending]);

  const registerSearchInput = useCallback(
    (node: HTMLInputElement | null) => {
      searchInputInternalRef.current = node;
      if (searchInputRef) {
        (searchInputRef as unknown as React.MutableRefObject<HTMLInputElement | null>).current = node;
      }
    },
    [searchInputRef]
  );

  const entryMeta = useMemo(
    () => entries.map((entry) => ({ entry, key: transcriptEntryKey(entry) })),
    [entries]
  );

  const displayMeta = useMemo(() => {
    if (!showPinnedOnly) return entryMeta;
    return entryMeta.filter(({ key }) => pinnedKeys.has(key));
  }, [entryMeta, showPinnedOnly, pinnedKeys]);

  const displayEntries = useMemo(() => displayMeta.map((item) => item.entry), [displayMeta]);

  useEffect(() => {
    setIsHydrated(true);
  }, []);

  // Measure header height and set CSS variable
  useEffect(() => {
    const header = headerRef.current;
    const container = scrollContainerRef.current;
    if (!header || !container) return;

    const updateHeaderHeight = () => {
      const height = header.offsetHeight;
      container.style.setProperty('--transcript-header-h', `${height}px`);
    };

    updateHeaderHeight();

    const observer = new ResizeObserver(updateHeaderHeight);
    observer.observe(header);

    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const element = scrollContainerRef.current;
    if (!element) return;

    const handleScroll = () => {
      setIsAtBottom(isNearBottom());
    };

    handleScroll();

    element.addEventListener('scroll', handleScroll, { passive: true });
    return () => {
      element.removeEventListener('scroll', handleScroll);
    };
  }, [isNearBottom]);

  const virtualizer = useVirtualizer({
    count: isHydrated && shouldVirtualize ? displayEntries.length : 0,
    getScrollElement: () => scrollContainerRef.current,
    estimateSize,
    overscan: 6,
    getItemKey: (index) => displayMeta[index]?.key ?? `${displayEntries[index]?.role ?? 'turn'}-${index}`,
  });

  const virtualItems = isHydrated && shouldVirtualize ? virtualizer.getVirtualItems() : [];
  const virtualItemsCount = virtualItems.length;
  const totalDisplayEntries = displayEntries.length;

  const performScrollToBottom = useCallback(
    (behavior: ScrollBehavior = 'auto') => {
      const element = scrollContainerRef.current;
      if (!element) return;
      const lastIndex = displayEntries.length - 1;
      if (lastIndex >= 0) {
        virtualizer.scrollToIndex(lastIndex, { align: 'end' });
      }

      const flush = () => {
        const el = scrollContainerRef.current;
        if (!el) return;
        if (behavior === 'auto') {
          el.scrollTop = el.scrollHeight;
        } else {
          el.scrollTo({ top: el.scrollHeight, behavior });
        }
        setIsAtBottom(true);
      };

      requestAnimationFrame(() => {
        requestAnimationFrame(flush);
      });
    },
    [displayEntries.length, virtualizer]
  );

  const scrollToBottom = useCallback(() => {
    performScrollToBottom('auto');
  }, [performScrollToBottom]);

  useEffect(() => {
    const element = scrollContainerRef.current;
    if (!element) return;
    setIsAtBottom(isNearBottom());
  }, [displayEntries.length, isNearBottom]);

  useEffect(() => {
    if (typeof ResizeObserver === 'undefined') return;
    const element = scrollContainerRef.current;
    if (!element) return;

    const observer = new ResizeObserver(() => {
      const nearBottom = isNearBottom();
      setIsAtBottom(nearBottom);
      if (!autoScroll || showPinnedOnly || searchTerm) return;
      if (nearBottom) {
        performScrollToBottom('auto');
      }
    });

    observer.observe(element);
    return () => observer.disconnect();
  }, [autoScroll, showPinnedOnly, searchTerm, isNearBottom, performScrollToBottom]);

  useEffect(() => {
    if (focusedIndex == null) return;
    if (focusedIndex < 0 || focusedIndex >= displayEntries.length) {
      setFocusedIndex(displayEntries.length > 0 ? Math.min(focusedIndex, displayEntries.length - 1) : null);
    }
  }, [displayEntries, focusedIndex]);

  useEffect(() => {
    if (!isHydrated) return;
    updateVirtualizerMetrics('transcript', {
      total: totalDisplayEntries,
      visible: virtualItemsCount,
    });
  }, [isHydrated, totalDisplayEntries, virtualItemsCount]);

  useEffect(() => {
    return () => {
      removeVirtualizerMetrics('transcript');
    };
  }, []);

  useEffect(() => {
    return () => {
      if (copyTimerRef.current) {
        window.clearTimeout(copyTimerRef.current);
        copyTimerRef.current = null;
      }
      if (headerStatusTimerRef.current) {
        window.clearTimeout(headerStatusTimerRef.current);
        headerStatusTimerRef.current = null;
      }
      if (codeCopyTimerRef.current) {
        window.clearTimeout(codeCopyTimerRef.current);
        codeCopyTimerRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    initialScrollDoneRef.current = false;
    if (typeof window === 'undefined') {
      setEntries(buildDefaultTranscript());
      setCacheNotice(false);
      setFocusedIndex(null);
      return;
    }
    const trimmed = activeUserId.trim();
    if (!trimmed) {
      setEntries(buildDefaultTranscript());
      setCacheNotice(false);
      setFocusedIndex(null);
      return;
    }
    const cached = loadCachedTranscript(trimmed);
    if (cached && cached.length) {
      setEntries(cached);
      setCacheNotice(true);
      setFocusedIndex(null);
    } else {
      setEntries(buildDefaultTranscript());
      setCacheNotice(false);
      setFocusedIndex(null);
    }
  }, [activeUserId]);

  useEffect(() => {
    setCoolItApplied(new Set());
    setCoolItPending(null);
  }, [activeUserId]);

  useEffect(() => {
    const trimmed = activeUserId.trim();
    if (!trimmed) {
      setPinnedKeys(new Set());
      setShowPinnedOnly(false);
      setSearchInput('');
      setSearchTerm('');
      setActiveMatchIndex(null);
      setFocusedIndex(null);
      return;
    }
    setPinnedKeys(loadPinnedEntries(trimmed));
    setShowPinnedOnly(false);
    setSearchInput('');
    setSearchTerm('');
    setActiveMatchIndex(null);
    setFocusedIndex(null);
  }, [activeUserId]);

  useEffect(() => {
    setMenuOpen(false);
  }, [activeUserId]);

  useEffect(() => {
    const trimmed = activeUserId.trim();
    if (!trimmed) return;
    saveCachedTranscript(trimmed, entries);
  }, [entries, activeUserId]);

  useEffect(() => {
    const trimmed = activeUserId.trim();
    if (!trimmed) return;
    savePinnedEntries(trimmed, pinnedKeys);
  }, [pinnedKeys, activeUserId]);

  useEffect(() => {
    setPinnedKeys((prev) => {
      if (prev.size === 0) return prev;
      const valid = new Set<string>();
      for (const { key } of entryMeta) {
        if (prev.has(key)) valid.add(key);
      }
      if (valid.size === prev.size) {
        let identical = true;
        for (const key of prev) {
          if (!valid.has(key)) {
            identical = false;
            break;
          }
        }
        if (identical) return prev;
      }
      return valid;
    });
  }, [entryMeta]);

  useEffect(() => {
    if (showPinnedOnly && pinnedKeys.size === 0) setShowPinnedOnly(false);
  }, [showPinnedOnly, pinnedKeys]);

  useEffect(() => {
    if (!menuOpen) return;

    const handlePointer = (event: MouseEvent | TouchEvent) => {
      if (!menuRef.current) return;
      const target = event.target as Node | null;
      if (target && menuRef.current.contains(target)) return;
      setMenuOpen(false);
    };

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setMenuOpen(false);
      }
    };

    document.addEventListener('mousedown', handlePointer);
    document.addEventListener('touchstart', handlePointer, { passive: true });
    window.addEventListener('keydown', handleEscape);

    return () => {
      document.removeEventListener('mousedown', handlePointer);
      document.removeEventListener('touchstart', handlePointer);
      window.removeEventListener('keydown', handleEscape);
    };
  }, [menuOpen]);

  useLayoutEffect(() => {
    if (!isHydrated) return;
    if (initialScrollDoneRef.current) return;
    performScrollToBottom('auto');
    initialScrollDoneRef.current = true;
  }, [isHydrated, performScrollToBottom]);

  useLayoutEffect(() => {
    if (!isHydrated) return;
    if (!autoScroll || showPinnedOnly || searchTerm) return;
    if (!isAtBottom) return;

    const schedule = () => {
      requestAnimationFrame(() => {
        performScrollToBottom('auto');
      });
    };

    if (typeof queueMicrotask === 'function') {
      queueMicrotask(schedule);
    } else {
      schedule();
    }
  }, [
    displayEntries.length,
    isHydrated,
    autoScroll,
    showPinnedOnly,
    searchTerm,
    isAtBottom,
    performScrollToBottom,
  ]);

  useEffect(() => {
    type LocalDetail = {
      entry: TranscriptEntry;
      clientMessageId: string;
      personaLabel: string;
      streaming?: boolean;
    };

    type SuccessDetail = {
      clientMessageId: string;
      apiMessageId: string;
      message: { text: string; ts: number; personaLabel: string };
    };

    type ErrorDetail = { clientMessageId: string; error: string };
    type CancelDetail = { clientMessageId: string };

    function handleLocalMessage(event: Event) {
      const custom = event as CustomEvent<LocalDetail>;
      if (!custom.detail?.entry) return;
      const { entry, clientMessageId, personaLabel, streaming } = custom.detail;
      setCacheNotice(false);
      setEntries((prev) => {
        const baseEntry: TranscriptEntry = {
          ...entry,
          clientMessageId,
          source: 'client-cache',
        };
        const echoEntry: TranscriptEntry = {
          role: 'assistant',
          persona: personaLabel,
          text: streaming ? '…' : buildEchoReply(entry.text),
          ts: Date.now(),
          clientMessageId,
          pending: true,
          streaming: Boolean(streaming),
          cancelled: false,
          source: 'client-cache',
        };
        const next: TranscriptEntry[] = [...prev, baseEntry, echoEntry];
        return next.length > 30 ? (next.slice(-30) as TranscriptEntry[]) : next;
      });
      // Scroll to bottom after user sends message
      // Only scroll the transcript panel internally, don't scroll the page
      window.requestAnimationFrame(() => {
        scrollToBottom();
      });
    }

    function handleSuccess(event: Event) {
      const custom = event as CustomEvent<SuccessDetail>;
      if (!custom.detail) return;
      setCacheNotice(false);
      setEntries((prev) => {
        let found = false;
        const next: TranscriptEntry[] = prev.map((entry) => {
          if (
            entry.role === 'assistant' &&
            entry.clientMessageId &&
            entry.clientMessageId === custom.detail.clientMessageId
          ) {
            found = true;
            return {
              ...entry,
              text: custom.detail.message.text,
              persona: custom.detail.message.personaLabel,
              ts: custom.detail.message.ts,
              pending: false,
              streaming: false,
              cancelled: false,
              source: 'live',
            };
          }
          return entry;
        });
        if (!found) {
          const appended: TranscriptEntry[] = [
            ...next,
            {
              role: 'assistant',
              persona: custom.detail.message.personaLabel,
              text: custom.detail.message.text,
              ts: custom.detail.message.ts,
              clientMessageId: custom.detail.clientMessageId,
              pending: false,
              streaming: false,
              cancelled: false,
              source: 'live',
            },
          ];
          return appended.length > 30 ? (appended.slice(-30) as TranscriptEntry[]) : appended;
        }
        return next;
      });
    }

    function handleError(event: Event) {
      const custom = event as CustomEvent<ErrorDetail>;
      if (!custom.detail) return;
      setEntries((prev) =>
        prev.map((entry) =>
          entry.role === 'assistant' && entry.clientMessageId === custom.detail.clientMessageId
            ? { ...entry, pending: false, streaming: false }
            : entry
        )
      );
    }

    function handleCancel(event: Event) {
      const custom = event as CustomEvent<CancelDetail>;
      if (!custom.detail?.clientMessageId) return;
      setEntries((prev) =>
        prev.map((entry) =>
          entry.role === 'assistant' && entry.clientMessageId === custom.detail.clientMessageId
            ? {
                ...entry,
                pending: false,
                streaming: false,
                cancelled: true,
                text: entry.text && entry.text !== '…' ? entry.text : 'Response cancelled.',
              }
            : entry
        )
      );
    }

    function handleStream(event: Event) {
      const custom = event as CustomEvent<StreamDetail>;
      if (!custom.detail) return;
      setCacheNotice(false);
      setEntries((prev) =>
        prev.map((entry) => {
          if (
            entry.role === 'assistant' &&
            entry.clientMessageId === custom.detail.clientMessageId &&
            entry.pending
          ) {
            const existing = entry.text === '…' ? '' : entry.text ?? '';
            return {
              ...entry,
              text: existing + custom.detail.delta,
              persona: entry.persona ?? custom.detail.personaLabel,
              streaming: true,
              source: 'live',
            };
          }
          return entry;
        })
      );
    }

    const localListener: EventListener = handleLocalMessage as EventListener;
    const successListener: EventListener = handleSuccess as EventListener;
    const errorListener: EventListener = handleError as EventListener;
    const streamListener: EventListener = handleStream as EventListener;
    const cancelListener: EventListener = handleCancel as EventListener;

    window.addEventListener('hc-local-message', localListener);
    window.addEventListener('hc-chat-success', successListener);
    window.addEventListener('hc-chat-error', errorListener);
    window.addEventListener('hc-chat-stream', streamListener);
    window.addEventListener('hc-chat-cancelled', cancelListener);

    return () => {
      window.removeEventListener('hc-local-message', localListener);
      window.removeEventListener('hc-chat-success', successListener);
      window.removeEventListener('hc-chat-error', errorListener);
      window.removeEventListener('hc-chat-stream', streamListener);
      window.removeEventListener('hc-chat-cancelled', cancelListener);
    };
  }, [scrollToBottom]);

  useEffect(() => {
    if (!searchInput.trim()) {
      setSearchTerm('');
      return;
    }
    const handle = window.setTimeout(() => {
      setSearchTerm(searchInput.trim());
    }, 200);
    return () => window.clearTimeout(handle);
  }, [searchInput]);

  const searchMatches = useMemo(() => {
    if (!searchTerm) return [] as number[];
    const term = searchTerm.toLowerCase();
    const matches: number[] = [];
    displayEntries.forEach((entry, index) => {
      if ((entry.text ?? '').toLowerCase().includes(term)) matches.push(index);
    });
    return matches;
  }, [displayEntries, searchTerm]);

  const matchSet = useMemo(() => new Set(searchMatches), [searchMatches]);
  const activeMatchPosition = activeMatchIndex != null ? searchMatches[activeMatchIndex] ?? null : null;
  const activeMatchDisplay = activeMatchIndex != null ? activeMatchIndex + 1 : searchMatches.length > 0 ? 1 : 0;

  const formatRelativeTime = useCallback((timestamp: number) => {
    if (!timestamp || !Number.isFinite(timestamp)) return 'just now';
    const rt = new Intl.RelativeTimeFormat('en', { numeric: 'auto' });
    const now = Date.now();
    const diffMs = timestamp - now;
    const sec = Math.round(diffMs / 1000);
    if (!Number.isFinite(sec) || Math.abs(sec) < 5) return 'just now';
    if (Math.abs(sec) < 60) return rt.format(sec, 'seconds');
    const min = Math.round(diffMs / 60000);
    if (!Number.isFinite(min)) return 'just now';
    if (Math.abs(min) < 60) return rt.format(min, 'minutes');
    const hr = Math.round(diffMs / 3600000);
    if (!Number.isFinite(hr)) return 'just now';
    if (Math.abs(hr) < 24) return rt.format(hr, 'hours');
    const day = Math.round(diffMs / 86400000);
    if (!Number.isFinite(day)) return 'just now';
    return rt.format(day, 'days');
  }, []);

  const togglePinByIndex = useCallback(
    (index: number): 'pinned' | 'unpinned' | null => {
      const target = displayMeta[index];
      if (!target) return null;
      let result: 'pinned' | 'unpinned' = 'pinned';
      setPinnedKeys((prev) => {
        const next = new Set(prev);
        if (next.has(target.key)) {
          next.delete(target.key);
          result = 'unpinned';
        } else {
          next.add(target.key);
        }
        return next;
      });
      setFocusedIndex(index);
      return result;
    },
    [displayMeta]
  );

  const togglePinFocused = useCallback((): 'pinned' | 'unpinned' | null => {
    if (focusedIndex == null) return null;
    return togglePinByIndex(focusedIndex);
  }, [focusedIndex, togglePinByIndex]);

  const togglePinnedFilter = useCallback(() => {
    if (!showPinnedOnly && pinnedKeys.size === 0) return false;
    setShowPinnedOnly((prev) => (pinnedKeys.size === 0 ? false : !prev));
    return true;
  }, [pinnedKeys.size, showPinnedOnly]);

  const showHeaderStatus = useCallback((message: string, tone: 'info' | 'success' | 'error' = 'success') => {
    if (headerStatusTimerRef.current) {
      window.clearTimeout(headerStatusTimerRef.current);
      headerStatusTimerRef.current = null;
    }
    setHeaderStatus({ message, tone });
    headerStatusTimerRef.current = window.setTimeout(() => {
      setHeaderStatus(null);
      headerStatusTimerRef.current = null;
    }, 2500);
  }, []);

  const downloadBlob = useCallback((blob: Blob, fileName: string) => {
    if (typeof window === 'undefined' || typeof document === 'undefined') return;
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = fileName;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    URL.revokeObjectURL(url);
  }, []);

  const handleExport = useCallback(
    (format: 'json' | 'csv') => {
      setMenuOpen(false);
      const trimmedUser = activeUserId.trim();
      if (entries.length === 0) {
        showHeaderStatus('No transcript entries to export.', 'info');
        return;
      }

      const safeUser = (trimmedUser || 'transcript').replace(/[^A-Za-z0-9_-]+/g, '-');
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
      const fileBase = `${safeUser}_${timestamp}`;

      try {
        if (format === 'json') {
          const normalized = entries.map((entry) => ({
            ts: entry.ts,
            role: entry.role,
            persona: entry.persona ?? null,
            text: entry.text ?? '',
          }));
          const blob = new Blob([JSON.stringify(normalized, null, 2)], { type: 'application/json' });
          downloadBlob(blob, `${fileBase}.json`);
          showHeaderStatus(`Transcript exported (${entries.length} entries) as JSON.`, 'success');
        } else {
          const header = ['ts', 'role', 'persona', 'text'];
          const escapeCsv = (value: unknown) => {
            const str = value == null ? '' : String(value);
            return `"${str.replace(/"/g, '""')}"`;
          };
          const rows = entries.map((entry) => [
            entry.ts,
            entry.role,
            entry.persona ?? '',
            entry.text ?? '',
          ]);
          const csv = [header, ...rows]
            .map((row) => row.map((cell) => escapeCsv(cell)).join(','))
            .join('\r\n');
          const blob = new Blob([csv], { type: 'text/csv' });
          downloadBlob(blob, `${fileBase}.csv`);
          showHeaderStatus(`Transcript exported (${entries.length} entries) as CSV.`, 'success');
        }
      } catch (error) {
        console.error('Failed to export transcript', error);
        showHeaderStatus('Failed to export transcript.', 'error');
      }
    },
    [activeUserId, downloadBlob, entries, showHeaderStatus]
  );

  const handleCopyPinned = useCallback(async () => {
    setMenuOpen(false);
    const pinnedEntries = entryMeta.filter(({ key }) => pinnedKeys.has(key)).map(({ entry }) => entry);
    if (pinnedEntries.length === 0) {
      showHeaderStatus('No pinned entries to copy.', 'info');
      return;
    }

    const markdownSections = pinnedEntries.map((entry) => {
      const persona = entry.persona ?? (entry.role === 'assistant' ? 'Head Coach' : 'Member');
      const timestamp = new Date(entry.ts).toLocaleString();
      const body = entry.text?.trim() ? entry.text.trim() : '_No content_';
      return `### ${persona} (${timestamp})\n\n${body}`;
    });

    const markdown = markdownSections.join('\n\n');

    try {
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(markdown);
      } else if (typeof document !== 'undefined') {
        const textarea = document.createElement('textarea');
        textarea.value = markdown;
        textarea.setAttribute('readonly', '');
        textarea.style.position = 'absolute';
        textarea.style.left = '-9999px';
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
      } else {
        throw new Error('Clipboard API unavailable');
      }
      showHeaderStatus(`Pinned transcript copied (${pinnedEntries.length} entries).`, 'success');
    } catch (error) {
      console.error('Failed to copy pinned transcript', error);
      showHeaderStatus('Failed to copy pinned transcript.', 'error');
    }
  }, [entryMeta, pinnedKeys, showHeaderStatus]);

  useImperativeHandle(
    ref,
    () => ({
      focusSearch: () => {
        if (searchInputInternalRef.current) {
          searchInputInternalRef.current.focus();
          if (typeof searchInputInternalRef.current.select === 'function') {
            searchInputInternalRef.current.select();
          }
          return true;
        }
        return false;
      },
      togglePinFocused,
      togglePinnedFilter,
      scrollToBottom,
    }),
    [togglePinFocused, togglePinnedFilter, scrollToBottom]
  );

  useEffect(() => {
    if (!searchTerm || searchMatches.length === 0) {
      setActiveMatchIndex(null);
      return;
    }
    setActiveMatchIndex((current) => {
      if (current == null || current >= searchMatches.length) return 0;
      return current;
    });
  }, [searchTerm, searchMatches]);

  useEffect(() => {
    if (!isHydrated) return;
    if (activeMatchIndex == null) return;
    if (activeMatchIndex < 0 || activeMatchIndex >= searchMatches.length) return;
    const targetIndex = searchMatches[activeMatchIndex];
    virtualizer.scrollToIndex(targetIndex, { align: 'center' });
  }, [activeMatchIndex, searchMatches, virtualizer, isHydrated]);

  const togglePin = useCallback((key: string) => {
    setPinnedKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  const handleClearPins = useCallback(() => {
    setPinnedKeys(new Set());
    setShowPinnedOnly(false);
  }, []);

  const handleClearSearch = useCallback(() => {
    setSearchInput('');
    setSearchTerm('');
    setActiveMatchIndex(null);
  }, []);

  const handleNextMatch = useCallback(() => {
    if (searchMatches.length === 0) return;
    setActiveMatchIndex((prev) => {
      if (prev == null) return 0;
      return (prev + 1) % searchMatches.length;
    });
  }, [searchMatches]);

  const handlePrevMatch = useCallback(() => {
    if (searchMatches.length === 0) return;
    setActiveMatchIndex((prev) => {
      if (prev == null) return searchMatches.length - 1;
      return (prev - 1 + searchMatches.length) % searchMatches.length;
    });
  }, [searchMatches]);

  const renderTranscriptItem = (
    index: number,
    { key, isVirtual, start }: { key: string; isVirtual: boolean; start?: number }
  ): React.ReactElement | null => {
    const turn = displayEntries[index];
    if (!turn) return null;

    const meta = displayMeta[index];
    const entryKey = meta?.key ?? transcriptEntryKey(turn);
    const bubbleId = `${turn.clientMessageId ?? 'local'}-${index}`;
    const isPinned = pinnedKeys.has(entryKey);
    const isAssistant = turn.role === 'assistant';
    const relativeTs = isHydrated ? formatRelativeTime(turn.ts) : 'just now';
    const absoluteTs = isHydrated ? new Date(turn.ts).toLocaleString() : '';
    const isCopied = copiedId === bubbleId;
    const isSearchMatch = matchSet.has(index);
    const isActiveMatch = activeMatchPosition === index;
    const isFocused = focusedIndex === index;
    const offerCoolIt = shouldOfferCoolIt(turn);
    const topicKey = offerCoolIt ? inferCoolItTopicKey(turn) : null;
    const coolItCompositeKey = topicKey ? `${entryKey}::${topicKey}` : null;
    const coolItAlready = coolItCompositeKey ? coolItApplied.has(coolItCompositeKey) : false;
    const coolItBusy = coolItCompositeKey ? coolItPending === coolItCompositeKey : false;
    const spacing = compact ? 12 : 16;
    const isLast = index === displayEntries.length - 1;

    const bubbleBase = compact
      ? 'max-w-xl rounded-2xl border px-4 py-2.5 text-[13px] shadow-sm'
      : 'max-w-xl rounded-2xl border px-5 py-3 text-sm shadow-sm';
    const personaBadge = isAssistant
      ? 'ml-auto border-cyan-500/30 bg-cyan-500/10 text-cyan-50'
      : 'mr-auto border-slate-700 bg-slate-800/70 text-slate-200';
    const matchHighlightClass = isActiveMatch
      ? 'ring-2 ring-cyan-300/80 shadow-cyan-200/20'
      : isSearchMatch
      ? 'ring-1 ring-amber-300/60'
      : '';
    const pinHighlightClass = isPinned ? 'border-amber-400/60 ring-1 ring-amber-400/70' : '';
    const focusHighlightClass = isFocused ? 'ring-2 ring-cyan-300/40' : '';
    const lastScrollMarginClass = isLast ? 'scroll-mb-[calc(var(--composer-h,72px)+16px)]' : '';

    const containerStyle: React.CSSProperties = isVirtual
      ? {
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          transform: `translateY(${start ?? 0}px)`,
          paddingBottom: spacing,
        }
      : {
          marginBottom: index === displayEntries.length - 1 ? 0 : spacing,
        };

    return (
      <div
        key={key}
        ref={(node) => {
          if (isVirtual && isHydrated && node) {
            virtualizer.measureElement(node);
          }
        }}
        data-index={index}
        style={containerStyle}
      >
        <article
          role="listitem"
          tabIndex={0}
          onFocus={() => setFocusedIndex(index)}
          onClick={() => setFocusedIndex(index)}
          onKeyDown={(event) => {
            if (event.key === 'ArrowDown') {
              if (!isHydrated) return;
              event.preventDefault();
              const next = Math.min(displayEntries.length - 1, index + 1);
              setFocusedIndex(displayEntries.length ? next : null);
              if (displayEntries.length) virtualizer.scrollToIndex(next, { align: 'center' });
            } else if (event.key === 'ArrowUp') {
              if (!isHydrated) return;
              event.preventDefault();
              const prev = Math.max(index - 1, 0);
              setFocusedIndex(displayEntries.length ? prev : null);
              if (displayEntries.length) virtualizer.scrollToIndex(prev, { align: 'center' });
            } else if (
              !event.metaKey &&
              !event.ctrlKey &&
              !event.altKey &&
              event.key.toLowerCase() === 'p'
            ) {
              event.preventDefault();
              togglePinByIndex(index);
            }
          }}
          data-testid="transcript-message"
          data-message-key={entryKey}
          className={`${bubbleBase} ${personaBadge} ${matchHighlightClass} ${pinHighlightClass} ${focusHighlightClass} ${lastScrollMarginClass}`}
        >
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1 space-y-2">
              <div className="flex flex-wrap items-center gap-2 text-xs uppercase tracking-wide text-slate-300">
                <span>{isAssistant ? turn.persona ?? 'Head Coach' : 'Member'}</span>
                <span
                  className="text-slate-500"
                  aria-label={absoluteTs || undefined}
                  title={absoluteTs || undefined}
                >
                  {relativeTs}
                </span>
                {isPinned ? (
                  <span className="inline-flex items-center gap-1 rounded-full border border-amber-400/40 bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold text-amber-200">
                    📌 Pinned
                  </span>
                ) : null}
                {isActiveMatch ? (
                  <span className="inline-flex items-center rounded-full border border-cyan-300/60 bg-cyan-400/10 px-2 py-0.5 text-[10px] font-semibold text-cyan-200">
                    Match
                  </span>
                ) : null}
              </div>

              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={markdownComponents}
                className={compact ? 'space-y-1.5' : 'space-y-2'}
              >
                {turn.text || ''}
              </ReactMarkdown>

              {turn.cancelled ? (
                <p className="text-xs text-rose-200" aria-live="polite">
                  Response cancelled.
                </p>
              ) : null}

              {turn.pending && !turn.cancelled ? (
                <p className="text-xs text-slate-400" aria-live="polite">
                  {turn.streaming ? 'Assistant is responding…' : 'Waiting for assistant…'}
                </p>
              ) : null}
            </div>

            <div className="flex flex-col items-end gap-2">
              {offerCoolIt && topicKey ? (
                <button
                  type="button"
                  onClick={() => {
                    if (coolItCompositeKey) {
                      void handleCoolIt(turn, topicKey, entryKey);
                    }
                  }}
                  className={`rounded-full border px-2 py-1 text-[11px] transition ${
                    coolItAlready
                      ? 'border-emerald-400 text-emerald-200 bg-emerald-500/10'
                      : 'border-slate-600 text-slate-200 hover:bg-slate-800'
                  }`}
                  aria-label="Cool it on this topic"
                  title="Cool it on this topic"
                  disabled={!hasActiveUser || coolItBusy || coolItAlready}
                >
                  {coolItAlready ? 'Cooling' : coolItBusy ? 'Saving…' : 'Cool it'}
                </button>
              ) : null}

              <button
                type="button"
                onClick={() => togglePin(entryKey)}
                className={`rounded-full border px-2 py-1 text-[11px] transition ${
                  isPinned
                    ? 'border-amber-400 text-amber-200 hover:bg-amber-500/20'
                    : 'border-slate-600 text-slate-200 hover:bg-slate-800'
                }`}
                aria-pressed={isPinned}
                aria-label={isPinned ? 'Unpin message' : 'Pin message'}
                data-testid="transcript-pin-button"
              >
                {isPinned ? 'Pinned' : 'Pin'}
              </button>

              <button
                type="button"
                onClick={() => handleCopy(turn, bubbleId)}
                className="rounded-full border border-slate-600 px-2 py-1 text-[11px] text-slate-200 hover:bg-slate-800"
                aria-label="Copy message"
              >
                {isCopied ? 'Copied' : 'Copy'}
              </button>

              {isAssistant && turn.pending && turn.streaming && turn.clientMessageId ? (
                <button
                  type="button"
                  onClick={() => requestCancel(turn.clientMessageId)}
                  className="rounded-full border border-rose-400/60 px-3 py-1 text-xs font-semibold text-rose-100 hover:bg-rose-500/10"
                  aria-label="Cancel response"
                >
                  Cancel
                </button>
              ) : null}
            </div>
          </div>
        </article>
      </div>
    );
  };

  const requestCancel = useCallback((clientMessageId?: string) => {
    if (!clientMessageId) return;
    window.dispatchEvent(
      new CustomEvent<{ clientMessageId: string }>('hc-chat-cancel-request', {
        detail: { clientMessageId },
      })
    );
  }, []);

  const handleClearChat = useCallback(() => {
    const trimmed = activeUserId.trim();
    if (trimmed) {
      clearCachedTranscript(trimmed);
      onClearChat?.(trimmed);
    }
    setEntries(buildDefaultTranscript());
    setCacheNotice(false);
    setPinnedKeys(new Set());
    setShowPinnedOnly(false);
    setSearchInput('');
    setSearchTerm('');
    setActiveMatchIndex(null);
    setFocusedIndex(null);
  }, [activeUserId, onClearChat]);

  useEffect(() => {
    if (resetToken == null) {
      return;
    }
    if (lastResetTokenRef.current === null) {
      lastResetTokenRef.current = resetToken;
      return;
    }
    if (lastResetTokenRef.current === resetToken) {
      return;
    }
    lastResetTokenRef.current = resetToken;
    handleClearChat();
  }, [resetToken, handleClearChat]);

  const handleCopy = useCallback((entry: TranscriptEntry, bubbleId: string) => {
    const text = entry.text ?? '';
    if (!text) return;
    if (navigator?.clipboard?.writeText) {
      navigator.clipboard
        .writeText(text)
        .then(() => {
          setCopiedId(bubbleId);
          if (copyTimerRef.current) window.clearTimeout(copyTimerRef.current);
          copyTimerRef.current = window.setTimeout(() => {
            setCopiedId(null);
            copyTimerRef.current = null;
          }, 2000);
        })
        .catch(() => {
          setCopiedId(null);
        });
    } else {
      setCopiedId(bubbleId);
      if (copyTimerRef.current) window.clearTimeout(copyTimerRef.current);
      copyTimerRef.current = window.setTimeout(() => {
        setCopiedId(null);
        copyTimerRef.current = null;
      }, 2000);
    }
  }, []);

  const handleCodeCopy = useCallback(
    (codeText: string, blockId: string) => {
      const performCopy = async () => {
        if (navigator?.clipboard?.writeText) {
          await navigator.clipboard.writeText(codeText);
        } else {
          const textarea = document.createElement('textarea');
          textarea.value = codeText;
          textarea.setAttribute('readonly', '');
          textarea.style.position = 'absolute';
          textarea.style.left = '-9999px';
          document.body.appendChild(textarea);
          textarea.select();
          document.execCommand('copy');
          document.body.removeChild(textarea);
        }
      };

      performCopy()
        .then(() => {
          setCopiedCodeBlockId(blockId);
          showHeaderStatus('Code copied.', 'success');
          if (codeCopyTimerRef.current) {
            window.clearTimeout(codeCopyTimerRef.current);
          }
          codeCopyTimerRef.current = window.setTimeout(() => {
            setCopiedCodeBlockId(null);
            codeCopyTimerRef.current = null;
          }, 1500);
        })
        .catch(() => {
          showHeaderStatus('Unable to copy code.', 'error');
        });
    },
    [showHeaderStatus]
  );

  const handleCoolIt = useCallback(
    async (entry: TranscriptEntry, topicKey: string, messageKey: string) => {
      const trimmedUser = activeUserId.trim();
      if (!trimmedUser) {
        showHeaderStatus('Select a user first.', 'info');
        return;
      }

      const dedupeKey = `${messageKey}::${topicKey}`;
      if (coolItApplied.has(dedupeKey)) {
        showHeaderStatus('Already easing up on this topic.', 'info');
        return;
      }

      setCoolItPending(dedupeKey);
      try {
        await submitTopicPreference({ userId: trimmedUser, key: topicKey, ttlDays: COOL_IT_TTL_DAYS });
        setCoolItApplied((prev) => {
          const next = new Set(prev);
          next.add(dedupeKey);
          return next;
        });
        showHeaderStatus('Okay—easing up on this topic.', 'success');
      } catch (error) {
        console.error('Failed to submit cool-it preference', error);
        showHeaderStatus('Could not record the preference. Try again.', 'error');
      } finally {
        setCoolItPending((current) => (current === dedupeKey ? null : current));
      }
    },
    [activeUserId, coolItApplied, showHeaderStatus]
  );

  const paragraphClass = compact ? 'leading-relaxed text-[13px]' : 'leading-relaxed text-sm';
  const listClass = compact ? 'text-[13px] leading-relaxed' : 'text-sm leading-relaxed';

  codeBlockIndexRef.current = 0;
  const markdownComponents = useMemo(
    () => ({
      a: (props: any) => (
        <a
          {...props}
          target="_blank"
          rel="noreferrer noopener"
          className="text-cyan-200 underline decoration-dotted underline-offset-2 hover:text-cyan-100"
        />
      ),
      p: ({ children }: any) => <p className={paragraphClass}>{children}</p>,
      ul: ({ children }: any) => <ul className={`list-disc space-y-1 pl-5 ${listClass}`}>{children}</ul>,
      ol: ({ children }: any) => <ol className={`list-decimal space-y-1 pl-5 ${listClass}`}>{children}</ol>,
      li: ({ children }: any) => <li className={listClass}>{children}</li>,
      blockquote: ({ children }: any) => (
        <blockquote className={`border-l-2 border-cyan-500/40 pl-3 italic text-slate-200 ${listClass}`}>
          {children}
        </blockquote>
      ),
      code: ({ inline, className, children, ...props }: any) =>
        inline ? (
          <code
            {...props}
            className={`rounded bg-slate-900/70 px-1 py-0.5 text-[12px] text-cyan-100 ${className ?? ''}`}
          >
            {children}
          </code>
        ) : (
          (() => {
            codeBlockIndexRef.current += 1;
            const blockId = `transcript-code-${codeBlockIndexRef.current}`;
            const codeContent = String(Array.isArray(children) ? children.join('') : children ?? '');
            return (
              <div className="group relative" data-code-block-id={blockId}>
                <pre
                  {...props}
                  className={`overflow-x-auto rounded-xl bg-slate-950/70 p-4 text-[12px] leading-relaxed text-cyan-100 ${className ?? ''}`}
                >
                  <code>{children}</code>
                </pre>
                <button
                  type="button"
                  onClick={() => handleCodeCopy(codeContent, blockId)}
                  className="absolute right-3 top-3 hidden items-center gap-1 rounded-full border border-slate-700 bg-slate-900/80 px-3 py-1 text-xs text-slate-200 transition hover:border-cyan-400 hover:text-cyan-200 group-hover:flex"
                  aria-label="Copy code block"
                >
                  Copy
                </button>
                {copiedCodeBlockId === blockId ? (
                  <span className="absolute right-3 top-3 flex items-center gap-1 rounded-full border border-emerald-400/60 bg-emerald-500/10 px-3 py-1 text-xs font-semibold text-emerald-200">
                    Copied
                  </span>
                ) : null}
              </div>
            );
          })()
        ),
    }),
    [copiedCodeBlockId, handleCodeCopy, listClass, paragraphClass]
  );

  // ⚠️ LEFT PANE SANCTITY RULE ⚠️
  // h-full max-h-full (NOT flex-1) prevents recalculation cycles
  // DO NOT change without reading LEFT_PANE_SANCTITY_RULE.md
  const heightClass = fillHeight ? 'h-full max-h-full' : 'h-[60vh]';
  const showJumpToLatest = !isAtBottom && !showPinnedOnly && !searchTerm;


  const sectionBg = fillHeight ? 'bg-slate-900/60' : 'bg-rose-900/60';

  return (
    <section className={`flex flex-col ${heightClass} min-h-0 overflow-hidden overscroll-none rounded-2xl border border-slate-800 ${sectionBg} shadow-xl`}>
      <header ref={headerRef} className="shrink-0 border-b border-slate-800 px-5 py-4">
        <div className="flex items-center justify-between gap-3">
          <div className="flex-1">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
              Transcript {fillHeight && <span className="text-xs text-cyan-400">[fillHeight mode]</span>}
            </h2>
            <p className="text-xs text-slate-500">Composer stays visible; transcript scrolls independently.</p>
            {cacheNotice ? (
              <p className="mt-1 text-xs text-amber-300" aria-live="polite">
                {t('transcript.cachedWarning')}
              </p>
            ) : null}
            {headerStatus ? (
              <p
                className={`mt-1 text-xs ${
                  headerStatus.tone === 'success'
                    ? 'text-emerald-300'
                    : headerStatus.tone === 'error'
                    ? 'text-rose-300'
                    : 'text-slate-500'
                }`}
                role="status"
                aria-live="polite"
              >
                {headerStatus.message}
              </p>
            ) : null}
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {loading ? <span className="text-xs text-slate-500">Refreshing…</span> : null}
            <div ref={menuRef} className="relative">
              <button
                type="button"
                onClick={() => setMenuOpen((prev) => !prev)}
                className="flex items-center justify-center rounded-full border border-slate-700 p-2 text-slate-200 transition hover:bg-slate-800"
              aria-haspopup="true"
              aria-expanded={menuOpen}
              aria-label="Transcript actions"
              data-testid="transcript-actions-toggle"
              disabled={entries.length === 0 && !onQuickSnapshot}
            >
              <span aria-hidden="true">⋮</span>
            </button>
              {menuOpen ? (
                <div
                  className="absolute right-0 z-10 mt-2 w-52 rounded-xl border border-slate-800 bg-slate-900/95 p-2 shadow-xl backdrop-blur"
                  role="menu"
                >
                  {onQuickSnapshot ? (
                    <button
                      type="button"
                      onClick={() => {
                        void handleQuickSnapshotAction();
                      }}
                      className="block w-full rounded-lg px-3 py-2 text-left text-xs text-cyan-200 hover:bg-cyan-700/20 disabled:cursor-not-allowed disabled:opacity-50"
                      data-testid="transcript-quick-snapshot"
                      role="menuitem"
                      disabled={quickSnapshotPending || !hasActiveUser}
                    >
                      {quickSnapshotPending ? 'Creating snapshot…' : 'Quick snapshot'}
                    </button>
                  ) : null}
                  <button
                    type="button"
                    onClick={() => handleExport('json')}
                    className={`block w-full rounded-lg px-3 py-2 text-left text-xs text-slate-200 hover:bg-slate-800${onQuickSnapshot ? ' mt-1' : ''}`}
                    data-testid="transcript-export-json"
                    role="menuitem"
                  >
                    Export transcript (JSON)
                  </button>
                  <button
                    type="button"
                    onClick={() => handleExport('csv')}
                    className="mt-1 block w-full rounded-lg px-3 py-2 text-left text-xs text-slate-200 hover:bg-slate-800"
                    data-testid="transcript-export-csv"
                    role="menuitem"
                  >
                    Export transcript (CSV)
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      void handleCopyPinned();
                    }}
                    className="mt-1 block w-full rounded-lg px-3 py-2 text-left text-xs text-slate-200 hover:bg-slate-800 disabled:opacity-40"
                    data-testid="transcript-copy-pinned"
                    role="menuitem"
                    disabled={pinnedKeys.size === 0}
                  >
                    Copy pinned only
                  </button>
                </div>
              ) : null}
            </div>
            <button
              type="button"
              onClick={handleClearChat}
              className="rounded-full border border-slate-700 px-3 py-1 text-xs font-semibold text-slate-200 transition hover:border-rose-400 hover:text-rose-200 disabled:opacity-40"
              disabled={!hasActiveUser}
            >
              Clear chat
            </button>
          </div>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-2">
          <label className="relative flex items-center">
            <span className="sr-only">Search transcript</span>
            <input
              type="search"
              ref={registerSearchInput}
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              placeholder="Search transcript…"
              className="w-48 rounded-full border border-slate-700 bg-slate-900 px-3 py-1 text-sm text-slate-200 placeholder:text-slate-500 focus:border-cyan-400 focus:outline-none sm:w-64"
              data-testid="transcript-search-input"
            />
          </label>

          <button
            type="button"
            onClick={handlePrevMatch}
            className="rounded-full border border-slate-700 px-2 py-1 text-xs text-slate-200 hover:bg-slate-800 disabled:opacity-40"
            disabled={!searchTerm || searchMatches.length === 0}
            data-testid="transcript-search-prev"
          >
            Prev
          </button>

          <button
            type="button"
            onClick={handleNextMatch}
            className="rounded-full border border-slate-700 px-2 py-1 text-xs text-slate-200 hover:bg-slate-800 disabled:opacity-40"
            disabled={!searchTerm || searchMatches.length === 0}
            data-testid="transcript-search-next"
          >
            Next
          </button>

          <span className="text-xs text-slate-500">
            {searchTerm
              ? searchMatches.length
                ? `Match ${activeMatchDisplay} of ${searchMatches.length}`
                : 'No matches'
              : 'Type to search'}
          </span>

          <button
            type="button"
            onClick={handleClearSearch}
            className="rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-200 hover:bg-slate-800 disabled:opacity-40"
            disabled={!searchTerm}
            data-testid="transcript-search-clear"
          >
            Clear search
          </button>

          <div className="ml-auto flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => setShowPinnedOnly((prev) => !prev)}
              className={`rounded-full border px-3 py-1 text-xs font-semibold transition ${
                showPinnedOnly
                  ? 'border-amber-400 text-amber-200 bg-amber-500/10'
                  : 'border-slate-700 text-slate-200 hover:bg-slate-800'
              }`}
              disabled={pinnedKeys.size === 0}
              data-testid="transcript-pins-toggle"
            >
              {showPinnedOnly ? 'Showing pinned' : `Pinned (${pinnedKeys.size})`}
            </button>

            <button
              type="button"
              onClick={handleClearPins}
              className="rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-200 hover:bg-slate-800 disabled:opacity-40"
              disabled={pinnedKeys.size === 0}
              data-testid="transcript-pins-clear"
            >
              Clear pins
            </button>
          </div>
        </div>
      </header>

      <div
        ref={scrollContainerRef}
        className={`${compact ? 'px-4 py-4' : 'px-5 py-6'}
                flex-1 min-h-0 overflow-y-auto overscroll-contain
                [padding-bottom:calc(var(--composer-h,72px)+12px)]
                [scroll-padding-bottom:calc(var(--composer-h,72px)+12px)]
                [scrollbar-gutter:stable_both-edges]`}
        style={{
          WebkitOverflowScrolling: 'touch'
        }}
      >
        {isHydrated && shouldVirtualize ? (
          <div
            role="list"
            aria-label="Assistant and member transcript"
            style={{ height: `${virtualizer.getTotalSize()}px`, width: '100%', position: 'relative' }}
          >
            {virtualItems.map((virtualItem) =>
              renderTranscriptItem(virtualItem.index, {
                key: String(virtualItem.key),
                isVirtual: true,
                start: virtualItem.start,
              })
            )}
          </div>
        ) : isHydrated ? (
          <div role="list" aria-label="Assistant and member transcript" className="flex flex-col">
            {displayEntries.map((_, index) =>
              renderTranscriptItem(index, {
                key: displayMeta[index]?.key ?? `${displayEntries[index]?.role ?? 'turn'}-${index}`,
                isVirtual: false,
              })
            )}
          </div>
        ) : (
          <div role="list" aria-label="Assistant and member transcript" className="flex flex-col">
            {displayEntries.map((_, index) =>
              renderTranscriptItem(index, {
                key: displayMeta[index]?.key ?? `${displayEntries[index]?.role ?? 'turn'}-${index}`,
                isVirtual: false,
              })
            )}
          </div>
        )}

        {showJumpToLatest ? (
          <button
            type="button"
            onClick={() => performScrollToBottom('smooth')}
            className="absolute bottom-6 left-1/2 -translate-x-1/2 rounded-full border border-slate-700 bg-slate-800/80 px-3 py-1 text-sm font-medium text-slate-200 shadow-lg transition hover:border-cyan-400 hover:text-cyan-100"
          >
            Jump to latest
          </button>
        ) : null}
      </div>
    </section>
  );
});

function buildEchoReply(message: string): string {
  if (!message.trim()) {
    return 'Noted. I will queue this for the planner.';
  }
  if (message.length < 80) {
    return `Got it — I'll keep this in mind: "${message}"`;
  }
  return 'Thanks! I captured that context and will adjust the next plan.';
}
