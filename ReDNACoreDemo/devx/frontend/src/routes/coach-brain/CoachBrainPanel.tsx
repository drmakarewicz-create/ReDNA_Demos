import { useEffect, useMemo, useState } from 'react'
import { ActivationSnapshot, getCoachBrain } from '../../lib/coachInsightsApi'
import ChorusPreviewButton from '../../components/ChorusPreviewButton'
import { userOpsHC } from '../../lib/routes'
import { Link } from 'react-router-dom'

interface ActivationGraphProps {
  snapshot: ActivationSnapshot | null
}

interface Position {
  x: number
  y: number
}

const GRAPH_WIDTH = 520
const GRAPH_HEIGHT = 360
const CENTER: Position = { x: GRAPH_WIDTH / 2, y: GRAPH_HEIGHT / 2 }

const COLOR_MAP: Record<string, string> = {
  head_coach: '#1d4ed8',
  head_coach_role: '#1d4ed8',
  curiosity_engine: '#059669',
  learning: '#7c3aed',
  permission: '#f97316',
  augment: '#f97316',
}

const LEGEND = [
  { label: 'Head Coach', color: '#1d4ed8' },
  { label: 'Augment', color: '#fb923c' },
  { label: 'Curiosity Engine', color: '#059669' },
  { label: 'Self-Improvement', color: '#7c3aed' },
  { label: 'Permission Guard', color: '#f97316' },
]

function nodeColor(id: string): string {
  if (COLOR_MAP[id]) return COLOR_MAP[id]
  if (id === 'permission_guard') return '#f97316'
  if (id.includes('permission')) return '#f97316'
  if (id.includes('curiosity')) return '#059669'
  if (id.includes('learning')) return '#7c3aed'
  return '#fb923c'
}

function computePositions(nodes: ActivationSnapshot['nodes']): Record<string, Position> {
  const positions: Record<string, Position> = {}

  const basePositions: Record<string, Position> = {
    head_coach: CENTER,
    head_coach_role: { x: CENTER.x + 140, y: CENTER.y + 20 },
    curiosity_engine: { x: CENTER.x - 180, y: CENTER.y - 120 },
    learning: { x: CENTER.x + 180, y: CENTER.y - 120 },
    permission: { x: CENTER.x - 180, y: CENTER.y + 130 },
  }

  nodes.forEach((node) => {
    if (basePositions[node.id]) {
      positions[node.id] = basePositions[node.id]
    }
  })

  const fallbackSlots: Position[] = [
    { x: CENTER.x + 190, y: CENTER.y + 140 },
    { x: CENTER.x + 180, y: CENTER.y },
    { x: CENTER.x, y: CENTER.y + 150 },
    { x: CENTER.x - 60, y: CENTER.y - 180 },
  ]

  let fallbackIndex = 0
  nodes.forEach((node) => {
    if (!positions[node.id]) {
      positions[node.id] = fallbackSlots[fallbackIndex] || {
        x: CENTER.x + 120 * Math.cos(fallbackIndex),
        y: CENTER.y + 120 * Math.sin(fallbackIndex),
      }
      fallbackIndex += 1
    }
  })

  return positions
}

interface EmptyStateProps {
  userId: string
}

function EmptyState({ userId }: EmptyStateProps) {
  return (
    <div className="flex items-center justify-center h-80 bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-200 rounded-lg shadow-sm">
      <div className="text-center max-w-md px-6">
        <div className="text-6xl mb-4">🧠</div>
        <p className="text-lg font-semibold text-gray-900 mb-2">No activation snapshot yet</p>
        <p className="text-sm text-gray-600 mb-6">
          Run a Head Coach turn or daemon cycle to generate an activation graph. The snapshot will appear here after the next orchestration decision.
        </p>
        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <button
            disabled
            className="px-4 py-2 bg-gray-300 text-gray-500 rounded-md text-sm font-medium cursor-not-allowed"
          >
            Chorus Preview (disabled)
          </button>
          <Link
            to={userOpsHC(userId)}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm font-medium transition-colors"
          >
            Open Head Coach settings
          </Link>
        </div>
      </div>
    </div>
  )
}

function ActivationGraph({ snapshot, userId }: ActivationGraphProps & { userId: string }) {
  if (!snapshot) {
    return <EmptyState userId={userId} />
  }

  const positions = computePositions(snapshot.nodes)

  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-sm">
      <svg width={GRAPH_WIDTH} height={GRAPH_HEIGHT} viewBox={`0 0 ${GRAPH_WIDTH} ${GRAPH_HEIGHT}`}>
        {/* Edges */}
        {snapshot.edges.map((edge, idx) => {
          const from = positions[edge.from]
          const to = positions[edge.to]
          if (!from || !to) return null
          const strength = Math.max(0.5, edge.strength || 0.1)
          return (
            <line
              key={`${edge.from}-${edge.to}-${idx}`}
              x1={from.x}
              y1={from.y}
              x2={to.x}
              y2={to.y}
              stroke="#cbd5f5"
              strokeWidth={2 + strength * 4}
              strokeLinecap="round"
              opacity={0.9}
            />
          )
        })}

        {/* Nodes */}
        {snapshot.nodes.map((node) => {
          const position = positions[node.id]
          if (!position) return null
          const weight = Math.max(0.1, node.weight || 0)
          const radius = 20 + weight * 18
          const color = nodeColor(node.id === snapshot.active_coach_id ? 'augment' : node.id)
          return (
            <g key={node.id} transform={`translate(${position.x}, ${position.y})`}>
              {node.active && (
                <circle
                  r={radius + 12}
                  fill={color}
                  opacity={0.15}
                />
              )}
              <circle
                r={radius}
                fill="white"
                stroke={color}
                strokeWidth={3}
                opacity={node.active ? 1 : 0.85}
                className={node.active ? 'shadow-lg' : ''}
              />
              <text
                textAnchor="middle"
                dy={4}
                className="text-xs font-semibold"
                fill={node.active ? '#111827' : '#374151'}
              >
                {node.label}
              </text>
              <text
                textAnchor="middle"
                dy={22}
                className="text-[10px] font-mono"
                fill="#6b7280"
              >
                w={weight.toFixed(2)}
              </text>
            </g>
          )
        })}
      </svg>
      <div className="px-6 pb-4">
        <div className="flex flex-wrap gap-3 text-xs text-gray-600">
          {LEGEND.map((item) => (
            <span key={item.label} className="inline-flex items-center gap-2">
              <span
                className="inline-block w-3 h-3 rounded-full"
                style={{ backgroundColor: item.color }}
              />
              {item.label}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}

const DEFAULT_USER_ID = 'TEST'

export default function CoachBrainPanel() {
  const [userField, setUserField] = useState(DEFAULT_USER_ID)
  const [userId, setUserId] = useState(DEFAULT_USER_ID)
  const [snapshot, setSnapshot] = useState<ActivationSnapshot | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdated, setLastUpdated] = useState<string | null>(null)

  const loadSnapshot = async (targetUser: string) => {
    setLoading(true)
    setError(null)
    try {
      const data = await getCoachBrain(targetUser)
      setSnapshot(data)
      setLastUpdated(new Date().toLocaleTimeString())
    } catch (err) {
      // Only show error for real failures, not 404/empty
      setError(err instanceof Error ? err.message : 'Failed to load activation snapshot')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadSnapshot(userId)
  }, [userId])

  const activeCoachLabel = useMemo(() => {
    if (!snapshot) return '—'
    const activeNode = snapshot.nodes.find((node) => node.id === snapshot.active_coach_id)
    return activeNode?.label || snapshot.active_coach_id
  }, [snapshot])

  const curiosityTarget = snapshot?.meta?.curiosity_target || '—'
  const curiosityPriority =
    snapshot && typeof snapshot.meta?.curiosity_priority === 'number'
      ? `${(snapshot.meta.curiosity_priority * 100).toFixed(0)}%`
      : '—'
  const requiresConsent = snapshot?.meta?.requires_consent ? 'Yes' : 'No'
  const augmentConfidence =
    snapshot && typeof snapshot.meta?.augment_confidence === 'number'
      ? `${(snapshot.meta.augment_confidence * 100).toFixed(0)}%`
      : '—'
  const learningPositive =
    snapshot && typeof snapshot.meta?.learning_positive_rate === 'number'
      ? `${(snapshot.meta.learning_positive_rate * 100).toFixed(0)}%`
      : '—'

  const handleSubmitUser = () => {
    const sanitized = userField.trim()
    if (sanitized.length === 0) return
    setUserId(sanitized)
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">🧠 Coach Brain</h1>
          <p className="text-sm text-gray-600 mt-1">
            Live activation graph for Head Coach orchestration — visualize curiosity, learning, and permission flows per turn.
          </p>
          {lastUpdated && (
            <p className="text-xs text-gray-400 mt-1">Last updated {lastUpdated}</p>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <label htmlFor="coach-brain-user" className="text-xs uppercase tracking-wide text-gray-500">
              User ID
            </label>
            <input
              id="coach-brain-user"
              value={userField}
              onChange={(e) => setUserField(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  handleSubmitUser()
                }
              }}
              className="px-3 py-1.5 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              onClick={handleSubmitUser}
              className="px-3 py-1.5 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm font-medium"
            >
              Set
            </button>
          </div>
          <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-700">
            v{snapshot?.context_version ?? '—'}
          </span>
          <button
            onClick={() => loadSnapshot(userId)}
            disabled={loading}
            className="px-3 py-1.5 bg-white text-blue-600 border border-blue-200 rounded-md hover:bg-blue-50 text-sm font-medium disabled:opacity-50"
          >
            {loading ? 'Refreshing…' : 'Refresh'}
          </button>
          <ChorusPreviewButton userId={userId} contextVersion={snapshot?.context_version} />
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md text-sm">
          {error}
        </div>
      )}

      <ActivationGraph snapshot={snapshot} userId={userId} />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
          <div className="text-xs uppercase text-gray-500 mb-1">Active Coach</div>
          <div className="text-lg font-semibold text-gray-900">{activeCoachLabel}</div>
          <div className="text-xs text-gray-500 mt-2">
            Confidence: <span className="font-mono">{augmentConfidence}</span>
          </div>
        </div>

        <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
          <div className="text-xs uppercase text-gray-500 mb-1">Curiosity Target</div>
          <div className="text-sm font-medium text-gray-900 truncate">{curiosityTarget}</div>
          <div className="text-xs text-gray-500 mt-2">
            Priority: <span className="font-mono">{curiosityPriority}</span>
          </div>
        </div>

        <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
          <div className="text-xs uppercase text-gray-500 mb-1">Learning Influence</div>
          <div className="text-sm font-medium text-gray-900">{learningPositive}</div>
          <div className="text-xs text-gray-500 mt-2">
            Requires Consent:{' '}
            <span className="font-mono">{requiresConsent}</span>
          </div>
        </div>
      </div>
    </div>
  )
}
