import { devxUrl } from './env'

export type ReferenceSource = 'SYNTHETIC' | 'ACTUAL'
export type ReferenceUniverse = 'combined' | 'low' | 'medium' | 'high'

export interface ReferenceConfig {
  source: ReferenceSource
  universe: ReferenceUniverse
  cohort_keys: string[]
  updated_at?: string | null
}

export interface ReferenceConfigResponse {
  config: ReferenceConfig
  restart_hint?: string
  config_path?: string
}

export interface ReferenceStatusResponse {
  traitId: string
  core: Record<string, unknown>
  config: ReferenceConfig
  raw: Record<string, unknown>
}

export interface ReferenceSamplesResponse {
  traitId: string
  source?: string
  n_samples?: number
  generated_at?: string
  fallback_reason?: string
  config: ReferenceConfig
  core?: Record<string, unknown>
  raw: Record<string, unknown>
}

const handleResponse = async (response: Response) => {
  if (!response.ok) {
    let detail: string | undefined
    try {
      const payload = await response.json()
      detail =
        typeof payload?.detail === 'string'
          ? payload.detail
          : typeof payload?.error === 'string'
          ? payload.error
          : Array.isArray(payload?.errors)
          ? payload.errors.join(', ')
          : undefined
    } catch {
      detail = undefined
    }
    throw new Error(detail || `Request failed (HTTP ${response.status})`)
  }
  return response.json()
}

export const fetchReferenceConfig = async (): Promise<ReferenceConfigResponse> => {
  const response = await fetch(devxUrl('/rr/reference/config'), {
    cache: 'no-store',
  })
  const payload = await handleResponse(response)
  const config = normalizeConfig(payload?.config)
  return {
    config,
    restart_hint: payload?.restart_hint,
    config_path: payload?.config_path,
  }
}

export const saveReferenceConfig = async (
  config: ReferenceConfig
): Promise<ReferenceConfigResponse & { message?: string }> => {
  const response = await fetch(devxUrl('/rr/reference/config'), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      source: config.source,
      universe: config.universe,
      cohort_keys: config.cohort_keys,
    }),
  })
  const payload = await handleResponse(response)
  const normalized = normalizeConfig(payload?.config)
  return {
    config: normalized,
    restart_hint: payload?.restart_hint,
    config_path: payload?.config_path,
    message: payload?.message,
  }
}

export const fetchReferenceStatus = async (
  traitId: string,
  cohort?: string
): Promise<ReferenceStatusResponse> => {
  const url = new URL(devxUrl('/rr/reference/status'))
  url.searchParams.set('trait_id', traitId)
  if (cohort && cohort.trim().length > 0) {
    url.searchParams.set('cohort', cohort.trim())
  }

  const payload = await handleResponse(await fetch(url.toString(), { cache: 'no-store' }))
  const config = normalizeConfig(payload?.config)
  return {
    traitId: payload?.trait_id ?? traitId,
    core: (payload?.core ?? {}) as Record<string, unknown>,
    config,
    raw: payload ?? {},
  }
}

export const fetchReferenceSamples = async (traitId: string): Promise<ReferenceSamplesResponse> => {
  const url = new URL(devxUrl('/rr/reference/samples'))
  url.searchParams.set('trait_id', traitId)

  const payload = await handleResponse(await fetch(url.toString(), { cache: 'no-store' }))
  const config = normalizeConfig(payload?.config)

  const corePayload =
    payload?.core && typeof payload.core === 'object' ? (payload.core as Record<string, unknown>) : undefined

  return {
    traitId: payload?.trait_id ?? traitId,
    source: typeof payload?.source === 'string' ? payload.source : undefined,
    n_samples: typeof payload?.n_samples === 'number' ? payload.n_samples : undefined,
    generated_at: typeof payload?.generated_at === 'string' ? payload.generated_at : undefined,
    fallback_reason: typeof payload?.fallback_reason === 'string' ? payload.fallback_reason : undefined,
    config,
    core: corePayload,
    raw: payload ?? {},
  }
}

const normalizeConfig = (input: ReferenceConfig | null | undefined): ReferenceConfig => {
  const safe: ReferenceConfig = {
    source: (input?.source === 'ACTUAL' ? 'ACTUAL' : 'SYNTHETIC') as ReferenceSource,
    universe: isUniverse(input?.universe) ? input!.universe : 'combined',
    cohort_keys: Array.isArray(input?.cohort_keys)
      ? input!.cohort_keys.map((entry) => String(entry).trim()).filter(Boolean)
      : [],
    updated_at: input?.updated_at ?? null,
  }
  if (safe.source !== 'ACTUAL') {
    safe.cohort_keys = []
  }
  return safe
}

const isUniverse = (value: unknown): value is ReferenceUniverse => {
  return value === 'combined' || value === 'low' || value === 'medium' || value === 'high'
}
