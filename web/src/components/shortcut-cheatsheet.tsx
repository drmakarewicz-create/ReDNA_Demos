'use client';

import { useEffect } from 'react';

import { useShortcutManager } from '../hooks/use-shortcuts';

interface ShortcutCheatsheetProps {
  open: boolean;
  onClose: () => void;
}

type GroupedShortcut = {
  group: string;
  description: string;
  combos: string[];
};

const GROUP_ORDER = ['Navigation', 'Actions', 'View', 'Debug'];

function formatCombo(combo: string): string {
  const parts = combo.split('+');
  return parts
    .map((part) => {
      switch (part) {
        case 'cmd':
          return '⌘';
        case 'ctrl':
          return 'Ctrl';
        case 'alt':
          return 'Alt';
        case 'shift':
          return 'Shift';
        case 'space':
          return 'Space';
        case 'enter':
          return 'Enter';
        case 'esc':
          return 'Esc';
        default:
          return part.length === 1 ? part.toUpperCase() : part;
      }
    })
    .join(' + ');
}

export function ShortcutCheatsheet({ open, onClose }: ShortcutCheatsheetProps) {
  const manager = useShortcutManager();

  useEffect(() => {
    if (!open) {
      return;
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        event.preventDefault();
        onClose();
      }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) {
    return null;
  }

  const shortcuts = manager.getAll();
  const groupedMap = new Map<string, GroupedShortcut>();
  shortcuts.forEach((shortcut) => {
    const key = `${shortcut.group ?? 'General'}::${shortcut.description}`;
    const entry = groupedMap.get(key);
    if (entry) {
      if (!entry.combos.includes(shortcut.combo)) {
        entry.combos.push(shortcut.combo);
      }
    } else {
      groupedMap.set(key, {
        group: shortcut.group ?? 'General',
        description: shortcut.description,
        combos: [shortcut.combo]
      });
    }
  });

  const grouped = Array.from(groupedMap.values());
  grouped.sort((a, b) => {
    const groupIndexA = GROUP_ORDER.indexOf(a.group);
    const groupIndexB = GROUP_ORDER.indexOf(b.group);
    if (groupIndexA !== groupIndexB) {
      if (groupIndexA === -1) return 1;
      if (groupIndexB === -1) return -1;
      return groupIndexA - groupIndexB;
    }
    return a.description.localeCompare(b.description);
  });
  grouped.forEach((entry) => entry.combos.sort());

  const groupedByGroup = new Map<string, GroupedShortcut[]>();
  grouped.forEach((entry) => {
    const list = groupedByGroup.get(entry.group) ?? [];
    list.push(entry);
    groupedByGroup.set(entry.group, list);
  });

  const orderedGroups = Array.from(groupedByGroup.keys()).sort((a, b) => {
    const indexA = GROUP_ORDER.indexOf(a);
    const indexB = GROUP_ORDER.indexOf(b);
    if (indexA !== indexB) {
      if (indexA === -1) return 1;
      if (indexB === -1) return -1;
      return indexA - indexB;
    }
    return a.localeCompare(b);
  });

  return (
    <div
      className="fixed inset-0 z-[210] flex items-center justify-center bg-slate-950/70 px-4 py-10 backdrop-blur"
      role="dialog"
      aria-modal="true"
      aria-label="Keyboard shortcuts"
      onClick={onClose}
    >
      <div
        className="max-h-[80vh] w-full max-w-3xl overflow-y-auto rounded-3xl border border-slate-800 bg-slate-950 p-6 text-slate-100 shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="mb-6 flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold">Keyboard shortcuts</h2>
            <p className="text-sm text-slate-400">Press Esc to close.</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-slate-700 px-3 py-1 text-sm text-slate-300 hover:bg-slate-900"
          >
            Close
          </button>
        </header>
        {shortcuts.length === 0 ? (
          <p className="text-sm text-slate-400">No shortcuts registered.</p>
        ) : (
          <div className="space-y-6">
            {orderedGroups.map((groupKey) => {
              const entries = groupedByGroup.get(groupKey) ?? [];
              return (
                <section key={groupKey}>
                  <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
                    {groupKey}
                  </h3>
                  <div className="grid gap-3 sm:grid-cols-2">
                    {entries.map((entry) => (
                      <article
                        key={`${entry.group}-${entry.description}`}
                        className="rounded-2xl border border-slate-800 bg-slate-900/60 px-4 py-3"
                      >
                        <p className="text-sm font-medium text-slate-100">{entry.description}</p>
                        <p className="mt-2 text-xs text-slate-400">
                          {entry.combos.map(formatCombo).join(' / ')}
                        </p>
                      </article>
                    ))}
                  </div>
                </section>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
