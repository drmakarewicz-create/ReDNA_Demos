'use client';

import { useEffect, useMemo } from 'react';

export type Shortcut = {
  combo: string;
  description: string;
  run: () => void;
  group?: string;
};

type ParsedShortcut = Shortcut & {
  comboKey: string;
  key: string;
  modifiers: {
    cmd: boolean;
    ctrl: boolean;
    alt: boolean;
    shift: boolean;
  };
};

const shortcutRegistry = new Map<string, ParsedShortcut>();
let listenerAttached = false;
let listenerRefs = 0;

function normalizeToken(token: string): string {
  const value = token.trim().toLowerCase();
  if (value === 'cmd' || value === 'meta') return 'cmd';
  if (value === 'control' || value === 'ctrl' || value === 'ctl') return 'ctrl';
  if (value === 'option' || value === 'alt') return 'alt';
  if (value === 'shift') return 'shift';
  if (value === 'escape' || value === 'esc') return 'esc';
  if (value === 'enter' || value === 'return') return 'enter';
  if (value === 'space' || value === 'spacebar') return 'space';
  return value;
}

function normalizeKeyToken(token: string): string {
  const normalized = normalizeToken(token);
  return normalized;
}

function normalizeEventKey(event: KeyboardEvent): string {
  if (event.key === ' ') {
    return 'space';
  }
  const key = event.key.toLowerCase();
  if (key === 'escape' || key === 'esc') {
    return 'esc';
  }
  if (key === 'enter' || key === 'return') {
    return 'enter';
  }
  if (key === 'arrowup') {
    return 'arrowup';
  }
  if (key === 'arrowdown') {
    return 'arrowdown';
  }
  if (key === 'arrowleft') {
    return 'arrowleft';
  }
  if (key === 'arrowright') {
    return 'arrowright';
  }
  return key.length === 1 ? key : key;
}

function buildComboKey(parts: { cmd: boolean; ctrl: boolean; alt: boolean; shift: boolean }, key: string): string {
  const modifiers: string[] = [];
  if (parts.cmd) modifiers.push('cmd');
  if (parts.ctrl) modifiers.push('ctrl');
  if (parts.alt) modifiers.push('alt');
  if (parts.shift) modifiers.push('shift');
  modifiers.push(key);
  return modifiers.join('+');
}

function parseCombo(shortcut: Shortcut): ParsedShortcut {
  const rawTokens = shortcut.combo.split('+').map((token) => token.trim()).filter(Boolean);
  if (rawTokens.length === 0) {
    throw new Error(`Invalid shortcut combo: "${shortcut.combo}"`);
  }
  const modifiers = { cmd: false, ctrl: false, alt: false, shift: false };
  const keyToken = normalizeKeyToken(rawTokens[rawTokens.length - 1]);
  for (let i = 0; i < rawTokens.length - 1; i += 1) {
    const token = normalizeToken(rawTokens[i]);
    if (token === 'cmd') modifiers.cmd = true;
    else if (token === 'ctrl') modifiers.ctrl = true;
    else if (token === 'alt') modifiers.alt = true;
    else if (token === 'shift') modifiers.shift = true;
  }
  const comboKey = buildComboKey(modifiers, keyToken);
  return {
    ...shortcut,
    comboKey,
    key: keyToken,
    modifiers
  };
}

function registerShortcut(shortcut: Shortcut) {
  const parsed = parseCombo(shortcut);
  shortcutRegistry.set(parsed.comboKey, parsed);
  return parsed;
}

function unregisterShortcut(combo: string) {
  try {
    const parsed = parseCombo({ combo, description: '', run: () => undefined });
    shortcutRegistry.delete(parsed.comboKey);
  } catch (error) {
    console.warn('Failed to unregister shortcut', combo, error);
  }
}

function matchShortcut(event: KeyboardEvent): ParsedShortcut | null {
  const key = normalizeEventKey(event);
  const modifiers = {
    cmd: Boolean(event.metaKey),
    ctrl: Boolean(event.ctrlKey),
    alt: Boolean(event.altKey),
    shift: Boolean(event.shiftKey)
  };
  const comboKey = buildComboKey(modifiers, key);
  return shortcutRegistry.get(comboKey) ?? null;
}

function handleKeydown(event: KeyboardEvent) {
  const target = event.target as HTMLElement | null;
  const tag = target?.tagName?.toLowerCase();
  const isEditable = target?.isContentEditable ?? false;
  const isInputElement =
    isEditable || tag === 'input' || tag === 'textarea' || tag === 'select';
  const hasModifier = event.metaKey || event.ctrlKey || event.altKey || event.shiftKey;

  if (isInputElement && !hasModifier) {
    return;
  }

  const match = matchShortcut(event);
  if (!match) {
    return;
  }

  event.preventDefault();
  try {
    match.run();
  } catch (error) {
    console.error('Shortcut handler failed', match.combo, error);
  }
}

function ensureListener() {
  if (listenerAttached || typeof window === 'undefined') {
    return;
  }
  window.addEventListener('keydown', handleKeydown);
  listenerAttached = true;
}

function teardownListener() {
  if (!listenerAttached || typeof window === 'undefined' || listenerRefs > 0) {
    return;
  }
  window.removeEventListener('keydown', handleKeydown);
  listenerAttached = false;
}

export function useShortcutManager(): {
  register: (shortcut: Shortcut) => void;
  unregister: (combo: string) => void;
  registerMany: (shortcuts: Shortcut[]) => () => void;
  unregisterMany: (combos: string[]) => void;
  getAll: () => Shortcut[];
} {
  useEffect(() => {
    listenerRefs += 1;
    ensureListener();
    return () => {
      listenerRefs = Math.max(0, listenerRefs - 1);
      teardownListener();
    };
  }, []);

  return useMemo(
    () => ({
      register(shortcut: Shortcut) {
        registerShortcut(shortcut);
      },
      unregister(combo: string) {
        unregisterShortcut(combo);
      },
      registerMany(shortcuts: Shortcut[]) {
        const parsedList = shortcuts.map((shortcut) => registerShortcut(shortcut));
        return () => {
          parsedList.forEach((parsed) => {
            const current = shortcutRegistry.get(parsed.comboKey);
            if (current === parsed) {
              shortcutRegistry.delete(parsed.comboKey);
            }
          });
        };
      },
      unregisterMany(combos: string[]) {
        combos.forEach((combo) => unregisterShortcut(combo));
      },
      getAll() {
        return Array.from(shortcutRegistry.values()).map(({ comboKey: _comboKey, ...rest }) => rest);
      }
    }),
    []
  );
}
