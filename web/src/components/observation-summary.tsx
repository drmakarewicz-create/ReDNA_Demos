'use client';

import { useMemo } from 'react';

import type {
  ObservationAggregates,
  ObservationPersonaBreakdown,
  ObservationWindowMetrics,
  PersonaRosterEntry,
} from '../lib/api';
import { PanelError } from './panel-error';

interface ObservationSummaryProps {
  aggregates: ObservationAggregates | null;
  personas?: PersonaRosterEntry[];
  windowKey: string;
  onWindowChange: (key: string) => void;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
}

export function ObservationSummary({
  aggregates,
  personas,
  windowKey,
  onWindowChange,
  loading,
  error,
  onRetry,
}: ObservationSummaryProps) {
  const windowOptions = useMemo(() => deriveWindowOptions(aggregates), [aggregates]);
  const metrics = useMemo(() => resolveWindowMetrics(aggregates, windowKey), [aggregates, windowKey]);
  const dialogChips = useMemo(() => topDistribution(metrics?.dialog_acts.distribution), [metrics?.dialog_acts.distribution]);
  const cadenceChips = useMemo(() => topDistribution(metrics?.cadence.histogram), [metrics?.cadence.histogram]);
  const latencyEntries = useMemo(() => histogramEntries(metrics?.latency.histogram), [metrics?.latency.histogram]);
  const personaEntries = useMemo(
    () => derivePersonaEntries(metrics?.per_persona, personas ?? []),
    [metrics?.per_persona, personas]
  );

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/60 shadow-xl" aria-live="polite">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 px-5 py-4">
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
            Conversation Metrics
          </h2>
          {aggregates && windowOptions.length ? (
            <WindowSelect
              options={windowOptions}
              activeKey={metrics?.__windowKey ?? windowOptions[0] ?? 'all'}
              onChange={onWindowChange}
              disabled={loading || !aggregates}
            />
          ) : null}
        </div>
        {loading ? <span className="text-xs text-slate-500">Refreshing…</span> : null}
      </header>
      {error ? (
        <div className="px-5 pt-4">
          <PanelError message={error} onRetry={onRetry} />
        </div>
      ) : null}
      {metrics ? (
        <div className="flex flex-col gap-4 px-5 py-5">
          <div className="flex flex-wrap gap-3 text-xs">
            <Chip
              label="Dialog Act"
              value={metrics.dialog_acts.latest ?? '—'}
              tooltip={buildTooltip(dialogChips)}
            />
            <Chip
              label="Cadence"
              value={metrics.cadence.latest_bucket ?? '—'}
              tooltip={buildTooltip(cadenceChips)}
            />
            <Chip label="Entries" value={metrics.observation_count.toString()} />
          </div>

          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            <MetricTile label="Dialog mix" value={formatChipPreview(dialogChips)} hint={buildTooltip(dialogChips)} />
            <MetricTile label="Cadence mix" value={formatChipPreview(cadenceChips)} hint={buildTooltip(cadenceChips)} />
            <MetricTile
              label="Latency median"
              value={formatMs(metrics.latency.median_ms)}
              hint={`Mean ${formatMs(metrics.latency.mean_ms)}`}
            />
          </div>

          <LatencyCard entries={latencyEntries} />

          {personaEntries.length ? <PersonaBreakdown entries={personaEntries} /> : null}
        </div>
      ) : (
        <div className="px-5 py-6 text-sm text-slate-500">
          Metrics unavailable for this user. Start a session to collect conversation telemetry.
        </div>
      )}
    </section>
  );
}

function Chip({ label, value, tooltip }: { label: string; value: string; tooltip?: string }) {
  return (
    <span
      className="inline-flex items-center gap-2 rounded-full border border-slate-700 bg-slate-950/80 px-3 py-1 text-xs text-slate-200"
      title={tooltip}
    >
      <span className="uppercase tracking-wide text-slate-400">{label}</span>
      <span className="font-semibold text-slate-100">{value}</span>
    </span>
  );
}

function MetricTile({ label, value, hint }: { label: string; value: string; hint?: string | null }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
      <p className="text-xs uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-1 text-lg font-semibold text-slate-100" title={hint ?? undefined}>
        {value}
      </p>
      {hint ? <p className="mt-1 text-xs text-slate-500">{hint}</p> : null}
    </div>
  );
}

function formatMs(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) {
    return '—';
  }
  return `${Math.round(value)} ms`;
}

function topDistribution(map?: Record<string, number> | null) {
  if (!map) {
    return [] as Array<{ key: string; count: number }>;
  }
  return Object.entries(map)
    .map(([key, count]) => ({ key, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 4);
}

function buildTooltip(entries: Array<{ key: string; count: number }>) {
  if (!entries.length) {
    return undefined;
  }
  return entries.map((entry) => `${entry.key}: ${entry.count}`).join('\n');
}

function formatChipPreview(entries: Array<{ key: string; count: number }>) {
  if (!entries.length) {
    return '—';
  }
  return entries
    .slice(0, 3)
    .map((entry) => `${entry.key} (${entry.count})`)
    .join(', ');
}

function histogramEntries(map?: Record<string, number> | null) {
  if (!map) {
    return [] as Array<{ bucket: string; count: number; order: number }>;
  }
  return Object.entries(map)
    .map(([bucket, count]) => ({ bucket, count, order: parseLatencyBucket(bucket) }))
    .sort((a, b) => a.order - b.order);
}

function parseLatencyBucket(bucket: string) {
  const numeric = parseFloat(bucket.replace(/[^0-9.]+/g, ''));
  return Number.isNaN(numeric) ? Number.MAX_SAFE_INTEGER : numeric;
}

function LatencyCard({ entries }: { entries: Array<{ bucket: string; count: number }> }) {
  if (!entries.length) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4 text-sm text-slate-400">
        <p className="text-xs uppercase tracking-wide text-slate-400">Latency trend</p>
        <p className="mt-2 text-sm">No latency histogram captured yet.</p>
      </div>
    );
  }

  const counts = entries.map((entry) => entry.count);
  const max = Math.max(...counts, 1);
  const svgWidth = 160;
  const svgHeight = 60;
  const barGap = 4;
  const barWidth = (svgWidth - barGap * (counts.length - 1)) / counts.length;

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
      <p className="text-xs uppercase tracking-wide text-slate-400">Latency trend</p>
      <svg
        width={svgWidth}
        height={svgHeight}
        role="img"
        aria-label="Latency histogram sparkline"
        className="mt-3"
      >
        {entries.map((entry, index) => {
          const height = Math.round((entry.count / max) * (svgHeight - 12));
          const x = index * (barWidth + barGap);
          const y = svgHeight - height;
          return (
            <g key={entry.bucket}>
              <title>{`${entry.bucket}: ${entry.count}`}</title>
              <rect
                x={x}
                y={y}
                width={barWidth}
                height={height}
                rx={2}
                fill="#38bdf8"
                fillOpacity={0.55 + (entry.count / max) * 0.35}
              />
            </g>
          );
        })}
      </svg>
      <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-400">
        {entries.slice(0, 4).map((entry) => (
          <span key={entry.bucket} className="rounded-full bg-slate-800 px-2 py-0.5">
            {entry.bucket}: {entry.count}
          </span>
        ))}
      </div>
    </div>
  );
}

const DEFAULT_WINDOW_LABELS: Record<string, string> = {
  all: 'All time',
  '1h': 'Last hour',
  '24h': 'Last 24h',
  session: 'Current session',
};

type PersonaEntry = {
  key: string;
  label: string;
  icon?: string | null;
  count: number;
  latestAct?: string | null;
};

function deriveWindowOptions(aggregates: ObservationAggregates | null): string[] {
  if (!aggregates) {
    return ['all'];
  }
  const base = ['all'];
  const extra = Object.keys(aggregates.windows ?? {});
  const merged = [...base, ...extra];
  return Array.from(new Set(merged));
}

function resolveWindowMetrics(
  aggregates: ObservationAggregates | null,
  requestedKey: string,
): (ObservationWindowMetrics & { __windowKey: string }) | null {
  if (!aggregates) {
    return null;
  }
  const normalizedKey = requestedKey && requestedKey !== '' ? requestedKey : 'all';
  if (normalizedKey !== 'all' && aggregates.windows?.[normalizedKey]) {
    return { ...aggregates.windows[normalizedKey], __windowKey: normalizedKey };
  }
  return {
    observation_count: aggregates.observation_count,
    dialog_acts: aggregates.dialog_acts,
    cadence: aggregates.cadence,
    latency: aggregates.latency,
    per_persona: aggregates.per_persona,
    __windowKey: 'all',
  };
}

function derivePersonaEntries(
  perPersona: Record<string, ObservationPersonaBreakdown> | undefined,
  personas: PersonaRosterEntry[],
): PersonaEntry[] {
  if (!perPersona) {
    return [];
  }
  const rosterMap = new Map(personas.map((persona) => [persona.key, persona]));
  return Object.entries(perPersona)
    .map(([key, detail]) => {
      const roster = rosterMap.get(key);
      const label = roster?.label ?? fallbackPersonaLabel(key);
      return {
        key,
        label,
        icon: roster?.icon,
        count: detail?.observation_count ?? 0,
        latestAct: detail?.dialog_acts?.latest ?? null,
      };
    })
    .sort((a, b) => b.count - a.count);
}

function fallbackPersonaLabel(rawKey: string): string {
  return rawKey
    .replace(/[_\-]+/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function PersonaBreakdown({ entries }: { entries: PersonaEntry[] }) {
  return (
    <div className="mt-2 rounded-xl border border-slate-800 bg-slate-950/60 p-4">
      <p className="text-xs uppercase tracking-wide text-slate-400">Persona activity</p>
      <ul className="mt-3 space-y-2 text-xs text-slate-300">
        {entries.map((entry) => (
          <li key={entry.key} className="flex items-center justify-between gap-3">
            <span className="flex items-center gap-2">
              {entry.icon ? <span aria-hidden="true">{entry.icon}</span> : null}
              <span className="font-semibold text-slate-100">{entry.label}</span>
            </span>
            <span className="text-slate-400">
              {entry.count} entr{entry.count === 1 ? 'y' : 'ies'}
              {entry.latestAct ? ` · latest ${entry.latestAct}` : ''}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function WindowSelect({
  options,
  activeKey,
  onChange,
  disabled,
}: {
  options: string[];
  activeKey: string;
  onChange: (key: string) => void;
  disabled?: boolean;
}) {
  if (!options.length) {
    return null;
  }
  const resolved = options.includes(activeKey) ? activeKey : options[0];
  return (
    <label className="flex items-center gap-2 text-xs text-slate-400">
      Window
      <select
        className="rounded-full border border-slate-700 bg-slate-950/80 px-2 py-1 text-xs text-slate-100 focus:border-cyan-400 focus:outline-none"
        value={resolved}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled || options.length <= 1}
        aria-label="Select observation window"
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {DEFAULT_WINDOW_LABELS[option] ?? fallbackPersonaLabel(option)}
          </option>
        ))}
      </select>
    </label>
  );
}
