'use client';

import type { ReactNode, ReactElement } from 'react';
import React, { Children, cloneElement, isValidElement, useEffect, useRef } from 'react';
import { useFeatureFlags } from '../lib/feature-flags';

/**
 * Layout Switcher
 *
 * Switches between Classic Layout and Focused Chat Layout based on feature flag.
 *
 * - Classic Layout: Original scrolling page with fixed composer at viewport bottom
 * - Focused Chat Layout: Fixed-height chat window (like ChatGPT/Claude) with composer docked below transcript
 */

interface LayoutProps {
  header: ReactNode;
  centerContent: ReactNode;
  sidebar: ReactNode;
  composer: ReactNode;
  modals: ReactNode;
  notices: ReactNode;
}

export function LayoutSwitcher(props: LayoutProps) {
  const { flags } = useFeatureFlags();

  if (flags.focusedChatLayout) {
    return <FocusedChatLayout {...props} />;
  }

  return <ClassicLayout {...props} />;
}

/**
 * Classic Layout (Original)
 *
 * Full-page scrolling with fixed composer at viewport bottom.
 * Content has large bottom padding to prevent composer overlap.
 */
function ClassicLayout({ header, centerContent, sidebar, composer, modals, notices }: LayoutProps) {
  return (
    <div className="flex min-h-screen flex-col bg-hc-background" suppressHydrationWarning>
      {header}

      <main className="flex flex-1 justify-center">
        <div className="flex w-full max-w-6xl flex-1 flex-col px-4 pb-[calc(10rem+env(safe-area-inset-bottom,0px))] pt-4 sm:px-6 sm:pt-6">
          {notices}
          <div className="flex flex-col-reverse gap-6 lg:flex-row">
            <div className="flex-1 space-y-6">
              {centerContent}
            </div>
            <aside className="w-full shrink-0 space-y-6 lg:w-72">
              {sidebar}
            </aside>
          </div>
        </div>
      </main>

      {composer}
      {modals}
    </div>
  );
}

/**
 * Focused Chat Layout (ChatGPT-style with Two-Pane Support)
 *
 * CSS Grid layout with two independent columns:
 * - LEFT: Head Coach chat (black box, stable, isolated)
 * - RIGHT: Persona-specific tools (independent scroll)
 *
 * ⚠️ ⚠️ ⚠️ LEFT PANE SANCTITY RULE ⚠️ ⚠️ ⚠️
 *
 * DO NOT MODIFY THE LEFT PANE WITHOUT EXTREME CAUTION!
 *
 * The left chat pane is SACRED. It took 20+ iterations to stabilize.
 * ALL new features must go in the RIGHT pane unless absolutely necessary.
 *
 * Before touching the left pane:
 * 1. Read LEFT_PANE_SANCTITY_RULE.md
 * 2. Read FOCUSED_CHAT_LAYOUT_SOLUTION.md
 * 3. Read TWO_PANE_LAYOUT_IMPLEMENTATION.md
 * 4. Ask yourself: "Can this be done in the right pane instead?"
 * 5. If the answer is yes, DO IT IN THE RIGHT PANE.
 *
 * CRITICAL RULES:
 * - Left column: overflow-hidden (only transcript scrolls internally)
 * - Right column: overflow-auto (independent scroll)
 * - Grid, not flex (more stable for two-pane)
 * - Responsive: collapses to single column at <lg breakpoint
 *
 * See: LEFT_PANE_SANCTITY_RULE.md for full details
 */
function FocusedChatLayout({ header, centerContent, sidebar, composer, modals, notices }: LayoutProps) {
  // Clone composer with docked prop
  const dockedComposer = isValidElement(composer)
    ? cloneElement(composer as ReactElement<any>, { docked: true })
    : composer;

  return (
    <div className="flex h-dvh bg-hc-background overflow-hidden overscroll-none" suppressHydrationWarning>
      {/* Work area: 2-column grid (no global header) */}
      <main className="grid flex-1 min-h-0 overflow-hidden overscroll-none
                       grid-cols-1 lg:grid-cols-[minmax(400px,560px)_minmax(0,1fr)]
                       gap-x-4">

        {/* LEFT: Head Coach Chat Pane (black box) - FULL HEIGHT */}
        <section className="flex flex-col min-h-0 overflow-hidden pl-4 sm:pl-6">
          {/* Notices */}
          {notices && <div className="shrink-0 pt-4 pb-4">{notices}</div>}

          {/* Center content (HeadCoachChatPane with toolbar + transcript) */}
          <div className="flex-1 min-h-0 pt-4">
            {centerContent}
          </div>

          {/* Composer: fixed at bottom */}
          <div className="shrink-0 pt-4 pb-4">
            {dockedComposer}
          </div>
        </section>

        {/* RIGHT: Header + Feature/Tools Pane */}
        <aside className="flex flex-col min-h-0 overflow-hidden hidden lg:flex pr-4 sm:pr-6">
          {/* Header: fixed at top of right pane */}
          <div className="shrink-0">
            {header}
          </div>

          {/* Tools Pane: scrollable */}
          <div className="flex-1 min-h-0 overflow-auto overscroll-contain
                          [scrollbar-gutter:stable_both-edges] pt-4">
            {sidebar}
          </div>
        </aside>
      </main>

      {modals}
    </div>
  );
}
