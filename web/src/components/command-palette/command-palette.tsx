'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { MessageKey } from '../../i18n/messages';

export interface CommandPaletteEntry {
  id: string;
  label: string;
  run: () => void;
  aliases?: string[];
  shortcut?: string;
}

export interface CommandPaletteText {
  placeholder: string;
  ariaLabel: string;
  empty: string;
}

export interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
  actions: CommandPaletteEntry[];
  text: CommandPaletteText;
}

export interface CommandContext {
  focusUserSwitcher: () => void;
  openSettings: () => void;
  openSnapshots: () => void;
  startTour: () => void;
  quickSnapshot: () => void | Promise<void>;
  focusTranscriptSearch: () => void;
  toggleCompactDensity: () => void;
  toggleStreaming: () => void;
  compactDensityEnabled: boolean;
  streamingEnabled: boolean;
}

interface CommandDefinition {
  id: string;
  labelKey: MessageKey;
  aliases?: string[];
  shortcut?: string;
  dynamicLabelKey?: (context: CommandContext) => MessageKey;
  run: (context: CommandContext) => void;
}

interface RankedAction {
  action: CommandPaletteEntry;
  score: number;
}

const POSITION_WEIGHT = 4;
const CONSECUTIVE_BONUS = 6;
const START_BONUS = 8;

const COMMAND_REGISTRY: CommandDefinition[] = [
  {
    id: 'switch-user',
    labelKey: 'commandPalette.switchUser',
    aliases: ['user', 'switch', 'picker'],
    run: (context) => {
      context.focusUserSwitcher();
    },
  },
  {
    id: 'open-settings',
    labelKey: 'commandPalette.openSettings',
    aliases: ['preferences', 'config'],
    run: (context) => {
      context.openSettings();
    },
  },
  {
    id: 'open-snapshots',
    labelKey: 'commandPalette.openSnapshots',
    aliases: ['snapshots', 'bundles', 'history'],
    run: (context) => {
      context.openSnapshots();
    },
  },
  {
    id: 'start-tour',
    labelKey: 'commandPalette.startTour',
    aliases: ['tour', 'help'],
    run: (context) => {
      context.startTour();
    },
  },
  {
    id: 'quick-snapshot',
    labelKey: 'commandPalette.quickSnapshot',
    aliases: ['snapshot', 'save state'],
    run: (context) => {
      void context.quickSnapshot();
    },
  },
  {
    id: 'focus-transcript-search',
    labelKey: 'commandPalette.focusTranscriptSearch',
    aliases: ['search', 'find transcript'],
    run: (context) => {
      context.focusTranscriptSearch();
    },
  },
  {
    id: 'toggle-compact-density',
    labelKey: 'commandPalette.toggleCompact',
    aliases: ['density', 'layout', 'compact'],
    dynamicLabelKey: (context) =>
      context.compactDensityEnabled
        ? 'commandPalette.toggleCompactDisable'
        : 'commandPalette.toggleCompactEnable',
    run: (context) => {
      context.toggleCompactDensity();
    },
  },
  {
    id: 'toggle-streaming',
    labelKey: 'commandPalette.toggleStreaming',
    aliases: ['streaming', 'live updates'],
    dynamicLabelKey: (context) =>
      context.streamingEnabled
        ? 'commandPalette.toggleStreamingDisable'
        : 'commandPalette.toggleStreamingEnable',
    run: (context) => {
      context.toggleStreaming();
    },
  },
];

export function buildCommandPaletteActions(
  context: CommandContext,
  translate: (key: MessageKey) => string
): CommandPaletteEntry[] {
  return COMMAND_REGISTRY.map((definition) => ({
    id: definition.id,
    label: translate(definition.dynamicLabelKey ? definition.dynamicLabelKey(context) : definition.labelKey),
    aliases: definition.aliases,
    shortcut: definition.shortcut,
    run: () => definition.run(context),
  }));
}

function normalizeQuery(value: string): string {
  return value.trim().toLowerCase();
}

function scoreText(text: string, query: string): number | null {
  const haystack = text.toLowerCase();
  const needle = query.replace(/\s+/g, '');
  if (!needle) {
    return 0;
  }

  let score = 0;
  let position = -1;
  let adjacency = 0;

  for (const char of needle) {
    const nextIndex = haystack.indexOf(char, position + 1);
    if (nextIndex === -1) {
      return null;
    }

    if (nextIndex === position + 1) {
      adjacency += CONSECUTIVE_BONUS;
    } else {
      adjacency = 0;
    }

    const positional = POSITION_WEIGHT - Math.min(nextIndex, POSITION_WEIGHT);
    const startBonus = nextIndex === 0 ? START_BONUS : 0;
    score += 5 + positional + adjacency + startBonus;
    position = nextIndex;
  }

  return score;
}

function rankActions(actions: CommandPaletteEntry[], query: string): CommandPaletteEntry[] {
  const normalized = normalizeQuery(query);
  if (!normalized) {
    return actions;
  }

  const ranked: RankedAction[] = [];

  for (const action of actions) {
    const candidates = [action.label, ...(action.aliases ?? [])];
    let bestScore: number | null = null;
    for (const candidate of candidates) {
      const score = scoreText(candidate, normalized);
      if (score != null && (bestScore == null || score > bestScore)) {
        bestScore = score;
      }
    }
    if (bestScore != null) {
      ranked.push({ action, score: bestScore });
    }
  }

  ranked.sort((a, b) => {
    if (b.score !== a.score) {
      return b.score - a.score;
    }
    return a.action.label.localeCompare(b.action.label);
  });

  return ranked.map((entry) => entry.action);
}

export function CommandPalette({ open, onClose, actions, text }: CommandPaletteProps) {
  const [query, setQuery] = useState('');
  const [highlightedIndex, setHighlightedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const filtered = useMemo(() => rankActions(actions, query), [actions, query]);

  useEffect(() => {
    if (!open) {
      setQuery('');
      setHighlightedIndex(0);
      return;
    }
    setQuery('');
    setHighlightedIndex(0);
    const frame = requestAnimationFrame(() => {
      inputRef.current?.focus();
      inputRef.current?.select();
    });
    return () => cancelAnimationFrame(frame);
  }, [open]);

  useEffect(() => {
    if (highlightedIndex >= filtered.length) {
      setHighlightedIndex(filtered.length === 0 ? 0 : filtered.length - 1);
    }
  }, [filtered.length, highlightedIndex]);

  useEffect(() => {
    if (open) {
      setHighlightedIndex(0);
    }
  }, [open, query]);

  const executeAction = useCallback(
    (entry: CommandPaletteEntry) => {
      onClose();
      requestAnimationFrame(() => {
        try {
          entry.run();
        } catch (error) {
          console.error('Command action failed', entry.id, error);
        }
      });
    },
    [onClose]
  );

  useEffect(() => {
    if (!open) {
      return;
    }
    function handleKey(event: KeyboardEvent) {
      if (!open) {
        return;
      }
      if (event.key === 'Escape') {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key === 'ArrowDown') {
        event.preventDefault();
        if (filtered.length === 0) {
          return;
        }
        setHighlightedIndex((prev) => (prev + 1) % filtered.length);
        return;
      }
      if (event.key === 'ArrowUp') {
        event.preventDefault();
        if (filtered.length === 0) {
          return;
        }
        setHighlightedIndex((prev) => (prev - 1 + filtered.length) % filtered.length);
        return;
      }
      if (event.key === 'Enter') {
        const entry = filtered[highlightedIndex];
        if (entry) {
          event.preventDefault();
          executeAction(entry);
        }
      }
    }

    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [executeAction, filtered, highlightedIndex, onClose, open]);

  if (!open) {
    return null;
  }

  return (
    <div
      className="fixed inset-0 z-[200] flex items-start justify-center bg-slate-950/60 px-4 py-12 backdrop-blur"
      role="dialog"
      aria-modal="true"
      aria-label={text.ariaLabel}
      onClick={onClose}
    >
      <div
        className="w-full max-w-xl overflow-hidden rounded-3xl border border-slate-800 bg-slate-950 shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="border-b border-slate-800 px-4 py-3">
          <input
            ref={inputRef}
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={text.placeholder}
            className="w-full rounded-full border border-slate-700 bg-slate-900 px-4 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:border-cyan-400 focus:outline-none"
            aria-label={text.placeholder}
          />
        </header>
        <ul
          role="listbox"
          aria-activedescendant={filtered[highlightedIndex]?.id ?? undefined}
          className="max-h-72 overflow-y-auto p-2 text-sm text-slate-100"
        >
          {filtered.length === 0 ? (
            <li className="rounded-xl px-3 py-4 text-center text-slate-500" role="option" aria-selected="false">
              {text.empty}
            </li>
          ) : (
            filtered.map((action, index) => {
              const selected = index === highlightedIndex;
              return (
                <li
                  key={action.id}
                  id={action.id}
                  role="option"
                  aria-selected={selected}
                  className={`rounded-xl ${selected ? 'bg-slate-900' : ''}`}
                  onMouseEnter={() => setHighlightedIndex(index)}
                >
                  <button
                    type="button"
                    className="flex w-full items-center justify-between gap-4 rounded-xl px-3 py-2 text-left focus:outline-none"
                    onClick={() => executeAction(action)}
                  >
                    <div>
                      <p className="font-medium">{action.label}</p>
                      {action.aliases && action.aliases.length ? (
                        <p className="text-xs text-slate-400">{action.aliases.join(', ')}</p>
                      ) : null}
                    </div>
                    {action.shortcut ? (
                      <span className="rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-300">
                        {action.shortcut}
                      </span>
                    ) : null}
                  </button>
                </li>
              );
            })
          )}
        </ul>
      </div>
    </div>
  );
}
