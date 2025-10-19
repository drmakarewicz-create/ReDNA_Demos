import { CORE_API_BASE } from './env'

const API_BASE = CORE_API_BASE

export interface ActivationNode {
  id: string
  label: string
  active: boolean
  weight: number
}

export interface ActivationEdge {
  from: string
  to: string
  strength: number
}

export interface ActivationSnapshot {
  ts: string
  user_id: string
  context_version: number
  active_coach_id: string
  nodes: ActivationNode[]
  edges: ActivationEdge[]
  meta?: Record<string, any>
}

export interface ChorusSection {
  text: string
  hash: string
  label?: string
}

export interface ChorusRuntime {
  json: Record<string, any>
  hash: string
}

export interface ChorusPayload {
  ok: boolean
  head_coach: ChorusSection
  augment: ChorusSection
  runtime: ChorusRuntime
  merged: ChorusSection
  context_version: number
  requested_context_version?: number | null
  active_coach_id: string
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.text().catch(() => '')
    throw new Error(`HTTP ${response.status}: ${response.statusText} ${body}`)
  }
  return response.json() as Promise<T>
}

function is404OrEmpty(error: Error): boolean {
  return error.message.includes('HTTP 404') || error.message.includes('not found')
}

export async function getCoachBrain(userId: string, contextVersion?: number): Promise<ActivationSnapshot | null> {
  const params = new URLSearchParams({ user_id: userId })
  if (typeof contextVersion === 'number') {
    params.append('context_version', String(contextVersion))
  }

  try {
    const response = await fetch(`${API_BASE}/coach/brain?${params.toString()}`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
    })

    const data = await handleResponse<{ ok: boolean; snapshot: ActivationSnapshot }>(response)
    if (!data.ok || !data.snapshot) {
      return null
    }
    return data.snapshot
  } catch (err) {
    if (err instanceof Error && is404OrEmpty(err)) {
      return null
    }
    throw err
  }
}

export async function getChorus(userId: string, contextVersion?: number): Promise<ChorusPayload> {
  const params = new URLSearchParams({ user_id: userId })
  if (typeof contextVersion === 'number') {
    params.append('context_version', String(contextVersion))
  }

  const response = await fetch(`${API_BASE}/coach/chorus?${params.toString()}`, {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
  })

  return handleResponse<ChorusPayload>(response)
}
