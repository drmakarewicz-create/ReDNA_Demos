'use client';

import { useState, useEffect } from 'react';
import { CORE_API_BASE } from '../../lib/api';

interface ChorusSection {
  text: string;
  hash: string;
}

interface ChorusData {
  head_coach: ChorusSection;
  augment: ChorusSection & { label: string };
  runtime: {
    json: Record<string, any>;
    hash: string;
  };
  merged: ChorusSection;
  context_version: number;
  active_coach_id: string;
}

interface ChorusPreviewProps {
  userId: string;
  autoRefresh?: boolean;
  refreshInterval?: number;
}

type ViewMode = 'split' | 'merged';
type SectionType = 'head_coach' | 'augment' | 'runtime';

export function ChorusPreview({
  userId,
  autoRefresh = false,
  refreshInterval = 5000,
}: ChorusPreviewProps) {
  const [chorus, setChorus] = useState<ChorusData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>('split');
  const [expandedSection, setExpandedSection] = useState<SectionType | null>(null);
  const [copiedHash, setCopiedHash] = useState<string | null>(null);

  const fetchChorus = async () => {
    try {
      const response = await fetch(`${CORE_API_BASE}/coach/chorus?user_id=${userId}`);
      const json = await response.json();

      if (json.ok) {
        setChorus(json);
        setError(null);
      } else {
        setError(json.detail || 'Failed to load chorus');
      }
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchChorus();

    if (autoRefresh) {
      const interval = setInterval(fetchChorus, refreshInterval);
      return () => clearInterval(interval);
    }
  }, [userId, autoRefresh, refreshInterval]);

  const copyToClipboard = (text: string, hash: string) => {
    navigator.clipboard.writeText(text);
    setCopiedHash(hash);
    setTimeout(() => setCopiedHash(null), 2000);
  };

  const exportMerged = () => {
    if (!chorus) return;

    const blob = new Blob([chorus.merged.text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `chorus_${userId}_v${chorus.context_version}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (loading) {
    return (
      <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6">
        <h2 className="mb-4 text-lg font-semibold text-slate-200">
          Live Chorus Preview
        </h2>
        <div className="flex h-96 items-center justify-center">
          <div className="text-slate-500">Loading chorus...</div>
        </div>
      </div>
    );
  }

  if (error || !chorus) {
    return (
      <div className="rounded-2xl border border-red-800/30 bg-red-950/20 p-6">
        <h2 className="mb-4 text-lg font-semibold text-red-400">
          Live Chorus Preview
        </h2>
        <div className="text-red-300">{error || 'No chorus available'}</div>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6">
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-200">
          Live Chorus Preview
        </h2>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setViewMode(viewMode === 'split' ? 'merged' : 'split')}
            className="rounded-lg bg-slate-800 px-3 py-1.5 text-xs font-medium text-slate-300 hover:bg-slate-700"
          >
            {viewMode === 'split' ? 'Show Merged' : 'Show Split'}
          </button>
          <button
            onClick={exportMerged}
            className="rounded-lg bg-blue-900/50 px-3 py-1.5 text-xs font-medium text-blue-300 hover:bg-blue-800/50"
          >
            Export
          </button>
        </div>
      </div>

      {/* Context Info */}
      <div className="mb-4 flex items-center gap-3 text-xs text-slate-400">
        <div>Version: <span className="font-mono text-slate-300">v{chorus.context_version}</span></div>
        <div>•</div>
        <div>Coach: <span className="font-semibold text-slate-300">{chorus.active_coach_id}</span></div>
        <div>•</div>
        <div>Label: <span className="text-slate-300">{chorus.augment.label}</span></div>
      </div>

      {/* View Mode: Split */}
      {viewMode === 'split' && (
        <div className="space-y-3">
          {/* Head Coach Section */}
          <div className="rounded-lg border border-blue-800/30 bg-blue-950/20 p-4">
            <div className="mb-2 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-blue-400" />
                <h3 className="text-sm font-semibold text-blue-300">Head Coach Mandate</h3>
              </div>
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs text-slate-500">
                  {chorus.head_coach.hash}
                </span>
                <button
                  onClick={() => copyToClipboard(chorus.head_coach.text, chorus.head_coach.hash)}
                  className="text-xs text-blue-400 hover:text-blue-300"
                >
                  {copiedHash === chorus.head_coach.hash ? '✓ Copied' : 'Copy'}
                </button>
              </div>
            </div>
            <div
              className={`overflow-hidden font-mono text-xs text-slate-300 transition-all ${
                expandedSection === 'head_coach' ? 'max-h-none' : 'max-h-24'
              }`}
            >
              <pre className="whitespace-pre-wrap">{chorus.head_coach.text}</pre>
            </div>
            <button
              onClick={() =>
                setExpandedSection(expandedSection === 'head_coach' ? null : 'head_coach')
              }
              className="mt-2 text-xs text-blue-400 hover:text-blue-300"
            >
              {expandedSection === 'head_coach' ? 'Collapse' : 'Expand'}
            </button>
          </div>

          {/* Augmentation Section */}
          {chorus.augment.text && (
            <div className="rounded-lg border border-purple-800/30 bg-purple-950/20 p-4">
              <div className="mb-2 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="h-2 w-2 rounded-full bg-purple-400" />
                  <h3 className="text-sm font-semibold text-purple-300">
                    Augmentation: {chorus.augment.label}
                  </h3>
                </div>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs text-slate-500">
                    {chorus.augment.hash}
                  </span>
                  <button
                    onClick={() => copyToClipboard(chorus.augment.text, chorus.augment.hash)}
                    className="text-xs text-purple-400 hover:text-purple-300"
                  >
                    {copiedHash === chorus.augment.hash ? '✓ Copied' : 'Copy'}
                  </button>
                </div>
              </div>
              <div
                className={`overflow-hidden font-mono text-xs text-slate-300 transition-all ${
                  expandedSection === 'augment' ? 'max-h-none' : 'max-h-24'
                }`}
              >
                <pre className="whitespace-pre-wrap">{chorus.augment.text}</pre>
              </div>
              <button
                onClick={() =>
                  setExpandedSection(expandedSection === 'augment' ? null : 'augment')
                }
                className="mt-2 text-xs text-purple-400 hover:text-purple-300"
              >
                {expandedSection === 'augment' ? 'Collapse' : 'Expand'}
              </button>
            </div>
          )}

          {/* Runtime Context Section */}
          <div className="rounded-lg border border-yellow-800/30 bg-yellow-950/20 p-4">
            <div className="mb-2 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-yellow-400" />
                <h3 className="text-sm font-semibold text-yellow-300">Runtime Behavior Context</h3>
              </div>
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs text-slate-500">
                  {chorus.runtime.hash}
                </span>
                <button
                  onClick={() =>
                    copyToClipboard(JSON.stringify(chorus.runtime.json, null, 2), chorus.runtime.hash)
                  }
                  className="text-xs text-yellow-400 hover:text-yellow-300"
                >
                  {copiedHash === chorus.runtime.hash ? '✓ Copied' : 'Copy'}
                </button>
              </div>
            </div>
            <div
              className={`overflow-hidden font-mono text-xs text-slate-300 transition-all ${
                expandedSection === 'runtime' ? 'max-h-none' : 'max-h-24'
              }`}
            >
              <pre className="whitespace-pre-wrap">
                {JSON.stringify(chorus.runtime.json, null, 2)}
              </pre>
            </div>
            <button
              onClick={() =>
                setExpandedSection(expandedSection === 'runtime' ? null : 'runtime')
              }
              className="mt-2 text-xs text-yellow-400 hover:text-yellow-300"
            >
              {expandedSection === 'runtime' ? 'Collapse' : 'Expand'}
            </button>
          </div>
        </div>
      )}

      {/* View Mode: Merged */}
      {viewMode === 'merged' && (
        <div className="rounded-lg border border-slate-700 bg-slate-950/50 p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-300">Merged Prompt</h3>
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs text-slate-500">
                {chorus.merged.hash}
              </span>
              <button
                onClick={() => copyToClipboard(chorus.merged.text, chorus.merged.hash)}
                className="text-xs text-slate-400 hover:text-slate-300"
              >
                {copiedHash === chorus.merged.hash ? '✓ Copied' : 'Copy'}
              </button>
            </div>
          </div>
          <div className="max-h-[600px] overflow-y-auto font-mono text-xs text-slate-300">
            <pre className="whitespace-pre-wrap">{chorus.merged.text}</pre>
          </div>
        </div>
      )}

      {/* Stats Footer */}
      <div className="mt-4 flex gap-4 text-xs text-slate-400">
        <div>
          Head Coach: <span className="font-semibold text-slate-300">{chorus.head_coach.text.length}</span> chars
        </div>
        <div>•</div>
        <div>
          Augment: <span className="font-semibold text-slate-300">{chorus.augment.text.length}</span> chars
        </div>
        <div>•</div>
        <div>
          Merged: <span className="font-semibold text-slate-300">{chorus.merged.text.length}</span> chars
        </div>
      </div>
    </div>
  );
}
