'use client';

import { useEffect, useMemo, useRef, useState } from 'react';

import {
  flexRender,
  getCoreRowModel,
  type ColumnDef,
  useReactTable,
} from '@tanstack/react-table';
import { useVirtualizer } from '@tanstack/react-virtual';

import type { UnabridgedSnapshot, UnabridgedTrait } from '../lib/api';
import { PanelError } from './panel-error';
import { updateVirtualizerMetrics, removeVirtualizerMetrics } from '../lib/perf-hud';
import { RRBadge, CuriosityBadge } from './rr-curiosity-badges';
import { ProvenanceModal } from './provenance-modal';
import { overrideTrait } from '../lib/api';

interface TraitChange {
  trait: string;
  old_rr: number;
  new_rr: number;
  delta: number;
}

interface UnabridgedPanelProps {
  snapshot: UnabridgedSnapshot | null;
  loading?: boolean;
  id?: string;
  error?: string | null;
  onRetry?: () => void;
  onTimeline?: (traitId: string) => void;
  timelineDisabled?: boolean;
  changedTraits?: TraitChange[];
  onRefresh?: () => void;
}

export function UnabridgedPanel({ snapshot, loading, id, error, onRetry, onTimeline, timelineDisabled, changedTraits, onRefresh }: UnabridgedPanelProps) {
  const [searchTerm, setSearchTerm] = useState('');
  const [containerFilter, setContainerFilter] = useState<string>('all');
  const [highlightedTraits, setHighlightedTraits] = useState<Set<string>>(new Set());
  const [provenanceOpen, setProvenanceOpen] = useState(false);
  const [selectedTrait, setSelectedTrait] = useState<{ id: string; value: any; userId: string } | null>(null);
  const [showHighCuriosity, setShowHighCuriosity] = useState(false);
  const [editingTrait, setEditingTrait] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  const [saving, setSaving] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const containers = useMemo(() => {
    if (!snapshot?.traits?.length) {
      return [];
    }
    const unique = new Set<string>();
    snapshot.traits.forEach((trait) => {
      unique.add(containerFromTrait(trait.trait_id));
    });
    return Array.from(unique).sort((a, b) => a.localeCompare(b));
  }, [snapshot]);

  const filteredTraits = useMemo<UnabridgedTrait[]>(() => {
    if (!snapshot?.traits) {
      return [];
    }
    const term = searchTerm.trim().toLowerCase();
    return snapshot.traits
      .filter((trait) => {
        const container = containerFromTrait(trait.trait_id);
        if (containerFilter !== 'all' && container !== containerFilter) {
          return false;
        }
        if (showHighCuriosity) {
          const curiosity = trait.curiosity ?? 0;
          if (curiosity < 0.6) {
            return false;
          }
        }
        if (!term) {
          return true;
        }
        const valueText = renderValue(trait.value).toLowerCase();
        const reasonText = (trait.reasons ?? []).join(' ').toLowerCase();
        return (
          trait.trait_id.toLowerCase().includes(term) ||
          valueText.includes(term) ||
          reasonText.includes(term)
        );
      })
      .sort((a, b) => a.trait_id.localeCompare(b.trait_id));
  }, [snapshot, containerFilter, searchTerm, showHighCuriosity]);

  const handleEditStart = (traitId: string, currentValue: unknown) => {
    setEditingTrait(traitId);
    setEditValue(String(currentValue ?? ''));
  };

  const handleEditCancel = () => {
    setEditingTrait(null);
    setEditValue('');
  };

  const handleEditSave = async (traitId: string, oldValue: unknown) => {
    if (!snapshot?.user_id || !editValue.trim()) return;

    setSaving(true);
    try {
      const result = await overrideTrait({
        userId: snapshot.user_id,
        traitId,
        value: editValue,
      });

      if (result.ok) {
        const oldRR = result.old_rr ?? 0;
        const newRR = result.new_rr ?? 0;
        const delta = Math.round(newRR - oldRR);
        const sign = delta > 0 ? '+' : '';

        setToastMessage(`Trait updated: ${oldValue} → ${editValue} (RR ${sign}${delta})`);
        setTimeout(() => setToastMessage(null), 5000);

        setEditingTrait(null);
        setEditValue('');

        if (onRefresh) {
          onRefresh();
        }
      }
    } catch (error) {
      setToastMessage(`Failed to update trait: ${error instanceof Error ? error.message : 'Unknown error'}`);
      setTimeout(() => setToastMessage(null), 5000);
    } finally {
      setSaving(false);
    }
  };

  const columns = useMemo<ColumnDef<UnabridgedTrait>[]>(
    () => [
      {
        id: 'container',
        header: () => 'Container',
        accessorFn: (row) => containerFromTrait(row.trait_id),
        enableSorting: false,
        size: 160,
      },
      {
        id: 'trait',
        header: () => 'Trait',
        accessorKey: 'trait_id',
        enableSorting: false,
        size: 280,
        cell: ({ row }) => {
          const trait = row.original;
          const lastObserved = trait.last_observed;
          let daysOld = 0;
          let isStale = false;

          if (lastObserved) {
            try {
              const lastDate = new Date(lastObserved);
              const now = new Date();
              daysOld = Math.floor((now.getTime() - lastDate.getTime()) / (1000 * 60 * 60 * 24));
              isStale = daysOld > 30; // Consider stale after 30 days
            } catch (e) {
              // Invalid date
            }
          }

          return (
            <div className="text-slate-100">
              <div className="flex items-center gap-2">
                <span className="font-medium">{trait.trait_id}</span>
                {isStale && (
                  <span
                    className="text-slate-400 cursor-help text-xs"
                    title={`Last updated ${daysOld} days ago`}
                  >
                    🕒
                  </span>
                )}
              </div>
              {trait.reasons?.length ? (
                <div className="mt-1 text-xs text-slate-500">{trait.reasons.join(', ')}</div>
              ) : null}
            </div>
          );
        },
      },
      {
        id: 'value',
        header: () => 'Value',
        accessorFn: (row) => row.value,
        enableSorting: false,
        size: 280,
        cell: ({ row }) => {
          const hasConflict = row.original.metadata?.conflicts || row.original.metadata?.tensions;
          const isEditing = editingTrait === row.original.trait_id;

          if (isEditing) {
            return (
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={editValue}
                  onChange={(e) => setEditValue(e.target.value)}
                  className="rounded border border-slate-700 bg-slate-950/70 px-2 py-1 text-sm text-slate-100 focus:border-cyan-400 focus:outline-none"
                  disabled={saving}
                  autoFocus
                />
                <button
                  onClick={() => handleEditSave(row.original.trait_id, row.original.value)}
                  disabled={saving}
                  className="text-xs text-emerald-400 hover:text-emerald-300 disabled:opacity-40"
                >
                  ✓
                </button>
                <button
                  onClick={handleEditCancel}
                  disabled={saving}
                  className="text-xs text-slate-400 hover:text-slate-300 disabled:opacity-40"
                >
                  ✕
                </button>
              </div>
            );
          }

          return (
            <div className="flex items-center gap-2">
              <span className="text-slate-200">{renderValue(row.original.value)}</span>
              {hasConflict ? (
                <span
                  className="text-amber-400 cursor-help"
                  title="This trait has active conflicts or tensions"
                >
                  ⚠️
                </span>
              ) : null}
              <button
                onClick={() => handleEditStart(row.original.trait_id, row.original.value)}
                className="ml-auto text-xs text-slate-400 hover:text-slate-200"
                title="Edit trait value"
              >
                ✏️
              </button>
            </div>
          );
        },
      },
      {
        id: 'ucn',
        header: () => 'UCN',
        accessorFn: (row) => row.ucn,
        enableSorting: false,
        size: 90,
        cell: ({ row }) => <span className="text-slate-300">{row.original.ucn ?? '—'}</span>,
      },
      {
        id: 'rr',
        header: () => 'RR',
        accessorFn: (row) => row.rr,
        enableSorting: false,
        size: 160,
        cell: ({ row }) => {
          const change = changedTraits?.find(c => c.trait === row.original.trait_id);
          return (
            <div className="flex items-center gap-2">
              <RRBadge rr={row.original.rr} />
              {change && (
                <span
                  className={`text-xs font-semibold ${change.delta > 0 ? 'text-emerald-400' : 'text-rose-400'}`}
                  title={`Changed from ${Math.round(change.old_rr)} to ${Math.round(change.new_rr)}`}
                >
                  {change.delta > 0 ? '+' : ''}{Math.round(change.delta)}
                </span>
              )}
            </div>
          );
        },
      },
      {
        id: 'curiosity',
        header: () => 'Curiosity',
        accessorFn: (row) => row.curiosity,
        enableSorting: false,
        size: 110,
        cell: ({ row }) => <CuriosityBadge curiosity={row.original.curiosity} />,
      },
      {
        id: 'governance',
        header: () => 'Governance',
        accessorFn: (row) => row.badges ?? [],
        enableSorting: false,
        size: 240,
        cell: ({ row }) => {
          const governance = governanceBadges(row.original.badges ?? []);
          if (!governance.length) {
            return <span className="text-xs text-slate-500">—</span>;
          }
          return (
            <div className="flex flex-wrap gap-2">
              {governance.map((badge) => (
                <span
                  key={badge.label}
                  className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${
                    badge.kind === 'sensitive'
                      ? 'bg-rose-500/20 text-rose-200'
                      : 'bg-amber-500/20 text-amber-200'
                  }`}
                >
                  <span aria-hidden>{badge.icon}</span>
                  <span>{badge.label}</span>
                </span>
              ))}
            </div>
          );
        },
      },
      {
        id: 'why',
        header: () => 'Why?',
        enableSorting: false,
        size: 80,
        cell: ({ row }) => (
          <button
            type="button"
            className="rounded-full border border-slate-700 px-2 py-1 text-xs text-violet-200 hover:border-violet-400 hover:text-violet-100 disabled:opacity-40"
            onClick={() => {
              setSelectedTrait({
                id: row.original.trait_id,
                value: row.original.value,
                userId: snapshot?.user_id || '',
              });
              setProvenanceOpen(true);
            }}
            aria-label={`View provenance for ${row.original.trait_id}`}
          >
            Why?
          </button>
        ),
      },
      {
        id: 'timeline',
        header: () => 'Timeline',
        enableSorting: false,
        size: 100,
        cell: ({ row }) => (
          <button
            type="button"
            className="rounded-full border border-slate-700 px-2 py-1 text-xs text-cyan-200 hover:border-cyan-400 hover:text-cyan-100 disabled:opacity-40"
            onClick={() => onTimeline?.(row.original.trait_id)}
            disabled={timelineDisabled}
            aria-label={`View timeline for ${row.original.trait_id}`}
          >
            🕒
          </button>
        ),
      },
    ],
    [onTimeline, timelineDisabled, snapshot?.user_id, editingTrait, editValue, saving, changedTraits]
  );

  const table = useReactTable({
    data: filteredTraits,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  const parentRef = useRef<HTMLDivElement | null>(null);
  const rowModel = table.getRowModel();
  const rowVirtualizer = useVirtualizer({
    count: rowModel.rows.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 68,
    overscan: 12,
  });
  const virtualRows = rowVirtualizer.getVirtualItems();
  const totalSize = rowVirtualizer.getTotalSize();
  const totalRowCount = rowModel.rows.length;
  const visibleRowCount = virtualRows.length;

  useEffect(() => {
    updateVirtualizerMetrics('unabridged', {
      total: totalRowCount,
      visible: visibleRowCount,
    });
  }, [totalRowCount, visibleRowCount]);

  useEffect(() => {
    return () => {
      removeVirtualizerMetrics('unabridged');
    };
  }, []);

  return (
    <section
      id={id}
      className="rounded-2xl border border-slate-800 bg-slate-900/60 shadow-xl"
      aria-label="Unabridged traits"
    >
      <header className="flex items-center justify-between border-b border-slate-800 px-5 py-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">Unabridged</h2>
        {loading ? <span className="text-xs text-slate-500">Refreshing…</span> : null}
      </header>
      <div className="flex flex-col gap-4 px-5 py-5 text-sm">
        {error ? <PanelError message={error} onRetry={onRetry} /> : null}
        <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <label className="flex flex-1 flex-col gap-1 text-xs uppercase tracking-wide text-slate-400">
            Search
            <input
              type="search"
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
              placeholder="Filter by trait, value, or reason"
              className="w-full rounded-lg border border-slate-700 bg-slate-950/70 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:border-cyan-400 focus:outline-none"
            />
          </label>
          <label className="flex w-full flex-col gap-1 text-xs uppercase tracking-wide text-slate-400 md:w-52">
            Container
            <select
              value={containerFilter}
              onChange={(event) => setContainerFilter(event.target.value)}
              className="w-full rounded-lg border border-slate-700 bg-slate-950/70 px-3 py-2 text-sm text-slate-100 focus:border-cyan-400 focus:outline-none"
            >
              <option value="all">All containers</option>
              {containers.map((container) => (
                <option key={container} value={container}>
                  {container}
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-2 text-xs text-slate-300 md:pt-5">
            <input
              type="checkbox"
              checked={showHighCuriosity}
              onChange={(e) => setShowHighCuriosity(e.target.checked)}
              className="rounded border-slate-700 bg-slate-950/70 text-violet-500 focus:ring-violet-500"
            />
            High curiosity ≥60%
          </label>
        </div>

        <div
          ref={parentRef}
          className="max-h-80 overflow-auto rounded-xl border border-slate-800 bg-slate-950/40"
        >
          {rowModel.rows.length ? (
            <table className="min-w-full divide-y divide-slate-800 text-left text-sm text-slate-100">
              <thead className="bg-slate-950/70 text-xs uppercase tracking-wide text-slate-400">
                {table.getHeaderGroups().map((headerGroup) => (
                  <tr key={headerGroup.id}>
                    {headerGroup.headers.map((header) => (
                      <th
                        key={header.id}
                        scope="col"
                        className={`px-3 py-3 ${headerClassFor(header.column.id)}`}
                        style={{ width: header.getSize() }}
                      >
                        {header.isPlaceholder
                          ? null
                          : flexRender(header.column.columnDef.header, header.getContext())}
                      </th>
                    ))}
                  </tr>
                ))}
              </thead>
              <tbody
                className="divide-y divide-slate-800"
                style={{ position: 'relative', height: `${totalSize}px` }}
              >
                {virtualRows.map((virtualRow) => {
                  const row = rowModel.rows[virtualRow.index];
                  if (!row) {
                    return null;
                  }
                  return (
                    <tr
                      key={row.id}
                      ref={(node) => {
                        if (node) {
                          rowVirtualizer.measureElement(node);
                        }
                      }}
                      className="hover:bg-slate-900/70"
                      style={{
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        width: '100%',
                        transform: `translateY(${virtualRow.start}px)`
                      }}
                    >
                      {row.getVisibleCells().map((cell) => (
                        <td
                          key={cell.id}
                          className={`align-top ${cellClassFor(cell.column.id)}`}
                          style={{ width: cell.column.getSize() }}
                        >
                          {flexRender(cell.column.columnDef.cell, cell.getContext())}
                        </td>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          ) : (
            <div className="px-4 py-6 text-sm text-slate-500">No traits match the current filters.</div>
          )}
        </div>
      </div>

      {selectedTrait && (
        <ProvenanceModal
          open={provenanceOpen}
          traitId={selectedTrait.id}
          traitValue={selectedTrait.value}
          userId={selectedTrait.userId}
          onClose={() => {
            setProvenanceOpen(false);
            setSelectedTrait(null);
          }}
        />
      )}

      {toastMessage && (
        <div className="fixed bottom-4 right-4 rounded-lg border border-emerald-500/60 bg-slate-950/90 px-4 py-3 text-sm text-emerald-200 shadow-xl">
          {toastMessage}
        </div>
      )}
    </section>
  );
}

function renderValue(value: unknown): string {
  if (Array.isArray(value)) {
    return value.map((item) => renderValue(item)).join(', ');
  }
  if (value && typeof value === 'object') {
    return JSON.stringify(value);
  }
  if (value === null || value === undefined || value === '') {
    return '—';
  }
  return String(value);
}

function containerFromTrait(traitId: string): string {
  return traitId.includes('.') ? traitId.split('.')[0] : traitId;
}

function headerClassFor(columnId: string): string {
  switch (columnId) {
    case 'container':
      return 'text-left';
    case 'trait':
    case 'value':
    case 'governance':
      return 'text-left';
    case 'ucn':
    case 'timeline':
      return 'text-left';
    default:
      return '';
  }
}

function cellClassFor(columnId: string): string {
  switch (columnId) {
    case 'container':
      return 'px-3 py-3 text-slate-300';
    case 'trait':
      return 'px-3 py-3 text-slate-100';
    case 'value':
      return 'px-3 py-3 text-slate-200';
    case 'ucn':
      return 'px-3 py-3 text-slate-300';
    case 'governance':
      return 'px-3 py-3 text-slate-200';
    case 'timeline':
      return 'px-3 py-3';
    default:
      return 'px-3 py-3';
  }
}

function governanceBadges(badges: string[]) {
  const meta = {
    sensitive: { icon: '🔒', label: 'Sensitive', kind: 'sensitive' as const },
    observational: { icon: '🔍', label: 'Observational', kind: 'observational' as const },
  };
  return badges
    .map((badge) => meta[badge as keyof typeof meta])
    .filter(Boolean) as Array<{ icon: string; label: string; kind: 'sensitive' | 'observational' }>;
}
