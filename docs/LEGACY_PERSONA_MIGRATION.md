# Legacy Persona Migration Guide

**Version:** 1.0
**Last Updated:** October 7, 2025
**Status:** Migration Strategy

---

## Overview

This document provides a migration path from the legacy persona registry system to the new manifest-driven delegation system with RPUF (Right Pane Unified Framework).

## Current Legacy Personas

| Persona ID | Display Name | Status | Location |
|------------|-------------|--------|----------|
| `padna` | PaDNA Outbound Coach | Legacy | `ExplorerFinal/ui/personas/padna.py` |
| `photo` | Photo Coach | Legacy | `ExplorerFinal/ui/personas/photo.py` |
| `relationship_coach` | Relationship Coach | Legacy | `ExplorerFinal/ui/personas/relationship_coach.py` |

**Note:** Career Coach and Personality Test Coach are **delegation-native** (no legacy persona files).

## Migration Phases

### Phase 1: Adapter Pattern (Non-Breaking)

Create minimal manifests for legacy personas that wrap existing UI components without changing behavior.

**Goal:** Enable Workshop preview for legacy personas without modifying production code.

#### Steps

1. **Create manifest directory structure**
   ```bash
   mkdir -p ReDNACoreDemo/coaches/{padna_coach,photo_coach,relationship_coach}
   mkdir -p ReDNACoreDemo/coaches/{padna_coach,photo_coach,relationship_coach}/workshop_fixtures
   ```

2. **Create minimal adapter manifests**

   See examples below for each legacy coach.

3. **Test in Workshop**
   - Load manifest in Delegation tab
   - Verify widgets map to existing components
   - Ensure no production impact (manifests only used in Workshop)

**Acceptance Criteria:**
- ✅ All 3 legacy personas load in Workshop Delegation tab
- ✅ Manifests validate against schema
- ✅ Widget preview shows existing components
- ✅ Production UI unchanged (still uses persona_registry)

---

### Phase 2: Gradual Enhancement (Incremental)

Add delegation-specific features to legacy coaches incrementally.

**Goal:** Enhance legacy coaches with intent layouts, AI suggestions, and better data binding without full rewrite.

#### Steps

1. **Add intent-specific layouts**
   - Identify common user intents for each coach
   - Define `intent_layouts` in manifest
   - Test layout switching in Workshop

2. **Add conditional widgets**
   - Define conditions based on RR/Curiosity
   - Add new delegation-specific widgets alongside legacy ones
   - A/B test in production (feature flag)

3. **Enhance data sources**
   - Migrate from hard-coded API calls to manifest `data_source` configs
   - Add caching via `cache_ttl`
   - Enable stubbed mode for Workshop testing

**Acceptance Criteria:**
- ✅ Intent layouts work for at least 2 intents per coach
- ✅ New widgets coexist with legacy widgets
- ✅ No regressions in existing functionality

---

### Phase 3: Full Migration (Breaking - Optional)

Fully migrate legacy personas to delegation system and retire persona_registry.

**Goal:** Unify all coaches under manifest-driven RPUF architecture.

#### Steps

1. **Audit persona_registry dependencies**
   - Identify all imports of `ExplorerFinal/ui/personas/*.py`
   - Map to equivalent manifest configs

2. **Create complete manifests**
   - Convert all persona config to manifest format
   - Move all widgets to RPUF component registry
   - Add comprehensive workshop fixtures

3. **Update production UI**
   - Replace persona_registry calls with manifest loader
   - Use RPUF renderer for all coaches
   - Add feature flag for gradual rollout

4. **Retire legacy system**
   - Archive `ExplorerFinal/ui/personas/*.py` files
   - Remove persona_registry imports
   - Update documentation

**Acceptance Criteria:**
- ✅ All coaches render via RPUF in production
- ✅ Performance targets met (≤200ms compose, ≤300ms FCP)
- ✅ No persona_registry imports remain
- ✅ Legacy persona files archived

---

## Adapter Manifest Examples

### Photo Coach Adapter Manifest

**File:** `ReDNACoreDemo/coaches/photo_coach/coach_ui_manifest.yaml`

```yaml
schema_version: "1.0"
coach_id: "photo_coach"
manifest_version: "0.1.0"
renderer_version: "1.0"

metadata:
  author: "ReDNA Core Team"
  updated_at: "2025-10-07T00:00:00Z"
  description: "Photo Coach legacy adapter manifest"
  legacy_adapter: true  # Marks this as a legacy wrapper

widgets:
  # Existing PhotoPanel component
  - id: photo_panel
    type: interactive
    component: PhotoPanel  # Maps to existing component
    title: "Photo Analysis"
    description: "Upload and analyze photos for physical appearance traits"
    position: 0
    default_visible: true
    pinnable: true
    collapsible: true
    data_source:
      type: api
      endpoint: /api/photo/batches
      method: GET
      cache_ttl: 60
    conditions:
      - type: data_available
        data_available:
          path: "photo_batches"
          min_count: 0  # Always show (photo upload is primary feature)
    props:
      allowUpload: true
      showBatchHistory: true

  # Existing Avatar Render Panel
  - id: avatar_render_panel
    type: display
    component: AvatarRenderPanel
    title: "Avatar Renders"
    description: "Generated avatar visualizations from photos"
    position: 1
    default_visible: true
    pinnable: true
    collapsible: true
    data_source:
      type: api
      endpoint: /api/photo/renders
      method: GET
      cache_ttl: 120
    conditions:
      - type: data_available
        data_available:
          path: "render_batches"
          min_count: 1
    props:
      showHistory: true
      enableRegenerate: true

  # Existing Portrait Render Card
  - id: portrait_render_card
    type: display
    component: PortraitRenderCard
    title: "Portrait Render"
    description: "Latest portrait render with side-by-side comparison"
    position: 2
    default_visible: false  # Only show when renders exist
    pinnable: true
    collapsible: true
    data_source:
      type: api
      endpoint: /api/photo/portrait/latest
      method: GET
      cache_ttl: 180
    conditions:
      - type: data_available
        data_available:
          path: "latest_portrait"
          min_count: 1

# No intent layouts yet (phase 2)
intent_layouts: {}

default_layout:
  max_visible_widgets: 3
  spacing: normal

performance:
  compose_target_ms: 200
  fcp_target_ms: 300
  max_api_calls: 2
```

---

### Relationship Coach Adapter Manifest

**File:** `ReDNACoreDemo/coaches/relationship_coach/coach_ui_manifest.yaml`

```yaml
schema_version: "1.0"
coach_id: "relationship_coach"
manifest_version: "0.1.0"
renderer_version: "1.0"

metadata:
  author: "ReDNA Core Team"
  updated_at: "2025-10-07T00:00:00Z"
  description: "Relationship Coach legacy adapter manifest"
  legacy_adapter: true

widgets:
  # Existing ObservationSummary
  - id: observation_summary
    type: display
    component: ObservationSummary
    title: "Relationship Observations"
    description: "Summary of relationship patterns and insights"
    position: 0
    default_visible: true
    pinnable: true
    collapsible: true
    data_source:
      type: api
      endpoint: /api/observations/aggregates
      method: GET
      cache_ttl: 120
    conditions:
      - type: data_available
        data_available:
          path: "observations"
          min_count: 1
    props:
      showTimeline: true
      groupByCategory: true

  # Existing CoachAsksPanel
  - id: coach_asks_panel
    type: interactive
    component: CoachAsksPanel
    title: "Reflection Questions"
    description: "Personalized questions to deepen relationship understanding"
    position: 1
    default_visible: true
    pinnable: false  # Questions shouldn't be pinned
    collapsible: true
    data_source:
      type: api
      endpoint: /api/planner/asks
      method: GET
      cache_ttl: 0  # Always fresh
    props:
      maxAsks: 5
      allowDismiss: true

  # Existing NudgeInboxPanel
  - id: nudge_inbox_panel
    type: action
    component: NudgeInboxPanel
    title: "Relationship Nudges"
    description: "Suggested actions and micro-experiments"
    position: 2
    default_visible: true
    pinnable: true
    collapsible: true
    data_source:
      type: api
      endpoint: /api/planner/nudges
      method: GET
      cache_ttl: 60
    props:
      showCompleted: false
      groupByPriority: true

intent_layouts: {}

default_layout:
  max_visible_widgets: 3
  spacing: normal

performance:
  compose_target_ms: 200
  fcp_target_ms: 300
  max_api_calls: 3
```

---

### PaDNA Coach Adapter Manifest

**File:** `ReDNACoreDemo/coaches/padna_coach/coach_ui_manifest.yaml`

```yaml
schema_version: "1.0"
coach_id: "padna_coach"
manifest_version: "0.1.0"
renderer_version: "1.0"

metadata:
  author: "ReDNA Core Team"
  updated_at: "2025-10-07T00:00:00Z"
  description: "PaDNA Coach legacy adapter manifest"
  legacy_adapter: true

widgets:
  # Physical Appearance Summary
  - id: padna_summary
    type: display
    component: PaDNASummary
    title: "Physical Appearance Profile"
    description: "Comprehensive PaDNA trait summary"
    position: 0
    default_visible: true
    pinnable: true
    collapsible: true
    data_source:
      type: api
      endpoint: /api/coach/padna_coach/summary
      method: GET
      cache_ttl: 300
    conditions:
      - type: data_available
        data_available:
          path: "resolved.PaDNA"
          min_count: 5
    props:
      showCategories: true
      includePhotos: true

  # Style & Aesthetic Preferences
  - id: style_preferences
    type: display
    component: StylePreferences
    title: "Style DNA"
    description: "Fashion and aesthetic preferences"
    position: 1
    default_visible: true
    pinnable: true
    collapsible: true
    data_source:
      type: api
      endpoint: /api/coach/padna_coach/style
      method: GET
      cache_ttl: 600
    conditions:
      - type: data_available
        data_available:
          path: "resolved.PaDNA.StyleDNA"
          min_count: 3

intent_layouts: {}

default_layout:
  max_visible_widgets: 2
  spacing: normal

performance:
  compose_target_ms: 200
  fcp_target_ms: 300
  max_api_calls: 2
```

---

## Component Mapping Strategy

### Existing Components → RPUF Widgets

| Legacy Component | Location | RPUF Widget ID | Migration Status |
|------------------|----------|----------------|------------------|
| `PhotoPanel` | `web/src/components/photo/photo-panel.tsx` | `photo_panel` | ✅ Adapter ready |
| `AvatarRenderPanel` | `web/src/components/rendering/avatar-render-panel.tsx` | `avatar_render_panel` | ✅ Adapter ready |
| `PortraitRenderCard` | `web/src/components/padna/portrait-render-card.tsx` | `portrait_render_card` | ✅ Adapter ready |
| `ObservationSummary` | `web/src/components/observation-summary.tsx` | `observation_summary` | ✅ Adapter ready |
| `CoachAsksPanel` | `web/src/components/coach-asks-panel.tsx` | `coach_asks_panel` | ✅ Adapter ready |
| `NudgeInboxPanel` | `web/src/components/nudge-inbox-panel.tsx` | `nudge_inbox_panel` | ✅ Adapter ready |

**Key insight:** All existing UI components can be wrapped in RPUF `WidgetContainer` without modification. The manifest just provides metadata and conditional logic.

---

## Testing Strategy

### Phase 1 Testing (Adapters)

1. **Workshop Validation**
   - Load each legacy coach in Delegation tab
   - Verify manifest validates
   - Confirm widget list matches expectations

2. **Component Resolution**
   - Check that `component` field resolves to actual React component
   - Test with missing component (should show error gracefully)

3. **Data Source Stubbing**
   - Create minimal workshop fixtures
   - Test stubbed mode with fixture data

### Phase 2 Testing (Enhancements)

1. **Intent Switching**
   - Define 2-3 intents per coach
   - Test widget visibility changes with intent simulator
   - Verify priority boost works

2. **Conditional Rendering**
   - Test RR threshold conditions
   - Test curiosity threshold conditions
   - Test data availability conditions

3. **A/B Testing**
   - Feature flag: `rpuf_legacy_migration`
   - 50/50 split: old persona renderer vs. RPUF
   - Compare performance metrics

### Phase 3 Testing (Full Migration)

1. **Regression Testing**
   - All existing workflows continue to work
   - No visual regressions
   - Performance equals or exceeds legacy system

2. **Load Testing**
   - Manifest load time < 20ms
   - Widget render time < 100ms per widget
   - No memory leaks with repeated navigation

---

## Rollback Plan

### Phase 1 Rollback
- **Impact:** None (Workshop only, no production changes)
- **Action:** Remove manifests, Workshop reverts to Personas tab only

### Phase 2 Rollback
- **Impact:** Partial (new features only, old features unchanged)
- **Action:** Disable feature flag, hides new widgets

### Phase 3 Rollback
- **Impact:** Full (all coaches affected)
- **Action:** Restore persona_registry imports, revert to legacy renderer
- **Data:** No data migration needed (manifests are additive)

---

## Timeline Estimate

| Phase | Duration | Dependencies |
|-------|----------|-------------|
| Phase 1: Adapters | 1-2 days | RPUF core, Workshop integration |
| Phase 2: Enhancements | 1-2 weeks | Phase 1 complete, widget development |
| Phase 3: Full Migration | 2-4 weeks | Phase 2 validated, A/B test results |

**Total:** 3-6 weeks for full migration (if Phase 3 is pursued)

---

## Decision: To Migrate or Not?

### Arguments for Full Migration (Phase 3)

✅ **Unified system** - One codebase, one mental model
✅ **Better tooling** - Workshop works for all coaches
✅ **Easier to maintain** - Manifest changes don't require code deploys
✅ **Feature parity** - Legacy coaches get intent layouts, AI suggestions, etc.
✅ **Performance** - RPUF optimizations benefit all coaches

### Arguments Against Full Migration

❌ **Risk** - Legacy coaches work well, migration introduces regression risk
❌ **Cost** - 3-6 weeks of dev time
❌ **Low ROI** - If legacy coaches don't need new features, why rewrite?
❌ **Technical debt** - persona_registry is stable, no urgent need to retire

### Recommendation

**Proceed with Phase 1 & 2, defer Phase 3 decision**

- Phase 1 (adapters) is **zero-risk** and enables Workshop preview
- Phase 2 (enhancements) is **low-risk** and adds value incrementally
- Phase 3 (full migration) can be **decided later** based on Phase 2 results

If Phase 2 enhancements prove valuable and no major issues arise, Phase 3 becomes a natural next step. If not, legacy coaches can remain on persona_registry indefinitely.

---

## Appendix: Conversion Checklist

Use this checklist when creating adapter manifests:

- [ ] Create coach directory: `ReDNACoreDemo/coaches/{coach_id}/`
- [ ] Create manifest file: `coach_ui_manifest.yaml`
- [ ] Set `legacy_adapter: true` in metadata
- [ ] Map all existing UI components to widgets
- [ ] Use existing component names in `component` field
- [ ] Define data sources (API endpoints from existing code)
- [ ] Set reasonable `cache_ttl` values
- [ ] Add minimal conditions (data_available checks)
- [ ] Validate manifest against schema
- [ ] Create workshop_fixtures directory
- [ ] Add at least one fixture file
- [ ] Test in Workshop Delegation tab
- [ ] Document any component props needed

---

**References:**
- `RPUF_ARCHITECTURE.md` - Overall RPUF design
- `WORKSHOP_INTEGRATION_SPEC.md` - Workshop implementation details
- `coach_ui_manifest.schema.json` - Manifest schema
