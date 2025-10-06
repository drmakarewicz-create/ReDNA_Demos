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
      {title && (
        <header className="sticky top-0 z-10 bg-hc-background/95 backdrop-blur border-b border-slate-800 px-4 py-3 mb-4">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
            {title}
          </h2>
        </header>
      )}

      <div className="space-y-6 px-4 pb-6">{children}</div>
    </div>
  );
}
