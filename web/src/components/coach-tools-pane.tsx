'use client';

import type { ReactNode } from 'react';

/**
 * CoachToolsPane - Right-Side Tools/Features Pane
 *
 * This component provides an independent scrolling area for:
 * - Persona-specific tools (photo upload, rendering, etc.)
 * - Support panels (ObservationSummary, CoachAsks, NudgeInbox, etc.)
 * - Any additional features that don't fit in the chat flow
 *
 * CRITICAL: This pane scrolls independently and cannot affect the left chat pane.
 *
 * RULES:
 * - ONE scroll container only (this component)
 * - NO position:fixed inside this pane
 * - Use position:sticky for sub-headers if needed
 * - DO NOT modify --composer-h (scoped to left pane)
 * - Avoid nested scroll containers
 */

export interface CoachToolsPaneProps {
  /** Tool/feature components to display */
  children: ReactNode;

  /** Optional title for the tools pane */
  title?: string;
}

export function CoachToolsPane({ children, title }: CoachToolsPaneProps) {
  return (
    <div
      className="h-full overflow-auto overscroll-contain [scrollbar-gutter:stable_both-edges]"
      data-tools-pane="coach-features"
    >
      {/* ReDNA Logo Header */}
      <header className="sticky top-0 z-10 bg-hc-background/95 backdrop-blur border-b border-slate-800 px-4 py-3 mb-4">
        <div className="flex items-center gap-3 mb-2">
          <svg className="h-8 w-8" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
            {/* DNA Double Helix */}
            <g className="opacity-90">
              {/* Left strand */}
              <path
                d="M10 5 Q 15 12, 10 20 Q 5 28, 10 35"
                stroke="url(#gradient1)"
                strokeWidth="2.5"
                fill="none"
                strokeLinecap="round"
              />
              {/* Right strand */}
              <path
                d="M30 5 Q 25 12, 30 20 Q 35 28, 30 35"
                stroke="url(#gradient2)"
                strokeWidth="2.5"
                fill="none"
                strokeLinecap="round"
              />
              {/* Cross connections (base pairs) */}
              <line x1="10" y1="8" x2="30" y2="8" stroke="cyan" strokeWidth="1.5" opacity="0.6" />
              <line x1="12" y1="14" x2="28" y2="14" stroke="violet" strokeWidth="1.5" opacity="0.6" />
              <line x1="10" y1="20" x2="30" y2="20" stroke="cyan" strokeWidth="1.5" opacity="0.6" />
              <line x1="12" y1="26" x2="28" y2="26" stroke="violet" strokeWidth="1.5" opacity="0.6" />
              <line x1="10" y1="32" x2="30" y2="32" stroke="cyan" strokeWidth="1.5" opacity="0.6" />
            </g>
            {/* Gradients */}
            <defs>
              <linearGradient id="gradient1" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" stopColor="#06b6d4" />
                <stop offset="100%" stopColor="#8b5cf6" />
              </linearGradient>
              <linearGradient id="gradient2" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" stopColor="#8b5cf6" />
                <stop offset="100%" stopColor="#06b6d4" />
              </linearGradient>
            </defs>
          </svg>
          <div>
            <h1 className="text-lg font-bold text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-violet-500">
              ReDNA
            </h1>
            <p className="text-[10px] text-slate-500 -mt-0.5">Refinement DNA</p>
          </div>
        </div>
        {title && (
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400 border-t border-slate-800/50 pt-2 mt-1">
            {title}
          </h2>
        )}
      </header>

      <div className="space-y-6 px-4 pb-6">{children}</div>
    </div>
  );
}
