/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_DEVX_API_BASE?: string
  readonly VITE_CORE_API_BASE?: string
  readonly VITE_DEVX_AGENT_ADMIN_TOKEN?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
