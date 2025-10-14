/**
 * Privacy Dashboard - User privacy and consent management
 */

import React, { useEffect, useState } from 'react'
import { DEVX_API_BASE, devxUrl } from '@/lib/env'

interface Capability {
  cap_id: string
  grantee_id: string
  purpose: string
  scopes: string[]
  issued_at: string
  expires_at: string
  ttl: string
  use_count: number
  reuse_limit: number | null
  revoked: boolean
  export_allowed: boolean
}

interface LedgerEvent {
  event_id: string
  timestamp: string
  event_type: 'grant' | 'revoke' | 'use' | 'deny'
  cap_id?: string
  grantee_id?: string
  purpose?: string
  scopes?: string[]
  reason?: string
}

interface PrivacyPreferences {
  refinement_enabled: boolean
  auto_approve_low_risk: boolean
  audit_notifications: boolean
  export_warning: boolean
}

interface CapabilityTotals {
  total: number | null
  export_enabled: number | null
  revoked: number | null
}

const API_BASE = DEVX_API_BASE

export default function PrivacyDashboard() {
  const [userId, setUserId] = useState('TEST')
  const [capabilities, setCapabilities] = useState<Capability[]>([])
  const [ledgerEvents, setLedgerEvents] = useState<LedgerEvent[]>([])
  const [preferences, setPreferences] = useState<PrivacyPreferences>({
    refinement_enabled: true,
    auto_approve_low_risk: false,
    audit_notifications: true,
    export_warning: true,
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [infoMessage, setInfoMessage] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'permissions' | 'ledger' | 'export'>('permissions')
  const [syntheticTraits, setSyntheticTraits] = useState<any[]>([])
  const [usingSynthetic, setUsingSynthetic] = useState(false)
  const [auditLoading, setAuditLoading] = useState(false)
  const [capabilityTotals, setCapabilityTotals] = useState<CapabilityTotals>({
    total: null,
    export_enabled: null,
    revoked: null,
  })
  const [managedBy, setManagedBy] = useState('PermCoach')

  useEffect(() => {
    loadDashboardData()
  }, [userId])

  const loadDashboardData = async () => {
    try {
      setLoading(true)
      setError(null)
      setInfoMessage(null)
      setCapabilityTotals({
        total: null,
        export_enabled: null,
        revoked: null,
      })
      setManagedBy('PermCoach')

      await Promise.all([loadCapabilities(), loadLedger()])
      const summaryLoaded = await loadSummary()
      if (!summaryLoaded) {
        await loadPreferences()
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load dashboard data')
      await loadSyntheticTraits()
    } finally {
      setLoading(false)
    }
  }

  const loadSummary = async (): Promise<boolean> => {
    try {
      const response = await fetch(`${API_BASE}/privacy/summary?user_id=${encodeURIComponent(userId)}`)

      if (response.status === 401 || response.status === 403) {
        setCapabilityTotals({
          total: null,
          export_enabled: null,
          revoked: null,
        })
        setError((prev) => prev ?? 'Permission required to view privacy summary. Obtain a valid developer token.')
        return false
      }

      if (!response.ok) {
        let detail = 'Failed to load privacy summary.'
        try {
          const errorPayload = await response.json()
          if (typeof errorPayload?.detail === 'string') {
            detail = errorPayload.detail
          }
        } catch {
          try {
            const text = await response.text()
            if (text) {
              detail = text
            }
          } catch {
            // Ignore secondary failures
          }
        }
        setCapabilityTotals({
          total: null,
          export_enabled: null,
          revoked: null,
        })
        setError((prev) => prev ?? detail)
        return false
      }

      const data = await response.json()
      const totals = data?.capability_totals ?? {}
      const parseTotal = (value: unknown) =>
        typeof value === 'number' && Number.isFinite(value) ? value : null

      setCapabilityTotals({
        total: parseTotal(totals.total),
        export_enabled: parseTotal(totals.export_enabled),
        revoked: parseTotal(totals.revoked),
      })

      if (data?.managed_by) {
        setManagedBy(data.managed_by)
      }

      if (data?.summary?.preferences) {
        setPreferences(data.summary.preferences)
      }

      return true
    } catch (summaryError) {
      console.warn('Privacy summary unavailable', summaryError)
      setCapabilityTotals({
        total: null,
        export_enabled: null,
        revoked: null,
      })
      const message = summaryError instanceof Error ? summaryError.message : 'Failed to load privacy summary.'
      setError((prev) => prev ?? message)
      return false
    }
  }

  const loadCapabilities = async () => {
    const response = await fetch(`${API_BASE}/privacy/capabilities?user_id=${encodeURIComponent(userId)}`)
    if (response.status === 401 || response.status === 403) {
      throw new Error('Permission required to view capabilities. Obtain a valid developer token.')
    }
    if (!response.ok) {
      throw new Error('Failed to load capabilities')
    }
    const data = await response.json()
    setCapabilities(data.capabilities || [])
    if ((!data.capabilities || data.capabilities.length === 0) && syntheticTraits.length === 0) {
      await loadSyntheticTraits()
    } else {
      setUsingSynthetic(false)
    }
  }

  const loadLedger = async () => {
    const response = await fetch(`${API_BASE}/privacy/ledger?user_id=${encodeURIComponent(userId)}&limit=50`)
    if (response.status === 401 || response.status === 403) {
      throw new Error('Permission required to view consent ledger events.')
    }
    if (!response.ok) {
      throw new Error('Failed to load ledger events')
    }
    const data = await response.json()
    setLedgerEvents(data.events || [])
  }

  const loadPreferences = async () => {
    const response = await fetch(`${API_BASE}/privacy/preferences?user_id=${encodeURIComponent(userId)}`)
    if (!response.ok) {
      throw new Error('Failed to load preferences')
    }
    const data = await response.json()
    setPreferences(data.preferences)
  }

  const loadSyntheticTraits = async () => {
    try {
      const response = await fetch(devxUrl('/synthetic/traits'))
      if (!response.ok) {
        return
      }
      const data = await response.json()
      setSyntheticTraits(Array.isArray(data.containers) ? data.containers : [])
      setUsingSynthetic(true)
    } catch (syntheticError) {
      console.warn('Synthetic traits unavailable for privacy dashboard', syntheticError)
    }
  }

  const handleRevokeCapability = async (capId: string) => {
    if (!confirm('Are you sure you want to revoke this capability? The coach will lose access immediately.')) {
      return
    }

    try {
      const response = await fetch(`${API_BASE}/privacy/revoke`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          cap_id: capId,
          reason: 'User revoked via Privacy Dashboard',
        }),
      })

      if (response.ok) {
        await loadDashboardData()
      } else {
        const errorText = await response.text()
        alert(`Failed to revoke capability: ${errorText}`)
      }
    } catch (err) {
      alert(`Error revoking capability: ${err instanceof Error ? err.message : 'Unknown error'}`)
    }
  }

  const handleToggleRefinement = async (enabled: boolean) => {
    const newPrefs = { ...preferences, refinement_enabled: enabled }

    try {
      const response = await fetch(`${API_BASE}/privacy/preferences`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          preferences: newPrefs,
        }),
      })

      if (response.ok) {
        setPreferences(newPrefs)
      } else {
        alert('Failed to update preferences')
      }
    } catch (err) {
      alert(`Error updating preferences: ${err instanceof Error ? err.message : 'Unknown error'}`)
    }
  }

  const handleRequestExport = async (format: string) => {
    try {
      const response = await fetch(`${API_BASE}/privacy/export-request`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          format: format,
        }),
      })

      if (response.ok) {
        const result = await response.json()
        alert(`Export requested! Estimated time: ${result.estimated_time_minutes} minutes. You will be notified when ready.`)
      } else {
        alert('Failed to request export')
      }
    } catch (err) {
      alert(`Error requesting export: ${err instanceof Error ? err.message : 'Unknown error'}`)
    }
  }

  const handleAudit = async () => {
    setAuditLoading(true)
    setError(null)
    setInfoMessage(null)
    try {
      const response = await fetch(`${API_BASE}/privacy/audit?user_id=${encodeURIComponent(userId)}`)
      if (response.status === 401 || response.status === 403) {
        setError('Permission required to run audit via PermCoach.')
        return
      }
      if (!response.ok) {
        let detail = 'Audit failed. Check logs for details.'
        try {
          const errorPayload = await response.json()
          if (typeof errorPayload?.detail === 'string') {
            detail = errorPayload.detail
          }
        } catch {
          try {
            const fallbackText = await response.text()
            if (fallbackText) {
              detail = fallbackText
            }
          } catch {
            // ignore
          }
        }
        setError(`Audit failed: ${detail}`)
        return
      }
      const report = await response.json()
      const anomalies = Array.isArray(report?.anomalies) ? report.anomalies : []
      const severityBreakdown = report?.summary?.severity_breakdown ?? {}
      const counts = {
        high: typeof severityBreakdown.high === 'number' ? severityBreakdown.high : anomalies.filter((a) => (a.severity || 'low').toLowerCase() === 'high').length,
        medium: typeof severityBreakdown.medium === 'number' ? severityBreakdown.medium : anomalies.filter((a) => (a.severity || 'low').toLowerCase() === 'medium').length,
        low: typeof severityBreakdown.low === 'number' ? severityBreakdown.low : anomalies.filter((a) => (a.severity || 'low').toLowerCase() === 'low').length,
      }
      setInfoMessage(`Audit complete — ${counts.high} high / ${counts.medium} medium / ${counts.low} low`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Audit failed. Check logs for details.')
    } finally {
      setAuditLoading(false)
    }
  }

  const formatTimestamp = (timestamp: string) => {
    try {
      return new Date(timestamp).toLocaleString()
    } catch {
      return timestamp
    }
  }

  const getEventTypeColor = (eventType: string) => {
    switch (eventType) {
      case 'grant':
        return 'text-green-600 bg-green-50'
      case 'revoke':
        return 'text-red-600 bg-red-50'
      case 'use':
        return 'text-blue-600 bg-blue-50'
      case 'deny':
        return 'text-yellow-600 bg-yellow-50'
      default:
        return 'text-gray-600 bg-gray-50'
    }
  }

  const totalCapabilities = capabilities.length
  const formatStatValue = (value: number | null) => (typeof value === 'number' ? value : '—')
  const summaryStatCards = [
    {
      label: 'Total Capabilities',
      value: capabilityTotals.total,
      containerClass: 'border-blue-100 bg-blue-50',
      valueClass: 'text-blue-900',
      labelClass: 'text-blue-600',
      caption: 'Total tokens',
    },
    {
      label: 'Export Enabled',
      value: capabilityTotals.export_enabled,
      containerClass: 'border-emerald-100 bg-emerald-50',
      valueClass: 'text-emerald-900',
      labelClass: 'text-emerald-600',
      caption: 'Export allowed',
    },
    {
      label: 'Revoked',
      value: capabilityTotals.revoked,
      containerClass: 'border-slate-200 bg-slate-50',
      valueClass: 'text-slate-900',
      labelClass: 'text-slate-500',
      caption: 'Revoked tokens',
    },
  ]

  const renderSpinner = (label: string) => (
    <div className="flex items-center gap-2 text-gray-600">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-blue-200 border-t-blue-600"></span>
      <span>{label}</span>
    </div>
  )

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-4">
      <div className="mb-2">
        <h1 className="text-3xl font-bold text-gray-900">Privacy Dashboard</h1>
        <p className="text-sm text-gray-600 mt-1">
          Managed by <span className="font-semibold text-blue-600">{managedBy}</span> — Your consent guardian
        </p>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {summaryStatCards.map((stat) => (
          <div key={stat.label} className={`rounded border ${stat.containerClass} p-4`}>
            <p className={`text-xs uppercase ${stat.labelClass}`}>{stat.label}</p>
            <p className={`mt-1 text-2xl font-semibold ${stat.valueClass}`}>{formatStatValue(stat.value)}</p>
            <p className="text-xs text-gray-600 mt-1">{stat.caption}</p>
          </div>
        ))}
      </div>

      {infoMessage && (
        <div className="p-3 rounded border border-emerald-200 bg-emerald-50 text-emerald-700 text-sm">{infoMessage}</div>
      )}

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-800 text-sm">{error}</div>
      )}

      <div className="mb-4 flex flex-wrap items-center gap-2 text-sm text-gray-500">
        <span>User: <span className="font-semibold text-gray-800">{userId}</span></span>
        <button
          type="button"
          onClick={() => {
            const nextUser = prompt('Enter user ID to inspect', userId)
            if (nextUser) {
              setUserId(nextUser.trim())
            }
          }}
          className="rounded border border-gray-300 bg-white px-3 py-1 text-gray-600 transition hover:border-gray-400 hover:text-gray-800"
        >
          Change user
        </button>
        <button
          type="button"
          onClick={loadDashboardData}
          className="rounded border border-gray-300 bg-white px-3 py-1 text-gray-600 transition hover:border-gray-400 hover:text-gray-800"
        >
          Refresh
        </button>
        <button
          type="button"
          onClick={handleAudit}
          disabled={auditLoading}
          className="rounded border border-blue-300 bg-blue-50 px-3 py-1 text-blue-700 transition hover:border-blue-400 hover:text-blue-900 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {auditLoading ? 'Running audit…' : 'Run PermCoach audit'}
        </button>
      </div>

      <div className="mb-4 border-b border-gray-200">
        <nav className="flex space-x-8 text-sm font-medium">
          <button
            onClick={() => setActiveTab('permissions')}
            className={`py-2 px-1 border-b-2 ${
              activeTab === 'permissions'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            Active Permissions ({totalCapabilities})
          </button>
          <button
            onClick={() => setActiveTab('ledger')}
            className={`py-2 px-1 border-b-2 ${
              activeTab === 'ledger'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            Consent Ledger ({ledgerEvents.length})
          </button>
          <button
            onClick={() => setActiveTab('export')}
            className={`py-2 px-1 border-b-2 ${
              activeTab === 'export'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            Export & Deletion
          </button>
        </nav>
      </div>

      {activeTab === 'permissions' && (
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
          <div className="p-6 space-y-4">
            <h2 className="text-xl font-semibold text-gray-900">🔐 Active Permissions</h2>

            {loading ? (
              renderSpinner('Loading permissions…')
            ) : totalCapabilities === 0 ? (
              <div className="space-y-4">
                <p className="text-gray-600">
                  No active capabilities. All coaches are denied by default.
                  {usingSynthetic && ' Showing synthetic trait summary for demo purposes.'}
                </p>
                {usingSynthetic && syntheticTraits.length > 0 && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {syntheticTraits.map((trait: any, index: number) => (
                      <div key={trait.path || index} className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                        <h3 className="text-sm font-semibold text-blue-800">{trait.label || trait.path || `Synthetic Trait ${index + 1}`}</h3>
                        <p className="text-xs text-blue-600 mt-1">Synthetic container preview</p>
                        <dl className="mt-3 grid grid-cols-2 gap-2 text-xs text-blue-700">
                          <div>
                            <dt className="font-semibold">RR</dt>
                            <dd>{trait.rr ?? '—'}</dd>
                          </div>
                          <div>
                            <dt className="font-semibold">Curiosity</dt>
                            <dd>{trait.curiosity ?? '—'}</dd>
                          </div>
                          <div>
                            <dt className="font-semibold">UCN</dt>
                            <dd>{trait.ucn ?? '—'}</dd>
                          </div>
                          <div>
                            <dt className="font-semibold">Last Evidence</dt>
                            <dd>{trait.last_evidence || 'n/a'}</dd>
                          </div>
                        </dl>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <div className="space-y-4">
                {capabilities.map((cap) => (
                  <div
                    key={cap.cap_id}
                    className={`border rounded-lg p-4 ${cap.revoked ? 'bg-gray-50 border-gray-300' : 'border-gray-200'}`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          <h3 className="font-semibold text-gray-900">{cap.grantee_id}</h3>
                          {cap.revoked && (
                            <span className="px-2 py-0.5 text-xs font-medium bg-red-100 text-red-800 rounded">REVOKED</span>
                          )}
                          {cap.export_allowed && (
                            <span className="px-2 py-0.5 text-xs font-medium bg-yellow-100 text-yellow-800 rounded">EXPORT OK</span>
                          )}
                        </div>
                        <p className="text-sm text-gray-700 mb-2">
                          <strong>Purpose:</strong> {cap.purpose}
                        </p>
                        <div className="text-sm text-gray-600 space-y-1">
                          <p><strong>Scopes:</strong> {cap.scopes.join(', ')}</p>
                          <p><strong>Issued:</strong> {formatTimestamp(cap.issued_at)}</p>
                          <p><strong>Expires:</strong> {formatTimestamp(cap.expires_at)} ({cap.ttl})</p>
                          <p><strong>Uses:</strong> {cap.use_count} {cap.reuse_limit ? `/ ${cap.reuse_limit}` : ''}</p>
                        </div>
                      </div>
                      {!cap.revoked && (
                        <button
                          onClick={() => handleRevokeCapability(cap.cap_id)}
                          className="ml-4 px-4 py-2 text-sm font-medium text-red-700 bg-red-50 border border-red-200 rounded hover:bg-red-100"
                        >
                          Revoke
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === 'ledger' && (
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
          <div className="p-6">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">📜 Consent Ledger</h2>
            <p className="text-sm text-gray-600 mb-4">
              Append-only log of all consent events. Every capability grant, revocation, use, and denial is recorded here.
            </p>

            {loading ? (
              renderSpinner('Loading ledger…')
            ) : ledgerEvents.length === 0 ? (
              <p className="text-gray-600">No ledger events yet.</p>
            ) : (
              <div className="space-y-2">
                {ledgerEvents.map((event) => (
                  <div key={event.event_id} className="border-l-4 border-gray-300 pl-4 py-2 hover:bg-gray-50">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`px-2 py-0.5 text-xs font-semibold rounded ${getEventTypeColor(event.event_type)}`}>
                        {event.event_type.toUpperCase()}
                      </span>
                      <span className="text-xs text-gray-500">{formatTimestamp(event.timestamp)}</span>
                    </div>
                    <div className="text-sm text-gray-700">
                      {event.grantee_id && <span><strong>Grantee:</strong> {event.grantee_id}</span>}
                      {event.purpose && <span className="ml-4"><strong>Purpose:</strong> {event.purpose}</span>}
                    </div>
                    {event.scopes && event.scopes.length > 0 && (
                      <div className="text-xs text-gray-600 mt-1">
                        <strong>Scopes:</strong> {event.scopes.join(', ')}
                      </div>
                    )}
                    {event.reason && (
                      <div className="text-xs text-gray-600 mt-1">
                        <strong>Reason:</strong> {event.reason}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === 'export' && (
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
          <div className="p-6 space-y-8">
            <section>
              <h2 className="text-xl font-semibold text-gray-900 mb-2">📦 Export Your Data</h2>
              <p className="text-sm text-gray-600 mb-4">
                Download a complete copy of your ReDNA data in your preferred format.
              </p>
              <div className="flex flex-wrap gap-2">
                {['json', 'csv', 'pdf'].map((fmt) => (
                  <button
                    key={fmt}
                    onClick={() => handleRequestExport(fmt)}
                    className="px-4 py-2 text-sm font-medium text-blue-700 bg-blue-50 border border-blue-200 rounded hover:bg-blue-100"
                  >
                    Export as {fmt.toUpperCase()}
                  </button>
                ))}
              </div>
            </section>

            <section className="border-t border-gray-200 pt-6">
              <h3 className="text-lg font-medium text-red-900 mb-2">⚠️ Delete All Data</h3>
              <p className="text-sm text-gray-600 mb-4">
                <strong>GDPR Right to Deletion:</strong> Permanently delete all your ReDNA data. This action is irreversible and has a 7-day review period.
              </p>
              <button
                onClick={() => {
                  const confirmation = prompt('Type your user ID to confirm deletion:')
                  if (confirmation === userId) {
                    fetch(`${API_BASE}/privacy/purge-request`, {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({ user_id: userId, confirmation }),
                    }).then((res) => {
                      if (res.ok) {
                        alert('Deletion request submitted. 7-day review period begins now.')
                      } else {
                        alert('Failed to submit deletion request')
                      }
                    })
                  } else {
                    alert('Confirmation did not match. Deletion cancelled.')
                  }
                }}
                className="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded hover:bg-red-700"
              >
                Request Data Deletion
              </button>
            </section>
          </div>
        </div>
      )}
    </div>
  )
}
