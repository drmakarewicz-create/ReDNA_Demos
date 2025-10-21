import { formatPercent } from '@/lib/provenanceClient';

interface RRBadgeProps {
  rr: number | null | undefined;
}

interface CuriosityBadgeProps {
  curiosity: number | null | undefined;
}

function clampPercent(value: number): number {
  if (!Number.isFinite(value)) {
    return 0;
  }
  return Math.min(100, Math.max(0, value));
}

function normalizePercentValue(value: number | null | undefined): number | null {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return null;
  }
  if (value > 100) {
    return clampPercent(value / 10);
  }
  if (value <= 1) {
    return clampPercent(value * 100);
  }
  return clampPercent(value);
}

function getRRBand(rr: number): 'low' | 'medium' | 'high' {
  if (rr < 33.4) return 'low';
  if (rr <= 66.7) return 'medium';
  return 'high';
}

function getRRBandColor(band: 'low' | 'medium' | 'high'): string {
  switch (band) {
    case 'low':
      return 'bg-rose-500/20 text-rose-200 border-rose-500/40';
    case 'medium':
      return 'bg-amber-500/20 text-amber-200 border-amber-500/40';
    case 'high':
      return 'bg-emerald-500/20 text-emerald-200 border-emerald-500/40';
  }
}

function getCuriosityColor(curiosity: number): string {
  if (curiosity < 20) return 'bg-slate-500/20 text-slate-300 border-slate-500/40';
  if (curiosity < 50) return 'bg-blue-500/20 text-blue-200 border-blue-500/40';
  if (curiosity < 80) return 'bg-violet-500/20 text-violet-200 border-violet-500/40';
  return 'bg-fuchsia-500/20 text-fuchsia-200 border-fuchsia-500/40';
}

export function RRBadge({ rr }: RRBadgeProps) {
  const rrPercent = normalizePercentValue(rr);
  if (rrPercent === null) {
    return <span className="text-xs text-slate-500">—</span>;
  }

  const band = getRRBand(rrPercent);
  const colorClass = getRRBandColor(band);

  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${colorClass}`}
      title={`Refinement Rating: ${formatPercent(rrPercent)} (${band})`}
    >
      RR {Math.round(rrPercent)}%
    </span>
  );
}

export function CuriosityBadge({ curiosity }: CuriosityBadgeProps) {
  const curiosityPercent = normalizePercentValue(curiosity);
  if (curiosityPercent === null) {
    return <span className="text-xs text-slate-500">—</span>;
  }

  const percentage = Math.round(curiosityPercent);
  const colorClass = getCuriosityColor(curiosityPercent);

  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${colorClass}`}
      title={`Curiosity: ${formatPercent(curiosityPercent)}`}
    >
      Cur {percentage}%
    </span>
  );
}
