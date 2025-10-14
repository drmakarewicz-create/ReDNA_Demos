import { FormEvent, useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import userOpsApi, {
  DryRunResponse,
  JobStatusResponse,
  UserListItem,
} from '@/lib/userOpsApi'

const PAGE_SIZE = 20

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const index = Math.floor(Math.log(bytes) / Math.log(1024))
  const value = bytes / Math.pow(1024, index)
  return `${value.toFixed(1)} ${units[index]}`
}

function formatDate(value?: string | null): string {
  if (!value) return '—'
  try {
    const date = new Date(value)
    return date.toLocaleString()
  } catch {
    return value
  }
}

export default function UserOps() {
  const [activeTab, setActiveTab] = useState<'delete' | 'holistic' | 'revoke'>('delete')

  const [searchParams, setSearchParams] = useSearchParams()
  const includeSynthetic = searchParams.get('include_synthetic') === '1'

  const [users, setUsers] = useState<UserListItem[]>([])
  const [total, setTotal] = useState(0)
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(0)
  const [loadingUsers, setLoadingUsers] = useState(false)

  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [selectedUserIds, setSelectedUserIds] = useState<string[]>([])

  const [dryRunResult, setDryRunResult] = useState<DryRunResponse | null>(null)
  const [dryRunLoading, setDryRunLoading] = useState(false)

  const [showDeleteModal, setShowDeleteModal] = useState(false)
  const [deleteReason, setDeleteReason] = useState('')
  const [deleteGraceDays, setDeleteGraceDays] = useState(7)
  const [deleteConfirm, setDeleteConfirm] = useState('')
  const [deleteSubmitting, setDeleteSubmitting] = useState(false)

  const [jobIds, setJobIds] = useState<string[]>([])
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null)
  const [jobStatus, setJobStatus] = useState<JobStatusResponse | null>(null)
  const [jobStatusLoading, setJobStatusLoading] = useState(false)

  const [undoSelection, setUndoSelection] = useState<string[]>([])
  const [undoConfirm, setUndoConfirm] = useState('')
  const [undoSubmitting, setUndoSubmitting] = useState(false)

  const [purgeSelection, setPurgeSelection] = useState<string[]>([])
  const [purgeConfirm, setPurgeConfirm] = useState('')
  const [purgeSubmitting, setPurgeSubmitting] = useState(false)
  const [showRevokeModal, setShowRevokeModal] = useState(false)
  const [revokeReason, setRevokeReason] = useState('')
  const [revokeConfirm, setRevokeConfirm] = useState('')
  const [revokeSubmitting, setRevokeSubmitting] = useState(false)
  const [revokeResults, setRevokeResults] = useState<
    { user_id: string; revoked: number; warnings?: string[] }[] | null
  >(null)
  const [exporting, setExporting] = useState(false)
  const [exportResults, setExportResults] = useState<
    { user_id: string; status: string; download?: string; reason?: string }[] | null
  >(null)

  const [showHolisticModal, setShowHolisticModal] = useState(false)
  const [holisticReason, setHolisticReason] = useState('')
  const [holisticSubmitting, setHolisticSubmitting] = useState(false)

  useEffect(() => {
    loadUsers()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, includeSynthetic])

  useEffect(() => {
    if (!selectedJobId) {
      setJobStatus(null)
      return
    }
    fetchJobStatus(selectedJobId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedJobId])

  useEffect(() => {
    if (activeTab === 'holistic') {
      setDryRunResult(null)
      setUndoConfirm('')
      setPurgeConfirm('')
    }
  }, [activeTab])

  const loadUsers = async () => {
    try {
      setLoadingUsers(true)
      setErrorMessage(null)
      const response = await userOpsApi.listUsers({
        query: query.trim() || undefined,
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
        includeSynthetic,
      })
      setUsers(response.users)
      setTotal(response.total)
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : 'Failed to load users.')
    } finally {
      setLoadingUsers(false)
    }
  }

  const handleSearch = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setPage(0)
    await loadUsers()
  }

  const handleIncludeSyntheticChange = (checked: boolean) => {
    const next = new URLSearchParams(searchParams)
    if (checked) {
      next.set('include_synthetic', '1')
    } else {
      next.delete('include_synthetic')
    }
    setSearchParams(next, { replace: true })
    setPage(0)
    setSelectedUserIds([])
  }

  const toggleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedUserIds(users.map(user => user.user_id))
    } else {
      setSelectedUserIds([])
    }
  }

  const toggleUserSelection = (userId: string) => {
    setSuccessMessage(null)
    setSelectedUserIds(prev =>
      prev.includes(userId) ? prev.filter(id => id !== userId) : [...prev, userId],
    )
  }

  const runDryRun = async () => {
    if (selectedUserIds.length === 0) return
    try {
      setDryRunLoading(true)
      setErrorMessage(null)
      const result = await userOpsApi.dryRunDelete(selectedUserIds)
      setDryRunResult(result)
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : 'Dry run failed.')
    } finally {
      setDryRunLoading(false)
    }
  }

  const openDeleteModal = () => {
    setDeleteConfirm('')
    setDeleteReason('')
    setDeleteGraceDays(7)
    setShowDeleteModal(true)
    setSuccessMessage(null)
    setErrorMessage(null)
  }

  const openHolisticModal = () => {
    setHolisticReason('')
    setShowHolisticModal(true)
    setSuccessMessage(null)
    setErrorMessage(null)
  }

  const submitDelete = async () => {
    if (selectedUserIds.length === 0) return
    const expectedConfirm = `DELETE ${selectedUserIds.length} USERS`
    if (deleteConfirm !== expectedConfirm) {
      setErrorMessage(`Confirmation string must match "${expectedConfirm}"`)
      return
    }
    try {
      setDeleteSubmitting(true)
      const response = await userOpsApi.submitDelete({
        user_ids: selectedUserIds,
        reason: deleteReason,
        grace_days: deleteGraceDays,
        confirm: deleteConfirm,
      })
      setSuccessMessage(`Quarantine requested. Job id: ${response.job_id}`)
      setErrorMessage(null)
      setShowDeleteModal(false)
      setDryRunResult(null)
      setSelectedUserIds([])
      setJobIds(prev => (prev.includes(response.job_id) ? prev : [response.job_id, ...prev]))
      setSelectedJobId(response.job_id)
      await loadUsers()
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : 'Delete request failed.')
    } finally {
      setDeleteSubmitting(false)
    }
  }

  const submitHolistic = async () => {
    if (selectedUserIds.length === 0) return
    try {
      setHolisticSubmitting(true)
      const response = await userOpsApi.runHolistic(selectedUserIds, holisticReason)
      setSuccessMessage(`Queued holistic review job ${response.job_id}`)
      setErrorMessage(null)
      setShowHolisticModal(false)
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : 'Failed to queue holistic review job.')
    } finally {
      setHolisticSubmitting(false)
    }
  }

  const openRevokeModal = () => {
    setShowRevokeModal(true)
    setRevokeReason('')
    setRevokeConfirm('')
    setSuccessMessage(null)
    setErrorMessage(null)
  }

  const submitRevoke = async () => {
    if (selectedUserIds.length === 0) return
    const expected = `REVOKE CAPS ${selectedUserIds.length} USERS`
    if (revokeConfirm !== expected) {
      setErrorMessage(`Confirmation string must match "${expected}"`)
      return
    }
    try {
      setRevokeSubmitting(true)
      const response = await userOpsApi.revokeCaps(selectedUserIds, revokeReason)
      setRevokeResults(response.results || [])
      setSuccessMessage(
        `Revoked ${response.total_revoked} capabilities across ${selectedUserIds.length} users (job ${response.job_id}).`
      )
      setErrorMessage(null)
      setShowRevokeModal(false)
      setRevokeConfirm('')
      setRevokeReason('')
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : 'Failed to revoke capabilities.')
    } finally {
      setRevokeSubmitting(false)
    }
  }

  const handleExport = async () => {
    if (selectedUserIds.length === 0) return
    try {
      setExporting(true)
      const response = await userOpsApi.exportUsers(selectedUserIds)
      setExportResults(response.results || [])
      setSuccessMessage('Exports ready. Use the download links below.')
      setErrorMessage(null)
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : 'Failed to export user data.')
    } finally {
      setExporting(false)
    }
  }

  const fetchJobStatus = async (jobId: string) => {
    try {
      setJobStatusLoading(true)
      const status = await userOpsApi.jobStatus(jobId)
      setJobStatus(status)
      const quarantineUsers = Object.entries(status.users || {})
        .filter(([, info]) => info.status === 'quarantine')
        .map(([userId]) => userId)
      setUndoSelection(quarantineUsers)

      const now = Date.now()
      const eligibleForPurge = Object.entries(status.users || {})
        .filter(([, info]) => {
          if (info.status !== 'quarantine' || !info.review_until) return false
          try {
            return new Date(info.review_until).getTime() <= now
          } catch {
            return false
          }
        })
        .map(([userId]) => userId)
      setPurgeSelection(eligibleForPurge)
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : 'Failed to load job status.')
    } finally {
      setJobStatusLoading(false)
    }
  }

  const handleUndo = async () => {
    if (!selectedJobId || undoSelection.length === 0) return
    const expected = `UNDO ${undoSelection.length} USERS`
    if (undoConfirm !== expected) {
      setErrorMessage(`Confirmation string must match "${expected}"`)
      return
    }
    try {
      setUndoSubmitting(true)
      const result = await userOpsApi.undoDelete({
        job_id: selectedJobId,
        user_ids: undoSelection,
        confirm: undoConfirm,
      })
      if (result.errors.length > 0) {
        setErrorMessage(result.errors.map(e => `${e.user_id}: ${e.message}`).join('; '))
      } else {
        setErrorMessage(null)
      }
      if (result.restored.length > 0) {
        setSuccessMessage(`Restored users: ${result.restored.join(', ')}`)
      }
      setUndoConfirm('')
      await fetchJobStatus(selectedJobId)
      await loadUsers()
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : 'Undo failed.')
    } finally {
      setUndoSubmitting(false)
    }
  }

  const handlePurge = async () => {
    if (purgeSelection.length === 0) return
    const expected = `PURGE ${purgeSelection.length} USERS`
    if (purgeConfirm !== expected) {
      setErrorMessage(`Confirmation string must match "${expected}"`)
      return
    }
    try {
      setPurgeSubmitting(true)
      const result = await userOpsApi.purgeUsers({
        user_ids: purgeSelection,
        confirm: purgeConfirm,
      })
      if (result.errors.length > 0) {
        setErrorMessage(result.errors.map(e => `${e.user_id}: ${e.message}`).join('; '))
      } else {
        setErrorMessage(null)
      }
      if (result.purged.length > 0) {
        setSuccessMessage(`Purged users: ${result.purged.join(', ')}`)
      }
      setPurgeConfirm('')
      if (selectedJobId) {
        await fetchJobStatus(selectedJobId)
      }
      await loadUsers()
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : 'Purge failed.')
    } finally {
      setPurgeSubmitting(false)
    }
  }

  const selectedAll =
    selectedUserIds.length > 0 && selectedUserIds.length === users.length && users.length > 0

  const undoCandidates = useMemo(() => {
    if (!jobStatus) return []
    return Object.entries(jobStatus.users || {})
      .filter(([, info]) => info.status === 'quarantine')
      .map(([userId, info]) => ({
        userId,
        reviewUntil: info.review_until,
      }))
  }, [jobStatus])

  const purgeCandidates = useMemo(() => {
    if (!jobStatus) return []
    const now = Date.now()
    return Object.entries(jobStatus.users || {})
      .filter(([, info]) => {
        if (info.status !== 'quarantine' || !info.review_until) return false
        try {
          return new Date(info.review_until).getTime() <= now
        } catch {
          return false
        }
      })
      .map(([userId, info]) => ({
        userId,
        reviewUntil: info.review_until,
      }))
  }, [jobStatus])

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center gap-3">
          <h2 className="text-3xl font-bold text-gray-900">🧰 User Ops (Batch)</h2>
          {includeSynthetic && (
            <span className="inline-flex items-center rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700">
              Personas shown
            </span>
          )}
        </div>
        <p className="mt-2 text-sm text-gray-600">
          Plan and execute multi-user maintenance jobs with quarantine safeguards.
        </p>
      </div>

      {errorMessage && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md text-sm">
          {errorMessage}
        </div>
      )}

      {successMessage && (
        <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-md text-sm">
          {successMessage}
        </div>
      )}

      <div className="grid grid-cols-12 gap-6">
        <div className="col-span-12 lg:col-span-6 space-y-4">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <form onSubmit={handleSearch} className="flex flex-1 space-x-2">
              <input
                type="text"
                value={query}
                onChange={event => setQuery(event.target.value)}
                placeholder="Search users..."
                className="flex-1 px-3 py-2 border border-gray-300 rounded-md"
              />
              <button
                type="submit"
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
              >
                Search
              </button>
            </form>
            <label
              htmlFor="include-synthetic-toggle"
              className="flex items-center justify-end gap-2 text-sm text-gray-600"
            >
              <input
                id="include-synthetic-toggle"
                type="checkbox"
                checked={includeSynthetic}
                onChange={event => handleIncludeSyntheticChange(event.target.checked)}
                className="h-4 w-4"
              />
              <span>Include personas / synthetic users</span>
            </label>
          </div>

          <div className="bg-white border border-gray-200 rounded-md overflow-hidden">
            <div className="px-4 py-2 border-b border-gray-200 flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  checked={selectedAll}
                  onChange={event => toggleSelectAll(event.target.checked)}
                />
                <span className="text-sm text-gray-600">
                  Select all ({selectedUserIds.length} selected)
                </span>
              </div>
              <span className="text-xs text-gray-500">
                Page {page + 1} · Total {total}
              </span>
            </div>
            <div className="max-h-[400px] overflow-y-auto divide-y divide-gray-200">
              {loadingUsers ? (
                <div className="px-4 py-12 text-center text-sm text-gray-500">Loading users…</div>
              ) : users.length === 0 ? (
                <div className="px-4 py-12 text-center text-sm text-gray-500">No users found.</div>
              ) : (
                users.map(user => (
                  <label
                    key={user.user_id}
                    className="px-4 py-3 flex items-start space-x-3 hover:bg-gray-50 cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      checked={selectedUserIds.includes(user.user_id)}
                      onChange={() => toggleUserSelection(user.user_id)}
                      className="mt-1"
                    />
                    <div className="flex-1">
                      <div className="flex items-center justify-between">
                        <span className="font-medium text-gray-900">{user.user_id}</span>
                        <div className="flex items-center gap-3">
                          <Link
                            to={`/user-ops/${encodeURIComponent(user.user_id)}`}
                            onClick={event => event.stopPropagation()}
                            className="text-xs font-medium text-blue-600 hover:text-blue-800"
                          >
                            Open
                          </Link>
                          <span className="text-xs text-gray-500">
                            {formatBytes(user.size_bytes)}
                          </span>
                        </div>
                      </div>
                      <div className="text-xs text-gray-500">
                        Last updated: {formatDate(user.last_updated)}
                      </div>
                      {user.quarantine_status && (
                        <div className="text-xs text-yellow-700 mt-1">
                          Status: {user.quarantine_status}{' '}
                          {user.review_until ? `(review until ${formatDate(user.review_until)})` : ''}
                        </div>
                      )}
                    </div>
                  </label>
                ))
              )}
            </div>
            <div className="flex items-center justify-between px-4 py-2 bg-gray-50 border-t border-gray-200 text-sm">
              <button
                type="button"
                onClick={() => setPage(prev => Math.max(prev - 1, 0))}
                disabled={page === 0}
                className={`px-3 py-1 rounded-md ${
                  page === 0 ? 'bg-gray-200 text-gray-500 cursor-not-allowed' : 'bg-white border'
                }`}
              >
                Previous
              </button>
              <button
                type="button"
                onClick={() => {
                  const maxPage = Math.max(Math.ceil(total / PAGE_SIZE) - 1, 0)
                  setPage(prev => Math.min(prev + 1, maxPage))
                }}
                disabled={(page + 1) * PAGE_SIZE >= total}
                className={`px-3 py-1 rounded-md ${
                  (page + 1) * PAGE_SIZE >= total
                    ? 'bg-gray-200 text-gray-500 cursor-not-allowed'
                    : 'bg-white border'
                }`}
              >
                Next
              </button>
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            {activeTab === 'delete' && (
              <>
                <button
                  type="button"
                  onClick={runDryRun}
                  disabled={selectedUserIds.length === 0 || dryRunLoading}
                  className={`px-4 py-2 rounded-md text-sm font-medium text-white ${
                    selectedUserIds.length === 0
                      ? 'bg-gray-300 cursor-not-allowed'
                      : 'bg-blue-600 hover:bg-blue-700'
                  }`}
                >
                  {dryRunLoading ? 'Dry-running…' : 'Dry Run Delete'}
                </button>
                <button
                  type="button"
                  onClick={openDeleteModal}
                  disabled={selectedUserIds.length === 0}
                  className={`px-4 py-2 rounded-md text-sm font-medium text-white ${
                    selectedUserIds.length === 0
                      ? 'bg-gray-300 cursor-not-allowed'
                      : 'bg-red-600 hover:bg-red-700'
                  }`}
                >
                  Delete (Quarantine)
                </button>
              </>
            )}

            {activeTab === 'holistic' && (
              <button
                type="button"
                onClick={openHolisticModal}
                disabled={selectedUserIds.length === 0}
                className={`px-4 py-2 rounded-md text-sm font-medium text-white ${
                  selectedUserIds.length === 0
                    ? 'bg-gray-300 cursor-not-allowed'
                    : 'bg-purple-600 hover:bg-purple-700'
                }`}
              >
                Queue Holistic Review
              </button>
            )}

            {activeTab === 'revoke' && (
              <button
                type="button"
                onClick={openRevokeModal}
                disabled={selectedUserIds.length === 0}
                className={`px-4 py-2 rounded-md text-sm font-medium text-white ${
                  selectedUserIds.length === 0
                    ? 'bg-gray-300 cursor-not-allowed'
                    : 'bg-amber-600 hover:bg-amber-700'
                }`}
              >
                Revoke Caps
              </button>
            )}

            <button
              type="button"
              onClick={handleExport}
              disabled={selectedUserIds.length === 0 || exporting}
              className={`px-4 py-2 rounded-md text-sm font-medium text-white ${
                selectedUserIds.length === 0
                  ? 'bg-gray-300 cursor-not-allowed'
                  : 'bg-slate-700 hover:bg-slate-800'
              }`}
            >
              {exporting ? 'Exporting…' : 'Export JSON'}
            </button>
          </div>

          {exportResults && (
            <div className="rounded-md border border-gray-200 bg-white">
              <div className="border-b border-gray-200 px-4 py-2 text-sm font-semibold text-gray-800">
                Export Downloads
              </div>
              <ul className="divide-y divide-gray-200 text-sm">
                {exportResults.map(result => (
                  <li key={result.user_id} className="px-4 py-2 flex items-center justify-between">
                    <span className="text-gray-700">{result.user_id}</span>
                    {result.status === 'ready' && result.download ? (
                      <a
                        href={result.download}
                        className="text-blue-600 hover:underline"
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        Download
                      </a>
                    ) : (
                      <span className="text-xs text-red-600">Error: {result.reason}</span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {activeTab === 'delete' && dryRunResult && (
            <div className="bg-white border border-gray-200 rounded-md">
              <div className="px-4 py-2 border-b border-gray-200">
                <h4 className="text-sm font-semibold text-gray-800">Dry Run Plan</h4>
                <p className="text-xs text-gray-500">
                  Total bytes to quarantine: {formatBytes(dryRunResult.totals.bytes_to_quarantine)}
                </p>
              </div>
              <div className="divide-y divide-gray-200">
                {Object.values(dryRunResult.users).map(entry => (
                  <div key={entry.user_id} className="px-4 py-3 text-sm text-gray-700 space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="font-medium">{entry.user_id}</span>
                      {entry.bytes_to_quarantine !== undefined && (
                        <span className="text-xs text-gray-500">
                          {formatBytes(entry.bytes_to_quarantine)}
                        </span>
                      )}
                    </div>
                    {entry.error ? (
                      <div className="text-xs text-red-600">{entry.error}</div>
                    ) : (
                      <>
                        <div className="text-xs text-gray-500">
                          Paths: {(entry.vault_paths || []).join(', ') || '—'}
                        </div>
                        <div className="text-xs text-gray-500">
                          Capabilities: {entry.capability_count ?? 'unknown'}
                        </div>
                        {entry.warnings && entry.warnings.length > 0 && (
                          <ul className="text-xs text-yellow-700 list-disc list-inside">
                            {entry.warnings.map((warning, index) => (
                              <li key={index}>{warning}</li>
                            ))}
                          </ul>
                        )}
                        {entry.has_open_tickets && (
                          <div className="text-xs text-red-600">
                            Existing quarantine ticket detected.
                          </div>
                        )}
                      </>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="col-span-12 lg:col-span-6 space-y-4">
          <div className="bg-white border border-gray-200 rounded-md">
            <div className="px-4 py-2 border-b border-gray-200 flex space-x-4 text-sm font-medium">
              <button
                type="button"
                onClick={() => setActiveTab('delete')}
                className={`px-3 py-1 rounded-md ${
                  activeTab === 'delete'
                    ? 'bg-blue-100 text-blue-700'
                    : 'text-gray-600 hover:text-gray-800'
                }`}
              >
                Delete Users
              </button>
              <button
                type="button"
                onClick={() => setActiveTab('holistic')}
                className={`px-3 py-1 rounded-md ${
                  activeTab === 'holistic'
                    ? 'bg-blue-100 text-blue-700'
                    : 'text-gray-600 hover:text-gray-800'
                }`}
              >
                Run Holistic Review
              </button>
              <button
                type="button"
                onClick={() => setActiveTab('revoke')}
                className={`px-3 py-1 rounded-md ${
                  activeTab === 'revoke'
                    ? 'bg-blue-100 text-blue-700'
                    : 'text-gray-600 hover:text-gray-800'
                }`}
              >
                Revoke All Caps
              </button>
            </div>

            <div className="p-4 space-y-4">
              {activeTab === 'delete' && (
                <>
                  <div>
                    <h4 className="text-sm font-semibold text-gray-800 mb-2">Job History</h4>
                    {jobIds.length === 0 ? (
                      <p className="text-xs text-gray-500">
                        Jobs appear here after you submit a deletion.
                      </p>
                    ) : (
                      <select
                        className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                        value={selectedJobId ?? ''}
                        onChange={event => setSelectedJobId(event.target.value || null)}
                      >
                        <option value="">Select a job…</option>
                        {jobIds.map(id => (
                          <option key={id} value={id}>
                            {id}
                          </option>
                        ))}
                      </select>
                    )}
                  </div>

                  {selectedJobId && (
                    <div className="space-y-4">
                      <div className="bg-gray-50 border border-gray-200 rounded-md p-3 text-xs text-gray-600">
                        {jobStatusLoading || !jobStatus ? (
                          <p>Loading job status…</p>
                        ) : (
                          <>
                            <p>
                              Job {jobStatus.job_id} · Created {formatDate(jobStatus.created_at)}
                            </p>
                            <ul className="mt-2 space-y-1">
                              {Object.entries(jobStatus.users).map(([userId, info]) => (
                                <li key={userId}>
                                  <span className="font-medium text-gray-800">{userId}</span> –{' '}
                                  <span className="text-gray-700">{info.status}</span>
                                  {info.review_until && (
                                    <span className="text-gray-500">
                                      {' '}
                                      (review until {formatDate(info.review_until)})
                                    </span>
                                  )}
                                </li>
                              ))}
                            </ul>
                          </>
                        )}
                      </div>

                      <div className="space-y-2">
                        <h5 className="text-sm font-semibold text-gray-800">Undo (within grace period)</h5>
                        {undoCandidates.length === 0 ? (
                          <p className="text-xs text-gray-500">No users currently eligible for undo.</p>
                        ) : (
                          <div className="space-y-2">
                            <div className="flex flex-wrap gap-2">
                              {undoCandidates.map(candidate => (
                                <label
                                  key={candidate.userId}
                                  className="flex items-center space-x-2 bg-gray-100 px-2 py-1 rounded-md text-xs"
                                >
                                  <input
                                    type="checkbox"
                                    checked={undoSelection.includes(candidate.userId)}
                                    onChange={() =>
                                      setUndoSelection(prev =>
                                        prev.includes(candidate.userId)
                                          ? prev.filter(id => id !== candidate.userId)
                                          : [...prev, candidate.userId],
                                      )
                                    }
                                  />
                                  <span>
                                    {candidate.userId}{' '}
                                    {candidate.reviewUntil && (
                                      <span className="text-gray-500">
                                        (until {formatDate(candidate.reviewUntil)})
                                      </span>
                                    )}
                                  </span>
                                </label>
                              ))}
                            </div>
                            <input
                              type="text"
                              value={undoConfirm}
                              onChange={event => setUndoConfirm(event.target.value)}
                              placeholder={`Type "UNDO ${undoSelection.length || undoCandidates.length} USERS"`}
                              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                            />
                            <button
                              type="button"
                              onClick={handleUndo}
                              disabled={undoSelection.length === 0 || undoSubmitting}
                              className={`px-4 py-2 rounded-md text-sm font-medium text-white ${
                                undoSelection.length === 0
                                  ? 'bg-gray-300 cursor-not-allowed'
                                  : 'bg-green-600 hover:bg-green-700'
                              }`}
                            >
                              {undoSubmitting ? 'Undoing…' : `Undo ${undoSelection.length} Users`}
                            </button>
                          </div>
                        )}
                      </div>

                      <div className="space-y-2">
                        <h5 className="text-sm font-semibold text-gray-800">Purge (after grace)</h5>
                        {purgeCandidates.length === 0 ? (
                          <p className="text-xs text-gray-500">No users eligible for purge yet.</p>
                        ) : (
                          <div className="space-y-2">
                            <div className="flex flex-wrap gap-2">
                              {purgeCandidates.map(candidate => (
                                <label
                                  key={candidate.userId}
                                  className="flex items-center space-x-2 bg-red-50 px-2 py-1 rounded-md text-xs text-red-700"
                                >
                                  <input
                                    type="checkbox"
                                    checked={purgeSelection.includes(candidate.userId)}
                                    onChange={() =>
                                      setPurgeSelection(prev =>
                                        prev.includes(candidate.userId)
                                          ? prev.filter(id => id !== candidate.userId)
                                          : [...prev, candidate.userId],
                                      )
                                    }
                                  />
                                  <span>
                                    {candidate.userId}{' '}
                                    {candidate.reviewUntil && (
                                      <span className="text-gray-500">
                                        (since {formatDate(candidate.reviewUntil)})
                                      </span>
                                    )}
                                  </span>
                                </label>
                              ))}
                            </div>
                            <input
                              type="text"
                              value={purgeConfirm}
                              onChange={event => setPurgeConfirm(event.target.value)}
                              placeholder={`Type "PURGE ${purgeSelection.length || purgeCandidates.length} USERS"`}
                              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                            />
                            <button
                              type="button"
                              onClick={handlePurge}
                              disabled={purgeSelection.length === 0 || purgeSubmitting}
                              className={`px-4 py-2 rounded-md text-sm font-medium text-white ${
                                purgeSelection.length === 0
                                  ? 'bg-gray-300 cursor-not-allowed'
                                  : 'bg-red-600 hover:bg-red-700'
                              }`}
                            >
                              {purgeSubmitting ? 'Purging…' : `Purge ${purgeSelection.length} Users`}
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </>
              )}

              {activeTab === 'holistic' && (
                <div className="space-y-3 text-sm text-gray-600">
                  <p>
                    Queue holistic review jobs for the selected users. Jobs run asynchronously and do not
                    modify vault data.
                  </p>
                  <p>
                    Selected users:{' '}
                    {selectedUserIds.length === 0 ? (
                      <span className="text-gray-400">none</span>
                    ) : (
                      <span className="font-medium text-gray-900">{selectedUserIds.join(', ')}</span>
                    )}
                  </p>
                  <p className="text-xs text-gray-500">
                    Once holistic jobs are wired into Core, DevX will surface status here.
                  </p>
                </div>
              )}

              {activeTab === 'revoke' && (
                <div className="space-y-3 text-sm text-gray-600">
                  <p>
                    Revoke all active capabilities for the selected users. A manifest is written to{' '}
                    <code>data/devx_jobs/revoke_caps/</code> with per-user results.
                  </p>
                  {revokeResults ? (
                    <div className="rounded border border-amber-200 bg-amber-50">
                      <div className="border-b border-amber-200 px-3 py-2 text-xs font-semibold text-amber-800">
                        Latest revoke manifest
                      </div>
                      <ul className="divide-y divide-amber-200 text-xs text-amber-900">
                        {revokeResults.map(result => (
                          <li key={result.user_id} className="flex items-center justify-between px-3 py-2">
                            <span className="font-medium">{result.user_id}</span>
                            <span>
                              {result.revoked} revoked
                              {result.warnings && result.warnings.length > 0 && (
                                <span className="text-amber-600">
                                  {' '}
                                  · {result.warnings.join('; ')}
                                </span>
                              )}
                            </span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : (
                    <p className="text-xs text-gray-500">Run a revoke job to see results here.</p>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {showDeleteModal && (
        <div className="fixed inset-0 bg-black bg-opacity-30 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-lg w-full p-6 space-y-4">
            <h3 className="text-lg font-semibold text-gray-900">Confirm User Deletion</h3>
            <p className="text-sm text-gray-600">
              Users will be moved to quarantine. You can undo within the grace period before purging.
            </p>

            <div className="space-y-3 text-sm">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Reason</label>
                <textarea
                  value={deleteReason}
                  onChange={event => setDeleteReason(event.target.value)}
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  placeholder="Describe why these users are being quarantined."
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Grace period</label>
                <select
                  value={deleteGraceDays}
                  onChange={event => setDeleteGraceDays(Number(event.target.value))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                >
                  {[1, 3, 7, 14, 30].map(days => (
                    <option key={days} value={days}>
                      {days} {days === 1 ? 'day' : 'days'}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Confirmation (type DELETE {selectedUserIds.length} USERS)
                </label>
                <input
                  type="text"
                  value={deleteConfirm}
                  onChange={event => setDeleteConfirm(event.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  placeholder={`DELETE ${selectedUserIds.length} USERS`}
                />
              </div>
            </div>

            <div className="flex justify-end space-x-2">
              <button
                type="button"
                onClick={() => setShowDeleteModal(false)}
                className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-800"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={submitDelete}
                disabled={deleteSubmitting}
                className="px-4 py-2 bg-red-600 text-white text-sm font-medium rounded-md hover:bg-red-700"
              >
                {deleteSubmitting ? 'Submitting…' : `Delete ${selectedUserIds.length} Users`}
              </button>
            </div>
          </div>
        </div>
      )}

      {showHolisticModal && (
        <div className="fixed inset-0 bg-black bg-opacity-30 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-lg w-full p-6 space-y-4">
            <h3 className="text-lg font-semibold text-gray-900">Queue Holistic Review</h3>
            <p className="text-sm text-gray-600">
              This queues a non-destructive holistic review job for the selected users.
            </p>
            <div className="bg-gray-50 border border-gray-200 rounded-md p-3 text-xs text-gray-600 max-h-32 overflow-y-auto">
              {selectedUserIds.join(', ')}
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Optional notes for the job manifest
              </label>
              <textarea
                value={holisticReason}
                onChange={event => setHolisticReason(event.target.value)}
                rows={3}
                className="w-full px-3 py-2 border border-gray-300 rounded-md"
                placeholder="Reason or context for this batch run."
              />
            </div>
            <div className="flex justify-end space-x-2">
              <button
                type="button"
                onClick={() => setShowHolisticModal(false)}
                className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-800"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={submitHolistic}
                disabled={holisticSubmitting}
                className="px-4 py-2 bg-purple-600 text-white text-sm font-medium rounded-md hover:bg-purple-700"
              >
                {holisticSubmitting ? 'Queuing…' : `Queue ${selectedUserIds.length} Users`}
              </button>
            </div>
          </div>
        </div>
      )}

      {showRevokeModal && (
        <div className="fixed inset-0 bg-black bg-opacity-30 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-lg w-full p-6 space-y-4">
            <h3 className="text-lg font-semibold text-gray-900">Revoke All Capabilities</h3>
            <p className="text-sm text-gray-600">
              This revokes every active capability for the selected users through the Consent Service.
            </p>
            <div className="bg-gray-50 border border-gray-200 rounded-md p-3 text-xs text-gray-600 max-h-32 overflow-y-auto">
              {selectedUserIds.join(', ')}
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Optional reason</label>
              <textarea
                value={revokeReason}
                onChange={event => setRevokeReason(event.target.value)}
                rows={3}
                className="w-full px-3 py-2 border border-gray-300 rounded-md"
                placeholder="Reason recorded with each revoke."
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Confirmation (type REVOKE CAPS {selectedUserIds.length} USERS)
              </label>
              <input
                type="text"
                value={revokeConfirm}
                onChange={event => setRevokeConfirm(event.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md"
                placeholder={`REVOKE CAPS ${selectedUserIds.length} USERS`}
              />
            </div>
            <div className="flex justify-end space-x-2">
              <button
                type="button"
                onClick={() => setShowRevokeModal(false)}
                className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-800"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={submitRevoke}
                disabled={revokeSubmitting}
                className="px-4 py-2 bg-amber-600 text-white text-sm font-medium rounded-md hover:bg-amber-700"
              >
                {revokeSubmitting ? 'Revoking…' : `Revoke ${selectedUserIds.length} Users`}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
