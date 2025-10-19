import { DEVX_API_BASE, devxUrl } from './env'

const API_ROOT = `${DEVX_API_BASE}/holistic`

async function handleResponse(response: Response) {
  if (!response.ok) {
    const text = await response.text()
    throw new Error(text || `Holistic API error (${response.status})`)
  }
  return response.json()
}

export interface HolisticResult {
  user_id: string
  generated_at: string
  counts: {
    containers: number
    evidence: number
    derived: number
  }
  rr: {
    overall_rr: number
    by_domain: Record<string, number>
  }
  top_low_rr_paths: { path: string; rr: number }[]
  notes?: string
}

export interface HolisticHistoryEntry {
  generated_at?: string
  counts?: Record<string, number>
  rr?: Record<string, unknown>
  path: string
}

export interface HolisticHistoryResponse {
  user_id: string
  entries: HolisticHistoryEntry[]
}

export interface HolisticProcessResponse {
  job_id: string
  status: string
  results: { user_id: string; status: string; reason?: string; generated_at?: string }[]
}

export const holisticApi = {
  async getResult(userId: string): Promise<HolisticResult> {
    const response = await fetch(`${API_ROOT}/get?user_id=${encodeURIComponent(userId)}`)
    return handleResponse(response)
  },

  async getHistory(userId: string, limit = 10): Promise<HolisticHistoryResponse> {
    const response = await fetch(
      `${API_ROOT}/history?user_id=${encodeURIComponent(userId)}&limit=${limit}`
    )
    return handleResponse(response)
  },

  async processJob(jobId: string): Promise<HolisticProcessResponse> {
    const response = await fetch(devxUrl('/users/batch/run-holistic/process'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job_id: jobId }),
    })
    return handleResponse(response)
  },
}

export default holisticApi
