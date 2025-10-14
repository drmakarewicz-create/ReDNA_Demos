'use client';

import { useState } from 'react';

interface ReasonMapEntry {
  trait: string;
  rr: number;
  weight: number;
  influence: string;
}

interface BeliefReasonMapProps {
  reasonMap: ReasonMapEntry[];
  rr_summary?: {
    BeliefValueDNA?: number;
    CogDNA?: number;
    MotivationDNA?: number;
    PsyDNA?: number;
    EmDNA?: number;
  };
}

export function BeliefReasonMap({ reasonMap, rr_summary }: BeliefReasonMapProps) {
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  if (!reasonMap || reasonMap.length === 0) {
    return (
      <div className="rounded-xl border border-purple-500/20 bg-slate-950/40 p-6">
        <div className="flex items-center gap-2 mb-3">
          <span className="text-lg">🧠</span>
          <h4 className="text-sm font-semibold text-purple-200">Reasoning Transparency</h4>
        </div>
        <p className="text-xs text-slate-400 italic">
          Ask a question to see which traits influence the response
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-purple-500/20 bg-slate-950/40 p-6">
      <div className="flex items-center gap-2 mb-4">
        <span className="text-lg">🧠</span>
        <h4 className="text-sm font-semibold text-purple-200">Reasoning Transparency</h4>
      </div>

      {/* RR Summary */}
      {rr_summary && (
        <div className="mb-4 pb-4 border-b border-purple-500/20">
          <div className="text-xs text-slate-400 mb-2">ReDNA Contribution</div>
          <div className="flex flex-wrap gap-3">
            {Object.entries(rr_summary).map(([namespace, rr]) => (
              <div key={namespace} className="flex items-center gap-2">
                <span className="text-xs text-slate-300">{namespace.replace('DNA', '')}</span>
                <div className="flex items-center gap-1">
                  <div className="w-16 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-purple-500 to-purple-400"
                      style={{ width: `${rr}%` }}
                    />
                  </div>
                  <span className="text-xs font-medium text-purple-400">{rr}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Reason Map Table */}
      <div className="space-y-2">
        {reasonMap.map((entry, idx) => {
          const isExpanded = expandedRow === entry.trait;
          const traitName = entry.trait.split('.').pop() || entry.trait;
          const namespace = entry.trait.includes('.') ? entry.trait.split('.').slice(0, -1).join('.') : '';

          return (
            <div
              key={`${entry.trait}-${idx}`}
              className="rounded-lg border border-purple-500/20 bg-slate-900/50 overflow-hidden"
            >
              <button
                onClick={() => setExpandedRow(isExpanded ? null : entry.trait)}
                className="w-full px-4 py-3 flex items-center justify-between hover:bg-purple-500/5 transition-colors"
              >
                <div className="flex items-center gap-3 flex-1">
                  {/* Weight Indicator */}
                  <div className="flex items-center gap-1.5">
                    <div className="w-12 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-yellow-500 to-yellow-400"
                        style={{ width: `${entry.weight * 100}%` }}
                      />
                    </div>
                    <span className="text-xs font-medium text-yellow-400 w-8">
                      {Math.round(entry.weight * 100)}%
                    </span>
                  </div>

                  {/* Trait Name */}
                  <div className="flex-1 text-left">
                    <div className="text-sm font-medium text-slate-200">{traitName}</div>
                    {namespace && (
                      <div className="text-xs text-slate-500 mt-0.5">{namespace}</div>
                    )}
                  </div>

                  {/* RR Badge */}
                  <div className="px-2 py-1 rounded bg-purple-500/20 border border-purple-500/30">
                    <span className="text-xs font-medium text-purple-300">RR {entry.rr}</span>
                  </div>

                  {/* Expand Icon */}
                  <svg
                    className={`w-4 h-4 text-slate-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </div>
              </button>

              {/* Expanded Details */}
              {isExpanded && (
                <div className="px-4 py-3 border-t border-purple-500/20 bg-slate-950/60">
                  <div className="text-xs text-slate-400 mb-1">Influence on Response:</div>
                  <p className="text-sm text-slate-300">{entry.influence}</p>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Legend */}
      <div className="mt-4 pt-4 border-t border-purple-500/10">
        <div className="text-xs text-slate-500">
          <span className="text-yellow-400">Weight</span> = How much this trait influenced the response •{' '}
          <span className="text-purple-300">RR</span> = Current trait strength (0-100)
        </div>
      </div>
    </div>
  );
}
