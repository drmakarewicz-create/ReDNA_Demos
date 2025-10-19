"use client"

import { useState } from "react"
import { Check, Loader2, Sparkles, TrendingDown } from "lucide-react"

interface DelegationCompleteButtonProps {
  userId: string
  delegationId: string
  traitsCollected: string[]
  curiosityBefore: Record<string, number>
  curiosityAfter: Record<string, number>
  notes?: string
  onComplete?: (summary: DelegationSummary) => void
  variant?: "default" | "success" | "celebration"
}

interface DelegationSummary {
  traitsCollectedCount: number
  curiositySatisfied: number
  notes: string
  modeSwitch: {
    previousMode: string
    newMode: string
    message: string
  }
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000"

export function DelegationCompleteButton({
  userId,
  delegationId,
  traitsCollected,
  curiosityBefore,
  curiosityAfter,
  notes = "",
  onComplete,
  variant = "default",
}: DelegationCompleteButtonProps) {
  const [completing, setCompleting] = useState(false)
  const [completed, setCompleted] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [summary, setSummary] = useState<DelegationSummary | null>(null)

  const handleComplete = async () => {
    setCompleting(true)
    setError(null)

    try {
      const response = await fetch(
        `${API_BASE}/delegation/${userId}/complete/${delegationId}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            traits_collected: traitsCollected,
            curiosity_before: curiosityBefore,
            curiosity_after: curiosityAfter,
            notes: notes,
            auto_return: true,
          }),
        }
      )

      if (!response.ok) {
        throw new Error("Failed to complete delegation")
      }

      const data = await response.json()

      if (!data.ok) {
        throw new Error(data.message || "Completion failed")
      }

      const delegationSummary: DelegationSummary = {
        traitsCollectedCount: data.delegation_summary.traits_collected_count,
        curiositySatisfied: data.delegation_summary.curiosity_satisfied,
        notes: data.delegation_summary.notes,
        modeSwitch: data.mode_switch,
      }

      setSummary(delegationSummary)
      setCompleted(true)

      // Call onComplete callback after a brief celebration delay
      if (onComplete) {
        setTimeout(() => {
          onComplete(delegationSummary)
        }, 2000)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error")
      setCompleting(false)
    }
  }

  // Calculate curiosity reduction for display
  const calculateReduction = () => {
    let totalReduction = 0
    let totalBefore = 0

    for (const path of traitsCollected) {
      const before = curiosityBefore[path] || 0
      const after = curiosityAfter[path] || 0
      totalBefore += before
      totalReduction += Math.max(0, before - after)
    }

    return totalBefore > 0 ? (totalReduction / totalBefore) * 100 : 0
  }

  const reductionPercent = calculateReduction()
  const isHighSatisfaction = reductionPercent >= 70

  if (completed && summary) {
    return (
      <div className="flex flex-col items-center gap-3 p-6 rounded-lg bg-gradient-to-br from-green-50 to-emerald-50 border-2 border-green-200">
        <div className="flex items-center gap-2 text-green-700">
          <div className="relative">
            <Check className="h-8 w-8" />
            {isHighSatisfaction && (
              <Sparkles className="h-4 w-4 absolute -top-1 -right-1 text-yellow-500 animate-pulse" />
            )}
          </div>
          <span className="font-semibold text-lg">Delegation Complete!</span>
        </div>

        <div className="text-center text-sm text-gray-700">
          <p>
            Collected <strong>{summary.traitsCollectedCount}</strong> traits
          </p>
          <p className="flex items-center justify-center gap-1 mt-1">
            <TrendingDown className="h-4 w-4 text-green-600" />
            <span className="font-medium text-green-700">
              {Math.round(summary.curiositySatisfied * 100)}% curiosity satisfied
            </span>
          </p>
        </div>

        {isHighSatisfaction && (
          <div className="text-xs text-green-600 font-medium animate-pulse">
            🎉 Outstanding exploration!
          </div>
        )}

        <div className="text-xs text-gray-600 mt-2">
          Returning to {summary.modeSwitch.newMode.replace("_", " ")}...
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <button
        onClick={handleComplete}
        disabled={completing || traitsCollected.length === 0}
        className={`
          px-6 py-3 rounded-lg font-medium transition-all
          flex items-center justify-center gap-2
          ${
            variant === "celebration"
              ? "bg-gradient-to-r from-purple-500 to-pink-500 text-white hover:from-purple-600 hover:to-pink-600"
              : variant === "success"
              ? "bg-gradient-to-r from-green-500 to-emerald-500 text-white hover:from-green-600 hover:to-emerald-600"
              : "bg-gradient-to-r from-blue-500 to-indigo-500 text-white hover:from-blue-600 hover:to-indigo-600"
          }
          disabled:opacity-50 disabled:cursor-not-allowed
          shadow-md hover:shadow-lg
        `}
      >
        {completing ? (
          <>
            <Loader2 className="h-5 w-5 animate-spin" />
            <span>Completing...</span>
          </>
        ) : (
          <>
            <Check className="h-5 w-5" />
            <span>Mark Complete & Return to Head Coach</span>
          </>
        )}
      </button>

      {/* Preview stats before completion */}
      {!completing && traitsCollected.length > 0 && (
        <div className="text-sm text-gray-600 px-2">
          <div className="flex justify-between">
            <span>Traits collected:</span>
            <strong>{traitsCollected.length}</strong>
          </div>
          <div className="flex justify-between mt-1">
            <span>Estimated satisfaction:</span>
            <strong className="text-green-600">~{Math.round(reductionPercent)}%</strong>
          </div>
        </div>
      )}

      {error && (
        <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded p-2">
          {error}
        </div>
      )}

      {traitsCollected.length === 0 && (
        <div className="text-xs text-gray-500 text-center">
          No traits collected yet. Continue the conversation to collect data.
        </div>
      )}
    </div>
  )
}
