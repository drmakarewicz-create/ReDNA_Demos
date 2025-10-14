import { writeCache } from './offline-cache';

export const CORE_API_BASE = process.env.NEXT_PUBLIC_CORE_API_BASE ?? 'http://127.0.0.1:8015';

export interface PersonaRosterEntry {
  key: string;
  label: string;
  icon: string;
  enabled: boolean;
  accent_color?: string | null;
}

export interface AskActionPolicy {
  allowed: boolean;
  reason: string | null;
}

export interface PlannerAskPolicy {
  approve: AskActionPolicy;
  snooze: AskActionPolicy;
  skip: AskActionPolicy;
}

export type AskListStatus = 'all' | 'open' | 'done';

export interface CoachPane {
  title: string;
  type: 'switch' | 'slider' | 'text' | 'select' | 'meter';
  path: string;
  options?: Array<{ label: string; value: any }>;
  min?: number;
  max?: number;
  step?: number;
  placeholder?: string;
}

export interface FetchAsksOptions {
  status?: AskListStatus;
  limit?: number;
  sort?: 'new' | 'old';
}

export interface PlannerAsk {
  id: string;
  container: string;
  gap: string;
  confidence: number;
  ask_type: string;
  phrasing_stub: string;
  sensitivity: boolean;
  created_at: string;
  expires_at: string;
  next_available_at: string;
  ttl_minutes: number;
  snooze_minutes: number;
  metadata?: Record<string, unknown>;
  status?: string;
  policy?: PlannerAskPolicy;
  default_snooze_minutes?: number;
}

export interface ObservationDistribution {
  latest: string | null;
  distribution: Record<string, number>;
}

export interface ObservationCadenceSummary {
  latest_bucket: string | null;
  histogram: Record<string, number>;
}

export interface ObservationLatencySummary {
  median_ms: number | null;
  mean_ms: number | null;
  histogram: Record<string, number>;
}

export interface ObservationPersonaBreakdown {
  observation_count: number;
  dialog_acts: ObservationDistribution;
}

export interface ObservationWindowMetrics {
  observation_count: number;
  dialog_acts: ObservationDistribution;
  cadence: ObservationCadenceSummary;
  latency: ObservationLatencySummary;
  per_persona?: Record<string, ObservationPersonaBreakdown>;
}

export interface ObservationAggregates extends ObservationWindowMetrics {
  user_id: string;
  windows?: Record<string, ObservationWindowMetrics>;
}

export interface ChatProviderSettings {
  model?: string;
  temperature?: number;
  maxTokens?: number;
}

export interface ChatSendResponse {
  message_id: string;
  persona: string;
  text: string;
  ts: number;
  provider?: string;
  provider_settings?: ChatProviderSettings;
}

export interface PreferenceSubmitResponse {
  ok: boolean;
  user_id: string;
  key: string;
  set_at: string;
  ttl_days: number;
}

export interface UserSummary {
  id: string;
  label: string;
  created_ts: string;
  last_used_ts?: string | null;
  last_modified_ts?: string | null;
}

export interface UserMediaItem {
  id: string;
  filename: string;
  original_name: string;
  content_type: string | null;
  size: number | null;
  uploaded_ts: string | null;
  label?: string | null;
  download_url?: string | null;
  metadata?: Record<string, unknown> | null;
}

export type PhotoRenderJobState = 'queued' | 'running' | 'done' | 'error';

export interface PhotoRenderJob {
  id: string;
  user_id: string;
  media_id: string;
  state: PhotoRenderJobState;
  progress: number | null;
  created_at: string | null;
  updated_at: string | null;
  error: string | null;
  result_id: string | null;
  result_filename: string | null;
  result_content_type: string | null;
  status_url: string | null;
  result_url: string | null;
  params: Record<string, unknown>;
}

export interface PhotoExtractedTrait {
  trait: string;
  value: string;
  ucn: number;
  rr?: number;
  rr_band?: string;
  curiosity?: number;
}

export interface PhotoExtractFix {
  trait_id: string;
  value: string;
  ucn: number;
  rr: number;
  curiosity: number;
  rr_band: string;
  fix_text: string;
}

export interface PhotoExtractSummary {
  top_fix_1?: string;
  top_fix_2?: string;
  top_fix_3?: string;
}

export interface PhotoExtractResult {
  traits: PhotoExtractedTrait[];
  summary_fixes?: PhotoExtractSummary | PhotoExtractFix[];
}

export interface AvatarRenderJob {
  job_id: string;
  user_id: string;
  created_at: string;
  state: string;
  rendering_traits: Record<string, { value: any; ucn: number; rr: number }>;
  result_path: string;
  download_url: string;
  traits_count?: number;
}

export interface AvatarRenderResult {
  ok: boolean;
  job: AvatarRenderJob;
}

export interface CoreHealthStatus {
  ok: boolean;
  traits_known?: number;
  curiosity_enabled: boolean;
  photo_import_available?: boolean;
  ucnrr_enabled?: boolean;
  ts: number;
}

export interface UcnrrHealthStatus {
  reachable: boolean;
  base_url?: string;
  last_compute_ts?: number;
  reason?: string;
}

export type PadnaRenderJobState = 'queued' | 'running' | 'done' | 'error';

export interface PadnaRenderJob {
  id: string;
  user_id: string;
  state: PadnaRenderJobState;
  progress: number | null;
  created_at: string | null;
  updated_at: string | null;
  error: string | null;
  result_filename: string | null;
  result_content_type: string | null;
  content_type?: string | null;
  status_url: string | null;
  result_url: string | null;
  bundle: Record<string, unknown>;
  params: Record<string, unknown>;
  storage_path?: string | null;
}

export interface DraftChatItem {
  id: string;
  ts: string | null;
  title?: string | null;
  content: string;
  source_path?: string | null;
}

export interface DraftImportEntry {
  title?: string | null;
  content: string;
  ts?: string | number | null;
  source_path?: string | null;
}

export interface SnapshotItem {
  filename: string;
  path: string;
  size: number | null;
  version: string | null;
  generated_at: string | null;
  download_url?: string | null;
}

export interface BigFiveSeed {
  O: number;
  C: number;
  E: number;
  A: number;
  N: number;
}

export interface CreateUserRequest {
  userId: string;
  label?: string;
  seed?: {
    Big5?: Record<string, number>;
  };
}

export interface CreateUserResponse {
  ok: boolean;
  user: {
    id: string;
    label: string;
    created_ts: string;
  };
}

export interface InitUserContainersResponse {
  ok: boolean;
  user_id: string;
  traits_total: number;
  traits_added: number;
  traits_updated: number;
  by_trait_initialized: number;
  onboarding_written?: string;
}

export interface OnboardingFactPayload {
  value?: string | null;
  label?: string | null;
  custom?: string | null;
}

export interface SubmitOnboardingRequest {
  userId: string;
  displayName?: string;
  bigFive?: Record<'O' | 'C' | 'E' | 'A' | 'N', number> | null;
  quickFacts: {
    eye_color?: OnboardingFactPayload;
    hair_color?: OnboardingFactPayload;
    handedness?: OnboardingFactPayload;
  };
  interests: {
    selected: string[];
    custom: string[];
  };
  notes?: string | null;
}

export interface SubmitOnboardingResponse {
  ok: boolean;
  written?: string;
  ucnrr?: Record<string, unknown> | null;
  profile?: Record<string, unknown> | null;
}

export interface UnabridgedTrait {
  trait_id: string;
  value: unknown;
  ucn: number | null;
  rr?: number | null;
  curiosity?: number | null;
  reasons: string[];
  last_observed?: string | null;
  metadata?: Record<string, unknown>;
  badges: string[];
  status?: 'resolved' | 'inferred' | 'unknown' | 'conflict';
  ui_hidden?: boolean;
}

export interface UnabridgedSnapshot {
  user_id: string;
  count: number;
  traits: UnabridgedTrait[];
}

export class ApiError extends Error {
  status: number;
  payload?: unknown;

  constructor(message: string, status: number, payload?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.payload = payload;
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

async function ensureOk(response: Response): Promise<Response> {
  if (response.ok) {
    return response;
  }
  let detail = '';
  let payload: unknown;
  try {
    payload = await response.clone().json();
    const data = payload as any;
    detail = typeof data === 'string' ? data : data?.error || data?.message || JSON.stringify(data);
  } catch (error) {
    try {
      detail = await response.clone().text();
    } catch (errorText) {
      detail = '';
    }
  }
  const base = `Request failed (${response.status})`;
  const message = detail ? `${base}: ${detail}` : base;
  throw new ApiError(message, response.status, payload);
}

export async function fetchPersonaRoster(): Promise<PersonaRosterEntry[]> {
  const response = await ensureOk(
    await fetch(`${CORE_API_BASE}/ui/personas`, {
      headers: { Accept: 'application/json' }
    })
  );
  const payload = await response.json();
  const personas = Array.isArray(payload?.personas) ? payload.personas : [];
  return normalizePersonaRoster(personas);
}

function normalizeUserSummary(raw: any): UserSummary {
  const id = String(raw?.id ?? raw?.user_id ?? '');
  return {
    id,
    label: String(raw?.label ?? id),
    created_ts: String(raw?.created_ts ?? ''),
    last_used_ts: raw?.last_used_ts ?? null,
    last_modified_ts: raw?.last_modified_ts ?? null
  };
}

function coerceUserSummary(raw: any): UserSummary {
  const summary = normalizeUserSummary(raw);
  if (!summary.created_ts) {
    summary.created_ts = new Date().toISOString();
  }
  return summary;
}

function normalizeUserMedia(raw: any): UserMediaItem {
  if (!raw) {
    throw new ApiError('Malformed media response', 500, raw);
  }
  return {
    id: String(raw.id ?? raw.media_id ?? ''),
    filename: String(raw.filename ?? ''),
    original_name: String(raw.original_name ?? raw.filename ?? ''),
    content_type: raw.content_type ?? null,
    size: typeof raw.size === 'number' ? raw.size : raw.size != null ? Number(raw.size) : null,
    uploaded_ts: raw.uploaded_ts ?? null,
    label: raw.label ?? null,
    download_url: raw.download_url ?? null,
    metadata: raw.metadata && typeof raw.metadata === 'object' ? (raw.metadata as Record<string, unknown>) : null
  };
}

function normalizeSnapshotItem(raw: any): SnapshotItem {
  if (!raw) {
    throw new ApiError('Malformed snapshot response', 500, raw);
  }
  return {
    filename: String(raw.filename ?? ''),
    path: String(raw.path ?? ''),
    size: typeof raw.size === 'number' ? raw.size : raw.size != null ? Number(raw.size) : null,
    version: raw.version != null ? String(raw.version) : null,
    generated_at: raw.generated_at ?? null,
    download_url: raw.download_url ?? null
  };
}

function normalizePhotoRenderJob(raw: any): PhotoRenderJob {
  if (!raw) {
    throw new ApiError('Malformed render job response', 500, raw);
  }
  const ensureNumber = (value: any): number | null => {
    if (typeof value === 'number' && Number.isFinite(value)) {
      return Math.max(0, Math.min(1, value));
    }
    if (value == null) {
      return null;
    }
    const parsed = Number(value);
    if (Number.isNaN(parsed)) {
      return null;
    }
    return Math.max(0, Math.min(1, parsed));
  };

  const allowedStates: PhotoRenderJobState[] = ['queued', 'running', 'done', 'error'];
  const stateCandidate = typeof raw.state === 'string' ? raw.state.toLowerCase() : 'queued';
  const normalizedState = allowedStates.includes(stateCandidate as PhotoRenderJobState)
    ? (stateCandidate as PhotoRenderJobState)
    : 'queued';

  return {
    id: String(raw.id ?? raw.job_id ?? ''),
    user_id: String(raw.user_id ?? ''),
    media_id: String(raw.media_id ?? ''),
    state: normalizedState,
    progress: ensureNumber(raw.progress),
    created_at: raw.created_at ?? null,
    updated_at: raw.updated_at ?? null,
    error: raw.error ?? null,
    result_id: raw.result_id ?? null,
    result_filename: raw.result_filename ?? null,
    result_content_type: raw.result_content_type ?? null,
    status_url: raw.status_url ?? null,
    result_url: raw.result_url ?? null,
    params: typeof raw.params === 'object' && raw.params !== null ? raw.params : {}
  };
}

function normalizePadnaRenderJob(raw: any): PadnaRenderJob {
  if (!raw) {
    throw new ApiError('Malformed PaDNA render job response', 500, raw);
  }
  const ensureNumber = (value: any): number | null => {
    if (typeof value === 'number' && Number.isFinite(value)) {
      return Math.max(0, Math.min(1, value));
    }
    if (value == null) {
      return null;
    }
    const parsed = Number(value);
    if (Number.isNaN(parsed)) {
      return null;
    }
    return Math.max(0, Math.min(1, parsed));
  };

  const allowedStates: PadnaRenderJobState[] = ['queued', 'running', 'done', 'error'];
  const stateCandidate = typeof raw.state === 'string' ? raw.state.toLowerCase() : 'queued';
  const normalizedState = allowedStates.includes(stateCandidate as PadnaRenderJobState)
    ? (stateCandidate as PadnaRenderJobState)
    : 'queued';

  return {
    id: String(raw.id ?? raw.job_id ?? ''),
    user_id: String(raw.user_id ?? ''),
    state: normalizedState,
    progress: ensureNumber(raw.progress),
    created_at: raw.created_at ?? null,
    updated_at: raw.updated_at ?? null,
    error: raw.error ?? null,
    result_filename: raw.result_filename ?? null,
    result_content_type: raw.result_content_type ?? null,
    content_type: raw.content_type ?? raw.result_content_type ?? null,
    status_url: raw.status_url ?? null,
    result_url: raw.result_url ?? null,
    bundle: typeof raw.bundle === 'object' && raw.bundle !== null ? (raw.bundle as Record<string, unknown>) : {},
    params: typeof raw.params === 'object' && raw.params !== null ? (raw.params as Record<string, unknown>) : {},
    storage_path:
      typeof raw.storage_path === 'string' && raw.storage_path.trim()
        ? String(raw.storage_path)
        : raw.id
        ? `renders/${String(raw.id)}/`
        : null
  };
}

function normalizeDraftChatItem(raw: any): DraftChatItem {
  if (!raw) {
    throw new ApiError('Malformed draft chat response', 500, raw);
  }
  const coerceContent = (value: any): string => {
    if (value == null) {
      return '';
    }
    if (typeof value === 'string') {
      return value;
    }
    if (Array.isArray(value)) {
      return value
        .map((item) => coerceContent(item))
        .filter((item) => item.length > 0)
        .join('\n\n');
    }
    if (typeof value === 'object') {
      try {
        return JSON.stringify(value, null, 2);
      } catch (error) {
        return String(value);
      }
    }
    return String(value);
  };

  return {
    id: String(raw.id ?? raw.job_id ?? raw.draft_id ?? ''),
    ts: raw.ts ?? raw.timestamp ?? raw.created_at ?? null,
    title: raw.title ?? raw.summary ?? null,
    content: coerceContent(raw.content ?? raw.body ?? raw.text ?? raw.markdown ?? ''),
    source_path: raw.source_path ?? null
  };
}

export async function fetchUsers(query: string): Promise<UserSummary[]> {
  const params = new URLSearchParams();
  if (query.trim()) {
    params.set('query', query.trim());
  }
  const qs = params.toString();
  const response = await ensureOk(
    await fetch(`${CORE_API_BASE}/ui/users${qs ? `?${qs}` : ''}`, {
      headers: { Accept: 'application/json' }
    })
  );
  const payload = await response.json();
  const users = Array.isArray(payload?.users) ? payload.users : [];
  return users.map((entry: any) => normalizeUserSummary(entry));
}

export async function listUserMedia(userId: string): Promise<UserMediaItem[]> {
  const trimmed = userId.trim();
  if (!trimmed) {
    return [];
  }
  const params = new URLSearchParams({ user_id: trimmed });
  const response = await ensureOk(
    await fetch(`${CORE_API_BASE}/ui/media/list?${params.toString()}`, {
      headers: { Accept: 'application/json' }
    })
  );
  const payload = await response.json();
  const items = Array.isArray(payload?.items) ? payload.items : [];
  return items.map((entry: any) => normalizeUserMedia(entry));
}

export async function uploadUserMedia(
  userId: string,
  file: File,
  options?: { label?: string }
): Promise<UserMediaItem> {
  const trimmed = userId.trim();
  if (!trimmed) {
    throw new ApiError('user_id is required for media upload.', 400);
  }

  const form = new FormData();
  form.append('user_id', trimmed);
  form.append('file', file, file.name);
  if (options?.label) {
    form.append('label', options.label);
  }

  const response = await ensureOk(
    await fetch(`${CORE_API_BASE}/ui/media/upload`, {
      method: 'POST',
      body: form
    })
  );
  const payload = await response.json();
  return normalizeUserMedia(payload?.media);
}

export async function createPhotoRenderJob(
  userId: string,
  mediaId: string,
  params?: Record<string, unknown>
): Promise<PhotoRenderJob> {
  const trimmedUser = userId.trim();
  const trimmedMedia = mediaId.trim();
  if (!trimmedUser || !trimmedMedia) {
    throw new ApiError('user_id and media_id are required for render jobs.', 400);
  }
  const response = await ensureOk(
    await fetch(`${CORE_API_BASE}/ui/photo/render`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({ user_id: trimmedUser, media_id: trimmedMedia, params: params ?? {} })
    })
  );
  const payload = await response.json();
  if (payload?.job) {
    return normalizePhotoRenderJob(payload.job);
  }
  if (payload?.job_id) {
    return normalizePhotoRenderJob({ ...(payload.job ?? {}), id: payload.job_id, user_id: trimmedUser, media_id: trimmedMedia });
  }
  throw new ApiError('Unexpected render job response', 500, payload);
}

export async function fetchPhotoRenderStatus(jobId: string, userId?: string): Promise<PhotoRenderJob> {
  const trimmedJob = jobId.trim();
  if (!trimmedJob) {
    throw new ApiError('job_id is required for status lookup.', 400);
  }
  const params = new URLSearchParams({ job_id: trimmedJob });
  if (userId?.trim()) {
    params.set('user_id', userId.trim());
  }
  const response = await ensureOk(
    await fetch(`${CORE_API_BASE}/ui/photo/status?${params.toString()}`, {
      headers: { Accept: 'application/json' }
    })
  );
  const payload = await response.json();
  if (!payload?.job) {
    throw new ApiError('Render job not found.', 404, payload);
  }
  return normalizePhotoRenderJob(payload.job);
}

export async function listPhotoRenderJobs(userId: string, limit?: number): Promise<PhotoRenderJob[]> {
  const trimmedUser = userId.trim();
  if (!trimmedUser) {
    return [];
  }
  const params = new URLSearchParams({ user_id: trimmedUser });
  if (typeof limit === 'number' && Number.isFinite(limit)) {
    params.set('limit', String(limit));
  }
  const response = await ensureOk(
    await fetch(`${CORE_API_BASE}/ui/photo/jobs?${params.toString()}`, {
      headers: { Accept: 'application/json' }
    })
  );
  const payload = await response.json();
  const items = Array.isArray(payload?.items) ? payload.items : [];
  return items.map((entry: any) => normalizePhotoRenderJob(entry));
}

export async function extractPhotoTraits(userId: string, mediaId: string): Promise<PhotoExtractResult> {
  const trimmedUser = userId.trim();
  const trimmedMedia = mediaId.trim();
  if (!trimmedUser || !trimmedMedia) {
    throw new ApiError('user_id and media_id are required for photo extraction.', 400);
  }

  const response = await ensureOk(
    await fetch(`${CORE_API_BASE}/ui/photo/extract`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json'
      },
      body: JSON.stringify({ user_id: trimmedUser, media_id: trimmedMedia })
    })
  );

  const payload = await response.json();
  const traits = Array.isArray(payload?.traits) ? payload.traits : [];
  const summary_fixes = payload?.summary_fixes;

  return {
    traits: traits
      .map((entry: any) => ({
        trait: String(entry?.trait ?? ''),
        value: String(entry?.value ?? ''),
        ucn: Number(entry?.ucn ?? 0),
        rr: entry?.rr,
        rr_band: entry?.rr_band,
        curiosity: entry?.curiosity
      }))
      .filter((entry: { trait: string; value: string; ucn: number }) => entry.trait),
    summary_fixes
  };
}

export async function renderAvatar(userId: string): Promise<AvatarRenderResult> {
  const trimmedUser = userId.trim();
  if (!trimmedUser) {
    throw new ApiError('user_id is required for avatar render.', 400);
  }

  const response = await ensureOk(
    await fetch(`${CORE_API_BASE}/ui/render/avatar`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify({ user_id: trimmedUser }),
    })
  );

  return await response.json();
}

export async function listRenderJobs(userId: string): Promise<AvatarRenderJob[]> {
  const trimmedUser = userId.trim();
  if (!trimmedUser) {
    return [];
  }

  const response = await ensureOk(
    await fetch(`${CORE_API_BASE}/ui/render/jobs/${encodeURIComponent(trimmedUser)}`, {
      headers: { Accept: 'application/json' }
    })
  );

  const payload = await response.json();
  const jobs = Array.isArray(payload?.jobs) ? payload.jobs : [];

  return jobs.map((job: any) => ({
    job_id: String(job?.job_id ?? ''),
    user_id: trimmedUser,
    created_at: String(job?.created_at ?? ''),
    state: String(job?.state ?? 'unknown'),
    rendering_traits: {},
    result_path: '',
    download_url: String(job?.download_url ?? ''),
    traits_count: Number(job?.traits_count ?? 0)
  }));
}

export interface PhotoFixApplyRequest {
  user_id: string;
  trait_id: string;
  value: string;
  reason?: string;
}

export interface PhotoFixApplyResult {
  ok: boolean;
  trait_id: string;
  value: string;
  changes: Array<{
    trait: string;
    old_rr: number;
    new_rr: number;
    delta: number;
  }>;
  rescore_triggered: boolean;
}

export async function applyPhotoFix(request: PhotoFixApplyRequest): Promise<PhotoFixApplyResult> {
  const trimmedUser = request.user_id.trim();
  const trimmedTrait = request.trait_id.trim();

  if (!trimmedUser || !trimmedTrait || request.value == null) {
    throw new ApiError('user_id, trait_id, and value are required.', 400);
  }

  const response = await ensureOk(
    await fetch(`${CORE_API_BASE}/ui/photo/apply_fix`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify({
        user_id: trimmedUser,
        trait_id: trimmedTrait,
        value: request.value,
        reason: request.reason || 'photo_fix_applied'
      }),
    })
  );

  return await response.json();
}

export interface PhotoImportRequest {
  user_id: string;
  data: any; // Can be structured JSON or plain text string
  source?: string;
}

export interface PhotoImportTrait {
  trait: string;
  value: any;
  ucn: number;
}

export interface PhotoImportQuarantined {
  raw_path: string;
  raw_value: any;
  reasons: string[];
}

export interface InferredTrait {
  trait_path: string;
  value: any;
  confidence: number;
  reasoning: string;
  source_traits: string[];
  category: string;
}

export interface InferenceResults {
  available: boolean;
  count: number;
  model_used?: string;
  traits: InferredTrait[];
  skipped?: string[];
  warnings?: string[];
}

export interface PhotoImportResult {
  ok: boolean;
  imported: number;
  traits: PhotoImportTrait[];
  quarantined: PhotoImportQuarantined[];
  assisted: any[];
  warnings: string[];
  rescore_triggered: boolean;
  inferences?: InferenceResults;
}

export async function importPhotoData(request: PhotoImportRequest): Promise<PhotoImportResult> {
  const trimmedUser = request.user_id.trim();

  if (!trimmedUser || request.data == null) {
    throw new ApiError('user_id and data are required.', 400);
  }

  const response = await ensureOk(
    await fetch(`${CORE_API_BASE}/ui/photo/import`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify({
        user_id: trimmedUser,
        data: request.data,
        source: request.source || 'photo-import'
      }),
    })
  );

  return await response.json();
}

export interface ApplyInferencesRequest {
  user_id: string;
  inferences: InferredTrait[];
}

export interface ApplyInferencesResult {
  ok: boolean;
  applied: number;
  message: string;
}

export async function applyInferences(request: ApplyInferencesRequest): Promise<ApplyInferencesResult> {
  const trimmedUser = request.user_id.trim();

  if (!trimmedUser || !request.inferences || request.inferences.length === 0) {
    throw new ApiError('user_id and inferences are required.', 400);
  }

  const response = await ensureOk(
    await fetch(`${CORE_API_BASE}/ui/photo/apply_inferences`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify({
        user_id: trimmedUser,
        inferences: request.inferences
      }),
    })
  );

  return await response.json();
}

export async function fetchCoreHealth(): Promise<CoreHealthStatus> {
  const response = await ensureOk(
    await fetch(`${CORE_API_BASE}/health`, {
      headers: { Accept: 'application/json' }
    })
  );
  const payload = await response.json();
  const traitsKnownRaw = payload?.traits_known;
  const tsRaw = payload?.ts || payload?.timestamp;

  // Use current time if no timestamp in response
  let ts = Date.now();
  if (typeof tsRaw === 'number' && Number.isFinite(tsRaw)) {
    ts = tsRaw;
  } else if (typeof tsRaw === 'string') {
    const parsed = Date.parse(tsRaw);
    if (!Number.isNaN(parsed)) {
      ts = parsed;
    }
  }

  // Handle both old format (ok: boolean) and new format (status: "healthy")
  const isHealthy = payload?.ok === true || payload?.status === 'healthy';

  const features = payload?.features || {};

  return {
    ok: isHealthy,
    traits_known: typeof traitsKnownRaw === 'number' && Number.isFinite(traitsKnownRaw) ? traitsKnownRaw : undefined,
    curiosity_enabled: Boolean(payload?.curiosity_enabled || features?.curiosity_enabled),
    photo_import_available: Boolean(features?.photo_import),
    ucnrr_enabled: Boolean(features?.ucnrr_enabled),
    ts
  };
}

export async function fetchUcnrrHealth(): Promise<UcnrrHealthStatus> {
  const response = await ensureOk(
    await fetch(`${CORE_API_BASE}/ui/ucnrr/health`, {
      headers: { Accept: 'application/json' }
    })
  );
  const payload = await response.json();

  return {
    reachable: Boolean(payload?.reachable),
    base_url: payload?.base_url,
    last_compute_ts: typeof payload?.last_compute_ts === 'number' ? payload.last_compute_ts : undefined,
    reason: payload?.reason
  };
}

export async function createPadnaRenderJob(
  userId: string,
  bundle: Record<string, unknown>
): Promise<PadnaRenderJob> {
  const trimmedUser = userId.trim();
  if (!trimmedUser) {
    throw new ApiError('user_id is required for PaDNA render jobs.', 400);
  }
  const response = await ensureOk(
    await fetch(`${CORE_API_BASE}/ui/padna/render`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({ user_id: trimmedUser, bundle })
    })
  );
  const payload = await response.json();
  if (payload?.job) {
    return normalizePadnaRenderJob(payload.job);
  }
  throw new ApiError('Unexpected PaDNA render response.', 500, payload);
}

export async function listPadnaRenderJobs(userId: string, limit?: number): Promise<PadnaRenderJob[]> {
  const trimmedUser = userId.trim();
  if (!trimmedUser) {
    return [];
  }
  const params = new URLSearchParams({ user_id: trimmedUser });
  if (typeof limit === 'number' && Number.isFinite(limit) && limit > 0) {
    params.set('limit', String(Math.floor(limit)));
  }
  const response = await ensureOk(
    await fetch(`${CORE_API_BASE}/ui/padna/list?${params.toString()}`, {
      headers: { Accept: 'application/json' }
    })
  );
  const payload = await response.json();
  const items = Array.isArray(payload?.items) ? payload.items : [];
  return items.map((entry: any) => normalizePadnaRenderJob(entry));
}

export async function fetchPadnaRenderStatus(jobId: string, userId?: string): Promise<PadnaRenderJob> {
  const trimmedJob = jobId.trim();
  if (!trimmedJob) {
    throw new ApiError('job_id is required for status lookup.', 400);
  }
  const params = new URLSearchParams({ job_id: trimmedJob });
  if (userId?.trim()) {
    params.set('user_id', userId.trim());
  }
  const response = await ensureOk(
    await fetch(`${CORE_API_BASE}/ui/padna/status?${params.toString()}`, {
      headers: { Accept: 'application/json' }
    })
  );
  const payload = await response.json();
  if (!payload?.job) {
    throw new ApiError('PaDNA render job not found.', 404, payload);
  }
  return normalizePadnaRenderJob(payload.job);
}

export function buildPadnaResultUrl(job: PadnaRenderJob): string {
  const basePath = job.result_url ?? `/ui/padna/result?job_id=${encodeURIComponent(job.id)}`;
  const normalizedPath = basePath.startsWith('/') ? basePath : `/${basePath}`;
  return `${CORE_API_BASE}${normalizedPath}`;
}

export async function listSnapshots(userId: string): Promise<SnapshotItem[]> {
  const trimmed = userId.trim();
  if (!trimmed) {
    return [];
  }
  const params = new URLSearchParams({ user_id: trimmed });
  const response = await ensureOk(
    await fetch(`${CORE_API_BASE}/ui/snapshots?${params.toString()}`, {
      headers: { Accept: 'application/json' }
    })
  );
  const payload = await response.json();
  const items = Array.isArray(payload?.items) ? payload.items : [];
  const normalized = items.map((entry: any) => normalizeSnapshotItem(entry));
  writeCache('snapshots', trimmed, normalized);
  return normalized;
}

export async function fetchDraftChat(
  userId: string,
  options?: { limit?: number; since?: string }
): Promise<DraftChatItem[]> {
  const trimmed = userId.trim();
  if (!trimmed) {
    return [];
  }
  const params = new URLSearchParams({ user_id: trimmed });
  if (options?.limit != null && Number.isFinite(options.limit)) {
    params.set('limit', String(Math.max(1, Math.floor(options.limit))));
  }
  if (options?.since) {
    params.set('since', options.since);
  }
  const response = await ensureOk(
    await fetch(`${CORE_API_BASE}/ui/draft_chat?${params.toString()}`, {
      headers: { Accept: 'application/json' }
    })
  );
  const payload = await response.json();
  const items = Array.isArray(payload?.items) ? payload.items : [];
  return items.map((entry: any) => normalizeDraftChatItem(entry));
}

export async function importDraftChatEntries(
  userId: string,
  entries: DraftImportEntry[]
): Promise<number> {
  const trimmed = userId.trim();
  if (!trimmed) {
    throw new ApiError('user_id is required to import drafts.', 400);
  }
  const safeEntries = Array.isArray(entries) ? entries : [];
  const params = new URLSearchParams({ user_id: trimmed });
  const response = await ensureOk(
    await fetch(`${CORE_API_BASE}/ui/draft/import?${params.toString()}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json'
      },
      body: JSON.stringify(safeEntries)
    })
  );
  const payload = await response.json();
  return Number(payload?.imported ?? 0);
}

export async function clearDraftChat(userId: string): Promise<number> {
  const trimmed = userId.trim();
  if (!trimmed) {
    throw new ApiError('user_id is required to clear drafts.', 400);
  }
  const params = new URLSearchParams({ user_id: trimmed });
  const response = await ensureOk(
    await fetch(`${CORE_API_BASE}/ui/draft/clear?${params.toString()}`, {
      method: 'POST',
      headers: {
        Accept: 'application/json'
      }
    })
  );
  const payload = await response.json();
  return Number(payload?.removed ?? 0);
}

export interface ImportUserResponse {
  ok: boolean;
  user: UserSummary;
  overwrote: boolean;
  snapshot_path?: string | null;
}

export interface BulkImportResult {
  filename: string;
  status: 'imported' | 'conflict' | 'error';
  user?: UserSummary;
  overwrote?: boolean;
  message?: string | null;
  snapshot_path?: string | null;
}

export interface BulkImportResponse {
  ok: boolean;
  imported: number;
  overwritten: number;
  conflicts: number;
  results: BulkImportResult[];
}

function extractImportError(response: Response): Promise<ApiError> {
  return response
    .clone()
    .json()
    .then((payload) => {
      const message = typeof payload?.message === 'string' ? payload.message : 'Import failed.';
      return new ApiError(message, response.status, payload);
    })
    .catch(async () => {
      const text = await response.clone().text();
      const message = text || 'Import failed.';
      return new ApiError(message, response.status);
    });
}

export async function importUserBundle(file: File, options?: { overwrite?: boolean }): Promise<ImportUserResponse> {
  const form = new FormData();
  form.append('file', file, file.name);
  if (options?.overwrite) {
    form.append('overwrite', 'true');
  }

  const response = await fetch(`${CORE_API_BASE}/ui/user/import`, {
    method: 'POST',
    body: form
  });

  if (response.status === 409) {
    throw await extractImportError(response);
  }
  if (!response.ok) {
    throw await extractImportError(response);
  }

  const payload = await response.json();
  const summary = coerceUserSummary(payload?.user ?? {});
  return {
    ok: Boolean(payload?.ok ?? true),
    user: summary,
    overwrote: Boolean(payload?.overwrote),
    snapshot_path: payload?.snapshot_path ?? null
  };
}

export async function importUsersBulk(file: File, options?: { overwrite?: boolean }): Promise<BulkImportResponse> {
  const form = new FormData();
  form.append('file', file, file.name);
  if (options?.overwrite) {
    form.append('overwrite', 'true');
  }

  const response = await fetch(`${CORE_API_BASE}/ui/users/import_bulk`, {
    method: 'POST',
    body: form
  });

  if (!response.ok) {
    throw await extractImportError(response);
  }

  const payload = await response.json();
  const rows = Array.isArray(payload?.results) ? payload.results : [];
  const results: BulkImportResult[] = rows.map((entry: any) => {
    const filename = String(entry?.filename ?? file.name ?? 'bundle.json');
    const status = entry?.status === 'conflict' ? 'conflict' : entry?.status === 'imported' ? 'imported' : 'error';
    return {
      filename,
      status,
      user: entry?.user ? coerceUserSummary(entry.user) : undefined,
      overwrote: Boolean(entry?.overwrote),
      message: entry?.message != null ? String(entry.message) : null,
      snapshot_path: entry?.snapshot_path ?? null
    };
  });

  return {
    ok: Boolean(payload?.ok ?? true),
    imported: Number(payload?.imported ?? 0),
    overwritten: Number(payload?.overwritten ?? 0),
    conflicts: Number(payload?.conflicts ?? 0),
    results
  };
}

export async function createUser(request: CreateUserRequest): Promise<CreateUserResponse> {
  const body: Record<string, unknown> = {
    user_id: request.userId,
    label: request.label
  };
  if (request.seed) {
    body.seed = request.seed;
  }

  const response = await ensureOk(
    await fetch(`${CORE_API_BASE}/ui/user/create`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json'
      },
      body: JSON.stringify(body)
    })
  );
  const payload = await response.json();
  return {
    ok: Boolean(payload?.ok),
    user: {
      id: String(payload?.user?.id ?? request.userId),
      label: String(payload?.user?.label ?? request.label ?? request.userId),
      created_ts: String(payload?.user?.created_ts ?? new Date().toISOString())
    }
  };
}

export async function initUserContainers(params: {
  userId: string;
  label?: string | null;
  scriptPath?: 'smart_defaults' | 'trust_walkthrough';
  quickFacts?: SubmitOnboardingRequest['quickFacts'];
  interests?: SubmitOnboardingRequest['interests'];
  seedUsed?: boolean;
}): Promise<InitUserContainersResponse> {
  const payload: Record<string, unknown> = {
    user_id: params.userId,
  };
  if (params.label && params.label.trim()) {
    payload.label = params.label.trim();
  }

  const onboarding: Record<string, unknown> = {};
  if (params.scriptPath) {
    onboarding.script_path = params.scriptPath;
  }
  if (params.quickFacts && Object.keys(params.quickFacts).length > 0) {
    onboarding.quick_facts = params.quickFacts;
  }
  if (params.interests) {
    onboarding.interests = {
      selected: [...(params.interests.selected ?? [])],
      custom: [...(params.interests.custom ?? [])],
    };
  }
  if (typeof params.seedUsed === 'boolean') {
    onboarding.seed_used = params.seedUsed;
  }
  if (Object.keys(onboarding).length > 0) {
    payload.onboarding = onboarding;
  }

  const response = await ensureOk(
    await fetch(`${CORE_API_BASE}/ui/users/init`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify(payload),
    })
  );

  const body = await response.json();
  return {
    ok: Boolean(body?.ok ?? true),
    user_id: String(body?.user_id ?? params.userId),
    traits_total: Number(body?.traits_total ?? 0),
    traits_added: Number(body?.traits_added ?? 0),
    traits_updated: Number(body?.traits_updated ?? 0),
    by_trait_initialized: Number(body?.by_trait_initialized ?? 0),
    onboarding_written:
      typeof body?.onboarding_written === 'string' ? String(body.onboarding_written) : undefined,
  };
}

export interface OnboardingWizardData {
  basic_setup: Record<string, string>;
  head_coach_name: string;
  wyr_answer?: {
    question_id: string;
    selected_letter: string;
    selected_text: string;
  };
}

export interface OnboardingWizardSubmitResponse {
  ok: boolean;
  written?: string;
  checkpoint_event?: string | null;
}

/**
 * @deprecated NORTHSTAR PHASE 2: Use unified Core ingestion instead
 * This function bypasses the Core → UCN/RR roundtrip pipeline.
 * Use: formatOnboardingPayload() + ingestAndRefresh() from hcIngestor.ts
 */
export async function submitOnboardingWizardData(
  userId: string,
  data: OnboardingWizardData
): Promise<OnboardingWizardSubmitResponse> {
  // NORTHSTAR PHASE 2: Log bypass attempt
  if (typeof process !== 'undefined' && process.env.NEXT_PUBLIC_CORE_BYPASS_ALLOWED === 'false') {
    console.warn('[Northstar] Direct trait writes are disabled (No-Bypass Rule). Use hcIngestor.ts instead.');
  }

  const trimmedUser = userId.trim();
  if (!trimmedUser) {
    throw new ApiError('user_id is required for onboarding submission.', 400);
  }

  // Wrap data in 'profile' object as expected by Core API
  const profile: Record<string, unknown> = {
    basic_setup: data.basic_setup,
    head_coach_name: data.head_coach_name
  };

  if (data.wyr_answer) {
    profile.wyr_answer = data.wyr_answer;
  }

  const body = {
    user_id: trimmedUser,
    profile: profile
  };

  const response = await ensureOk(
    await fetch(`${CORE_API_BASE}/ui/onboarding/submit`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json'
      },
      body: JSON.stringify(body)
    })
  );

  const payload = await response.json();
  return {
    ok: Boolean(payload?.ok),
    written: typeof payload?.written === 'string' ? payload.written : undefined,
    checkpoint_event: payload?.checkpoint_event ?? null
  };
}

export async function fetchOnboardingStatus(userId: string): Promise<boolean> {
  const trimmedUser = userId.trim();
  if (!trimmedUser) {
    return false;
  }

  try {
    const response = await fetch(
      `${CORE_API_BASE}/ui/onboarding/status?user_id=${encodeURIComponent(trimmedUser)}`,
      {
        headers: { Accept: 'application/json' }
      }
    );

    if (!response.ok) {
      return false;
    }

    const payload = await response.json();
    return Boolean(payload?.completed ?? payload?.exists ?? false);
  } catch (error) {
    console.warn('Failed to fetch onboarding status', error);
    return false;
  }
}

export async function submitOnboardingProfile(
  request: SubmitOnboardingRequest
): Promise<SubmitOnboardingResponse> {
  const profile: Record<string, unknown> = {
    name: {
      display: request.displayName ?? null
    }
  };

  const quickFactsPayload: Record<string, unknown> = {};
  for (const key of ['eye_color', 'hair_color', 'handedness'] as const) {
    const fact = request.quickFacts[key];
    if (fact && (fact.value || fact.label || fact.custom)) {
      const factPayload: Record<string, unknown> = {};
      if (fact.value != null && String(fact.value).trim()) {
        factPayload.value = String(fact.value).trim();
      }
      if (fact.label != null && String(fact.label).trim()) {
        factPayload.label = String(fact.label).trim();
      }
      if (fact.custom != null && String(fact.custom).trim()) {
        factPayload.custom = String(fact.custom).trim();
      }
      if (Object.keys(factPayload).length > 0) {
        quickFactsPayload[key] = factPayload;
      }
    }
  }
  profile.quick_facts = quickFactsPayload;

  const interestsSelected = Array.isArray(request.interests.selected)
    ? request.interests.selected.map((item) => String(item).trim()).filter(Boolean)
    : [];
  const interestsCustom = Array.isArray(request.interests.custom)
    ? request.interests.custom.map((item) => String(item).trim()).filter(Boolean)
    : [];
  profile.interests = {
    selected: interestsSelected,
    custom: interestsCustom
  };

  if (request.bigFive) {
    profile.seed = {
      Big5: request.bigFive
    };
  }

  if (request.notes && request.notes.trim()) {
    profile.notes = request.notes.trim();
  }

  const body: Record<string, unknown> = {
    user_id: request.userId,
    profile
  };

  const response = await ensureOk(
    await fetch(`${CORE_API_BASE}/ui/onboarding/submit`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json'
      },
      body: JSON.stringify(body)
    })
  );

  const payload = await response.json();
  return {
    ok: Boolean(payload?.ok),
    written: typeof payload?.written === 'string' ? payload.written : undefined,
    ucnrr: payload?.ucnrr ?? null,
    profile: payload?.profile ?? null
  };
}

function normalizeActionPolicy(raw: any): AskActionPolicy {
  if (raw && typeof raw === 'object') {
    return {
      allowed: Boolean(raw.allowed),
      reason: raw.reason != null ? String(raw.reason) : null
    };
  }
  return { allowed: true, reason: null };
}

function normalizePlannerAsk(raw: any): PlannerAsk {
  const policyRaw = raw?.policy ?? {};
  return {
    id: String(raw?.id ?? ''),
    container: String(raw?.container ?? ''),
    gap: String(raw?.gap ?? ''),
    confidence: Number(raw?.confidence ?? 0),
    ask_type: String(raw?.ask_type ?? ''),
    phrasing_stub: String(raw?.phrasing_stub ?? ''),
    sensitivity: Boolean(raw?.sensitivity),
    created_at: String(raw?.created_at ?? ''),
    expires_at: String(raw?.expires_at ?? ''),
    next_available_at: String(raw?.next_available_at ?? ''),
    ttl_minutes: Number(raw?.ttl_minutes ?? 0),
    snooze_minutes: Number(raw?.snooze_minutes ?? 0),
    metadata: raw?.metadata ?? {},
    status: raw?.status ? String(raw.status) : 'pending',
    policy: {
      approve: normalizeActionPolicy(policyRaw.approve),
      snooze: normalizeActionPolicy(policyRaw.snooze),
      skip: normalizeActionPolicy(policyRaw.skip)
    },
    default_snooze_minutes: Number(raw?.default_snooze_minutes ?? raw?.snooze_minutes ?? 120)
  };
}

function ensureIsoFromMillis(value: unknown): string {
  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (trimmed) {
      const parsed = Date.parse(trimmed);
      if (!Number.isNaN(parsed)) {
        return new Date(parsed).toISOString();
      }
    }
  }

  const numeric = typeof value === 'number' ? value : Number(value);
  if (Number.isFinite(numeric)) {
    try {
      return new Date(numeric).toISOString();
    } catch (error) {
      return new Date().toISOString();
    }
  }

  return new Date().toISOString();
}

const ASK_COMPLETED_STATUSES = new Set(['done', 'completed', 'closed']);
const NUDGE_COMPLETED_STATUSES = new Set(['read', 'done', 'completed']);

function normalizeAskListEntry(raw: any, userId: string, index: number): PlannerAsk {
  const fallbackId = `${userId || 'user'}_ask_${index + 1}`;
  const id = String(raw?.id ?? fallbackId);
  const statusRaw = String(raw?.status ?? 'open').toLowerCase();
  const normalizedStatus = ASK_COMPLETED_STATUSES.has(statusRaw) ? 'completed' : 'pending';
  const title = raw?.title != null ? String(raw.title) : String(raw?.headline ?? 'Coach ask');
  const body = raw?.body != null ? String(raw.body) : String(raw?.summary ?? '');
  const createdIso = ensureIsoFromMillis(raw?.ts ?? raw?.created_ts ?? raw?.created_at);

  const metadata: Record<string, unknown> = {
    ...(raw?.meta && typeof raw.meta === 'object' ? raw.meta : {}),
    title,
  };
  if (body) {
    metadata.body = body;
  }
  metadata.original_status = statusRaw;

  const defaultPolicy = {
    approve: { allowed: true, reason: null },
    snooze: { allowed: true, reason: null },
    skip: { allowed: true, reason: null }
  };

  const prepared = {
    id,
    container: raw?.container ?? '',
    gap: typeof raw?.gap === 'string' ? raw.gap : '',
    confidence: typeof raw?.confidence === 'number' ? raw.confidence : 0.5,
    ask_type: raw?.ask_type ?? 'coach',
    phrasing_stub: title,
    sensitivity: Boolean(raw?.sensitivity ?? false),
    created_at: createdIso,
    expires_at: createdIso,
    next_available_at: createdIso,
    ttl_minutes: typeof raw?.ttl_minutes === 'number' ? raw.ttl_minutes : 0,
    snooze_minutes: typeof raw?.snooze_minutes === 'number' ? raw.snooze_minutes : 0,
    metadata,
    status: normalizedStatus,
    policy: raw?.policy ?? defaultPolicy,
    default_snooze_minutes:
      typeof raw?.default_snooze_minutes === 'number'
        ? raw.default_snooze_minutes
        : typeof raw?.snooze_minutes === 'number'
          ? raw.snooze_minutes
          : 120
  };

  return normalizePlannerAsk(prepared);
}

export async function fetchAsks(userId: string, options: FetchAsksOptions = {}): Promise<PlannerAsk[]> {
  const trimmedUser = userId.trim();
  if (!trimmedUser) {
    return [];
  }

  const params = new URLSearchParams({ user_id: trimmedUser });
  if (options.limit != null) {
    params.set('limit', String(options.limit));
  }
  if (options.status && options.status !== 'all') {
    params.set('status', options.status);
  }
  if (options.sort) {
    params.set('sort', options.sort);
  }

  const response = await ensureOk(
    await fetch(`${CORE_API_BASE}/ui/asks/list?${params.toString()}`, {
      headers: { Accept: 'application/json' }
    })
  );
  const payload = await response.json();
  const items = Array.isArray(payload?.items) ? payload.items : [];
  const normalized = items.map((item: any, index: number) =>
    normalizeAskListEntry(item, trimmedUser, index)
  );
  writeCache('asks', trimmedUser, normalized);
  return normalized;
}

export async function fetchPlannerAsks(userId: string, limit: number): Promise<PlannerAsk[]> {
  return fetchAsks(userId, { limit });
}

export type AskAction = 'approve' | 'skip' | 'snooze';

export interface AskActionResponse {
  ok: boolean;
  ask?: PlannerAsk;
  reason?: string | null;
}

export async function actOnAsk(params: {
  userId: string;
  id: string;
  action: AskAction;
  minutes?: number;
}): Promise<AskActionResponse> {
  const body: Record<string, unknown> = {
    user_id: params.userId,
    id: params.id,
    action: params.action
  };
  if (params.minutes != null) {
    body.minutes = params.minutes;
  }

  const response = await ensureOk(
    await fetch(`${CORE_API_BASE}/ui/asks/act`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json'
      },
      body: JSON.stringify(body)
    })
  );

  const payload = await response.json();
  const result: AskActionResponse = {
    ok: Boolean(payload?.ok),
    reason: payload?.reason ?? null
  };
  if (payload?.ask) {
    result.ask = normalizeAskListEntry(payload.ask, params.userId, 0);
  }
  return result;
}

export async function addDemoPlannerAsk(
  userId: string,
  options: { title: string; summary?: string; persona?: string; confidence?: number }
): Promise<PlannerAsk> {
  const trimmedUser = userId.trim();
  if (!trimmedUser) {
    throw new ApiError('user_id is required to add a demo ask.', 400);
  }

  const payload: Record<string, unknown> = {
    user_id: trimmedUser,
    title: options.title,
  };
  if (options.summary) {
    payload.summary = options.summary;
  }
  if (options.persona) {
    payload.persona = options.persona;
  }
  if (typeof options.confidence === 'number') {
    payload.confidence = options.confidence;
  }

  const response = await ensureOk(
    await fetch(`${CORE_API_BASE}/ui/asks/add_demo`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify(payload)
    })
  );
  const body = await response.json();
  if (!body?.ask) {
    throw new ApiError('Core did not return a planner ask.', 500, body);
  }
  return normalizePlannerAsk(body.ask);
}

export async function actOnPlannerAsk(
  userId: string,
  askId: string,
  action: 'approve' | 'skip' | 'snooze',
  options?: { snooze_minutes?: number }
): Promise<PlannerAsk> {
  const trimmedUser = userId.trim();
  const trimmedAsk = askId.trim();
  if (!trimmedUser || !trimmedAsk) {
    throw new ApiError('user_id and ask_id are required for ask actions.', 400);
  }

  const payload: Record<string, unknown> = {
    user_id: trimmedUser,
    ask_id: trimmedAsk,
    action
  };
  if (action === 'snooze' && options?.snooze_minutes != null) {
    payload.snooze_minutes = options.snooze_minutes;
  }

  const response = await ensureOk(
    await fetch(`${CORE_API_BASE}/ui/asks/act`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify(payload)
    })
  );
  const body = await response.json();
  if (!body?.ok) {
    throw new ApiError(body?.reason ?? 'Ask action was rejected.', 409, body);
  }
  if (!body.ask) {
    throw new ApiError('Ask action response missing ask payload.', 500, body);
  }
  return normalizePlannerAsk(body.ask);
}

export async function fetchObservationAggregates(userId: string): Promise<ObservationAggregates> {
  const params = new URLSearchParams({ user_id: userId });
  const response = await ensureOk(
    await fetch(`${CORE_API_BASE}/ui/observations/aggregates?${params.toString()}`, {
      headers: { Accept: 'application/json' }
    })
  );
  const payload = await response.json();
  const baseMetrics = normalizeObservationWindowMetrics(payload);
  const windowMetrics = normalizeObservationWindows(payload?.windows);
  return {
    user_id: String(payload?.user_id ?? userId),
    ...baseMetrics,
    windows: windowMetrics,
  };
}

export async function submitTopicPreference(params: {
  userId: string;
  key: string;
  ttlDays: number;
}): Promise<PreferenceSubmitResponse> {
  const trimmedUser = params.userId.trim();
  const trimmedKey = params.key.trim();
  if (!trimmedUser) {
    throw new ApiError('user_id is required to submit a preference.', 400);
  }
  if (!trimmedKey) {
    throw new ApiError('key is required to submit a preference.', 400);
  }
  const response = await ensureOk(
    await fetch(`${CORE_API_BASE}/ui/preferences/submit`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json'
      },
      body: JSON.stringify({
        user_id: trimmedUser,
        key: trimmedKey,
        ttl_days: params.ttlDays,
      }),
    })
  );
  const payload = await response.json();
  return {
    ok: Boolean(payload?.ok),
    user_id: String(payload?.user_id ?? trimmedUser),
    key: String(payload?.key ?? trimmedKey),
    set_at: String(payload?.set_at ?? new Date().toISOString()),
    ttl_days: Number(payload?.ttl_days ?? params.ttlDays),
  };
}

function normalizeObservationWindowMetrics(raw: any): ObservationWindowMetrics {
  const observation_count = Number(raw?.observation_count ?? 0);
  return {
    observation_count: Number.isFinite(observation_count) ? observation_count : 0,
    dialog_acts: normalizeObservationDistribution(raw?.dialog_acts),
    cadence: normalizeObservationCadence(raw?.cadence),
    latency: normalizeObservationLatency(raw?.latency),
    per_persona: normalizeObservationPersonaMap(raw?.per_persona),
  };
}

function normalizeObservationDistribution(raw: any): ObservationDistribution {
  const latestRaw = raw?.latest;
  let latest: string | null = null;
  if (latestRaw !== null && latestRaw !== undefined && `${latestRaw}`.trim() !== '') {
    latest = String(latestRaw);
  }
  const distributionRaw = raw?.distribution;
  const distribution: Record<string, number> = {};
  if (distributionRaw && typeof distributionRaw === 'object') {
    for (const [key, value] of Object.entries(distributionRaw)) {
      const numeric = Number(value);
      if (!Number.isNaN(numeric)) {
        distribution[String(key)] = numeric;
      }
    }
  }
  return { latest, distribution };
}

function normalizeObservationCadence(raw: any): ObservationCadenceSummary {
  const histogramRaw = raw?.histogram;
  const histogram: Record<string, number> = {};
  if (histogramRaw && typeof histogramRaw === 'object') {
    for (const [key, value] of Object.entries(histogramRaw)) {
      const numeric = Number(value);
      if (!Number.isNaN(numeric)) {
        histogram[String(key)] = numeric;
      }
    }
  }
  const latestRaw = raw?.latest_bucket;
  const latest_bucket = latestRaw !== undefined && latestRaw !== null ? String(latestRaw) : null;
  return { latest_bucket, histogram };
}

function normalizeObservationLatency(raw: any): ObservationLatencySummary {
  const histogramRaw = raw?.histogram;
  const histogram: Record<string, number> = {};
  if (histogramRaw && typeof histogramRaw === 'object') {
    for (const [key, value] of Object.entries(histogramRaw)) {
      const numeric = Number(value);
      if (!Number.isNaN(numeric)) {
        histogram[String(key)] = numeric;
      }
    }
  }
  const medianRaw = raw?.median_ms;
  const meanRaw = raw?.mean_ms;
  const median = Number(medianRaw);
  const mean = Number(meanRaw);
  return {
    median_ms: Number.isFinite(median) ? median : null,
    mean_ms: Number.isFinite(mean) ? mean : null,
    histogram,
  };
}

function normalizeObservationPersonaMap(raw: any): Record<string, ObservationPersonaBreakdown> | undefined {
  if (!raw || typeof raw !== 'object') {
    return undefined;
  }
  const entries: Record<string, ObservationPersonaBreakdown> = {};
  for (const [key, value] of Object.entries(raw)) {
    if (value && typeof value === 'object') {
      entries[String(key)] = normalizeObservationPersona(value);
    }
  }
  return Object.keys(entries).length ? entries : undefined;
}

function normalizeObservationPersona(raw: any): ObservationPersonaBreakdown {
  const observation_count = Number(raw?.observation_count ?? 0);
  return {
    observation_count: Number.isFinite(observation_count) ? observation_count : 0,
    dialog_acts: normalizeObservationDistribution(raw?.dialog_acts ?? {}),
  };
}

function normalizeObservationWindows(raw: any): Record<string, ObservationWindowMetrics> | undefined {
  if (!raw || typeof raw !== 'object') {
    return undefined;
  }
  const normalized: Record<string, ObservationWindowMetrics> = {};
  for (const [key, value] of Object.entries(raw)) {
    if (value && typeof value === 'object') {
      normalized[String(key)] = normalizeObservationWindowMetrics(value);
    }
  }
  return Object.keys(normalized).length ? normalized : undefined;
}

export async function fetchUnabridged(userId: string): Promise<UnabridgedSnapshot> {
  const params = new URLSearchParams({ user_id: userId });
  const response = await ensureOk(
    await fetch(`${CORE_API_BASE}/ui/unabridged?${params.toString()}`, {
      headers: { Accept: 'application/json' }
    })
  );
  const payload = await response.json();
  const traits = Array.isArray(payload?.traits) ? payload.traits : [];
  return {
    user_id: String(payload.user_id ?? userId),
    count: Number(payload.count ?? traits.length),
    traits: traits.map((trait: any) => ({
      trait_id: String(trait.trait_id ?? ''),
      value: trait.value ?? trait.resolved_value ?? null,
      ucn: trait.ucn ?? null,
      reasons: Array.isArray(trait.reasons) ? trait.reasons.map(String) : [],
      last_observed: trait.last_observed ?? null,
      metadata: trait.metadata ?? {},
      badges: Array.isArray(trait.badges) ? trait.badges.map(String) : []
    }))
  };
}

export interface NudgePolicyEntry {
  allowed: boolean;
  reason: string | null;
}

export interface NudgePolicy {
  accept: NudgePolicyEntry;
  dismiss: NudgePolicyEntry;
  undo: NudgePolicyEntry;
}

export type NudgeListStatus = 'all' | 'new' | 'read';

export interface FetchNudgesOptions {
  status?: NudgeListStatus;
  limit?: number;
  sort?: 'new' | 'old';
}

export interface NudgeItem {
  id: string;
  kind: string;
  text: string;
  created_ts: string;
  status: string;
  ttl_minutes: number;
  snooze_minutes: number;
  metadata?: Record<string, unknown>;
  policy?: NudgePolicy;
}

function normalizeNudgePolicy(raw: any): NudgePolicy {
  return {
    accept: normalizeActionPolicy(raw?.accept),
    dismiss: normalizeActionPolicy(raw?.dismiss),
    undo: normalizeActionPolicy(raw?.undo)
  };
}

function normalizeNudge(raw: any): NudgeItem {
  return {
    id: String(raw?.id ?? ''),
    kind: String(raw?.kind ?? 'general'),
    text: String(raw?.text ?? ''),
    created_ts: String(raw?.created_ts ?? ''),
    status: String(raw?.status ?? 'pending'),
    ttl_minutes: Number(raw?.ttl_minutes ?? 0),
    snooze_minutes: Number(raw?.snooze_minutes ?? 0),
    metadata: raw?.metadata ?? {},
    policy: normalizeNudgePolicy(raw?.policy ?? {})
  };
}

function normalizeNudgeListEntry(raw: any, userId: string, index: number): NudgeItem {
  const fallbackId = `${userId || 'user'}_nudge_${index + 1}`;
  const id = String(raw?.id ?? fallbackId);
  const statusRaw = String(raw?.status ?? 'new').toLowerCase();
  const normalizedStatus = NUDGE_COMPLETED_STATUSES.has(statusRaw) ? 'completed' : 'pending';
  const title = raw?.title != null ? String(raw.title) : 'Coach nudge';
  const body = raw?.body != null ? String(raw.body) : '';
  const createdIso = ensureIsoFromMillis(raw?.ts ?? raw?.created_ts ?? raw?.created_at);
  const metadata: Record<string, unknown> = {
    ...(raw?.meta && typeof raw.meta === 'object' ? raw.meta : {}),
    title,
  };
  if (body) {
    metadata.body = body;
  }
  metadata.original_status = statusRaw;

  const policyRaw = raw?.policy && typeof raw.policy === 'object' ? raw.policy : {};

  return normalizeNudge({
    id,
    kind: raw?.kind ?? 'coach',
    text: body || title,
    created_ts: createdIso,
    status: normalizedStatus,
    ttl_minutes: typeof raw?.ttl_minutes === 'number' ? raw.ttl_minutes : 0,
    snooze_minutes: typeof raw?.snooze_minutes === 'number' ? raw.snooze_minutes : 0,
    metadata,
    policy: {
      accept: policyRaw.accept ?? { allowed: true, reason: null },
      dismiss: policyRaw.dismiss ?? { allowed: true, reason: null },
      undo: policyRaw.undo ?? { allowed: false, reason: null }
    }
  });
}

export async function fetchNudges(userId: string, options: FetchNudgesOptions = {}): Promise<NudgeItem[]> {
  const trimmedUser = userId.trim();
  if (!trimmedUser) {
    return [];
  }

  const params = new URLSearchParams({ user_id: trimmedUser });
  if (options.limit != null) {
    params.set('limit', String(options.limit));
  }
  if (options.status && options.status !== 'all') {
    params.set('status', options.status);
  }
  if (options.sort) {
    params.set('sort', options.sort);
  }

  const response = await ensureOk(
    await fetch(`${CORE_API_BASE}/ui/nudges/list?${params.toString()}`, {
      headers: { Accept: 'application/json' }
    })
  );
  const payload = await response.json();
  const items = Array.isArray(payload?.items) ? payload.items : [];
  const normalized = items.map((entry: any, index: number) =>
    normalizeNudgeListEntry(entry, trimmedUser, index)
  );
  writeCache('nudges', trimmedUser, normalized);
  return normalized;
}

export type NudgeAction = 'accept' | 'dismiss' | 'undo';

export interface NudgeActionResponse {
  ok: boolean;
  nudge?: NudgeItem;
  reason?: string | null;
}

export async function actOnNudge(params: {
  userId: string;
  id: string;
  action: NudgeAction;
}): Promise<NudgeActionResponse> {
  const response = await ensureOk(
    await fetch(`${CORE_API_BASE}/ui/nudges/act`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json'
      },
      body: JSON.stringify({
        user_id: params.userId,
        id: params.id,
        action: params.action
      })
    })
  );
  const payload = await response.json();
  const result: NudgeActionResponse = {
    ok: Boolean(payload?.ok),
    reason: payload?.reason ?? null
  };
  if (payload?.nudge) {
    result.nudge = normalizeNudge(payload.nudge);
  }
  return result;
}

export interface TraitTimelineEntry {
  ts: string;
  source: string;
  reason?: string | null;
  value?: unknown;
  ucn?: number | null;
  delta_ucn?: number | null;
}

export async function fetchTraitTimeline(userId: string, traitId: string, limit = 50): Promise<TraitTimelineEntry[]> {
  const params = new URLSearchParams({ user_id: userId, trait_id: traitId, limit: String(limit) });
  const response = await ensureOk(
    await fetch(`${CORE_API_BASE}/ui/trait_timeline?${params.toString()}`, {
      headers: { Accept: 'application/json' }
    })
  );
  const payload = await response.json();
  const entries = Array.isArray(payload?.entries) ? payload.entries : [];
  return entries.map((entry: any) => ({
    ts: String(entry?.ts ?? ''),
    source: String(entry?.source ?? 'unknown'),
    reason: entry?.reason != null ? String(entry.reason) : null,
    value: entry?.value,
    ucn: entry?.ucn ?? null,
    delta_ucn: entry?.delta_ucn ?? null
  }));
}

export interface SnapshotResponse {
  ok: boolean;
  path: string;
  version: string;
  bundle: Record<string, unknown>;
  filename?: string;
  download_url?: string | null;
}

export async function snapshotUser(userId: string): Promise<SnapshotResponse> {
  const response = await ensureOk(
    await fetch(`${CORE_API_BASE}/ui/snapshot`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json'
      },
      body: JSON.stringify({ user_id: userId })
    })
  );
  const payload = await response.json();
  return {
    ok: Boolean(payload?.ok),
    path: String(payload?.path ?? ''),
    version: String(payload?.version ?? ''),
    bundle: payload?.bundle ?? {},
    filename: payload?.filename ? String(payload.filename) : undefined,
    download_url: payload?.download_url ?? null
  };
}

export interface QuickSnapshotMetadata {
  ok: boolean;
  filename?: string;
  version?: string;
  download_url?: string | null;
  snapshot_path?: string | null;
}

export async function createSnapshotMetadata(userId: string): Promise<QuickSnapshotMetadata> {
  const trimmed = userId.trim();
  if (!trimmed) {
    throw new ApiError('User id required for snapshot', 400);
  }
  const params = new URLSearchParams({ user_id: trimmed });
  const response = await ensureOk(
    await fetch(`${CORE_API_BASE}/ui/snapshots/create?${params.toString()}`, {
      method: 'POST',
      headers: {
        Accept: 'application/json'
      }
    })
  );
  const payload = await response.json();
  return {
    ok: Boolean(payload?.ok),
    filename: payload?.filename ? String(payload.filename) : undefined,
    version: payload?.version ? String(payload.version) : undefined,
    download_url: payload?.download_url ?? null,
    snapshot_path: payload?.snapshot_path ?? null
  };
}

interface SendChatOptions {
  stream?: boolean;
  onDelta?: (delta: string) => void;
  signal?: AbortSignal;
}

export async function sendChat(
  params: {
    userId: string;
    persona: string;
    text: string;
    clientTs: number;
    provider?: ChatProviderSettings;
  },
  options: SendChatOptions = {}
): Promise<ChatSendResponse> {
  const streamRequested = options.stream ?? false;
  const query = streamRequested ? '?stream=1' : '';
  let response: Response;
  try {
    const body: Record<string, unknown> = {
      user_id: params.userId,
      persona: params.persona,
      text: params.text,
      client_ts: params.clientTs
    };
    const providerPayload = buildProviderRequestPayload(params.provider);
    if (providerPayload) {
      body.provider = providerPayload;
    }
    response = await ensureOk(
      await fetch(`${CORE_API_BASE}/ui/chat/send${query}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: streamRequested ? 'text/event-stream' : 'application/json'
        },
        body: JSON.stringify(body),
        signal: options.signal
      })
    );
  } catch (error) {
    if (isApiError(error)) {
      throw error;
    }
    throw error;
  }

  if (streamRequested && isEventStream(response)) {
    return consumeEventStream(response, options.onDelta);
  }

  // Fallback to JSON response (non-streaming or stream disabled)
  const payload = await response.json();
  const rawTs = Number(payload?.ts);
  return {
    message_id: String(payload?.message_id ?? ''),
    persona: String(payload?.persona ?? ''),
    text: String(payload?.text ?? ''),
    ts: Number.isFinite(rawTs) ? rawTs : Date.now(),
    provider: typeof payload?.provider === 'string' ? payload.provider : undefined,
    provider_settings: normalizeProviderSettings(
      payload?.provider_settings ?? payload?.providerSettings
    )
  };
}

export interface RecordChatTurnParams {
  userId: string;
  persona: string;
  userText: string;
  assistantText: string;
  clientMessageId: string;
  assistantMessageId?: string;
  personaLabel?: string;
  userTs?: number;
  assistantTs?: number;
  provider?: string;
  providerSettings?: ChatProviderSettings;
}

export async function recordChatTurn(params: RecordChatTurnParams): Promise<void> {
  const trimmedUser = params.userId?.trim() ?? '';
  const trimmedPersona = params.persona?.trim() ?? '';
  if (!trimmedUser || !trimmedPersona) {
    return;
  }

  const payload: Record<string, unknown> = {
    user_id: trimmedUser,
    persona: trimmedPersona,
    user_text: params.userText ?? '',
    assistant_text: params.assistantText ?? '',
    client_message_id: params.clientMessageId ?? '',
    source: 'react_ui',
  };

  if (params.personaLabel) {
    payload.persona_label = params.personaLabel;
  }
  if (params.assistantMessageId) {
    payload.assistant_message_id = params.assistantMessageId;
  }
  if (typeof params.userTs === 'number' && Number.isFinite(params.userTs)) {
    payload.user_ts = params.userTs;
  }
  if (typeof params.assistantTs === 'number' && Number.isFinite(params.assistantTs)) {
    payload.assistant_ts = params.assistantTs;
  }
  if (params.provider) {
    payload.provider = params.provider;
  }
  if (params.providerSettings && Object.keys(params.providerSettings).length > 0) {
    payload.provider_settings = params.providerSettings;
  }

  try {
    const response = await fetch(`${CORE_API_BASE}/ui/chat/turn`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      if (response.status === 404) {
        return;
      }
      let detail: unknown = null;
      try {
        detail = await response.json();
      } catch (error) {
        detail = null;
      }
      console.warn('Failed to record chat turn', response.status, detail);
    }
  } catch (error) {
    console.warn('Failed to record chat turn', error);
  }
}

function isEventStream(response: Response): boolean {
  const contentType = response.headers.get('content-type') ?? '';
  return contentType.includes('text/event-stream') && typeof ReadableStream !== 'undefined';
}

async function consumeEventStream(response: Response, onDelta?: (delta: string) => void): Promise<ChatSendResponse> {
  if (!response.body) {
    throw new Error('Stream ended before data arrived.');
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';
  let finalPayload: ChatSendResponse | null = null;
  let encounteredError: { message: string; status?: number; payload: any } | null = null;

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    buffer = processSseBuffer(buffer, (data) => {
      if (encounteredError || finalPayload) {
        return;
      }
      if (data.error && !encounteredError) {
        const detail = typeof data.detail === 'string' ? data.detail : undefined;
        const errorMessage = detail || String(data.error || 'Provider error');
        encounteredError = {
          message: errorMessage,
          status: typeof data.status === 'number' ? data.status : undefined,
          payload: data
        };
        return;
      }
      if (data.delta && onDelta) {
        onDelta(String(data.delta));
      }
      if (data.done) {
        const rawTs = Number(data.ts);
        finalPayload = {
          message_id: String(data.message_id ?? ''),
          persona: String(data.persona ?? ''),
          text: String(data.text ?? ''),
          ts: Number.isFinite(rawTs) ? rawTs : Date.now(),
          provider: typeof data.provider === 'string' ? data.provider : undefined,
          provider_settings: normalizeProviderSettings(data.provider_settings ?? data.providerSettings)
        };
      }
    });
    if (encounteredError) {
      await reader.cancel();
      break;
    }
    if (finalPayload) {
      await reader.cancel();
      break;
    }
  }

  if (encounteredError) {
    const e = encounteredError as { status?: number; message?: string; payload?: any } | undefined;
    const status = e?.status ?? 500;
    throw new ApiError(e?.message ?? 'Provider error', status, e?.payload);
  }
  if (!finalPayload) {
    throw new Error('Stream ended without a completion payload.');
  }
  return finalPayload;
}

function processSseBuffer(buffer: string, handle: (payload: any) => void): string {
  let working = buffer;
  let separatorIndex = working.indexOf('\n\n');
  while (separatorIndex !== -1) {
    const rawEvent = working.slice(0, separatorIndex);
    working = working.slice(separatorIndex + 2);
    const dataLines = rawEvent
      .split('\n')
      .map((line) => line.trim())
      .filter((line) => line.startsWith('data:'));
    for (const line of dataLines) {
      const jsonText = line.slice(5).trim();
      if (!jsonText) {
        continue;
      }
      try {
        const parsed = JSON.parse(jsonText);
        handle(parsed);
      } catch (error) {
        console.warn('Failed to parse SSE chunk', error);
      }
    }
    separatorIndex = working.indexOf('\n\n');
  }
  return working;
}

function buildProviderRequestPayload(options?: ChatProviderSettings): Record<string, unknown> | undefined {
  if (!options) {
    return undefined;
  }
  const payload: Record<string, unknown> = {};
  if (typeof options.model === 'string' && options.model.trim()) {
    payload.model = options.model.trim();
  }
  if (typeof options.temperature === 'number' && Number.isFinite(options.temperature)) {
    payload.temperature = options.temperature;
  }
  if (typeof options.maxTokens === 'number' && Number.isFinite(options.maxTokens) && options.maxTokens > 0) {
    payload.max_tokens = Math.trunc(options.maxTokens);
  }
  return Object.keys(payload).length ? payload : undefined;
}

function normalizeProviderSettings(value: any): ChatProviderSettings | undefined {
  if (!value || typeof value !== 'object') {
    return undefined;
  }
  const normalized: ChatProviderSettings = {};
  if (typeof value.model === 'string' && value.model.trim()) {
    normalized.model = value.model.trim();
  }
  const temperatureCandidate = value.temperature;
  if (typeof temperatureCandidate === 'number' && Number.isFinite(temperatureCandidate)) {
    normalized.temperature = temperatureCandidate;
  }
  const maxTokensCandidate = value.max_tokens ?? value.maxTokens;
  if (typeof maxTokensCandidate === 'number' && Number.isFinite(maxTokensCandidate) && maxTokensCandidate > 0) {
    normalized.maxTokens = Math.trunc(maxTokensCandidate);
  }
  return Object.keys(normalized).length ? normalized : undefined;
}

const CANONICAL_ORDER = [
  'head_coach',
  'relationship_coach',
  'career_coach',
  'personality_test_coach',
  'chatdna_coach',
  'beliefdna_coach',
  'padna',
  'photo',
  'permission_coach'
] as const;
type CanonicalKey = (typeof CANONICAL_ORDER)[number];

const CANONICAL_DEFAULTS: Record<CanonicalKey, PersonaRosterEntry> = {
  head_coach: {
    key: 'head_coach',
    label: 'Head Coach (Orchestrator)',
    icon: '🧭',
    enabled: true,
    accent_color: null
  },
  relationship_coach: {
    key: 'relationship_coach',
    label: 'Relationship Coach',
    icon: '💞',
    enabled: true,
    accent_color: null
  },
  career_coach: {
    key: 'career_coach',
    label: 'Career Coach',
    icon: '💼',
    enabled: true,
    accent_color: null
  },
  personality_test_coach: {
    key: 'personality_test_coach',
    label: 'Personality Test Coach',
    icon: '🧠',
    enabled: true,
    accent_color: null
  },
  chatdna_coach: {
    key: 'chatdna_coach',
    label: 'ChatDNA Coach',
    icon: '💬',
    enabled: true,
    accent_color: null
  },
  beliefdna_coach: {
    key: 'beliefdna_coach',
    label: 'BeliefDNA Coach',
    icon: '🔮',
    enabled: true,
    accent_color: null
  },
  padna: {
    key: 'padna',
    label: 'PaDNA Coach',
    icon: '🧬',
    enabled: true,
    accent_color: null
  },
  photo: {
    key: 'photo',
    label: 'Photo Coach',
    icon: '📸',
    enabled: true,
    accent_color: null
  },
  permission_coach: {
    key: 'permission_coach',
    label: 'Permission Coach',
    icon: '🔐',
    enabled: true,
    accent_color: null
  }
};

const PERSONA_ALIASES: Record<string, CanonicalKey> = {
  head_coach: 'head_coach',
  'head coach': 'head_coach',
  headcoach: 'head_coach',
  hc: 'head_coach',
  relationship_coach: 'relationship_coach',
  'relationship coach': 'relationship_coach',
  rc: 'relationship_coach',
  relationship: 'relationship_coach',
  career_coach: 'career_coach',
  'career coach': 'career_coach',
  career: 'career_coach',
  personality_test_coach: 'personality_test_coach',
  'personality test coach': 'personality_test_coach',
  'personality coach': 'personality_test_coach',
  ptc: 'personality_test_coach',
  chatdna_coach: 'chatdna_coach',
  'chatdna coach': 'chatdna_coach',
  chatdna: 'chatdna_coach',
  beliefdna_coach: 'beliefdna_coach',
  'beliefdna coach': 'beliefdna_coach',
  beliefdna: 'beliefdna_coach',
  padna: 'padna',
  padna_coach: 'padna',
  'padna coach': 'padna',
  rendering: 'padna',
  'rendering coach': 'padna',
  avatar: 'padna',
  photo: 'photo',
  photo_coach: 'photo',
  'photo coach': 'photo',
  permission_coach: 'permission_coach',
  'permission coach': 'permission_coach',
  permissions: 'permission_coach'
};

type RawPersonaEntry = {
  key?: string;
  id?: string;
  label?: string;
  title?: string;
  name?: string;
  icon?: string;
  enabled?: boolean;
  accent_color?: string;
  color?: string;
};

function normalizePersonaRoster(entries: RawPersonaEntry[]): PersonaRosterEntry[] {
  const merged: Partial<Record<CanonicalKey, PersonaRosterEntry>> = {};

  for (const entry of entries) {
    const rawKey = String(entry.key ?? entry.id ?? '').trim().toLowerCase();
    const canonicalKey = PERSONA_ALIASES[rawKey];
    if (!canonicalKey) {
      continue;
    }
    const defaultPersona = CANONICAL_DEFAULTS[canonicalKey];
    const apiEnabled = typeof entry.enabled === 'boolean' ? entry.enabled : true;
    const candidate: PersonaRosterEntry = {
      key: defaultPersona.key,
      label: defaultPersona.label,
      icon: entry.icon ? String(entry.icon) : defaultPersona.icon,
      enabled: apiEnabled,
      accent_color: entry.accent_color ?? entry.color ?? null
    };
    const existing = merged[canonicalKey];
    if (existing) {
      merged[canonicalKey] = {
        key: defaultPersona.key,
        label: defaultPersona.label,
        icon: existing.icon || candidate.icon,
        enabled: existing.enabled && candidate.enabled,
        accent_color: candidate.accent_color ?? existing.accent_color ?? null
      };
    } else {
      merged[canonicalKey] = candidate;
    }
  }

  return CANONICAL_ORDER.map((key) => {
    const defaultPersona = CANONICAL_DEFAULTS[key];
    const mergedPersona = merged[key];
    if (mergedPersona) {
      return {
        key: defaultPersona.key,
        label: defaultPersona.label,
        icon: mergedPersona.icon || defaultPersona.icon,
        enabled: mergedPersona.enabled,
        accent_color: mergedPersona.accent_color ?? null
      };
    }
    return { ...defaultPersona };
  });
}

export async function deleteUserMedia(userId: string, mediaId: string): Promise<void> {
  const trimmedUser = userId.trim();
  const trimmedMedia = mediaId.trim();
  if (!trimmedUser || !trimmedMedia) {
    throw new ApiError('user_id and media_id are required for delete.', 400);
  }
  const params = new URLSearchParams({ user_id: trimmedUser, media_id: trimmedMedia });
  await ensureOk(
    await fetch(`${CORE_API_BASE}/ui/media/delete?${params.toString()}`, {
      method: 'DELETE',
      headers: { Accept: 'application/json' }
    })
  );
}

export interface RescoreUpdatedTrait {
  trait: string;
  old_rr: number;
  new_rr: number;
  curiosity: number;
}

export interface RescoreNowResponse {
  ok: boolean;
  updated_traits: RescoreUpdatedTrait[];
  event_ref?: string | null;
}

export async function rescoreNow(params: {
  userId: string;
  text: string;
  persona?: string;
}): Promise<RescoreNowResponse> {
  const trimmedUser = params.userId.trim();
  const trimmedText = params.text.trim();
  if (!trimmedUser || !trimmedText) {
    throw new ApiError('user_id and text are required for rescore.', 400);
  }

  const payload: Record<string, unknown> = {
    user_id: trimmedUser,
    text: trimmedText,
  };
  if (params.persona) {
    payload.persona = params.persona;
  }

  const response = await ensureOk(
    await fetch(`${CORE_API_BASE}/ui/coach/rescore_now`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify(payload),
    })
  );

  const body = await response.json();
  return {
    ok: Boolean(body?.ok),
    updated_traits: Array.isArray(body?.updated_traits) ? body.updated_traits : [],
    event_ref: body?.event_ref ?? null,
  };
}

export interface IngestTextResponse {
  success: boolean;
  event_id?: string;
  user_id: string;
  rescore?: {
    ok: boolean;
    user_id: string;
    rr_by_trait?: Record<string, number>;
    curiosity_by_trait?: Record<string, number>;
    traits_updated?: number;
    timestamp?: string;
  };
}

/**
 * Ingest text programmatically into Core for a user.
 * This is for silent ingestion (e.g., onboarding data, Life OS entries, photo metadata)
 * that should be processed immediately without showing in the chat transcript.
 *
 * Core will automatically extract traits and rescore the user.
 */
export async function ingestText(params: {
  userId: string;
  text: string;
  source?: string;
}): Promise<IngestTextResponse> {
  const trimmedUser = params.userId.trim();
  const trimmedText = params.text.trim();
  if (!trimmedUser || !trimmedText) {
    throw new ApiError('user_id and text are required for ingestion.', 400);
  }

  const payload: Record<string, unknown> = {
    user_id: trimmedUser,
    text: trimmedText,
    source: params.source || 'web_ui_programmatic',
  };

  const response = await ensureOk(
    await fetch(`${CORE_API_BASE}/core/api/ingest_text`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify(payload),
    })
  );

  const body = await response.json();
  return {
    success: Boolean(body?.success),
    event_id: body?.event_id,
    user_id: body?.user_id || trimmedUser,
    rescore: body?.rescore,
  };
}

export interface RevertLastResponse {
  ok: boolean;
  reverted_count?: number;
  message?: string;
}

export async function revertLastRescore(userId: string): Promise<RevertLastResponse> {
  const trimmedUser = userId.trim();
  if (!trimmedUser) {
    throw new ApiError('user_id is required for revert.', 400);
  }

  const response = await ensureOk(
    await fetch(`${CORE_API_BASE}/ui/trait/revert_last`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify({ user_id: trimmedUser }),
    })
  );

  const body = await response.json();
  return {
    ok: Boolean(body?.ok),
    reverted_count: body?.reverted_count,
    message: body?.message,
  };
}

export interface OverrideTraitResponse {
  ok: boolean;
  trait_id?: string;
  new_value?: unknown;
  old_rr?: number;
  new_rr?: number;
  curiosity?: number;
  event_ref?: string;
}

export async function overrideTrait(params: {
  userId: string;
  traitId: string;
  value: unknown;
}): Promise<OverrideTraitResponse> {
  const trimmedUser = params.userId.trim();
  const trimmedTrait = params.traitId.trim();
  if (!trimmedUser || !trimmedTrait) {
    throw new ApiError('user_id and trait_id are required for override.', 400);
  }

  const response = await ensureOk(
    await fetch(`${CORE_API_BASE}/ui/trait/override`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify({
        user_id: trimmedUser,
        trait_id: trimmedTrait,
        value: params.value,
      }),
    })
  );

  const body = await response.json();
  return {
    ok: Boolean(body?.ok),
    trait_id: body?.trait_id,
    new_value: body?.new_value,
    old_rr: body?.old_rr,
    new_rr: body?.new_rr,
    curiosity: body?.curiosity,
    event_ref: body?.event_ref,
  };
}
