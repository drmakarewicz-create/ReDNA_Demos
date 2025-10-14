'use client';

import { useCallback, useEffect, useState } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_CORE_API_BASE ?? 'http://127.0.0.1:8015';

interface Coach {
  id: string;
  display_name: string;
  description: string;
  icon: string;
  primary_namespaces: string[];
  capabilities: string[];
  natural_domains: string[];
  delegation_context: string;
  autonomy_level: string;
  is_default: boolean;
  available: boolean;
}

interface CoachCatalogModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectCoach: (coachId: string) => void;
  currentCoach?: string;
}

export function CoachCatalogModal({
  isOpen,
  onClose,
  currentCoach,
  onSelectCoach
}: CoachCatalogModalProps) {
  const [coaches, setCoaches] = useState<Coach[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    if (isOpen) {
      loadCoachCatalog();
    }
  }, [isOpen]);

  const loadCoachCatalog = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE}/ui/coach-catalog`);
      if (!response.ok) {
        throw new Error(`Failed to load coach catalog: ${response.statusText}`);
      }

      const data = await response.json();
      if (data.error) {
        throw new Error(data.error);
      }

      setCoaches(data.coaches || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load coaches');
    } finally {
      setLoading(false);
    }
  };

  const handleSelectCoach = useCallback((coachId: string) => {
    onSelectCoach(coachId);
    onClose();
  }, [onSelectCoach, onClose]);

  const filteredCoaches = coaches.filter(coach => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return (
      coach.display_name.toLowerCase().includes(query) ||
      coach.description.toLowerCase().includes(query) ||
      coach.natural_domains.some(domain => domain.toLowerCase().includes(query))
    );
  });

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="relative w-full max-w-4xl max-h-[90vh] m-4 rounded-2xl border border-slate-700 bg-slate-900 shadow-2xl overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-800 bg-gradient-to-r from-cyan-950/40 to-slate-950/60 p-6">
          <div>
            <h2 className="text-2xl font-bold text-slate-100">Coach Catalog</h2>
            <p className="text-sm text-slate-400 mt-1">
              Browse all available coaches and their specializations
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-full p-2 text-slate-400 hover:bg-slate-800 hover:text-slate-200 transition"
            aria-label="Close catalog"
          >
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Search */}
        <div className="p-4 border-b border-slate-800">
          <input
            type="text"
            placeholder="Search coaches by name, description, or domain..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full rounded-lg border border-slate-700 bg-slate-950/70 px-4 py-2 text-slate-200 placeholder-slate-500 focus:border-cyan-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/20"
          />
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {loading && (
            <div className="flex items-center justify-center py-12">
              <div className="text-slate-400">Loading coaches...</div>
            </div>
          )}

          {error && (
            <div className="rounded-lg border border-red-500/30 bg-red-950/20 p-4">
              <p className="text-sm text-red-300">⚠️ {error}</p>
            </div>
          )}

          {!loading && !error && filteredCoaches.length === 0 && (
            <div className="text-center py-12 text-slate-400">
              No coaches found matching your search.
            </div>
          )}

          {!loading && !error && filteredCoaches.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {filteredCoaches.map((coach) => (
                <CoachCard
                  key={coach.id}
                  coach={coach}
                  isActive={coach.id === currentCoach}
                  onSelect={() => handleSelectCoach(coach.id)}
                />
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-slate-800 bg-slate-950/60 p-4">
          <p className="text-xs text-slate-500 text-center">
            💡 Tip: Click any coach to switch to their specialized interface
          </p>
        </div>
      </div>
    </div>
  );
}

interface CoachCardProps {
  coach: Coach;
  isActive: boolean;
  onSelect: () => void;
}

function CoachCard({ coach, isActive, onSelect }: CoachCardProps) {
  const getAutonomyColor = (level: string) => {
    switch (level) {
      case 'high':
      case 'medium-high':
        return 'text-emerald-400 bg-emerald-500/10';
      case 'medium':
        return 'text-blue-400 bg-blue-500/10';
      case 'low':
        return 'text-amber-400 bg-amber-500/10';
      default:
        return 'text-slate-400 bg-slate-500/10';
    }
  };

  return (
    <button
      onClick={onSelect}
      disabled={!coach.available}
      className={`
        relative rounded-xl border p-5 text-left transition-all duration-200
        ${isActive
          ? 'border-cyan-400 bg-cyan-400/10 ring-2 ring-cyan-400/20'
          : 'border-slate-700 bg-slate-950/40 hover:border-slate-600 hover:bg-slate-950/60'
        }
        ${!coach.available ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
      `}
    >
      {/* Icon and Title */}
      <div className="flex items-start gap-3 mb-3">
        <span className="text-3xl" aria-hidden>{coach.icon}</span>
        <div className="flex-1">
          <h3 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
            {coach.display_name}
            {isActive && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-cyan-500/20 text-cyan-300">
                Active
              </span>
            )}
            {coach.is_default && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300">
                Default
              </span>
            )}
          </h3>
          <p className="text-xs text-slate-400 mt-1">{coach.delegation_context}</p>
        </div>
      </div>

      {/* Description */}
      <p className="text-sm text-slate-300 mb-3 line-clamp-2">
        {coach.description}
      </p>

      {/* Domains */}
      {coach.natural_domains.length > 0 && (
        <div className="mb-3">
          <div className="flex flex-wrap gap-1.5">
            {coach.natural_domains.slice(0, 4).map((domain) => (
              <span
                key={domain}
                className="text-xs px-2 py-1 rounded-md bg-slate-800/60 text-slate-300"
              >
                {domain}
              </span>
            ))}
            {coach.natural_domains.length > 4 && (
              <span className="text-xs px-2 py-1 rounded-md bg-slate-800/60 text-slate-400">
                +{coach.natural_domains.length - 4} more
              </span>
            )}
          </div>
        </div>
      )}

      {/* Autonomy Level */}
      <div className="flex items-center gap-2 text-xs">
        <span className="text-slate-500">Autonomy:</span>
        <span className={`px-2 py-0.5 rounded ${getAutonomyColor(coach.autonomy_level)}`}>
          {coach.autonomy_level}
        </span>
      </div>

      {!coach.available && (
        <div className="absolute inset-0 flex items-center justify-center rounded-xl bg-slate-950/80">
          <span className="text-sm font-medium text-slate-400">Unavailable</span>
        </div>
      )}
    </button>
  );
}
