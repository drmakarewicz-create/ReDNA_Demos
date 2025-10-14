'use client';

import { useState } from 'react';

interface Container {
  path: string;
  similarity: number;
  rr: number;
}

interface EvidenceLinksProps {
  containers: Container[];
  onContainerClick?: (path: string) => void;
}

export function EvidenceLinks({ containers, onContainerClick }: EvidenceLinksProps) {
  const [expandedContainer, setExpandedContainer] = useState<string | null>(null);

  if (!containers || containers.length === 0) {
    return null;
  }

  const getSimilarityColor = (similarity: number) => {
    if (similarity >= 0.8) return 'text-green-400 border-green-500/30 bg-green-500/10';
    if (similarity >= 0.6) return 'text-yellow-400 border-yellow-500/30 bg-yellow-500/10';
    return 'text-orange-400 border-orange-500/30 bg-orange-500/10';
  };

  const formatPath = (path: string) => {
    const parts = path.split('.');
    return {
      namespace: parts.slice(0, -1).join('.'),
      container: parts[parts.length - 1]
    };
  };

  return (
    <div className="rounded-xl border border-purple-500/20 bg-slate-950/40 p-6">
      <div className="flex items-center gap-2 mb-4">
        <span className="text-lg">🔗</span>
        <h4 className="text-sm font-semibold text-purple-200">Evidence Trail</h4>
      </div>

      <p className="text-xs text-slate-400 mb-4">
        ReDNA containers used to generate this response
      </p>

      <div className="space-y-2">
        {containers.map((container, idx) => {
          const { namespace, container: name } = formatPath(container.path);
          const isExpanded = expandedContainer === container.path;

          return (
            <div
              key={`${container.path}-${idx}`}
              className="rounded-lg border border-purple-500/20 bg-slate-900/50 overflow-hidden"
            >
              <button
                onClick={() => {
                  setExpandedContainer(isExpanded ? null : container.path);
                  if (onContainerClick && !isExpanded) {
                    onContainerClick(container.path);
                  }
                }}
                className="w-full px-4 py-3 flex items-center gap-3 hover:bg-purple-500/5 transition-colors"
              >
                {/* Similarity Badge */}
                <div className={`px-2 py-1 rounded text-xs font-medium border ${getSimilarityColor(container.similarity)}`}>
                  {Math.round(container.similarity * 100)}%
                </div>

                {/* Container Info */}
                <div className="flex-1 text-left min-w-0">
                  <div className="text-sm font-medium text-slate-200 truncate">{name}</div>
                  <div className="text-xs text-slate-500 truncate">{namespace}</div>
                </div>

                {/* RR Value */}
                <div className="flex items-center gap-2">
                  <div className="w-16 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-purple-500 to-purple-400"
                      style={{ width: `${container.rr}%` }}
                    />
                  </div>
                  <span className="text-xs font-medium text-purple-400 w-6">{container.rr}</span>
                </div>

                {/* Expand Icon */}
                <svg
                  className={`w-4 h-4 text-slate-400 transition-transform flex-shrink-0 ${isExpanded ? 'rotate-180' : ''}`}
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>

              {/* Expanded Details */}
              {isExpanded && (
                <div className="px-4 py-3 border-t border-purple-500/20 bg-slate-950/60">
                  <div className="space-y-2">
                    <div>
                      <div className="text-xs text-slate-500 mb-1">Full Path</div>
                      <code className="text-xs text-purple-300 font-mono">{container.path}</code>
                    </div>
                    <div className="grid grid-cols-2 gap-3 pt-2">
                      <div>
                        <div className="text-xs text-slate-500 mb-1">Relevance</div>
                        <div className="text-sm font-medium text-slate-300">
                          {(container.similarity * 100).toFixed(1)}% match
                        </div>
                      </div>
                      <div>
                        <div className="text-xs text-slate-500 mb-1">Current RR</div>
                        <div className="text-sm font-medium text-slate-300">
                          {container.rr} / 100
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Legend */}
      <div className="mt-4 pt-4 border-t border-purple-500/10">
        <div className="text-xs text-slate-500">
          <span className="text-green-400">High</span> (80%+) •{' '}
          <span className="text-yellow-400">Medium</span> (60-80%) •{' '}
          <span className="text-orange-400">Low</span> (&lt;60%) relevance
        </div>
      </div>
    </div>
  );
}
