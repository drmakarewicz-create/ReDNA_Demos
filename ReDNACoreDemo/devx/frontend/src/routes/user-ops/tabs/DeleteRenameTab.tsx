import { useEffect, useMemo, useState } from 'react'
import userOpsApi, {
  AuditEntry,
  DeleteUserPayload,
  DeleteUserResponse,
  RenamePayload,
  RenameResponse,
} from '@/lib/userOpsApi'

interface DeleteRenameTabProps {
  userId: string
}

type DeleteMode = 'retire' | 'purge'

export default function DeleteRenameTab({ userId }: DeleteRenameTabProps) {
  const [renameId, setRenameId] = useState('')
  const [renameReason, setRenameReason] = useState('')
  const [renameConfirm, setRenameConfirm] = useState('')
  const [renameLoading, setRenameLoading] = useState(false)
  const [renameResult, setRenameResult] = useState<RenameResponse | null>(null)
  const [renameError, setRenameError] = useState<string | null>(null)

  const [deleteMode, setDeleteMode] = useState<DeleteMode>('retire')
  const [deleteReason, setDeleteReason] = useState('')
  const [deleteGraceDays, setDeleteGraceDays] = useState(7)
  const [deleteConfirm, setDeleteConfirm] = useState('')
  const [deleteLoading, setDeleteLoading] = useState(false)
  const [deleteResult, setDeleteResult] = useState<DeleteUserResponse | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  const [auditEntries, setAuditEntries] = useState<AuditEntry[]>([])
  const [auditLoading, setAuditLoading] = useState(false)
  const [auditError, setAuditError] = useState<string | null>(null)

  const expectedRenameConfirm = useMemo(() => {
    return renameId ? `RENAME ${userId} TO ${renameId}` : `RENAME ${userId} TO <NEW_ID>`
  }, [renameId, userId])

  const expectedDeleteConfirm = useMemo(() => {
    return deleteMode === 'retire' ? `DELETE ${userId}` : `PURGE ${userId}`
  }, [deleteMode, userId])

  const loadAudit = async () => {
    try {
      setAuditLoading(true)
      setAuditError(null)
      const response = await userOpsApi.getAudit(userId, 10)
      setAuditEntries(response.entries || [])
    } catch (err) {
      setAuditError(err instanceof Error ? err.message : 'Failed to load audit trail.')
      setAuditEntries([])
    } finally {
      setAuditLoading(false)
    }
  }

  useEffect(() => {
    loadAudit()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId])

  const handleRename = async () => {
    if (!renameId.trim()) {
      setRenameError('New user id is required.')
      return
    }
    const payload: RenamePayload = {
      new_user_id: renameId.trim(),
      reason: renameReason.trim() || undefined,
      confirm: renameConfirm.trim() || undefined,
    }
    try {
      setRenameLoading(true)
      setRenameError(null)
      const response = await userOpsApi.renameUser(userId, payload)
      setRenameResult(response)
      setRenameConfirm('')
      setRenameReason('')
      await loadAudit()
    } catch (err) {
      setRenameError(err instanceof Error ? err.message : 'Rename failed.')
      setRenameResult(null)
    } finally {
      setRenameLoading(false)
    }
  }

  const handleDelete = async () => {
    const payload: DeleteUserPayload = {
      mode: deleteMode,
      confirm: deleteConfirm.trim(),
      reason: deleteMode === 'retire' ? deleteReason.trim() || undefined : undefined,
      grace_days: deleteMode === 'retire' ? deleteGraceDays : undefined,
    }
    if (!payload.confirm) {
      setDeleteError('Confirmation string is required.')
      return
    }
    try {
      setDeleteLoading(true)
      setDeleteError(null)
      const response = await userOpsApi.deleteUser(userId, payload)
      setDeleteResult(response)
      setDeleteConfirm('')
      if (deleteMode === 'retire') {
        setDeleteReason('')
      }
      await loadAudit()
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : 'Delete request failed.')
      setDeleteResult(null)
    } finally {
      setDeleteLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-6 lg:grid-cols-2">
        <section className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm space-y-4">
          <div>
            <h3 className="text-sm font-semibold text-gray-900">Rename User</h3>
            <p className="mt-2 text-sm text-gray-600">
              Update the canonical user id. All vault, quarantine, and holistic artifacts will be moved
              atomically.
            </p>
          </div>
          <div className="space-y-3">
            <label className="block text-sm text-gray-700">
              New User ID
              <input
                type="text"
                value={renameId}
                onChange={event => setRenameId(event.target.value)}
                className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                placeholder="Enter new user id"
              />
            </label>
            <label className="block text-sm text-gray-700">
              Reason (optional)
              <input
                type="text"
                value={renameReason}
                onChange={event => setRenameReason(event.target.value)}
                className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                placeholder="Audit note"
              />
            </label>
            <div className="text-xs text-gray-500">
              Confirmation must match{' '}
              <span className="font-semibold text-gray-700">{expectedRenameConfirm}</span>
            </div>
            <input
              type="text"
              value={renameConfirm}
              onChange={event => setRenameConfirm(event.target.value)}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              placeholder={expectedRenameConfirm}
            />
            {renameError && (
              <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
                {renameError}
              </div>
            )}
            <div className="flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={handleRename}
                disabled={renameLoading}
                className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60"
              >
                {renameLoading ? 'Renaming…' : 'Rename User'}
              </button>
            </div>
            {renameResult && (
              <div className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-3 text-xs text-emerald-700">
                <div className="font-semibold text-emerald-800">Rename successful</div>
                <div className="mt-2 overflow-x-auto">
                  <pre className="max-h-48 whitespace-pre-wrap break-all text-[11px]">
                    {JSON.stringify(renameResult, null, 2)}
                  </pre>
                </div>
              </div>
            )}
          </div>
        </section>

        <section className="rounded-lg border border-red-200 bg-red-50/70 p-4 shadow-sm space-y-4">
          <div>
            <h3 className="text-sm font-semibold text-red-900">Retire / Purge</h3>
            <p className="mt-1 text-sm text-red-800">
              Retire moves the vault into quarantine (with grace period) while Purge permanently deletes
              data once grace has expired.
            </p>
          </div>
          <div className="space-y-3">
            <div className="flex items-center gap-4 text-sm text-red-900">
              <label className="flex items-center gap-2">
                <input
                  type="radio"
                  name="delete-mode"
                  value="retire"
                  checked={deleteMode === 'retire'}
                  onChange={() => setDeleteMode('retire')}
                />
                Retire (quarantine)
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="radio"
                  name="delete-mode"
                  value="purge"
                  checked={deleteMode === 'purge'}
                  onChange={() => setDeleteMode('purge')}
                />
                Purge (permanent)
              </label>
            </div>
            {deleteMode === 'retire' && (
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="text-sm text-red-900">
                  Reason (optional)
                  <input
                    type="text"
                    value={deleteReason}
                    onChange={event => setDeleteReason(event.target.value)}
                    className="mt-1 w-full rounded-md border border-red-200 px-3 py-2 text-sm"
                  />
                </label>
                <label className="text-sm text-red-900">
                  Grace days
                  <input
                    type="number"
                    min={1}
                    value={deleteGraceDays}
                    onChange={event => setDeleteGraceDays(Number(event.target.value) || 1)}
                    className="mt-1 w-full rounded-md border border-red-200 px-3 py-2 text-sm"
                  />
                </label>
              </div>
            )}
            <div className="text-xs text-red-700">
              Confirmation must match{' '}
              <span className="font-semibold text-red-900">{expectedDeleteConfirm}</span>
            </div>
            <input
              type="text"
              value={deleteConfirm}
              onChange={event => setDeleteConfirm(event.target.value)}
              className="w-full rounded-md border border-red-200 px-3 py-2 text-sm"
              placeholder={expectedDeleteConfirm}
            />
            {deleteError && (
              <div className="rounded-md border border-red-300 bg-white px-3 py-2 text-xs text-red-700">
                {deleteError}
              </div>
            )}
            <div className="flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={handleDelete}
                disabled={deleteLoading}
                className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-60"
              >
                {deleteLoading ? 'Processing…' : deleteMode === 'retire' ? 'Retire User' : 'Purge User'}
              </button>
            </div>
            {deleteResult && (
              <div className="rounded-md border border-red-200 bg-white px-3 py-3 text-xs text-red-800">
                <div className="font-semibold">
                  {deleteResult.status === 'purged' ? 'Purge complete' : 'User moved to quarantine'}
                </div>
                <div className="mt-2 overflow-x-auto">
                  <pre className="max-h-48 whitespace-pre-wrap break-all text-[11px]">
                    {JSON.stringify(deleteResult, null, 2)}
                  </pre>
                </div>
              </div>
            )}
          </div>
        </section>
      </div>

      <section className="rounded-lg border border-gray-200 bg-white shadow-sm">
        <div className="border-b border-gray-200 px-4 py-3">
          <h3 className="text-sm font-semibold text-gray-900">Audit Trail</h3>
          <p className="mt-1 text-xs text-gray-500">Most recent user lifecycle events.</p>
        </div>
        {auditError && (
          <div className="px-4 py-3 text-xs text-red-600">{auditError}</div>
        )}
        {auditLoading ? (
          <div className="px-4 py-6 text-sm text-gray-500">Loading audit entries…</div>
        ) : auditEntries.length === 0 ? (
          <div className="px-4 py-6 text-sm text-gray-500">No audit entries recorded yet.</div>
        ) : (
          <ul className="divide-y divide-gray-200">
            {auditEntries.map((entry, idx) => (
              <li key={`${entry.timestamp}-${idx}`} className="px-4 py-3 text-xs text-gray-600 space-y-1">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-gray-800">{entry.event}</span>
                  <span>{formatTimestamp(entry.timestamp)}</span>
                </div>
                <pre className="whitespace-pre-wrap break-all text-[11px] bg-gray-50 rounded-md px-3 py-2">
                  {JSON.stringify(entry, null, 2)}
                </pre>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}

function formatTimestamp(value?: string) {
  if (!value) return '—'
  try {
    return new Date(value).toLocaleString()
  } catch {
    return value
  }
}
