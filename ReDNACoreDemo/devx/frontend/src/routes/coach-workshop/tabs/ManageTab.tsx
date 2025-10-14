import { useState } from 'react'
import { DEVX_API_BASE } from '@/lib/env'

const API_BASE = DEVX_API_BASE

interface ManageTabProps {
  coachId: string
  coachLabel: string
  coachStatus: 'present' | 'missing' | 'retired'
  onRefresh: () => void
}

interface Reference {
  file: string
  line: number
  content: string
}

interface RenamePreview {
  coach_id: string
  new_coach_id: string
  new_label: string
  references_found: number
  files_to_modify: Array<{ file: string; changes: string[] }>
  total_files: number
}

export default function ManageTab({ coachId, coachLabel, coachStatus, onRefresh }: ManageTabProps) {
  // Rename state
  const [showRenameModal, setShowRenameModal] = useState(false)
  const [renameStep, setRenameStep] = useState(1)
  const [newCoachId, setNewCoachId] = useState('')
  const [newLabel, setNewLabel] = useState('')
  const [renameReason, setRenameReason] = useState('')
  const [renamePreview, setRenamePreview] = useState<RenamePreview | null>(null)
  const [renaming, setRenaming] = useState(false)
  const [renameConfirm, setRenameConfirm] = useState(false)

  // Delete/Retire state (moved from CoachWorkshop)
  const [showDeleteModal, setShowDeleteModal] = useState(false)
  const [deleteStep, setDeleteStep] = useState(1)
  const [deleteMode, setDeleteMode] = useState<'retire' | 'purge'>('retire')
  const [deleteReason, setDeleteReason] = useState('')
  const [deleteConfirm, setDeleteConfirm] = useState(false)
  const [deleteFinalConfirm, setDeleteFinalConfirm] = useState(false)
  const [references, setReferences] = useState<Reference[]>([])
  const [deleting, setDeleting] = useState(false)

  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  // Rename handlers
  const handleStartRename = () => {
    setNewCoachId(coachId)
    setNewLabel(coachLabel)
    setRenameReason('')
    setRenameStep(1)
    setRenameConfirm(false)
    setShowRenameModal(true)
  }

  const handleRenamePreview = async () => {
    try {
      setRenaming(true)
      const response = await fetch(
        `${API_BASE}/coaches/${encodeURIComponent(coachId)}/rename`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ new_coach_id: newCoachId, new_label: newLabel, reason: renameReason })
        }
      )

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Failed to preview rename')
      }

      const preview = await response.json()
      setRenamePreview(preview)
      setRenameStep(2)
    } catch (error) {
      setMessage({ type: 'error', text: `${error}` })
    } finally {
      setRenaming(false)
    }
  }

  const handleExecuteRename = async () => {
    try {
      setRenaming(true)
      const response = await fetch(
        `${API_BASE}/coaches/${encodeURIComponent(coachId)}/rename/execute`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ new_coach_id: newCoachId, new_label: newLabel, reason: renameReason })
        }
      )

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Failed to execute rename')
      }

      const result = await response.json()
      setMessage({ type: 'success', text: `Successfully renamed to '${newCoachId}'!` })
      setShowRenameModal(false)
      setTimeout(() => onRefresh(), 1000)
    } catch (error) {
      setMessage({ type: 'error', text: `${error}` })
    } finally {
      setRenaming(false)
    }
  }

  // Delete/Retire handlers (from original CoachWorkshop)
  const handleStartDelete = async () => {
    setDeleteStep(1)
    setDeleteConfirm(false)
    setDeleteFinalConfirm(false)
    setDeleteMode('retire')
    setDeleteReason('')
    setReferences([])
    setShowDeleteModal(true)

    // Scan references immediately
    try {
      const response = await fetch(
        `${API_BASE}/coaches/${encodeURIComponent(coachId)}?mode=retire&preview=true`
      )
      if (response.ok) {
        const data = await response.json()
        setReferences(data.references_found || [])
      }
    } catch (e) {
      // Non-fatal
    }
  }

  const handleDeleteNext = () => {
    if (deleteStep === 1 && deleteConfirm) {
      setDeleteStep(2)
    } else if (deleteStep === 2) {
      setDeleteStep(3)
    }
  }

  const handleDelete = async () => {
    try {
      setDeleting(true)
      const response = await fetch(
        `${API_BASE}/coaches/${encodeURIComponent(coachId)}?mode=${deleteMode}&force=true&reason=${encodeURIComponent(
          deleteReason
        )}`,
        { method: 'DELETE' }
      )

      if (!response.ok) throw new Error('Failed to delete coach')

      setMessage({ type: 'success', text: `Coach ${deleteMode === 'retire' ? 'retired' : 'purged'} successfully` })
      setShowDeleteModal(false)
      setTimeout(() => onRefresh(), 1000)
    } catch (error) {
      setMessage({ type: 'error', text: `${error}` })
    } finally {
      setDeleting(false)
    }
  }

  const handleRestore = async () => {
    try {
      const response = await fetch(`${API_BASE}/coaches/${encodeURIComponent(coachId)}/restore`, {
        method: 'POST'
      })

      if (!response.ok) throw new Error('Failed to restore coach')

      const result = await response.json()
      setMessage({ type: 'success', text: `Coach restored from ${result.source}` })
      setTimeout(() => onRefresh(), 1000)
    } catch (error) {
      setMessage({ type: 'error', text: `${error}` })
    }
  }

  return (
    <div className="space-y-6">
      {/* Coach Header */}
      <div className="pb-3 border-b border-gray-200">
        <h2 className="text-xl font-bold text-gray-900">{coachLabel}</h2>
        <p className="text-sm text-gray-500 mt-1">Rename, retire, or restore this coach</p>
      </div>

      {message && (
        <div
          className={`p-3 rounded-md text-sm ${
            message.type === 'success' ? 'bg-green-50 text-green-800 border border-green-200' : 'bg-red-50 text-red-800 border border-red-200'
          }`}
        >
          {message.text}
        </div>
      )}

      {/* Action Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Rename */}
        <div className="border border-gray-200 rounded-md p-4">
          <h3 className="font-semibold text-gray-900 mb-2">✏️ Rename Coach</h3>
          <p className="text-sm text-gray-600 mb-4">Change the coach ID and label across all integration layers</p>
          <button
            onClick={handleStartRename}
            disabled={coachStatus === 'retired'}
            className="w-full px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium"
          >
            Rename Coach
          </button>
        </div>

        {/* Retire/Delete */}
        <div className="border border-gray-200 rounded-md p-4">
          <h3 className="font-semibold text-gray-900 mb-2">🗑️ Retire / Delete</h3>
          <p className="text-sm text-gray-600 mb-4">Temporarily retire or permanently delete this coach</p>
          <button
            onClick={handleStartDelete}
            disabled={coachStatus === 'retired'}
            className="w-full px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium"
          >
            Retire / Delete
          </button>
        </div>

        {/* Restore */}
        <div className="border border-gray-200 rounded-md p-4">
          <h3 className="font-semibold text-gray-900 mb-2">♻️ Restore Coach</h3>
          <p className="text-sm text-gray-600 mb-4">Restore a previously retired or deleted coach</p>
          <button
            onClick={handleRestore}
            disabled={coachStatus !== 'retired'}
            className="w-full px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium"
          >
            Restore Coach
          </button>
        </div>
      </div>

      {/* Rename Modal */}
      {showRenameModal && (
        <div className="fixed inset-0 bg-black bg-opacity-30 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6 space-y-4">
              <h3 className="text-lg font-semibold text-gray-900">
                {renameStep === 1 && 'Step 1: Enter New Coach Details'}
                {renameStep === 2 && 'Step 2: Review Changes'}
              </h3>

              {renameStep === 1 && (
                <>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">New Coach ID</label>
                    <input
                      type="text"
                      value={newCoachId}
                      onChange={(e) => setNewCoachId(e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md"
                      placeholder="e.g., new_coach_id"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">New Display Label</label>
                    <input
                      type="text"
                      value={newLabel}
                      onChange={(e) => setNewLabel(e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md"
                      placeholder="e.g., New Coach Name"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Reason (Optional)</label>
                    <textarea
                      value={renameReason}
                      onChange={(e) => setRenameReason(e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md"
                      rows={3}
                      placeholder="Why are you renaming this coach?"
                    />
                  </div>
                </>
              )}

              {renameStep === 2 && renamePreview && (
                <>
                  <div className="bg-blue-50 border border-blue-200 rounded-md p-4">
                    <div className="text-sm text-blue-900">
                      <strong>'{coachId}'</strong> → <strong>'{newCoachId}'</strong>
                    </div>
                    <div className="text-sm text-blue-700 mt-2">
                      {renamePreview.total_files} file(s) will be modified
                    </div>
                  </div>

                  <div className="max-h-60 overflow-y-auto space-y-2">
                    {renamePreview.files_to_modify.map((item, idx) => (
                      <div key={idx} className="text-sm bg-gray-50 p-2 rounded">
                        <div className="font-mono text-xs text-gray-700">{item.file}</div>
                        <div className="text-gray-600 mt-1">{item.changes.join(', ')}</div>
                      </div>
                    ))}
                  </div>

                  <label className="flex items-center space-x-2">
                    <input type="checkbox" checked={renameConfirm} onChange={(e) => setRenameConfirm(e.target.checked)} />
                    <span className="text-sm text-gray-700">I understand this will modify {renamePreview.total_files} file(s)</span>
                  </label>
                </>
              )}

              <div className="flex justify-end space-x-2 pt-4 border-t">
                <button onClick={() => setShowRenameModal(false)} className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-800">
                  Cancel
                </button>
                {renameStep === 1 ? (
                  <button
                    onClick={handleRenamePreview}
                    disabled={!newCoachId || !newLabel || renaming}
                    className="px-4 py-2 rounded-md text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {renaming ? 'Loading...' : 'Preview Changes'}
                  </button>
                ) : (
                  <button
                    onClick={handleExecuteRename}
                    disabled={!renameConfirm || renaming}
                    className="px-4 py-2 rounded-md text-sm font-medium text-white bg-green-600 hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {renaming ? 'Renaming...' : 'Execute Rename'}
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Delete Modal - Simplified version */}
      {showDeleteModal && (
        <div className="fixed inset-0 bg-black bg-opacity-30 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full">
            <div className="p-6 space-y-4">
              <h3 className="text-lg font-semibold">
                Step {deleteStep}: {deleteStep === 1 ? 'Confirm' : deleteStep === 2 ? 'Review References' : 'Choose Mode'}
              </h3>

              {deleteStep === 1 && (
                <label className="flex items-center space-x-2">
                  <input type="checkbox" checked={deleteConfirm} onChange={(e) => setDeleteConfirm(e.target.checked)} />
                  <span>Yes, I want to proceed</span>
                </label>
              )}

              {deleteStep === 2 && (
                <div className="text-sm text-gray-700">
                  Found <strong>{references.length}</strong> reference(s) in the codebase.
                </div>
              )}

              {deleteStep === 3 && (
                <>
                  <div className="space-y-2">
                    <label className="flex items-center space-x-2">
                      <input type="radio" checked={deleteMode === 'retire'} onChange={() => setDeleteMode('retire')} />
                      <span>Retire (Reversible)</span>
                    </label>
                    <label className="flex items-center space-x-2">
                      <input type="radio" checked={deleteMode === 'purge'} onChange={() => setDeleteMode('purge')} />
                      <span>Purge (Permanent)</span>
                    </label>
                  </div>
                  <textarea
                    value={deleteReason}
                    onChange={(e) => setDeleteReason(e.target.value)}
                    placeholder="Reason..."
                    className="w-full px-3 py-2 border rounded-md"
                    rows={3}
                  />
                  <label className="flex items-center space-x-2">
                    <input type="checkbox" checked={deleteFinalConfirm} onChange={(e) => setDeleteFinalConfirm(e.target.checked)} />
                    <span>I understand this action</span>
                  </label>
                </>
              )}

              <div className="flex justify-end space-x-2 pt-4 border-t">
                <button onClick={() => setShowDeleteModal(false)} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800">
                  Cancel
                </button>
                {deleteStep < 3 ? (
                  <button
                    onClick={handleDeleteNext}
                    disabled={(deleteStep === 1 && !deleteConfirm)}
                    className="px-4 py-2 rounded-md text-sm text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50"
                  >
                    Next
                  </button>
                ) : (
                  <button
                    onClick={handleDelete}
                    disabled={!deleteFinalConfirm || deleting}
                    className="px-4 py-2 rounded-md text-sm text-white bg-red-600 hover:bg-red-700 disabled:opacity-50"
                  >
                    {deleting ? 'Processing...' : deleteMode === 'retire' ? 'Retire' : 'Purge'}
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
