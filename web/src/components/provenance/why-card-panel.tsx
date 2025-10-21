'use client';

import React, { useMemo } from 'react';
import { PanelSkeleton } from '@/components/panel-skeleton';
import {
  formatTimestamp,
  type WhyCard,
  formatTraitValue,
  shapeWhyCard,
  type ShapedWhyCard,
  formatPercent,
  type RRMeta,
} from '@/lib/provenanceClient';

interface WhyCardPanelProps {
  loading: boolean;
  card: WhyCard | null;
  error?: string | null;
  traitId?: string;
  value?: unknown;
}

export const WhyCardPanel: React.FC<WhyCardPanelProps> = ({ loading, card, error, traitId, value }) => {
  const displayValue = useMemo(() => {
    const metadata = card?.metadata ?? {};
    const metadataValue =
      (metadata as Record<string, unknown>)?.trait_value ??
      (metadata as Record<string, unknown>)?.value ??
      (metadata as Record<string, unknown>)?.resolved_value ??
      null;

    if (metadataValue !== null && metadataValue !== undefined) {
      return formatTraitValue(metadataValue);
    }

    if (value !== undefined) {
      return formatTraitValue(value);
    }

    return '—';
  }, [card?.metadata, value]);

  const shapedCard = useMemo<ShapedWhyCard>(() => shapeWhyCard(card, value), [card, value]);

  return (
    <section data-testid="why-card-panel">
      <div className="text-xs uppercase tracking-wide text-gray-500 font-semibold mb-2 flex items-center gap-2">
        <span>Why-Card (Explainability)</span>
        {traitId && <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-gray-100 text-gray-600">{traitId}</span>}
      </div>

      <div className="mb-3 text-xs text-gray-500">
        <span className="font-semibold text-gray-700">Value:</span>{' '}
        <span className="text-gray-900">{displayValue}</span>
      </div>

      {loading && (
        <PanelSkeleton rows={4} columns={1} className="bg-gray-50 rounded-md border border-gray-200 p-3" />
      )}

      {!loading && error && (
        <div className="p-3 rounded-md bg-red-50 border border-red-200">
          <div className="text-sm text-red-800 font-medium">Unable to load Why-Card</div>
          <div className="text-xs text-red-600 mt-1">{error}</div>
        </div>
      )}

      {!loading && !error && card && <WhyCardDetails shaped={shapedCard} />}

      {!loading && !error && !card && (
        <div className="p-3 rounded-md border border-dashed border-gray-300 bg-gray-50 text-sm text-gray-600">
          No Why-Card yet. Promote this trait or provide more evidence to unlock a rationale.
        </div>
      )}
    </section>
  );
};

WhyCardPanel.displayName = 'WhyCardPanel';

interface WhyCardDetailsProps {
  shaped: ShapedWhyCard;
}

const MetricPill: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <span className="inline-flex items-center gap-1 rounded-full border border-gray-200 bg-white px-2 py-0.5 text-xs font-medium text-gray-700">
    <span className="uppercase text-[10px] tracking-wider text-gray-500">{label}</span>
    <span className="font-mono text-gray-800">{value}</span>
  </span>
);

const formatUcnSegment = (label: string, value: NullableNumber) => {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return null;
  }
  return `${label.toUpperCase()} ${value.toFixed(2)}`;
};

type NullableNumber = number | null | undefined;

export const WhyCardDetails: React.FC<WhyCardDetailsProps> = ({ shaped }) => {
  const { what, why, next, rr, curiosity, rrMeta, ucn, createdAt, source, isFallback } = shaped;

  const ucnPills: string[] = [];
  const ucnU = formatUcnSegment('u', ucn.u);
  const ucnC = formatUcnSegment('c', ucn.c);
  const ucnN = formatUcnSegment('n', ucn.n);
  if (ucnU) ucnPills.push(ucnU);
  if (ucnC) ucnPills.push(ucnC);
  if (ucnN) ucnPills.push(ucnN);
  if (!ucnPills.length) {
    if (typeof ucn.raw === 'number') {
      ucnPills.push(`UCN ${ucn.raw.toFixed(2)}`);
    } else {
      ucnPills.push('UCN —');
    }
  }

  const rrDisplay = formatPercent(rr ?? undefined);
  const curiosityDisplay = formatPercent(curiosity ?? undefined);
  const rrMetaTooltip = formatRrMetaTooltip(rrMeta);

  return (
    <div
      className="space-y-4 rounded-md border border-blue-200 bg-gradient-to-br from-blue-50 via-white to-white p-3 shadow-sm"
      data-whycard-shape={isFallback ? 'fallback' : 'exact'}
    >
      <div className="grid gap-3 md:grid-cols-3">
        <div className="rounded-lg border border-blue-100 bg-white/70 p-3">
          <div className="text-xs font-semibold uppercase tracking-wide text-blue-600">What</div>
          <div className="mt-2 text-sm text-gray-900 whitespace-pre-line">{what || '—'}</div>
        </div>
        <div className="rounded-lg border border-blue-100 bg-white/70 p-3">
          <div className="text-xs font-semibold uppercase tracking-wide text-blue-600">Why</div>
          <div className="mt-2 text-sm text-gray-900 whitespace-pre-line">{why || '—'}</div>
        </div>
        <div className="rounded-lg border border-blue-100 bg-white/70 p-3">
          <div className="text-xs font-semibold uppercase tracking-wide text-blue-600">Next</div>
          <div className="mt-2 text-sm text-gray-900 whitespace-pre-line">{next || '—'}</div>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 text-xs text-gray-600">
        <div className="flex items-center gap-1">
          <MetricPill label="RR" value={rrDisplay} />
          {rrMetaTooltip ? (
            <span className="text-[11px] text-gray-400 cursor-help" title={rrMetaTooltip} aria-label="RR metadata">
              ℹ︎
            </span>
          ) : null}
        </div>
        <MetricPill label="Cur" value={curiosityDisplay} />
        {ucnPills.map((pill) => {
          const [label, ...rest] = pill.split(' ');
          return <MetricPill key={pill} label={label} value={rest.join(' ')} />;
        })}
      </div>

      {(source || createdAt) && (
        <div className="flex flex-wrap items-center gap-3 text-xs text-gray-500">
          {source ? <span>Source: {source}</span> : null}
          {createdAt ? <span>Created: {formatTimestamp(createdAt)}</span> : null}
        </div>
      )}
    </div>
  );
};

WhyCardDetails.displayName = 'WhyCardDetails';

function formatRrMetaTooltip(rrMeta: RRMeta | null): string | null {
  if (!rrMeta) {
    return null;
  }
  const raw = typeof rrMeta.rr_raw === 'number' && Number.isFinite(rrMeta.rr_raw) ? rrMeta.rr_raw : null;
  const scale = rrMeta.scale ? String(rrMeta.scale) : 'unspecified';
  if (raw === null) {
    return `Original scale: ${scale}`;
  }
  const precision = Math.abs(raw) >= 100 ? 1 : 2;
  return `Raw RR: ${raw.toFixed(precision)} (scale: ${scale})`;
}
