const normalizeBase = (value: string | undefined, fallback: string) => {
  const base = (value && value.trim()) || fallback
  return base.replace(/\/+$/, '')
}

export const DEVX_API_BASE = normalizeBase(
  (import.meta.env as Record<string, string> | undefined)?.VITE_DEVX_API_BASE,
  'http://localhost:8100/devx/api'
)

export const CORE_API_BASE = normalizeBase(
  (import.meta.env as Record<string, string> | undefined)?.VITE_CORE_API_BASE,
  'http://localhost:8015'
)

export const devxUrl = (path: string) => `${DEVX_API_BASE}${path.startsWith('/') ? path : `/${path}`}`
export const coreUrl = (path: string) => `${CORE_API_BASE}${path.startsWith('/') ? path : `/${path}`}`

export const getApiBase = () => DEVX_API_BASE
