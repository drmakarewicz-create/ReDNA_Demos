/**
 * DevX route helpers
 *
 * Centralized route construction to prevent typos and ensure consistency.
 */

/**
 * User Ops routes
 */
export function userOpsHome(): string {
  return '/user-ops'
}

export function userOpsDetail(userId: string): string {
  return `/user-ops/${userId}`
}

export function userOpsHC(userId: string): string {
  return `/user-ops/${userId}/hc`
}

export function userOpsProfile(userId: string): string {
  return `/user-ops/${userId}/profile`
}

export function userOpsTriggers(userId: string): string {
  return `/user-ops/${userId}/triggers`
}

export function userOpsHolistic(userId: string): string {
  return `/user-ops/${userId}/holistic`
}

export function userOpsPermissions(userId: string): string {
  return `/user-ops/${userId}/permissions`
}

export function userOpsManage(userId: string): string {
  return `/user-ops/${userId}/manage`
}

/**
 * Insights routes
 */
export function coachBrain(): string {
  return '/coach-brain'
}

export function narratorTimeline(): string {
  return '/narrator-timeline'
}

/**
 * Agent routes
 */
export function agentControl(): string {
  return '/agent-control'
}
