/**
 * TypeScript type definitions for Coach Delegation System
 *
 * These types provide type safety for all delegation-related
 * API requests, responses, and component props.
 */

// ============================================================
// Core Types
// ============================================================

export type CoachMode = "head_coach" | "photo" | "relationship"

export type DelegationStatus = "pending" | "active" | "completed" | "failed"

export interface CoachInfo {
  id: CoachMode
  display_name: string
  emoji: string
  description: string
  tagline: string
  namespaces: string[]
}

// ============================================================
// API Request Types
// ============================================================

export interface AnalyzeCuriosityRequest {
  user_id: string
  curiosity_data: Record<string, number>
  tolerance: number
}

export interface CreateDelegationRequest {
  user_id: string
  coach_id: string
  curiosity_targets: string[]
  context?: {
    delegation_reason?: string
    priority?: number
    [key: string]: any
  }
}

export interface SwitchCoachModeRequest {
  target_mode: CoachMode
  delegation_id?: string
  context?: Record<string, any>
}

export interface CompleteDelegationRequest {
  traits_collected: string[]
  curiosity_before: Record<string, number>
  curiosity_after: Record<string, number>
  notes: string
  auto_return?: boolean
}

// ============================================================
// API Response Types
// ============================================================

export interface AnalyzeCuriosityResponse {
  ok: boolean
  should_delegate: boolean
  recommended_coach?: string
  priority_items: CuriosityItem[]
  message: string
}

export interface CuriosityItem {
  path: string
  curiosity: number
  namespace: string
}

export interface CreateDelegationResponse {
  ok: boolean
  delegation: {
    delegation_id: string
    coach: string
    status: DelegationStatus
    curiosity_targets: string[]
    created_at: string
  }
  message: string
}

export interface SwitchCoachModeResponse {
  ok: boolean
  success: boolean
  previous_mode: CoachMode
  new_mode: CoachMode
  mode_info: CoachInfo
  message: string
  no_change?: boolean
}

export interface GetCoachModeResponse {
  ok: boolean
  active_mode: CoachMode
  mode_info: CoachInfo
}

export interface CompleteDelegationResponse {
  ok: boolean
  message: string
  delegation_summary: {
    traits_collected_count: number
    curiosity_satisfied: number
    notes: string
  }
  mode_switch: {
    success: boolean
    previous_mode: CoachMode
    new_mode: CoachMode
    message: string
  } | null
}

export interface DelegationStatusResponse {
  ok: boolean
  status: {
    delegation_id: string
    coach: string
    status: DelegationStatus
    traits_collected: string[]
    curiosity_satisfied: number
    timestamp: string
    notes: string
  }
}

export interface ActiveDelegationsResponse {
  ok: boolean
  count: number
  delegations: Array<{
    delegation_id: string
    coach: string
    status: DelegationStatus
    traits_collected: string[]
    curiosity_satisfied: number
    timestamp: string
  }>
}

export interface ModeHistoryResponse {
  ok: boolean
  history: ModeTransition[]
}

export interface ModeTransition {
  from_mode: CoachMode
  to_mode: CoachMode
  timestamp: string
  context?: {
    delegation_id?: string
    reason?: "delegation" | "delegation_complete" | "manual_switch"
    curiosity_satisfied?: number
    traits_collected?: string[]
    [key: string]: any
  }
}

export interface ModeStatsResponse {
  ok: boolean
  stats: {
    total_transitions: number
    mode_counts: Record<CoachMode, number>
    current_mode: CoachMode
    most_used_mode: CoachMode
  }
}

// ============================================================
// Component Prop Types
// ============================================================

export interface DelegationRecommendation {
  coach: string
  coachName: string
  coachEmoji: string
  itemCount: number
  priorityScore: number
  curiosityTargets: string[]
}

export interface DelegationBannerProps {
  recommendation: DelegationRecommendation
  onAccept: () => void
  onDismiss: () => void
}

export interface CoachSwitcherProps {
  userId: string
  currentCoach: CoachMode
  targetCoach: CoachMode
  curiosityTargets: string[]
  onSwitchComplete: (delegationId: string) => void
  onCancel: () => void
}

export interface ActiveDelegationsWidgetProps {
  userId: string
  onDelegationClick?: (delegationId: string) => void
}

export interface DelegationCompleteButtonProps {
  userId: string
  delegationId: string
  traitsCollected: string[]
  curiosityBefore: Record<string, number>
  curiosityAfter: Record<string, number>
  notes?: string
  onComplete?: (summary: DelegationSummary) => void
  variant?: "default" | "success" | "celebration"
}

export interface DelegationSummary {
  traitsCollectedCount: number
  curiositySatisfied: number
  notes: string
  modeSwitch: {
    previousMode: CoachMode
    newMode: CoachMode
    message: string
  }
}

export interface DelegationReturnAcknowledgmentProps {
  delegationId: string
  coachMode: string
  traitsCollected: string[]
  curiositySatisfied: number
  notes: string
  timestamp?: string
  onDismiss?: () => void
}

export interface DelegationHistoryPanelProps {
  userId: string
  onClose: () => void
}

// ============================================================
// Utility Types
// ============================================================

/**
 * API error response structure
 */
export interface APIError {
  ok: false
  error: string
  message: string
}

/**
 * Generic API response wrapper
 */
export type APIResponse<T> = T | APIError

/**
 * Type guard to check if response is an error
 */
export function isAPIError(response: any): response is APIError {
  return response.ok === false && "error" in response
}

/**
 * Coach mode display information
 */
export const COACH_INFO: Record<CoachMode, CoachInfo> = {
  head_coach: {
    id: "head_coach",
    display_name: "Head Coach",
    emoji: "🧠",
    description: "Your strategic guide for holistic health insights",
    tagline: "Your strategic guide",
    namespaces: ["CogDNA", "GenDNA"],
  },
  photo: {
    id: "photo",
    display_name: "Photo Coach",
    emoji: "📸",
    description: "Visual trait specialist for physical appearance analysis",
    tagline: "Visual trait specialist",
    namespaces: ["PaDNA"],
  },
  relationship: {
    id: "relationship",
    display_name: "Relationship Coach",
    emoji: "💝",
    description: "Relationship and emotional intelligence expert",
    tagline: "Relationship expert",
    namespaces: ["ReDNA", "PsyDNA", "EmDNA"],
  },
}

/**
 * Get coach info by mode
 */
export function getCoachInfo(mode: CoachMode): CoachInfo {
  return COACH_INFO[mode]
}

/**
 * Check if a string is a valid coach mode
 */
export function isValidCoachMode(mode: string): mode is CoachMode {
  return mode === "head_coach" || mode === "photo" || mode === "relationship"
}

// ============================================================
// Delegation State Management
// ============================================================

/**
 * Local state for tracking active delegation
 */
export interface DelegationState {
  delegationId: string | null
  coachMode: CoachMode
  curiosityTargets: string[]
  traitsCollected: string[]
  curiosityBefore: Record<string, number>
  curiosityAfter: Record<string, number>
  isActive: boolean
}

/**
 * Initial delegation state
 */
export const INITIAL_DELEGATION_STATE: DelegationState = {
  delegationId: null,
  coachMode: "head_coach",
  curiosityTargets: [],
  traitsCollected: [],
  curiosityBefore: {},
  curiosityAfter: {},
  isActive: false,
}

// ============================================================
// Curiosity Calculation Utilities
// ============================================================

/**
 * Calculate curiosity satisfaction percentage
 *
 * @param before - Curiosity scores before delegation
 * @param after - Curiosity scores after delegation
 * @param traits - Traits that were collected
 * @returns Satisfaction as a decimal (0.0 - 1.0)
 */
export function calculateCuriositySatisfaction(
  before: Record<string, number>,
  after: Record<string, number>,
  traits: string[]
): number {
  let totalReduction = 0
  let totalBefore = 0

  for (const trait of traits) {
    const beforeValue = before[trait] || 0
    const afterValue = after[trait] || 0
    totalBefore += beforeValue
    totalReduction += Math.max(0, beforeValue - afterValue)
  }

  return totalBefore > 0 ? totalReduction / totalBefore : 0
}

/**
 * Get satisfaction level description
 *
 * @param satisfaction - Satisfaction as decimal (0.0 - 1.0)
 * @returns Human-readable satisfaction level
 */
export function getSatisfactionLevel(satisfaction: number): string {
  const percent = satisfaction * 100

  if (percent >= 80) return "Excellent"
  if (percent >= 60) return "Good"
  if (percent >= 40) return "Moderate"
  return "Low"
}

/**
 * Get satisfaction color class
 *
 * @param satisfaction - Satisfaction as decimal (0.0 - 1.0)
 * @returns Tailwind color class
 */
export function getSatisfactionColorClass(satisfaction: number): string {
  const percent = satisfaction * 100

  if (percent >= 80) return "text-green-600"
  if (percent >= 60) return "text-blue-600"
  if (percent >= 40) return "text-yellow-600"
  return "text-gray-600"
}

// ============================================================
// Namespace Utilities
// ============================================================

/**
 * Group traits by namespace
 *
 * @param traits - Array of trait paths (e.g., "PaDNA.HairDNA.Color")
 * @returns Record of namespace to trait paths
 */
export function groupTraitsByNamespace(
  traits: string[]
): Record<string, string[]> {
  return traits.reduce((acc, path) => {
    const namespace = path.split(".")[0]
    if (!acc[namespace]) acc[namespace] = []
    acc[namespace].push(path)
    return acc
  }, {} as Record<string, string[]>)
}

/**
 * Get trait display name
 *
 * @param traitPath - Full trait path (e.g., "PaDNA.HairDNA.Color")
 * @returns Display name (e.g., "Hair Color")
 */
export function getTraitDisplayName(traitPath: string): string {
  const parts = traitPath.split(".")
  if (parts.length < 2) return traitPath

  // Remove "DNA" suffix from parts
  const cleanParts = parts.slice(1).map((part) => part.replace(/DNA$/, ""))

  return cleanParts.join(" ")
}

// ============================================================
// API Client Helper
// ============================================================

/**
 * Base API URL
 */
export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000"

/**
 * Generic API fetch wrapper with type safety
 */
export async function fetchAPI<T>(
  endpoint: string,
  options?: RequestInit
): Promise<APIResponse<T>> {
  try {
    const response = await fetch(`${API_BASE}${endpoint}`, {
      headers: {
        "Content-Type": "application/json",
        ...options?.headers,
      },
      ...options,
    })

    if (!response.ok) {
      const error = await response.json()
      return {
        ok: false,
        error: error.error || "request_failed",
        message: error.message || `HTTP ${response.status}`,
      }
    }

    return await response.json()
  } catch (error) {
    return {
      ok: false,
      error: "network_error",
      message: error instanceof Error ? error.message : "Unknown error",
    }
  }
}

// ============================================================
// Delegation API Client
// ============================================================

export const DelegationAPI = {
  /**
   * Analyze curiosity data for delegation recommendation
   */
  async analyzeCuriosity(
    request: AnalyzeCuriosityRequest
  ): Promise<APIResponse<AnalyzeCuriosityResponse>> {
    return fetchAPI<AnalyzeCuriosityResponse>("/delegation/analyze", {
      method: "POST",
      body: JSON.stringify(request),
    })
  },

  /**
   * Create a new delegation
   */
  async createDelegation(
    request: CreateDelegationRequest
  ): Promise<APIResponse<CreateDelegationResponse>> {
    return fetchAPI<CreateDelegationResponse>("/delegation/create", {
      method: "POST",
      body: JSON.stringify(request),
    })
  },

  /**
   * Complete a delegation
   */
  async completeDelegation(
    userId: string,
    delegationId: string,
    request: CompleteDelegationRequest
  ): Promise<APIResponse<CompleteDelegationResponse>> {
    return fetchAPI<CompleteDelegationResponse>(
      `/delegation/${userId}/complete/${delegationId}`,
      {
        method: "POST",
        body: JSON.stringify(request),
      }
    )
  },

  /**
   * Get delegation status
   */
  async getDelegationStatus(
    userId: string,
    delegationId: string
  ): Promise<APIResponse<DelegationStatusResponse>> {
    return fetchAPI<DelegationStatusResponse>(
      `/delegation/${userId}/status/${delegationId}`
    )
  },

  /**
   * Get active delegations
   */
  async getActiveDelegations(
    userId: string
  ): Promise<APIResponse<ActiveDelegationsResponse>> {
    return fetchAPI<ActiveDelegationsResponse>(
      `/delegation/${userId}/active`
    )
  },
}

// ============================================================
// Coach Mode API Client
// ============================================================

export const CoachModeAPI = {
  /**
   * Get user's active coach mode
   */
  async getActiveMode(
    userId: string
  ): Promise<APIResponse<GetCoachModeResponse>> {
    return fetchAPI<GetCoachModeResponse>(`/users/${userId}/coach-mode`)
  },

  /**
   * Switch coach mode
   */
  async switchMode(
    userId: string,
    request: SwitchCoachModeRequest
  ): Promise<APIResponse<SwitchCoachModeResponse>> {
    return fetchAPI<SwitchCoachModeResponse>(`/users/${userId}/coach-mode`, {
      method: "POST",
      body: JSON.stringify(request),
    })
  },

  /**
   * Get mode switching history
   */
  async getModeHistory(
    userId: string,
    limit = 10
  ): Promise<APIResponse<ModeHistoryResponse>> {
    return fetchAPI<ModeHistoryResponse>(
      `/users/${userId}/coach-mode/history?limit=${limit}`
    )
  },

  /**
   * Get mode usage statistics
   */
  async getModeStats(
    userId: string
  ): Promise<APIResponse<ModeStatsResponse>> {
    return fetchAPI<ModeStatsResponse>(`/users/${userId}/coach-mode/stats`)
  },
}
