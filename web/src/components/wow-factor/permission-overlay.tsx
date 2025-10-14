'use client';

import { useState, useEffect } from 'react';
import { CORE_API_BASE } from '../../lib/api';

interface PermissionAccess {
  ts: string;
  namespace: string;
  reason: string;
  consent_status: 'granted' | 'pending' | 'denied';
  data_accessed: string[];
}

interface PermissionOverlayProps {
  userId: string;
  showOverlay?: boolean;
  onToggle?: (show: boolean) => void;
}

const PERMISSION_COLORS = {
  granted: {
    bg: 'bg-green-950/20',
    border: 'border-green-800/30',
    text: 'text-green-400',
    badge: '🟢',
  },
  pending: {
    bg: 'bg-yellow-950/20',
    border: 'border-yellow-800/30',
    text: 'text-yellow-400',
    badge: '🟡',
  },
  denied: {
    bg: 'bg-red-950/20',
    border: 'border-red-800/30',
    text: 'text-red-400',
    badge: '🔴',
  },
};

export function PermissionOverlay({
  userId,
  showOverlay = true,
  onToggle,
}: PermissionOverlayProps) {
  const [accesses, setAccesses] = useState<PermissionAccess[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);

  const fetchPermissionAccesses = async () => {
    try {
      // Using governance API to get consent timeline
      const response = await fetch(
        `${CORE_API_BASE}/api/governance/${userId}/consent/timeline`
      );
      const json = await response.json();

      if (json.ok && json.timeline) {
        // Transform to permission access format
        const transformed: PermissionAccess[] = json.timeline.map((entry: any) => ({
          ts: entry.ts,
          namespace: entry.namespace || 'Unknown',
          reason: entry.reason || 'Access required',
          consent_status: entry.status || 'granted',
          data_accessed: entry.accessed_data || [],
        }));
        setAccesses(transformed);
        setError(null);
      } else {
        setError(json.detail || 'Failed to load permission data');
      }
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (showOverlay) {
      fetchPermissionAccesses();
    }
  }, [userId, showOverlay]);

  if (!showOverlay) return null;

  if (loading) {
    return (
      <div className="fixed right-4 top-4 z-50 w-80 rounded-2xl border border-slate-800 bg-slate-900/95 p-4 shadow-xl backdrop-blur">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-semibold text-slate-200">
            Permission Transparency
          </h3>
          <button
            onClick={() => onToggle?.(false)}
            className="text-slate-400 hover:text-slate-300"
          >
            ✕
          </button>
        </div>
        <div className="text-xs text-slate-500">Loading permission data...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="fixed right-4 top-4 z-50 w-80 rounded-2xl border border-red-800/30 bg-red-950/95 p-4 shadow-xl backdrop-blur">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-semibold text-red-400">
            Permission Transparency
          </h3>
          <button
            onClick={() => onToggle?.(false)}
            className="text-red-400 hover:text-red-300"
          >
            ✕
          </button>
        </div>
        <div className="text-xs text-red-300">{error}</div>
      </div>
    );
  }

  // Get summary stats
  const granted = accesses.filter((a) => a.consent_status === 'granted').length;
  const pending = accesses.filter((a) => a.consent_status === 'pending').length;
  const denied = accesses.filter((a) => a.consent_status === 'denied').length;

  return (
    <div className="fixed right-4 top-4 z-50 w-96 rounded-2xl border border-slate-800 bg-slate-900/95 p-4 shadow-xl backdrop-blur">
      {/* Header */}
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-200">
          🔒 Permission Transparency
        </h3>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-xs text-slate-400 hover:text-slate-300"
          >
            {expanded ? 'Collapse' : 'Expand'}
          </button>
          <button
            onClick={() => onToggle?.(false)}
            className="text-slate-400 hover:text-slate-300"
          >
            ✕
          </button>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="mb-3 grid grid-cols-3 gap-2 text-center">
        <div className="rounded-lg bg-green-950/20 p-2">
          <div className="text-lg font-bold text-green-400">{granted}</div>
          <div className="text-xs text-slate-400">Granted</div>
        </div>
        <div className="rounded-lg bg-yellow-950/20 p-2">
          <div className="text-lg font-bold text-yellow-400">{pending}</div>
          <div className="text-xs text-slate-400">Pending</div>
        </div>
        <div className="rounded-lg bg-red-950/20 p-2">
          <div className="text-lg font-bold text-red-400">{denied}</div>
          <div className="text-xs text-slate-400">Denied</div>
        </div>
      </div>

      {/* Access Log */}
      {expanded && accesses.length > 0 && (
        <div className="max-h-96 space-y-2 overflow-y-auto">
          <div className="text-xs font-medium text-slate-400">Recent Accesses</div>
          {accesses.slice(-10).reverse().map((access, idx) => {
            const config = PERMISSION_COLORS[access.consent_status];
            const timestamp = new Date(access.ts);

            return (
              <div
                key={idx}
                className={`rounded-lg border ${config.border} ${config.bg} p-3`}
              >
                <div className="mb-1 flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <span>{config.badge}</span>
                    <span className={`text-xs font-semibold ${config.text}`}>
                      {access.namespace}
                    </span>
                  </div>
                  <div className="text-xs text-slate-500">
                    {timestamp.toLocaleTimeString([], {
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </div>
                </div>

                <div className="mb-2 text-xs text-slate-400">{access.reason}</div>

                {access.data_accessed.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {access.data_accessed.slice(0, 3).map((data, dataIdx) => (
                      <div
                        key={dataIdx}
                        className="rounded bg-slate-800/50 px-1.5 py-0.5 font-mono text-xs text-slate-400"
                      >
                        {data}
                      </div>
                    ))}
                    {access.data_accessed.length > 3 && (
                      <div className="rounded bg-slate-800/50 px-1.5 py-0.5 text-xs text-slate-500">
                        +{access.data_accessed.length - 3}
                      </div>
                    )}
                  </div>
                )}

                <div className="mt-2 flex items-center gap-2">
                  {access.consent_status === 'pending' && (
                    <>
                      <button className="flex-1 rounded bg-green-900/50 px-2 py-1 text-xs font-medium text-green-300 hover:bg-green-800/50">
                        Grant
                      </button>
                      <button className="flex-1 rounded bg-red-900/50 px-2 py-1 text-xs font-medium text-red-300 hover:bg-red-800/50">
                        Deny
                      </button>
                    </>
                  )}
                  {access.consent_status === 'granted' && (
                    <div className="w-full text-center text-xs text-green-400">
                      ✓ Access Granted
                    </div>
                  )}
                  {access.consent_status === 'denied' && (
                    <div className="w-full text-center text-xs text-red-400">
                      ✗ Access Denied
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Empty State */}
      {expanded && accesses.length === 0 && (
        <div className="rounded-lg bg-slate-800/30 p-4 text-center text-xs text-slate-500">
          No permission accesses recorded yet
        </div>
      )}

      {/* Footer */}
      <div className="mt-3 text-center text-xs text-slate-500">
        All sensitive data access is logged and auditable
      </div>
    </div>
  );
}
