import { DEVX_API_BASE } from './env'

const API_BASE = `${DEVX_API_BASE}/semantics`

export class SemanticsStoreUnavailableError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'SemanticsStoreUnavailableError'
  }
}

async function handleResponse(response: Response) {
  if (response.status === 503) {
    const detail = await response.json().catch(() => ({}))
    throw new SemanticsStoreUnavailableError(detail?.detail || 'Trait semantics store is unavailable.')
  }

  if (!response.ok) {
    const text = await response.text()
    throw new Error(text || `Semantics API error (${response.status})`)
  }

  return response.json()
}

export interface SemanticsResult {
  path: string
  semantics: Record<string, any> | null
}

export interface ProposeResponse {
  path: string
  accepted: boolean
  cr_id?: string
  errors?: string[]
}

export interface ValidateResponse {
  cr_id: string
  valid: boolean
  errors: string[]
}

export interface ApplyResponse {
  cr_id: string
  applied: boolean
  path?: string
  errors?: string[]
  requires_approval?: boolean
}

export interface DiagnosticsResponse {
  store_path: string
  registry_path: string
  schema_path: string
  registry_exists: boolean
  entry_count: number
}

export const semanticsApi = {
  async getSemantics(path: string): Promise<SemanticsResult> {
    const response = await fetch(`${API_BASE}/get?path=${encodeURIComponent(path)}`)
    return handleResponse(response)
  },

  async proposeChange(path: string, draft: Record<string, any>, notes?: string): Promise<ProposeResponse> {
    const response = await fetch(`${API_BASE}/propose`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path, draft, notes }),
    })
    return handleResponse(response)
  },

  async validateCR(crId: string): Promise<ValidateResponse> {
    const response = await fetch(`${API_BASE}/validate?cr_id=${encodeURIComponent(crId)}`)
    return handleResponse(response)
  },

  async applyCR(crId: string): Promise<ApplyResponse> {
    const response = await fetch(`${API_BASE}/apply`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cr_id: crId }),
    })
    return handleResponse(response)
  },

  async getSchema(): Promise<Record<string, any>> {
    const response = await fetch(`${API_BASE}/schema`)
    return handleResponse(response)
  },

  async diagnostics(): Promise<DiagnosticsResponse> {
    const response = await fetch(`${API_BASE}/diagnostics`)
    return handleResponse(response)
  },

  async seed(path: string): Promise<{ status: string; cr_id?: string }> {
    const response = await fetch(`${API_BASE}/seed`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path }),
    })
    return handleResponse(response)
  },
}

export default semanticsApi
