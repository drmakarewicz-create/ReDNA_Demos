"use client"

import { Check, TrendingDown, Sparkles, Award } from "lucide-react"

interface DelegationReturnAcknowledgmentProps {
  delegationId: string
  coachMode: string
  traitsCollected: string[]
  curiositySatisfied: number
  notes: string
  timestamp?: string
  onDismiss?: () => void
}

export function DelegationReturnAcknowledgment({
  delegationId,
  coachMode,
  traitsCollected,
  curiositySatisfied,
  notes,
  timestamp,
  onDismiss,
}: DelegationReturnAcknowledgmentProps) {
  const getCoachInfo = (mode: string) => {
    const coaches: Record<string, { name: string; emoji: string }> = {
      photo_coach: { name: "Photo Coach", emoji: "📸" },
      relationship_coach: { name: "Relationship Coach", emoji: "💝" },
      head_coach: { name: "Head Coach", emoji: "🧠" },
    }
    return coaches[mode] || { name: mode, emoji: "🤖" }
  }

  const coachInfo = getCoachInfo(coachMode)
  const satisfactionPercent = Math.round(curiositySatisfied * 100)
  const isExcellent = satisfactionPercent >= 80
  const isGood = satisfactionPercent >= 60
  const isModerate = satisfactionPercent >= 40

  const getBorderColor = () => {
    if (isExcellent) return "border-green-300"
    if (isGood) return "border-blue-300"
    if (isModerate) return "border-yellow-300"
    return "border-gray-300"
  }

  const getBackgroundGradient = () => {
    if (isExcellent) return "from-green-50 via-emerald-50 to-teal-50"
    if (isGood) return "from-blue-50 via-indigo-50 to-purple-50"
    if (isModerate) return "from-yellow-50 via-amber-50 to-orange-50"
    return "from-gray-50 via-slate-50 to-zinc-50"
  }

  const getAcknowledgmentMessage = () => {
    if (isExcellent) {
      return "Fantastic work! Your curiosity exploration was highly productive."
    }
    if (isGood) {
      return "Great progress! We gathered valuable insights together."
    }
    if (isModerate) {
      return "Good session! We made solid progress on your curiosity."
    }
    return "Welcome back! We collected some useful information."
  }

  // Group traits by namespace for display
  const groupedTraits = traitsCollected.reduce((acc, path) => {
    const namespace = path.split(".")[0]
    if (!acc[namespace]) acc[namespace] = []
    acc[namespace].push(path)
    return acc
  }, {} as Record<string, string[]>)

  return (
    <div
      className={`
        relative overflow-hidden
        p-5 rounded-xl border-2 ${getBorderColor()}
        bg-gradient-to-br ${getBackgroundGradient()}
        shadow-lg
        animate-slideIn
      `}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="text-3xl">{coachInfo.emoji}</div>
          <div>
            <div className="font-semibold text-gray-900 flex items-center gap-2">
              <span>Delegation Complete</span>
              {isExcellent && (
                <Award className="h-5 w-5 text-yellow-500 animate-pulse" />
              )}
            </div>
            <div className="text-sm text-gray-600">
              {coachInfo.name} • Just now
            </div>
          </div>
        </div>

        {onDismiss && (
          <button
            onClick={onDismiss}
            className="text-gray-400 hover:text-gray-600 transition-colors"
            aria-label="Dismiss"
          >
            ×
          </button>
        )}
      </div>

      {/* Acknowledgment message */}
      <div className="mb-4 p-3 bg-white/60 rounded-lg border border-white/80">
        <p className="text-sm text-gray-800 font-medium">
          {getAcknowledgmentMessage()}
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        {/* Traits Collected */}
        <div className="bg-white/70 rounded-lg p-3 border border-white/90">
          <div className="flex items-center gap-2 mb-1">
            <Check className="h-4 w-4 text-green-600" />
            <span className="text-xs font-medium text-gray-600">
              Traits Collected
            </span>
          </div>
          <div className="text-2xl font-bold text-gray-900">
            {traitsCollected.length}
          </div>
        </div>

        {/* Curiosity Satisfied */}
        <div className="bg-white/70 rounded-lg p-3 border border-white/90">
          <div className="flex items-center gap-2 mb-1">
            <TrendingDown className="h-4 w-4 text-blue-600" />
            <span className="text-xs font-medium text-gray-600">
              Curiosity Satisfied
            </span>
          </div>
          <div className="flex items-center gap-1">
            <span className="text-2xl font-bold text-gray-900">
              {satisfactionPercent}%
            </span>
            {isExcellent && (
              <Sparkles className="h-5 w-5 text-yellow-500 animate-pulse" />
            )}
          </div>
        </div>
      </div>

      {/* Trait Breakdown */}
      {Object.keys(groupedTraits).length > 0 && (
        <div className="mb-4">
          <div className="text-xs font-medium text-gray-600 mb-2">
            Explored Domains:
          </div>
          <div className="flex flex-wrap gap-2">
            {Object.entries(groupedTraits).map(([namespace, paths]) => (
              <div
                key={namespace}
                className="inline-flex items-center gap-1 px-3 py-1 bg-white/80 rounded-full border border-gray-200 text-xs"
              >
                <span className="font-semibold text-gray-700">{namespace}</span>
                <span className="text-gray-500">({paths.length})</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Notes */}
      {notes && (
        <div className="bg-white/60 rounded-lg p-3 border border-white/80">
          <div className="text-xs font-medium text-gray-600 mb-1">Notes:</div>
          <p className="text-sm text-gray-700 italic">&ldquo;{notes}&rdquo;</p>
        </div>
      )}

      {/* Celebration sparkles for excellent results */}
      {isExcellent && (
        <div className="absolute top-2 right-2 animate-pulse">
          <Sparkles className="h-6 w-6 text-yellow-400" />
        </div>
      )}
    </div>
  )
}
