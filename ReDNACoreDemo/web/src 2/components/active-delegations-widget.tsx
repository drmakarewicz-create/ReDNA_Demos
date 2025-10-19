"use client"

import { useState, useEffect } from "react"
import { Clock, CheckCircle2, ArrowRight, Loader2 } from "lucide-react"

interface ActiveDelegation {
  delegation_id: string
  coach: string
  status: "pending" | "active" | "completed"
  traits_collected: string[]
  curiosity_satisfied: number
  timestamp: string
  notes: string
}

interface ActiveDelegationsWidgetProps {
  userId: string
  onDelegationClick?: (delegationId: string) => void
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000"

export function ActiveDelegationsWidget({
  userId,
  onDelegationClick,
}: ActiveDelegationsWidgetProps) {
  const [delegations, setDelegations] = useState<ActiveDelegation[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchActiveDelegations()
    // Poll every 30 seconds for updates
    const interval = setInterval(fetchActiveDelegations, 30000)
    return () => clearInterval(interval)
  }, [userId])

  const fetchActiveDelegations = async () => {
    try {
      const response = await fetch(`${API_BASE}/delegation/${userId}/active`)
      if (!response.ok) throw new Error("Failed to fetch delegations")

      const data = await response.json()
      if (data.ok) {
        setDelegations(data.delegations || [])
      }
      setError(null)
    } catch (err) {
      console.error("Error fetching active delegations:", err)
      setError(err instanceof Error ? err.message : "Unknown error")
    } finally {
      setLoading(false)
    }
  }

  const getCoachDisplayName = (coachId: string) => {
    const names: Record<string, string> = {
      photo_coach: "Photo Coach",
      relationship_coach: "Relationship Coach",
      head_coach: "Head Coach",
    }
    return names[coachId] || coachId
  }

  const getCoachEmoji = (coachId: string) => {
    const emojis: Record<string, string> = {
      photo_coach: "📸",
      relationship_coach: "💝",
      head_coach: "🧠",
    }
    return emojis[coachId] || "🤖"
  }

  const getStatusColor = (status: string) => {
    if (status === "completed") return "text-green-400"
    if (status === "active") return "text-orange-400"
    return "text-slate-400"
  }

  const getStatusIcon = (status: string) => {
    if (status === "completed")
      return <CheckCircle2 className="h-3.5 w-3.5 text-green-400" />
    if (status === "active")
      return <Loader2 className="h-3.5 w-3.5 animate-spin text-orange-400" />
    return <Clock className="h-3.5 w-3.5 text-slate-400" />
  }

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 60000)

    if (diffMins < 1) return "just now"
    if (diffMins < 60) return `${diffMins}m ago`
    if (diffMins < 1440) return `${Math.floor(diffMins / 60)}h ago`
    return `${Math.floor(diffMins / 1440)}d ago`
  }

  if (loading) {
    return (
      <div className="rounded-lg border border-slate-700/50 bg-slate-900/30 p-4">
        <div className="flex items-center gap-2 text-sm text-slate-400">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading delegations...
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-800/50 bg-red-950/20 p-4">
        <p className="text-sm text-red-400">Error: {error}</p>
      </div>
    )
  }

  if (delegations.length === 0) {
    return null // Hide widget when no active delegations
  }

  return (
    <div className="rounded-lg border border-slate-700/50 bg-slate-900/30 p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-300">
          Active Delegations
        </h3>
        <span className="rounded-full bg-slate-800 px-2 py-0.5 text-xs font-medium text-slate-400">
          {delegations.length}
        </span>
      </div>

      <div className="space-y-2">
        {delegations.map((delegation) => (
          <button
            key={delegation.delegation_id}
            onClick={() => onDelegationClick?.(delegation.delegation_id)}
            className="
              w-full rounded-lg border border-slate-700/30 bg-slate-800/40
              p-3 text-left transition-all hover:border-slate-600/50
              hover:bg-slate-800/60
            "
          >
            <div className="flex items-start gap-3">
              {/* Coach icon */}
              <div className="flex-shrink-0 text-lg">
                {getCoachEmoji(delegation.coach)}
              </div>

              {/* Content */}
              <div className="flex-1 space-y-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-slate-200">
                    {getCoachDisplayName(delegation.coach)}
                  </span>
                  {getStatusIcon(delegation.status)}
                </div>

                {delegation.traits_collected.length > 0 && (
                  <p className="text-xs text-slate-400">
                    {delegation.traits_collected.length} trait
                    {delegation.traits_collected.length !== 1 ? "s" : ""}{" "}
                    collected
                  </p>
                )}

                {delegation.curiosity_satisfied > 0 && (
                  <div className="flex items-center gap-2">
                    <div className="h-1 flex-1 overflow-hidden rounded-full bg-slate-700">
                      <div
                        className="h-full bg-gradient-to-r from-green-600 to-green-400"
                        style={{
                          width: `${delegation.curiosity_satisfied * 100}%`,
                        }}
                      />
                    </div>
                    <span className="text-xs text-green-400">
                      {Math.round(delegation.curiosity_satisfied * 100)}%
                    </span>
                  </div>
                )}

                <p className="text-xs text-slate-500">
                  {formatTimestamp(delegation.timestamp)}
                </p>
              </div>

              {/* Arrow */}
              <ArrowRight className="h-4 w-4 flex-shrink-0 text-slate-500" />
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}
