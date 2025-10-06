interface RRBadgeProps {
  rr: number | null | undefined;
}

interface CuriosityBadgeProps {
  curiosity: number | null | undefined;
}

function getRRBand(rr: number): 'low' | 'medium' | 'high' {
  if (rr < 333) return 'low';
  if (rr <= 667) return 'medium';
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
  if (curiosity < 0.2) return 'bg-slate-500/20 text-slate-300 border-slate-500/40';
  if (curiosity < 0.5) return 'bg-blue-500/20 text-blue-200 border-blue-500/40';
  if (curiosity < 0.8) return 'bg-violet-500/20 text-violet-200 border-violet-500/40';
  return 'bg-fuchsia-500/20 text-fuchsia-200 border-fuchsia-500/40';
}

export function RRBadge({ rr }: RRBadgeProps) {
  if (rr == null) {
    return <span className="text-xs text-slate-500">—</span>;
  }

  const band = getRRBand(rr);
  const colorClass = getRRBandColor(band);

  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${colorClass}`}
      title={`Refinement Rating: ${Math.round(rr)} (${band})`}
    >
      RR {Math.round(rr)}
    </span>
  );
}

export function CuriosityBadge({ curiosity }: CuriosityBadgeProps) {
  if (curiosity == null) {
    return <span className="text-xs text-slate-500">—</span>;
  }

  const percentage = Math.round(curiosity * 100);
  const colorClass = getCuriosityColor(curiosity);

  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${colorClass}`}
      title={`Curiosity: ${percentage}%`}
    >
      Cur {percentage}%
    </span>
  );
}
