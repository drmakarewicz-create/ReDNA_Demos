'use client';

import { useState, useEffect, useCallback } from 'react';
import { CORE_API_BASE } from '../lib/api';
import { LifeWeekReview } from './life-week-review';

interface NorthStar {
  identity: string;
  purpose: string;
  happiness_notes: string;
}

interface Todo {
  id: string;
  text: string;
  when: 'today' | 'week' | 'backlog' | 'scheduled';
  priority: number;
  status: 'open' | 'done' | 'snoozed';
  goal_id?: string;
  tags: string[];
  created_at: string;
  updated_at: string;
}

interface Goal {
  id: string;
  text: string;
  owner: string;
  why: string;
  first_step: string;
  confidence: number;
  target_date?: string;
  status: 'active' | 'completed' | 'archived';
}

interface Link {
  id: string;
  title: string;
  url: string;
  source: string;
  est_time_minutes?: number;
}

interface Inspiration {
  id: string;
  text: string;
  source: string;
  why_matters: string;
}

interface Project {
  id: string;
  title: string;
  goal_id?: string;
  quadrant: string;
  status: string;
  next_step?: string;
  risk?: string;
  confidence: number;
}

interface CompactInsights {
  todays_three_success_rate: number;
  current_streak: number;
  top_tag: string | null;
  quadrant_share: {
    important_urgent: number;
    important_not_urgent: number;
    not_important_urgent: number;
    neither: number;
  };
}

interface LifeSummary {
  north_star: NorthStar;
  today_three: Todo[];
  inbox: Todo[];
  goals: Goal[];
  links: Link[];
  quote: Inspiration | null;
}

interface LifeOSChatPanelProps {
  userId: string;
  variant?: 'full' | 'relationship' | 'hidden';
}

type ModalType = 'goal' | 'project' | 'link' | 'quote' | 'north_star' | null;

type HumanIntelDirection = 'up' | 'down' | 'steady';

interface HumanIntelGap {
  target?: string;
  namespace?: string;
  debt_score?: number;
}

interface HumanIntelSnapshot {
  generated_at: string;
  empathy: {
    latest: {
      emotional_state?: string | null;
      bonding_metrics: {
        trust_score: number;
        rapport_score: number;
      };
    } | null;
    trend: {
      direction: HumanIntelDirection;
      trust_delta: number;
    };
  };
  curiosity: {
    top_gaps: HumanIntelGap[];
    trend: {
      direction: HumanIntelDirection;
      delta: number;
    };
    snapshot: {
      daily_questions: HumanIntelGap[];
    };
  };
}

export function LifeOSChatPanel({ userId, variant = 'full' }: LifeOSChatPanelProps) {
  // Persistent collapse state
  const [collapsed, setCollapsed] = useState(() => {
    if (typeof window === 'undefined') return false;
    try {
      const key = `life_os_chat_collapsed:${userId}`;
      const stored = localStorage.getItem(key);
      return stored === 'true';
    } catch {
      return false;
    }
  });

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<LifeSummary | null>(null);
  const [topProject, setTopProject] = useState<Project | null>(null);
  const [insights, setInsights] = useState<CompactInsights | null>(null);
  const [humanIntel, setHumanIntel] = useState<HumanIntelSnapshot | null>(null);
  const [captureText, setCaptureText] = useState('');
  const [capturing, setCapturing] = useState(false);

  // Modal state
  const [activeModal, setActiveModal] = useState<ModalType>(null);
  const [showAddMenu, setShowAddMenu] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);
  const [modalSubmitting, setModalSubmitting] = useState(false);

  // Form state for Goal
  const [goalText, setGoalText] = useState('');
  const [goalWhy, setGoalWhy] = useState('');
  const [goalFirstStep, setGoalFirstStep] = useState('');
  const [goalConfidence, setGoalConfidence] = useState(0.5);

  // Form state for Project
  const [projectTitle, setProjectTitle] = useState('');
  const [projectGoalId, setProjectGoalId] = useState('');
  const [projectNextStep, setProjectNextStep] = useState('');

  // Form state for Link
  const [linkTitle, setLinkTitle] = useState('');
  const [linkUrl, setLinkUrl] = useState('');
  const [linkSource, setLinkSource] = useState('');
  const [linkMinutes, setLinkMinutes] = useState('');

  // Form state for Quote
  const [quoteText, setQuoteText] = useState('');
  const [quoteAuthor, setQuoteAuthor] = useState('');

  // Form state for North Star
  const [nsIdentity, setNsIdentity] = useState('');
  const [nsPurpose, setNsPurpose] = useState('');
  const [nsHappiness, setNsHappiness] = useState('');

  const loadSummary = useCallback(async () => {
    setLoading(true);
    setError(null);
    setHumanIntel(null);
    try {
      const response = await fetch(`${CORE_API_BASE}/ui/hc/life/${userId}/summary`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = await response.json();

      // Filter data based on variant
      let filteredSummary = data.summary;
      if (variant === 'relationship' && filteredSummary) {
        // Filter to only relationship-tagged items
        filteredSummary = {
          ...filteredSummary,
          today_three: filteredSummary.today_three?.filter((t: Todo) =>
            t.tags?.includes('relationship') || t.tags?.includes('relationships')
          ) || [],
          inbox: filteredSummary.inbox?.filter((t: Todo) =>
            t.tags?.includes('relationship') || t.tags?.includes('relationships')
          ) || [],
          goals: filteredSummary.goals?.filter((g: Goal) =>
            g.text?.toLowerCase().includes('relationship') ||
            g.why?.toLowerCase().includes('relationship')
          ) || [],
        };
      }

      setSummary(filteredSummary);

      // Load top project
      try {
        const projectResponse = await fetch(`${CORE_API_BASE}/ui/hc/life/${userId}/projects/top?limit=1`);
        if (projectResponse.ok) {
          const projectData = await projectResponse.json();
          if (projectData.projects && projectData.projects.length > 0) {
            setTopProject(projectData.projects[0]);
          }
        }
      } catch (err) {
        console.debug('Projects not available:', err);
      }

      // Load insights (compact version)
      try {
        const insightsResponse = await fetch(`${CORE_API_BASE}/ui/hc/life/${userId}/insights?days=7`);
        if (insightsResponse.ok) {
          const insightsData = await insightsResponse.json();
          const fullInsights = insightsData.insights;
          // Extract compact subset
          setInsights({
            todays_three_success_rate: fullInsights.todays_three_success_rate,
            current_streak: fullInsights.current_streak,
            top_tag: fullInsights.top_tags.length > 0 ? fullInsights.top_tags[0][0] : null,
            quadrant_share: fullInsights.quadrant_share
          });
        }
      } catch (err) {
        console.debug('Insights not available:', err);
      }

      // Load human intelligence telemetry
      try {
        const intelResponse = await fetch(`${CORE_API_BASE}/ui/hc/life/${userId}/human_intel?days=7`);
        if (intelResponse.ok) {
          const intelData = await intelResponse.json();
          if (intelData.snapshot) {
            setHumanIntel(intelData.snapshot);
          } else {
            setHumanIntel(null);
          }
        } else {
          setHumanIntel(null);
        }
      } catch (err) {
        console.debug('Human intelligence telemetry not available:', err);
        setHumanIntel(null);
      }
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Unknown error';
      console.error('Failed to load Life OS summary:', err);
      setError(errorMsg);
    } finally {
      setLoading(false);
    }
  }, [userId, variant]);

  useEffect(() => {
    if (!collapsed) {
      loadSummary();
    }
  }, [collapsed, loadSummary]);

  const trendSymbolMap: Record<HumanIntelDirection, string> = { up: '↑', down: '↓', steady: '→' };
  const trendStyleMap: Record<HumanIntelDirection, string> = {
    up: 'text-emerald-300 bg-emerald-800/40 border border-emerald-500/40',
    down: 'text-rose-300 bg-rose-800/40 border border-rose-500/40',
    steady: 'text-slate-300 bg-slate-800/40 border border-slate-600/60',
  };

  const formatDeltaShort = (value: number): string => {
    const scaled = value * 100;
    if (Math.abs(scaled) < 0.05) {
      return '0.0';
    }
    const prefix = scaled > 0 ? '+' : '';
    return `${prefix}${scaled.toFixed(1)}`;
  };

  const handleQuickCapture = async () => {
    if (!captureText.trim()) return;

    setCapturing(true);
    try {
      const response = await fetch(`${CORE_API_BASE}/ui/hc/life/${userId}/capture`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ text: captureText, when: 'today' }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      setCaptureText('');
      loadSummary();
    } catch (err) {
      console.error('Quick capture failed:', err);
      setError('Failed to capture task');
    } finally {
      setCapturing(false);
    }
  };

  const handleToggleTodo = async (todoId: string, currentStatus: string) => {
    const newStatus = currentStatus === 'done' ? 'open' : 'done';

    try {
      const response = await fetch(`${CORE_API_BASE}/ui/hc/life/${userId}/todos/${todoId}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ status: newStatus }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      loadSummary();
    } catch (err) {
      console.error('Toggle todo failed:', err);
    }
  };

  const handleToggleCollapse = () => {
    const newCollapsed = !collapsed;
    setCollapsed(newCollapsed);

    if (typeof window !== 'undefined') {
      try {
        const key = `life_os_chat_collapsed:${userId}`;
        localStorage.setItem(key, String(newCollapsed));
      } catch (err) {
        console.debug('Failed to persist collapse state:', err);
      }
    }
  };

  const openModal = (type: ModalType) => {
    setActiveModal(type);
    setShowAddMenu(false);
    setModalError(null);

    // Pre-fill North Star if it exists
    if (type === 'north_star' && summary?.north_star) {
      setNsIdentity(summary.north_star.identity || '');
      setNsPurpose(summary.north_star.purpose || '');
      setNsHappiness(summary.north_star.happiness_notes || '');
    }
  };

  const closeModal = () => {
    setActiveModal(null);
    setModalError(null);
    // Reset form state
    setGoalText('');
    setGoalWhy('');
    setGoalFirstStep('');
    setGoalConfidence(0.5);
    setProjectTitle('');
    setProjectGoalId('');
    setProjectNextStep('');
    setLinkTitle('');
    setLinkUrl('');
    setLinkSource('');
    setLinkMinutes('');
    setQuoteText('');
    setQuoteAuthor('');
    setNsIdentity('');
    setNsPurpose('');
    setNsHappiness('');
  };

  const handleSubmitGoal = async () => {
    if (!goalText.trim() || !goalFirstStep.trim()) {
      setModalError('Goal text and first step are required');
      return;
    }

    setModalSubmitting(true);
    setModalError(null);

    try {
      const response = await fetch(`${CORE_API_BASE}/ui/hc/life/${userId}/goals`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: goalText,
          owner: userId,
          why: goalWhy || 'Personal goal',
          first_step: goalFirstStep,
          confidence: goalConfidence,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      closeModal();
      loadSummary();
    } catch (err) {
      setModalError(err instanceof Error ? err.message : 'Failed to create goal');
    } finally {
      setModalSubmitting(false);
    }
  };

  const handleSubmitProject = async () => {
    if (!projectTitle.trim()) {
      setModalError('Project title is required');
      return;
    }

    setModalSubmitting(true);
    setModalError(null);

    try {
      const response = await fetch(`${CORE_API_BASE}/ui/hc/life/${userId}/projects`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: projectTitle,
          goal_id: projectGoalId || undefined,
          next_step: projectNextStep || undefined,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      closeModal();
      loadSummary();
    } catch (err) {
      setModalError(err instanceof Error ? err.message : 'Failed to create project');
    } finally {
      setModalSubmitting(false);
    }
  };

  const handleSubmitLink = async () => {
    if (!linkTitle.trim() || !linkUrl.trim()) {
      setModalError('Title and URL are required');
      return;
    }

    setModalSubmitting(true);
    setModalError(null);

    try {
      const response = await fetch(`${CORE_API_BASE}/ui/hc/life/${userId}/links`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: linkTitle,
          url: linkUrl,
          source: linkSource || 'Manual',
          est_time_minutes: linkMinutes ? parseInt(linkMinutes) : undefined,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      closeModal();
      loadSummary();
    } catch (err) {
      setModalError(err instanceof Error ? err.message : 'Failed to save link');
    } finally {
      setModalSubmitting(false);
    }
  };

  const empathyState = humanIntel?.empathy.latest?.emotional_state ?? 'neutral';
  const trustPercent = humanIntel?.empathy.latest
    ? Math.round(humanIntel.empathy.latest.bonding_metrics.trust_score * 100)
    : null;
  const curiosityPrompt =
    humanIntel?.curiosity.snapshot.daily_questions[0]?.target ??
    humanIntel?.curiosity.snapshot.daily_questions[0]?.namespace ??
    null;

  const handleSubmitQuote = async () => {
    if (!quoteText.trim()) {
      setModalError('Quote text is required');
      return;
    }

    setModalSubmitting(true);
    setModalError(null);

    try {
      // For MVP: use links endpoint with special marker
      const response = await fetch(`${CORE_API_BASE}/ui/hc/life/${userId}/links`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: quoteText,
          url: 'inspiration://local',
          source: quoteAuthor || 'Unknown',
          est_time_minutes: 0,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      closeModal();
      loadSummary();
    } catch (err) {
      setModalError(err instanceof Error ? err.message : 'Failed to add quote');
    } finally {
      setModalSubmitting(false);
    }
  };

  const handleSubmitNorthStar = async () => {
    setModalSubmitting(true);
    setModalError(null);

    try {
      // Use PATCH on summary endpoint with north_star field
      const response = await fetch(`${CORE_API_BASE}/ui/hc/life/${userId}/north_star`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          identity: nsIdentity,
          purpose: nsPurpose,
          happiness_notes: nsHappiness,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      closeModal();
      loadSummary();
    } catch (err) {
      setModalError(err instanceof Error ? err.message : 'Failed to update North Star');
    } finally {
      setModalSubmitting(false);
    }
  };

  const renderModal = () => {
    if (!activeModal) return null;

    const handleKeyDown = (e: React.KeyboardEvent) => {
      if (e.key === 'Escape') {
        closeModal();
      } else if (e.key === 'Enter' && !e.shiftKey && activeModal !== 'north_star') {
        e.preventDefault();
        if (activeModal === 'goal') handleSubmitGoal();
        else if (activeModal === 'project') handleSubmitProject();
        else if (activeModal === 'link') handleSubmitLink();
        else if (activeModal === 'quote') handleSubmitQuote();
      }
    };

    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" onClick={closeModal}>
        <div
          className="bg-slate-900 border border-slate-700 rounded-xl p-4 w-full max-w-md space-y-3"
          onClick={(e) => e.stopPropagation()}
          onKeyDown={handleKeyDown}
        >
          {/* Goal Modal */}
          {activeModal === 'goal' && (
            <>
              <div className="text-sm font-semibold text-slate-200">Add Goal</div>
              <input
                type="text"
                value={goalText}
                onChange={(e) => setGoalText(e.target.value)}
                placeholder="Goal (e.g., Run a 5K)"
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500"
                autoFocus
              />
              <input
                type="text"
                value={goalWhy}
                onChange={(e) => setGoalWhy(e.target.value)}
                placeholder="Why? (optional)"
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500"
              />
              <input
                type="text"
                value={goalFirstStep}
                onChange={(e) => setGoalFirstStep(e.target.value)}
                placeholder="First step"
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500"
              />
              <div className="space-y-1">
                <div className="flex items-center justify-between text-xs text-slate-400">
                  <span>Confidence</span>
                  <span className="tabular-nums">{Math.round(goalConfidence * 100)}%</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.1"
                  value={goalConfidence}
                  onChange={(e) => setGoalConfidence(parseFloat(e.target.value))}
                  className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer slider-cyan"
                />
              </div>
            </>
          )}

          {/* Project Modal */}
          {activeModal === 'project' && (
            <>
              <div className="text-sm font-semibold text-slate-200">Add Project</div>
              <input
                type="text"
                value={projectTitle}
                onChange={(e) => setProjectTitle(e.target.value)}
                placeholder="Project title"
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500"
                autoFocus
              />
              {summary && summary.goals.length > 0 && (
                <select
                  value={projectGoalId}
                  onChange={(e) => setProjectGoalId(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
                >
                  <option value="">Link to goal (optional)</option>
                  {summary.goals.map((goal) => (
                    <option key={goal.id} value={goal.id}>{goal.text}</option>
                  ))}
                </select>
              )}
              <input
                type="text"
                value={projectNextStep}
                onChange={(e) => setProjectNextStep(e.target.value)}
                placeholder="Next step (optional)"
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500"
              />
            </>
          )}

          {/* Link Modal */}
          {activeModal === 'link' && (
            <>
              <div className="text-sm font-semibold text-slate-200">Save Link</div>
              <input
                type="text"
                value={linkTitle}
                onChange={(e) => setLinkTitle(e.target.value)}
                placeholder="Title"
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500"
                autoFocus
              />
              <input
                type="url"
                value={linkUrl}
                onChange={(e) => setLinkUrl(e.target.value)}
                placeholder="URL"
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500"
              />
              <div className="grid grid-cols-2 gap-2">
                <input
                  type="text"
                  value={linkSource}
                  onChange={(e) => setLinkSource(e.target.value)}
                  placeholder="Source (optional)"
                  className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500"
                />
                <input
                  type="number"
                  value={linkMinutes}
                  onChange={(e) => setLinkMinutes(e.target.value)}
                  placeholder="Minutes"
                  className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500"
                />
              </div>
            </>
          )}

          {/* Quote Modal */}
          {activeModal === 'quote' && (
            <>
              <div className="text-sm font-semibold text-slate-200">Add Inspiration</div>
              <textarea
                value={quoteText}
                onChange={(e) => setQuoteText(e.target.value)}
                placeholder="Quote or wisdom..."
                rows={3}
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500 resize-none"
                autoFocus
              />
              <input
                type="text"
                value={quoteAuthor}
                onChange={(e) => setQuoteAuthor(e.target.value)}
                placeholder="Author/Source (optional)"
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500"
              />
            </>
          )}

          {/* North Star Modal */}
          {activeModal === 'north_star' && (
            <>
              <div className="text-sm font-semibold text-slate-200">Set North Star</div>
              <input
                type="text"
                value={nsIdentity}
                onChange={(e) => setNsIdentity(e.target.value)}
                placeholder="Identity (who you are)"
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500"
                autoFocus
              />
              <input
                type="text"
                value={nsPurpose}
                onChange={(e) => setNsPurpose(e.target.value)}
                placeholder="Purpose (what drives you)"
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500"
              />
              <textarea
                value={nsHappiness}
                onChange={(e) => setNsHappiness(e.target.value)}
                placeholder="Happiness notes (what makes you happy)"
                rows={2}
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500 resize-none"
              />
            </>
          )}

          {modalError && (
            <div className="text-xs text-red-400 bg-red-950/30 rounded px-2 py-1.5 flex items-center justify-between">
              <span>{modalError}</span>
              <button onClick={() => setModalError(null)} className="text-red-300 hover:text-red-200">×</button>
            </div>
          )}

          <div className="flex gap-2 pt-1">
            <button
              onClick={closeModal}
              className="flex-1 px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium rounded-lg transition-colors"
            >
              Cancel (Esc)
            </button>
            <button
              onClick={() => {
                if (activeModal === 'goal') handleSubmitGoal();
                else if (activeModal === 'project') handleSubmitProject();
                else if (activeModal === 'link') handleSubmitLink();
                else if (activeModal === 'quote') handleSubmitQuote();
                else if (activeModal === 'north_star') handleSubmitNorthStar();
              }}
              disabled={modalSubmitting}
              className="flex-1 px-3 py-2 bg-cyan-600 hover:bg-cyan-700 disabled:bg-slate-700 disabled:text-slate-500 text-white text-xs font-medium rounded-lg transition-colors"
            >
              {modalSubmitting ? 'Saving...' : 'Save (Enter)'}
            </button>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="rounded-xl border border-slate-700/50 bg-gradient-to-br from-slate-900/40 to-slate-950/60 overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 flex items-center justify-between border-b border-slate-700/50">
        <button
          onClick={handleToggleCollapse}
          className="flex items-center gap-2 hover:opacity-80 transition-opacity"
        >
          <span className="text-lg">🎯</span>
          <span className="text-sm font-semibold text-slate-200">Life OS</span>
          <svg
            className={`w-4 h-4 text-slate-400 transition-transform ${collapsed ? '' : 'rotate-90'}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </button>

        {!collapsed && (
          <div className="relative">
            <button
              onClick={() => setShowAddMenu(!showAddMenu)}
              className="px-2 py-1 bg-cyan-600/20 hover:bg-cyan-600/30 text-cyan-400 text-xs font-medium rounded-md transition-colors flex items-center gap-1"
            >
              <span>+</span>
              <span>Add</span>
            </button>

            {showAddMenu && (
              <>
                <div className="fixed inset-0 z-40" onClick={() => setShowAddMenu(false)} />
                <div className="absolute right-0 top-full mt-1 bg-slate-900 border border-slate-700 rounded-lg shadow-xl py-1 z-50 min-w-[140px]">
                  <button
                    onClick={() => openModal('goal')}
                    className="w-full px-3 py-1.5 text-xs text-slate-300 hover:bg-slate-800 text-left"
                  >
                    Add Goal
                  </button>
                  <button
                    onClick={() => openModal('project')}
                    className="w-full px-3 py-1.5 text-xs text-slate-300 hover:bg-slate-800 text-left"
                  >
                    Add Project
                  </button>
                  <button
                    onClick={() => openModal('link')}
                    className="w-full px-3 py-1.5 text-xs text-slate-300 hover:bg-slate-800 text-left"
                  >
                    Save Link
                  </button>
                  <button
                    onClick={() => openModal('quote')}
                    className="w-full px-3 py-1.5 text-xs text-slate-300 hover:bg-slate-800 text-left"
                  >
                    Add Quote
                  </button>
                  <div className="border-t border-slate-700 my-1" />
                  <button
                    onClick={() => openModal('north_star')}
                    className="w-full px-3 py-1.5 text-xs text-slate-300 hover:bg-slate-800 text-left"
                  >
                    Set North Star
                  </button>
                </div>
              </>
            )}
          </div>
        )}
      </div>

      {/* Content */}
      {!collapsed && (
        <div className="px-4 pb-4 space-y-4">
          {loading && (
            <div className="text-xs text-slate-400 text-center py-4">Loading...</div>
          )}

          {error && (
            <div className="text-xs text-amber-400 bg-amber-950/30 rounded-lg px-3 py-2 flex items-center justify-between">
              <span>{error}</span>
              <button
                onClick={loadSummary}
                className="text-amber-300 hover:text-amber-200 underline"
              >
                Retry
              </button>
            </div>
          )}

          {!loading && !error && summary && (
            <>
              {/* Quick Capture */}
              <div className="space-y-2 pt-2">
                <div className="text-xs font-semibold text-slate-300">Quick Capture</div>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={captureText}
                    onChange={(e) => setCaptureText(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleQuickCapture()}
                    placeholder="Add task..."
                    disabled={capturing}
                    className="flex-1 bg-slate-800/50 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500/50"
                  />
                  <button
                    onClick={handleQuickCapture}
                    disabled={!captureText.trim() || capturing}
                    className="px-3 py-1.5 bg-cyan-600 hover:bg-cyan-700 disabled:bg-slate-700 disabled:text-slate-500 text-white text-xs font-medium rounded-lg transition-colors"
                  >
                    +
                  </button>
                </div>
              </div>

              {/* Human Intelligence */}
              <div className="space-y-2">
                <div className="text-xs font-semibold text-slate-300">Human Intelligence</div>
                <div className="bg-slate-800/40 rounded-lg p-2.5 border border-slate-700/60">
                  {humanIntel ? (
                    <div className="space-y-2 text-[11px] text-slate-200">
                      <div className="flex items-center justify-between gap-2">
                        <div>
                          <div className="text-[10px] uppercase text-slate-500">Empathy</div>
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-semibold text-rose-300">
                              {empathyState}
                            </span>
                            <span
                              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium border ${trendStyleMap[humanIntel.empathy.trend.direction]}`}
                              title={`Trust delta ${formatDeltaShort(humanIntel.empathy.trend.trust_delta)} pts`}
                            >
                              {trendSymbolMap[humanIntel.empathy.trend.direction]}{' '}
                              {formatDeltaShort(humanIntel.empathy.trend.trust_delta)}
                            </span>
                          </div>
                        </div>
                        <div className="text-right text-[10px] text-slate-400">
                          Trust {trustPercent !== null ? `${trustPercent}%` : '—'}
                        </div>
                      </div>
                      <div className="border-t border-slate-700/60 pt-2 flex items-start justify-between gap-3">
                        <div className="flex-1">
                          <div className="text-[10px] uppercase text-slate-500">Curiosity</div>
                          {humanIntel.curiosity.top_gaps.length > 0 ? (
                            <ul className="space-y-1">
                              {humanIntel.curiosity.top_gaps.slice(0, 3).map((gap, index) => (
                                <li
                                  key={`${gap.target ?? index}`}
                                  className="flex items-center justify-between text-[10px] text-slate-300"
                                >
                                  <span className="truncate">
                                    {gap.namespace ?? gap.target ?? 'Unknown'}
                                  </span>
                                  <span className="text-sky-300 font-medium">
                                    {(gap.debt_score ?? 0).toFixed(2)}
                                  </span>
                                </li>
                              ))}
                            </ul>
                          ) : (
                            <div className="text-[10px] text-slate-500">No open gaps</div>
                          )}
                        </div>
                        <div className="w-28 text-[10px] text-slate-400">
                          <div className="text-slate-500 uppercase tracking-wide">Prompt</div>
                          <div className="italic text-slate-300 line-clamp-3">
                            {curiosityPrompt ?? 'Engage curiosity today'}
                          </div>
                        </div>
                      </div>
                      <div className="pt-1 text-right">
                        <a
                          href={`http://localhost:3100/user-ops/${userId}/hc`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-[10px] text-cyan-400 hover:text-cyan-300 hover:underline"
                        >
                          Explore in DevX →
                        </a>
                      </div>
                    </div>
                  ) : (
                    <div className="text-[10px] text-slate-500">
                      Human telemetry not available yet.
                    </div>
                  )}
                </div>
              </div>

              {/* Today's 3 */}
              {summary.today_three.length > 0 ? (
                <div className="space-y-2">
                  <div className="text-xs font-semibold text-slate-300">Today's 3</div>
                  <div className="space-y-1.5">
                    {summary.today_three.slice(0, 3).map((todo) => (
                      <div key={todo.id} className="flex items-start gap-2">
                        <input
                          type="checkbox"
                          checked={todo.status === 'done'}
                          onChange={() => handleToggleTodo(todo.id, todo.status)}
                          className="mt-0.5 h-3.5 w-3.5 rounded border-slate-600 text-cyan-600 focus:ring-cyan-500 focus:ring-offset-slate-900"
                        />
                        <span
                          className={`text-xs flex-1 ${
                            todo.status === 'done'
                              ? 'line-through text-slate-500'
                              : 'text-slate-300'
                          }`}
                        >
                          {todo.text}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="text-xs text-slate-400 italic text-center py-2">
                  No tasks for today — use <button onClick={handleQuickCapture} className="text-cyan-400 hover:underline">Quick Capture</button>
                </div>
              )}

              {/* Goals */}
              {summary.goals.length > 0 ? (
                <div className="space-y-2">
                  <div className="text-xs font-semibold text-slate-300">Active Goals</div>
                  <div className="space-y-2">
                    {summary.goals.slice(0, 3).map((goal) => (
                      <div key={goal.id} className="bg-slate-800/40 rounded-lg p-2.5 space-y-1.5">
                        <div className="text-xs font-medium text-slate-200">{goal.text}</div>
                        <div className="text-[10px] text-slate-400">
                          Next: {goal.first_step}
                        </div>
                        <div className="flex items-center gap-2">
                          <div className="flex-1 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                            <div
                              className="h-full bg-gradient-to-r from-cyan-500 to-blue-500 rounded-full"
                              style={{ width: `${goal.confidence * 100}%` }}
                            />
                          </div>
                          <span className="text-[10px] text-slate-400 tabular-nums">
                            {Math.round(goal.confidence * 100)}%
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="text-xs text-slate-400 italic text-center py-2">
                  No goals yet — <button onClick={() => openModal('goal')} className="text-cyan-400 hover:underline">Add Goal</button>
                </div>
              )}

              {/* Top Project */}
              {topProject ? (
                <div className="space-y-2">
                  <div className="text-xs font-semibold text-slate-300">Top Project</div>
                  <div className="bg-slate-800/40 rounded-lg p-2.5 space-y-1.5 border-l-2 border-orange-500">
                    <div className="text-xs font-medium text-slate-200">{topProject.title}</div>
                    {topProject.next_step && (
                      <div className="text-[10px] text-slate-400">
                        Next: {topProject.next_step}
                      </div>
                    )}
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-orange-500 to-amber-500 rounded-full"
                          style={{ width: `${topProject.confidence * 100}%` }}
                        />
                      </div>
                      <span className="text-[10px] text-slate-400 tabular-nums">
                        {Math.round(topProject.confidence * 100)}%
                      </span>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-xs text-slate-400 italic text-center py-2">
                  No active projects — <button onClick={() => openModal('project')} className="text-cyan-400 hover:underline">Add Project</button>
                </div>
              )}

              {/* Week in Review - Phase 4 */}
              <LifeWeekReview userId={userId} collapsed={collapsed} />

              {/* Compact Insights - Phase 3 */}
              {insights && (insights.current_streak > 0 || insights.todays_three_success_rate > 0) && (
                <div className="space-y-2">
                  <div className="text-xs font-semibold text-slate-300">📊 Insights</div>
                  <div className="bg-slate-800/40 rounded-lg p-2.5 space-y-2">
                    <div className="grid grid-cols-3 gap-2 text-center">
                      <div>
                        <div className="text-base font-bold text-cyan-400">{insights.todays_three_success_rate.toFixed(0)}%</div>
                        <div className="text-[9px] text-slate-400">Success</div>
                      </div>
                      <div>
                        <div className="text-base font-bold text-green-400">{insights.current_streak}</div>
                        <div className="text-[9px] text-slate-400">Streak</div>
                      </div>
                      <div>
                        <div className="text-base font-bold text-purple-400">
                          {insights.quadrant_share.important_not_urgent.toFixed(0)}%
                        </div>
                        <div className="text-[9px] text-slate-400">Plan</div>
                      </div>
                    </div>
                    {insights.top_tag && (
                      <div className="pt-2 border-t border-slate-700 text-[10px] text-slate-400 text-center">
                        Focus: <span className="text-purple-300 font-medium">{insights.top_tag}</span>
                      </div>
                    )}
                    <div className="pt-1">
                      <a
                        href={`http://localhost:3100/user-ops/${userId}/hc`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[10px] text-cyan-400 hover:text-cyan-300 hover:underline block text-center"
                      >
                        View details in DevX →
                      </a>
                    </div>
                  </div>
                </div>
              )}

              {/* Links */}
              {summary.links.length > 0 ? (
                <div className="space-y-2">
                  <div className="text-xs font-semibold text-slate-300">Reading</div>
                  <div className="space-y-1.5">
                    {summary.links.slice(0, 2).map((link) => (
                      <a
                        key={link.id}
                        href={link.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="block text-xs text-cyan-400 hover:text-cyan-300 hover:underline"
                      >
                        {link.title}
                        {link.est_time_minutes && (
                          <span className="text-slate-500 ml-1">
                            ({link.est_time_minutes}m)
                          </span>
                        )}
                      </a>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="text-xs text-slate-400 italic text-center py-2">
                  No saved links yet — <button onClick={() => openModal('link')} className="text-cyan-400 hover:underline">Save Link</button>
                </div>
              )}

              {/* Inspiration Quote */}
              {summary.quote ? (
                <div className="bg-gradient-to-br from-purple-950/30 to-blue-950/30 rounded-lg p-3 border border-purple-800/30">
                  <div className="text-[11px] italic text-purple-200/90 leading-relaxed">
                    "{summary.quote.text}"
                  </div>
                  <div className="text-[10px] text-purple-400/70 mt-1.5">
                    — {summary.quote.source}
                  </div>
                </div>
              ) : (
                <div className="text-xs text-slate-400 italic text-center py-2">
                  No inspiration yet — <button onClick={() => openModal('quote')} className="text-cyan-400 hover:underline">Add Quote</button>
                </div>
              )}

              {/* North Star CTA */}
              {(!summary.north_star.identity && !summary.north_star.purpose) && (
                <div className="text-xs text-slate-400 italic text-center py-2 border-t border-slate-700/50 pt-4">
                  North Star not set — <button onClick={() => openModal('north_star')} className="text-cyan-400 hover:underline">Define your purpose</button>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {renderModal()}
    </div>
  );
}
