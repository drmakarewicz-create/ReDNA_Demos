import { useEffect, useMemo, useState } from 'react'
import { toast } from 'react-toastify'

import { issueCapability } from '@/lib/capabilityClient'

const SCOPE_OPTIONS = [
  { value: 'core.agent.config', label: 'core.agent.config · Configure Head Coach' },
  { value: 'core.agent.run', label: 'core.agent.run · Execute Head Coach jobs' },
] as const

const TTL_MIN = 5
const TTL_MAX = 240
const DEFAULT_TTL = 30
const DEFAULT_REASON = 'DevX Life OS quick capture'

interface CapabilityTokenModalProps {
  userId: string
  open: boolean
  onClose: () => void
}

type CapabilityResult = {
  token: string
  capability_id: string
  expires_at: string
}

const maskToken = (token: string): string => {
  if (!token) return ''
  if (token.length <= 10) return `${token.slice(0, 2)}****`
  return `${token.slice(0, 4)}****${token.slice(-4)}`
}

const formatCountdown = (expiry: Date): string => {
  const diff = expiry.getTime() - Date.now()
  if (diff <= 0) return 'expired'
  const minutes = Math.floor(diff / 60_000)
  const seconds = Math.floor((diff % 60_000) / 1000)
  if (minutes === 0) {
    return `${seconds}s remaining`
  }
  return `${minutes}m ${seconds.toString().padStart(2, '0')}s remaining`
}

export default function CapabilityTokenModal({ userId, open, onClose }: CapabilityTokenModalProps) {
  const [scope, setScope] = useState<string>(SCOPE_OPTIONS[0].value)
  const [ttlMinutes, setTtlMinutes] = useState<number>(DEFAULT_TTL)
  const [reason, setReason] = useState<string>(DEFAULT_REASON)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<CapabilityResult | null>(null)
  const [countdown, setCountdown] = useState<string>('')

  const expiresAt = useMemo(() => {
    if (!result) return null
    const ts = Date.parse(result.expires_at)
    if (Number.isNaN(ts)) return null
    return new Date(ts)
  }, [result])

  useEffect(() => {
    if (!open) {
      setScope(SCOPE_OPTIONS[0].value)
      setTtlMinutes(DEFAULT_TTL)
      setReason(DEFAULT_REASON)
      setError(null)
      setResult(null)
      setCountdown('')
      setSubmitting(false)
    }
  }, [open])

  useEffect(() => {
    if (!expiresAt) return
    const update = () => setCountdown(formatCountdown(expiresAt))
    update()
    const timer = window.setInterval(update, 1_000)
    return () => window.clearInterval(timer)
  }, [expiresAt])

  if (!open) return null

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (submitting) return

    const ttl = Math.max(TTL_MIN, Math.min(TTL_MAX, Number(ttlMinutes) || DEFAULT_TTL))
    setTtlMinutes(ttl)
    setSubmitting(true)
    setError(null)

    try {
      const payload = await issueCapability({
        userId,
        scope,
        ttlMinutes: ttl,
        reason: reason.trim() || DEFAULT_REASON,
      })
      setResult(payload)
      if (typeof window !== 'undefined') {
        ;(window as any).__devxCapToken = payload.token
        try {
          window.localStorage.setItem('DEVX_CAP_TOKEN', payload.token)
          window.localStorage.setItem('DEVX_CAP_EXPIRES_AT', payload.expires_at)
          window.localStorage.setItem(
            'DEVX_CAP_META',
            JSON.stringify({
              capability_id: payload.capability_id,
              scope,
              expires_at: payload.expires_at,
              user_id: userId,
            })
          )
        } catch {
          // Ignore storage errors; token remains in memory for the current tab.
        }
      }
      toast.success('Capability token issued')
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to issue capability token.'
      setError(message)
    } finally {
      setSubmitting(false)
    }
  }

  const handleCopy = async () => {
    if (!result) return
    try {
      await navigator.clipboard.writeText(result.token)
      toast.success('Capability token copied to clipboard')
    } catch {
      toast.error('Unable to copy token. Copy manually if needed.')
    }
  }

  const shortCapabilityId = result ? `${result.capability_id.slice(0, 8)}…` : ''
  const humanExpiry =
    expiresAt?.toLocaleString(undefined, {
      hour: 'numeric',
      minute: '2-digit',
      second: '2-digit',
      hour12: true,
    }) ?? ''

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-gray-900/60 px-4 py-6">
      <div className="w-full max-w-xl rounded-lg border border-gray-200 bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Generate Capability Token</h2>
            <p className="text-sm text-gray-600">
              Mint a short-lived capability for <span className="font-semibold">{userId}</span>
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-md border border-gray-200 px-2 py-1 text-sm text-gray-600 hover:bg-gray-100"
            type="button"
            disabled={submitting}
          >
            Close
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 px-6 py-5">
          {!result && (
            <>
              <div className="space-y-1">
                <label htmlFor="cap-scope" className="text-sm font-medium text-gray-800">
                  Scope
                </label>
                <select
                  id="cap-scope"
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  value={scope}
                  onChange={event => setScope(event.target.value)}
                  disabled={submitting}
                >
                  {SCOPE_OPTIONS.map(option => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-1">
                <label htmlFor="cap-ttl" className="text-sm font-medium text-gray-800">
                  TTL (minutes)
                </label>
                <input
                  id="cap-ttl"
                  type="number"
                  min={TTL_MIN}
                  max={TTL_MAX}
                  step={5}
                  value={ttlMinutes}
                  onChange={event => setTtlMinutes(Number(event.target.value))}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  disabled={submitting}
                />
                <p className="text-xs text-gray-500">
                  Allowed range: {TTL_MIN} – {TTL_MAX} minutes
                </p>
              </div>

              <div className="space-y-1">
                <label htmlFor="cap-reason" className="text-sm font-medium text-gray-800">
                  Reason
                </label>
                <input
                  id="cap-reason"
                  value={reason}
                  onChange={event => setReason(event.target.value)}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  disabled={submitting}
                  placeholder="Describe why this capability is needed"
                />
              </div>
            </>
          )}

          {result && (
            <div className="space-y-3 rounded-md border border-blue-100 bg-blue-50 px-4 py-3 text-sm text-blue-900">
              <div>
                <span className="font-semibold">Capability ID:</span> {shortCapabilityId}
              </div>
              <div>
                <span className="font-semibold">Expires:</span> {humanExpiry} ({countdown})
              </div>
              <div className="flex items-center gap-3">
                <div>
                  <span className="font-semibold">Token:</span> {maskToken(result.token)}
                </div>
                <button
                  type="button"
                  onClick={handleCopy}
                  className="rounded-md border border-blue-200 px-2 py-1 text-xs font-medium text-blue-700 hover:bg-blue-100"
                >
                  Copy
                </button>
              </div>
              <div className="text-xs text-blue-700">
                Token is masked. Copy to clipboard to paste into the client that needs authorization.
              </div>
            </div>
          )}

          {error && (
            <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
              {error}
            </div>
          )}

          <div className="flex items-center justify-end gap-3 border-t border-gray-100 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 disabled:opacity-60"
              disabled={submitting}
            >
              Cancel
            </button>
            {!result && (
              <button
                type="submit"
                className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60"
                disabled={submitting}
              >
                {submitting ? 'Issuing…' : 'Issue token'}
              </button>
            )}
          </div>
        </form>
      </div>
    </div>
  )
}
