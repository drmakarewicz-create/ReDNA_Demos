# Right Pane Architecture Proposal
**ReDNA Chat UI — Persona-Specific Panel System**

## Executive Summary

This proposal outlines a clean, scalable architecture for managing persona-specific content in the right pane (CoachToolsPane) of the ReDNA chat UI. The solution introduces a **persona configuration system** that declaratively defines what panels appear for each coach, eliminating conditional chaos and enabling easy extensibility.

---

## Current State Analysis

### What Works
✅ **Modular rendering function** (`renderPersonaTools()`) already exists at [page-client.tsx:2930-3002](web/src/app/page-client.tsx#L2930-L3002)
✅ **Panel boundary system** provides error isolation and clean resets
✅ **Existing components** are ready: `PhotoPanel`, `PortraitRenderCard`, `LifeOSChatPanel`, etc.
✅ **Backend APIs** exist for most features (Life OS, Photo import, PaDNA rendering)

### Current Problems
❌ **Life OS shows everywhere** — It's rendered unconditionally in the sidebar (line 2282-2286), not gated by persona
❌ **Photo Coach features disappeared** — `PhotoPanel` exists but isn't rendered anywhere
❌ **PaDNA Coach UI missing** — `PortraitRenderCard` only renders for `rendering` persona, not `padna`
❌ **Hard-coded switch statements** — Adding a new coach panel requires editing multiple files
❌ **No centralized persona config** — Panel logic is scattered across the codebase

---

## Proposed Architecture

### 1. Persona Panel Configuration System

**Create a declarative config file** that maps each persona to its right-pane panels.

#### File: `web/src/lib/persona-panels-config.ts`

```typescript
import type { ReactNode } from 'react';
import { LifeOSChatPanel } from '@/components/life-os-chat-panel';
import { PhotoPanel } from '@/components/photo/photo-panel';
import { PortraitRenderCard } from '@/components/padna/portrait-render-card';
import { AvatarRenderPanel } from '@/components/rendering/avatar-render-panel';
import { CareerSnapshotCard } from '@/components/career/career-snapshot-card';
import { SkillCuriosityMap } from '@/components/career/skill-curiosity-map';
import { PersonalitySnapshotCard } from '@/components/personality/personality-snapshot-card';
import { PersonalityMapVisualization } from '@/components/personality/personality-map-visualization';
import { ChatDNASnapshotCard } from '@/components/chatdna-snapshot-card';
import { LanguageStylePanel } from '@/components/language-style-panel';
import { BeliefDNACoachPanel } from '@/app/page-client'; // or extract to own file

export interface PanelConfig {
  component: React.ComponentType<any>;
  props?: Record<string, any>;
  order: number;
  section: 'top' | 'middle' | 'bottom';
  requiresUser?: boolean;
  requiresFlag?: string; // For feature flags
}

export interface PersonaPanelConfig {
  panels: PanelConfig[];
  showLifeOS?: boolean;
  lifeOSVariant?: 'full' | 'relationship' | 'career'; // For filtered views
}

/**
 * Persona Panel Configuration
 * Defines which panels appear in the right pane for each coach
 */
export const PERSONA_PANEL_CONFIG: Record<string, PersonaPanelConfig> = {
  head_coach: {
    showLifeOS: true,
    lifeOSVariant: 'full',
    panels: [
      // Head Coach: Life OS + shared support panels only
    ],
  },

  relationship_coach: {
    showLifeOS: true,
    lifeOSVariant: 'relationship', // Filtered to relationship goals/todos
    panels: [
      // Relationship Coach: Life OS (filtered) + support panels
    ],
  },

  photo: {
    showLifeOS: false,
    panels: [
      {
        component: PhotoPanel,
        order: 1,
        section: 'top',
        requiresUser: true,
      },
    ],
  },

  padna: {
    showLifeOS: false,
    panels: [
      {
        component: PortraitRenderCard,
        order: 1,
        section: 'top',
        requiresUser: true,
      },
    ],
  },

  rendering: {
    showLifeOS: false,
    panels: [
      {
        component: AvatarRenderPanel,
        order: 1,
        section: 'top',
        requiresUser: true,
      },
      {
        component: PortraitRenderCard,
        order: 2,
        section: 'top',
        requiresUser: true,
      },
    ],
  },

  career_coach: {
    showLifeOS: false,
    panels: [
      {
        component: CareerSnapshotCard,
        order: 1,
        section: 'top',
        requiresUser: true,
      },
      {
        component: SkillCuriosityMap,
        order: 2,
        section: 'middle',
        requiresUser: true,
        props: { minCuriosity: 50 },
      },
    ],
  },

  personality_test_coach: {
    showLifeOS: false,
    panels: [
      {
        component: PersonalitySnapshotCard,
        order: 1,
        section: 'top',
        requiresUser: true,
      },
      {
        component: PersonalityMapVisualization,
        order: 2,
        section: 'middle',
        requiresUser: true,
      },
    ],
  },

  chatdna_coach: {
    showLifeOS: false,
    panels: [
      {
        component: ChatDNASnapshotCard,
        order: 1,
        section: 'top',
        requiresUser: true,
      },
      {
        component: LanguageStylePanel,
        order: 2,
        section: 'middle',
        requiresUser: true,
        props: { minCuriosity: 50 },
      },
    ],
  },

  beliefdna_coach: {
    showLifeOS: false,
    panels: [
      {
        component: BeliefDNACoachPanel,
        order: 1,
        section: 'top',
        requiresUser: true,
      },
    ],
  },

  permission_coach: {
    showLifeOS: false,
    panels: [
      // Permission Coach: TBD - governance/audit panels will go here
    ],
  },
};

/**
 * Get panel configuration for a persona
 */
export function getPersonaPanelConfig(personaKey: string): PersonaPanelConfig {
  const normalized = personaKey.toLowerCase().trim();
  return PERSONA_PANEL_CONFIG[normalized] ?? PERSONA_PANEL_CONFIG.head_coach;
}
```

---

### 2. Refactored Right Pane Rendering

**Update the sidebar section** to use the config system.

#### Changes to `web/src/app/page-client.tsx`

```typescript
// Import the config
import { getPersonaPanelConfig, type PersonaPanelConfig } from '../lib/persona-panels-config';

// In the sidebarSection (around line 2279):
const sidebarSection = flags.focusedChatLayout ? (
  <CoachToolsPane title="Coach Tools">
    {/* 1) Coach Catalog FIRST - Always at top */}
    <button
      onClick={() => setCatalogOpen(true)}
      className="w-full mb-3 rounded-xl border border-cyan-500/30 bg-gradient-to-r from-cyan-950/30 to-slate-950/40 p-3 text-left transition hover:border-cyan-500/50 hover:bg-cyan-950/40"
    >
      <div className="flex items-center gap-2">
        <span className="text-xl">📚</span>
        <div className="flex-1">
          <div className="text-sm font-semibold text-cyan-200">Coach Catalog</div>
          <div className="text-xs text-slate-400">Browse all {personas.length + 2} coaches</div>
        </div>
        <svg className="w-4 h-4 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
      </div>
    </button>

    {/* 2) Persona-specific panels (Life OS, Coach tools, etc.) */}
    {renderPersonaPanels(activePersona, personaContext, flags)}

    {/* 3) Coach Recommendation banner */}
    {delegationRecommendation && (
      <DelegationRecommendationBanner
        recommendation={delegationRecommendation}
        onAccept={() => setShowCoachSwitcher(true)}
        onDismiss={() => setDelegationRecommendation(null)}
      />
    )}

    {/* 4) Shared support panels (Dev tools, etc.) */}
    <DevOnly>
      <PersonaRail
        id="tour-persona-rail"
        personas={personas}
        activePersona={activePersona}
        onPersonaChange={setActivePersona}
      />
    </DevOnly>
    <DevOnly>
      <PanelBoundary resetKeys={[activeUser]} onRetry={retryUnabridged}>
        <RRDnaPanel
          snapshot={unabridged}
          loading={unabridgedLoading}
          error={unabridgedError}
          onRetry={retryUnabridged}
        />
      </PanelBoundary>
    </DevOnly>

    {/* Unabridged panel (shown for select coaches) */}
    {shouldShowUnabridgedPanel(activePersona) && (
      <PanelBoundary resetKeys={[activeUser]} onRetry={retryUnabridged}>
        <UnabridgedPanel
          snapshot={unabridged}
          loading={unabridgedLoading}
          error={unabridgedError}
          onRetry={retryUnabridged}
          id="unabridged"
          onRefresh={refreshAllPanels}
        />
      </PanelBoundary>
    )}

    {/* Coach-specific feature panes from features JSON */}
    {coachFeatures && coachFeatures.showInUI && coachFeatures.panes.length > 0 && coachFeatureState && (
      <DynamicCoachPanes
        coachId={coachFeatures.coach_id}
        panes={coachFeatures.panes}
        featureState={coachFeatureState.values}
        onChange={handleFeatureStateChange}
        onWarning={handleFeatureWarning}
      />
    )}

    {/* Support panels (shared across all coaches) */}
    {renderSharedSupportPanels(personaContext)}
  </CoachToolsPane>
) : (
  // ... existing non-focused layout
);
```

**New rendering function:**

```typescript
/**
 * Render persona-specific panels based on configuration
 */
function renderPersonaPanels(
  personaKey: string,
  context: PersonaCenterContext,
  flags: any
): ReactNode {
  const config = getPersonaPanelConfig(personaKey);

  return (
    <>
      {/* Life OS (if enabled for this persona) */}
      {config.showLifeOS && flags.lifeOsInChat && context.activeUser && (
        <div className="mb-4">
          <LifeOSChatPanel
            userId={context.activeUser}
            variant={config.lifeOSVariant}
          />
        </div>
      )}

      {/* Persona-specific panels */}
      {config.panels
        .sort((a, b) => a.order - b.order)
        .map((panelConfig, index) => {
          const Component = panelConfig.component;
          const props = {
            userId: context.activeUser,
            ...(panelConfig.props || {}),
          };

          // Skip if requires user and no user is active
          if (panelConfig.requiresUser && !context.activeUser) {
            return null;
          }

          // Skip if requires flag and flag is not enabled
          if (panelConfig.requiresFlag && !flags[panelConfig.requiresFlag]) {
            return null;
          }

          return (
            <PanelBoundary
              key={`${personaKey}-panel-${index}`}
              resetKeys={[personaKey, context.activeUser]}
            >
              <Component {...props} />
            </PanelBoundary>
          );
        })}
    </>
  );
}
```

---

### 3. Life OS Variants (Optional Enhancement)

**Support filtered Life OS views** for different coaches.

#### Changes to `LifeOSChatPanel.tsx`

```typescript
interface LifeOSChatPanelProps {
  userId: string;
  variant?: 'full' | 'relationship' | 'career';
}

export function LifeOSChatPanel({ userId, variant = 'full' }: LifeOSChatPanelProps) {
  // Fetch Life OS data
  const { data, loading, error } = useLifeOSData(userId);

  // Filter based on variant
  const filteredData = useMemo(() => {
    if (!data || variant === 'full') return data;

    if (variant === 'relationship') {
      return {
        ...data,
        goals: data.goals.filter(g => g.tags?.includes('relationship')),
        today_three: data.today_three.filter(t => t.tags?.includes('relationship')),
        // ... filter other sections
      };
    }

    if (variant === 'career') {
      return {
        ...data,
        goals: data.goals.filter(g => g.tags?.includes('career')),
        // ... filter other sections
      };
    }

    return data;
  }, [data, variant]);

  // ... render with filteredData
}
```

---

### 4. Backend API Alignment

#### Existing Endpoints (Already Working)
✅ **Life OS**: `/users/{user_id}/life-os/summary` (implemented in `hc_life.py`)
✅ **Photo Upload**: `/users/{user_id}/media/upload` (photo ingestion)
✅ **PaDNA Portrait**: `/api/padna/portrait` (ComfyUI integration)
✅ **Career Stats**: Inferred from unabridged snapshot
✅ **Personality**: Inferred from unabridged snapshot

#### Recommended New Endpoints
1. **Photo Import List**: `GET /users/{user_id}/photo-imports/recent`
   - Returns list of recently imported photos with metadata
   - Backend: Add to `ReDNACoreDemo/core/api.py`

2. **PaDNA Summary**: `GET /users/{user_id}/padna/summary`
   - Returns condensed PaDNA trait summary for right pane
   - Backend: Extract from existing unabridged data

3. **Life OS Filtered**: `GET /users/{user_id}/life-os/summary?filter=relationship`
   - Returns filtered Life OS data (relationship, career, etc.)
   - Backend: Add filter parameter to `hc_life.py:build_life_summary()`

---

### 5. Component Directory Structure

```
web/src/
├── lib/
│   ├── persona-panels-config.ts       ← NEW: Central config
│   └── api.ts
├── components/
│   ├── life-os-chat-panel.tsx         ← UPDATE: Add variant support
│   ├── photo/
│   │   ├── photo-panel.tsx            ← EXISTS: Photo upload + recent imports
│   │   └── photo-import-panel.tsx     ← EXISTS: Import UI
│   ├── padna/
│   │   └── portrait-render-card.tsx   ← EXISTS: PaDNA renderer
│   ├── career/
│   │   ├── career-snapshot-card.tsx   ← EXISTS
│   │   └── skill-curiosity-map.tsx    ← EXISTS
│   ├── personality/
│   │   ├── personality-snapshot-card.tsx  ← EXISTS
│   │   └── personality-map-visualization.tsx ← EXISTS
│   ├── chatdna-snapshot-card.tsx      ← EXISTS
│   ├── language-style-panel.tsx       ← EXISTS
│   ├── belief-console.tsx             ← EXISTS (for BeliefDNA)
│   └── coach-tools-pane.tsx           ← Container component
└── app/
    └── page-client.tsx                ← UPDATE: Use config system
```

---

## Implementation Plan

### Phase 1: Foundation (Low Risk, High Value)
**Time: 2-3 hours**

1. ✅ Create `persona-panels-config.ts` with all persona definitions
2. ✅ Extract `renderPersonaPanels()` helper function
3. ✅ Update `sidebarSection` to use config system
4. ✅ Gate Life OS rendering with `config.showLifeOS`
5. ✅ Test with Head Coach (should look identical)

### Phase 2: Restore Missing Panels (Quick Wins)
**Time: 1-2 hours**

1. ✅ Add `PhotoPanel` to photo persona config
2. ✅ Add `PortraitRenderCard` to padna persona config
3. ✅ Verify Photo Coach shows upload UI and recent imports
4. ✅ Verify PaDNA Coach shows portrait renderer

### Phase 3: Life OS Variants (Optional Polish)
**Time: 2-3 hours**

1. ⚠️ Add `variant` prop to `LifeOSChatPanel`
2. ⚠️ Implement filtering logic for relationship/career views
3. ⚠️ Update backend to support `?filter=` parameter (optional)
4. ⚠️ Test Relationship Coach with filtered Life OS

### Phase 4: Backend Enhancements (As Needed)
**Time: 1-2 hours**

1. ⚠️ Add `GET /users/{user_id}/photo-imports/recent` endpoint
2. ⚠️ Add `GET /users/{user_id}/padna/summary` endpoint
3. ⚠️ Update Photo panel to fetch recent imports

---

## Benefits

### ✅ Immediate Wins
- **Life OS only shows where relevant** (Head Coach, Relationship Coach)
- **Photo Coach regains photo upload/import UI**
- **PaDNA Coach regains portrait renderer**
- **Career/Personality/ChatDNA/Belief coaches stay focused** on their domain

### ✅ Long-Term Scalability
- **Add new coaches in 5 lines** (just add config entry)
- **No more switch statement sprawl**
- **Easy to A/B test panel layouts** (just swap config)
- **Panel order and visibility centralized**
- **Feature flags integrate cleanly**

### ✅ Developer Experience
- **One file to rule them all** (`persona-panels-config.ts`)
- **Type-safe panel definitions**
- **Clear separation of concerns** (config vs rendering)
- **Easy to document** what each coach shows

---

## Migration Strategy

### Option A: Big Bang (Recommended)
1. Create config file
2. Refactor `sidebarSection` in one PR
3. Test all personas
4. Ship

**Pros**: Clean, atomic change. Easy to review.
**Cons**: Larger PR, more testing needed.

### Option B: Incremental
1. Create config file (no functional changes)
2. Migrate Head Coach to use config
3. Migrate other coaches one by one
4. Remove old `renderPersonaTools()` switch

**Pros**: Lower risk per PR.
**Cons**: Temporary duplication, more PRs.

---

## Risk Mitigation

### Potential Issues
1. **Breaking existing layouts**: Test all personas before merge
2. **Performance regression**: Config lookup is O(1), no perf impact
3. **Feature flag conflicts**: Config supports `requiresFlag` field
4. **Missing components**: All components already exist, just need wiring

### Rollback Plan
- Keep old `renderPersonaTools()` function for 1 release
- Add feature flag `usePersonaPanelConfig` (default true)
- If issues arise, flip flag to false

---

## Open Questions

1. **Should Life OS be a tab in the chat for some coaches?**
   - Current: Always right pane
   - Alternative: Tab in left pane for Head Coach, hidden for others

2. **Should we unify `renderPersonaTools()` and `renderPersonaPanels()`?**
   - Current: Separate functions
   - Proposed: Replace `renderPersonaTools()` with config system

3. **Should panel configs live in JSON files for easier editing?**
   - Current proposal: TypeScript file
   - Alternative: `persona-panels.config.json` + validation

4. **Should we add panel analytics?**
   - Track which panels users interact with per coach
   - Could inform future panel prioritization

---

## Conclusion

This architecture provides a **clean, declarative, and scalable** solution for managing persona-specific right pane content. It:

- ✅ Solves the immediate problem (Life OS showing everywhere)
- ✅ Restores missing features (Photo upload, PaDNA renderer)
- ✅ Sets up the system for future growth
- ✅ Maintains performance and clarity
- ✅ Requires minimal backend changes

**Recommendation**: Proceed with **Phase 1 + Phase 2** (foundation + restore panels) as a single PR. This delivers maximum value with minimal risk.

---

## Next Steps

1. **Review this proposal** with team
2. **Confirm approach** (Big Bang vs Incremental)
3. **Create implementation tickets**
4. **Begin Phase 1** (config system + Life OS gating)
5. **Ship and iterate**

---

**Document Version**: 1.0
**Author**: Claude (ReDNA Architecture Agent)
**Date**: 2025-10-11
**Status**: Proposed — Awaiting Review
