/**
 * Life OS Dashboard - Multi-user Analytics
 * Phase 4: Visual dashboards for DevX operators
 */

import { useEffect, useState, useMemo } from 'react'
import { lifeDashboardApi, UserAggregate, QuadrantShare } from '@/lib/lifeDashboardApi'
import { Link } from 'react-router-dom'

// ============================================================================
// Types
// ============================================================================

type SortKey = 'user_id' | 'streak' | 'completed' | 'success_rate' | 'at_risk'
type SortDirection = 'asc' | 'desc'

interface FilterState {
  search: string
  teamNamespace: string
  minStreak: number
  showAtRiskOnly: boolean
}

// ============================================================================
// Helper Functions
// ============================================================================

function formatPercentage(value: number): string {
  return `${(value * 100).toFixed(0)}%`
}

function getQuadrantColor(quadrant: keyof QuadrantShare): string {
  const colors = {
    IU: 'bg-red-500',     // Important & Urgent - critical
    IN: 'bg-blue-500',    // Important & Not Urgent - strategic
    NU: 'bg-yellow-500',  // Not Important & Urgent - distraction
    NN: 'bg-gray-400'     // Not Important & Not Urgent - waste
  }
  return colors[quadrant] || 'bg-gray-400'
}

function getStreakBadgeColor(streak: number): string {
  if (streak >= 7) return 'bg-green-600 text-white'
  if (streak >= 3) return 'bg-green-500 text-white'
  if (streak >= 1) return 'bg-green-400 text-gray-900'
  return 'bg-gray-300 text-gray-700'
}

// ============================================================================
// Sub-Components
// ============================================================================

function KPICard({ label, value, icon }: { label: string; value: string | number; icon: string }) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-600">{label}</p>
          <p className="text-2xl font-bold text-gray-900 mt-1">{value}</p>
        </div>
        <span className="text-3xl">{icon}</span>
      </div>
    </div>
  )
}

function QuadrantHeatmap({ quadrant_share }: { quadrant_share: QuadrantShare }) {
  const quadrants: (keyof QuadrantShare)[] = ['IU', 'IN', 'NU', 'NN']
  const labels = {
    IU: 'Important & Urgent',
    IN: 'Important & Not Urgent',
    NU: 'Not Important & Urgent',
    NN: 'Not Important & Not Urgent'
  }

  return (
    <div className="grid grid-cols-2 gap-2">
      {quadrants.map((q) => {
        const value = quadrant_share[q] || 0
        return (
          <div key={q} className="bg-gray-50 rounded p-2">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-medium text-gray-700">{q}</span>
              <span className="text-xs font-bold text-gray-900">{formatPercentage(value)}</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-1.5">
              <div
                className={`h-1.5 rounded-full ${getQuadrantColor(q)}`}
                style={{ width: `${value * 100}%` }}
              />
            </div>
            <p className="text-[10px] text-gray-500 mt-1">{labels[q]}</p>
          </div>
        )
      })}
    </div>
  )
}

function TrendSparkline({ trends }: { trends: { week_label: string; completion_rate: number }[] }) {
  if (!trends || trends.length === 0) {
    return <span className="text-xs text-gray-400">No data</span>
  }

  const maxRate = Math.max(...trends.map(t => t.completion_rate), 1)
  const points = trends.map((t, i) => {
    const x = (i / (trends.length - 1 || 1)) * 100
    const y = 100 - ((t.completion_rate / maxRate) * 100)
    return `${x},${y}`
  }).join(' ')

  return (
    <div className="relative w-32 h-8">
      <svg viewBox="0 0 100 100" className="w-full h-full" preserveAspectRatio="none">
        <polyline
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          points={points}
          className="text-blue-500"
        />
      </svg>
      <span className="text-[10px] text-gray-500 absolute -bottom-3 right-0">
        {formatPercentage(trends[trends.length - 1]?.completion_rate || 0)}
      </span>
    </div>
  )
}

// ============================================================================
// Main Component
// ============================================================================

export default function LifeDashboard() {
  const [aggregates, setAggregates] = useState<UserAggregate[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [days, setDays] = useState(14)

  // Sort & Filter state
  const [sortKey, setSortKey] = useState<SortKey>('completed')
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc')
  const [filters, setFilters] = useState<FilterState>({
    search: '',
    teamNamespace: '',
    minStreak: 0,
    showAtRiskOnly: false
  })

  // Load data
  useEffect(() => {
    loadDashboard()
  }, [days])

  async function loadDashboard() {
    setLoading(true)
    setError(null)

    try {
      const data = await lifeDashboardApi.getAggregates(days)
      setAggregates(data)
    } catch (err: any) {
      setError(err.message || 'Failed to load dashboard')
    } finally {
      setLoading(false)
    }
  }

  // Filtering & Sorting
  const filteredAndSorted = useMemo(() => {
    let result = [...aggregates]

    // Apply filters
    if (filters.search) {
      const query = filters.search.toLowerCase()
      result = result.filter(u => u.user_id.toLowerCase().includes(query))
    }

    if (filters.teamNamespace) {
      result = result.filter(u => u.user_id.startsWith(filters.teamNamespace))
    }

    if (filters.minStreak > 0) {
      result = result.filter(u => u.kpis.current_streak >= filters.minStreak)
    }

    if (filters.showAtRiskOnly) {
      result = result.filter(u => u.kpis.goals_at_risk > 0)
    }

    // Apply sort
    result.sort((a, b) => {
      let aVal: any, bVal: any

      switch (sortKey) {
        case 'user_id':
          aVal = a.user_id
          bVal = b.user_id
          break
        case 'streak':
          aVal = a.kpis.current_streak
          bVal = b.kpis.current_streak
          break
        case 'completed':
          aVal = a.kpis.todos_completed
          bVal = b.kpis.todos_completed
          break
        case 'success_rate':
          aVal = a.kpis.todays_three_success_rate
          bVal = b.kpis.todays_three_success_rate
          break
        case 'at_risk':
          aVal = a.kpis.goals_at_risk
          bVal = b.kpis.goals_at_risk
          break
        default:
          return 0
      }

      if (typeof aVal === 'string') {
        return sortDirection === 'asc'
          ? aVal.localeCompare(bVal)
          : bVal.localeCompare(aVal)
      }

      return sortDirection === 'asc' ? aVal - bVal : bVal - aVal
    })

    return result
  }, [aggregates, filters, sortKey, sortDirection])

  // Summary stats
  const stats = useMemo(() => {
    const totalUsers = aggregates.length
    const activeUsers = aggregates.filter(u => u.kpis.todos_completed > 0).length
    const totalCompleted = aggregates.reduce((sum, u) => sum + u.kpis.todos_completed, 0)
    const avgStreak = aggregates.length > 0
      ? (aggregates.reduce((sum, u) => sum + u.kpis.current_streak, 0) / totalUsers).toFixed(1)
      : '0.0'
    const usersAtRisk = aggregates.filter(u => u.kpis.goals_at_risk > 0).length

    return { totalUsers, activeUsers, totalCompleted, avgStreak, usersAtRisk }
  }, [aggregates])

  // Handle sort
  function handleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc')
    } else {
      setSortKey(key)
      setSortDirection('desc')
    }
  }

  // Render
  return (
    <div className="min-h-screen bg-gray-50 p-6">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900">Life OS Dashboard</h1>
        <p className="text-gray-600 mt-1">Multi-user analytics and insights</p>
      </div>

      {/* Summary KPIs */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4 mb-6">
        <KPICard label="Total Users" value={stats.totalUsers} icon="👥" />
        <KPICard label="Active Users" value={stats.activeUsers} icon="✅" />
        <KPICard label="Tasks Completed" value={stats.totalCompleted} icon="📋" />
        <KPICard label="Avg Streak" value={`${stats.avgStreak}d`} icon="🔥" />
        <KPICard label="At Risk" value={stats.usersAtRisk} icon="⚠️" />
      </div>

      {/* Controls */}
      <div className="bg-white rounded-lg border border-gray-200 p-4 mb-6">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {/* Search */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Search User ID</label>
            <input
              type="text"
              value={filters.search}
              onChange={(e) => setFilters({ ...filters, search: e.target.value })}
              placeholder="user123"
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* Team/Namespace */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Team/Namespace</label>
            <input
              type="text"
              value={filters.teamNamespace}
              onChange={(e) => setFilters({ ...filters, teamNamespace: e.target.value })}
              placeholder="team-"
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* Min Streak */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Min Streak</label>
            <input
              type="number"
              value={filters.minStreak}
              onChange={(e) => setFilters({ ...filters, minStreak: parseInt(e.target.value) || 0 })}
              min="0"
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* Time Window */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Time Window</label>
            <select
              value={days}
              onChange={(e) => setDays(parseInt(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
            >
              <option value="7">7 days</option>
              <option value="14">14 days</option>
              <option value="30">30 days</option>
            </select>
          </div>
        </div>

        <div className="mt-3">
          <label className="flex items-center">
            <input
              type="checkbox"
              checked={filters.showAtRiskOnly}
              onChange={(e) => setFilters({ ...filters, showAtRiskOnly: e.target.checked })}
              className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <span className="ml-2 text-sm text-gray-700">Show at-risk users only</span>
          </label>
        </div>
      </div>

      {/* Loading/Error States */}
      {loading && (
        <div className="bg-white rounded-lg border border-gray-200 p-12 text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading dashboard...</p>
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
          <p className="text-red-800 font-medium">Error loading dashboard</p>
          <p className="text-red-600 text-sm mt-1">{error}</p>
          <button
            onClick={loadDashboard}
            className="mt-3 px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700"
          >
            Retry
          </button>
        </div>
      )}

      {/* User Table */}
      {!loading && !error && (
        <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th
                    className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                    onClick={() => handleSort('user_id')}
                  >
                    User ID {sortKey === 'user_id' && (sortDirection === 'asc' ? '↑' : '↓')}
                  </th>
                  <th
                    className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                    onClick={() => handleSort('streak')}
                  >
                    Streak {sortKey === 'streak' && (sortDirection === 'asc' ? '↑' : '↓')}
                  </th>
                  <th
                    className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                    onClick={() => handleSort('completed')}
                  >
                    Completed {sortKey === 'completed' && (sortDirection === 'asc' ? '↑' : '↓')}
                  </th>
                  <th
                    className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                    onClick={() => handleSort('success_rate')}
                  >
                    Success % {sortKey === 'success_rate' && (sortDirection === 'asc' ? '↑' : '↓')}
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">
                    Top Tag
                  </th>
                  <th
                    className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                    onClick={() => handleSort('at_risk')}
                  >
                    At Risk {sortKey === 'at_risk' && (sortDirection === 'asc' ? '↑' : '↓')}
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">
                    Trend
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">
                    Quadrants
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {filteredAndSorted.length === 0 && (
                  <tr>
                    <td colSpan={9} className="px-4 py-8 text-center text-gray-500">
                      No users match the current filters
                    </td>
                  </tr>
                )}
                {filteredAndSorted.map((user) => (
                  <tr key={user.user_id} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <Link
                        to={`/user-ops/${user.user_id}/hc`}
                        className="text-blue-600 hover:text-blue-800 font-medium"
                      >
                        {user.user_id}
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${getStreakBadgeColor(user.kpis.current_streak)}`}>
                        🔥 {user.kpis.current_streak}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-900">
                      {user.kpis.todos_completed}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-900">
                      {formatPercentage(user.kpis.todays_three_success_rate)}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {user.kpis.top_tag || '—'}
                    </td>
                    <td className="px-4 py-3">
                      {user.kpis.goals_at_risk > 0 ? (
                        <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-red-100 text-red-800">
                          ⚠️ {user.kpis.goals_at_risk}
                        </span>
                      ) : (
                        <span className="text-xs text-gray-400">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <TrendSparkline trends={user.trends} />
                    </td>
                    <td className="px-4 py-3">
                      <div className="w-48">
                        <QuadrantHeatmap quadrant_share={user.quadrant_share} />
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <Link
                        to={`/user-ops/${user.user_id}/hc`}
                        className="text-sm text-blue-600 hover:text-blue-800"
                      >
                        View →
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Footer */}
          <div className="bg-gray-50 px-4 py-3 border-t border-gray-200">
            <p className="text-sm text-gray-600">
              Showing {filteredAndSorted.length} of {aggregates.length} users
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
