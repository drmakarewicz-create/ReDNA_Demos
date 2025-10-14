'use client';

import { useState, useEffect } from 'react';
import { CORE_API_BASE } from '../../lib/api';

interface BrainNode {
  id: string;
  label: string;
  active: boolean;
  weight: number;
}

interface BrainEdge {
  from: string;
  to: string;
  strength: number;
}

interface BrainSnapshot {
  ts: string;
  user_id: string;
  context_version: number;
  active_coach_id: string;
  nodes: BrainNode[];
  edges: BrainEdge[];
  meta: {
    augment_confidence: number;
    curiosity_priority: number;
    curiosity_target?: string | null;
    learning_positive_rate: number;
    requires_consent: boolean;
  };
}

interface CoachBrainVisualizerProps {
  userId: string;
  autoRefresh?: boolean;
  refreshInterval?: number;
}

// Color coding by domain
const NODE_COLORS: Record<string, string> = {
  head_coach: 'rgb(59, 130, 246)', // blue
  head_coach_role: 'rgb(59, 130, 246)',
  curiosity_engine: 'rgb(34, 197, 94)', // green
  learning: 'rgb(34, 197, 94)',
  permission: 'rgb(251, 191, 36)', // yellow
  career_coach: 'rgb(168, 85, 247)', // purple
  relationship_coach: 'rgb(236, 72, 153)', // pink
  padna_coach: 'rgb(20, 184, 166)', // teal
  photo_coach: 'rgb(249, 115, 22)', // orange
};

function getNodeColor(nodeId: string): string {
  return NODE_COLORS[nodeId] || 'rgb(148, 163, 184)'; // default slate
}

export function CoachBrainVisualizer({
  userId,
  autoRefresh = true,
  refreshInterval = 3000,
}: CoachBrainVisualizerProps) {
  const [snapshot, setSnapshot] = useState<BrainSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  const fetchBrainState = async () => {
    try {
      const response = await fetch(`${CORE_API_BASE}/ui/hc/brain_state/${userId}`);
      const json = await response.json();

      if (json.ok && json.brain_state) {
        setSnapshot(json.brain_state);
        setLastUpdate(new Date());
        setError(null);
      } else {
        setError(json.detail || 'Failed to load brain state');
      }
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBrainState();

    if (autoRefresh) {
      const interval = setInterval(fetchBrainState, refreshInterval);
      return () => clearInterval(interval);
    }
  }, [userId, autoRefresh, refreshInterval]);

  if (loading) {
    return (
      <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6">
        <h2 className="mb-4 text-lg font-semibold text-slate-200">
          Coach Brain Visualizer
        </h2>
        <div className="flex h-96 items-center justify-center">
          <div className="text-slate-500">Loading brain state...</div>
        </div>
      </div>
    );
  }

  if (error || !snapshot) {
    return (
      <div className="rounded-2xl border border-red-800/30 bg-red-950/20 p-6">
        <h2 className="mb-4 text-lg font-semibold text-red-400">
          Coach Brain Visualizer
        </h2>
        <div className="text-red-300">{error || 'No snapshot available'}</div>
      </div>
    );
  }

  // Layout nodes in a circle
  const centerX = 300;
  const centerY = 250;
  const radius = 150;
  const nodePositions: Record<string, { x: number; y: number }> = {};

  snapshot.nodes.forEach((node, index) => {
    const angle = (index / snapshot.nodes.length) * 2 * Math.PI - Math.PI / 2;
    nodePositions[node.id] = {
      x: centerX + radius * Math.cos(angle),
      y: centerY + radius * Math.sin(angle),
    };
  });

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-200">
          Coach Brain Visualizer
        </h2>
        {lastUpdate && (
          <div className="text-xs text-slate-500">
            Updated {lastUpdate.toLocaleTimeString()}
          </div>
        )}
      </div>

      {/* SVG Visualization */}
      <svg
        viewBox="0 0 600 500"
        className="w-full rounded-lg bg-slate-950/50"
      >
        {/* Render edges */}
        {snapshot.edges.map((edge, idx) => {
          const from = nodePositions[edge.from];
          const to = nodePositions[edge.to];
          if (!from || !to) return null;

          return (
            <g key={`edge-${idx}`}>
              <line
                x1={from.x}
                y1={from.y}
                x2={to.x}
                y2={to.y}
                stroke="rgba(148, 163, 184, 0.3)"
                strokeWidth={edge.strength * 3}
                strokeDasharray={edge.strength < 0.5 ? '5,5' : '0'}
              >
                <animate
                  attributeName="stroke-opacity"
                  values="0.3;0.7;0.3"
                  dur="2s"
                  repeatCount="indefinite"
                />
              </line>
            </g>
          );
        })}

        {/* Render nodes */}
        {snapshot.nodes.map((node) => {
          const pos = nodePositions[node.id];
          if (!pos) return null;

          const color = getNodeColor(node.id);
          const nodeRadius = 15 + node.weight * 25;
          const pulseActive = node.active && node.weight > 0.5;

          return (
            <g key={node.id}>
              {/* Pulse effect for active nodes */}
              {pulseActive && (
                <circle
                  cx={pos.x}
                  cy={pos.y}
                  r={nodeRadius}
                  fill={color}
                  opacity="0.2"
                >
                  <animate
                    attributeName="r"
                    values={`${nodeRadius};${nodeRadius + 15};${nodeRadius}`}
                    dur="1.5s"
                    repeatCount="indefinite"
                  />
                  <animate
                    attributeName="opacity"
                    values="0.4;0.1;0.4"
                    dur="1.5s"
                    repeatCount="indefinite"
                  />
                </circle>
              )}

              {/* Main node circle */}
              <circle
                cx={pos.x}
                cy={pos.y}
                r={nodeRadius}
                fill={color}
                opacity={node.active ? 0.8 : 0.3}
                stroke={node.active ? color : 'rgba(148, 163, 184, 0.5)'}
                strokeWidth="2"
              />

              {/* Node label */}
              <text
                x={pos.x}
                y={pos.y + nodeRadius + 18}
                textAnchor="middle"
                fill="rgb(226, 232, 240)"
                fontSize="11"
                fontWeight={node.active ? 'bold' : 'normal'}
              >
                {node.label}
              </text>

              {/* Weight indicator */}
              <text
                x={pos.x}
                y={pos.y + 4}
                textAnchor="middle"
                fill="white"
                fontSize="10"
                fontWeight="bold"
              >
                {Math.round(node.weight * 100)}%
              </text>
            </g>
          );
        })}
      </svg>

      {/* Metadata Display */}
      <div className="mt-4 grid grid-cols-2 gap-3 text-xs">
        <div className="rounded-lg bg-slate-800/50 p-3">
          <div className="mb-1 text-slate-400">Active Coach</div>
          <div className="font-semibold text-slate-200">
            {snapshot.active_coach_id.replace('_', ' ').toUpperCase()}
          </div>
        </div>

        <div className="rounded-lg bg-slate-800/50 p-3">
          <div className="mb-1 text-slate-400">Context Version</div>
          <div className="font-semibold text-slate-200">
            v{snapshot.context_version}
          </div>
        </div>

        {snapshot.meta.curiosity_target && (
          <div className="rounded-lg bg-green-950/20 p-3">
            <div className="mb-1 text-green-400">Curiosity Target</div>
            <div className="truncate font-mono text-xs text-green-300">
              {snapshot.meta.curiosity_target}
            </div>
          </div>
        )}

        {snapshot.meta.requires_consent && (
          <div className="rounded-lg bg-yellow-950/20 p-3">
            <div className="mb-1 text-yellow-400">Permission Required</div>
            <div className="text-yellow-300">🔒 Sensitive Access</div>
          </div>
        )}

        <div className="rounded-lg bg-slate-800/50 p-3">
          <div className="mb-1 text-slate-400">Learning Rate</div>
          <div className="font-semibold text-slate-200">
            {Math.round(snapshot.meta.learning_positive_rate * 100)}%
          </div>
        </div>

        <div className="rounded-lg bg-slate-800/50 p-3">
          <div className="mb-1 text-slate-400">Augment Confidence</div>
          <div className="font-semibold text-slate-200">
            {Math.round(snapshot.meta.augment_confidence * 100)}%
          </div>
        </div>
      </div>

      {/* Legend */}
      <div className="mt-4 flex flex-wrap gap-3 text-xs">
        <div className="flex items-center gap-1.5">
          <div
            className="h-3 w-3 rounded-full"
            style={{ backgroundColor: NODE_COLORS.head_coach }}
          />
          <span className="text-slate-400">Core</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div
            className="h-3 w-3 rounded-full"
            style={{ backgroundColor: NODE_COLORS.curiosity_engine }}
          />
          <span className="text-slate-400">Learning/Curiosity</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div
            className="h-3 w-3 rounded-full"
            style={{ backgroundColor: NODE_COLORS.permission }}
          />
          <span className="text-slate-400">Governance</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div
            className="h-3 w-3 rounded-full"
            style={{ backgroundColor: NODE_COLORS.career_coach }}
          />
          <span className="text-slate-400">Specialist Coaches</span>
        </div>
      </div>
    </div>
  );
}
