import { DEVX_API_BASE } from './env'

const API_ROOT = `${DEVX_API_BASE}/health`

async function handleResponse(response: Response) {
  if (!response.ok) {
    const text = await response.text()
    throw new Error(text || `Health API error (${response.status})`)
  }
  return response.json()
}

export interface HealthStatusEntry {
  status: string
  ok: boolean
  ms: number | null
  detail?: string
  warning?: string
  reported_status?: string | null
  checked_at: string
}

export interface HealthStatusResponse {
  devx: HealthStatusEntry
  consent: HealthStatusEntry
  core: HealthStatusEntry
}

export interface HealthHistoryEntry {
  ts: string
  devx: { ok: boolean; ms: number | null }
  consent: { ok: boolean; ms: number | null }
  core: { ok: boolean; ms: number | null }
}

export const healthApi = {
  async getStatus(): Promise<HealthStatusResponse> {
    const response = await fetch(`${API_ROOT}/status`)
    return handleResponse(response)
  },

  async getHistory(limit = 100): Promise<{ entries: HealthHistoryEntry[] }> {
    const response = await fetch(`${API_ROOT}/history?limit=${limit}`)
    return handleResponse(response)
  },
}

export default healthApi
