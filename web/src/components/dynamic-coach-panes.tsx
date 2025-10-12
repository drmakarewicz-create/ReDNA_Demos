'use client';

import { useState, useEffect, useRef } from 'react';
import type { CoachPane } from '../lib/api';

export interface DynamicCoachPanesProps {
  coachId: string;
  panes: CoachPane[];
  featureState: Record<string, any>;
  onChange: (partial: Record<string, any>) => void;
  onWarning?: (message: string) => void;
}

/**
 * Renders coach-specific feature panes dynamically based on configuration.
 * Supports: slider, switch, text, select, meter
 * State management with debounced saves.
 */
export function DynamicCoachPanes({ coachId, panes, featureState, onChange, onWarning }: DynamicCoachPanesProps) {
  // Track local state for each pane (optimistic updates)
  const [values, setValues] = useState<Record<string, any>>(featureState);
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);
  const pendingChangesRef = useRef<Record<string, any>>({});

  // Sync with external state changes
  useEffect(() => {
    setValues(featureState);
  }, [featureState]);

  const handleChange = (path: string, value: any) => {
    // Optimistic update
    setValues(prev => ({ ...prev, [path]: value }));

    // Accumulate pending changes
    pendingChangesRef.current[path] = value;

    // Debounce save (400ms)
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    debounceTimerRef.current = setTimeout(() => {
      const partial = { ...pendingChangesRef.current };
      pendingChangesRef.current = {};
      onChange(partial);
    }, 400);
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, []);

  if (panes.length === 0) {
    return (
      <div className="text-sm text-slate-400 italic">
        No features configured for this coach
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {panes.map((pane, idx) => (
        <div
          key={idx}
          className="rounded-lg border border-slate-700 bg-slate-900/50 p-4"
        >
          <div className="mb-3 font-medium text-slate-200">{pane.title}</div>

          {pane.type === 'switch' && (
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={Boolean(values[pane.path])}
                onChange={(e) => handleChange(pane.path, e.target.checked)}
                className="w-5 h-5 rounded border-slate-600 bg-slate-800 text-blue-500 focus:ring-2 focus:ring-blue-500"
              />
              <span className="text-sm text-slate-400">
                {values[pane.path] ? 'Enabled' : 'Disabled'}
              </span>
            </label>
          )}

          {pane.type === 'slider' && (
            <div className="space-y-2">
              <input
                type="range"
                min={pane.min ?? 0}
                max={pane.max ?? 100}
                step={pane.step ?? 1}
                value={values[pane.path] ?? pane.min ?? 0}
                onChange={(e) => handleChange(pane.path, Number(e.target.value))}
                className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
              />
              <div className="flex justify-between text-xs text-slate-400">
                <span>{pane.min ?? 0}</span>
                <span className="font-mono text-blue-400">
                  {values[pane.path] ?? pane.min ?? 0}
                </span>
                <span>{pane.max ?? 100}</span>
              </div>
            </div>
          )}

          {pane.type === 'text' && (
            <input
              type="text"
              value={values[pane.path] ?? ''}
              onChange={(e) => handleChange(pane.path, e.target.value)}
              placeholder={pane.placeholder ?? 'Enter text...'}
              className="w-full px-3 py-2 rounded-md border border-slate-600 bg-slate-800 text-slate-200 placeholder:text-slate-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          )}

          {pane.type === 'select' && pane.options && (
            <select
              value={values[pane.path] ?? pane.options[0]}
              onChange={(e) => handleChange(pane.path, e.target.value)}
              className="w-full px-3 py-2 rounded-md border border-slate-600 bg-slate-800 text-slate-200 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              {pane.options.map((option: any, optIdx: number) => (
                <option key={optIdx} value={option.value ?? option}>
                  {option.label ?? option}
                </option>
              ))}
            </select>
          )}

          {pane.type === 'meter' && (
            <div className="space-y-2">
              <div className="w-full h-3 bg-slate-700 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-blue-500 to-cyan-400 transition-all duration-300"
                  style={{
                    width: `${((values[pane.path] ?? 0) / (pane.max ?? 100)) * 100}%`
                  }}
                />
              </div>
              <div className="flex justify-between text-xs text-slate-400">
                <span>{pane.min ?? 0}</span>
                <span className="font-mono text-cyan-400">
                  {values[pane.path] ?? 0} / {pane.max ?? 100}
                </span>
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
