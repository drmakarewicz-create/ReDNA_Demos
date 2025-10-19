import React, { useEffect, useMemo, useState } from 'react'

import { devxApi } from '@/lib/devxApi'
import { ConflictDetail } from './components/ConflictDetail'
import { ConflictFilters } from './components/Filters'
import { ConflictTable, ConflictRow } from './components/ConflictTable'

type TabKey = 'list' | 'detail' | 'simulate'

interface SimulateFormState {
  user_id: string
  kind: string
  severity: string
  path: string
  value: string
}

const initialSimulate: SimulateFormState = {
  user_id: 'TEST',
  kind: 'trait',
  severity: 'low',
  path: 'SkillDNA.sample_trait',
  value: 'contradiction',
}

export default function ConflictDashboard() {
  const [conflicts, setConflicts] = useState<ConflictRow[]>([])
  const [filters, setFilters] = useState({ status: '', kind: '', user_id: '' })
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [selectedDetail, setSelectedDetail] = useState<Record<string, any> | null>(null)
  const [tab, setTab] = useState<TabKey>('list')
  const [loading, setLoading] = useState(false)
  const [simulateForm, setSimulateForm] = useState<SimulateFormState>(initialSimulate)
  const [simulateResult, setSimulateResult] = useState<string>('')
  const [stats, setStats] = useState<Record<string, any> | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [infoMessage, setInfoMessage] = useState<string | null>(null)
  const [exporting, setExporting] = useState(false)
  const [seeding, setSeeding] = useState(false)

  useEffect(() => {
    loadConflicts()
    loadStats()
  }, [filters.status, filters.kind, filters.user_id])

  useEffect(() => {
    if (!selectedId) {
      setSelectedDetail(null)
      return
    }
    loadDetail(selectedId)
  }, [selectedId])

  const filteredConflicts = useMemo(() => {
    return conflicts.filter((conflict) => {
      if (filters.status && conflict.status !== filters.status) {
        return false
      }
      if (filters.kind && conflict.kind !== filters.kind) {
        return false
      }
      if (filters.user_id && conflict.user_id !== filters.user_id) {
        return false
      }
      return true
    })
  }, [conflicts, filters])

  const loadConflicts = async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await devxApi.listConflicts(filters)
      setConflicts(data.conflicts ?? data ?? [])
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to load conflicts'
      setError(message)
    } finally {
      setLoading(false)
    }
  }

  const loadStats = async () => {
    try {
      const data = await devxApi.getConflictStats()
      setStats(data)
    } catch (error) {
      console.error('Failed to load conflict stats', error)
    }
  }

  const loadDetail = async (conflictId: string) => {
    try {
      const data = await devxApi.getConflictDetail(conflictId)
      setSelectedDetail(data)
      setTab('detail')
    } catch (error) {
      console.error('Failed to load conflict detail', error)
    }
  }

  const handleSimulate = async (event: React.FormEvent) => {
    event.preventDefault()
    setSimulateResult('')
    try {
      const payload = {
        conflict: {
          user_id: simulateForm.user_id,
          kind: simulateForm.kind,
          severity: simulateForm.severity,
          path: simulateForm.path,
        },
        evidence: [
          {
            evidence_id: `sim-${Date.now()}`,
            source_type: 'user_assertion',
            timestamp: new Date().toISOString(),
            value: simulateForm.value,
            provenance: { support: 1.0 },
          },
          {
            evidence_id: `sim-core-${Date.now()}`,
            source_type: 'core',
            timestamp: new Date().toISOString(),
            value: 'baseline',
            provenance: { support: -1.0 },
          },
        ],
      }
      const response = await devxApi.simulateConflict(payload)
      setSimulateResult('Simulated conflict created and resolved.')
      await loadConflicts()
      if (response.conflict_id) {
        setSelectedId(response.conflict_id)
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to simulate conflict'
      setSimulateResult(message)
    }
  }

  const handleExport = async () => {
    const userId = filters.user_id || filteredConflicts[0]?.user_id || conflicts[0]?.user_id || ''
    if (!userId) {
      setError('Select a user or ensure conflicts are loaded before exporting the log.')
      return
    }
    setExporting(true)
    setError(null)
    setInfoMessage(null)
    try {
      const blob = await devxApi.exportConflictLog(userId)
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `${userId}_conflict_log.jsonl`
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
      setInfoMessage(`Exported conflict log for ${userId}.`)
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to export conflict log'
      setError(message)
    } finally {
      setExporting(false)
    }
  }

  const handleSeedConflict = async () => {
    setSeeding(true)
    setError(null)
    try {
      const response = await devxApi.seedConflict()
      setInfoMessage(`Seeded conflict payload (core status ${response.core_status ?? 'unknown'}).`)
      await loadConflicts()
      setTab('list')
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to seed conflict'
      setError(message)
    } finally {
      setSeeding(false)
    }
  }

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <h1 className="text-3xl font-bold text-slate-900">Conflict Dashboard</h1>
        <p className="text-sm text-slate-500">
          Inspect refinements that required arbitration. Self-reports are treated as calibrated evidence and never override policy without corroboration.
        </p>
      </header>

      {infoMessage && (
        <div className="rounded border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{infoMessage}</div>
      )}
      {error && (
        <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>
      )}

      <nav className="flex gap-2 text-sm font-medium">
        {[
          { key: 'list', label: 'All Conflicts' },
          { key: 'detail', label: 'Details' },
          { key: 'simulate', label: 'Simulate' },
        ].map((entry) => (
          <button
            key={entry.key}
            type="button"
            onClick={() => setTab(entry.key as TabKey)}
            className={`rounded px-3 py-1 ${
              tab === entry.key ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            {entry.label}
          </button>
        ))}
      </nav>

      {tab === 'list' && (
        <div className="space-y-4">
          {stats && (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <div className="rounded border border-slate-200 bg-white p-4">
                <p className="text-xs uppercase text-slate-500">Total Conflicts</p>
                <p className="mt-1 text-2xl font-semibold text-slate-900">{stats.total}</p>
              </div>
              <div className="rounded border border-slate-200 bg-white p-4">
                <p className="text-xs uppercase text-slate-500">Escalated</p>
                <p className="mt-1 text-2xl font-semibold text-slate-900">{stats.by_status?.escalated ?? 0}</p>
              </div>
              <div className="rounded border border-slate-200 bg-white p-4">
                <p className="text-xs uppercase text-slate-500">Resolved</p>
                <p className="mt-1 text-2xl font-semibold text-slate-900">{stats.by_status?.resolved ?? stats.by_status?.auto_resolved ?? 0}</p>
              </div>
            </div>
          )}
          <ConflictFilters
            status={filters.status}
            kind={filters.kind}
            userId={filters.user_id}
            onStatusChange={(value) => setFilters((prev) => ({ ...prev, status: value }))}
            onKindChange={(value) => setFilters((prev) => ({ ...prev, kind: value }))}
            onUserChange={(value) => setFilters((prev) => ({ ...prev, user_id: value }))}
          />
          <div className="flex items-center justify-end gap-2 text-sm">
            <button
              type="button"
              onClick={handleSeedConflict}
              disabled={seeding}
              className="rounded border border-amber-300 bg-amber-50 px-3 py-1 text-amber-700 transition hover:border-amber-400 hover:text-amber-800 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {seeding ? 'Seeding…' : 'Seed Example'}
            </button>
            <button
              type="button"
              onClick={handleExport}
              disabled={exporting}
              className="rounded border border-slate-300 bg-white px-3 py-1 text-slate-600 transition hover:border-slate-400 hover:text-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {exporting ? 'Exporting…' : 'Export log'}
            </button>
          </div>
          {loading ? (
            <div className="rounded border border-slate-200 bg-white p-6 text-center text-sm text-slate-500">
              Loading conflicts…
            </div>
          ) : (
            <ConflictTable conflicts={filteredConflicts} onSelect={(id) => setSelectedId(id)} />
          )}
        </div>
      )}

      {tab === 'detail' && <ConflictDetail conflict={selectedDetail} />}

      {tab === 'simulate' && (
        <form
          onSubmit={handleSimulate}
          className="space-y-4 rounded border border-slate-200 bg-white p-6 text-sm text-slate-600"
        >
          <div className="grid grid-cols-2 gap-4">
            <label className="space-y-1">
              <span className="text-xs text-slate-500">User ID</span>
              <input
                value={simulateForm.user_id}
                onChange={(event) => setSimulateForm((prev) => ({ ...prev, user_id: event.target.value }))}
                className="w-full rounded border border-slate-300 px-2 py-1"
              />
            </label>
            <label className="space-y-1">
              <span className="text-xs text-slate-500">Severity</span>
              <select
                value={simulateForm.severity}
                onChange={(event) => setSimulateForm((prev) => ({ ...prev, severity: event.target.value }))}
                className="w-full rounded border border-slate-300 px-2 py-1"
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </select>
            </label>
            <label className="space-y-1">
              <span className="text-xs text-slate-500">Kind</span>
              <select
                value={simulateForm.kind}
                onChange={(event) => setSimulateForm((prev) => ({ ...prev, kind: event.target.value }))}
                className="w-full rounded border border-slate-300 px-2 py-1"
              >
                <option value="trait">Trait</option>
                <option value="interpretation">Interpretation</option>
                <option value="policy">Policy</option>
                <option value="permission">Permission</option>
              </select>
            </label>
            <label className="space-y-1">
              <span className="text-xs text-slate-500">Path</span>
              <input
                value={simulateForm.path}
                onChange={(event) => setSimulateForm((prev) => ({ ...prev, path: event.target.value }))}
                className="w-full rounded border border-slate-300 px-2 py-1"
              />
            </label>
          </div>

          <label className="block space-y-1">
            <span className="text-xs text-slate-500">User assertion</span>
            <textarea
              value={simulateForm.value}
              onChange={(event) => setSimulateForm((prev) => ({ ...prev, value: event.target.value }))}
              rows={3}
              className="w-full rounded border border-slate-300 px-2 py-1"
            />
          </label>

          <div className="flex items-center gap-2">
            <button
              type="submit"
              className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
            >
              Simulate Conflict
            </button>
            {simulateResult && <span className="text-xs text-slate-500">{simulateResult}</span>}
          </div>
        </form>
      )}
    </div>
  )
}
