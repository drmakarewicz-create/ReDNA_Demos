import { useEffect, useMemo, useState } from 'react'
import { Navigate, NavLink, Route, Routes, useParams, useNavigate, Link } from 'react-router-dom'
import userOpsApi, { UserSummary } from '@/lib/userOpsApi'
import HCTab from './tabs/HCTab'
import TriggersTab from './tabs/TriggersTab'
import HolisticTab from './tabs/HolisticTab'
import DeleteRenameTab from './tabs/DeleteRenameTab'
import PermissionsTab from './tabs/PermissionsTab'
import ProfileTab from './tabs/ProfileTab'

interface SummaryState {
  loading: boolean
  error: string | null
  summary: UserSummary | null
}

const tabs = [
  { key: 'profile', label: 'Profile', path: 'profile' },
  { key: 'hc', label: 'Head Coach', path: 'hc' },
  { key: 'triggers', label: 'Triggers', path: 'triggers' },
  { key: 'holistic', label: 'Holistic', path: 'holistic' },
  { key: 'permissions', label: 'Permissions', path: 'permissions' },
  { key: 'manage', label: 'Manage', path: 'manage' },
]

export default function UserDetail() {
  const params = useParams<{ userId: string }>()
  const userId = params.userId || ''
  const navigate = useNavigate()

  const [{ loading, error, summary }, setState] = useState<SummaryState>({
    loading: true,
    error: null,
    summary: null,
  })

  // Handle Escape key to navigate back
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        navigate('/user-ops')
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [navigate])

  useEffect(() => {
    if (!userId) {
      setState({ loading: false, error: 'Missing user id', summary: null })
      return
    }
    let cancelled = false
    setState(prev => ({ ...prev, loading: true, error: null }))
    userOpsApi
      .getUserSummary(userId)
      .then(result => {
        if (!cancelled) {
          setState({ loading: false, error: null, summary: result })
        }
      })
      .catch(err => {
        if (!cancelled) {
          setState({
            loading: false,
            error: err instanceof Error ? err.message : 'Failed to load user summary.',
            summary: null,
          })
        }
      })
    return () => {
      cancelled = true
    }
  }, [userId])

  const cardMetrics = useMemo(() => {
    if (!summary) return []
    return [
      { label: 'Evidence', value: summary.counts?.evidence ?? 0 },
      { label: 'Derived', value: summary.counts?.derived ?? 0 },
      { label: 'Containers', value: summary.counts?.containers ?? 0 },
      { label: 'Storage', value: formatBytes(summary.size_bytes) },
    ]
  }, [summary])

  if (!userId) {
    return (
      <div className="space-y-4">
        <h2 className="text-2xl font-semibold text-gray-900">User detail</h2>
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          Invalid URL: no user selected.
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-2 text-sm text-gray-600">
        <Link to="/user-ops" className="hover:text-blue-600 transition-colors">
          User Ops
        </Link>
        <span className="text-gray-400">›</span>
        <span className="text-gray-900 font-medium">{userId}</span>
      </nav>

      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <h1 className="text-3xl font-bold text-gray-900">🧬 {userId}</h1>
          </div>
          <button
            onClick={() => navigate('/user-ops')}
            className="text-sm text-blue-600 hover:text-blue-700 flex items-center gap-1 mb-2 transition-colors"
          >
            <span>←</span> All users
          </button>
          <p className="text-sm text-gray-600">
            Per-user controls for Head Coach, holistic review, consent, and lifecycle management.
          </p>
        </div>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {cardMetrics.map(metric => (
            <div
              key={metric.label}
              className="rounded-lg border border-gray-200 bg-white px-4 py-3 shadow-sm"
            >
              <div className="text-xs uppercase tracking-wide text-gray-500">{metric.label}</div>
              <div className="mt-1 text-lg font-semibold text-gray-900">{metric.value}</div>
            </div>
          ))}
        </div>
      </div>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
        <div className="border-b border-gray-200 px-4 pt-4">
          <nav className="-mb-px flex flex-wrap gap-3 text-sm font-medium text-gray-600">
            {tabs.map(tab => (
              <NavLink
                key={tab.key}
                to={tab.path}
                className={({ isActive }) =>
                  [
                    'rounded-t-md px-3 py-2 transition',
                    isActive
                      ? 'border-b-2 border-blue-600 bg-blue-50 text-blue-700'
                      : 'text-gray-600 hover:text-blue-600 hover:bg-blue-50',
                  ].join(' ')
                }
                end={tab.path === 'profile'}
              >
                {tab.label}
              </NavLink>
            ))}
          </nav>
        </div>
        <div className="px-6 py-6">
          <Routes>
            <Route index element={<Navigate to="profile" replace />} />
            <Route
              path="profile"
              element={<ProfileTab summary={summary} loading={loading} userId={userId} />}
            />
            <Route path="hc" element={<HCTab userId={userId} />} />
            <Route path="triggers" element={<TriggersTab userId={userId} />} />
            <Route path="holistic" element={<HolisticTab userId={userId} />} />
            <Route path="permissions" element={<PermissionsTab userId={userId} />} />
            <Route path="manage" element={<DeleteRenameTab userId={userId} />} />
            <Route path="*" element={<Navigate to="profile" replace />} />
          </Routes>
        </div>
      </div>
    </div>
  )
}

function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes)) return '—'
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const index = Math.floor(Math.log(bytes) / Math.log(1024))
  const value = bytes / Math.pow(1024, index)
  return `${value.toFixed(1)} ${units[index]}`
}
