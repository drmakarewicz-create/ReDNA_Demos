'use client';

import { useMemo, useState } from 'react';

import { addDemoPlannerAsk, actOnPlannerAsk, rescoreNow, revertLastRescore, type PlannerAsk } from '../../lib/api';
import { useI18n } from '../../i18n/context';
import { useEffect, useRef } from 'react';

export interface TraitChange {
  trait: string;
  old_rr: number;
  new_rr: number;
  delta: number;
}

interface HeadCoachToolbarProps {
  userId: string;
  asks: PlannerAsk[];
  loading?: boolean;
  onRefresh: () => void;
  onNotify: (message: string, tone?: 'success' | 'info' | 'warning' | 'error') => void;
  id?: string;
  getComposerText?: () => string;
  clearComposerText?: () => void;
  onRefreshPanels?: () => void;
  onTraitsChanged?: (changes: TraitChange[]) => void;
}

const SUGGESTIONS: Array<{ title: string; summary: string }> = [
  {
    title: 'Confirm next focus milestone',
    summary: 'Quick checkpoint to confirm the member is ready to move into milestone two.'
  },
  {
    title: 'Prep photo inspiration share',
    summary: 'Invite the member to gather two inspiration references before the next session.'
  },
  {
    title: 'Schedule PaDNA refinement touchpoint',
    summary: 'Offer a nudge to book the PaDNA follow-up call within the next week.'
  }
];

export function HeadCoachToolbar({ userId, asks, loading = false, onRefresh, onNotify, id, getComposerText, clearComposerText, onRefreshPanels, onTraitsChanged }: HeadCoachToolbarProps) {
  const [creating, setCreating] = useState(false);
  const [approving, setApproving] = useState(false);
  const [rescoring, setRescoring] = useState(false);
  const [undoing, setUndoing] = useState(false);
  const [showUndo, setShowUndo] = useState(false);
  const undoTimerRef = useRef<number | null>(null);
  const trimmedUser = userId.trim();
  const hasUser = Boolean(trimmedUser);
  const { t } = useI18n();

  const nextSuggestion = useMemo(() => {
    if (!hasUser) {
      return SUGGESTIONS[0];
    }
    const seed = trimmedUser.charCodeAt(0) + asks.length;
    return SUGGESTIONS[seed % SUGGESTIONS.length];
  }, [asks.length, hasUser, trimmedUser]);

  const primaryAsk = useMemo(() => asks.find((ask) => ask.status !== 'approved'), [asks]);
  const metadataTitle =
    primaryAsk?.metadata && typeof primaryAsk.metadata === 'object' && 'title' in primaryAsk.metadata
      ? String((primaryAsk.metadata as Record<string, unknown>).title)
      : null;
  const primaryLabel = primaryAsk?.phrasing_stub ?? metadataTitle ?? primaryAsk?.container ?? null;

  async function handleCreateDemoAsk() {
    if (!hasUser) {
      onNotify(t('toolbar.headCoach.noUserNotice'), 'warning');
      return;
    }
    setCreating(true);
    try {
      await addDemoPlannerAsk(trimmedUser, {
        title: nextSuggestion.title,
        summary: nextSuggestion.summary,
        persona: 'head_coach'
      });
      onNotify(t('toolbar.headCoach.generatedNotice'), 'success');
      onRefresh();
    } catch (error) {
      onNotify(error instanceof Error ? error.message : 'Failed to create demo ask.', 'error');
    } finally {
      setCreating(false);
    }
  }

  async function handleApproveAsk() {
    if (!hasUser || !primaryAsk) {
      onNotify(hasUser ? t('toolbar.headCoach.noPendingNotice') : t('toolbar.headCoach.noUserNotice'), 'info');
      return;
    }
    setApproving(true);
    try {
      await actOnPlannerAsk(trimmedUser, primaryAsk.id, 'approve');
      onNotify(t('toolbar.headCoach.approvedNotice'), 'success');
      onRefresh();
    } catch (error) {
      onNotify(error instanceof Error ? error.message : 'Failed to approve ask.', 'error');
    } finally {
      setApproving(false);
    }
  }

  async function handleRescoreNow() {
    if (!hasUser) {
      onNotify(t('toolbar.headCoach.noUserNotice'), 'warning');
      return;
    }
    const text = getComposerText?.() ?? '';
    if (!text.trim()) {
      onNotify('Please enter some text to rescore.', 'warning');
      return;
    }
    setRescoring(true);
    try {
      const result = await rescoreNow({
        userId: trimmedUser,
        text,
        persona: 'head_coach',
      });

      if (clearComposerText) {
        clearComposerText();
      }

      if (result.updated_traits.length === 0) {
        onNotify('Rescore complete. No significant changes detected.', 'info');
      } else {
        const topChanges = result.updated_traits.slice(0, 3);
        const summary = topChanges.map(t => {
          const traitName = t.trait.split('.').pop() ?? t.trait;
          const delta = Math.round(t.new_rr - t.old_rr);
          const sign = delta > 0 ? '+' : '';
          return `${traitName} (${sign}${delta})`;
        }).join(', ');
        onNotify(`Rescore complete! Updated ${result.updated_traits.length} traits: ${summary}`, 'success');

        // Notify about changed traits for scroll/highlight
        if (onTraitsChanged) {
          const changes: TraitChange[] = result.updated_traits.map(t => ({
            trait: t.trait,
            old_rr: t.old_rr,
            new_rr: t.new_rr,
            delta: t.new_rr - t.old_rr,
          }));
          onTraitsChanged(changes);
        }
      }

      onRefresh();
      if (onRefreshPanels) {
        onRefreshPanels();
      }

      // Show undo button for 60 seconds
      setShowUndo(true);
      if (undoTimerRef.current) {
        window.clearTimeout(undoTimerRef.current);
      }
      undoTimerRef.current = window.setTimeout(() => {
        setShowUndo(false);
      }, 60000);
    } catch (error) {
      onNotify(error instanceof Error ? error.message : 'Failed to rescore.', 'error');
    } finally {
      setRescoring(false);
    }
  }

  async function handleUndo() {
    if (!hasUser) {
      return;
    }
    setUndoing(true);
    try {
      const result = await revertLastRescore(trimmedUser);
      if (result.ok) {
        onNotify(result.message || `Undid last rescore (${result.reverted_count} traits)`, 'success');
        setShowUndo(false);
        if (onRefreshPanels) {
          onRefreshPanels();
        }
      } else {
        onNotify(result.message || 'Failed to undo', 'error');
      }
    } catch (error) {
      onNotify(error instanceof Error ? error.message : 'Failed to undo.', 'error');
    } finally {
      setUndoing(false);
    }
  }

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (undoTimerRef.current) {
        window.clearTimeout(undoTimerRef.current);
      }
    };
  }, []);

  // Quick Actions panel hidden to save screen real estate
  return null;
}
