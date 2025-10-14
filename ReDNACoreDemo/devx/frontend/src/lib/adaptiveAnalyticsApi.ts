/**
 * Adaptive Analytics API client (Phase 10).
 */

import { getApiBase } from './env'

const API_BASE = `${getApiBase()}/adaptive-analytics`

export interface LearningVelocityPoint {
  date: string
  value: number
}

export interface PredictionSourceWeights {
  ontology: number
  correlation: number
  life_os: number
}

export interface PredictionItem {
  target: string
  persona: string
  score: number
  sources: PredictionSourceWeights
}

export interface ConfidenceSummary {
  value: number
  sources: Partial<PredictionSourceWeights>
}

export interface UserAnalyticsPayload {
  user_id: string
  generated_at: string
  refresh_epoch: string | null
  learning_velocity: {
    daily: LearningVelocityPoint[]
    rolling_avg_7d: number
    goal_confidence_avg: number
    goals_total: number
  }
  predictions: PredictionItem[]
  confidence: ConfidenceSummary
  latency_ms: number
}

export interface OverviewItem {
  user_id: string
  rolling_avg_7d: number
  top_focus: PredictionItem[]
  confidence: number
}

export interface OverviewResponse {
  generated_at: string | null
  users: OverviewItem[]
}

class AdaptiveAnalyticsClient {
  async getOverview(): Promise<OverviewResponse> {
    const response = await fetch(`${API_BASE}/overview`)
    if (!response.ok) {
      throw new Error(`Failed to fetch adaptive analytics overview: ${response.statusText}`)
    }
    return response.json()
  }

  async getUserView(userId: string): Promise<UserAnalyticsPayload> {
    const response = await fetch(`${API_BASE}/user/${encodeURIComponent(userId)}`)
    if (!response.ok) {
      throw new Error(`Failed to fetch adaptive analytics view for ${userId}: ${response.statusText}`)
    }
    return response.json()
  }
}

export const adaptiveAnalyticsApi = new AdaptiveAnalyticsClient()
