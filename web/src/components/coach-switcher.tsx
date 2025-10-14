"use client"

import { useState, useRef, useEffect } from "react"
import { ArrowRight, Check, Loader2 } from "lucide-react"

interface CoachSwitcherProps {
  userId: string
  currentCoach: string
  targetCoach: string
  curiosityTargets: string[]
  onSwitchComplete: (delegationId: string, contextVersion: number, cancelToken: string) => void
  onCancel: () => void
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000"

// Debounce duration for rapid clicking protection (ms)
const SWITCH_DEBOUNCE_MS = 300

export function CoachSwitcher({
  userId,
  currentCoach,
  targetCoach,
  curiosityTargets,
  onSwitchComplete,
  onCancel,
}: CoachSwitcherProps) {
  const [switching, setSwitching] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [contextVersion, setContextVersion] = useState<number | null>(null)

  // Abort controller for canceling in-flight requests
  const abortControllerRef = useRef<AbortController | null>(null)

  // Debounce timer ref
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null)

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort()
      }
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current)
      }
    }
  }, [])

  const getCoachInfo = (coachId: string) => {
    const coaches: Record<
      string,
      { name: string; emoji: string; tagline: string }
    > = {
      head_coach: {
        name: "Head Coach",
        emoji: "🧠",
        tagline: "Your strategic guide",
      },
      photo_coach: {
        name: "Photo Coach",
        emoji: "📸",
        tagline: "Visual trait specialist",
      },
      relationship_coach: {
        name: "Relationship Coach",
        emoji: "💝",
        tagline: "Relationship expert",
      },
    }
    return (
      coaches[coachId] || { name: coachId, emoji: "🤖", tagline: "Specialist" }
    )
  }

  const currentInfo = getCoachInfo(currentCoach)
  const targetInfo = getCoachInfo(targetCoach)

  const handleSwitch = async () => {
    // Cancel any in-flight request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }

    // Create new abort controller
    const abortController = new AbortController()
    abortControllerRef.current = abortController

    setSwitching(true)
    setError(null)

    try {
      // Step 1: Create delegation
      const delegationResponse = await fetch(`${API_BASE}/delegation/create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: userId,
          coach_id: targetCoach,
          curiosity_targets: curiosityTargets,
          context: {
            delegation_reason: "user_accepted_recommendation",
            previous_coach: currentCoach,
            timestamp: new Date().toISOString(),
          },
        }),
        signal: abortController.signal,
      })

      if (!delegationResponse.ok) {
        throw new Error("Failed to create delegation")
      }

      const delegationData = await delegationResponse.json()

      if (!delegationData.ok) {
        throw new Error(delegationData.message || "Delegation failed")
      }

      const delegationId = delegationData.delegation.delegation_id

      // Step 2: Switch coach mode (atomic context build)
      const modeResponse = await fetch(`${API_BASE}/users/${userId}/coach-mode`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          target_mode: targetCoach,
          delegation_id: delegationId,
          context: {
            curiosity_targets: curiosityTargets,
          },
        }),
        signal: abortController.signal,
      })

      if (!modeResponse.ok) {
        throw new Error("Failed to switch coach mode")
      }

      const modeData = await modeResponse.json()

      if (!modeData.ok) {
        throw new Error(modeData.message || "Mode switch failed")
      }

      // Extract context version and cancel token
      const newContextVersion = modeData.context_version || 0
      const cancelToken = modeData.cancel_token || ""

      setContextVersion(newContextVersion)

      // Wait a moment for visual effect
      await new Promise((resolve) => setTimeout(resolve, 500))

      // Notify parent with new session data
      onSwitchComplete(delegationId, newContextVersion, cancelToken)
    } catch (err) {
      // Ignore abort errors (user canceled)
      if (err instanceof Error && err.name === "AbortError") {
        console.log("Switch canceled by user")
        return
      }

      console.error("Switch error:", err)
      setError(err instanceof Error ? err.message : "Failed to switch coaches")
      setSwitching(false)
    }
  }

  const handleSwitchDebounced = () => {
    // Clear existing debounce timer
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current)
    }

    // Set new debounce timer
    debounceTimerRef.current = setTimeout(() => {
      handleSwitch()
    }, SWITCH_DEBOUNCE_MS)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-2xl rounded-xl border border-slate-700 bg-slate-900 p-6 shadow-2xl">
        {/* Header */}
        <div className="mb-6 text-center">
          <h2 className="mb-2 text-2xl font-bold text-slate-100">
            Switch Coaches
          </h2>
          <p className="text-sm text-slate-400">
            Delegate {curiosityTargets.length} high-curiosity area
            {curiosityTargets.length !== 1 ? "s" : ""} to a specialist
          </p>
          {contextVersion !== null && (
            <p className="mt-1 text-xs text-slate-500">
              Context version: {contextVersion}
            </p>
          )}
        </div>

        {/* Coach transition visual */}
        <div className="mb-6 flex items-center justify-center gap-8">
          {/* Current coach */}
          <div className="text-center">
            <div className="mb-2 flex h-20 w-20 items-center justify-center rounded-full bg-slate-800 text-4xl shadow-lg">
              {currentInfo.emoji}
            </div>
            <p className="font-medium text-slate-300">{currentInfo.name}</p>
            <p className="text-xs text-slate-500">{currentInfo.tagline}</p>
          </div>

          {/* Arrow */}
          <div className="flex h-20 items-center">
            <ArrowRight
              className={`h-8 w-8 text-orange-400 transition-transform ${
                switching ? "animate-pulse" : ""
              }`}
            />
          </div>

          {/* Target coach */}
          <div className="text-center">
            <div
              className={`mb-2 flex h-20 w-20 items-center justify-center rounded-full text-4xl shadow-lg transition-all ${
                switching
                  ? "animate-pulse bg-orange-600 ring-4 ring-orange-400/50"
                  : "bg-orange-900/50 ring-2 ring-orange-700/50"
              }`}
            >
              {targetInfo.emoji}
            </div>
            <p className="font-medium text-slate-200">{targetInfo.name}</p>
            <p className="text-xs text-orange-400">{targetInfo.tagline}</p>
          </div>
        </div>

        {/* Curiosity targets */}
        <div className="mb-6 rounded-lg border border-slate-700/50 bg-slate-800/40 p-4">
          <h3 className="mb-3 text-sm font-semibold text-slate-300">
            Areas to Explore
          </h3>
          <div className="flex flex-wrap gap-2">
            {curiosityTargets.map((target) => {
              const traitName = target.split(".").pop() || target
              return (
                <div
                  key={target}
                  className="flex items-center gap-2 rounded-md border border-orange-800/30 bg-orange-950/20 px-3 py-1.5"
                >
                  <span className="text-sm text-slate-200">{traitName}</span>
                  {switching && (
                    <Loader2 className="h-3 w-3 animate-spin text-orange-400" />
                  )}
                </div>
              )
            })}
          </div>
        </div>

        {/* What happens next */}
        <div className="mb-6 rounded-lg bg-slate-800/40 p-4">
          <h3 className="mb-2 text-sm font-semibold text-slate-300">
            What happens next?
          </h3>
          <ul className="space-y-2 text-sm text-slate-400">
            <li className="flex items-start gap-2">
              <Check className="mt-0.5 h-4 w-4 flex-shrink-0 text-green-400" />
              <span>
                {targetInfo.name} will focus on these high-curiosity areas
              </span>
            </li>
            <li className="flex items-start gap-2">
              <Check className="mt-0.5 h-4 w-4 flex-shrink-0 text-green-400" />
              <span>
                Your conversation history will be shared for context
              </span>
            </li>
            <li className="flex items-start gap-2">
              <Check className="mt-0.5 h-4 w-4 flex-shrink-0 text-green-400" />
              <span>
                You can switch back to {currentInfo.name} anytime
              </span>
            </li>
          </ul>
        </div>

        {/* Error message */}
        {error && (
          <div className="mb-4 rounded-lg border border-red-800/50 bg-red-950/20 p-3">
            <p className="text-sm text-red-400">{error}</p>
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-3">
          <button
            onClick={onCancel}
            disabled={switching}
            className="
              flex-1 rounded-lg border border-slate-700 bg-slate-800
              px-4 py-3 font-medium text-slate-300 transition-colors
              hover:bg-slate-700 disabled:cursor-not-allowed
              disabled:opacity-50
            "
          >
            Cancel
          </button>
          <button
            onClick={handleSwitchDebounced}
            disabled={switching}
            className="
              flex flex-1 items-center justify-center gap-2 rounded-lg
              bg-orange-600 px-4 py-3 font-medium text-white shadow-lg
              transition-all hover:bg-orange-500 hover:shadow-xl
              disabled:cursor-not-allowed disabled:opacity-50
            "
          >
            {switching ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Switching...
              </>
            ) : (
              <>
                Switch to {targetInfo.name}
                <ArrowRight className="h-4 w-4" />
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
