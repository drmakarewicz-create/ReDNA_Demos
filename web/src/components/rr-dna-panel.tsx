'use client';

import { useState, useMemo } from 'react';
import { useI18n } from '../i18n/context';
import type { UnabridgedSnapshot, UnabridgedTrait } from '../lib/api';
import { formatPercent } from '@/lib/provenanceClient';

interface RRDnaPanelProps {
  snapshot: UnabridgedSnapshot | null;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
}

interface DnaContainer {
  name: string;
  icon: string;
  traits: UnabridgedTrait[];
  avgRR: number;
  avgUCN: number;
  avgCuriosity: number;
  sensitive: boolean;
}

const DNA_CONTAINERS = [
  // NORTHSTAR: BasicDNA container for onboarding traits
  { key: 'BasicDNA', name: 'Basic Info', icon: '🪪', sensitive: false },
  { key: 'Identity', name: 'Identity', icon: '🪪', sensitive: false },
  { key: 'PaDNA', name: 'Physical Appearance', icon: '👤', sensitive: false },
  { key: 'Writing', name: 'Communication Style', icon: '✍️', sensitive: false },
  // NORTHSTAR: PersonalityDNA (used by Core) + Personality (legacy)
  { key: 'PersonalityDNA', name: 'Personality', icon: '🎭', sensitive: false },
  { key: 'Personality', name: 'Personality', icon: '🎭', sensitive: false },
  { key: 'Emotion', name: 'Emotion & Affect', icon: '💭', sensitive: false },
  { key: 'Social', name: 'Social', icon: '👥', sensitive: false },
  { key: 'Family', name: 'Family & Relationships', icon: '👪', sensitive: true },
  { key: 'Cognitive', name: 'Cognitive Style', icon: '🧠', sensitive: false },
  { key: 'Work', name: 'Work & Professional', icon: '💼', sensitive: false },
  { key: 'Taste', name: 'Taste & Entertainment', icon: '🎬', sensitive: false },
  { key: 'Gaming', name: 'Gaming', icon: '🎮', sensitive: false },
  { key: 'Health', name: 'Health', icon: '🏥', sensitive: true },
  { key: 'Finance', name: 'Finance', icon: '💰', sensitive: true },
  { key: 'Routine', name: 'Routine & Lifestyle', icon: '📅', sensitive: false },
  { key: 'Learning', name: 'Learning', icon: '📚', sensitive: false },
  { key: 'Behavior', name: 'Behavior', icon: '⚡', sensitive: false },
  { key: 'Values', name: 'Values & Beliefs', icon: '⭐', sensitive: true },
  { key: 'Digital', name: 'Digital & Technology', icon: '💻', sensitive: false },
  { key: 'Cultural', name: 'Cultural & Civic', icon: '🌍', sensitive: true },
  { key: 'Environmental', name: 'Environmental', icon: '🌱', sensitive: false },
  { key: 'Motivations', name: 'Motivations & Goals', icon: '🎯', sensitive: false },
  { key: 'Safety', name: 'Safety & Risk', icon: '🛡️', sensitive: false },
];

function getRRBand(rr: number): { label: string; color: string } {
  if (rr >= 98) return { label: 'Elite', color: 'text-purple-400' };
  if (rr >= 90) return { label: 'Exceptional', color: 'text-violet-400' };
  if (rr >= 75) return { label: 'Well-Refined', color: 'text-blue-400' };
  if (rr >= 50) return { label: 'Developing', color: 'text-cyan-400' };
  if (rr >= 25) return { label: 'Emerging', color: 'text-teal-400' };
  return { label: 'Early', color: 'text-slate-400' };
}

export function RRDnaPanel({ snapshot, loading, error, onRetry }: RRDnaPanelProps) {
  const { t } = useI18n();
  const [expandedContainer, setExpandedContainer] = useState<string | null>(null);

  const dnaContainers = useMemo(() => {
    if (!snapshot || !snapshot.traits || snapshot.traits.length === 0) return [];

    const containers: DnaContainer[] = [];
    const traits = snapshot.traits;

    for (const config of DNA_CONTAINERS) {
      // Find all traits that belong to this container
      const containerTraits = traits.filter((trait) => {
        const path = trait.trait_id || '';
        return path.startsWith(config.key);
      });

      if (containerTraits.length === 0) continue;

      // Calculate averages
      const rrScores = containerTraits.map((t) => t.rr).filter((r): r is number => typeof r === 'number');
      const ucnScores = containerTraits.map((t) => t.ucn).filter((u): u is number => typeof u === 'number');
      const curiosityScores = containerTraits
        .map((t) => t.curiosity)
        .filter((c): c is number => typeof c === 'number');

      const avgRR = rrScores.length > 0 ? rrScores.reduce((a, b) => a + b, 0) / rrScores.length : 0;
      const avgUCN = ucnScores.length > 0 ? ucnScores.reduce((a, b) => a + b, 0) / ucnScores.length : 0;
      const avgCuriosity =
        curiosityScores.length > 0 ? curiosityScores.reduce((a, b) => a + b, 0) / curiosityScores.length : 0;

      containers.push({
        name: config.name,
        icon: config.icon,
        traits: containerTraits,
        avgRR: Math.round(avgRR * 100) / 100,
        avgUCN: Math.round(avgUCN),
        avgCuriosity: Math.round(avgCuriosity * 100) / 100,
        sensitive: config.sensitive,
      });
    }

    // Sort by RR (highest first)
    return containers.sort((a, b) => b.avgRR - a.avgRR);
  }, [snapshot]);

  const overallRR = useMemo(() => {
    if (!snapshot || !snapshot.traits || snapshot.traits.length === 0) return null;
    const rrScores = snapshot.traits.map((t) => t.rr).filter((r): r is number => typeof r === 'number');
    if (rrScores.length === 0) return null;
    return Math.round((rrScores.reduce((a, b) => a + b, 0) / rrScores.length) * 100) / 100;
  }, [snapshot]);
  const overallBand = overallRR !== null ? getRRBand(overallRR) : null;

  if (error) {
    return (
      <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6">
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-400">RR by DNA</h2>
        <div className="text-center text-sm text-red-400">{error}</div>
        {onRetry && (
          <button
            onClick={onRetry}
            className="mt-4 rounded-lg border border-red-700 px-4 py-2 text-sm text-red-300 hover:bg-red-950/40"
          >
            Retry
          </button>
        )}
      </div>
    );
  }

  if (loading) {
    return (
      <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6">
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-400">RR by DNA</h2>
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-16 animate-pulse rounded-lg bg-slate-800/50" />
          ))}
        </div>
      </div>
    );
  }

  if (!snapshot || dnaContainers.length === 0) {
    return (
      <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6">
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-400">RR by DNA</h2>
        <p className="text-sm text-slate-500">No DNA containers found</p>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 shadow-xl">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">RR by DNA</h2>
        {overallRR !== null && (
          <div className="text-sm">
            <span className="text-slate-500">Overall: </span>
            {overallBand && (
              <span className={`font-semibold ${overallBand.color}`}>
                {formatPercent(overallRR)} ({overallBand.label})
              </span>
            )}
          </div>
        )}
      </div>

      <div className="space-y-2">
        {dnaContainers.map((container) => {
          const isExpanded = expandedContainer === container.name;
          const band = getRRBand(container.avgRR);

          return (
            <div key={container.name} className="rounded-lg border border-slate-800 bg-slate-950/60">
              <button
                onClick={() => setExpandedContainer(isExpanded ? null : container.name)}
                className="flex w-full items-center justify-between p-3 text-left transition hover:bg-slate-800/40"
              >
                <div className="flex items-center gap-3">
                  <span className="text-xl" aria-hidden>
                    {container.icon}
                  </span>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-slate-200">{container.name}</span>
                      {container.sensitive && (
                        <span className="rounded bg-orange-950/40 px-1.5 py-0.5 text-[10px] font-semibold text-orange-400">
                          SENSITIVE
                        </span>
                      )}
                    </div>
                    <div className="mt-0.5 text-xs text-slate-500">{container.traits.length} traits</div>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <div className="text-right">
                    <div className={`text-sm font-semibold ${band.color}`}>{container.avgRR.toFixed(1)}</div>
                    <div className="text-[10px] text-slate-500">{band.label}</div>
                  </div>
                  <svg
                    className={`h-5 w-5 text-slate-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </div>
              </button>

              {isExpanded && (
                <div className="border-t border-slate-800 p-3">
                  <div className="mb-3 grid grid-cols-3 gap-2 text-center text-xs">
                    <div>
                      <div className="text-slate-500">Avg RR</div>
                      <div className={`font-semibold ${band.color}`}>{container.avgRR.toFixed(1)}</div>
                    </div>
                    <div>
                      <div className="text-slate-500">Avg UCN</div>
                      <div className="font-semibold text-cyan-400">{container.avgUCN}</div>
                    </div>
                    <div>
                      <div className="text-slate-500">Curiosity</div>
                      <div className="font-semibold text-violet-400">{(container.avgCuriosity * 100).toFixed(0)}%</div>
                    </div>
                  </div>

                  <div className="space-y-1">
                    {container.traits
                      .sort((a, b) => (b.rr ?? 0) - (a.rr ?? 0))
                      .slice(0, 10)
                      .map((trait) => {
                        const traitBand = getRRBand(trait.rr ?? 0);
                        return (
                          <div
                            key={trait.trait_id}
                            className="flex items-center justify-between rounded border border-slate-800/50 bg-slate-900/40 px-2 py-1.5 text-xs"
                          >
                            <span className="truncate text-slate-300">{trait.trait_id}</span>
                            <span className={`ml-2 font-medium ${traitBand.color}`}>
                              {trait.rr?.toFixed(1) ?? '—'}
                            </span>
                          </div>
                        );
                      })}
                    {container.traits.length > 10 && (
                      <div className="pt-1 text-center text-[10px] text-slate-500">
                        ...and {container.traits.length - 10} more
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
