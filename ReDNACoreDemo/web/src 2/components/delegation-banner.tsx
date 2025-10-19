"use client"

import { useState } from "react"
import { X, ArrowRight, Sparkles } from "lucide-react"

interface DelegationRecommendation {
  coach: string
  coach_display_name: string
  items: Array<{
    path: string
    curiosity: number
    rr: number
  }>
  priority: number
}

interface DelegationBannerProps {
  recommendation: DelegationRecommendation
  onAccept: () => void
  onDismiss: () => void
}

export function DelegationBanner({
  recommendation,
  onAccept,
  onDismiss,
}: DelegationBannerProps) {
  const [isAnimating, setIsAnimating] = useState(false)

  const handleAccept = () => {
    setIsAnimating(true)
    setTimeout(() => {
      onAccept()
    }, 300)
  }

  const itemCount = recommendation.items.length
  const sampleItems = recommendation.items.slice(0, 2)
  const itemNames = sampleItems.map((item) =>
    item.path.split(".").pop()
  )

  const getCoachEmoji = (coach: string) => {
    if (coach === "photo_coach") return "📸"
    if (coach === "relationship_coach") return "💝"
    return "🤖"
  }

  return (
    <div
      className={`
        relative overflow-hidden rounded-lg border border-orange-800/30
        bg-gradient-to-r from-orange-950/40 via-orange-900/20 to-orange-950/40
        p-4 shadow-lg backdrop-blur-sm transition-all duration-300
        ${isAnimating ? "scale-95 opacity-0" : "scale-100 opacity-100"}
      `}
    >
      {/* Sparkle accent */}
      <div className="absolute right-4 top-4 text-orange-400/20">
        <Sparkles className="h-8 w-8" />
      </div>

      {/* Content */}
      <div className="relative flex items-start gap-4">
        {/* Coach icon */}
        <div className="flex-shrink-0">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-orange-900/50 text-2xl ring-2 ring-orange-700/50">
            {getCoachEmoji(recommendation.coach)}
          </div>
        </div>

        {/* Message */}
        <div className="flex-1 space-y-2">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-orange-100">
              {recommendation.coach_display_name} can help
            </h3>
            <span className="rounded-full bg-orange-800/50 px-2 py-0.5 text-xs font-medium text-orange-200">
              {itemCount} area{itemCount !== 1 ? "s" : ""}
            </span>
          </div>

          <p className="text-sm text-slate-300">
            I noticed you have high curiosity about{" "}
            <span className="font-medium text-orange-200">
              {itemNames.join(", ")}
            </span>
            {itemCount > 2 && ` and ${itemCount - 2} more`}.{" "}
            {recommendation.coach_display_name} specializes in this area and can
            help explore these traits more effectively.
          </p>

          {/* Priority indicator */}
          <div className="flex items-center gap-2">
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-800">
              <div
                className="h-full bg-gradient-to-r from-orange-600 to-orange-400 transition-all duration-500"
                style={{ width: `${Math.min(recommendation.priority, 100)}%` }}
              />
            </div>
            <span className="text-xs text-slate-400">
              Priority: {Math.round(recommendation.priority)}
            </span>
          </div>
        </div>

        {/* Actions */}
        <div className="flex flex-shrink-0 items-center gap-2">
          <button
            onClick={handleAccept}
            className="
              group flex items-center gap-1.5 rounded-lg bg-orange-600
              px-4 py-2 text-sm font-medium text-white shadow-sm
              transition-all hover:bg-orange-500 hover:shadow-md
            "
          >
            Switch
            <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
          </button>

          <button
            onClick={onDismiss}
            className="
              rounded-lg p-2 text-slate-400 transition-colors
              hover:bg-slate-800/50 hover:text-slate-200
            "
            aria-label="Dismiss"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  )
}
