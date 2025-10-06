'use client';

import type { PersonaRosterEntry } from '../lib/api';
import { useI18n } from '../i18n/context';

export const DEFAULT_CANONICAL_PERSONAS: PersonaRosterEntry[] = [
  { key: 'head_coach', label: 'Head Coach (Orchestrator)', icon: '🧭', enabled: true },
  { key: 'relationship_coach', label: 'Relationship Coach', icon: '💞', enabled: true },
  { key: 'padna', label: 'PaDNA Coach', icon: '🧬', enabled: true },
  { key: 'photo', label: 'Photo Coach', icon: '📸', enabled: true }
];

interface PersonaRailProps {
  personas: PersonaRosterEntry[];
  activePersona: string;
  onPersonaChange: (persona: string) => void;
  id?: string;
  className?: string;
}

export function PersonaRail({ personas, activePersona, onPersonaChange, id, className }: PersonaRailProps) {
  const fallback = personas.length ? personas : DEFAULT_CANONICAL_PERSONAS;
  const activeMeta = fallback.find((persona) => persona.key === activePersona) ?? fallback[0];
  const { t } = useI18n();

  const containerClassName = ['flex flex-col gap-4 rounded-2xl border border-slate-800 bg-slate-900/70 p-4 shadow-xl sm:p-5', className]
    .filter(Boolean)
    .join(' ');

  return (
    <div id={id} className={containerClassName}>
      <div>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">{t('personaRail.title')}</h2>
        <p className="mt-1 text-xs text-slate-500">{t('personaRail.subtitle')}</p>
      </div>
      <div
        className="flex gap-2 overflow-x-auto pb-1 md:flex-wrap md:overflow-visible"
        role="list"
        aria-label="Persona roster"
      >
        {fallback.map((persona) => (
          <button
            key={persona.key}
            type="button"
            role="listitem"
            className={`flex items-center gap-2 rounded-full border px-4 py-2 text-sm transition whitespace-nowrap ${
              activePersona === persona.key
                ? 'border-cyan-400 bg-cyan-400/10 text-cyan-200'
                : 'border-slate-800 bg-slate-900 text-slate-300 hover:border-slate-700'
            } ${persona.enabled ? '' : 'opacity-40'}`}
            onClick={() => persona.enabled && onPersonaChange(persona.key)}
            disabled={!persona.enabled}
            aria-pressed={activePersona === persona.key}
            aria-current={activePersona === persona.key ? 'true' : undefined}
            aria-label={`${persona.label}${persona.enabled ? '' : ' (disabled)'}`}
            data-testid={`persona-button-${persona.key}`}
          >
            <span className="text-lg" aria-hidden>
              {persona.icon}
            </span>
            <span>{persona.label}</span>
          </button>
        ))}
      </div>
      <div
        className="rounded-lg border border-slate-800 bg-slate-950/60 p-3 text-xs text-slate-400 sm:p-4"
        data-testid="persona-bubble"
      >
        <p className="font-semibold text-slate-200">{t('personaRail.activeBubble')}</p>
        <p data-testid="persona-bubble-label">
          {activeMeta?.icon} {activeMeta?.label ?? t('app.title')}
        </p>
      </div>
    </div>
  );
}
