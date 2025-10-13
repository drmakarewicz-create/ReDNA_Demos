import { devxUrl } from './env'

const CAP_TOKEN_KEY = 'DEVX_CAP_TOKEN'
const CAP_EXPIRES_KEY = 'DEVX_CAP_EXPIRES_AT'
const CAP_META_KEY = 'DEVX_CAP_META'

interface CapabilityCacheEntry {
  token: string
  exp: number
}

const cache = new Map<string, Map<string, CapabilityCacheEntry>>()
const ONE_MINUTE = 60_000
const DEFAULT_TTL_MINUTES = 5

function devxAgentAdminToken(): string {
  const metaEnv: Record<string, string> | undefined = (import.meta as any)?.env
  const envToken = metaEnv?.VITE_DEVX_AGENT_ADMIN_TOKEN || ''
  return envToken.trim() || 'devx-local'
}

function resolveAdminToken(): string {
  const metaEnv: Record<string, string> | undefined = (import.meta as any)?.env
  const envValue = metaEnv?.VITE_DEVX_ADMIN_TOKEN ?? ''
  if (envValue && envValue.trim()) {
    return envValue.trim()
  }

  if (typeof window !== 'undefined') {
    try {
      const stored = window.localStorage.getItem('DEVX_ADMIN_TOKEN') ?? ''
      if (stored.trim()) {
        return stored.trim()
      }
    } catch {
      // ignore storage access errors
    }
  }

  throw new Error('Admin token missing. Set VITE_DEVX_ADMIN_TOKEN or DEVX_ADMIN_TOKEN in localStorage.')
}

function getUserCache(userId: string): Map<string, CapabilityCacheEntry> {
  let entry = cache.get(userId)
  if (!entry) {
    entry = new Map()
    cache.set(userId, entry)
  }
  return entry
}

function parseExpiry(expiresAt: string | undefined, ttlMinutes: number): number {
  if (expiresAt) {
    const parsed = Date.parse(expiresAt)
    if (!Number.isNaN(parsed)) {
      return parsed
    }
  }
  return Date.now() + ttlMinutes * 60_000
}

export function clearStoredCapabilityToken(): void {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.removeItem(CAP_TOKEN_KEY)
    window.localStorage.removeItem(CAP_EXPIRES_KEY)
    window.localStorage.removeItem(CAP_META_KEY)
  } catch {
    // ignore storage cleanup errors
  }
  ;(window as any).__devxCapToken = undefined
}

export function invalidateCapability(userId: string, scope: string): void {
  const userCache = cache.get(userId)
  if (userCache) {
    userCache.delete(scope)
  }
}

async function requestCapabilityToken(userId: string, scope: string, ttlMinutes: number): Promise<CapabilityCacheEntry> {
  const response = await fetch(devxUrl('/capability/issue'), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-devx-auth': devxAgentAdminToken(),
    },
    body: JSON.stringify({
      user_id: userId,
      scope,
      ttl_minutes: Math.max(1, Math.min(ttlMinutes, DEFAULT_TTL_MINUTES)),
    }),
  })

  if (!response.ok) {
    const detail = await response.text()
    throw new Error(detail || `Capability issue failed (${response.status})`)
  }

  const payload = await response.json()
  const token: string = payload.token
  if (!token) {
    throw new Error('Capability response missing token')
  }

  const ttl = Number(payload.ttl_minutes ?? ttlMinutes)
  const entry: CapabilityCacheEntry = {
    token,
    exp: parseExpiry(payload.expires_at, ttl),
  }

  getUserCache(userId).set(scope, entry)
  return entry
}

export async function getCapabilityToken(userId: string, scope: string, ttlMinutes = DEFAULT_TTL_MINUTES): Promise<string> {
  const userCache = getUserCache(userId)
  const existing = userCache.get(scope)
  if (existing && existing.exp - Date.now() > ONE_MINUTE) {
    return existing.token
  }
  const entry = await requestCapabilityToken(userId, scope, ttlMinutes)
  return entry.token
}

function shouldRetryCapability(response: Response, reason: string): boolean {
  if (response.status !== 401 && response.status !== 403) return false
  return /capability/i.test(reason)
}

export async function authorizedFetch(
  userId: string,
  scope: string,
  input: RequestInfo | URL,
  init: RequestInit = {}
): Promise<Response> {
  const attempt = async (retry: boolean): Promise<Response> => {
    const token = await getCapabilityToken(userId, scope)
    const headers = new Headers(init.headers as HeadersInit | undefined)
    headers.set('X-Capability', token)
    headers.set('x-agent-capability', token)
    const response = await fetch(input, { ...init, headers })

    if (retry && (response.status === 401 || response.status === 403)) {
      const clone = response.clone()
      let detail = ''
      try {
        const data = await clone.json()
        detail = (data && (data.detail || JSON.stringify(data))) || ''
      } catch {
        try {
          detail = await clone.text()
        } catch {
          detail = ''
        }
      }

      if (shouldRetryCapability(response, detail)) {
        invalidateCapability(userId, scope)
        return attempt(false)
      }
    }

    return response
  }

  return attempt(true)
}

export async function issueCapability({
  userId,
  scope,
  ttlMinutes,
  reason,
}: {
  userId: string
  scope: string
  ttlMinutes: number
  reason: string
}): Promise<{ token: string; capability_id: string; expires_at: string }> {
  const admin = resolveAdminToken()

  const response = await fetch(devxUrl('/capability/issue'), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${admin}`,
    },
    body: JSON.stringify({
      user_id: userId,
      scope,
      ttl_minutes: ttlMinutes,
      reason,
    }),
  })

  if (!response.ok) {
    let detail = ''
    try {
      detail = await response.text()
    } catch {
      detail = ''
    }
    throw new Error(detail || `Capability issue failed (${response.status})`)
  }

  const payload = await response.json()
  if (!payload?.token || !payload?.capability_id || !payload?.expires_at) {
    throw new Error('Capability response missing fields')
  }

  if (typeof window !== 'undefined') {
    ;(window as any).__devxCapToken = payload.token
    try {
      window.localStorage.setItem(CAP_TOKEN_KEY, payload.token)
      window.localStorage.setItem(CAP_EXPIRES_KEY, payload.expires_at)
      window.localStorage.setItem(
        CAP_META_KEY,
        JSON.stringify({
          capability_id: payload.capability_id,
          scope,
          expires_at: payload.expires_at,
          user_id: userId,
        })
      )
    } catch {
      // ignore storage errors; token still lives in memory for this tab
    }
  }

  return {
    token: payload.token,
    capability_id: payload.capability_id,
    expires_at: payload.expires_at,
  }
}
