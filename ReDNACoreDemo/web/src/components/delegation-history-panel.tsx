"use client"

import { useState } from "react"
import { CheckCircle2, Clock, AlertCircle, TrendingUp, ChevronDown, ChevronUp } from "lucide-react"

interface DelegationHistoryItem {
  delegation_id: string
  coach: string
  status: "pending" | "active" | "completed" | "failed"
  traits_collected: string[]
  curiosity_satisfied: number
  timestamp: string
  completed_at?: string
  notes: string
}

interface DelegationHistoryPanelProps {
  userId: string
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000"

export function DelegationHistoryPanel({ userId }: DelegationHistoryPanelProps) {
  const [history, setHistory] = useState<DelegationHistoryItem[]>([])
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  // Mock data for now - would be replaced with actual API call
  // TODO: Add endpoint GET /delegation/{user_id}/history
  const mockHistory: DelegationHistoryItem[] = [
    {
      delegation_id: "del_1",
      coach: "photo_coach",
      status: "completed",
      traits_collected: ["PaDNA.HairDNA.Color", "PaDNA.EyeDNA.Color"],
      curiosity_satisfied: 0.87,
      timestamp: new Date(Date.now() - 3600000).toISOString(),
      completed_at: new Date(Date.now() - 1800000).toISOString(),
      notes: "Successfully analyzed photo and extracted hair and eye traits"
    },
    {
      delegation_id: "del_2",
      coach: "relationship_coach",
      status: "completed",
      traits_collected: ["ReDNA.AttachmentStyleDNA"],
      curiosity_satisfied: 0.65,
      timestamp: new Date(Date.now() - 86400000).toISOString(),
      completed_at: new Date(Date.now() - 82800000).toISOString(),
      notes: "Explored attachment patterns through conversation"
    },
  ]

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

  const getStatusBadge = (status: string) => {
    if (status === "completed") {
      return (
        <div className="flex items-center gap-1 rounded-full bg-green-950/50 px-2 py-1 text-xs font-medium text-green-400">
          <CheckCircle2 className="h-3 w-3" />
          Completed
        </div>
      )
    }
    if (status === "active") {
      return (
        <div className="flex items-center gap-1 rounded-full bg-orange-950/50 px-2 py-1 text-xs font-medium text-orange-400">
          <Clock className="h-3 w-3" />
          Active
        </div>
      )
    }
    if (status === "failed") {
      return (
        <div className="flex items-center gap-1 rounded-full bg-red-950/50 px-2 py-1 text-xs font-medium text-red-400">
          <AlertCircle className="h-3 w-3" />
          Failed
        </div>
      )
    }
    return (
      <div className="flex items-center gap-1 rounded-full bg-slate-800 px-2 py-1 text-xs font-medium text-slate-400">
        <Clock className="h-3 w-3" />
        Pending
      </div>
    )
  }

  const formatDate = (timestamp: string) => {
    const date = new Date(timestamp)
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    })
  }

  const getCuriositySatisfactionColor = (satisfaction: number) => {
    if (satisfaction >= 0.8) return "from-green-600 to-green-400"
    if (satisfaction >= 0.5) return "from-yellow-600 to-yellow-400"
    return "from-orange-600 to-orange-400"
  }

  const toggleExpanded = (delegationId: string) => {
    setExpandedId(expandedId === delegationId ? null : delegationId)
  }

  return (
    <div className="rounded-lg border border-slate-700/50 bg-slate-900/30 p-6">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-200">
          Delegation History
        </h2>
        <span className="rounded-full bg-slate-800 px-3 py-1 text-sm font-medium text-slate-400">
          {mockHistory.length} total
        </span>
      </div>

      {/* Stats summary */}
      <div className="mb-6 grid grid-cols-3 gap-4 rounded-lg border border-slate-700/30 bg-slate-800/40 p-4">
        <div className="text-center">
          <div className="text-2xl font-bold text-green-400">
            {mockHistory.filter((d) => d.status === "completed").length}
          </div>
          <div className="text-xs text-slate-400">Completed</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-orange-400">
            {Math.round(
              mockHistory.reduce((sum, d) => sum + d.curiosity_satisfied, 0) /
                mockHistory.length *
                100
            )}%
          </div>
          <div className="text-xs text-slate-400">Avg Satisfaction</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-blue-400">
            {mockHistory.reduce((sum, d) => sum + d.traits_collected.length, 0)}
          </div>
          <div className="text-xs text-slate-400">Traits Collected</div>
        </div>
      </div>

      {/* History list */}
      <div className="space-y-3">
        {mockHistory.length === 0 ? (
          <div className="rounded-lg border border-slate-700/30 bg-slate-800/20 p-8 text-center">
            <p className="text-sm text-slate-400">No delegation history yet</p>
          </div>
        ) : (
          mockHistory.map((item) => {
            const isExpanded = expandedId === item.delegation_id

            return (
              <div
                key={item.delegation_id}
                className="overflow-hidden rounded-lg border border-slate-700/30 bg-slate-800/40 transition-all"
              >
                {/* Header */}
                <button
                  onClick={() => toggleExpanded(item.delegation_id)}
                  className="w-full p-4 text-left transition-colors hover:bg-slate-800/60"
                >
                  <div className="flex items-start gap-4">
                    {/* Coach icon */}
                    <div className="flex-shrink-0 text-2xl">
                      {getCoachEmoji(item.coach)}
                    </div>

                    {/* Content */}
                    <div className="flex-1 space-y-2">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-slate-200">
                          {getCoachDisplayName(item.coach)}
                        </span>
                        {getStatusBadge(item.status)}
                      </div>

                      <div className="flex items-center gap-4 text-xs text-slate-400">
                        <span>{formatDate(item.timestamp)}</span>
                        <span>•</span>
                        <span>
                          {item.traits_collected.length} trait
                          {item.traits_collected.length !== 1 ? "s" : ""}
                        </span>
                      </div>

                      {/* Curiosity satisfaction bar */}
                      {item.curiosity_satisfied > 0 && (
                        <div className="flex items-center gap-2">
                          <TrendingUp className="h-3.5 w-3.5 text-green-400" />
                          <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-700">
                            <div
                              className={`h-full bg-gradient-to-r ${getCuriositySatisfactionColor(
                                item.curiosity_satisfied
                              )}`}
                              style={{
                                width: `${item.curiosity_satisfied * 100}%`,
                              }}
                            />
                          </div>
                          <span className="text-xs font-medium text-slate-300">
                            {Math.round(item.curiosity_satisfied * 100)}%
                          </span>
                        </div>
                      )}
                    </div>

                    {/* Expand icon */}
                    <div className="flex-shrink-0 text-slate-500">
                      {isExpanded ? (
                        <ChevronUp className="h-5 w-5" />
                      ) : (
                        <ChevronDown className="h-5 w-5" />
                      )}
                    </div>
                  </div>
                </button>

                {/* Expanded details */}
                {isExpanded && (
                  <div className="border-t border-slate-700/30 bg-slate-900/50 p-4">
                    <div className="space-y-3">
                      {/* Traits collected */}
                      <div>
                        <h4 className="mb-2 text-xs font-semibold uppercase text-slate-400">
                          Traits Collected
                        </h4>
                        <div className="flex flex-wrap gap-2">
                          {item.traits_collected.map((trait) => (
                            <span
                              key={trait}
                              className="rounded-md border border-slate-700/50 bg-slate-800/50 px-2 py-1 text-xs text-slate-300"
                            >
                              {trait.split(".").pop()}
                            </span>
                          ))}
                        </div>
                      </div>

                      {/* Notes */}
                      {item.notes && (
                        <div>
                          <h4 className="mb-2 text-xs font-semibold uppercase text-slate-400">
                            Notes
                          </h4>
                          <p className="text-sm text-slate-300">{item.notes}</p>
                        </div>
                      )}

                      {/* Timestamps */}
                      <div className="grid grid-cols-2 gap-4 text-xs">
                        <div>
                          <span className="text-slate-500">Started:</span>{" "}
                          <span className="text-slate-300">
                            {formatDate(item.timestamp)}
                          </span>
                        </div>
                        {item.completed_at && (
                          <div>
                            <span className="text-slate-500">Completed:</span>{" "}
                            <span className="text-slate-300">
                              {formatDate(item.completed_at)}
                            </span>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
