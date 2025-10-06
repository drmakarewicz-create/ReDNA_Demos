'use client';

import { useEffect, useRef, type ReactNode } from 'react';

/**
 * HeadCoachChatPane - Black Box Chat Interface
 *
 * This component encapsulates the entire left-pane chat interface:
 * - Toolbar (fixed at top)
 * - TranscriptPanel (scrollable, fills space)
 * - Composer (fixed at bottom)
 *
 * CRITICAL: This component manages --composer-h scoped to itself only.
 * The right pane cannot affect this measurement.
 *
 * DO NOT:
 * - Add overflow-auto to this component or its wrapper
 * - Change height calculation from h-full
 * - Re-enable virtualization in focused mode
 * - Let external components modify --composer-h
 */

export interface HeadCoachChatPaneProps {
  /** Toolbar element (fixed at top) */
  toolbar: ReactNode;

  /** Transcript panel element (scrollable, fills space) */
  transcript: ReactNode;

  /** Composer element (fixed at bottom) */
  composer: ReactNode;

  /** Optional notices to show above content */
  notices?: ReactNode;
}

export function HeadCoachChatPane({
  toolbar,
  transcript,
  composer,
  notices,
}: HeadCoachChatPaneProps) {
  const paneRootRef = useRef<HTMLDivElement | null>(null);
  const composerHolderRef = useRef<HTMLDivElement | null>(null);

  // Measure composer height and set CSS variable SCOPED to this pane
  useEffect(() => {
    const root = paneRootRef.current;
    const composerHolder = composerHolderRef.current;
    if (!root || !composerHolder) return;

    const updateComposerHeight = () => {
      const height = composerHolder.offsetHeight;
      // CRITICAL: Set --composer-h on the pane root, NOT document/body
      root.style.setProperty('--composer-h', `${height}px`);
    };

    updateComposerHeight();

    const observer = new ResizeObserver(updateComposerHeight);
    observer.observe(composerHolder);

    return () => observer.disconnect();
  }, []);

  return (
    <div
      ref={paneRootRef}
      className="flex h-full flex-col"
      data-chat-pane="head-coach"
    >
      {/* Notices: fixed height if present */}
      {notices && <div className="shrink-0">{notices}</div>}

      {/* Toolbar: fixed height */}
      <div className="shrink-0">{toolbar}</div>

      {/* Transcript: fills remaining space, scrolls internally */}
      <div className="flex-1 min-h-0">{transcript}</div>

      {/* Composer: fixed at bottom */}
      <div ref={composerHolderRef} className="shrink-0 pt-4">
        {composer}
      </div>
    </div>
  );
}
