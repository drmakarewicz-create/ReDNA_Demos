/**
 * LLM Benchmark API Client
 *
 * Read-only API client for LLM Benchmark system (Phase 1).
 * Provides access to backlog and reports data from DevX backend.
 */

const DEVX_API_BASE = process.env.NEXT_PUBLIC_DEVX_API_BASE ?? 'http://127.0.0.1:8012';

// ============================================================================
// Types
// ============================================================================

export interface BacklogCase {
  id: string;
  category: string;
  user_message: string;
  expected_trait_ids: string[];
  expected_values?: string[];
  notes?: string;
  risk: 'low' | 'med' | 'high';
  last_precision?: number;
  last_recall?: number;
  last_run_utc?: string;
}

export interface BacklogResponse {
  total: number;
  limit: number;
  offset: number;
  cases: BacklogCase[];
}

export interface ReportMeta {
  filename: string;
  path: string;
  modified: string;
  provider: string | null;
  model?: string | null;
  precision?: number | null;
  recall?: number | null;
  cases_run?: number | null;
  cost_usd?: number | null;
}

export interface ModelStatus {
  provider: string;
  model: string;
  source: string;
}

export interface BatchRun {
  batch_id: string;
  ts: string;
  provider: string;
  model: string;
  cases: number;
  total_cost_usd: number;
  prompt_tokens: number;
  completion_tokens: number;
  errors: number;
}

export interface MonthlyCosts {
  month: string;
  mtd_total_usd: number;
  by_provider: Record<string, number>;
  by_model: Record<string, number>;
  by_batch: Record<string, BatchRun>;
  runs: BatchRun[];
  total_tokens: number;
  total_requests: number;
  error_count: number;
  monthly_cap_usd?: number;
}

export interface HopMetrics {
  count: number;
  p50: number;
  p95: number;
  p99: number;
  mean: number;
}

export interface RoundtripMetrics {
  ok: boolean;
  window_seconds: number;
  ingest: {
    requests: number;
    errors: number;
  };
  hop_ms: {
    preprocess: HopMetrics | null;
    ucnrr: HopMetrics | null;
    resolve: HopMetrics | null;
    total: HopMetrics | null;
  };
  timestamp?: string;
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * Fetch backlog with optional filtering and pagination.
 */
export async function fetchBacklog(params?: {
  category?: string;
  risk?: string;
  limit?: number;
  offset?: number;
}): Promise<BacklogResponse> {
  const query = new URLSearchParams();
  if (params?.category) query.set('category', params.category);
  if (params?.risk) query.set('risk', params.risk);
  if (params?.limit !== undefined) query.set('limit', String(params.limit));
  if (params?.offset !== undefined) query.set('offset', String(params.offset));

  const url = `${DEVX_API_BASE}/devx/api/llm-bench/backlog?${query.toString()}`;
  const response = await fetch(url);

  if (!response.ok) {
    throw new Error(`Failed to fetch backlog: ${response.status} ${response.statusText}`);
  }

  return response.json();
}

/**
 * Fetch list of reports with optional provider filter.
 */
const normaliseReportMeta = (raw: any): ReportMeta | null => {
  if (!raw) return null;

  const filename: string | undefined = raw.filename ?? raw.name ?? raw.file ?? raw.slug;
  if (!filename) return null;

  const path: string =
    raw.path ??
    raw.filepath ??
    raw.full_path ??
    raw.absolute_path ??
    filename;

  const modifiedRaw = raw.modified ?? raw.timestamp ?? raw.mtime ?? raw.updated_at ?? raw.last_modified;
  let modified = '';
  if (modifiedRaw) {
    const date = new Date(modifiedRaw);
    modified = Number.isNaN(date.getTime()) ? String(modifiedRaw) : date.toISOString();
  }

  const provider =
    raw.provider ??
    raw.source ??
    (typeof raw.filename === 'string' && raw.filename.includes('local')
      ? 'ollama'
      : null);

  const toNumber = (value: any): number | null => {
    if (value === null || value === undefined) return null;
    const num = Number(value);
    return Number.isNaN(num) ? null : num;
  };

  return {
    filename,
    path,
    modified,
    provider: provider ?? null,
    model: raw.model ?? null,
    precision: toNumber(raw.precision),
    recall: toNumber(raw.recall),
    cases_run: toNumber(raw.cases ?? raw.cases_run),
    cost_usd: toNumber(raw.cost_usd),
  };
};

export async function fetchReports(params?: { limit?: number }): Promise<ReportMeta[]> {
  const query = new URLSearchParams();
  if (params?.limit !== undefined) query.set('limit', String(params.limit));

  const search = query.toString();
  const url = `${DEVX_API_BASE}/devx/api/llm-bench/reports${search ? `?${search}` : ''}`;
  const response = await fetch(url);

  if (!response.ok) {
    throw new Error(`Failed to fetch reports: ${response.status} ${response.statusText}`);
  }

  const payload = await response.json();

  const list: ReportMeta[] = [];

  if (Array.isArray(payload)) {
    for (const item of payload) {
      const normalised = normaliseReportMeta(item);
      if (normalised) {
        list.push(normalised);
      }
    }
    return list;
  }

  if (payload && Array.isArray(payload.reports)) {
    for (const item of payload.reports) {
      const normalised = normaliseReportMeta(item);
      if (normalised) {
        list.push(normalised);
      }
    }
    return list;
  }

  return list;
}

/**
 * Fetch full markdown content of a specific report.
 */
export async function fetchReportContent(filename: string): Promise<string> {
  const url = `${DEVX_API_BASE}/devx/api/llm-bench/report/${encodeURIComponent(filename)}`;
  const response = await fetch(url);

  if (!response.ok) {
    throw new Error(`Failed to fetch report: ${response.status} ${response.statusText}`);
  }

  return response.text();
}

/**
 * Fetch current model status (provider/model).
 * Optional endpoint - returns fallback if not available.
 */
export async function fetchModelStatus(): Promise<ModelStatus> {
  try {
    const url = `${DEVX_API_BASE}/devx/api/llm-bench/status`;
    const response = await fetch(url);

    if (!response.ok) {
      throw new Error('Status endpoint not available');
    }

    return response.json();
  } catch (error) {
    // Fallback: assume Ollama/llama3.1:8b
    return {
      provider: 'ollama',
      model: 'llama3.1:8b',
      source: 'fallback'
    };
  }
}

// ============================================================================
// Utilities
// ============================================================================

/**
 * Get display label for category.
 */
export function getCategoryLabel(category: string): string {
  const labels: Record<string, string> = {
    direct_fact: 'Direct Fact',
    behavior: 'Behavior',
    indirect_signal: 'Indirect Signal',
    edge_case: 'Edge Case',
    conversational: 'Conversational',
    ambiguous: 'Ambiguous',
    correction: 'Correction'
  };
  return labels[category] ?? category;
}

/**
 * Get color for risk level badge.
 */
export function getRiskColor(risk: string): string {
  const colors: Record<string, string> = {
    low: 'bg-green-100 text-green-800',
    med: 'bg-yellow-100 text-yellow-800',
    high: 'bg-red-100 text-red-800'
  };
  return colors[risk] ?? 'bg-gray-100 text-gray-800';
}

/**
 * Get color for provider badge.
 */
export function getProviderColor(provider?: string | null): string {
  const colors: Record<string, string> = {
    ollama: 'bg-green-100 text-green-800',
    openai: 'bg-orange-100 text-orange-800',
    anthropic: 'bg-purple-100 text-purple-800'
  };
  if (!provider) {
    return 'bg-gray-100 text-gray-800';
  }
  return colors[provider.toLowerCase()] ?? 'bg-gray-100 text-gray-800';
}

/**
 * Format precision/recall as percentage.
 */
export function formatPercent(value?: number): string {
  if (value === undefined || value === null) return '—';
  return `${(value * 100).toFixed(1)}%`;
}

/**
 * Format UTC timestamp as local date.
 */
export function formatDate(utcString?: string): string {
  if (!utcString) return '—';
  try {
    return new Date(utcString).toLocaleDateString();
  } catch {
    return utcString;
  }
}

/**
 * Fetch monthly cost aggregates.
 */
export async function fetchMonthlyCosts(month?: string): Promise<MonthlyCosts> {
  const query = month ? `?month=${encodeURIComponent(month)}` : '';
  const url = `${DEVX_API_BASE}/devx/api/llm-bench/costs${query}`;
  const response = await fetch(url);

  if (!response.ok) {
    throw new Error(`Failed to fetch costs: ${response.status} ${response.statusText}`);
  }

  return response.json();
}

/**
 * Format cost as USD currency.
 */
export function formatCost(cost?: number): string {
  if (cost === undefined || cost === null) return '$0.00';
  return `$${cost.toFixed(4)}`;
}

/**
 * Get meter color based on percentage of cap used.
 */
export function getMeterColor(used: number, cap?: number): string {
  if (!cap) return 'bg-gray-200';

  const percent = (used / cap) * 100;

  if (percent >= 90) return 'bg-red-500';
  if (percent >= 50) return 'bg-yellow-500';
  return 'bg-green-500';
}

// ============================================================================
// Phase 2: Local Execution Functions
// ============================================================================

export interface RunLocalRequest {
  model: string;
  limit: number;
  dry_run: boolean;
}

export interface RunLocalResponse {
  status: string;
  batch_id: string;
  model: string;
  limit: number;
  dry_run: boolean;
  cost_usd: number;
  log_file: string;
  report_path?: string;
}

export interface ProgressResponse {
  status: string;
  log_file?: string;
  lines: string[];
  total_lines?: number;
  message?: string;
}

/**
 * Run local Ollama benchmark.
 */
export async function runLocalBenchmark(params: RunLocalRequest): Promise<RunLocalResponse> {
  const query = new URLSearchParams();
  query.set('model', params.model);
  query.set('limit', String(params.limit));
  query.set('dry_run', String(params.dry_run));

  const url = `${DEVX_API_BASE}/devx/api/llm-bench/run-local?${query.toString()}`;
  const response = await fetch(url, { method: 'POST' });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(errorData.detail || `Failed to run benchmark: ${response.status}`);
  }

  return response.json();
}

/**
 * Get benchmark run progress (latest log tail).
 */
export async function fetchBenchmarkProgress(): Promise<ProgressResponse> {
  const url = `${DEVX_API_BASE}/devx/api/llm-bench/progress`;
  const response = await fetch(url);

  if (!response.ok) {
    throw new Error(`Failed to fetch progress: ${response.status} ${response.statusText}`);
  }

  return response.json();
}

// Phase 3: Guarded Paid Execution Functions
// ============================================================================

export interface CostPrecheckResponse {
  est_cost_usd: number;
  mtd_total_usd: number;
  monthly_cap_usd: number | null;
  remaining_usd: number | null;
  can_run: boolean;
}

export interface RunPaidRequest {
  provider: 'ollama' | 'openai' | 'anthropic';
  model: string;
  limit: number;
  run: boolean;
  allow_paid: boolean;
  ack_paid: string;
  max_cost_usd: number;
  batch_name?: string;
  reason?: string;
}

export interface RunPaidResponse {
  status: string;
  provider: string;
  model: string;
  batch_id: string;
  limit: number;
  cost_usd: number;
  log_file: string;
  report_path?: string;
}

/**
 * Get cost estimate and budget check for a benchmark run.
 */
export async function costPrecheck(
  provider: string,
  model: string,
  limit: number
): Promise<CostPrecheckResponse> {
  const query = new URLSearchParams();
  query.set('provider', provider);
  query.set('model', model);
  query.set('limit', String(limit));

  const url = `${DEVX_API_BASE}/devx/api/llm-bench/cost-precheck?${query.toString()}`;
  const response = await fetch(url);

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(errorData.detail || `Failed to check cost: ${response.status}`);
  }

  return response.json();
}

/**
 * Run paid benchmark with strict safety checks.
 */
export async function runPaidBenchmark(params: RunPaidRequest): Promise<RunPaidResponse> {
  const query = new URLSearchParams();
  query.set('provider', params.provider);
  query.set('model', params.model);
  query.set('limit', String(params.limit));
  query.set('run', String(params.run));
  query.set('allow_paid', String(params.allow_paid));
  if (params.ack_paid) query.set('ack_paid', params.ack_paid);
  query.set('max_cost_usd', String(params.max_cost_usd));
  if (params.batch_name) query.set('batch_name', params.batch_name);
  if (params.reason) query.set('reason', params.reason);

  const url = `${DEVX_API_BASE}/devx/api/llm-bench/run?${query.toString()}`;
  const response = await fetch(url, { method: 'POST' });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(errorData.detail || `Failed to run benchmark: ${response.status}`);
  }

  return response.json();
}

/**
 * Fetch roundtrip metrics (hop timing breakdown).
 */
export async function fetchRoundtripMetrics(): Promise<RoundtripMetrics> {
  const url = `${DEVX_API_BASE}/devx/api/metrics/roundtrip`;
  const response = await fetch(url);

  if (!response.ok) {
    throw new Error(`Failed to fetch roundtrip metrics: ${response.status} ${response.statusText}`);
  }

  return response.json();
}
