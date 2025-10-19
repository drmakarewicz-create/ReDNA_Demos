import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { toast } from 'react-toastify';
import {
  applyProposal,
  getProposal,
  getProposalStats,
  listProposals,
  rejectProposal,
  rollbackProposal,
  Proposal,
  ProposalDetail,
  ProposalStats,
  ProposalStatus,
  ProposalManifest,
  ProposalType,
  AutoReviewResult,
} from '../../lib/jarvisCodexApi';

type GuardrailStatus = 'pass' | 'fail' | 'warn' | 'skipped';

type FilterStatus = 'all' | ProposalStatus;

const EMPTY_STATS: ProposalStats = {
  pending: 0,
  applied: 0,
  rejected: 0,
  rolled_back: 0,
  total: 0,
};

// ============================================================================
// Utility helpers
// ============================================================================

function formatDate(value?: string): string {
  if (!value) return '—';
  return new Date(value).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function formatRiskPercent(score?: number): string {
  if (score == null) return '—';
  return `${Math.round(score * 100)}%`;
}

function guardrailLabel(name: string): string {
  return name
    .replace(/_/g, ' ')
    .replace(/\b\w/g, char => char.toUpperCase());
}

// ============================================================================
// Main Component
// ============================================================================

export default function JarvisCodexPanel() {
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [stats, setStats] = useState<ProposalStats>(EMPTY_STATS);
  const [filter, setFilter] = useState<FilterStatus>('all');
  const [loading, setLoading] = useState<boolean>(true);
  const [actionLoading, setActionLoading] = useState<boolean>(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedDetail, setSelectedDetail] = useState<ProposalDetail | null>(null);
  const detailsCache = useRef<Map<string, ProposalDetail>>(new Map());

  const loadProposals = useCallback(async () => {
    setLoading(true);
    try {
      const statusFilter = filter === 'all' ? undefined : filter;
      const data = await listProposals(statusFilter);
      setProposals(data);

      const statsData = await getProposalStats();
      setStats(statsData);

      if (data.length > 0) {
        const existing = data.find(p => p.proposal_id === selectedId);
        if (!existing) {
          setSelectedId(data[0].proposal_id);
        }
      } else {
        setSelectedId(null);
        setSelectedDetail(null);
      }
    } catch (error) {
      console.error('Failed to load proposals:', error);
      toast.error('Failed to load proposals');
    } finally {
      setLoading(false);
    }
  }, [filter, selectedId]);

  useEffect(() => {
    loadProposals();
  }, [loadProposals]);

  const loadProposalDetail = useCallback(
    async (proposalId: string) => {
      if (detailsCache.current.has(proposalId)) {
        const cached = detailsCache.current.get(proposalId)!;
        setSelectedDetail(cached);
        return;
      }

      try {
        const detail = await getProposal(proposalId);
        if (detail) {
          detailsCache.current.set(proposalId, detail);
          setSelectedDetail(detail);
        }
      } catch (error) {
        console.error('Failed to load proposal detail:', error);
        toast.error('Failed to load proposal detail');
      }
    },
    []
  );

  useEffect(() => {
    if (selectedId) {
      loadProposalDetail(selectedId);
    } else {
      setSelectedDetail(null);
    }
  }, [selectedId, loadProposalDetail]);

  const handleApprove = useCallback(async () => {
    if (!selectedId) return;

    try {
      setActionLoading(true);
      const result = await applyProposal(selectedId);
      toast.success(
        <div>
          <div className="font-semibold">✓ Proposal Applied</div>
          {result.files && result.files.length > 0 && (
            <div className="text-sm mt-1">
              Files: {result.files.join(', ')}
            </div>
          )}
          {result.backup_bundle && (
            <div className="text-xs mt-1 text-gray-500">
              Backup: {result.backup_bundle}
            </div>
          )}
        </div>
      );

      detailsCache.current.delete(selectedId);
      await loadProposals();
      await loadProposalDetail(selectedId);
    } catch (error: any) {
      toast.error(`Failed to apply: ${error.message || error}`);
    } finally {
      setActionLoading(false);
    }
  }, [loadProposalDetail, loadProposals, selectedId]);

  const handleReject = useCallback(async () => {
    if (!selectedId) return;
    const reason = prompt('Rejection reason (optional):');
    if (reason === null) return;

    try {
      setActionLoading(true);
      await rejectProposal(selectedId, 'admin', reason || undefined);
      toast.info('Proposal rejected');

      detailsCache.current.delete(selectedId);
      await loadProposals();
      await loadProposalDetail(selectedId);
    } catch (error: any) {
      toast.error(`Failed to reject: ${error.message || error}`);
    } finally {
      setActionLoading(false);
    }
  }, [loadProposalDetail, loadProposals, selectedId]);

  const handleRollback = useCallback(async () => {
    if (!selectedId) return;
    const confirmRollback = window.confirm(
      'Rollback this proposal? This will restore backup files.'
    );
    if (!confirmRollback) return;

    try {
      setActionLoading(true);
      const result = await rollbackProposal(selectedId);
      toast.success(
        `✓ Rolled back: ${(result.files_restored || []).length} file(s) restored`
      );

      detailsCache.current.delete(selectedId);
      await loadProposals();
      await loadProposalDetail(selectedId);
    } catch (error: any) {
      toast.error(`Rollback failed: ${error.message || error}`);
    } finally {
      setActionLoading(false);
    }
  }, [loadProposalDetail, loadProposals, selectedId]);

  const filters: Array<{ value: FilterStatus; label: string }> = useMemo(
    () => [
      { value: 'all', label: 'All' },
      { value: 'pending', label: 'Pending' },
      { value: 'applied', label: 'Applied' },
      { value: 'rolled_back', label: 'Rolled Back' },
      { value: 'rejected', label: 'Rejected' },
    ],
    []
  );

  const selectedProposal = useMemo(() => {
    if (!selectedDetail) return null;
    return selectedDetail.proposal;
  }, [selectedDetail]);

  const manifest = selectedProposal?.manifest;
  const diffs = selectedDetail?.diffs ?? {};

  return (
    <div className="flex flex-col h-full bg-gray-50">
      <Header stats={stats} onRefresh={loadProposals} loading={loading} />

      <div className="flex flex-1 overflow-hidden">
        <Sidebar
          proposals={proposals}
          selectedId={selectedId}
          filter={filter}
          filters={filters}
          loading={loading}
          onFilterChange={setFilter}
          onSelect={proposal => {
            setSelectedId(proposal.proposal_id);
          }}
        />

        <MainPane
          proposal={selectedProposal}
          manifest={manifest}
          diffs={diffs}
          actionLoading={actionLoading}
          onApprove={handleApprove}
          onReject={handleReject}
          onRollback={handleRollback}
        />
      </div>
    </div>
  );
}

// ============================================================================
// Header
// ============================================================================

interface HeaderProps {
  stats: ProposalStats;
  onRefresh: () => void;
  loading: boolean;
}

function Header({ stats, onRefresh, loading }: HeaderProps) {
  const summaryChips = [
    { label: 'Pending', value: stats.pending, color: 'bg-amber-100 text-amber-700' },
    { label: 'Applied', value: stats.applied, color: 'bg-emerald-100 text-emerald-700' },
    { label: 'Rolled Back', value: stats.rolled_back, color: 'bg-blue-100 text-blue-700' },
    { label: 'Rejected', value: stats.rejected, color: 'bg-gray-100 text-gray-700' },
  ];

  return (
    <div className="bg-white border-b border-gray-200 px-6 py-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h1 className="text-2xl font-bold text-gray-900">Jarvis-Codex Control Panel</h1>
          <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-red-100 text-red-700">
            <span className="w-2 h-2 bg-red-600 rounded-full mr-2" />
            Guarded Mode
          </span>
        </div>

        <div className="flex items-center gap-3">
          {summaryChips.map(chip => (
            <span
              key={chip.label}
              className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${chip.color}`}
            >
              {chip.label}: {chip.value}
            </span>
          ))}
          <button
            onClick={onRefresh}
            disabled={loading}
            className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50"
          >
            <svg
              className={`-ml-1 mr-2 h-5 w-5 text-gray-500 ${loading ? 'animate-spin' : ''}`}
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 20 20"
              fill="currentColor"
            >
              <path
                fillRule="evenodd"
                d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z"
                clipRule="evenodd"
              />
            </svg>
            Refresh
          </button>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Sidebar
// ============================================================================

interface SidebarProps {
  proposals: Proposal[];
  selectedId: string | null;
  filter: FilterStatus;
  filters: Array<{ value: FilterStatus; label: string }>;
  loading: boolean;
  onFilterChange: (filter: FilterStatus) => void;
  onSelect: (proposal: Proposal) => void;
}

function Sidebar({
  proposals,
  selectedId,
  filter,
  filters,
  loading,
  onFilterChange,
  onSelect,
}: SidebarProps) {
  return (
    <div className="w-80 bg-white border-r border-gray-200 flex flex-col">
      <div className="p-4 border-b border-gray-200">
        <div className="flex flex-wrap gap-2">
          {filters.map(f => (
            <button
              key={f.value}
              onClick={() => onFilterChange(f.value)}
              className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${
                filter === f.value
                  ? 'bg-indigo-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="p-4 text-center text-gray-500">Loading...</div>
        ) : proposals.length === 0 ? (
          <div className="p-4 text-center text-gray-500">No proposals found</div>
        ) : (
          proposals.map(proposal => (
            <ProposalItem
              key={proposal.proposal_id}
              proposal={proposal}
              selected={selectedId === proposal.proposal_id}
              onClick={() => onSelect(proposal)}
            />
          ))
        )}
      </div>
    </div>
  );
}

interface ProposalItemProps {
  proposal: Proposal;
  selected: boolean;
  onClick: () => void;
}

function ProposalItem({ proposal, selected, onClick }: ProposalItemProps) {
  const statusColors: Record<Proposal['status'], string> = {
    pending: 'bg-amber-100 text-amber-700',
    applied: 'bg-emerald-100 text-emerald-700',
    rejected: 'bg-gray-200 text-gray-700',
    rolled_back: 'bg-blue-100 text-blue-700',
  };

  const risk = proposal.risk_score ?? proposal.manifest?.risk_score ?? 0;

  return (
    <div
      onClick={onClick}
      className={`p-4 border-b border-gray-200 cursor-pointer transition-colors ${
        selected ? 'bg-indigo-50 border-indigo-200' : 'hover:bg-gray-50'
      }`}
    >
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2 text-sm font-medium text-gray-900 truncate">
          {proposal.file.split('/').pop()}
          <ProposalTypePill type={(proposal.change_type as ProposalType) || 'text_replace'} />
        </div>
        <span className={`ml-2 px-2 py-0.5 rounded text-xs font-medium ${statusColors[proposal.status]}`}>
          {proposal.status.replace('_', ' ')}
        </span>
      </div>

      <div className="text-sm text-gray-600 mb-2 line-clamp-2">{proposal.intent}</div>

      <div className="flex items-center justify-between text-xs text-gray-500">
        <span>Risk: {formatRiskPercent(risk)}</span>
        <span>{formatDate(proposal.created_at)}</span>
      </div>
    </div>
  );
}

// ============================================================================
// Main Pane
// ============================================================================

interface MainPaneProps {
  proposal: Proposal | null;
  manifest?: ProposalManifest;
  diffs: Record<string, string>;
  actionLoading: boolean;
  onApprove: () => void;
  onReject: () => void;
  onRollback: () => void;
}

function MainPane({
  proposal,
  manifest,
  diffs,
  actionLoading,
  onApprove,
  onReject,
  onRollback,
}: MainPaneProps) {
  if (!proposal) {
    return (
      <div className="flex-1 flex items-center justify-center text-gray-500">
        Select a proposal to view details
      </div>
    );
  }

  const autoReview = proposal.auto_review || null;
  const canApprove = proposal.status === 'pending';
  const canRollback = proposal.status === 'applied';

  const operationsCount = proposal.operations?.length ?? manifest?.changes.length ?? 0;
  const guardrailSummary = manifest
    ? {
        files: manifest.summary.files,
        lines: manifest.summary.insertions + manifest.summary.deletions,
        operations: operationsCount,
      }
    : null;

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="bg-white border-b border-gray-200 p-4 space-y-4">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-3">
              <h2 className="text-lg font-semibold text-gray-900">{proposal.file}</h2>
              <ProposalTypePill type={(proposal.change_type as ProposalType) || 'text_replace'} />
              {autoReview && <AutoReviewChip autoReview={autoReview} />}
            </div>
            <p className="text-sm text-gray-600">{proposal.intent}</p>
          </div>

          <div className="flex gap-2">
            {canApprove && (
              <>
                <button
                  onClick={onApprove}
                  disabled={actionLoading}
                  className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-emerald-600 hover:bg-emerald-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-emerald-500 disabled:opacity-50"
                >
                  ✓ Approve
                </button>
                <button
                  onClick={onReject}
                  disabled={actionLoading}
                  className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50"
                >
                  ✗ Reject
                </button>
              </>
            )}
            {canRollback && (
              <RollbackButton
                proposalId={proposal.proposal_id}
                loading={actionLoading}
                onRollback={onRollback}
              />
            )}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4 text-sm text-gray-600">
          <div>
            <span className="text-gray-500">Source:</span>{' '}
            <span className="font-medium">{proposal.source}</span>
          </div>
          <div>
            <span className="text-gray-500">Confidence:</span>{' '}
            <span className="font-medium">{Math.round(proposal.confidence * 100)}%</span>
          </div>
          <div>
            <span className="text-gray-500">Created:</span>{' '}
            <span className="font-medium">{formatDate(proposal.created_at)}</span>
          </div>
          <div>
            <span className="text-gray-500">Status:</span>{' '}
            <span className="font-medium capitalize">{proposal.status.replace('_', ' ')}</span>
          </div>
          {proposal.applied_at && (
            <div>
              <span className="text-gray-500">Applied:</span>{' '}
              <span className="font-medium">{formatDate(proposal.applied_at)}</span>
            </div>
          )}
          {proposal.rolled_back_at && (
            <div>
              <span className="text-gray-500">Rolled Back:</span>{' '}
              <span className="font-medium">{formatDate(proposal.rolled_back_at)}</span>
            </div>
          )}
        </div>

        {guardrailSummary && (
          <GuardrailsBadge
            files={guardrailSummary.files}
            lines={guardrailSummary.lines}
            operations={guardrailSummary.operations}
          />
        )}

        {autoReview && (
          <AutoReviewPanel
            autoReview={autoReview}
            manifest={manifest}
          />
        )}
      </div>

      <div className="flex-1 overflow-auto bg-gray-900">
        <MultiFileViewer manifest={manifest} diffs={diffs} />
      </div>
    </div>
  );
}

// ============================================================================
// Auto-Review Panel
// ============================================================================

interface AutoReviewPanelProps {
  autoReview: AutoReviewResult;
  manifest?: ProposalManifest;
}

function AutoReviewPanel({ autoReview, manifest }: AutoReviewPanelProps) {
  const notes = autoReview.notes || [];
  const summary = manifest?.summary;

  return (
    <div className="border border-gray-200 rounded-md p-4 bg-gray-50">
      <div className="flex items-center justify-between mb-3">
        <div className="text-sm font-semibold text-gray-700">Auto-Review Guardrails</div>
        <div className="text-sm text-gray-500">
          Recommendation: <span className="font-semibold">{autoReview.recommendation}</span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div>
          <div className="text-xs uppercase text-gray-400 mb-1">Risk Score</div>
          <div className="text-lg font-semibold text-gray-800">
            {formatRiskPercent(autoReview.risk_score)}
          </div>
          {summary && (
            <div className="text-xs text-gray-500 mt-1">
              Files: {summary.files} • Lines: {summary.insertions + summary.deletions}
            </div>
          )}
        </div>

        <div className="md:col-span-2">
          <div className="text-xs uppercase text-gray-400 mb-1">Guardrails</div>
          <GuardrailsChecklist checks={autoReview.checks} />
        </div>
      </div>

      {notes.length > 0 && (
        <div className="mt-3 text-xs text-gray-500 space-y-1">
          {notes.map((note, idx) => (
            <div key={idx}>• {note}</div>
          ))}
        </div>
      )}
    </div>
  );
}

interface GuardrailsChecklistProps {
  checks: Record<string, GuardrailStatus>;
}

function GuardrailsChecklist({ checks }: GuardrailsChecklistProps) {
  const statusColor: Record<GuardrailStatus, string> = {
    pass: 'text-emerald-600',
    fail: 'text-red-600',
    warn: 'text-amber-600',
    skipped: 'text-gray-400',
  };

  const statusIcon: Record<GuardrailStatus, string> = {
    pass: '✓',
    fail: '✗',
    warn: '⚠',
    skipped: '○',
  };

  return (
    <div className="space-y-1 text-sm">
      {Object.entries(checks).map(([name, status]) => (
        <div key={name} className="flex items-center gap-2">
          <span className={`font-semibold ${statusColor[status]}`}>{statusIcon[status]}</span>
          <span className="text-gray-600">{guardrailLabel(name)}</span>
        </div>
      ))}
    </div>
  );
}

// ============================================================================
// Guardrails Badge
// ============================================================================

interface GuardrailsBadgeProps {
  files: number;
  lines: number;
  operations: number;
}

function GuardrailsBadge({ files, lines, operations }: GuardrailsBadgeProps) {
  return (
    <div className="inline-flex items-center gap-3 bg-indigo-50 text-indigo-700 px-3 py-2 rounded-md text-xs font-medium">
      <span>Guardrails</span>
      <span className="flex items-center gap-1">
        📁 <strong>{files}</strong> files
      </span>
      <span className="flex items-center gap-1">
        ✏️ <strong>{lines}</strong> lines
      </span>
      <span className="flex items-center gap-1">
        ⚙️ <strong>{operations}</strong> ops
      </span>
    </div>
  );
}

// ============================================================================
// Multi-file Viewer
// ============================================================================

interface MultiFileViewerProps {
  manifest?: ProposalManifest;
  diffs: Record<string, string>;
}

function MultiFileViewer({ manifest, diffs }: MultiFileViewerProps) {
  const [selectedIndex, setSelectedIndex] = useState<number>(0);

  useEffect(() => {
    setSelectedIndex(0);
  }, [manifest?.proposal_id]);

  if (!manifest || manifest.changes.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-sm text-gray-400">
        Diff preview unavailable
      </div>
    );
  }

  const changes = manifest.changes;
  const selectedChange = changes[selectedIndex] || changes[0];
  const diffText = diffs[selectedChange.file] || selectedChange.diff || '';

  return (
    <div className="h-full grid grid-cols-[220px_1fr]">
      <div className="border-r border-gray-800 bg-gray-950/40 p-4 space-y-2">
        <div className="text-xs font-semibold text-gray-400 uppercase tracking-wide">
          Files ({changes.length})
        </div>
        {changes.map((change, idx) => (
          <button
            key={change.file}
            onClick={() => setSelectedIndex(idx)}
            className={`w-full text-left px-3 py-2 rounded-md text-sm transition-colors ${
              idx === selectedIndex
                ? 'bg-indigo-500/20 text-indigo-100 border border-indigo-500/50'
                : 'text-gray-300 hover:bg-gray-800/60'
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="truncate">{change.file.split('/').pop()}</span>
              <span className="text-xs text-gray-400 ml-2">
                ±{change.diff_stats?.total ?? change.lines_changed}
              </span>
            </div>
            <div className="text-2xs uppercase text-gray-500 mt-1">
              {change.operation.replace('_', ' ')}
            </div>
          </button>
        ))}
      </div>

      <div className="overflow-auto p-4">
        <DiffViewer diff={diffText} />
      </div>
    </div>
  );
}

interface DiffViewerProps {
  diff: string;
}

function DiffViewer({ diff }: DiffViewerProps) {
  if (!diff) {
    return (
      <div className="text-sm text-gray-400">No diff available for this file.</div>
    );
  }

  const lines = diff.split('\n');

  return (
    <pre className="text-xs md:text-sm text-gray-200 font-mono whitespace-pre-wrap">
      {lines.map((line, idx) => {
        let className = '';
        if (line.startsWith('+') && !line.startsWith('+++')) {
          className = 'text-emerald-400';
        } else if (line.startsWith('-') && !line.startsWith('---')) {
          className = 'text-rose-400';
        } else if (line.startsWith('@@')) {
          className = 'text-sky-300';
        } else {
          className = 'text-gray-200';
        }
        return (
          <div key={idx} className={className}>
            {line}
          </div>
        );
      })}
    </pre>
  );
}

// ============================================================================
// Supporting components
// ============================================================================

interface ProposalTypePillProps {
  type: ProposalType;
}

function ProposalTypePill({ type }: ProposalTypePillProps) {
  const styles: Record<ProposalType, string> = {
    text_replace: 'bg-blue-100 text-blue-700',
    semantic: 'bg-purple-100 text-purple-700',
  };

  const label = type === 'semantic' ? '🔧 Semantic' : '📝 Text';

  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${styles[type]}`}>
      {label}
    </span>
  );
}

interface AutoReviewChipProps {
  autoReview: AutoReviewResult;
}

function AutoReviewChip({ autoReview }: AutoReviewChipProps) {
  const statusClass =
    autoReview.status === 'pass'
      ? 'bg-emerald-100 text-emerald-700'
      : 'bg-rose-100 text-rose-700';

  const risk = autoReview.risk_score ?? 0;
  const riskClass =
    risk < 0.3 ? 'text-emerald-500' : risk < 0.6 ? 'text-amber-500' : 'text-rose-500';

  return (
    <div className="flex items-center gap-2">
      <span className={`px-2 py-0.5 rounded text-xs font-medium ${statusClass}`}>
        {autoReview.status === 'pass' ? '✓ Auto-Review' : '✗ Auto-Review'}
      </span>
      <span className={`text-xs font-medium ${riskClass}`}>
        Risk: {formatRiskPercent(autoReview.risk_score)}
      </span>
    </div>
  );
}

interface RollbackButtonProps {
  proposalId: string;
  loading: boolean;
  onRollback: () => void;
}

function RollbackButton({ proposalId, loading, onRollback }: RollbackButtonProps) {
  return (
    <button
      onClick={onRollback}
      disabled={loading}
      className="inline-flex items-center px-3 py-2 bg-amber-500 text-white rounded-md hover:bg-amber-600 disabled:opacity-50"
      title={`Rollback proposal ${proposalId}`}
    >
      {loading ? 'Rolling back…' : '↺ Rollback'}
    </button>
  );
}
