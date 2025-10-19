/**
 * DevX Feature Flags
 *
 * Enable/disable features in the DevX UI for gradual rollout or testing.
 */

export const FEATURE_FLAGS = {
  /**
   * Mount Life OS in User Ops → Head Coach tab
   * Displays the full Life OS panel with goals, todos, projects, and inspiration
   */
  LIFE_OS_IN_USER_OPS: true,
} as const

export type FeatureFlag = keyof typeof FEATURE_FLAGS
