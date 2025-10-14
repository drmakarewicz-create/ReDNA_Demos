import { useState, useEffect, useRef } from 'react';

export interface CoachPane {
  title: string;
  type: 'slider' | 'switch' | 'text' | 'select' | 'meter';
  path: string;
  min?: number;
  max?: number;
  step?: number;
  options?: string[];
  placeholder?: string;
}

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
export default function DynamicCoachPanes({ panes, featureState, onChange }: DynamicCoachPanesProps) {
  // Track local state for each pane (optimistic updates)
  const [values, setValues] = useState<Record<string, any>>(featureState);
  const debounceTimerRef = useRef<number | null>(null);
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

    debounceTimerRef.current = window.setTimeout(() => {
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
      <div className="text-sm text-gray-400 italic">
        No features configured for this coach
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {panes.map((pane, idx) => (
        <div
          key={idx}
          className="rounded-lg border border-gray-300 bg-white p-4"
        >
          <div className="mb-3 font-medium text-gray-900">{pane.title}</div>

          {pane.type === 'switch' && (
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={Boolean(values[pane.path])}
                onChange={(e) => handleChange(pane.path, e.target.checked)}
                className="w-5 h-5 rounded border-gray-400 bg-white text-blue-600 focus:ring-2 focus:ring-blue-500"
              />
              <span className="text-sm text-gray-600">
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
                className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
              />
              <div className="flex justify-between text-xs text-gray-500">
                <span>{pane.min ?? 0}</span>
                <span className="font-mono text-blue-600 font-medium">
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
              className="w-full px-3 py-2 rounded-md border border-gray-300 bg-white text-gray-900 placeholder:text-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          )}

          {pane.type === 'select' && pane.options && (
            <select
              value={values[pane.path] ?? pane.options[0]}
              onChange={(e) => handleChange(pane.path, e.target.value)}
              className="w-full px-3 py-2 rounded-md border border-gray-300 bg-white text-gray-900 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              {pane.options.map((option, optIdx) => (
                <option key={optIdx} value={option}>
                  {option}
                </option>
              ))}
            </select>
          )}

          {pane.type === 'meter' && (
            <div className="space-y-2">
              <div className="w-full h-3 bg-gray-200 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-blue-500 to-cyan-400 transition-all duration-300"
                  style={{
                    width: `${((values[pane.path] ?? 0) / (pane.max ?? 100)) * 100}%`
                  }}
                />
              </div>
              <div className="flex justify-between text-xs text-gray-500">
                <span>{pane.min ?? 0}</span>
                <span className="font-mono text-cyan-600 font-medium">
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
