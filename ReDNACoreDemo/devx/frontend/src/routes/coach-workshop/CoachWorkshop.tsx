import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import FeaturesTab from './tabs/FeaturesTab'
import ChecklistTab from './tabs/ChecklistTab'
import ManageTab from './tabs/ManageTab'
import TestsTab from './tabs/TestsTab'
import MetadataTab from './tabs/MetadataTab'
import InsightsTab from './tabs/InsightsTab'
import PlaygroundTab from './tabs/PlaygroundTab'
import ChorusPreviewButton from '../../components/ChorusPreviewButton'
import { DEVX_API_BASE } from '@/lib/env'

interface CoachInfo {
  id: string
  label: string
  filename: string
  prompt_path: string
  exists: boolean
  status: 'present' | 'missing' | 'retired'
  size_bytes: number
}

interface CoachDetail {
  id: string
  name: string
  display_name: string
  path: string
  text: string
  exists: boolean
  size_bytes: number
  modified_at: string
}

interface Reference {
  file: string
  line: number
  content: string
}

const API_BASE = DEVX_API_BASE

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  const index = Math.floor(Math.log(bytes) / Math.log(1024))
  const value = bytes / Math.pow(1024, index)
  return `${value.toFixed(1)} ${units[index]}`
}

function formatDate(isoString: string): string {
  try {
    return new Date(isoString).toLocaleString()
  } catch {
    return isoString
  }
}

export default function CoachWorkshop() {
  const [searchParams, setSearchParams] = useSearchParams()
  const activeTab = searchParams.get('tab') || 'prompt'

  const [coaches, setCoaches] = useState<CoachInfo[]>([])
  const [selectedCoachId, setSelectedCoachId] = useState<string | null>(null)
  const [coachDetail, setCoachDetail] = useState<CoachDetail | null>(null)
  const [editedText, setEditedText] = useState('')
  const [isDirty, setIsDirty] = useState(false)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [includeRetired, setIncludeRetired] = useState(false)

  const setActiveTab = (tab: string) => {
    setSearchParams({ tab })
  }

  // New Coach wizard state
  const [showNewCoachModal, setShowNewCoachModal] = useState(false)
  const [newCoachStep, setNewCoachStep] = useState(1)
  const [newCoachId, setNewCoachId] = useState('')
  const [newCoachLabel, setNewCoachLabel] = useState('')
  const [newCoachDescription, setNewCoachDescription] = useState('')
  const [creating, setCreating] = useState(false)

  // Deletion modal state
  const [showDeleteModal, setShowDeleteModal] = useState(false)
  const [deleteStep, setDeleteStep] = useState(1)
  const [deleteMode, setDeleteMode] = useState<'retire' | 'purge'>('retire')
  const [deleteReason, setDeleteReason] = useState('')
  const [deleteConfirm, setDeleteConfirm] = useState(false)
  const [deleteFinalConfirm, setDeleteFinalConfirm] = useState(false)
  const [references, setReferences] = useState<Reference[]>([])
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    loadCoaches()
  }, [includeRetired])

  useEffect(() => {
    if (selectedCoachId) {
      loadCoachDetail(selectedCoachId)
    } else {
      setCoachDetail(null)
      setEditedText('')
      setIsDirty(false)
    }
  }, [selectedCoachId])

  const loadCoaches = async () => {
    try {
      setLoading(true)
      setError(null)
      const url = `${API_BASE}/coaches${includeRetired ? '?include_retired=true' : ''}`
      const response = await fetch(url)
      if (!response.ok) {
        throw new Error(`Failed to load coaches: ${response.status} ${response.statusText}`)
      }
      const data: CoachInfo[] = await response.json()
      setCoaches(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load coaches')
    } finally {
      setLoading(false)
    }
  }

  const loadCoachDetail = async (coachId: string) => {
    try {
      setLoading(true)
      setError(null)
      const response = await fetch(`${API_BASE}/coaches/${encodeURIComponent(coachId)}`)
      if (!response.ok) {
        throw new Error(`Failed to load coach: ${response.status} ${response.statusText}`)
      }
      const data: CoachDetail = await response.json()
      setCoachDetail(data)
      setEditedText(data.text)
      setIsDirty(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load coach detail')
    } finally {
      setLoading(false)
    }
  }

  const handleTextChange = (newText: string) => {
    setEditedText(newText)
    setIsDirty(newText !== coachDetail?.text)
    setSuccessMessage(null)
  }

  const handleSave = async () => {
    if (!selectedCoachId || !isDirty) return

    try {
      setSaving(true)
      setError(null)
      const response = await fetch(`${API_BASE}/coaches/${encodeURIComponent(selectedCoachId)}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ text: editedText }),
      })

      if (!response.ok) {
        throw new Error(`Failed to save: ${response.status} ${response.statusText}`)
      }

      const result = await response.json()
      setSuccessMessage(
        `Saved ${result.name}. ${result.backup_created ? `Backup: ${result.backup_path}` : 'No backup (new file)'}`
      )
      setIsDirty(false)

      await loadCoachDetail(selectedCoachId)
      await loadCoaches()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save coach prompt')
    } finally {
      setSaving(false)
    }
  }

  const handleRevert = () => {
    if (coachDetail) {
      setEditedText(coachDetail.text)
      setIsDirty(false)
      setSuccessMessage(null)
    }
  }

  const handleCreateCoach = async () => {
    if (!newCoachId || !newCoachLabel) {
      setError('Coach ID and Label are required')
      return
    }

    setCreating(true)
    setError(null)

    try {
      const response = await fetch(`${API_BASE}/coaches/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          new_coach_id: newCoachId,
          new_label: newCoachLabel,
          description: newCoachDescription || 'New coach'
        })
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || `Failed to create coach: ${response.status}`)
      }

      const result = await response.json()
      setSuccessMessage(`Coach '${result.label}' created successfully!`)

      // Reset wizard state
      setShowNewCoachModal(false)
      setNewCoachStep(1)
      setNewCoachId('')
      setNewCoachLabel('')
      setNewCoachDescription('')

      // Reload coaches and select the new one
      await loadCoaches()
      setSelectedCoachId(result.coach_id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create coach')
    } finally {
      setCreating(false)
    }
  }

  const handleDownload = () => {
    if (!coachDetail) return

    const blob = new Blob([editedText], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${coachDetail.id}.md`
    a.click()
    URL.revokeObjectURL(url)
  }

  const openDeleteModal = () => {
    setShowDeleteModal(true)
    setDeleteStep(1)
    setDeleteMode('retire')
    setDeleteReason('')
    setDeleteConfirm(false)
    setDeleteFinalConfirm(false)
    setReferences([])
    setError(null)
  }

  const handleDeleteStepNext = async () => {
    if (deleteStep === 1 && deleteConfirm) {
      // Scan for references
      try {
        const response = await fetch(
          `${API_BASE}/coaches/${encodeURIComponent(selectedCoachId!)}?mode=${deleteMode}`,
          { method: 'DELETE' }
        )
        if (response.status === 409) {
          // References found
          const data = await response.json()
          setReferences(data.references_found || [])
          setDeleteStep(2)
        } else if (response.ok) {
          // No references, proceed
          const data = await response.json()
          setReferences(data.references_found || [])
          setDeleteStep(2)
        } else {
          throw new Error(`Failed to check references: ${response.status}`)
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to scan references')
      }
    } else if (deleteStep === 2) {
      setDeleteStep(3)
    }
  }

  const handleDelete = async () => {
    if (!selectedCoachId || !deleteFinalConfirm) return

    try {
      setDeleting(true)
      setError(null)

      const url = `${API_BASE}/coaches/${encodeURIComponent(selectedCoachId)}?mode=${deleteMode}&force=true${deleteReason ? `&reason=${encodeURIComponent(deleteReason)}` : ''}`

      const response = await fetch(url, { method: 'DELETE' })

      if (!response.ok) {
        throw new Error(`Failed to delete: ${response.status} ${response.statusText}`)
      }

      const result = await response.json()

      if (result.retired) {
        setSuccessMessage(`Coach "${selectedCoachId}" retired successfully`)
      } else if (result.purged) {
        setSuccessMessage(`Coach "${selectedCoachId}" purged successfully`)
      }

      setShowDeleteModal(false)
      setSelectedCoachId(null)
      await loadCoaches()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete coach')
    } finally {
      setDeleting(false)
    }
  }

  const handleRestore = async () => {
    if (!selectedCoachId) return

    try {
      setLoading(true)
      setError(null)

      const response = await fetch(`${API_BASE}/coaches/${encodeURIComponent(selectedCoachId)}/restore`, {
        method: 'POST',
      })

      if (!response.ok) {
        throw new Error(`Failed to restore: ${response.status} ${response.statusText}`)
      }

      const result = await response.json()
      setSuccessMessage(`Coach "${selectedCoachId}" restored from ${result.source}`)

      await loadCoaches()
      await loadCoachDetail(selectedCoachId)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to restore coach')
    } finally {
      setLoading(false)
    }
  }

  const selectedCoach = coaches.find((c) => c.id === selectedCoachId)

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h2 className="text-3xl font-bold text-gray-900">🎓 Coach Workshop</h2>
          <p className="mt-2 text-sm text-gray-600">
            Edit AI coach prompt files. Backups are automatically created on save.
          </p>
          <p className="text-xs text-gray-500 mt-1">
            Registry: {coaches.length} coaches ({coaches.filter((c) => c.status === 'present').length} present,{' '}
            {coaches.filter((c) => c.status === 'missing').length} missing)
          </p>
        </div>
        <div className="flex items-center gap-3">
          <ChorusPreviewButton userId="TEST" />
          <button
            onClick={() => {
              setNewCoachId('')
              setNewCoachLabel('')
              setNewCoachStep(1)
              setShowNewCoachModal(true)
            }}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm font-medium"
          >
            + New Coach
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md text-sm">
          {error}
        </div>
      )}

      {successMessage && (
        <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-md text-sm">
          {successMessage}
        </div>
      )}

      <div className="grid grid-cols-12 gap-6">
        {/* Coach List */}
        <div className="col-span-12 lg:col-span-4 space-y-4">
          <div className="bg-white border border-gray-200 rounded-md">
            <div className="px-4 py-3 border-b border-gray-200">
              <h3 className="text-sm font-semibold text-gray-800">Available Coaches</h3>
              <p className="text-xs text-gray-500 mt-1">{coaches.length} coach roles</p>
              <label className="flex items-center gap-2 mt-2 text-xs text-gray-600">
                <input
                  type="checkbox"
                  checked={includeRetired}
                  onChange={(e) => setIncludeRetired(e.target.checked)}
                  className="h-3 w-3"
                />
                <span>Show retired coaches</span>
              </label>
            </div>
            <div className="divide-y divide-gray-200 max-h-[600px] overflow-y-auto">
              {loading && coaches.length === 0 ? (
                <div className="px-4 py-8 text-center text-sm text-gray-500">Loading coaches...</div>
              ) : coaches.length === 0 ? (
                <div className="px-4 py-8 text-center text-sm text-gray-500">No coach roles found</div>
              ) : (
                coaches.map((coach) => (
                  <button
                    key={coach.id}
                    type="button"
                    onClick={() => setSelectedCoachId(coach.id)}
                    className={`w-full px-4 py-3 text-left hover:bg-gray-50 transition-colors ${
                      selectedCoachId === coach.id ? 'bg-blue-50 border-l-4 border-blue-600' : ''
                    } ${coach.status === 'retired' ? 'opacity-60' : ''}`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-gray-900 text-sm">{coach.label}</span>
                        {coach.status === 'present' ? (
                          <span className="inline-flex items-center rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700">
                            Present
                          </span>
                        ) : coach.status === 'retired' ? (
                          <span className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-700">
                            Retired
                          </span>
                        ) : (
                          <span className="inline-flex items-center rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700">
                            Scaffold
                          </span>
                        )}
                      </div>
                      <span className="text-xs text-gray-500">{formatBytes(coach.size_bytes)}</span>
                    </div>
                    <div className="text-xs text-gray-500 mt-1">{coach.filename}</div>
                  </button>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Editor Panel */}
        <div className="col-span-12 lg:col-span-8 space-y-4">
          {!selectedCoachId ? (
            <div className="bg-white border border-gray-200 rounded-md p-12 text-center text-gray-500">
              Select a coach from the list to edit its prompt
            </div>
          ) : loading ? (
            <div className="bg-white border border-gray-200 rounded-md p-12 text-center text-gray-500">
              Loading coach prompt...
            </div>
          ) : coachDetail ? (
            <>
              {/* Tab Navigation */}
              <div className="flex space-x-1 border-b border-gray-200 bg-white rounded-t-md">
                <button
                  onClick={() => setActiveTab('prompt')}
                  className={`px-4 py-2 text-sm font-medium rounded-t-md transition-colors ${
                    activeTab === 'prompt'
                      ? 'bg-white text-blue-600 border-b-2 border-blue-600'
                      : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                  }`}
                >
                  📝 Prompt
                </button>
                <button
                  onClick={() => setActiveTab('features')}
                  className={`px-4 py-2 text-sm font-medium rounded-t-md transition-colors ${
                    activeTab === 'features'
                      ? 'bg-white text-blue-600 border-b-2 border-blue-600'
                      : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                  }`}
                >
                  ⚙️ Features
                </button>
                <button
                  onClick={() => setActiveTab('checklist')}
                  className={`px-4 py-2 text-sm font-medium rounded-t-md transition-colors ${
                    activeTab === 'checklist'
                      ? 'bg-white text-blue-600 border-b-2 border-blue-600'
                      : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                  }`}
                >
                  ✅ Checklist
                </button>
                <button
                  onClick={() => setActiveTab('manage')}
                  className={`px-4 py-2 text-sm font-medium rounded-t-md transition-colors ${
                    activeTab === 'manage'
                      ? 'bg-white text-blue-600 border-b-2 border-blue-600'
                      : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                  }`}
                >
                  🔧 Manage
                </button>
                <button
                  onClick={() => setActiveTab('tests')}
                  className={`px-4 py-2 text-sm font-medium rounded-t-md transition-colors ${
                    activeTab === 'tests'
                      ? 'bg-white text-blue-600 border-b-2 border-blue-600'
                      : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                  }`}
                >
                  🧪 Tests
                </button>
                <button
                  onClick={() => setActiveTab('metadata')}
                  className={`px-4 py-2 text-sm font-medium rounded-t-md transition-colors ${
                    activeTab === 'metadata'
                      ? 'bg-white text-blue-600 border-b-2 border-blue-600'
                      : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                  }`}
                >
                  📊 Metadata
                </button>
                <button
                  onClick={() => setActiveTab('insights')}
                  className={`px-4 py-2 text-sm font-medium rounded-t-md transition-colors ${
                    activeTab === 'insights'
                      ? 'bg-white text-blue-600 border-b-2 border-blue-600'
                      : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                  }`}
                >
                  💡 Insights
                </button>
                <button
                  onClick={() => setActiveTab('playground')}
                  className={`px-4 py-2 text-sm font-medium rounded-t-md transition-colors ${
                    activeTab === 'playground'
                      ? 'bg-white text-blue-600 border-b-2 border-blue-600'
                      : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                  }`}
                >
                  🎮 Playground
                </button>
              </div>

              {/* Tab Content */}
              {activeTab === 'prompt' && (
              <>
              <div className="bg-white border border-gray-200 rounded-md">
                <div className="px-4 py-3 border-b border-gray-200">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <h3 className="text-sm font-semibold text-gray-800">{coachDetail.display_name}</h3>
                        {!coachDetail.exists && (
                          <span className="inline-flex items-center rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700">
                            Scaffold (not saved yet)
                          </span>
                        )}
                        {selectedCoach?.status === 'retired' && (
                          <span className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-700">
                            Retired
                          </span>
                        )}
                        {isDirty && (
                          <span className="inline-flex items-center rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
                            Unsaved changes
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-gray-500 mt-1">
                        {coachDetail.path} · {formatBytes(coachDetail.size_bytes)}
                        {coachDetail.exists && ` · Modified ${formatDate(coachDetail.modified_at)}`}
                      </p>
                    </div>
                  </div>
                </div>
                <div className="p-4">
                  <textarea
                    value={editedText}
                    onChange={(e) => handleTextChange(e.target.value)}
                    className="w-full h-[500px] px-3 py-2 border border-gray-300 rounded-md font-mono text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="Coach prompt text..."
                    spellCheck={false}
                  />
                </div>
              </div>

              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={handleSave}
                    disabled={!isDirty || saving}
                    className={`px-4 py-2 rounded-md text-sm font-medium text-white ${
                      !isDirty || saving ? 'bg-gray-300 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-700'
                    }`}
                  >
                    {saving ? 'Saving...' : coachDetail.exists ? 'Save Prompt' : 'Create Prompt'}
                  </button>
                  <button
                    type="button"
                    onClick={handleRevert}
                    disabled={!isDirty}
                    className={`px-4 py-2 rounded-md text-sm font-medium ${
                      !isDirty
                        ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                        : 'bg-white border border-gray-300 text-gray-700 hover:bg-gray-50'
                    }`}
                  >
                    Revert
                  </button>
                  <button
                    type="button"
                    onClick={handleDownload}
                    className="px-4 py-2 rounded-md text-sm font-medium bg-white border border-gray-300 text-gray-700 hover:bg-gray-50"
                  >
                    Download
                  </button>
                  {selectedCoach?.status === 'retired' ? (
                    <button
                      type="button"
                      onClick={handleRestore}
                      className="px-4 py-2 rounded-md text-sm font-medium bg-green-600 text-white hover:bg-green-700"
                    >
                      Restore Coach
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={openDeleteModal}
                      disabled={!coachDetail.exists}
                      className={`px-4 py-2 rounded-md text-sm font-medium ${
                        !coachDetail.exists
                          ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                          : 'bg-red-600 text-white hover:bg-red-700'
                      }`}
                    >
                      🗑 Retire / Delete
                    </button>
                  )}
                </div>
                <div className="text-xs text-gray-500">
                  {editedText.split('\n').length} lines · {editedText.length} characters
                </div>
              </div>
            </>
              )}

              {activeTab === 'features' && (
                <div className="bg-white border border-gray-200 rounded-md p-6">
                  <FeaturesTab coachId={selectedCoachId} coachLabel={coachDetail.display_name} />
                </div>
              )}

              {activeTab === 'checklist' && (
                <div className="bg-white border border-gray-200 rounded-md p-6">
                  <ChecklistTab coachId={selectedCoachId} coachLabel={coachDetail.display_name} />
                </div>
              )}

              {activeTab === 'manage' && (
                <div className="bg-white border border-gray-200 rounded-md p-6">
                  <ManageTab
                    coachId={selectedCoachId}
                    coachLabel={coachDetail.display_name}
                    coachStatus={selectedCoach?.status || 'present'}
                    onRefresh={() => {
                      loadCoaches()
                      if (selectedCoachId) loadCoachDetail(selectedCoachId)
                    }}
                  />
                </div>
              )}

              {activeTab === 'tests' && (
                <div className="bg-white border border-gray-200 rounded-md p-6">
                  <TestsTab coachId={selectedCoachId} coachLabel={coachDetail.display_name} />
                </div>
              )}

              {activeTab === 'metadata' && (
                <div className="bg-white border border-gray-200 rounded-md p-6">
                  <MetadataTab coachId={selectedCoachId} coachLabel={coachDetail.display_name} />
                </div>
              )}

              {activeTab === 'insights' && (
                <div className="bg-white border border-gray-200 rounded-md p-6">
                  <InsightsTab coachId={selectedCoachId} coachLabel={coachDetail.display_name} />
                </div>
              )}

              {activeTab === 'playground' && (
                <div className="bg-white border border-gray-200 rounded-md p-6">
                  <PlaygroundTab coachId={selectedCoachId} coachLabel={coachDetail.display_name} />
                </div>
              )}
            </>
          ) : null}
        </div>
      </div>

      {/* Delete Modal */}
      {showDeleteModal && (
        <div className="fixed inset-0 bg-black bg-opacity-30 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6 space-y-4">
              <h3 className="text-lg font-semibold text-gray-900">
                {deleteStep === 1 && 'Step 1: Confirm Coach Deletion'}
                {deleteStep === 2 && 'Step 2: Review References'}
                {deleteStep === 3 && 'Step 3: Choose Deletion Mode'}
              </h3>

              {deleteStep === 1 && (
                <>
                  <p className="text-sm text-gray-600">
                    You are about to retire or delete coach: <strong>{selectedCoachId}</strong>
                  </p>
                  <label className="flex items-center gap-2 text-sm">
                    <input type="checkbox" checked={deleteConfirm} onChange={(e) => setDeleteConfirm(e.target.checked)} />
                    <span>Yes, I want to proceed with this action</span>
                  </label>
                </>
              )}

              {deleteStep === 2 && (
                <>
                  <p className="text-sm text-gray-600">
                    Found <strong>{references.length}</strong> reference(s) in the codebase:
                  </p>
                  {references.length > 0 ? (
                    <div className="max-h-64 overflow-y-auto bg-gray-50 border border-gray-200 rounded p-3 text-xs">
                      {references.slice(0, 20).map((ref, idx) => (
                        <div key={idx} className="mb-2 font-mono">
                          <div className="text-blue-600">{ref.file}:{ref.line}</div>
                          <div className="text-gray-700 ml-4">{ref.content}</div>
                        </div>
                      ))}
                      {references.length > 20 && (
                        <div className="text-gray-500 mt-2">...and {references.length - 20} more</div>
                      )}
                    </div>
                  ) : (
                    <div className="text-sm text-green-600">No references found. Safe to delete.</div>
                  )}
                </>
              )}

              {deleteStep === 3 && (
                <>
                  <div className="space-y-3">
                    <label className="flex items-start gap-2">
                      <input
                        type="radio"
                        name="deleteMode"
                        checked={deleteMode === 'retire'}
                        onChange={() => setDeleteMode('retire')}
                        className="mt-1"
                      />
                      <div>
                        <div className="font-medium text-sm">Retire (Recommended)</div>
                        <div className="text-xs text-gray-600">
                          Safe and reversible. Moves prompt to prompts/retired/{selectedCoachId}/
                        </div>
                      </div>
                    </label>
                    <label className="flex items-start gap-2">
                      <input
                        type="radio"
                        name="deleteMode"
                        checked={deleteMode === 'purge'}
                        onChange={() => setDeleteMode('purge')}
                        className="mt-1"
                      />
                      <div>
                        <div className="font-medium text-sm text-red-700">Purge (Permanent)</div>
                        <div className="text-xs text-gray-600">
                          Moves to prompts/deleted/ and removes from active registry. Cannot be easily undone.
                        </div>
                      </div>
                    </label>
                    <div className="mt-4">
                      <label className="block text-sm font-medium text-gray-700 mb-1">Reason (optional)</label>
                      <textarea
                        value={deleteReason}
                        onChange={(e) => setDeleteReason(e.target.value)}
                        rows={2}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                        placeholder="Why are you retiring/deleting this coach?"
                      />
                    </div>
                    <label className="flex items-center gap-2 text-sm text-red-700 font-medium">
                      <input
                        type="checkbox"
                        checked={deleteFinalConfirm}
                        onChange={(e) => setDeleteFinalConfirm(e.target.checked)}
                      />
                      <span>Yes, I understand this action {deleteMode === 'purge' ? 'cannot be undone' : 'will retire this coach'}</span>
                    </label>
                  </div>
                </>
              )}

              <div className="flex justify-end space-x-2 pt-4 border-t">
                <button
                  type="button"
                  onClick={() => setShowDeleteModal(false)}
                  className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-800"
                >
                  Cancel
                </button>
                {deleteStep < 3 ? (
                  <button
                    type="button"
                    onClick={handleDeleteStepNext}
                    disabled={deleteStep === 1 && !deleteConfirm}
                    className={`px-4 py-2 rounded-md text-sm font-medium text-white ${
                      deleteStep === 1 && !deleteConfirm
                        ? 'bg-gray-300 cursor-not-allowed'
                        : 'bg-blue-600 hover:bg-blue-700'
                    }`}
                  >
                    Next
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={handleDelete}
                    disabled={!deleteFinalConfirm || deleting}
                    className={`px-4 py-2 rounded-md text-sm font-medium text-white ${
                      !deleteFinalConfirm || deleting
                        ? 'bg-gray-300 cursor-not-allowed'
                        : 'bg-red-600 hover:bg-red-700'
                    }`}
                  >
                    {deleting ? 'Processing...' : deleteMode === 'retire' ? 'Retire Coach' : 'Purge Coach'}
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* New Coach Wizard Modal */}
      {showNewCoachModal && (
        <div className="fixed inset-0 bg-black bg-opacity-30 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-3xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6 space-y-4">
              <h3 className="text-lg font-semibold text-gray-900">
                {newCoachStep === 1 && 'Step 1: Name & ID'}
                {newCoachStep === 2 && 'Step 2: Prompt Scaffold Preview'}
                {newCoachStep === 3 && 'Step 3: Features Scaffold Preview'}
                {newCoachStep === 4 && 'Step 4: Checklist Pre-Check'}
              </h3>

              {newCoachStep === 1 && (
                <>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Coach ID <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={newCoachId}
                      onChange={(e) => setNewCoachId(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ''))}
                      placeholder="e.g., wellness_coach"
                      className="w-full px-3 py-2 border border-gray-300 rounded-md font-mono text-sm"
                    />
                    <div className="text-xs text-gray-500 mt-1">
                      Lowercase letters, numbers, and underscores only
                    </div>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Display Label <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={newCoachLabel}
                      onChange={(e) => setNewCoachLabel(e.target.value)}
                      placeholder="e.g., Wellness Coach"
                      className="w-full px-3 py-2 border border-gray-300 rounded-md"
                    />
                    <div className="text-xs text-gray-500 mt-1">
                      User-facing name displayed in the UI
                    </div>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                    <textarea
                      value={newCoachDescription}
                      onChange={(e) => setNewCoachDescription(e.target.value)}
                      placeholder="Brief description of this coach's purpose"
                      className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm h-20"
                    />
                  </div>
                  <div className="bg-blue-50 border border-blue-200 rounded-md p-3 text-sm text-blue-800">
                    <strong>What happens next:</strong> Creates scaffold files, updates registries, and adds minimal integration entries.
                  </div>
                </>
              )}

              {newCoachStep === 2 && (
                <div className="space-y-3">
                  <div className="bg-gray-50 border border-gray-200 rounded-md p-4 max-h-80 overflow-y-auto font-mono text-xs">
                    {`# ${newCoachLabel || 'New Coach'}

**Purpose:**
Describe the primary purpose of this coach.

**Boundaries:**
What is in-scope and out-of-scope?

**Data Dependencies:**
Which DNA containers or traits required?

**Dialogue Tone:**
Personality and interaction style.

**Hand-off Rules:**
When to delegate to other coaches.

**Key Responsibilities:**
- Responsibility 1
- Responsibility 2
- Responsibility 3`}
                  </div>
                  <div className="text-xs text-gray-600">This scaffold will be created at <code>prompts/{newCoachId || 'new_coach'}_ai.md</code></div>
                </div>
              )}

              {newCoachStep === 3 && (
                <div className="space-y-3">
                  <div className="bg-gray-50 border border-gray-200 rounded-md p-4 max-h-80 overflow-y-auto font-mono text-xs">
                    {JSON.stringify({ version: "1.0", showInUI: true, panes: [] }, null, 2)}
                  </div>
                  <div className="text-xs text-gray-600">This scaffold will be created at <code>prompts/features/{newCoachId || 'new_coach'}_features.json</code></div>
                </div>
              )}

              {newCoachStep === 4 && (
                <div className="space-y-3">
                  <div className="text-sm text-gray-700">
                    After creation, the new coach will need integration across 7 layers:
                  </div>
                  <ul className="text-sm text-gray-600 space-y-1 pl-5 list-disc">
                    <li>Coach Registry (coach_registry.yaml)</li>
                    <li>Mode Manager (coach_mode_manager.py)</li>
                    <li>UI Roster (ui_readonly.py)</li>
                    <li>Frontend Roster (api.ts)</li>
                    <li>Frontend Normalize (page-client.tsx)</li>
                    <li>Prompts (api.py) - Optional</li>
                    <li>LLM Agent (hc_llm_agent.py) - Optional</li>
                  </ul>
                  <div className="bg-amber-50 border border-amber-200 rounded-md p-3 text-sm text-amber-800">
                    <strong>Note:</strong> The Checklist tab will help verify integration after creation.
                  </div>
                </div>
              )}

              <div className="flex justify-end space-x-2 pt-4 border-t">
                <button
                  onClick={() => setShowNewCoachModal(false)}
                  className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-800"
                >
                  Cancel
                </button>
                {newCoachStep > 1 && (
                  <button
                    onClick={() => setNewCoachStep(newCoachStep - 1)}
                    className="px-4 py-2 rounded-md text-sm font-medium bg-gray-100 text-gray-700 hover:bg-gray-200"
                  >
                    Back
                  </button>
                )}
                {newCoachStep < 4 ? (
                  <button
                    onClick={() => setNewCoachStep(newCoachStep + 1)}
                    disabled={newCoachStep === 1 && (!newCoachId || !newCoachLabel)}
                    className="px-4 py-2 rounded-md text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed"
                  >
                    Next
                  </button>
                ) : (
                  <button
                    onClick={handleCreateCoach}
                    disabled={creating || !newCoachId || !newCoachLabel}
                    className="px-4 py-2 rounded-md text-sm font-medium text-white bg-green-600 hover:bg-green-700 disabled:bg-gray-300 disabled:cursor-not-allowed"
                  >
                    {creating ? 'Creating...' : 'Create Coach'}
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
