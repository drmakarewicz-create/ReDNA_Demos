import { useEffect, useMemo, useState } from 'react'
import userOpsApi, {
  CapabilityTokenRecord,
  GrantPermissionPayload,
  RevokePermissionPayload,
  UserPermissionsResponse,
} from '@/lib/userOpsApi'

interface PermissionsTabProps {
  userId: string
}

const AVAILABLE_SCOPES = ['read', 'write']

export default function PermissionsTab({ userId }: PermissionsTabProps) {
  const [data, setData] = useState<UserPermissionsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  const [namespaceInput, setNamespaceInput] = useState('')
  const [scopeInput, setScopeInput] = useState<string>('read')
  const [expiryInput, setExpiryInput] = useState('')

  const [issueScope, setIssueScope] = useState('core.agent.run')
  const [issueTtl, setIssueTtl] = useState(30)
  const [issueLoading, setIssueLoading] = useState(false)
  const [grantLoading, setGrantLoading] = useState(false)
  const [revokeLoading, setRevokeLoading] = useState<string | null>(null)
  const [capabilityLoading, setCapabilityLoading] = useState<string | null>(null)

  const namespaces = useMemo(() => data?.namespaces ?? {}, [data])
  const localCapabilities = useMemo(() => data?.capabilities.local ?? [], [data])
  const consentCapabilities = useMemo(() => data?.capabilities.consent ?? [], [data])
  const consentError = data?.capabilities.consent_error

  const refresh = async () => {
    setLoading(true)
    setError(null)
    setMessage(null)
    try {
      const response = await userOpsApi.getPermissions(userId)
      setData(response)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load permissions.')
      setData(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    refresh()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId])

  const handleGrant = async () => {
    if (!namespaceInput.trim()) {
      setError('Namespace is required.')
      return
    }
    const payload: GrantPermissionPayload = {
      namespace: namespaceInput.trim(),
      scope: scopeInput,
      expiry: expiryInput.trim() || undefined,
    }
    try {
      setGrantLoading(true)
      setError(null)
      await userOpsApi.grantPermission(userId, payload)
      setMessage(`Granted ${payload.scope} on ${payload.namespace}.`)
      setNamespaceInput('')
      setExpiryInput('')
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to grant permission.')
    } finally {
      setGrantLoading(false)
    }
  }

  const handleRevokeScope = async (namespace: string, scope: string) => {
    const payload: RevokePermissionPayload = { namespace, scope }
    try {
      setRevokeLoading(`${namespace}:${scope}`)
      setError(null)
      await userOpsApi.revokePermission(userId, payload)
      setMessage(`Revoked ${scope} on ${namespace}.`)
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to revoke permission.')
    } finally {
      setRevokeLoading(null)
    }
  }

  const handleIssueCapability = async () => {
    if (!issueScope.trim()) {
      setError('Capability scope is required.')
      return
    }
    try {
      setIssueLoading(true)
      setCapabilityLoading('issue')
      setError(null)
      await userOpsApi.issueCapability(userId, {
        scope: issueScope.trim(),
        ttl_minutes: issueTtl,
      })
      setMessage('Capability token issued.')
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to issue capability.')
    } finally {
      setCapabilityLoading(null)
      setIssueLoading(false)
    }
  }

  const handleRevokeCapability = async (capability: CapabilityTokenRecord) => {
    try {
      setCapabilityLoading(capability.capability_id)
      setError(null)
      await userOpsApi.revokeCapability(userId, capability.capability_id)
      setMessage(`Capability ${capability.capability_id} revoked.`)
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to revoke capability.')
    } finally {
      setCapabilityLoading(null)
    }
  }

  return (
    <div className="space-y-6">
      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}
      {message && (
        <div className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
          {message}
        </div>
      )}

      <section className="rounded-lg border border-gray-200 bg-white shadow-sm">
        <div className="border-b border-gray-200 px-4 py-3">
          <h3 className="text-sm font-semibold text-gray-900">Consent Scopes</h3>
          <p className="mt-1 text-xs text-gray-500">
            Toggle namespace-level permissions for <span className="font-medium text-gray-900">{userId}</span>.
          </p>
        </div>
        <div className="space-y-4 p-4">
          {loading ? (
            <div className="text-sm text-gray-500">Loading permissions…</div>
          ) : Object.keys(namespaces).length === 0 ? (
            <div className="rounded-md border border-dashed border-gray-300 bg-gray-50 px-4 py-6 text-sm text-gray-600">
              No namespaces granted yet.
            </div>
          ) : (
            <ul className="divide-y divide-gray-200">
              {Object.entries(namespaces).map(([namespace, scopes]) => (
                <li key={namespace} className="py-3 text-sm">
                  <div className="font-semibold text-gray-900">{namespace}</div>
                  <div className="mt-2 grid gap-2 md:grid-cols-2 lg:grid-cols-3">
                    {Object.entries(scopes).map(([scope, meta]) => (
                      <div
                        key={`${namespace}:${scope}`}
                        className="flex items-center justify-between rounded-md border border-gray-200 bg-gray-50 px-3 py-2"
                      >
                        <div>
                          <div className="text-sm font-medium text-gray-800">{scope}</div>
                          <div className="text-xs text-gray-500">
                            Granted {formatTimestamp(meta?.granted_at)}
                            {meta?.expiry && ` · Expires ${formatTimestamp(meta.expiry)}`}
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={() => handleRevokeScope(namespace, scope)}
                          disabled={revokeLoading === `${namespace}:${scope}`}
                          className="text-xs font-medium text-red-600 hover:text-red-700 disabled:opacity-60"
                        >
                          {revokeLoading === `${namespace}:${scope}` ? 'Revoking…' : 'Revoke'}
                        </button>
                      </div>
                    ))}
                  </div>
                </li>
              ))}
            </ul>
          )}
          <div className="rounded-md border border-gray-200 bg-gray-50 p-4">
            <h4 className="text-sm font-semibold text-gray-900">Grant permission</h4>
            <div className="mt-3 grid gap-3 md:grid-cols-3">
              <input
                type="text"
                value={namespaceInput}
                onChange={event => setNamespaceInput(event.target.value)}
                placeholder="Namespace"
                className="rounded-md border border-gray-300 px-3 py-2 text-sm"
              />
              <select
                value={scopeInput}
                onChange={event => setScopeInput(event.target.value)}
                className="rounded-md border border-gray-300 px-3 py-2 text-sm"
              >
                {AVAILABLE_SCOPES.map(scope => (
                  <option key={scope} value={scope}>
                    {scope}
                  </option>
                ))}
              </select>
              <input
                type="text"
                value={expiryInput}
                onChange={event => setExpiryInput(event.target.value)}
                placeholder="Expiry (ISO timestamp)"
                className="rounded-md border border-gray-300 px-3 py-2 text-sm"
              />
            </div>
            <div className="mt-3 flex justify-end">
              <button
                type="button"
                onClick={handleGrant}
                disabled={grantLoading}
                className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60"
              >
                {grantLoading ? 'Granting…' : 'Grant permission'}
              </button>
            </div>
          </div>
        </div>
      </section>

      <section className="space-y-4 rounded-lg border border-blue-200 bg-blue-50/70 p-4 shadow-sm">
        <div>
          <h3 className="text-sm font-semibold text-blue-900">Capability Tokens</h3>
          <p className="mt-1 text-xs text-blue-800">
            Issue scoped capability tokens or revoke active ones for this user.
          </p>
          {consentError && (
            <div className="mt-2 rounded-md border border-blue-200 bg-white px-3 py-2 text-xs text-blue-700">
              Consent service warning: {consentError}
            </div>
          )}
        </div>

        <div className="space-y-4">
          <div className="rounded-md border border-blue-200 bg-white">
            {loading ? (
              <div className="px-4 py-6 text-sm text-blue-700">Loading capabilities…</div>
            ) : localCapabilities.length === 0 ? (
              <div className="px-4 py-6 text-sm text-blue-700">No capability tokens have been issued.</div>
            ) : (
              <ul className="divide-y divide-blue-100">
                {localCapabilities.map(cap => (
                  <li key={cap.capability_id} className="px-4 py-3 text-xs text-blue-900">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <div className="font-semibold">{cap.scope}</div>
                        <div className="text-[11px] text-blue-700/80">
                          Issued {formatTimestamp(cap.issued_at)} · Expires {formatTimestamp(cap.expires_at)}
                        </div>
                        <div className="mt-1 text-[11px] text-blue-700/80">ID: {cap.capability_id}</div>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleRevokeCapability(cap)}
                        disabled={capabilityLoading === cap.capability_id || cap.status === 'revoked'}
                        className="text-xs font-medium text-red-600 hover:text-red-700 disabled:opacity-60"
                      >
                        {cap.status === 'revoked'
                          ? 'Revoked'
                          : capabilityLoading === cap.capability_id
                          ? 'Revoking…'
                          : 'Revoke'}
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="rounded-md border border-blue-200 bg-white">
            <div className="border-b border-blue-100 px-4 py-2 text-xs font-semibold text-blue-800">
              Consent Service Capabilities
            </div>
            {loading ? (
              <div className="px-4 py-6 text-sm text-blue-700">Loading consent capabilities…</div>
            ) : consentCapabilities.length === 0 ? (
              <div className="px-4 py-6 text-sm text-blue-700">No active capabilities reported by consent service.</div>
            ) : (
              <ul className="divide-y divide-blue-100">
                {consentCapabilities.map((cap, idx) => (
                  <li key={cap.capability_id || idx} className="px-4 py-3 text-xs text-blue-900 space-y-1">
                    <div className="font-semibold">{cap.scope || cap.purpose || 'unknown.scope'}</div>
                    <div className="text-[11px] text-blue-700/80">
                      Issued {formatTimestamp(cap.issued_at)} · Expires {formatTimestamp(cap.expires_at || cap.expiry)}
                    </div>
                    <div className="text-[11px] text-blue-700/80">ID: {cap.capability_id || cap.id}</div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        <div className="rounded-md border border-blue-200 bg-white p-4">
          <h4 className="text-sm font-semibold text-blue-900">Issue capability</h4>
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            <input
              type="text"
              value={issueScope}
              onChange={event => setIssueScope(event.target.value)}
              placeholder="Scope (e.g. core.agent.run)"
              className="rounded-md border border-blue-200 px-3 py-2 text-sm"
            />
            <input
              type="number"
              min={1}
              value={issueTtl}
              onChange={event => setIssueTtl(Number(event.target.value) || 1)}
              className="rounded-md border border-blue-200 px-3 py-2 text-sm"
              placeholder="TTL minutes"
            />
          </div>
          <div className="mt-3 flex justify-end">
            <button
              type="button"
              onClick={handleIssueCapability}
              disabled={issueLoading}
              className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60"
            >
              {issueLoading ? 'Issuing…' : 'Issue capability'}
            </button>
          </div>
        </div>
      </section>
    </div>
  )
}

function formatTimestamp(value?: string | null) {
  if (!value) return '—'
  try {
    return new Date(value).toLocaleString()
  } catch {
    return value
  }
}
