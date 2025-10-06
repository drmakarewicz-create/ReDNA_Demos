// web/src/components/curiosity-tooltip.tsx
'use client';

import { useState, useRef, useEffect } from 'react';

export interface CuriosityTooltipProps {
  isEnabled: boolean;
  isReachable: boolean | null;
  children: React.ReactNode;
}

export function CuriosityTooltip({ isEnabled, isReachable, children }: CuriosityTooltipProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [position, setPosition] = useState<'top' | 'bottom'>('bottom');
  const triggerRef = useRef<HTMLDivElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen || !triggerRef.current || !tooltipRef.current) return;

    const triggerRect = triggerRef.current.getBoundingClientRect();
    const tooltipRect = tooltipRef.current.getBoundingClientRect();
    const viewportHeight = window.innerHeight;

    // Check if tooltip would overflow bottom
    if (triggerRect.bottom + tooltipRect.height + 8 > viewportHeight) {
      setPosition('top');
    } else {
      setPosition('bottom');
    }
  }, [isOpen]);

  const getStatusText = () => {
    if (!isEnabled) {
      return {
        title: 'Curiosity: Disabled',
        description: 'The curiosity engine is turned off in Core configuration (CURIOSITY_ON=false). Enable it to see curiosity scores for traits.',
        color: 'text-slate-400',
      };
    }

    if (isReachable === null) {
      return {
        title: 'Curiosity: Checking...',
        description: 'Checking if the curiosity engine is reachable.',
        color: 'text-blue-400',
      };
    }

    if (isReachable) {
      return {
        title: 'Curiosity: Online',
        description: 'The curiosity engine is enabled and running. Curiosity scores show how important it is to gather more evidence for each trait.',
        color: 'text-green-400',
      };
    }

    return {
      title: 'Curiosity: Unreachable',
      description: 'The curiosity engine is enabled but currently unreachable. Check that Core is running and configured correctly.',
      color: 'text-amber-400',
    };
  };

  const status = getStatusText();

  return (
    <div
      ref={triggerRef}
      className="relative inline-block"
      onMouseEnter={() => setIsOpen(true)}
      onMouseLeave={() => setIsOpen(false)}
    >
      {children}

      {isOpen && (
        <div
          ref={tooltipRef}
          className={`absolute z-50 w-64 ${
            position === 'top' ? 'bottom-full mb-2' : 'top-full mt-2'
          } left-1/2 -translate-x-1/2`}
        >
          <div className="bg-slate-800 border border-slate-700 rounded-lg shadow-xl p-3">
            <div className="flex items-start gap-2">
              <div className="flex-shrink-0 mt-0.5">
                {!isEnabled ? (
                  <svg className="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
                  </svg>
                ) : isReachable === null ? (
                  <svg className="w-4 h-4 text-blue-400 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                ) : isReachable ? (
                  <svg className="w-4 h-4 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                ) : (
                  <svg className="w-4 h-4 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                )}
              </div>
              <div className="flex-1 min-w-0">
                <div className={`text-sm font-medium ${status.color} mb-1`}>
                  {status.title}
                </div>
                <p className="text-xs text-slate-400 leading-relaxed">
                  {status.description}
                </p>
              </div>
            </div>

            {/* Tooltip arrow */}
            <div
              className={`absolute left-1/2 -translate-x-1/2 w-2 h-2 bg-slate-800 border-slate-700 ${
                position === 'top'
                  ? 'bottom-[-4px] border-b border-r'
                  : 'top-[-4px] border-t border-l'
              } rotate-45`}
            />
          </div>
        </div>
      )}
    </div>
  );
}
