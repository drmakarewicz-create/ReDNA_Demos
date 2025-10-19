'use client';

import { useState } from 'react';
import { CoachBrainVisualizer } from './coach-brain-visualizer';
import { ChorusPreview } from './chorus-preview';
import { ToneEcho } from './tone-echo';
import { TraitTimeline } from './trait-timeline';
import { DualCoachCompare } from './dual-coach-compare';
import { EmotionTimeline } from './emotion-timeline';
import { PermissionOverlay } from './permission-overlay';

interface WowFactorDashboardProps {
  userId: string;
  demoMode?: boolean;
}

type ViewMode = 'overview' | 'detailed';
type PanelId =
  | 'brain'
  | 'chorus'
  | 'tone'
  | 'timeline'
  | 'compare'
  | 'emotion'
  | 'permissions';

export function WowFactorDashboard({
  userId,
  demoMode = false,
}: WowFactorDashboardProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('overview');
  const [activePanels, setActivePanels] = useState<Set<PanelId>>(
    new Set(['brain', 'chorus', 'tone'])
  );
  const [showPermissions, setShowPermissions] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const togglePanel = (panelId: PanelId) => {
    setActivePanels((prev) => {
      const next = new Set(prev);
      if (next.has(panelId)) {
        next.delete(panelId);
      } else {
        next.add(panelId);
      }
      return next;
    });
  };

  const panels = [
    { id: 'brain' as PanelId, label: 'Coach Brain', icon: '🧠' },
    { id: 'chorus' as PanelId, label: 'Chorus', icon: '🎵' },
    { id: 'tone' as PanelId, label: 'Tone Echo', icon: '🎯' },
    { id: 'timeline' as PanelId, label: 'Timeline', icon: '⏱️' },
    { id: 'compare' as PanelId, label: 'Compare', icon: '⚖️' },
    { id: 'emotion' as PanelId, label: 'Emotions', icon: '💭' },
    { id: 'permissions' as PanelId, label: 'Privacy', icon: '🔒' },
  ];

  const handleExportScreenshot = () => {
    alert('Screenshot export would be triggered here (requires html2canvas library)');
  };

  const handleStartDemo = () => {
    // Enable all panels for demo
    setActivePanels(new Set(['brain', 'chorus', 'tone', 'timeline', 'emotion', 'permissions']));
    setViewMode('detailed');
    setAutoRefresh(true);
    setShowPermissions(true);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 p-6">
      {/* Header */}
      <div className="mb-6 rounded-2xl border border-slate-800 bg-slate-900/70 p-6 shadow-xl backdrop-blur">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-100">
              ReDNA Wow Factor Demo
            </h1>
            <p className="mt-1 text-sm text-slate-400">
              Phase 7: Interactive Intelligence Visualization
            </p>
          </div>
          <div className="flex items-center gap-2">
            {demoMode && (
              <button
                onClick={handleStartDemo}
                className="rounded-lg bg-gradient-to-r from-blue-600 to-purple-600 px-4 py-2 text-sm font-medium text-white hover:from-blue-700 hover:to-purple-700"
              >
                ▶ Start Demo
              </button>
            )}
            <button
              onClick={handleExportScreenshot}
              className="rounded-lg bg-slate-800 px-4 py-2 text-sm font-medium text-slate-300 hover:bg-slate-700"
            >
              📸 Export
            </button>
          </div>
        </div>

        {/* Controls */}
        <div className="flex flex-wrap items-center gap-4">
          {/* View Mode Toggle */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-400">View:</span>
            <button
              onClick={() => setViewMode('overview')}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium ${
                viewMode === 'overview'
                  ? 'bg-blue-900/50 text-blue-300'
                  : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
              }`}
            >
              Overview
            </button>
            <button
              onClick={() => setViewMode('detailed')}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium ${
                viewMode === 'detailed'
                  ? 'bg-blue-900/50 text-blue-300'
                  : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
              }`}
            >
              Detailed
            </button>
          </div>

          {/* Auto-refresh Toggle */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-400">Auto-refresh:</span>
            <button
              onClick={() => setAutoRefresh(!autoRefresh)}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium ${
                autoRefresh
                  ? 'bg-green-900/50 text-green-300'
                  : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
              }`}
            >
              {autoRefresh ? 'ON' : 'OFF'}
            </button>
          </div>

          {/* Panel Selection */}
          <div className="ml-auto flex flex-wrap items-center gap-2">
            <span className="text-xs text-slate-400">Panels:</span>
            {panels.map((panel) => (
              <button
                key={panel.id}
                onClick={() => togglePanel(panel.id)}
                className={`rounded-lg px-2 py-1 text-xs font-medium ${
                  activePanels.has(panel.id)
                    ? 'bg-blue-900/50 text-blue-300'
                    : 'bg-slate-800 text-slate-500 hover:bg-slate-700'
                }`}
              >
                {panel.icon} {panel.label}
              </button>
            ))}
          </div>
        </div>

        {/* User Info */}
        <div className="mt-4 rounded-lg bg-slate-800/50 px-3 py-2 text-xs text-slate-400">
          User ID: <span className="font-mono text-slate-300">{userId}</span>
          {demoMode && (
            <span className="ml-3 rounded bg-purple-900/50 px-2 py-0.5 text-purple-300">
              DEMO MODE
            </span>
          )}
        </div>
      </div>

      {/* Main Content Grid */}
      <div
        className={`grid gap-6 ${
          viewMode === 'overview' ? 'grid-cols-1 lg:grid-cols-2' : 'grid-cols-1'
        }`}
      >
        {/* Coach Brain Visualizer */}
        {activePanels.has('brain') && (
          <CoachBrainVisualizer
            userId={userId}
            autoRefresh={autoRefresh}
            refreshInterval={3000}
          />
        )}

        {/* Chorus Preview */}
        {activePanels.has('chorus') && (
          <ChorusPreview
            userId={userId}
            autoRefresh={autoRefresh}
            refreshInterval={5000}
          />
        )}

        {/* Tone Echo */}
        {activePanels.has('tone') && (
          <ToneEcho
            userId={userId}
            autoRefresh={autoRefresh}
            refreshInterval={3000}
          />
        )}

        {/* Trait Timeline */}
        {activePanels.has('timeline') && (
          <TraitTimeline userId={userId} autoPlay={demoMode} />
        )}

        {/* Dual-Coach Comparison */}
        {activePanels.has('compare') && <DualCoachCompare userId={userId} />}

        {/* Emotion Timeline */}
        {activePanels.has('emotion') && (
          <EmotionTimeline
            userId={userId}
            autoRefresh={autoRefresh}
            refreshInterval={10000}
          />
        )}
      </div>

      {/* Permission Overlay */}
      {(activePanels.has('permissions') || showPermissions) && (
        <PermissionOverlay
          userId={userId}
          showOverlay={true}
          onToggle={setShowPermissions}
        />
      )}

      {/* Footer */}
      <div className="mt-6 rounded-2xl border border-slate-800 bg-slate-900/70 p-4 text-center">
        <div className="text-xs text-slate-400">
          ReDNA Phase 7 — Wow Factor Demo Dashboard
        </div>
        <div className="mt-1 text-xs text-slate-500">
          All visualizations update in real-time • Privacy-first design • Fully auditable
        </div>
      </div>
    </div>
  );
}
