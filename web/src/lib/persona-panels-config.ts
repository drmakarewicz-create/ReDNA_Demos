/**
 * Persona Panel Configuration System
 *
 * ⚠️ PRODUCTION BASELINE - DO NOT REMOVE OR REPLACE
 * Full documentation: /COACH_FEATURES_BASELINE.md
 * Quick reference: /web/src/lib/PERSONA_PANELS_README.md
 *
 * This module defines which panels appear in the right pane (CoachToolsPane)
 * for each persona/coach in the ReDNA system.
 *
 * This is the ESTABLISHED ARCHITECTURE for coach-specific UI features.
 * Do not replace this declarative system with hardcoded switch statements.
 *
 * @module persona-panels-config
 */

import type { ComponentType } from "react";
import { lazy } from "react";

/**
 * Life OS display variants
 * - full: Show complete Life OS (all goals, todos, projects)
 * - relationship: Show filtered Life OS (relationship-specific items only)
 * - hidden: Don't show Life OS at all
 */
export type LifeOSVariant = "full" | "relationship" | "hidden";

/**
 * Configuration for a single panel in the right pane
 */
export interface PersonaPanelItem {
  /** Unique identifier for this panel (e.g., "photo", "padna") */
  id: string;

  /** React component to render */
  component: ComponentType<any>;

  /** Sort order (lower numbers appear higher in the pane) */
  order: number;

  /** Additional props to pass to the component */
  props?: Record<string, any>;

  /** Optional feature flag gate - panel only shows if flag is true */
  featureFlag?: string;
}

/**
 * Complete configuration for a persona's right pane
 */
export interface PersonaPanelConfig {
  /** Life OS display mode for this persona */
  lifeOS: LifeOSVariant;

  /** Persona-specific panels to display */
  panels: PersonaPanelItem[];
}

/**
 * User-specific override for a persona's panel configuration
 */
export interface PersonaPanelOverride {
  /** Override panel order (array of panel IDs) */
  order?: string[];

  /** Override panel visibility (panel ID -> visible boolean) */
  visible?: Record<string, boolean>;

  /** Override Life OS visibility */
  lifeOS?: LifeOSVariant;
}

/**
 * User layout override schema
 */
export interface UserRightPaneLayout {
  /** Schema version for migrations */
  version: number;

  /** Global card order for right pane sections */
  cards?: string[];

  /** Per-persona overrides */
  overrides?: Record<string, PersonaPanelOverride>;
}

// Lazy-loaded components to avoid bloating initial bundle
const PhotoPanel = lazy(() => import("../components/photo/photo-panel").then(m => ({ default: m.PhotoPanel })));
const PortraitRenderCard = lazy(() => import("../components/padna/portrait-render-card").then(m => ({ default: m.PortraitRenderCard })));
const AvatarRenderPanel = lazy(() => import("../components/rendering/avatar-render-panel").then(m => ({ default: m.AvatarRenderPanel })));
const CareerSnapshotCard = lazy(() => import("../components/career/career-snapshot-card").then(m => ({ default: m.CareerSnapshotCard })));
const SkillCuriosityMap = lazy(() => import("../components/career/skill-curiosity-map").then(m => ({ default: m.SkillCuriosityMap })));
const PersonalitySnapshotCard = lazy(() => import("../components/personality/personality-snapshot-card").then(m => ({ default: m.PersonalitySnapshotCard })));
const PersonalityMapVisualization = lazy(() => import("../components/personality/personality-map-visualization").then(m => ({ default: m.PersonalityMapVisualization })));
const ChatDNASnapshotCard = lazy(() => import("../components/chatdna-snapshot-card").then(m => ({ default: m.ChatDNASnapshotCard })));
const LanguageStylePanel = lazy(() => import("../components/language-style-panel").then(m => ({ default: m.LanguageStylePanel })));

/**
 * Master configuration mapping persona keys to their panel configs
 *
 * The "*" key provides default configuration for personas not explicitly listed.
 */
export const PERSONA_PANEL_CONFIG: Record<string, PersonaPanelConfig> = {
  /**
   * Head Coach (Orchestrator)
   * Shows full Life OS with all goals, todos, and projects
   */
  head_coach: {
    lifeOS: "full",
    panels: [],
  },

  /**
   * Relationship Coach
   * Shows filtered Life OS focused on relationship goals and todos
   */
  relationship_coach: {
    lifeOS: "relationship",
    panels: [],
  },

  /**
   * Photo Coach
   * Handles photo uploads and trait extraction from images
   */
  photo_coach: {
    lifeOS: "hidden",
    panels: [
      {
        id: "photo",
        component: PhotoPanel,
        order: 10,
      },
    ],
  },

  /**
   * Photo Coach (alternate key without _coach suffix)
   */
  photo: {
    lifeOS: "hidden",
    panels: [
      {
        id: "photo",
        component: PhotoPanel,
        order: 10,
      },
    ],
  },

  /**
   * PaDNA Coach (Portrait/Avatar DNA)
   * Shows portrait renderer for generating photorealistic images from traits
   */
  padna_coach: {
    lifeOS: "hidden",
    panels: [
      {
        id: "padna",
        component: PortraitRenderCard,
        order: 10,
      },
    ],
  },

  /**
   * PaDNA Coach (alternate key without _coach suffix)
   */
  padna: {
    lifeOS: "hidden",
    panels: [
      {
        id: "padna",
        component: PortraitRenderCard,
        order: 10,
      },
    ],
  },

  /**
   * Rendering Coach (Avatar + Portrait generation)
   * Shows both avatar and portrait rendering tools
   */
  rendering: {
    lifeOS: "hidden",
    panels: [
      {
        id: "avatar",
        component: AvatarRenderPanel,
        order: 10,
      },
      {
        id: "portrait",
        component: PortraitRenderCard,
        order: 20,
      },
    ],
  },

  /**
   * Career Coach
   * Shows career snapshot and skill curiosity map
   */
  career_coach: {
    lifeOS: "hidden",
    panels: [
      {
        id: "career_snapshot",
        component: CareerSnapshotCard,
        order: 10,
      },
      {
        id: "skill_map",
        component: SkillCuriosityMap,
        order: 20,
        props: { minCuriosity: 50 },
      },
    ],
  },

  /**
   * Personality Test Coach
   * Shows personality snapshot and map visualization
   */
  personality_test_coach: {
    lifeOS: "hidden",
    panels: [
      {
        id: "personality_snapshot",
        component: PersonalitySnapshotCard,
        order: 10,
      },
      {
        id: "personality_map",
        component: PersonalityMapVisualization,
        order: 20,
      },
    ],
  },

  /**
   * ChatDNA Coach (Communication style)
   * Shows chat style snapshot and language patterns
   */
  chatdna_coach: {
    lifeOS: "hidden",
    panels: [
      {
        id: "chatdna_snapshot",
        component: ChatDNASnapshotCard,
        order: 10,
      },
      {
        id: "language_style",
        component: LanguageStylePanel,
        order: 20,
        props: { minCuriosity: 50 },
      },
    ],
  },

  /**
   * BeliefDNA Coach (Philosophy & Values)
   * Note: BeliefDNA panels are rendered inline in page-client.tsx
   * via BeliefDNACoachPanel component - not included here to avoid circular imports
   */
  beliefdna_coach: {
    lifeOS: "hidden",
    panels: [
      // BeliefDNA panels rendered separately in renderPersonaTools()
    ],
  },

  /**
   * Permission Coach (Consent & Privacy)
   * Governance panels are rendered via DynamicCoachPanes system
   */
  permission_coach: {
    lifeOS: "hidden",
    panels: [
      // Permission panels rendered via DynamicCoachPanes
    ],
  },

  /**
   * Default fallback for unrecognized personas
   * Hides Life OS and shows no specialized panels
   */
  "*": {
    lifeOS: "hidden",
    panels: [],
  },
};

/**
 * Apply user-specific overrides to a base panel configuration
 *
 * @param baseConfig - The base configuration from PERSONA_PANEL_CONFIG
 * @param override - User-specific override settings
 * @returns Merged configuration with overrides applied
 */
function applyLayoutOverrides(
  baseConfig: PersonaPanelConfig,
  override: PersonaPanelOverride
): PersonaPanelConfig {
  let config = { ...baseConfig };

  // Override Life OS visibility
  if (override.lifeOS !== undefined) {
    config.lifeOS = override.lifeOS;
  }

  // Override panel visibility
  if (override.visible) {
    config.panels = config.panels.filter(panel => {
      const visible = override.visible?.[panel.id];
      // If not specified in override, keep original
      return visible !== false;
    });
  }

  // Override panel order
  if (override.order && override.order.length > 0) {
    const orderMap = new Map(override.order.map((id, index) => [id, index]));
    config.panels = [...config.panels].sort((a, b) => {
      const aOrder = orderMap.get(a.id) ?? 9999;
      const bOrder = orderMap.get(b.id) ?? 9999;
      return aOrder - bOrder;
    });
  }

  return config;
}

/**
 * Resolve panel configuration for a given persona key
 *
 * @param personaKey - The persona identifier (e.g., "head_coach", "photo", etc.)
 * @param userLayout - Optional user-specific layout overrides
 * @returns PersonaPanelConfig for the specified persona, with overrides applied
 *
 * @example
 * // Without overrides
 * const config = getPersonaPanelConfig("photo_coach");
 * // Returns: { lifeOS: "hidden", panels: [{ id: "photo", ... }] }
 *
 * @example
 * // With overrides
 * const config = getPersonaPanelConfig("photo_coach", {
 *   version: 2,
 *   overrides: {
 *     photo_coach: {
 *       visible: { photo: false },
 *       lifeOS: "full"
 *     }
 *   }
 * });
 * // Returns: { lifeOS: "full", panels: [] }
 */
export function getPersonaPanelConfig(
  personaKey: string,
  userLayout?: UserRightPaneLayout
): PersonaPanelConfig {
  const normalized = personaKey.toLowerCase().trim();

  // Look up persona in config, fall back to default
  const baseConfig = PERSONA_PANEL_CONFIG[normalized] ?? PERSONA_PANEL_CONFIG["*"];

  // Apply user layout overrides if provided
  if (userLayout?.overrides?.[normalized]) {
    return applyLayoutOverrides(baseConfig, userLayout.overrides[normalized]);
  }

  return baseConfig;
}

/**
 * Check if Life OS should be visible for a given persona
 *
 * @param personaKey - The persona identifier
 * @param userLayout - Optional user-specific layout overrides
 * @returns true if Life OS should be shown, false otherwise
 */
export function shouldShowLifeOS(
  personaKey: string,
  userLayout?: UserRightPaneLayout
): boolean {
  const config = getPersonaPanelConfig(personaKey, userLayout);
  return config.lifeOS !== "hidden";
}

/**
 * Get the Life OS variant for a given persona
 *
 * @param personaKey - The persona identifier
 * @param userLayout - Optional user-specific layout overrides
 * @returns The Life OS variant (full, relationship, or hidden)
 */
export function getLifeOSVariant(
  personaKey: string,
  userLayout?: UserRightPaneLayout
): LifeOSVariant {
  const config = getPersonaPanelConfig(personaKey, userLayout);
  return config.lifeOS;
}

/**
 * Get sorted panels for a given persona
 * Panels are sorted by ascending order value (lower numbers appear higher)
 * User overrides can change panel order and visibility
 *
 * @param personaKey - The persona identifier
 * @param activeFlags - Optional object containing active feature flags
 * @param userLayout - Optional user-specific layout overrides
 * @returns Array of PersonaPanelItem sorted by order
 */
export function getPersonaPanels(
  personaKey: string,
  activeFlags?: Record<string, boolean>,
  userLayout?: UserRightPaneLayout
): PersonaPanelItem[] {
  const config = getPersonaPanelConfig(personaKey, userLayout);

  let panels = config.panels;

  // Filter by feature flags if provided
  if (activeFlags) {
    panels = panels.filter(panel => {
      if (!panel.featureFlag) return true;
      return activeFlags[panel.featureFlag] === true;
    });
  }

  // Already sorted by user overrides if applied, otherwise sort by order
  if (!userLayout?.overrides?.[personaKey.toLowerCase().trim()]?.order) {
    panels = [...panels].sort((a, b) => a.order - b.order);
  }

  return panels;
}
