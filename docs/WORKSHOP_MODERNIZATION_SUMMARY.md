# Coach Workshop Modernization - Implementation Summary

**Date:** October 7, 2025
**Status:** Design Complete - Ready for Implementation
**Approach:** Option 3 - Bridge now, unify later (per ChatGPT recommendation)

---

## Executive Summary

The Coach Workshop has been redesigned to support both **legacy persona-based coaches** (PaDNA, Photo, Relationship) and **new delegation-based coaches** (Career Coach, Personality Test Coach) through a unified manifest-driven framework called **RPUF (Right Pane Unified Framework)**.

### Key Decision

We are implementing a **bridge architecture** that:
- ✅ **Preserves legacy functionality** - Existing persona registry continues to work unchanged
- ✅ **Enables delegation coaches** - Career Coach and PTC now visible in Workshop
- ✅ **Uses production renderer** - RPUF ensures dev/prod parity
- ✅ **Allows incremental migration** - Legacy coaches can adopt manifests over time
- ✅ **No breaking changes** - Workshop simply adds a new "Delegation" tab

---

## Deliverables

### 1. Core Architecture & Specifications

| Document | Location | Purpose |
|----------|----------|---------|
| **RPUF Architecture** | [`docs/RPUF_ARCHITECTURE.md`](RPUF_ARCHITECTURE.md) | Complete RPUF design: manifest loading, widget registry, layout resolution, performance targets |
| **Workshop Integration Spec** | [`docs/WORKSHOP_INTEGRATION_SPEC.md`](WORKSHOP_INTEGRATION_SPEC.md) | Implementation details for Workshop bridge: source switcher, data binding modes, simulator |
| **Legacy Persona Migration** | [`docs/LEGACY_PERSONA_MIGRATION.md`](LEGACY_PERSONA_MIGRATION.md) | 3-phase migration path for PaDNA, Photo, and Relationship Coach |
| **Dev Explorer Guide Update** | [`docs/Dev_Explorer_Guide.md`](Dev_Explorer_Guide.md) | Updated Workshop section with delegation mode documentation |

### 2. Manifest Schema

**File:** [`ReDNACoreDemo/schemas/coach_ui_manifest.schema.json`](../ReDNACoreDemo/schemas/coach_ui_manifest.schema.json)

**Features:**
- JSON Schema Draft-07 validation
- Widget types: visualization, interactive, form, display, action, diagnostic
- Condition types: intent, rr_threshold, curiosity_threshold, data_available, feature_flag, user_pref
- Intent-specific layouts: priority_boost, hide, show, reorder
- AI suggestions integration with policy gates
- Performance targets: compose_target_ms, fcp_target_ms, max_api_calls
- Workshop fixtures support

### 3. Coach Manifests

#### Career Coach Manifest

**File:** [`ReDNACoreDemo/coaches/career_coach/coach_ui_manifest.yaml`](../ReDNACoreDemo/coaches/career_coach/coach_ui_manifest.yaml)

**Widgets (6 total):**
1. **Skill Curiosity Map** - Visual heatmap of skill gaps and high-curiosity areas
2. **Career Dashboard** - Professional satisfaction, skill distribution, career health
3. **Transition Planner** - AI-powered career change planning (with AI suggestions)
4. **Learning Path Generator** - Personalized skill development roadmap
5. **Work Style Analyzer** - Productivity patterns and work preferences
6. **Skill Gap Analyzer** - Critical skill gaps for career goals

**Intent Layouts:**
- `career_change` - Boosts Transition Planner, Skill Gap Analyzer
- `skill_development` - Boosts Learning Path Generator
- `current_role_growth` - Boosts Career Dashboard, Work Style Analyzer
- `career_planning` - Boosts Dashboard, Transition Planner

**Fixture:** [`career_change.json`](../ReDNACoreDemo/coaches/career_coach/workshop_fixtures/career_change.json) - Software engineer → Product manager transition scenario

#### Personality Test Coach Manifest

**File:** [`ReDNACoreDemo/coaches/personality_test_coach/coach_ui_manifest.yaml`](../ReDNACoreDemo/coaches/personality_test_coach/coach_ui_manifest.yaml)

**Widgets (6 total):**
1. **Personality Radar** - OCEAN (Big Five) trait visualization
2. **Adaptive Questionnaire** - Context-aware personality questions with branching logic
3. **Personality Map** - Interactive trait landscape with connections
4. **Motivational Drivers** - Intrinsic/extrinsic motivation analysis
5. **Personality Insights** - AI-generated analysis and recommendations
6. **Belief & Values Explorer** - Core beliefs and value hierarchies

**Intent Layouts:**
- `personality_exploration` - Shows radar, map, insights
- `assessment_mode` - Shows questionnaire, hides insights (focus)
- `self_reflection` - Shows insights, motivations, beliefs
- `motivation_analysis` - Shows motivational drivers

**Fixture:** [`assessment_mode.json`](../ReDNACoreDemo/coaches/personality_test_coach/workshop_fixtures/assessment_mode.json) - Partial OCEAN profile with 46% completion

---

## Architecture Overview

### Current (Legacy) Flow

```
Coach Workshop
  ↓
persona_registry.list_personas()
  ↓
ExplorerFinal/ui/personas/*.py
  ↓
Display: PaDNA, Photo, Relationship Coach
```

**Limitation:** Career Coach and PTC not visible (no persona files)

### New (Bridge) Flow

```
Coach Workshop
  ↓
[Source Switcher]
  ↓
┌──────────────────────┬───────────────────────┐
│ Personas (legacy)    │ Delegation (registry) │
│                      │                       │
│ persona_registry     │ coach_registry.yaml   │
│ ↓                    │ ↓                     │
│ PaDNA, Photo, RC     │ Career, PTC, ...      │
│ ↓                    │ ↓                     │
│ Legacy Renderer      │ RPUF Renderer         │
└──────────────────────┴───────────────────────┘
```

**Benefits:**
- ✅ All 5 coaches visible in Workshop
- ✅ No breaking changes (legacy tab unchanged)
- ✅ Dev/prod parity (same RPUF renderer)
- ✅ Incremental migration path

---

## RPUF (Right Pane Unified Framework)

### Core Components

1. **Manifest Loader** - Load/validate YAML manifests against schema
2. **Widget Registry** - Map component names to React components
3. **Layout Manager** - Sort, filter, apply conditions
4. **Condition Evaluator** - Evaluate intent, RR, curiosity, data availability conditions
5. **Data Binder** - Bind API/static/computed data sources
6. **Telemetry Collector** - Track performance metrics

### Data Flow

```typescript
// 1. Load manifest
const manifest = await loadManifest(coachId);

// 2. Validate
validateManifest(manifest, schema);

// 3. Resolve layout (intent + RR + user prefs)
const resolvedLayout = resolveLayout(manifest, {
  intent: 'career_change',
  rrData: { SkillDNA: 65.0, ProfDNA: 30.0 },
  userPrefs: { pinned: ['skill_curiosity_map'] }
});

// 4. Render widgets
return (
  <CoachToolsPane>
    {resolvedLayout.widgets.map(widget => (
      <WidgetRenderer key={widget.id} widget={widget} />
    ))}
  </CoachToolsPane>
);
```

### Performance Targets

- **Compose Time**: ≤200ms (manifest load → first widget render)
- **First Contentful Paint**: ≤300ms (right pane visibility)
- **Max Concurrent API Calls**: ≤3
- **Per-Widget Load**: ≤150ms (including data fetch)

---

## Workshop Features

### Source Switcher

Two tabs at top of Workshop:
- **📋 Personas (Legacy)** - Existing persona registry UI (unchanged)
- **🚀 Delegation (Registry)** - New manifest-driven UI (Career, PTC, future coaches)

### Intent & RR Simulator

**Features:**
- Intent selector (populates from manifest `intent_layouts`)
- Domain RR sliders (extracted from widget conditions)
- Auto-calculated curiosity values (100 - RR)
- Test user ID input
- Apply button to re-render preview

**Purpose:** Test widget visibility and layout changes based on simulated user state

### Data Binding Modes

1. **Live** - Real API calls to Core backend
   - Endpoint: `GET /api/coach/{coach_id}/panel?user={user_id}`
   - Requires Core running
   - Best for integration testing

2. **Stubbed** - Fixture data from `workshop_fixtures/*.json`
   - No backend required
   - Fast iteration
   - Controlled scenarios

3. **Hybrid** - Live RR/Curiosity + stubbed widgets
   - Best of both worlds
   - Test layout logic independently

### Performance Telemetry Panel

Displays:
- Compose time target vs. actual
- FCP target vs. actual
- Max API calls limit
- Per-widget render times
- Color-coded: Green (meets), Yellow (close), Red (exceeds)

---

## Implementation Tasks

### Phase 1: Workshop Bridge (1-2 days)

**Location:** `ExplorerDev/explorer_dev.py`

1. **Add source switcher UI**
   - Two tabs: Personas | Delegation
   - Preserve existing Personas tab (no changes)

2. **Implement delegation workshop renderer**
   ```python
   def _render_delegation_workshop(context):
       coaches = _load_delegation_coaches()
       selected_coach = st.selectbox("Select Coach", coaches)
       manifest = _load_and_validate_manifest(selected_coach)
       _render_intent_rr_simulator(manifest)
       _render_workshop_preview(manifest, data_mode, context)
   ```

3. **Load coaches from registry**
   - Read `coach_registry.yaml`
   - Extract coach metadata (id, display_name, description)

4. **Load and validate manifests**
   - Load YAML from `ReDNACoreDemo/coaches/{coach_id}/coach_ui_manifest.yaml`
   - Validate against `coach_ui_manifest.schema.json`
   - Show validation errors clearly

5. **Build intent/RR simulator**
   - Intent dropdown from manifest
   - RR sliders for relevant domains
   - Store state in session

6. **Implement layout resolution**
   - Apply intent layout overrides
   - Evaluate widget conditions
   - Sort by position

7. **Render widget previews**
   - Show widget metadata (ID, type, component, position)
   - Display data source info
   - Show AI suggestion config
   - Render fixture data (stubbed mode)

8. **Add telemetry panel**
   - Display performance targets from manifest
   - Placeholder for actual metrics

**Acceptance Criteria:**
- ✅ Source switcher visible with two tabs
- ✅ Delegation tab loads Career Coach and PTC
- ✅ Manifests validate successfully
- ✅ Intent/RR simulator functional
- ✅ Widget visibility changes with intent/RR adjustments
- ✅ Stubbed mode shows fixture data
- ✅ Legacy Personas tab unchanged (no regressions)

### Phase 2: RPUF Core (1-2 weeks)

**Location:** `ReDNACoreDemo/core/rpuf/`

1. **Create RPUF module structure**
   ```
   rpuf/
   ├── __init__.py
   ├── manifest_loader.py
   ├── widget_registry.py
   ├── layout_manager.py
   ├── condition_evaluator.py
   ├── data_binder.py
   ├── telemetry.py
   └── types.py
   ```

2. **Implement manifest loader**
   - Load YAML files
   - Validate against schema
   - Cache manifests

3. **Build widget registry**
   - Map component names → Python/React components
   - Register built-in widgets
   - Allow custom widget registration

4. **Create layout manager**
   - Apply intent layouts
   - Sort by position
   - Handle priority boost/hide/show

5. **Implement condition evaluator**
   - Intent conditions (OR logic)
   - RR/Curiosity thresholds (operators: <, <=, >, >=, ==)
   - Data availability checks
   - Feature flag checks

6. **Build data binder**
   - API data source (with caching)
   - Static data source
   - Computed data source
   - Hybrid mode support

7. **Add telemetry**
   - Compose time tracking
   - FCP tracking
   - Per-widget render time
   - API call counting

**Acceptance Criteria:**
- ✅ RPUF module importable in Workshop and production
- ✅ Manifest loading works with caching
- ✅ Widget registry resolves components
- ✅ Layout resolution matches spec
- ✅ All condition types evaluate correctly
- ✅ Performance targets met (≤200ms compose, ≤300ms FCP)

### Phase 3: Frontend Integration (1 week)

**Location:** `web/src/lib/rpuf/`, `web/src/components/widgets/`

1. **Create frontend RPUF library**
   ```
   rpuf/
   ├── index.ts
   ├── manifest-loader.ts
   ├── widget-renderer.tsx
   ├── widget-registry.ts
   ├── layout-resolver.ts
   ├── data-fetcher.ts
   ├── telemetry-hooks.ts
   └── types.ts
   ```

2. **Build widget components**
   ```
   widgets/
   ├── career/
   │   ├── SkillCuriosityMap.tsx
   │   ├── TransitionPlanner.tsx
   │   └── CareerDashboard.tsx
   ├── personality/
   │   ├── PersonalityRadar.tsx
   │   ├── AdaptiveQuestionnaire.tsx
   │   └── PersonalityMap.tsx
   ├── shared/
   │   ├── WidgetContainer.tsx
   │   ├── WidgetError.tsx
   │   └── WidgetSkeleton.tsx
   └── registry.ts
   ```

3. **Integrate with production UI**
   - Update `CoachToolsPane` to use RPUF
   - Feature flag: `rpuf_enabled`
   - A/B test: 50/50 legacy vs. RPUF

4. **Add telemetry hooks**
   - `useWidgetTelemetry(widgetId)`
   - Track render, interaction, error events
   - Send to analytics backend

**Acceptance Criteria:**
- ✅ All 6 Career Coach widgets render correctly
- ✅ All 6 PTC widgets render correctly
- ✅ Intent switching works in production
- ✅ RR/Curiosity conditions work with live data
- ✅ Performance targets met in production
- ✅ No regressions in legacy coaches

---

## Testing Strategy

### Unit Tests

- Manifest schema validation
- Condition evaluator logic
- Layout resolution (intent overrides, sorting)
- Widget registry lookups

### Integration Tests

- Workshop loads manifests correctly
- Intent/RR simulator updates widget visibility
- Data binding modes (live, stubbed, hybrid)
- Fixture loading and parsing

### E2E Tests

- Complete Workshop workflow (load coach → simulate intent → verify widgets)
- Production right-pane rendering with RPUF
- Performance regression tests (compose time, FCP)

### Manual Testing Checklist

- [ ] Workshop source switcher loads both tabs
- [ ] Career Coach manifest loads and validates
- [ ] PTC manifest loads and validates
- [ ] Intent selector populates from manifest
- [ ] RR sliders adjust and re-render preview
- [ ] Widget visibility respects intent conditions
- [ ] Widget visibility respects RR threshold conditions
- [ ] Priority boost moves widgets to top
- [ ] Hide/show overrides work
- [ ] Stubbed mode shows fixture data
- [ ] Live mode calls API (when backend available)
- [ ] Telemetry panel shows targets
- [ ] Legacy Personas tab still works
- [ ] No console errors or warnings

---

## Migration Path for Legacy Personas

### Phase 1: Adapter Manifests (Non-Breaking)

Create minimal manifests for PaDNA, Photo, and Relationship Coach that wrap existing components without changing behavior.

**Status:** Example manifests documented in [`LEGACY_PERSONA_MIGRATION.md`](LEGACY_PERSONA_MIGRATION.md)

**Timeline:** 1-2 days (optional, can happen anytime)

### Phase 2: Gradual Enhancement (Incremental)

Add intent layouts, AI suggestions, and conditional widgets to legacy coaches.

**Timeline:** 1-2 weeks (as needed for new features)

### Phase 3: Full Migration (Optional)

Fully migrate legacy coaches to RPUF and retire persona_registry.

**Decision:** Deferred - can be decided later based on Phase 2 results

---

## Success Metrics

### Immediate (Phase 1)

- ✅ Career Coach and PTC visible in Workshop
- ✅ Manifest validation works
- ✅ Intent/RR simulator functional
- ✅ Zero regressions in legacy Workshop

### Short-Term (Phase 2-3)

- ✅ Performance targets met (≤200ms compose, ≤300ms FCP)
- ✅ Dev/prod parity (Workshop preview matches production)
- ✅ All 12 widgets (Career + PTC) render correctly
- ✅ AI suggestions integrate with policy gates

### Long-Term

- ✅ New coaches can be added with manifests only (no code changes)
- ✅ Workshop becomes primary development surface for right-pane UI
- ✅ Legacy coaches adopt manifests (if Phase 2 proves valuable)
- ✅ Unified RPUF architecture across all coaches

---

## Next Steps

1. **Review & Approve Design** - Stakeholder review of architecture and specs
2. **Implement Phase 1** - Workshop bridge with source switcher
3. **Test with Career Coach** - Validate manifest loading and simulator
4. **Test with PTC** - Validate adaptive questionnaire and personality radar
5. **Build RPUF Core** - Backend Python module
6. **Build Frontend Integration** - React components and widgets
7. **A/B Test in Production** - Gradual rollout with feature flag
8. **Document Widget Development** - Guide for adding new widgets
9. **Consider Legacy Migration** - Decide on Phase 2/3 for legacy coaches

---

## Files Created/Modified

### New Files (8)

1. `docs/RPUF_ARCHITECTURE.md` - RPUF design specification
2. `docs/WORKSHOP_INTEGRATION_SPEC.md` - Workshop implementation details
3. `docs/LEGACY_PERSONA_MIGRATION.md` - Migration guide for legacy coaches
4. `docs/WORKSHOP_MODERNIZATION_SUMMARY.md` - This document
5. `ReDNACoreDemo/schemas/coach_ui_manifest.schema.json` - Manifest schema
6. `ReDNACoreDemo/coaches/career_coach/coach_ui_manifest.yaml` - Career Coach manifest
7. `ReDNACoreDemo/coaches/personality_test_coach/coach_ui_manifest.yaml` - PTC manifest
8. `ReDNACoreDemo/coaches/career_coach/workshop_fixtures/career_change.json` - Career fixture
9. `ReDNACoreDemo/coaches/personality_test_coach/workshop_fixtures/assessment_mode.json` - PTC fixture

### Modified Files (1)

1. `docs/Dev_Explorer_Guide.md` - Updated Coach Workshop section with delegation mode documentation

---

## Questions for Discussion

1. **Timeline Priority**: Should we prioritize Phase 1 (Workshop bridge) immediately, or wait until other features are complete?

2. **Legacy Migration**: Do we want to create adapter manifests for PaDNA, Photo, and Relationship Coach now, or defer until Phase 2?

3. **Widget Development**: Should we build all 12 widgets (Career + PTC) in Phase 3, or start with a minimal set (e.g., 2-3 widgets per coach)?

4. **A/B Testing**: What's the rollout strategy for RPUF in production? 50/50 split, gradual ramp, or feature-flag-only?

5. **Performance Budget**: Are the targets (200ms compose, 300ms FCP) realistic, or should we adjust based on current baseline measurements?

---

## Conclusion

The Coach Workshop modernization design is **complete and ready for implementation**. The bridge architecture allows us to:

- ✅ **Support new delegation coaches** (Career, PTC) without breaking legacy functionality
- ✅ **Use production RPUF renderer** ensuring dev/prod parity
- ✅ **Enable incremental migration** for legacy coaches over time
- ✅ **Provide powerful dev tools** (intent/RR simulator, data binding modes, telemetry)

The design balances **pragmatism** (no breaking changes) with **forward progress** (manifest-driven architecture), following ChatGPT's "Option 3: Bridge now, unify later" recommendation.

**Recommended Next Action:** Implement Phase 1 (Workshop bridge) to immediately enable Career Coach and PTC testing in the Workshop, then proceed to Phase 2-3 as capacity allows.
