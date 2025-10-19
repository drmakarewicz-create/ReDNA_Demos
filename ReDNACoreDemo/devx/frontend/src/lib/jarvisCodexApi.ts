/**
 * Jarvis-Codex API Client
 *
 * Phase 2 enhancements:
 * - Auto-review metadata
 * - Multi-file manifests
 * - Atomic apply + rollback
 */

import { CORE_API_BASE } from './env';

const API_BASE = CORE_API_BASE;

// ============================================================================
// Types
// ============================================================================

export type ProposalType = 'text_replace' | 'semantic';

export type AutoReviewStatus = 'pass' | 'fail';
export type GuardrailStatus = 'pass' | 'fail' | 'skipped';

export interface AutoReviewResult {
  status: AutoReviewStatus;
  risk_score: number;
  checks: Record<string, GuardrailStatus>;
  notes: string[];
  recommendation: 'approve' | 'manual_review' | 'reject';
}

export interface ManifestChange {
  file: string;
  operation: string;
  lines_changed: number;
  diff: string;
  diff_stats: {
    added: number;
    removed: number;
    total: number;
  };
  after_path: string;
  checksum_before: string;
  context?: Record<string, any>;
  from_value?: string;
  to_value?: string;
}

export interface ProposalManifest {
  proposal_id: string;
  summary: {
    insertions: number;
    deletions: number;
    files: number;
  };
  changes: ManifestChange[];
  risk_score: number;
  created_at: string;
}

export interface Proposal {
  proposal_id: string;
  scope: string;
  file: string;
  files?: string[];
  intent: string;
  suggested_change: Record<string, any>;
  confidence: number;
  source: string;
  status: 'pending' | 'applied' | 'rejected' | 'rolled_back';
  created_at: string;
  checksum_before?: string;
  patch_file?: string;
  change_type?: ProposalType;
  operations?: Array<Record<string, any>>;
  auto_review?: AutoReviewResult | null;
  risk_score?: number;
  manifest?: ProposalManifest;
  file_manifest?: ManifestChange[];
  backup_bundle?: string;
  applied_at?: string;
  rolled_back_at?: string;
  rejection_reason?: string;
}

export interface ProposalDetail {
  proposal: Proposal;
  diffs: Record<string, string>;
  time_ms?: number;
}

export interface ApplyResult {
  ok: boolean;
  proposal_id: string;
  status: 'applied';
  files?: string[];
  backup_bundle?: string;
  applied_at?: string;
  time_ms: number;
}

export interface RollbackResult {
  ok: boolean;
  proposal_id: string;
  status: 'rolled_back';
  files_restored?: string[];
  backup_paths?: string[];
  rolled_back_at?: string;
  time_ms: number;
}

export interface RejectResult {
  ok: boolean;
  proposal_id: string;
  status: 'rejected';
}

export interface ProposalStats {
  pending: number;
  applied: number;
  rejected: number;
  rolled_back: number;
  total: number;
}

export type ProposalStatus = 'pending' | 'applied' | 'rejected' | 'rolled_back' | 'error';

// ============================================================================
// Helpers
// ============================================================================

function ensureOk(response: Response) {
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }
}

function normaliseProposal(proposal: Proposal): Proposal {
  if (proposal.manifest && !proposal.file_manifest) {
    proposal.file_manifest = proposal.manifest.changes;
  }
  return proposal;
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * List proposals with optional status filter.
 */
export async function listProposals(
  status?: ProposalStatus,
  limit: number = 50
): Promise<Proposal[]> {
  const params = new URLSearchParams();
  if (status && status !== 'error') {
    params.append('status', status);
  }
  params.append('limit', limit.toString());

  const url = `${API_BASE}/jarvis_codex/proposals?${params}`;
  const response = await fetch(url, {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
  });

  ensureOk(response);

  const data = await response.json();
  if (!data.ok) {
    throw new Error(data.error || 'List proposals failed');
  }

  const proposals: Proposal[] = (data.proposals || []).map(normaliseProposal);
  return proposals;
}

/**
 * Fetch a single proposal and its diff map.
 */
export async function getProposal(proposalId: string): Promise<ProposalDetail | null> {
  const url = `${API_BASE}/jarvis_codex/proposals/${proposalId}`;
  const response = await fetch(url, {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
  });

  if (response.status === 404) {
    return null;
  }

  ensureOk(response);

  const data = await response.json();
  if (!data.ok) {
    throw new Error(data.error || 'Get proposal failed');
  }

  const proposal = normaliseProposal(data.proposal as Proposal);
  const diffs = (data.diffs || {}) as Record<string, string>;

  return {
    proposal,
    diffs,
    time_ms: data.time_ms,
  };
}

/**
 * Extract a quick diff preview for legacy UI scenarios.
 */
export function getDiffPreview(proposal: Proposal): string {
  if (proposal.manifest && proposal.manifest.changes.length > 0) {
    return proposal.manifest.changes[0].diff;
  }

  const change = proposal.suggested_change || {};
  if (change.type === 'text_replace') {
    return `--- a/${proposal.file}\n+++ b/${proposal.file}\n@@\n-${change.before}\n+${change.after}`;
  }

  return '';
}

/**
 * Apply a proposal atomically.
 */
export async function applyProposal(
  proposalId: string,
  user: string = 'admin'
): Promise<ApplyResult> {
  const url = `${API_BASE}/jarvis_codex/apply`;
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ proposal_id: proposalId, user }),
  });

  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.detail || body.error || `HTTP ${response.status}`);
  }

  if (!body.ok) {
    throw new Error(body.error || 'Apply failed');
  }

  return body as ApplyResult;
}

/**
 * Rollback a previously applied proposal using backups.
 */
export async function rollbackProposal(
  proposalId: string,
  user: string = 'admin'
): Promise<RollbackResult> {
  const url = `${API_BASE}/jarvis_codex/rollback`;
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ proposal_id: proposalId, user }),
  });

  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.detail || body.error || `HTTP ${response.status}`);
  }

  if (!body.ok) {
    throw new Error(body.error || 'Rollback failed');
  }

  return body as RollbackResult;
}

/**
 * Reject a proposal.
 */
export async function rejectProposal(
  proposalId: string,
  user: string = 'admin',
  reason?: string
): Promise<RejectResult> {
  const url = `${API_BASE}/jarvis_codex/reject`;
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ proposal_id: proposalId, user, reason }),
  });

  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.detail || body.error || `HTTP ${response.status}`);
  }

  if (!body.ok) {
    throw new Error(body.error || 'Reject failed');
  }

  return body as RejectResult;
}

/**
 * Compute proposal statistics (client-side aggregation).
 */
export async function getProposalStats(): Promise<ProposalStats> {
  try {
    const proposals = await listProposals(undefined, 1000);

    const stats: ProposalStats = {
      pending: proposals.filter(p => p.status === 'pending').length,
      applied: proposals.filter(p => p.status === 'applied').length,
      rejected: proposals.filter(p => p.status === 'rejected').length,
      rolled_back: proposals.filter(p => p.status === 'rolled_back').length,
      total: proposals.length,
    };

    return stats;
  } catch (error) {
    console.error('Failed to compute proposal stats:', error);
    return {
      pending: 0,
      applied: 0,
      rejected: 0,
      rolled_back: 0,
      total: 0,
    };
  }
}
