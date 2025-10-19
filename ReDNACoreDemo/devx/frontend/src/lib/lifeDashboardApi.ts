/**
 * Life OS Dashboard API Client
 * Phase 4: Multi-user aggregates for DevX dashboard
 */

import { getApiBase } from './env'

const API_BASE = `${getApiBase()}/ui/hc/life`

// ============================================================================
// Types
// ============================================================================

export interface UserKPIs {
  todays_three_success_rate: number
  current_streak: number
  todos_completed: number
  top_tag: string | null
  goals_at_risk: number
}

export interface TrendPoint {
  week_label: string
  todos_completed: number
  completion_rate: number
}

export interface QuadrantShare {
  IU?: number  // Important & Urgent
  IN?: number  // Important & Not Urgent
  NU?: number  // Not Important & Urgent
  NN?: number  // Not Important & Not Urgent
}

export interface UserAggregate {
  user_id: string
  kpis: UserKPIs
  trends: TrendPoint[]
  quadrant_share: QuadrantShare
  tags_top: [string, number][]
}

export interface AggregateResponse {
  aggregates: UserAggregate[]
  duration_ms: number
  total_users: number
}

// ============================================================================
// API Client
// ============================================================================

class LifeDashboardClient {
  /**
   * Fetch multi-user aggregates for dashboard.
   *
   * @param days Time window (default 14)
   * @returns Array of user aggregates
   */
  async getAggregates(days: number = 14): Promise<UserAggregate[]> {
    const url = `${API_BASE}/aggregate?days=${days}`
    const response = await fetch(url)

    if (!response.ok) {
      throw new Error(`Failed to fetch aggregates: ${response.statusText}`)
    }

    const data = await response.json()
    return data as UserAggregate[]
  }

  /**
   * Fetch insights for a specific user (reuse existing endpoint).
   *
   * @param userId User ID
   * @param days Time window (default 7)
   */
  async getUserInsights(userId: string, days: number = 7) {
    const url = `${API_BASE}/${encodeURIComponent(userId)}/insights?days=${days}`
    const response = await fetch(url)

    if (!response.ok) {
      throw new Error(`Failed to fetch insights for ${userId}: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Fetch trends for a specific user (reuse existing endpoint).
   *
   * @param userId User ID
   * @param weeks Number of weeks (default 8)
   */
  async getUserTrends(userId: string, weeks: number = 8) {
    const url = `${API_BASE}/${encodeURIComponent(userId)}/trends?weeks=${weeks}`
    const response = await fetch(url)

    if (!response.ok) {
      throw new Error(`Failed to fetch trends for ${userId}: ${response.statusText}`)
    }

    return response.json()
  }
}

// ============================================================================
// Singleton Export
// ============================================================================

export const lifeDashboardApi = new LifeDashboardClient()
