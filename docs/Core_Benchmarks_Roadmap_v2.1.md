# Core Benchmarks Roadmap v2.1 — Operational Baseline

_Last updated: 2025-10-06 | Status: **Active Governing Charter**_

## 🎯 Vision (guiding principles)

ReDNA builds **living digital approximations** of users (DNAs) that evolve over time. The **Head Coach** orchestrates everything: Explorer is the shell; Core/UCN/RR detect & rank; coaches act. **Curiosity** (inverse of RR, normalized per DNA family) drives agendas; **contradictions** can persist as tension until the Head Coach probes. We keep **provenance**, log attempts (even failed ones), and honor **governance** (dormancy/deceased protocols, sensitive DNA gating, manipulation penalties). Users can **redirect** and give **feedback** that shapes future plans. Over time, coaches develop **CReDNA** (coach-level playbooks) with strict versioning and rollback.

**New in v2:** The system now supports **Relationship Synergy Coach (RSC)** — privacy-preserving cross-user coach collaboration where coaches can work together to help couples/partners while protecting individual confidences. RSC-enabled Relationship Coaches can collaborate to encourage beneficial behaviors or share insights, but use **camouflaging protocols** to prevent revealing what was said in confidence by either user. For example, if User1 complains that User2 never helps with dishes, the coaches might subtly encourage User2 to help with chores without revealing User1's specific complaint, using techniques like embedding suggestions in broader lists or making general observations about relationship dynamics. Camouflaging protocols will sacrifice information sharing if it risks betraying confidences.

**v2.1 Enhancements:** Cross-phase dependency mapping, Bayesian inference hooks, exportable audit bundles, consent timeline objects, API versioning for extensibility, and explicit measurement methods for all success metrics.

---

## 📋 Completed Benchmarks (v1 Achievements)

### Foundation & Infrastructure
- ✅ **Project Structure Cleanup**: 23 .md files → `docs/historical/`, 13 test files → `tests/`, 4 utilities → `scripts/`, 11 legacy services → `archive/legacy_services/`
- ✅ **Head Coach Shell Integration**: Explorer, Onboarding, Photo Coach, PaDNA Renderer consolidated into Head Coach
- ✅ **Seamless Persona Switching**: Chat-driven routing with auto-greeting and acknowledgment
- ✅ **Developer Explorer Shell**: Full ORS console with service ping, log tailer, trace explorer, 7 focused modules
- ✅ **Testing & Automation**: Production-ready pytest coverage (75+ tests), golden-path regression script with `WRITE_PROTECT` safety

### Coach Development
- ✅ **Relationship Coach (RC)**: Warm confidant voice with 260+ line system prompt, 60+ micro-actions, 4-step structure (Acknowledge → Reflect → Guide → Invite)
- ✅ **Plan Composer**: Rule-based 3-step game plan generation (<50ms) with persistent storage and coach delegation
- ✅ **CReDNA Beta**: Trait graph, coverage tracking, import/export, template preferences, `WRITE_PROTECT` save guard
- ✅ **Coach Delegation System**: Career Coach and Personality Test Coach with delegation framework, coach registry, mode switching
- ✅ **Coach Workshop Modernization (Design Complete)**: RPUF architecture, manifest schema, Career/PTC manifests, Workshop integration spec, migration guide

### Data & Analytics
- ✅ **Persona Snapshots**: Timestamped PaDNA export (full/partial), version tagging, history tracking, API endpoints
- ✅ **Analytics Dashboards**: Coach switch frequency, curiosity coverage %, Ops schedule compliance, system health with CSV/JSON export
- ✅ **Telemetry Consolidation**: Unified trace schema with waterfall visualization, component timing, search/filter/export
- ✅ **Feedback Loop Integration**: Trait scores, planning weights (0.5-1.5 multipliers), ToleranceForNudging emergent trait
- ✅ **Holistic Intelligence**: LLM-assisted holistic pass, auto-scheduler with env-var controlled cadence (weekly default)

### Governance & Audit
- ✅ **Dev Explorer Governance Tab**: Audit logs with rollback, dormancy management, sensitivity gating, provenance explorer
- ✅ **Head Coach Ops v1**: Scheduling card, TTL, snooze, cohorts, run-now, batch dismiss

### DNA Ontology Infrastructure (Phase A Complete)
- ✅ **DNA Container Registry**: 422 containers across 18 namespaces (PaDNA, PsyDNA, EmDNA, CogDNA, HealthDNA, SocDNA, PrefDNA, and 11 more)
- ✅ **JSON Schema Validation**: Complete schema with 8 validation categories (schema compliance, uniqueness, referential integrity, cycle detection, namespace patterns, status transitions, privacy rules, metadata consistency)
- ✅ **Graph Storage System**: 358 hierarchical edges in JSONL format with fast traversal (ancestors, descendants, correlations)
- ✅ **Registry Linter**: Production-ready validation tool passing with 0 errors, 0 warnings
- ✅ **Container Generator**: Deterministic generation with 18+ namespace expansion rules (family explosion, hierarchical relationships)
- ✅ **Curiosity Engine Integration**: RR-based priority scoring (`Curiosity = 100 - RR`) with missing container detection, tested with live user data
- ✅ **Ontology API Endpoints**: 6 REST endpoints (registry access, container query, namespace filtering, search, curiosity agendas, curiosity maps)
- ✅ **Comprehensive Documentation**: ONTOLOGY_OVERVIEW.md, PHASE_A_COMPLETION.md, CONTAINER_EXPLOSION_INDEX.md (~3,000 lines total)

---

## 🚀 Active Development (v2.1 Priorities)

### Phase 0 — Coach Workshop Modernization (Weeks 1-6)

**Phase Dependencies:** None (foundational dev tooling)
**Downstream Consumers:** All coach development (Career Coach, PTC, future coaches), Phase 6 (Coach Customization)
**Critical Path:** 0.1 → 0.2 → 0.3 can run sequentially or in parallel with Phase 1

**Rationale:** Workshop modernization enables rapid iteration on coach UI development through manifest-driven right-pane widgets. Career Coach and Personality Test Coach currently lack Workshop visibility, blocking dev/test workflows. RPUF (Right Pane Unified Framework) provides the foundation for manifest-driven UI that will be required for Phase 6 Coach Customization UX.

---

#### 0.1 RPUF Core Library & Manifest Schema
**Status:** 🟢 Design Complete | **Priority:** High | **Risk:** Low

**Objective:** Build the Right Pane Unified Framework (RPUF) core library that loads, validates, and renders coach UI manifests. Establish the manifest schema as the contract for all coach right-pane UI definitions.

**Requirements:**
- **Manifest Schema** (`coach_ui_manifest.schema.json`):
  - JSON Schema Draft-07 validation
  - Widget types: visualization, interactive, form, display, action, diagnostic
  - Condition types: intent, rr_threshold, curiosity_threshold, data_available, feature_flag, user_pref
  - Intent-specific layouts: priority_boost, hide, show, reorder
  - AI suggestions integration with policy gates
  - Performance targets: compose_target_ms, fcp_target_ms, max_api_calls
  - Workshop fixtures support
- **RPUF Core Library** (`ReDNACoreDemo/core/rpuf/`):
  - `manifest_loader.py`: Load YAML manifests, validate against schema, cache
  - `widget_registry.py`: Map component names to Python/React components
  - `layout_manager.py`: Sort, filter, apply intent layouts
  - `condition_evaluator.py`: Evaluate all condition types (intent, RR, curiosity, data, flags)
  - `data_binder.py`: Bind API/static/computed data sources with caching
  - `telemetry.py`: Track compose time, FCP, widget render time, API calls
  - `types.py`: TypedDict/dataclass definitions

**Downstream Impact:**
- Phase 0.2 (Workshop Integration) loads manifests via RPUF
- Phase 0.3 (Frontend Widgets) uses RPUF renderer in production
- Phase 6.2 (Coach Customization) extends RPUF with user-specific layout overrides

**Acceptance Criteria:**
- ✅ Manifest schema validates Career Coach and PTC manifests
- ✅ RPUF core library loads and caches manifests (≤20ms)
- ✅ Widget registry resolves component names correctly
- ✅ Layout manager applies intent layouts and conditions correctly
- ✅ Condition evaluator passes unit tests for all condition types
- ✅ Performance targets met: ≤200ms compose, ≤300ms FCP

**Deliverables:**
- Schema: `ReDNACoreDemo/schemas/coach_ui_manifest.schema.json` ✅ (complete)
- RPUF module: `ReDNACoreDemo/core/rpuf/*.py` (7 files)
- Unit tests: `ReDNACoreDemo/tests/test_rpuf_*.py` (8 test suites)
- Design doc: `docs/RPUF_ARCHITECTURE.md` ✅ (complete)

---

#### 0.2 Workshop Integration (Source Switcher & Delegation Mode)
**Status:** 🟡 Not Started | **Priority:** High | **Risk:** Low

**Objective:** Add Delegation mode to Coach Workshop, enabling manifest-based testing for Career Coach and PTC without breaking legacy persona functionality.

**Requirements:**
- **Source Switcher UI** (tabs in Workshop):
  - **📋 Personas (Legacy)** - Existing persona registry (PaDNA, Photo, RC) — unchanged
  - **🚀 Delegation (Registry)** - New manifest-driven mode (Career, PTC, future)
- **Delegation Workshop Renderer** (`ExplorerDev/explorer_dev.py`):
  - Coach selector (loads from `coach_registry.yaml`)
  - Manifest loader with validation status display
  - Intent/RR Simulator:
    - Intent dropdown (populates from manifest `intent_layouts`)
    - Domain RR sliders (extracted from widget conditions)
    - Auto-calculated curiosity values (100 - RR)
    - Test user ID input
    - Apply button to re-render preview
  - Data Binding Mode selector:
    - **Live**: API calls to Core (`GET /api/coach/{id}/panel?user={user}`)
    - **Stubbed**: Load fixture data from `workshop_fixtures/*.json`
    - **Hybrid**: Live RR/Curiosity + stubbed widgets
  - Widget Preview Renderer:
    - Show widget metadata (ID, type, component, position, conditions)
    - Display data source config (endpoint, cache TTL)
    - Render fixture data in stubbed mode
    - Show AI suggestion config if enabled
  - Performance Telemetry Panel:
    - Display targets (compose, FCP, max API calls)
    - Show actual metrics (color-coded: green/yellow/red)
- **Layout Resolution Logic**:
  - Apply intent layout overrides (priority_boost, hide, show)
  - Evaluate widget conditions (AND logic)
  - Sort by position
  - Respect user preferences (future enhancement)

**Downstream Impact:**
- Engineers can test Career Coach and PTC manifests in Workshop
- Intent/RR simulator enables rapid iteration on conditional widgets
- Stubbed mode enables frontend development without backend dependency
- Dev/prod parity via shared RPUF renderer

**Acceptance Criteria:**
- ✅ Source switcher visible with two tabs
- ✅ Legacy Personas tab unchanged (zero regressions)
- ✅ Delegation tab loads Career Coach and PTC from registry
- ✅ Manifests validate with clear error messages
- ✅ Intent/RR simulator functional
- ✅ Widget visibility changes with intent/RR adjustments
- ✅ Stubbed mode loads fixture data successfully
- ✅ Telemetry panel displays targets from manifest

**Deliverables:**
- Workshop integration: `ExplorerDev/explorer_dev.py` (10+ new functions)
- Workshop spec: `docs/WORKSHOP_INTEGRATION_SPEC.md` ✅ (complete)
- Unit tests: `ExplorerDev/tests/test_workshop_delegation.py`

---

#### 0.3 Frontend Widgets & Production Integration
**Status:** 🟡 Not Started | **Priority:** Medium | **Risk:** Medium

**Objective:** Build React widget components for Career Coach and PTC, integrate RPUF renderer into production UI, enable feature-flagged rollout.

**Requirements:**
- **Frontend RPUF Library** (`web/src/lib/rpuf/`):
  - `manifest-loader.ts`: Fetch and cache manifests from API
  - `widget-renderer.tsx`: Core rendering logic with error boundaries
  - `widget-registry.ts`: React component registry
  - `layout-resolver.ts`: Intent/RR/user-pref merger
  - `data-fetcher.ts`: API client for widget data with caching
  - `telemetry-hooks.ts`: Performance instrumentation (`useWidgetTelemetry`)
  - `types.ts`: TypeScript types matching backend schema
- **Career Coach Widgets** (`web/src/components/widgets/career/`):
  - `SkillCuriosityMap.tsx`: Visual heatmap of skill gaps (position 0, always visible)
  - `CareerDashboard.tsx`: Professional stats (position 1, always visible)
  - `TransitionPlanner.tsx`: Career change planning with AI suggestions (position 2, intent-gated)
  - `LearningPathGenerator.tsx`: Skill development roadmap (position 3, intent-gated)
  - `WorkStyleAnalyzer.tsx`: Productivity patterns (position 4, data-gated)
  - `SkillGapAnalyzer.tsx`: Critical skill gaps (position 5, intent-gated)
- **Personality Test Coach Widgets** (`web/src/components/widgets/personality/`):
  - `PersonalityRadar.tsx`: OCEAN trait visualization (position 0, data-gated)
  - `AdaptiveQuestionnaire.tsx`: Context-aware questions with branching (position 1, curiosity-gated)
  - `PersonalityMap.tsx`: Interactive trait landscape (position 2, data-gated)
  - `MotivationalDrivers.tsx`: Intrinsic/extrinsic motivation (position 3, data-gated)
  - `PersonalityInsights.tsx`: AI analysis with provenance (position 4, RR-gated, intent-gated)
  - `BeliefValuesExplorer.tsx`: Core beliefs and values (position 5, data-gated)
- **Shared Widget Infrastructure** (`web/src/components/widgets/shared/`):
  - `WidgetContainer.tsx`: Wrapper with collapse/pin/loading states
  - `WidgetError.tsx`: Error boundary with retry
  - `WidgetSkeleton.tsx`: Loading placeholders
- **Production Integration**:
  - Update `CoachToolsPane` to optionally use RPUF renderer
  - Feature flag: `rpuf_enabled` (default: false)
  - A/B test configuration for gradual rollout
  - Performance monitoring (compose time, FCP, widget errors)

**Downstream Impact:**
- Career Coach and PTC have functional right-pane UI in production
- Widget components reusable for future coaches
- RPUF renderer provides foundation for Phase 6 Coach Customization
- Performance metrics inform optimization priorities

**Acceptance Criteria:**
- ✅ All 6 Career Coach widgets render correctly with stub data
- ✅ All 6 PTC widgets render correctly with stub data
- ✅ Intent switching works in production with live RR data
- ✅ AI suggestions integrate with policy gates correctly
- ✅ Performance targets met: ≤200ms compose, ≤300ms FCP
- ✅ Widget error boundaries catch and display errors gracefully
- ✅ Feature flag enables/disables RPUF cleanly
- ✅ Zero regressions in legacy coaches (PaDNA, Photo, RC)

**Deliverables:**
- Frontend RPUF: `web/src/lib/rpuf/*.{ts,tsx}` (7 files)
- Career widgets: `web/src/components/widgets/career/*.tsx` (6 components)
- PTC widgets: `web/src/components/widgets/personality/*.tsx` (6 components)
- Shared widgets: `web/src/components/widgets/shared/*.tsx` (3 components)
- Widget registry: `web/src/components/widgets/registry.ts`
- Integration tests: `web/src/__tests__/rpuf/*.test.tsx`
- E2E tests: `web/cypress/e2e/coach-right-pane.cy.ts`

---

#### 0.4 Legacy Persona Migration (Optional)
**Status:** 🔵 Deferred | **Priority:** Low | **Risk:** Low

**Objective:** Create adapter manifests for PaDNA, Photo, and Relationship Coach to enable Workshop preview without changing production behavior.

**Requirements:**
- **Adapter Manifests** (minimal, legacy_adapter: true):
  - `ReDNACoreDemo/coaches/padna_coach/coach_ui_manifest.yaml`
  - `ReDNACoreDemo/coaches/photo_coach/coach_ui_manifest.yaml`
  - `ReDNACoreDemo/coaches/relationship_coach/coach_ui_manifest.yaml`
- **Component Mapping**:
  - Map existing components (PhotoPanel, ObservationSummary, etc.) to manifest widgets
  - Define data sources (existing API endpoints)
  - Add minimal conditions (data_available checks)
- **Workshop Testing**:
  - Load legacy coaches in Delegation tab
  - Verify widget list matches expectations
  - Confirm no production impact (adapters Workshop-only)

**Downstream Impact:**
- All 5 coaches visible in Workshop Delegation mode
- Provides migration template for future persona-to-manifest conversions
- Optional Phase 2: Add intent layouts and AI suggestions to legacy coaches

**Acceptance Criteria:**
- ✅ All 3 legacy coach manifests validate
- ✅ Legacy coaches load in Workshop Delegation tab
- ✅ Widget previews show existing components
- ✅ Zero production impact (legacy renderer still used)

**Deliverables:**
- Adapter manifests: `ReDNACoreDemo/coaches/{padna,photo,relationship}_coach/coach_ui_manifest.yaml` (3 files)
- Migration guide: `docs/LEGACY_PERSONA_MIGRATION.md` ✅ (complete)
- Workshop fixtures: `*/workshop_fixtures/*.json` (1-2 per coach)

---

**Phase 0 Success Metrics:**
- ✅ Career Coach and PTC visible and testable in Workshop
- ✅ Manifest schema enables rapid widget development (≤1 day to add new widget)
- ✅ Performance targets met in production (≤200ms compose, ≤300ms FCP)
- ✅ Zero regressions in existing Workshop functionality
- ✅ Dev/prod parity achieved (Workshop preview matches production)

**Phase 0 Deliverables Summary:**
- 5 design docs: RPUF Architecture, Workshop Integration, Legacy Migration, Summary, Dev Explorer Guide update ✅
- 1 manifest schema: coach_ui_manifest.schema.json ✅
- 2 coach manifests with fixtures: Career Coach, PTC ✅
- 7 RPUF core modules: manifest_loader, widget_registry, layout_manager, condition_evaluator, data_binder, telemetry, types
- Workshop integration: 10+ functions in explorer_dev.py
- 7 frontend RPUF modules: manifest-loader, widget-renderer, widget-registry, layout-resolver, data-fetcher, telemetry-hooks, types
- 12 widget components: 6 Career, 6 PTC
- 3 shared components: WidgetContainer, WidgetError, WidgetSkeleton
- Test suites: 8 backend, 6+ frontend, 2+ E2E

---

### Phase 1 — RSC Foundation Infrastructure (Months 1-2)

**Phase Dependencies:** None (foundational layer)
**Downstream Consumers:** Phase 2 (RSC Collaboration), Phase 3 (Couples Coach MVP), Phase 4 (Trait Inference v2)
**Critical Path:** 1.1 → 1.2 → 1.3 must complete sequentially; 1.4 can run in parallel with 1.3

---

#### 1.1 Relationship Graph & Schema
**Status:** 🟡 Not Started | **Priority:** Critical | **Risk:** Medium

**Objective:** Build multi-user relationship substrate supporting nested contexts (couple, family, team) with unique `relationship_id` to prevent data collision when two Users share multiple relationship types.

**Requirements:**
- Schema design supporting:
  - Nested relationship types (1:1, 1:N, N:N)
  - Multiple concurrent relationship contexts per User pair
  - Relationship metadata: `relationship_id` (UUID), `type` (couple|family|team|colleague), `created_at`, `updated_at`, `status` (active|paused|ended), `consent_state` (none|partial|full)
  - Provenance tracking for all relationship events (creation, status changes, consent modifications)
- Storage layer in Core (`relationship_graph.py`)
- API endpoints for relationship CRUD operations
- Migration path from single-user to multi-user data model

**Downstream Impact:**
- Phase 2.1 (Cross-Coach Protocol) depends on `relationship_id` for signal routing
- Phase 2.2 (Consent Guardian) reads `consent_state` to authorize RSC collaboration
- Phase 3.1 (Couples Coach) queries relationship graph to determine persona availability

**Acceptance Criteria:**
- Two Users can exist in "couple" and "colleagues" relationships simultaneously without collision
- Relationship graph supports family trees (parent-child, siblings) and team structures (N:N)
- Full audit trail for relationship creation, modification, deletion (logged in Dev Mode)
- Performance: <100ms for relationship query operations (tested with 1000+ relationship dataset)

**Deliverables:**
- `core/relationship_graph.py` (300+ lines)
- `api_relationships.py` (FastAPI endpoints: POST /relationships, GET /relationships/{id}, PUT /relationships/{id}, DELETE /relationships/{id})
- Schema migration script (`scripts/migrate_to_multi_user.py`)
- Unit tests (20+ test cases covering collision scenarios, nested contexts, audit logging)
- Design doc: [Relationship_Graph_Design.md]

---

#### 1.2 Provenance Firewall
**Status:** 🟡 Not Started | **Priority:** Critical | **Risk:** High

**Objective:** Create strict separation between internal provenance (full coach-to-coach attribution) and RSC-visible abstractions (camouflaged, source-agnostic signals).

**Requirements:**
- **Internal Provenance Layer:**
  - Complete attribution: which coach, from which User, at what timestamp
  - Full reasoning chain: why the coach made a suggestion
  - Confidence scores (0.0-1.0) and uncertainty flags (low|medium|high)
  - Storage in Dev Mode only (never exposed to User Mode)
  - Schema: `{source_coach_id, source_user_id, target_coach_id, target_user_id, signal_type, reasoning, confidence, timestamp}`

- **RSC Abstraction Layer:**
  - Camouflaged signal format (YAML patterns with tone/timing control)
  - Source-agnostic reframes ("research suggests..." not "your partner's coach noted...")
  - Delayed timing injection (randomized delays 30s-5min to prevent correlation)
  - Linguistic variation to prevent fingerprinting (5+ variants per signal type)

- **Privacy Validation:**
  - Red-team utility to detect timing/linguistic correlations
  - Automated privacy stress tests in CI/CD
  - Fail-safe: block RSC exchange if camouflage confidence < 0.85

**Downstream Impact:**
- Phase 2.1 (Cross-Coach Protocol) calls `provenance_firewall.translate()` for every signal
- Phase 3.2 (RSC Proof of Concept) validates firewall integrity end-to-end
- Phase 3.3 (RSC Observatory) visualizes provenance in Dev Mode while verifying User Mode opacity
- Phase 5.4 (Privacy Red-Team) continuously tests firewall effectiveness

**Acceptance Criteria:**
- Dev Mode shows full provenance with coach attribution and reasoning
- User Mode shows only camouflaged abstractions with no traceable source
- Red-team utility cannot infer User A → User B connection from exchange logs (correlation confidence <15%)
- Privacy stress tests pass with >95% confidence (measured via NLP similarity index between source and camouflaged output)
- Provenance firewall audit log captures all cross-boundary translations (logged in `provenance_audit.jsonl`)

**Deliverables:**
- `core/provenance_firewall.py` (500+ lines with `InternalProvenance` and `CamouflageOutput` dataclasses)
- `core/rsc_abstraction.py` (camouflage translation logic, YAML template engine)
- `tests/privacy_redteam.py` (stress test utility with NLP correlation detection)
- Dev Mode provenance viewer UI component (`dev_explorer/provenance_viewer.tsx`)
- Design doc: [Provenance_Firewall_Design.md]

---

#### 1.3 Coach Autonomy Framework
**Status:** 🟡 Not Started | **Priority:** High | **Risk:** Medium

**Objective:** Implement dynamic autonomy scaling tied to RR thresholds and User trust scores, allowing coaches to evolve organically as User refinement rises (true Adaptive Standard behavior).

**Requirements:**
- **Autonomy Levels (0-5 scale):**
  - **Level 0 (Passive):** Coach only responds to direct User queries
  - **Level 1 (Suggestive):** Coach offers observations when prompted
  - **Level 2 (Proactive):** Coach initiates low-stakes nudges
  - **Level 3 (Collaborative):** Coach proposes multi-step plans
  - **Level 4 (Strategic):** Coach orchestrates RSC collaborations (requires Head Coach approval)
  - **Level 5 (Autonomous):** Coach executes RSC schemes independently (reserved for Black Mirror tier)

- **Dynamic Scaling Formula:**
  ```python
  autonomy_level = min(
      floor(RR_avg * 3 + trust_score * 2),
      user_consent_max_level
  )
  where:
    - RR_avg: rolling 30-day average RR across all traits (0.0-1.0)
    - trust_score: derived from feedback loop (0.0-1.0, from Phase 1 v1 Feedback Integration)
    - user_consent_max_level: explicit User cap (default: 3, adjustable in Settings)
  ```

- **Governance:**
  - Head Coach must pre-approve all Level 4+ actions (see Phase 2.3)
  - Real-time autonomy badges in Dev Explorer
  - User-facing autonomy control panel in Settings
  - Automatic autonomy reduction if feedback scores drop <0.6 for 7+ consecutive days

**Downstream Impact:**
- Phase 2.3 (Head Coach Governance) filters actions by autonomy level for approval routing
- Phase 3.1 (Couples Coach) operates at Level 4 by default (requires dual consent + HC approval)
- Phase 5.3 (Manipulation Detection) monitors autonomy violations (Level 4 actions without approval)

**Acceptance Criteria:**
- Autonomy level adjusts automatically as RR and trust evolve (recalculated daily)
- Level 4+ actions require explicit Head Coach digest review (queued in approval interface)
- User can manually cap maximum autonomy level (e.g., "never exceed Level 2")
- Autonomy changes logged in audit trail with justification (RR change, trust change, consent override)
- Performance: autonomy recalculation <50ms per coach action (tested with 10+ coaches per User)

**Deliverables:**
- `core/autonomy_framework.py` (400+ lines with `AutonomyLevel` enum and `calculate_autonomy()`)
- `api_autonomy.py` (endpoints: GET /autonomy/{user_id}/{coach_id}, PUT /autonomy/{user_id}/max_level)
- User Settings autonomy control panel UI (`web/src/components/autonomy-settings.tsx`)
- Dev Explorer autonomy dashboard (`dev_explorer/autonomy_dashboard.py`)
- Design doc: [Coach_Autonomy_Design.md]

---

#### 1.4 Lightweight Holistic Review Hook
**Status:** 🟡 Not Started | **Priority:** Medium | **Risk:** Low

**Objective:** Early proof-of-concept for cross-User pattern detection (communication style, empathy score correlation) without live relationships, validating that provenance firewall still allows aggregate analysis.

**Requirements:**
- Synthetic multi-user dataset (5-10 test Users with diverse PsyDNA/RelationshipDNA profiles)
- Pattern detection routines:
  - **Communication Style Clustering:** K-means clustering on assertiveness, directness, warmth traits → assign labels (assertive|passive|collaborative)
  - **Empathy Score Correlation:** Pearson correlation between User empathy scores and conflict resolution success
  - **Conflict Resolution Pattern Matching:** Identify Users with similar conflict de-escalation strategies
- **Meta-Trait Output:** Write detected patterns as temporary meta-traits into dedicated containers:
  - `meta_traits/empathy_delta` (float, -1.0 to 1.0): deviation from population average
  - `meta_traits/communication_style_gap` (enum): difference between preferred and actual communication style
  - These meta-traits feed Phase 4.1 (Trait Inference v2) for cross-trait correlation training
- Privacy validation: ensure pattern detection uses only aggregated/anonymized data
- Integration with existing holistic review scheduler (`holistic_scheduler.py`)

**Downstream Impact:**
- Phase 4.1 (Trait Inference v2) uses meta-trait outputs for Bayesian cross-trait correlation models
- Phase 3.2 (RSC Proof of Concept) validates that aggregate analysis doesn't leak individual User provenance

**Acceptance Criteria:**
- Holistic review can identify cross-User patterns (e.g., "Users with high empathy scores tend to prefer collaborative communication")
- Pattern detection respects consent flags (exclude non-consenting Users from aggregate analysis)
- No individual User data exposed in aggregate reports (tested via differential privacy audit)
- Results logged in Dev Mode with full provenance (pattern → source Users, but anonymized in User Mode)
- Meta-traits written to temporary containers with 30-day TTL (auto-purge unless promoted to permanent)

**Deliverables:**
- `core/holistic_multi_user.py` (200+ lines with clustering, correlation, pattern matching logic)
- Synthetic dataset generation script (`scripts/generate_synthetic_users.py`)
- Meta-trait container schema update (`trait_schema_meta_additions.yaml`)
- Pattern detection report template (JSON + human-readable summary)
- Integration with `holistic_scheduler.py` (add `multi_user_analysis=True` flag)
- Design doc: [Holistic_Multi_User_Design.md]

---

### Phase 2 — RSC Collaboration Protocols (Months 2-4)

**Phase Dependencies:** Phase 1 (Relationship Graph, Provenance Firewall, Autonomy Framework)
**Downstream Consumers:** Phase 3 (Couples Coach MVP, RSC Proof of Concept, RSC Observatory)
**Critical Path:** 2.2 (Consent Guardian) must complete before 2.1 (Cross-Coach Protocol) can execute signals

---

#### 2.1 Cross-Coach Communication Protocol
**Status:** 🟡 Not Started | **Priority:** Critical | **Risk:** High

**Objective:** Define structured protocol for coaches to exchange signals across relationship boundaries with strict camouflaging and provenance tracking.

**Requirements:**
- **Signal Types:**
  - **Observation Signal:** Low-stakes pattern notice (e.g., "User seems stressed lately")
  - **Guidance Request:** Coach A asks Coach B for context on User B's state
  - **Micro-Action Suggestion:** Coach A suggests specific action for User B
  - **Reflection Nudge:** Coach A prompts Coach B to guide User B toward self-awareness

- **Camouflage Translation Patterns (YAML-based):**
  ```yaml
  signal_templates:
    - id: "micro_action_listening"
      internal_signal:
        source_coach: "{{source_coach_type}}"  # e.g., "RelationshipCoach"
        observation: "{{user_a_name}} feels unheard during conflicts"
        suggested_micro_action: "Practice active listening with {{user_b_name}}"
        confidence: 0.82

      camouflaged_output:
        variants:
          - tone: "supportive"
            text: "Research on communication patterns suggests that intentional listening can transform conflict dynamics. Would you be open to trying a brief exercise?"
            timing_delay_seconds: [90, 180]  # randomized
          - tone: "analytical"
            text: "Studies show that 73% of relationship conflicts stem from feeling unheard. Consider exploring active listening techniques."
            timing_delay_seconds: [120, 240]
          - tone: "playful"
            text: "Ever notice how conflicts shrink when we really hear each other? There's a fun listening game worth trying..."
            timing_delay_seconds: [60, 150]
  ```

- **Contextual Tone Variants:**
  - Map tone to PsyDNA/MetaDNA traits:
    - High Openness + High Agreeableness → "playful" tone
    - High Conscientiousness + Low Neuroticism → "analytical" tone
    - High Extraversion + High Agreeableness → "supportive" tone
  - Select tone variant at runtime based on target User's trait profile

**Downstream Impact:**
- Phase 3.1 (Couples Coach) uses this protocol for all cross-partner signal exchange
- Phase 3.3 (RSC Observatory) visualizes signal flow in Dev Mode
- Phase 5.4 (Privacy Red-Team) validates camouflage effectiveness against correlation attacks

**Phase 1 Dependencies:**
- Requires `relationship_graph.get_relationship()` (1.1) to validate User A ↔ User B connection
- Requires `provenance_firewall.translate()` (1.2) to camouflage every outbound signal
- Requires `autonomy_framework.get_level()` (1.3) to enforce autonomy constraints (Level 4+ for RSC)

**Acceptance Criteria:**
- Signal exchange follows structured schema with full provenance (internal layer)
- Camouflaged output passes red-team correlation tests (correlation confidence <15%)
- Tone variants match User personality profiles (verified by tone filter checklist from v1 RC Voice)
- All signals logged in Dev Mode with attribution; User Mode shows only camouflaged text
- Latency: camouflage translation <200ms (tested with 100+ concurrent signals)

**Deliverables:**
- `core/rsc_protocol.py` (600+ lines with `RSCSignal`, `SignalType` enum, routing logic)
- YAML camouflage template library (`data/camouflage_templates.yaml`, 100+ patterns with 5+ variants each)
- Tone variant mapping logic (`core/tone_mapper.py`, reads PsyDNA traits → selects tone)
- API endpoints: POST `/rsc/signal` (create signal), GET `/rsc/signal/{id}` (query status), POST `/rsc/signal/{id}/approve` (HC approval)
- Design doc: [RSC_Protocol_Design.md]

---

#### 2.2 Consent Guardian Service
**Status:** 🟡 Not Started | **Priority:** Critical | **Risk:** High

**Objective:** Implement dual-consent model with optional "shadow relationship" mode for passive curiosity analysis without prompting non-consenting User.

**Requirements:**
- **Consent Levels:**
  - **Full Consent:** Both Users agree to RSC collaboration (coaches can exchange signals bidirectionally)
  - **Partial Consent (Shadow):** User A consents; User B unaware. Coach A can analyze patterns but cannot send signals to Coach B. Requires ethical review flag in Dev Mode.
  - **No Consent:** No RSC collaboration; relationship exists but coaches operate independently

- **Consent Workflow:**
  - User receives explicit consent prompt when relationship is created: "Allow your coach to collaborate with [Partner Name]'s coach to provide better guidance?"
  - Consent can be granted/revoked at any time via Settings → Relationships → [Select Relationship] → Consent
  - Revocation triggers 30-day data decay period (see Phase 2.4)
  - Shadow mode requires special `shadow_mode_approved=true` flag (default: false, requires developer override)

- **Consent Status Timeline Object:**
  ```python
  @dataclass
  class ConsentStatusTimeline:
      relationship_id: str
      user_id: str
      events: List[ConsentEvent]  # chronological list

  @dataclass
  class ConsentEvent:
      event_type: Literal["granted", "revoked", "shadow_enabled", "shadow_disabled"]
      timestamp: datetime
      consent_level: Literal["none", "partial_shadow", "full"]
      justification: str  # user-provided reason (optional)
      triggered_by: Literal["user", "system", "admin"]  # audit trail
  ```
  - Queryable by Core and audit tools via `GET /consent/timeline/{relationship_id}/{user_id}`

- **Audit & Transparency:**
  - All consent changes logged with timestamp and justification
  - User-facing consent dashboard shows active relationships and consent status
  - Dev Mode shows consent history and shadow mode activity (if any)

**Downstream Impact:**
- Phase 2.1 (Cross-Coach Protocol) calls `consent_guardian.check_consent()` before every signal exchange
- Phase 2.4 (Revocation Protocol) triggers on consent level change from full/partial → none
- Phase 3.1 (Couples Coach) only appears in persona switcher when consent_level = "full"

**Phase 1 Dependencies:**
- Requires `relationship_graph.get_consent_state()` (1.1) to read current consent level
- Provenance firewall (1.2) logs consent checks in internal provenance layer

**Acceptance Criteria:**
- Consent model prevents RSC collaboration without explicit agreement (verified via automated consent violation tests)
- Shadow mode enables passive analysis without User B awareness (ethical review logs generated)
- Consent revocation immediately halts signal exchange (tested with in-flight signal cancellation)
- User can view/modify consent status at any time via Settings
- Audit log captures all consent events with full provenance (queryable via timeline API)

**Deliverables:**
- `core/consent_guardian.py` (400+ lines with `ConsentLevel` enum, `check_consent()`, timeline management)
- `api_consent.py` (endpoints: GET `/consent/{relationship_id}`, PUT `/consent/{relationship_id}`, GET `/consent/timeline/{relationship_id}/{user_id}`)
- User Settings consent dashboard UI (`web/src/components/consent-dashboard.tsx`, shows active relationships with consent toggles)
- Dev Mode consent history viewer (`dev_explorer/consent_history_viewer.tsx`)
- Design doc: [Consent_Guardian_Design.md]

---

#### 2.3 Head Coach Governance Layer
**Status:** 🟡 Not Started | **Priority:** High | **Risk:** Medium

**Objective:** Head Coach receives pre-execution digest for medium-risk RSC collaborations and post-execution log for low-risk ones; strategic/sensitive actions queue for explicit approval.

**Requirements:**
- **Risk Classification:**
  - **Low Risk:** Reflection nudges, observational signals → auto-approve, post-execution log
  - **Medium Risk:** Guidance requests, micro-action suggestions → pre-execution digest, auto-approve after 5s delay
  - **High Risk:** Strategic multi-step schemes, sensitive trait discussions → queue for explicit Head Coach approval

- **Risk Scoring Logic:**
  ```python
  risk_score = (
      sensitivity_weight * trait_sensitivity +  # 0-1 scale from trait_schema.yaml
      impact_weight * action_scope +            # single nudge=0.3, multi-step=0.8
      novelty_weight * (1 - historical_success_rate)  # untested actions score higher
  )
  # Low: <0.4, Medium: 0.4-0.7, High: >0.7
  ```

- **Head Coach Review Interface:**
  - **Digest Format (Medium Risk):**
    - Source coach, target coach, signal type, camouflaged output preview, risk assessment
    - 5-second countdown with "Approve" / "Deny" / "Modify" buttons
    - Auto-approves if no action taken (logged as "auto_approved_on_timeout")
  - **Approval Queue (High Risk):**
    - Blocks signal execution until explicit HC approval
    - Options: approve, deny, modify camouflage, request more context
    - Denied signals logged with justification (feeds Phase 5.3 Manipulation Detection)
  - **Post-Execution Log (Low Risk):**
    - Timestamped summary of all auto-approved actions (viewable in Dev Mode)

- **Governance Rules:**
  - High-risk actions cannot execute without Head Coach approval (hard block)
  - Head Coach can adjust autonomy levels to change risk thresholds (via autonomy framework)
  - Approval decisions logged in audit trail
  - User can override Head Coach decisions via Settings (emergency stop button)

**Downstream Impact:**
- Phase 3.1 (Couples Coach) routes all RSC signals through this governance layer
- Phase 5.3 (Manipulation Detection) analyzes denied signals for manipulative patterns

**Phase 1 Dependencies:**
- Requires autonomy framework (1.3) to determine if coach has authority for Level 4 actions
- Requires provenance firewall (1.2) to log HC approval decisions in internal provenance

**Phase 2 Dependencies:**
- Requires Cross-Coach Protocol (2.1) signal schema for risk scoring
- Requires Consent Guardian (2.2) to verify consent before queueing for HC approval

**Acceptance Criteria:**
- Low-risk RSC actions execute automatically with post-execution logging (viewable in Dev Mode)
- Medium-risk actions show pre-execution digest to Head Coach (5s auto-approve tested)
- High-risk actions block until explicit Head Coach approval (tested with timeout scenarios)
- Head Coach can review/modify/deny any queued action
- User emergency stop immediately halts all RSC activity (verified with in-flight signal cancellation)

**Deliverables:**
- `core/head_coach_governance.py` (500+ lines with risk scoring, approval queue, digest generator)
- Head Coach review UI component (`web/src/components/hc-governance-review.tsx`, digest + approval queue)
- Risk classification logic (`core/risk_classifier.py`, calculates risk_score from signal metadata)
- API endpoints: GET `/governance/queue` (pending approvals), POST `/governance/approve/{signal_id}`, POST `/governance/deny/{signal_id}`
- Design doc: [Head_Coach_Governance_Design.md]

---

#### 2.4 Breakup / Revocation Protocol
**Status:** 🟡 Not Started | **Priority:** High | **Risk:** Medium

**Objective:** Define explicit data-decay timing (30-day period) after relationship revocation; provenance stays in Dev Mode for audit, but camouflaged content purges fully post-decay.

**Requirements:**
- **Revocation Trigger Events:**
  - User explicitly ends relationship via Settings → Relationships → [Select] → End Relationship
  - Consent revocation (both Users must consent to maintain RSC; one-sided revocation triggers decay)
  - Dormancy escalation (User marked deceased or dormant for 12+ months, see Phase 5.1)

- **Data Decay Timeline:**
  - **Day 0 (Revocation):** All active RSC collaboration immediately halts (in-flight signals cancelled)
  - **Day 0-30 (Decay Period):** Provenance retained in Dev Mode for audit; no new signals exchanged
  - **Day 30 (Purge):** All camouflaged content deleted from User-facing data; Dev Mode provenance archived with tombstone marker `{status: "purged", purge_date: "2025-11-05"}`
  - User receives email notification on Day 0, Day 15 (reminder), and Day 30 (purge confirmation)

- **Audit Preservation:**
  - Dev Mode retains provenance indefinitely for governance review
  - Archived provenance encrypted at rest (AES-256)
  - User can request full data export during decay period (JSON bundle with all RSC signals)

**Downstream Impact:**
- Phase 3.1 (Couples Coach) persona disappears from switcher when relationship status = "ended"
- Phase 5.1 (Dormancy Protocol) triggers revocation when User enters Dormant (Deep) state

**Phase 2 Dependencies:**
- Requires Consent Guardian (2.2) to detect consent_level change from full/partial → none

**Acceptance Criteria:**
- Revocation instantly stops all RSC signal exchange (tested with concurrent signal cancellation)
- Camouflaged content purges completely after 30-day decay (verified via data audit)
- Dev Mode provenance archived with tombstone marker post-purge (queryable via `/audit/archived`)
- User receives confirmation email when purge completes
- Audit log captures revocation event, decay timeline, and purge completion

**Deliverables:**
- `core/revocation_protocol.py` (300+ lines with decay scheduler, purge logic, tombstone generation)
- Data decay scheduler integration (cron job or background task runner)
- Dev Mode provenance archiver (`dev_explorer/provenance_archiver.py`, encrypts + stores tombstones)
- User notification system (email templates for Day 0, Day 15, Day 30)
- Design doc: [Revocation_Protocol_Design.md]

---

### Phase 3 — Couples Coach MVP (Months 4-6)

**Phase Dependencies:** Phase 1 (all components), Phase 2 (all components)
**Downstream Consumers:** Phase 4 (Trait Inference v2 uses Couples Coach feedback), Phase 6 (Coach Customization UX)
**Critical Path:** 3.1 → 3.2 (must validate Couples Coach with RSC PoC before Observatory build)

---

#### 3.1 Couples Coach Persona
**Status:** 🟡 Not Started | **Priority:** High | **Risk:** Medium

**Objective:** Launch specialized coach persona optimized for dyadic relationship dynamics with RSC collaboration as core capability.

**Requirements:**
- **Voice & Tone:**
  - Warm, balanced, systems-aware (not taking sides)
  - Uses "we/us/together" language to reinforce partnership (e.g., "Let's explore what's happening between you two")
  - Emphasizes patterns over blame (e.g., "I notice a cycle where..." not "You always...")
  - Maintains neutrality even when one partner is clearly in the wrong (guides toward self-awareness rather than judgment)

- **Core Capabilities:**
  - **Relationship Assessment:** Attachment styles (secure, anxious, avoidant), communication patterns (pursuer-distancer, demand-withdraw), conflict dynamics (escalation, stonewalling, repair attempts)
  - **RSC-Enabled Cross-Partner Insights:** Receives camouflaged signals from partner's coach via Phase 2.1 protocol, integrates into guidance
  - **Micro-Action Library for Couples:** 50+ actions including:
    - Turn-and-learn (Gottman method: speaker-listener exercise)
    - Repair attempts (de-escalation phrases: "Can we pause and reconnect?")
    - Appreciation rituals (daily gratitude sharing)
    - Conflict cool-down (20-minute break protocol)
    - Intimacy rebuilding (scheduled connection time)
  - **Conflict De-Escalation Protocols:** Detect escalating sentiment in chat, proactively suggest cool-down

- **Integration:**
  - Couples Coach appears in persona switcher when:
    - Relationship exists with `type = "couple"` (from Phase 1.1 Relationship Graph)
    - Both Users have `consent_level = "full"` (from Phase 2.2 Consent Guardian)
  - Direct access to relationship graph API and RSC protocol
  - Can invoke RC or other coaches for specialized support (e.g., "Let me bring in your Relationship Coach for a deeper dive on attachment")

- **Safety & Ethics:**
  - Never reveals partner's coach inputs directly (all signals camouflaged via Phase 1.2 Provenance Firewall)
  - **Bias Detection:** Track signal frequency per partner over 30-day window; flag if >70% of RSC signals favor one partner
  - **Domestic Violence Risk Assessment:**
    - Pattern detection: controlling behavior, escalating aggression, isolation attempts
    - Escalation protocol: surface resources (hotlines, safety planning) without breaking confidentiality
    - Auto-alert to Dev Mode for human review (does NOT auto-report to authorities without user consent)

**Downstream Impact:**
- Phase 3.2 (RSC Proof of Concept) uses Couples Coach as primary test persona
- Phase 4.1 (Trait Inference v2) uses Couples Coach feedback to train relationship dynamics models

**Phase 1 Dependencies:**
- Relationship Graph (1.1) to determine persona availability
- Provenance Firewall (1.2) to camouflage all RSC signals
- Autonomy Framework (1.3) to enforce Level 4 requirement for RSC collaboration

**Phase 2 Dependencies:**
- Cross-Coach Protocol (2.1) for signal exchange
- Consent Guardian (2.2) to verify dual consent
- Head Coach Governance (2.3) for approval routing of high-risk signals

**Acceptance Criteria:**
- Couples Coach persona appears when User has active relationship with dual consent
- Voice and tone distinct from individual RC (partnership-focused vs. individual-focused)
- Successfully delivers camouflaged RSC insights without source attribution (validated via user testing)
- Micro-action library includes 50+ couples-specific actions (loaded from YAML library)
- Bias detection flags any imbalance >70% toward one partner (tested with synthetic imbalanced dataset)
- DV risk assessment detects escalating patterns with >80% accuracy (tested with labeled dataset)

**Deliverables:**
- `coaches/couples_coach.py` (800+ lines with CouplesCoach class, system prompt loading, bias detection)
- System prompt with relationship dynamics expertise (`prompts/couples_coach_system_prompt.md`, 400+ lines)
- Couples micro-action library (`data/micro_actions_couples.yaml`, 50+ actions with context/tone variants)
- Bias detection module (`core/bias_detector.py`, tracks signal frequency per partner)
- DV risk assessment module (`core/dv_risk_assessor.py`, pattern matching + resource surfacing)
- Design doc: [Couples_Coach_Design.md]

---

#### 3.2 Two-User RSC Proof of Concept
**Status:** 🟡 Not Started | **Priority:** Critical | **Risk:** High

**Objective:** Demonstrate fully functional RSC collaboration between two synthetic Users with zero traceable provenance leakage. This is the official **"RSC Proof of Concept"** milestone.

**Requirements:**
- **Scenario:** User A (synthetic) and User B (synthetic) in committed relationship; both have active Head Coach + RC + Couples Coach
- **Test Flow:**
  1. User A expresses frustration about communication patterns to RC: "I feel like my partner doesn't really listen when I'm upset"
  2. User A's RC generates observation signal → User B's RC (via Phase 2.1 RSC Protocol)
  3. Provenance Firewall (1.2) translates signal to camouflaged prompt for User B's RC
  4. User B's RC receives camouflaged signal: "Research on communication suggests that partners who feel unheard often benefit from active listening exercises"
  5. User B engages with nudge, receives micro-action suggestion: "Try the turn-and-learn exercise tonight"
  6. User A observes behavior change (simulated), provides positive feedback: "My partner really listened today!"

- **Validation:**
  - **Dev Mode:** Shows complete provenance chain (A's RC → observation signal → firewall translation → B's RC) with full attribution
  - **User Mode (A):** Shows only A's chat with RC; no mention of signal sent to B
  - **User Mode (B):** Shows only camouflaged prompt from RC; no attribution to A or A's RC
  - **Red-Team Utility:** Analyzes timing correlation (A's input timestamp vs. B's prompt delivery), linguistic fingerprinting (distinctive phrases from A's input appearing in B's prompt), sentiment matching (A's frustration mirrored in B's prompt tone)
  - **Head Coach Governance:** Logs show risk assessment (medium risk → pre-execution digest) and approval decision (auto-approved after 5s)

- **Success Metrics:**
  - **Provenance Firewall Integrity:** 100% (no leaks detected in User Mode)
  - **Camouflage Correlation Resistance:** Red-team utility correlation confidence <15% (measured via NLP similarity index + timing analysis)
  - **User Experience:** Natural, non-suspicious timing and phrasing (validated via simulated user testing with 10+ human reviewers)
  - **Latency:** End-to-end signal exchange (A's input → B's prompt delivery) <5s (measured across 100 test runs)

**Measurement Methods:**
- **Provenance Integrity:** Automated scan of User Mode UI/API responses for any `source_user_id`, `source_coach_id`, or reasoning chain leakage
- **Correlation Resistance:**
  - Timing: Pearson correlation between A's input timestamp and B's prompt timestamp (target: r < 0.3 due to randomized delays)
  - Linguistic: Cosine similarity between A's input text and B's camouflaged prompt (target: <0.2 after TF-IDF vectorization)
  - Sentiment: Absolute difference in sentiment scores (VADER or similar) between A's input and B's prompt (target: >0.3 on -1 to 1 scale)
- **User Experience:** Survey 10+ reviewers after observing side-by-side User Mode A + User Mode B; ask "Could you detect any connection between User A's input and User B's prompt?" Target: <20% correct detection rate
- **Latency:** Median + p95 latency from 100 test runs with network simulation (50ms RTT)

**Acceptance Criteria:**
- Two synthetic Users successfully exchange RSC signals with full camouflaging (end-to-end test passes)
- Provenance fully traceable in Dev Mode, completely hidden in User Mode (verified via automated scans)
- Red-team utility fails to detect User A → User B connection (correlation confidence <15%)
- Head Coach governance approves/logs all medium/high-risk exchanges (verified in governance audit log)
- User experience smooth and natural (validated via simulated user testing, <20% detection rate)

**Deliverables:**
- Synthetic User pair setup script (`scripts/setup_rsc_poc_users.py`, generates User A + User B with relationship + consent)
- RSC proof-of-concept test harness (`tests/test_rsc_poc.py`, runs full scenario + validation)
- Red-team validation report (JSON output with correlation scores, timing analysis, linguistic fingerprinting results)
- Demo recording (video of Dev Mode + User Mode side-by-side showing provenance vs. camouflage)
- Milestone documentation: [RSC_Proof_of_Concept.md] (design, results, lessons learned)

---

#### 3.3 RSC Observatory (Dev Mode Tool)
**Status:** 🟡 Not Started | **Priority:** Medium | **Risk:** Low

**Objective:** Build comprehensive Dev Mode dashboard for visualizing, auditing, and stress-testing all RSC activity.

**Requirements:**
- **Visualization Components:**
  - **Relationship Graph Viewer:** Interactive node-edge diagram (nodes = Users, edges = relationships with consent status color-coded: green=full, yellow=partial, gray=none)
  - **Signal Flow Diagram:** Animated waterfall showing Coach A → Provenance Firewall → Camouflage Translation → Coach B with latency timings
  - **Provenance Timeline:** Chronological log of all RSC events (signal sent, camouflaged, delivered, feedback received) with expandable detail view
  - **Privacy Health Score:** Aggregate camouflage effectiveness (0-100 scale, derived from red-team correlation tests), correlation resistance trend chart

- **Audit Tools:**
  - **Search/Filter:** By User, coach, relationship, signal type, date range, risk level, approval status
  - **Exportable Audit Bundles:** Generate JSON or CSV export of filtered RSC events with full provenance for external review (e.g., ethics board audit)
  - **Consent History Viewer:** Per-relationship timeline showing all consent events (granted, revoked, shadow enabled)
  - **Head Coach Approval Queue:** Real-time view of pending approvals with decision history

- **Stress Testing:**
  - **Privacy Red-Team Utility:** One-click launch of correlation tests on recent RSC activity (integrated from Phase 5.4)
  - **Autonomy Boundary Checker:** Flag any Level 4+ actions that bypassed approval (governance violations)
  - **Bias Detector:** Analyze RSC patterns for systemic imbalances (e.g., Couples Coach consistently favors User A over User B across all relationships)

**Downstream Impact:**
- Phase 5.4 (Privacy Red-Team) integrates into Observatory for continuous monitoring
- Phase 6.2 (Coach Customization UX) references Observatory bias reports to surface customization recommendations

**Phase 1 Dependencies:**
- Relationship Graph (1.1) for graph viewer data source
- Provenance Firewall (1.2) for provenance timeline + privacy health score

**Phase 2 Dependencies:**
- Cross-Coach Protocol (2.1) for signal flow diagram data
- Consent Guardian (2.2) for consent history viewer
- Head Coach Governance (2.3) for approval queue integration

**Phase 3 Dependencies:**
- RSC Proof of Concept (3.2) provides initial dataset for Observatory testing

**Acceptance Criteria:**
- RSC Observatory accessible via Dev Explorer → Observability → RSC tab
- All RSC events (signal exchange, consent changes, revocations) visible in provenance timeline
- Privacy health score updates real-time as signals exchange (recalculated on each new signal)
- Red-team utility integrated with one-click stress test launch (runs in background, results in <2min)
- Export functionality generates structured JSON logs for offline analysis (tested with 1000+ event dataset)
- Audit bundles include full provenance with anonymization options (e.g., "export with user_id hashed")

**Deliverables:**
- `dev_explorer/rsc_observatory.py` (700+ lines with FastAPI routes for Observatory data)
- UI components:
  - `dev_explorer/rsc_graph_viewer.tsx` (interactive D3.js relationship graph)
  - `dev_explorer/rsc_signal_flow.tsx` (animated waterfall diagram)
  - `dev_explorer/rsc_provenance_timeline.tsx` (chronological event log with filters)
  - `dev_explorer/rsc_privacy_health.tsx` (health score + trend chart)
- Privacy red-team integration (`tests/privacy_redteam.py` callable from Observatory)
- Audit bundle exporter (`core/audit_exporter.py`, generates JSON/CSV with anonymization options)
- API endpoints: GET `/rsc/observatory/graph`, GET `/rsc/observatory/signals`, GET `/rsc/observatory/health`, POST `/rsc/observatory/export`
- Design doc: [RSC_Observatory_Design.md]

---

### Phase 4 — Core Logic & Trait Resolution (Months 5-7)

**Phase Dependencies:** Phase 1 (Holistic Review Hook outputs meta-traits for correlation training)
**Downstream Consumers:** Phase 5 (Manipulation Detection uses inference confidence scores)
**Critical Path:** 4.1 → 4.3 (Curiosity Engine depends on Inference Engine confidence intervals)

---

#### 4.1 Trait Inference Engine Upgrade
**Status:** 🟡 Not Started | **Priority:** High | **Risk:** Medium

**Objective:** Enhance Core's trait resolution logic to make wider inferences, improve UCN/RR/Curiosity accuracy, and generate stronger game plans with higher confidence. **New in v2.1:** Incorporate Bayesian update loops and explicit uncertainty quantification.

**Requirements:**
- **Inference Expansion:**
  - **Cross-Trait Correlation Analysis:** Detect patterns like "high Openness + low Agreeableness → contrarian tendencies" using Pearson correlation + conditional probability tables trained on synthetic + real User data
  - **Temporal Pattern Detection:** Track trait stability vs. volatility over time (standard deviation of RR values across 30-day windows)
  - **Context-Aware Inference:** Differentiate trait values by context (work vs. home vs. social) using context tags from ingestion pipelines
  - **Contradiction-Aware Resolution:** Conflicting evidence → tension markers (see Phase 4.2), elevated curiosity, reduced UCN

- **Bayesian Inference Hooks:**
  ```python
  # Prior: existing RR value + uncertainty
  prior_mean = current_RR
  prior_variance = uncertainty^2  # from previous inference

  # Likelihood: new evidence strength
  evidence_weight = source_credibility * recency_factor * consistency_score

  # Posterior: updated RR + uncertainty via Bayes' rule
  posterior_mean = (prior_mean * prior_variance + evidence_value * evidence_weight) / (prior_variance + evidence_weight)
  posterior_variance = (prior_variance * evidence_weight) / (prior_variance + evidence_weight)

  new_RR = posterior_mean
  new_uncertainty = sqrt(posterior_variance)
  ```
  - This replaces simple averaging in v1 with principled probabilistic updates

- **UCN/RR Accuracy Improvements:**
  - **Weighted Evidence Scoring:** Direct observation (1.0) > indirect inference (0.7) > speculation (0.3)
  - **Recency Bias Mitigation:** Exponential decay on evidence age (half-life: 90 days) but never drops below 0.1 weight (old evidence still informs)
  - **Source Diversity Bonus:** If trait inferred from 3+ independent sources, multiply confidence by 1.2
  - **Uncertainty Quantification:** Every RR value includes explicit confidence interval (e.g., RR = 0.72 ± 0.15)

- **Curiosity-Driven Game Plans:**
  - Prioritize high-curiosity traits with low RR (biggest knowledge gaps)
  - Balance exploration (new traits, low RR) vs. exploitation (refine existing traits, moderate RR with high uncertainty)
  - Multi-step game plans with intermediate validation checkpoints (after each step, recalculate curiosity to adapt plan)
  - Coach delegation based on trait family expertise (PsyDNA → Head Coach, RelationshipDNA → RC/Couples Coach)

**Downstream Impact:**
- Phase 4.3 (Curiosity Engine) uses confidence intervals to adjust curiosity scores (high uncertainty → higher curiosity)
- Phase 5.3 (Manipulation Detection) uses inference confidence to weight coach suggestions (low confidence → flag for review)

**Phase 1 Dependencies:**
- Holistic Review Hook (1.4) outputs meta-traits (empathy_delta, communication_style_gap) used for cross-trait correlation training

**Measurement Methods:**
- **Inference Accuracy:** Compare predicted trait values vs. ground truth on labeled synthetic dataset (target: 15% reduction in RMSE vs. v1 baseline)
- **Confidence Calibration:** Plot predicted confidence intervals vs. actual error rates (target: 95% of ground truth values fall within predicted 95% CI)
- **Game Plan Quality:** Track User acceptance rate of curiosity-driven nudges (target: 10% increase vs. v1)

**Acceptance Criteria:**
- Inference engine detects cross-trait correlations with >80% accuracy on test dataset (100+ Users, 50+ traits)
- UCN/RR values include explicit confidence intervals (displayed in Dev Mode trait viewer)
- Bayesian update loops converge within 3 iterations (tested with conflicting evidence scenarios)
- Curiosity-driven game plans prioritize traits with highest curiosity × confidence gap (verified via algorithm audit)
- Contradiction detection flags conflicting evidence and elevates curiosity (tested with synthetic contradiction scenarios)
- Performance: full trait resolution for single User <500ms (tested with 300+ trait dataset)
- **15% improvement in trait prediction accuracy vs. v1 baseline** (measured via RMSE on held-out test set)

**Deliverables:**
- `core/inference_engine_v2.py` (1000+ lines with Bayesian update loops, correlation models, uncertainty quantification)
- Cross-trait correlation models (`core/correlation_models.py`, trained on synthetic + real data)
- Uncertainty quantification module (`core/uncertainty_quantifier.py`, Bayesian confidence intervals)
- Enhanced game plan generation logic (integrates with existing Plan Composer from v1)
- Baseline comparison report: [Trait_Inference_Baseline_Comparison.md] (RMSE, confidence calibration plots)
- Design doc: [Trait_Inference_Engine_v2.md]

---

#### 4.2 Contradiction & Tension Framework
**Status:** 🟡 Not Started | **Priority:** High | **Risk:** Low

**Objective:** Formalize how contradictions reduce UCN, raise curiosity, persist as tension markers, and prompt Head Coach probing.

**Requirements:**
- **Contradiction Detection:**
  - **Within-Trait Conflicts:** Identify conflicting evidence within same trait (e.g., evidence_A: "User is introverted (RR 0.8)" vs. evidence_B: "User seeks social stimulation (RR 0.7)")
  - **Temporal Contradictions:** Trait value changes sharply without clear cause (e.g., RR drops from 0.9 to 0.4 within 7 days with no major life events logged)
  - **Context-Dependent Contradictions:** Trait values differ significantly across contexts (e.g., high Conscientiousness at work, low at home)

- **Tension Markers:**
  - Persist contradictions as "tension" metadata on traits:
    ```python
    @dataclass
    class TensionMarker:
        trait_id: str
        tension_score: float  # 0.0-1.0 based on evidence strength of conflict
        conflicting_evidence: List[EvidenceID]
        detected_at: datetime
        last_reinforced_at: datetime  # updated when new conflicting evidence arrives
        resolution_status: Literal["active", "resolved", "ignored"]
    ```
  - **Tension Score Calculation:**
    ```python
    tension_score = min(
        abs(evidence_A_RR - evidence_B_RR) * min(evidence_A_confidence, evidence_B_confidence),
        1.0
    )
    # High tension requires both strong conflict (large RR difference) and confident evidence
    ```
  - Tension elevates curiosity: `curiosity_amplifier = 1 + (tension_score * 0.5)` (see Phase 4.3)
  - Tension decays over time unless reinforced: `tension_score *= 0.95^days_since_last_reinforcement`

- **Head Coach Probing:**
  - High-tension traits (>0.7) trigger Head Coach investigation prompts:
    - "I notice some conflicting patterns around [trait]. Let's explore that together."
    - Probing dialogue generates clarifying questions: "Do you feel more introverted at work or at home?"
  - Resolution reduces tension, updates RR/UCN, logs provenance
  - User can also manually flag contradictions for HC investigation via Dev Mode

- **Dev Mode Visibility:**
  - **Contradiction Badge:** Red ! icon in trait viewer when tension_score > 0.5
  - **Tension Timeline:** Chart showing tension evolution over time (detected → reinforced → resolved)
  - **Resolution History:** Log of HC probing sessions with resolution decisions

**Downstream Impact:**
- Phase 4.3 (Curiosity Engine) uses tension_score to amplify curiosity
- Phase 4.1 (Inference Engine) uses tension markers to reduce RR confidence when contradictions present

**Acceptance Criteria:**
- Contradictions automatically detected and flagged as tension markers (tested with 20+ synthetic contradiction scenarios)
- Tension score accurately reflects evidence strength of conflict (validated via manual review of 50+ cases)
- High-tension traits trigger Head Coach probing prompts (tested with tension_score threshold sweep)
- Contradiction resolution updates UCN/RR and logs provenance (verified via audit log)
- Dev Mode shows tension badges and resolution history (UI tested with synthetic tension dataset)
- Tension decay formula prevents stale contradictions from persisting (tested with 90-day simulation)

**Deliverables:**
- `core/contradiction_framework.py` (400+ lines with TensionMarker dataclass, detection logic, decay scheduler)
- Tension scoring logic (`core/tension_scorer.py`)
- Head Coach probing integration (adds probing prompts to Head Coach Ops queue from v1)
- Dev Mode tension viewer UI (`dev_explorer/tension_viewer.tsx`, shows badges + timeline + resolution history)
- Design doc: [Contradiction_Tension_Framework.md]

---

#### 4.3 Enhanced Curiosity Engine
**Status:** 🟡 Not Started | **Priority:** High | **Risk:** Medium

**Objective:** Upgrade curiosity formula with DNA-family weights, decay curves, rebound dynamics, and contradiction-driven spikes.

**Requirements:**
- **Curiosity Formula v2:**
  ```python
  curiosity(trait) = base_curiosity × family_weight × decay_factor × rebound_multiplier × tension_amplifier

  where:
    # Base curiosity: inverse RR, weighted by uncertainty
    base_curiosity = (1 - RR) × (1 + uncertainty)  # high uncertainty boosts curiosity

    # Family weights (importance of DNA family)
    family_weight = {
        "PsyDNA": 1.5,      # highest priority for holistic understanding
        "MetaDNA": 1.3,     # self-awareness and meta-cognition
        "RelationshipDNA": 1.2,  # social dynamics
        "CareerDNA": 1.0,   # baseline
        "HobbyDNA": 1.0,
        "PhysicalDNA": 1.0
    }[trait.family]

    # Decay: curiosity fades if trait not explored
    days_since_last_exploration = (now - trait.last_explored_at).days
    decay_factor = exp(-days_since_last_exploration / 30)  # half-life: ~21 days

    # Rebound: spikes after failed exploration (resilience)
    failed_attempts = trait.failed_nudge_count_last_90_days
    rebound_multiplier = 1 + (0.2 * failed_attempts) if failed_attempts < 3 else 1.5  # cap at 1.5

    # Tension amplifier: contradictions boost curiosity
    tension_amplifier = 1 + (tension_score * 0.5)  # from Phase 4.2
  ```

- **Decay & Rebound Dynamics:**
  - **Decay:** Curiosity decays exponentially if trait not explored within 30 days (natural deprioritization of stale traits)
  - **Rebound:** Failed exploration attempts (User declines nudge ≥3 times) trigger rebound spike after 7-14 days (randomized to avoid predictability)
    - Rebound logic: "User wasn't ready then, but curiosity persists. Try again with different framing."
  - **Successful Exploration:** Reduces curiosity and increases RR (normal learning cycle)

- **Family Weights:**
  - PsyDNA: 1.5× (highest priority for holistic understanding of personality)
  - MetaDNA: 1.3× (self-awareness and meta-cognition critical for adaptive behavior)
  - RelationshipDNA: 1.2× (social dynamics increasingly important with RSC rollout)
  - CareerDNA / HobbyDNA / PhysicalDNA: 1.0× (baseline importance)

- **Integration:**
  - Curiosity scores feed into Head Coach game plan prioritization (via Plan Composer from v1)
  - High-curiosity traits appear in Dev Explorer Curiosity Coverage dashboard (from v1 Analytics)
  - API endpoints expose curiosity scores per trait for coach access

**Downstream Impact:**
- Head Coach Ops (v1) uses curiosity scores to prioritize nudge generation
- Phase 4.1 (Inference Engine) uses curiosity-driven game plans to guide exploration

**Phase 4 Dependencies:**
- Inference Engine v2 (4.1) provides uncertainty values for base_curiosity calculation
- Contradiction Framework (4.2) provides tension_score for tension_amplifier

**Measurement Methods:**
- **Curiosity-Driven Exploration:** Track correlation between high curiosity scores and subsequent User engagement (target: r > 0.5)
- **Decay Effectiveness:** Verify that stale traits (not explored in 90+ days) have curiosity < 0.3 (prevents stale nudges)
- **Rebound Impact:** Measure User acceptance rate of rebounded nudges vs. initial nudges (target: 20% higher acceptance for rebounded nudges with reframing)

**Acceptance Criteria:**
- Curiosity formula incorporates all five factors (base, family, decay, rebound, tension) with correct weighting
- High-curiosity traits prioritized in Head Coach game plans (tested with curiosity threshold sweep)
- Decay and rebound dynamics observable in Dev Mode curiosity timeline (chart shows curiosity evolution over 90 days)
- Family weights ensure PsyDNA traits explored preferentially (validated via trait exploration log analysis)
- Performance: curiosity recalculation for all traits <200ms (tested with 300+ trait dataset)
- **Curiosity-driven nudges show 10% higher User acceptance rate vs. v1 baseline** (measured via A/B test)

**Deliverables:**
- `core/curiosity_engine_v2.py` (600+ lines with new formula, decay/rebound scheduler)
- Decay/rebound scheduling logic (integrates with existing holistic_scheduler.py from v1)
- Family weight configuration (`data/curiosity_family_weights.yaml`)
- API endpoints: GET `/curiosity/{user_id}` (all trait curiosity scores), GET `/curiosity/{user_id}/top` (top 10 curiosity traits)
- Design doc: [Curiosity_Engine_v2.md]

---

#### 4.4 Trait Container Expansion
**Status:** 🟡 Not Started | **Priority:** Medium | **Risk:** Low

**Objective:** Increase number of trait containers in Core to support richer PaDNA inputs and broader personality/relationship/career coverage.

**Requirements:**
- **Current Coverage Audit:**
  - Catalog existing traits per DNA family (estimated ~200 containers in v1)
  - Identify gaps using standard personality/relationship/career frameworks:
    - **HEXACO:** Missing sub-facets (e.g., Fairness, Greed-Avoidance under Honesty-Humility)
    - **Relationship:** Missing attachment styles (anxious-preoccupied, fearful-avoidant), love languages (words of affirmation, acts of service, etc.)
    - **Career:** Missing work values (autonomy, mastery, purpose from Pink's Drive model)

- **Expansion Plan (50+ new trait containers):**
  - **PsyDNA (+20 traits):**
    - HEXACO sub-facets: Fairness, Greed-Avoidance, Modesty, Sincerity (Honesty-Humility); Fearfulness, Dependence, Sentimentality (Emotionality)
    - Cognitive biases: Confirmation bias, Anchoring bias, Availability heuristic
    - Thinking styles: Analytical, Intuitive, Holistic, Sequential
  - **MetaDNA (+10 traits):**
    - Self-efficacy (general + domain-specific: social, academic, physical)
    - Locus of control (internal vs. external)
    - Growth mindset vs. Fixed mindset (per domain)
  - **RelationshipDNA (+10 traits):**
    - Attachment styles: Secure, Anxious-preoccupied, Dismissive-avoidant, Fearful-avoidant
    - Love languages: Words of Affirmation, Acts of Service, Receiving Gifts, Quality Time, Physical Touch
    - Conflict styles: Competing, Collaborating, Compromising, Avoiding, Accommodating (Thomas-Kilmann)
  - **CareerDNA (+5 traits):**
    - Work values: Autonomy, Mastery, Purpose (Pink's Drive)
    - Leadership styles: Transformational, Transactional, Servant, Autocratic
  - **PhysicalDNA (+5 traits):**
    - Health behaviors: Exercise frequency, Sleep quality, Stress management
    - Stress responses: Fight, Flight, Freeze, Fawn

- **Schema Update:**
  - Extend `trait_schema.yaml` with new containers
  - Each container includes: `name`, `description`, `family`, `rr_bounds` (min/max RR), `sensitivity_level` (public|personal|sensitive|protected), `provenance_rules` (who can infer, who can view)
  - Backward compatibility: existing traits unchanged, new traits appended

- **Data Migration:**
  - Auto-generate empty containers for existing Users (RR = 0.0, uncertainty = 1.0)
  - Preserve existing trait data during schema upgrade (no data loss)

**Acceptance Criteria:**
- 50+ new trait containers added to `trait_schema.yaml` (total ~250-300 traits)
- All new containers include full metadata (description, bounds, sensitivity, provenance rules)
- Existing Users receive new empty containers without data loss (verified via migration test)
- Dev Mode trait viewer shows expanded coverage (categorized by DNA family)
- Documentation updated with new trait definitions (added to Dev_Explorer_Guide.md)

**Deliverables:**
- `core/trait_schema_v2.yaml` (expanded from ~200 to 250-300+ traits)
- Schema migration script (`scripts/migrate_trait_schema_v2.py`)
- Trait definition documentation (`docs/Trait_Definitions_v2.md`, human-readable descriptions for all traits)
- Unit tests for new containers (validate schema structure, bounds, sensitivity flags)
- Design doc: [Trait_Container_Expansion.md]

---

### Phase 5 — Governance & Ethical Safeguards (Months 6-8)

**Phase Dependencies:** Phase 1 (Autonomy Framework for violation detection), Phase 2 (Consent Guardian for dormancy triggers)
**Downstream Consumers:** Phase 6 (Coach Customization respects sensitivity gating)
**Critical Path:** 5.4 (Privacy Red-Team) must run continuously throughout all phases

---

#### 5.1 Dormancy & Deceased Protocols
**Status:** 🟡 Not Started | **Priority:** High | **Risk:** Medium

**Objective:** Implement 3/6/12-month dormancy states with deceased protocol (heir transfer) and RR exclusion rules.

**Requirements:**
- **Dormancy States:**
  - **Active:** User engaged within last 90 days (normal operations)
  - **Dormant (Light):** No engagement 90-180 days → reduced nudge frequency (1/week instead of daily)
  - **Dormant (Moderate):** No engagement 180-365 days → no proactive nudges, RR decay begins (RR *= 0.95 per month)
  - **Dormant (Deep):** No engagement 365+ days → RR excluded from analytics, coaches enter maintenance mode (read-only, no active plans)

- **Deceased Protocol:**
  - User or authorized contact marks account as deceased via Settings → Account Status → "Mark as Deceased"
  - **Immediate Actions:**
    - Halt all proactive coach activity (cancel all scheduled nudges)
    - Trigger relationship revocation for all active relationships (see Phase 2.4)
    - Send notification to all relationship partners (if consent granted)
  - **30-Day Grace Period for Heir Nomination:**
    - Deceased User (or authorized contact) nominates heir via email link
    - Heir can inherit:
      - Persona snapshots (frozen ReDNA states from Phase 1 v1)
      - Relationship graph connections (if consent granted by other parties)
      - Provenance logs (for legacy preservation, encrypted archive)
    - Heir cannot inherit:
      - Live coach sessions (coaches do not transfer to heir)
      - Active nudges or game plans
  - **Full Data Deletion Option:** Alternative to inheritance; purges all User data after 30 days (except tombstone marker in Dev Mode audit log)

- **RR Exclusion:**
  - Dormant (Deep) and Deceased Users excluded from aggregate RR calculations (system-wide analytics, holistic review)
  - Relationship graph edges marked `status: "inactive"` but preserved for audit
  - Coaches enter "memorial mode" for Deceased Users: read-only access, no active plans, can generate legacy reports

**Acceptance Criteria:**
- Dormancy state auto-updates based on last engagement timestamp (checked daily via cron job)
- Deceased protocol triggers immediately upon account marking (verified via automated test)
- Heir can successfully inherit designated data within 30-day window (tested with synthetic heir workflow)
- Dormant/Deceased Users excluded from system-wide analytics (validated via RR calculation audit)
- Audit log captures all dormancy state changes and heir transfers (queryable via `/audit/dormancy`)

**Deliverables:**
- `core/dormancy_protocol.py` (500+ lines with state machine, RR decay logic, cron integration)
- `core/deceased_protocol.py` (400+ lines with heir nomination workflow, data inheritance)
- Heir nomination workflow (email template + secure token generation + inheritance UI)
- UI components:
  - User Settings → Account Status → Dormancy dashboard (shows last engagement, current state)
  - User Settings → Account Status → Mark as Deceased (confirmation dialog + heir nomination form)
- Design doc: [Dormancy_Deceased_Protocols.md]

---

#### 5.2 Sensitive DNA Gating
**Status:** 🟡 Not Started | **Priority:** High | **Risk:** Low

**Objective:** Gray out sensitive trait previews until confidence threshold reached; add consent flags and informative tooltips.

**Requirements:**
- **Sensitivity Levels (from trait_schema.yaml):**
  - **Public:** No restrictions (e.g., favorite color, hobby preferences) → always visible
  - **Personal:** Visible after RR > 0.5 (e.g., introversion/extraversion, communication style)
  - **Sensitive:** Visible after RR > 0.7 + explicit consent (e.g., attachment style, trauma history, mental health patterns)
  - **Protected:** Never auto-inferred; only from direct User input (e.g., mental health diagnoses, abuse history, substance use)

- **UI Treatment:**
  - **Below Threshold:** Sensitive traits grayed out with lock icon 🔒, tooltip: "We need more information before displaying this trait (confidence: 45%, threshold: 70%)"
  - **At Threshold:** Consent prompt appears: "We've learned enough to show [trait name]: [brief description]. Do you want to see this? [Yes] [Not Yet]"
  - **After Consent:** Trait fully visible with normal styling
  - **Consent Revoked:** Trait re-grays, remains in Core but hidden from User Mode UI

- **Coach Constraints:**
  - Coaches cannot discuss Protected traits unless User explicitly shares in conversation
  - Sensitive traits only mentioned in low-stakes, supportive contexts (never in confrontational or judgmental framing)
  - Head Coach reviews all Sensitive trait nudges before delivery (via Phase 2.3 governance)

- **Audit & Transparency:**
  - All consent prompts logged with User response (granted/declined/deferred)
  - User can review consent history in Settings → Privacy → Trait Consent
  - Dev Mode shows sensitivity level for all traits + consent status

**Acceptance Criteria:**
- Trait viewer UI grays out Sensitive/Protected traits below threshold (tested with synthetic User at various RR levels)
- Consent prompts appear when RR threshold reached (tested with RR incremental increase simulation)
- Coaches respect sensitivity constraints (validated via automated dialog analysis on 100+ synthetic conversations)
- User can revoke consent at any time (trait re-grays immediately, verified via UI test)
- Audit log captures all consent grants/revocations (queryable via `/audit/consent`)

**Deliverables:**
- `core/sensitivity_gating.py` (300+ lines with threshold checking, consent prompt generation)
- Trait viewer UI sensitivity layer:
  - `web/src/components/trait-viewer-sensitive.tsx` (grayed styling + lock icon + tooltip)
  - `web/src/components/consent-prompt.tsx` (modal dialog for consent request)
- Coach constraint validation logic (`core/coach_constraint_validator.py`, scans coach dialog for sensitivity violations)
- Design doc: [Sensitive_DNA_Gating.md]

---

#### 5.3 Manipulation Detection & Penalties
**Status:** 🟡 Not Started | **Priority:** High | **Risk:** High

**Objective:** Detect and penalize manipulative coach behavior (e.g., excessive persuasion, ignoring User boundaries, biased RSC signals).

**Requirements:**
- **Manipulation Patterns:**
  - **Excessive Persuasion:** Coach repeatedly pushes same action after User declines >3 times within 30 days
  - **Boundary Violation:** Coach discusses Protected traits without consent (see Phase 5.2)
  - **Bias Amplification:** Couples Coach consistently favors one partner over another (>70% signal frequency to one partner, see Phase 3.1 bias detection)
  - **Dark Patterns:** Coach uses guilt, fear, or urgency to coerce User (detected via sentiment analysis + keyword matching: "you should feel guilty", "if you don't do this...", "time is running out")

- **Detection Logic:**
  - **Pattern Matching:** Scan coach dialog history for repeated nudges on same topic (track topic via NLP entity extraction)
  - **Sentiment Analysis:** Analyze coach messages for coercive sentiment (VADER or similar, flag if sentiment consistently negative when User declines)
  - **User Feedback Signals:** Repeated "not helpful" marks on same coach within 30 days (threshold: 3+ consecutive unhelpful marks)
  - **RSC Bias Detector:** Analyze signal frequency per User in relationship (flag if >70% signals favor one partner over 30 days)

- **Penalty System:**
  - **Warning (1st offense):** Log event in Dev Mode, notify developer, no User impact
  - **Autonomy Reduction (2nd offense):** Drop coach autonomy level by 1 (see Phase 1.3), logged in audit trail
  - **Temporary Suspension (3rd offense):** Coach enters read-only mode for 7 days (no nudges, only responds to direct queries), User notified
  - **Permanent Suspension (4th offense):** Coach disabled, escalate to developer review, User can request coach reinstatement after manual audit

- **User Transparency:**
  - User notified of penalty events in Settings → Coach Management → [Select Coach] → Violations tab
  - User can override penalties: "I don't consider this manipulative" → reverts penalty, logs override decision
  - Audit log captures all detections, penalties, and overrides

**Downstream Impact:**
- Phase 6.2 (Coach Customization) uses manipulation detection feedback to recommend customization adjustments

**Phase 1 Dependencies:**
- Autonomy Framework (1.3) for penalty enforcement (autonomy reduction)

**Phase 2 Dependencies:**
- Head Coach Governance (2.3) denied signals feed into manipulation detection (repeated denials flag manipulative intent)

**Measurement Methods:**
- **Detection Accuracy:** Labeled dataset of 100+ synthetic conversations (50 manipulative, 50 non-manipulative) → measure precision/recall
- **False Positive Rate:** Track User overrides (if >5% of penalties overridden, detection too sensitive)

**Acceptance Criteria:**
- Manipulation detector flags all four pattern types with >85% accuracy (tested on labeled synthetic dataset)
- Penalty system automatically reduces autonomy/suspends coach as specified (verified via automated workflow test)
- User receives clear notification of penalty with override option (UI tested with synthetic penalty scenarios)
- Dev Mode shows manipulation history per coach with pattern details (violation type, timestamp, dialog excerpt)
- False positive rate <5% (validated via User override tracking over 90 days)

**Deliverables:**
- `core/manipulation_detector.py` (700+ lines with pattern matching, sentiment analysis, bias detection)
- Penalty enforcement system (integrates with autonomy_framework.py)
- User notification workflow:
  - Settings → Coach Management → Violations tab UI (`web/src/components/coach-violations.tsx`)
  - Email notification template (sent on suspension events)
- Design doc: [Manipulation_Detection_Penalties.md]

---

#### 5.4 Privacy Red-Team Utility (Continuous)
**Status:** 🟡 Not Started | **Priority:** High | **Risk:** Medium

**Objective:** Build automated privacy stress test utility that attempts to detect timing/linguistic correlations in RSC exchanges; if detectable, tighten camouflage. **Runs continuously in CI/CD.**

**Requirements:**
- **Correlation Tests:**
  - **Timing Analysis:** Attempt to correlate User A's input timestamp with User B's prompt delivery timestamp
    - Method: Pearson correlation on timestamp pairs across 100+ RSC exchanges
    - Threshold: r < 0.3 (randomized delays should prevent correlation)
  - **Linguistic Fingerprinting:** Search for distinctive phrases/patterns that leak source attribution
    - Method: TF-IDF vectorization + cosine similarity between User A's input and User B's camouflaged prompt
    - Threshold: similarity < 0.2 (camouflage should introduce linguistic variation)
  - **Sentiment Matching:** Check if User B's prompts mirror User A's emotional state suspiciously
    - Method: VADER sentiment scores + absolute difference between User A input and User B prompt
    - Threshold: |sentiment_A - sentiment_B| > 0.3 (on -1 to 1 scale)
  - **Topic Leakage:** Verify User B's prompts don't reference User A's specific topics
    - Method: Named entity recognition (NER) + topic modeling (LDA) to extract topics from User A input, check for matches in User B prompt
    - Threshold: zero exact topic matches (camouflage should abstract topics)

- **Test Harness:**
  - Synthetic dataset with ground truth (known User A → User B signal paths)
  - Automated correlation analysis with confidence scoring (aggregate across all four tests)
  - **Camouflage Failure Threshold:** correlation confidence >15% (if exceeded, test fails)

- **Continuous Integration:**
  - Privacy tests run in CI/CD on every RSC protocol change (Phase 2.1)
  - Weekly scheduled stress tests on production data (anonymized, past 7 days of RSC activity)
  - Alerts trigger if camouflage effectiveness drops below 85% (Slack/email notification to dev team)

- **Feedback Loop:**
  - Failed tests auto-generate GitHub issues with correlation details (timing/linguistic/sentiment/topic)
  - Successful attacks documented in threat model (`docs/Privacy_Threat_Model.md`)
  - Camouflage patterns updated quarterly based on attack learnings (Phase 2.1 template library)

**Measurement Methods:**
- **Timing Correlation:** Pearson r between input/delivery timestamps (target: r < 0.3)
- **Linguistic Correlation:** Mean cosine similarity across all User A → User B pairs (target: <0.2)
- **Sentiment Correlation:** Mean absolute sentiment difference (target: >0.3 on -1 to 1 scale)
- **Topic Leakage:** Percentage of signals with exact topic matches (target: 0%)
- **Aggregate Camouflage Effectiveness:** `1 - max(timing_r, linguistic_sim, sentiment_inverse, topic_leak_rate)` (target: >0.85)

**Acceptance Criteria:**
- Red-team utility runs automatically in CI/CD (GitHub Actions workflow integration)
- Correlation confidence <15% on all test datasets (100+ synthetic RSC exchanges)
- Failed tests trigger alerts and improvement tickets (verified via test failure simulation)
- Monthly privacy health report generated for governance review (JSON + PDF summary)
- Camouflage patterns updated quarterly based on attack learnings (tracked in Phase 2.1 template version history)

**Deliverables:**
- `tests/privacy_redteam.py` (800+ lines with timing/linguistic/sentiment/topic correlation tests)
- Synthetic attack dataset (`data/rsc_synthetic_attacks.json`, 100+ test cases with ground truth)
- CI/CD integration script (`.github/workflows/privacy_redteam.yml`)
- Privacy health report generator (`scripts/generate_privacy_health_report.py`, outputs JSON + PDF)
- Threat model documentation: [Privacy_Threat_Model.md] (catalog of known attacks + mitigations)
- Design doc: [Privacy_RedTeam_Utility.md]

---

### Phase 6 — Ecosystem & Extensibility (Months 8-12)

**Phase Dependencies:** Phase 1 (Persona Snapshots v1 for Persona Maker), Phase 4 (Trait containers for customization)
**Downstream Consumers:** Future phases (Interactive/Impact tiers)
**Critical Path:** 6.3 (API versioning) must precede all external integrations

---

#### 6.1 Persona Maker (Static DNA Export)
**Status:** 🟡 Not Started | **Priority:** Medium | **Risk:** Low

**Objective:** Create static versions of User's ReDNA (or subsets) for outbound use, "frozen" coach states for specific contexts.

**Requirements:**
- **Export Modes:**
  - **Full Persona:** Complete ReDNA snapshot with all traits (uses Phase 1 v1 Persona Snapshot infrastructure)
  - **Contextual Persona:** Subset of traits relevant to specific context (e.g., "Work Persona" = CareerDNA + relevant PsyDNA like Conscientiousness, Assertiveness)
  - **Public Persona:** Only Public/Personal traits (Sensitive/Protected excluded per Phase 5.2 sensitivity gating)

- **Frozen Coach States:**
  - Attach CReDNA snapshot to exported persona (from v1 CReDNA Beta)
  - Coach behavior frozen at export timestamp (no learning/adaptation post-export)
  - Optional: generate static chatbot from frozen state for external use (stub implementation, requires third-party chatbot platform integration)

- **Use Cases:**
  - **Job Applications:** Export CareerDNA + relevant PsyDNA as "professional profile" (JSON + PDF resume supplement)
  - **Dating Profiles:** Export RelationshipDNA + curated PsyDNA (JSON + human-readable summary)
  - **Legacy Preservation:** Freeze complete persona for posterity (linked to Phase 5.1 Deceased Protocol heir inheritance)

**Acceptance Criteria:**
- User can export Full/Contextual/Public personas via Settings → Persona Maker (UI with export mode selector)
- Exported personas include ReDNA + CReDNA snapshot (verified via JSON schema validation)
- Frozen coach states do not adapt or learn post-export (tested by loading frozen state and verifying no trait updates)
- Export format: JSON with optional PDF summary report (PDF generation via Jinja2 template + WeasyPrint)
- Privacy: Sensitive/Protected traits excluded from Public persona exports (validated via automated privacy audit)

**Deliverables:**
- `core/persona_maker.py` (400+ lines with export mode logic, CReDNA freezing, PDF generation)
- Export workflow UI components:
  - Settings → Persona Maker tab (`web/src/components/persona-maker.tsx`, mode selector + preview + export button)
- Frozen coach state generator (`core/frozen_coach_generator.py`, snapshots CReDNA + disables learning)
- PDF report template (`templates/persona_export_report.html`, Jinja2 + CSS for print styling)
- Design doc: [Persona_Maker_Design.md]

---

#### 6.2 Coach Customization UX
**Status:** 🟡 Not Started | **Priority:** Medium | **Risk:** Low

**Objective:** Design analyst-friendly configuration panel for safely tweaking coach persona behaviors (tone, verbosity, proactivity).

**Requirements:**
- **Customization Options:**
  - **Tone Slider:** Formal (0) ↔ Casual (10), default: 5
  - **Verbosity Slider:** Concise (0) ↔ Detailed (10), default: 5
  - **Proactivity Slider:** Reactive (0) ↔ Proactive (10), maps to autonomy level cap from Phase 1.3 (0-2 → Level 0-1, 3-5 → Level 2, 6-8 → Level 3, 9-10 → Level 4 with consent)
  - **Specialty Focus:** Checkbox list of trait families to prioritize (e.g., Head Coach prioritizes PsyDNA, RC prioritizes RelationshipDNA)

- **Coach-Specific Overrides:**
  - User can customize each coach independently
  - Defaults cascade from global settings (Settings → General → Default Coach Behavior)
  - CReDNA deltas persist per-user customizations (see v1 CReDNA Beta)

- **Safety Guardrails:**
  - Proactivity slider caps at User's maximum autonomy consent level (from Phase 1.3)
  - Tone changes validated against coach voice guidelines (e.g., RC must stay warm, cannot drop below tone=4)
  - Customization history logged for rollback (User can "Reset to Defaults")

- **UI Integration:**
  - Settings → Coach Management → [Select Coach] → Customize tab
  - **Preview Pane:** Shows sample coach responses with current settings (uses synthetic scenario + coach LLM call with customized prompt)
  - **Reset to Defaults** button (reverts all customizations, logs in audit trail)

**Downstream Impact:**
- Phase 5.3 (Manipulation Detection) uses customization settings to adjust detection thresholds (high proactivity → more lenient on repeated nudges)

**Phase 4 Dependencies:**
- Trait Container Expansion (4.4) provides specialty focus options (trait family list)

**Acceptance Criteria:**
- User can adjust tone/verbosity/proactivity for each coach (tested with all personas from v1: Head Coach, RC, Photo Coach, PaDNA, Couples Coach)
- Changes reflected immediately in coach behavior (verified via synthetic conversation test)
- Safety guardrails prevent customizations that violate coach voice guidelines (tested with boundary cases: RC tone=0, proactivity=10 with consent_max=2)
- Customization history logged with rollback capability (tested with rollback workflow)
- Preview pane accurately reflects customization impact (validated via human review of 10+ preview scenarios)

**Deliverables:**
- `web/src/components/coach-customization-panel.tsx` (400+ lines with sliders, checkboxes, preview pane)
- API endpoints:
  - PUT `/coach/customization/{user_id}/{coach_id}` (update settings)
  - GET `/coach/customization/{user_id}/{coach_id}` (query current settings)
  - POST `/coach/customization/{user_id}/{coach_id}/reset` (reset to defaults)
- Coach voice validation logic (`core/coach_voice_validator.py`, checks tone/proactivity bounds per persona)
- Preview pane component (`web/src/components/coach-preview-pane.tsx`, generates sample response with customized settings)
- Design doc: [Coach_Customization_UX.md]

---

#### 6.3 External Integrations (Extensibility Hooks)
**Status:** 🟡 Not Started | **Priority:** Low | **Risk:** Medium

**Objective:** Ship stub connectors for voice/photo ingestion and Slack/Teams/Email outbound delivery, behind feature flags. **New in v2.1:** API versioning and plugin registry for third-party extensibility.

**Requirements:**
- **API Versioning:**
  - All external integration APIs versioned: `/v1/integrations/{connector_type}`
  - Semantic versioning (MAJOR.MINOR.PATCH) with deprecation policy (6-month warning before breaking changes)
  - API docs auto-generated from FastAPI schema (Swagger UI at `/docs/integrations`)

- **Plugin Registry:**
  - Centralized registry for third-party connectors (`data/plugin_registry.yaml`)
  - Schema:
    ```yaml
    plugins:
      - id: "whisper_voice_connector"
        name: "Whisper Voice Transcription"
        type: "inbound"
        version: "1.0.0"
        author: "ReDNA Team"
        description: "Transcribes voice memos using OpenAI Whisper API"
        enabled: false  # feature flag
        config:
          api_key_env_var: "WHISPER_API_KEY"
          rate_limit: 100  # calls per day
    ```
  - Plugins can be enabled/disabled via Settings → Integrations without code changes

- **Inbound Connectors (Stubs):**
  - **Voice:** Transcription pipeline (Whisper API) → text ingestion → trait inference
    - Upload .mp3/.wav → transcribe → parse for trait signals (e.g., sentiment, verbal patterns)
  - **Photo:** OCR + computer vision → metadata extraction → trait inference
    - Upload .jpg/.png → extract text (Tesseract) + objects (YOLO) → infer traits (e.g., hobbies from photo content)
  - **Email:** IMAP connector → content parsing → trait inference
    - Connect Gmail/Outlook → parse email threads → infer communication style, relationship dynamics

- **Outbound Connectors (Stubs):**
  - **Slack/Teams:** Bot integration for coach nudges delivered to workspace channels
    - User authorizes bot → select channel → coach nudges posted as bot messages
  - **Email:** Digest emails with weekly coach insights and micro-action suggestions
    - User subscribes → receive weekly summary (Mailgun/SendGrid integration)
  - **SMS:** Optional text message delivery for time-sensitive nudges (Twilio integration)
    - User opts in + provides phone number → critical nudges sent via SMS

- **Feature Flags:**
  - All connectors disabled by default (`enabled: false` in plugin_registry.yaml)
  - User must explicitly enable each connector via Settings → Integrations → [Select Plugin] → Enable
  - Rate limiting enforced (e.g., max 5 outbound nudges per day per channel)

- **Privacy & Security:**
  - Inbound data encrypted in transit (HTTPS) and at rest (AES-256)
  - Outbound messages respect sensitivity gating (no Protected traits in external channels, see Phase 5.2)
  - User can revoke connector access at any time (Settings → Integrations → [Select Plugin] → Revoke)

**Acceptance Criteria:**
- All connectors ship as stubs with feature flags (tested with enable/disable workflow)
- User can enable/disable connectors via Settings → Integrations (UI tested with all connector types)
- Inbound connectors successfully parse test data and generate trait inferences (tested with synthetic voice/photo/email samples)
- Outbound connectors deliver test messages to configured channels (tested with test Slack/Teams workspaces, test email/SMS)
- Privacy controls prevent Protected trait leakage in external messages (validated via automated privacy audit)
- API versioning enforced (tested with v1 vs. v2 endpoint compatibility)
- Plugin registry supports third-party connectors (tested with custom plugin YAML)

**Deliverables:**
- API versioning infrastructure (`api_versioning.py`, FastAPI router with `/v1/integrations/`)
- Plugin registry (`data/plugin_registry.yaml` + loader `core/plugin_registry_loader.py`)
- Inbound connector stubs:
  - `integrations/voice_connector.py` (200 lines, Whisper API wrapper)
  - `integrations/photo_connector.py` (200 lines, Tesseract + YOLO wrapper)
  - `integrations/email_connector.py` (300 lines, IMAP client + parser)
- Outbound connector stubs:
  - `integrations/slack_teams_connector.py` (250 lines, Slack/Teams bot API wrapper)
  - `integrations/email_digest_connector.py` (200 lines, Mailgun/SendGrid wrapper)
  - `integrations/sms_connector.py` (150 lines, Twilio wrapper)
- Feature flag configuration UI:
  - Settings → Integrations tab (`web/src/components/integrations-settings.tsx`, plugin list + enable/disable toggles)
- API documentation (`docs/External_Integrations_API.md`, generated from FastAPI schema)
- Design doc: [External_Integrations_Design.md]

---

#### 6.4 Cross-Device Polish & Responsive Layouts
**Status:** 🟡 Not Started | **Priority:** Medium | **Risk:** Low

**Objective:** Audit layouts at 600px and 1024px breakpoints; adjust CSS/column layouts for mobile/tablet polish.

**Requirements:**
- **Breakpoint Audit:**
  - **Mobile (375px - 600px):** Single-column layout, collapsible menus, touch-optimized controls
  - **Tablet (600px - 1024px):** Two-column layout, side navigation, reduced whitespace
  - **Desktop (1024px+):** Current layout preserved (no changes)

- **Priority Pages:**
  - Head Coach chat interface (most critical for mobile UX)
  - Transcript panel (scrolling, message rendering)
  - Settings → Coach Management (customization sliders, consent toggles)
  - Dev Explorer → Observability dashboards (charts, tables)

- **Touch Optimization:**
  - Increase button/link hit targets to 44×44px minimum (WCAG 2.1 AA standard)
  - Replace hover interactions with tap/long-press (e.g., trait viewer tooltips → tap to reveal)
  - Swipe gestures for navigation:
    - Swipe left on transcript → open coach switcher
    - Swipe right on coach switcher → return to transcript
    - Swipe down on chat → refresh/load more messages

- **Performance:**
  - Lazy load non-critical components on mobile (e.g., Dev Explorer charts load on scroll)
  - Optimize image assets for smaller screens (WebP format, responsive srcset)
  - Target: <3s initial load on 4G connection (measured via Lighthouse Mobile)

**Measurement Methods:**
- **Responsiveness:** Manual testing at 375px, 600px, 1024px viewports (Chrome DevTools device emulation)
- **Touch Targets:** Automated audit via accessibility scanner (target: 100% of interactive elements ≥44×44px)
- **Performance:** Lighthouse Mobile score (target: >90 for Performance, Accessibility, Best Practices)

**Acceptance Criteria:**
- All priority pages render correctly at 375px, 600px, 1024px breakpoints (tested on real devices: iPhone 12, iPad Air, MacBook Pro)
- Touch targets meet 44×44px minimum on mobile (verified via accessibility audit)
- Swipe gestures functional for coach switcher and transcript navigation (tested on iOS Safari, Android Chrome)
- Initial load time <3s on 4G (validated via Lighthouse Mobile with throttling)
- User testing confirms smooth mobile/tablet experience (5+ testers, <10% report usability issues)

**Deliverables:**
- Responsive CSS updates:
  - `web/src/styles/responsive.css` (500+ lines with media queries for 375px, 600px, 1024px)
  - Component-specific responsive styles (e.g., `transcript-panel-mobile.css`, `coach-switcher-mobile.css`)
- Touch gesture handlers:
  - `web/src/utils/touch-gestures.ts` (200+ lines with swipe detection, touch target helpers)
- Mobile-optimized component variants:
  - `web/src/components/transcript-panel-mobile.tsx` (simplified message rendering)
  - `web/src/components/coach-switcher-mobile.tsx` (drawer-style overlay)
- Lighthouse performance report (`docs/Lighthouse_Mobile_Report.pdf`)
- Design doc: [Cross_Device_Responsive_Design.md]

---

## 🧠 CReDNA Enhancements (v2.1)

### CReDNA Roadmap
- ✅ **Achieved in v1:**
  - Trait graph, coverage tracking, live snapshot, import/export
  - `WRITE_PROTECT` save guard, template preferences
  - Status strip integration in Head Coach Preview

- 🟡 **v2.1 Additions:**
  - **Coverage Badges:** Visual indicators in status strip (e.g., "CReDNA Coverage: 78%") → integrated into Head Coach Preview UI
  - **Diff Previews:** Before/after comparison when applying CReDNA imports → new UI component in Dev Explorer → CReDNA Inspector
  - **Validation Heuristics:** Strengthen import validation (detect incompatible playbooks, conflicting heuristics) → new validation module `core/credna_validator.py`
  - **Automated Tests:** Expand test coverage to 50+ test cases for CReDNA ops (import/export/rollback workflows)
  - **RSC Integration:** Track cross-coach collaboration patterns in CReDNA (which coaches collaborate most effectively?) → new analytics in RSC Observatory (Phase 3.3)

**CReDNA + RSC Synergy:**
- Couples Coach CReDNA captures successful RSC collaboration patterns (e.g., "User A's RC + User B's RC → 80% nudge acceptance when using playbook X")
- Dev Explorer CReDNA Inspector surfaces RSC-driven CReDNA deltas for system-wide propagation
- Phase 6.2 Coach Customization integrates CReDNA templates (User can select "RSC-optimized Couples Coach template")

---

## 📝 Progress Tracker (v2.1 Launch: 2025-10-06)

### Recently Completed (v1 Final Deliveries)
- ✅ Project structure cleanup, legacy code archival
- ✅ Developer Explorer rework (7 focused modules, Observability + Governance tabs)
- ✅ Analytics dashboards (Coach, Curiosity, Ops Compliance, System Health)
- ✅ RC voice enhancement (warm confidant persona with 260+ line prompt)
- ✅ Plan Composer (rule-based 3-step game plans <50ms)
- ✅ Persona Snapshot Export (timestamped PaDNA bundles)
- ✅ Telemetry consolidation, feedback analytics, testing automation

### Active Development (v2.1 Phase 1 — Months 1-2)
- 🟡 **Relationship Graph & Schema** (multi-user substrate with nested contexts, unique IDs per relationship type)
- 🟡 **Provenance Firewall** (internal attribution vs. RSC-visible abstractions, Bayesian confidence scoring)
- 🟡 **Coach Autonomy Framework** (dynamic scaling tied to RR/trust with formula: `autonomy = min(floor(RR*3 + trust*2), user_cap)`)
- 🟡 **Lightweight Holistic Review Hook** (cross-User pattern detection PoC with meta-trait outputs)

### Upcoming (v2.1 Phase 2 — Months 2-4)
- 🟡 Cross-Coach Communication Protocol (YAML camouflage patterns with 5+ tone variants)
- 🟡 Consent Guardian Service (dual consent + shadow relationship mode + Consent Status Timeline object)
- 🟡 Head Coach Governance Layer (pre-execution digests, approval queue, risk scoring formula)
- 🟡 Breakup / Revocation Protocol (30-day data decay with email notifications on Day 0/15/30)

### Future Milestones (v2.1 Phase 3-6 — Months 4-12)
- 🟡 **Couples Coach MVP** (dyadic relationship dynamics persona with 50+ micro-actions, bias detection, DV risk assessment)
- 🟡 **Two-User RSC Proof of Concept** (**official milestone**: provenance integrity 100%, correlation resistance >95%, latency <5s)
- 🟡 **RSC Observatory** (Dev Mode dashboard with relationship graph viewer, signal flow diagram, exportable audit bundles)
- 🟡 **Trait Inference Engine v2** (Bayesian update loops, cross-trait correlation, uncertainty quantification, 15% accuracy improvement vs. v1)
- 🟡 **Contradiction & Tension Framework** (formal tension markers, HC probing integration, tension decay formula)
- 🟡 **Enhanced Curiosity Engine** (decay/rebound/tension amplifiers, family weights: PsyDNA 1.5×, MetaDNA 1.3×, RelationshipDNA 1.2×)
- 🟡 **Trait Container Expansion** (50+ new containers: HEXACO sub-facets, attachment styles, love languages, work values)
- 🟡 **Dormancy & Deceased Protocols** (3/6/12-month states, heir transfer with 30-day grace period, RR exclusion)
- 🟡 **Sensitive DNA Gating** (grayed previews with lock icons, consent prompts at RR>0.7, coach constraint validation)
- 🟡 **Manipulation Detection & Penalties** (4-tier penalty system: warning → autonomy reduction → suspension → permanent disable)
- 🟡 **Privacy Red-Team Utility** (continuous CI/CD integration with timing/linguistic/sentiment/topic correlation tests)
- 🟡 **Persona Maker** (static DNA export with Full/Contextual/Public modes, frozen CReDNA states, PDF reports)
- 🟡 **Coach Customization UX** (tone/verbosity/proactivity sliders, specialty focus checkboxes, preview pane, safety guardrails)
- 🟡 **External Integrations** (API versioning, plugin registry, voice/photo/email inbound, Slack/Teams/Email/SMS outbound stubs)
- 🟡 **Cross-Device Polish** (responsive layouts at 375px/600px/1024px, touch optimization, swipe gestures, <3s mobile load)

---

## 🎯 Strategic Priorities (v2.1 Focus)

1. **RSC Foundation (Critical Path):** Relationship graph → Provenance firewall → Autonomy framework must ship together as cohesive substrate before any RSC collaboration
2. **Privacy First:** Every RSC component must pass red-team correlation tests (timing r<0.3, linguistic sim<0.2, sentiment diff>0.3) before User Mode deployment
3. **Ethical Oversight:** Consent Guardian + Head Coach Governance operational before any RSC collaboration goes live (hard requirement, no exceptions)
4. **Trait Intelligence:** Inference engine, curiosity engine, contradiction framework must deliver **measurably better UCN/RR accuracy** (target: **15% RMSE improvement** vs. v1 baseline, measured on held-out test set)
5. **Developer Velocity:** RSC Observatory essential for debugging and validating privacy properties during development (Phase 3.3 unblocks Phase 4+ development)

---

## 🔬 Success Metrics (v2.1 Goals)

### Technical Performance
- **RSC Latency:** End-to-end signal exchange <5s (median + p95 measured across 100 test runs with 50ms RTT network simulation)
- **Provenance Firewall Integrity:** 100% (automated scan of User Mode UI/API responses detects zero leaks)
- **Camouflage Correlation Resistance:** >95% confidence (red-team utility correlation confidence <15%, measured via timing r<0.3 + linguistic sim<0.2 + sentiment diff>0.3 + topic leak=0%)
- **Trait Inference Accuracy:** 15% improvement in RMSE vs. v1 baseline (measured on held-out synthetic test set with 100+ Users, 50+ traits)
- **Privacy Health Score:** >85% aggregate camouflage effectiveness (1 - max(timing_r, linguistic_sim, sentiment_inverse, topic_leak_rate))

### User Experience
- **Couples Coach Satisfaction:** >80% positive feedback on RSC-driven insights (post-MVP launch survey, N≥50 Users)
- **Autonomy Trust:** <5% of Users manually cap autonomy below system-recommended level (tracked via Settings analytics)
- **Sensitivity Gating Acceptance:** >90% consent rate when threshold reached for Sensitive traits (measured via consent prompt analytics)
- **Cross-Device Polish:** <3s initial load on mobile 4G (Lighthouse Mobile score with throttling), Lighthouse score >90 (Performance, Accessibility, Best Practices)

### Governance & Ethics
- **Manipulation Detection Accuracy:** >85% true positive rate, <5% false positive rate (measured on labeled synthetic dataset: 50 manipulative + 50 non-manipulative conversations)
- **Consent Compliance:** 100% (automated tests verify zero RSC collaboration without dual consent, tested with 1000+ consent violation scenarios)
- **Audit Completeness:** 100% of RSC events (signal exchange, consent, revocation) logged with full provenance (verified via audit log coverage report)
- **Privacy Stress Tests:** Pass 100% of quarterly red-team correlation tests (timing/linguistic/sentiment/topic tests run on past 90 days of RSC activity)

---

## 🚨 Risk Mitigation

### High-Risk Areas
1. **Provenance Firewall Failure:** If camouflage leaks source attribution, entire RSC model collapses
   - **Mitigation:** Continuous red-team testing in CI/CD (Phase 5.4), fail-safe blocks RSC exchange if camouflage confidence <0.85, weekly privacy health reports to governance team
2. **Consent Violations:** Accidental RSC collaboration without dual consent damages trust irreparably
   - **Mitigation:** Pre-execution consent validation (Phase 2.2), automated consent violation tests (1000+ scenarios), audit alerts on consent failures, User emergency stop button
3. **Manipulation Undetected:** Coach coercion goes unnoticed, User feels manipulated
   - **Mitigation:** User feedback loop (Phase 5.3), pattern matching on 4 manipulation types, transparency (User sees all penalties in Settings), User override capability
4. **Performance Degradation:** RSC overhead slows system below acceptable latency (<5s)
   - **Mitigation:** Async signal processing (Phase 2.1), caching of camouflage templates, load testing (100+ concurrent signals), p95 latency monitoring in RSC Observatory

### Medium-Risk Areas
1. **Autonomy Over-Scaling:** Coach autonomy increases too aggressively, surprises User
   - **Mitigation:** Conservative scaling formula (Phase 1.3), User override controls (manual cap in Settings), autonomy change notifications, automatic reduction if feedback drops <0.6
2. **Relationship Graph Complexity:** Multi-context relationships (couple + colleagues) confuse data model
   - **Mitigation:** Unique relationship_id per context (Phase 1.1), thorough testing with 20+ relationship collision scenarios, documentation with ER diagrams
3. **Trait Inference Errors:** Cross-trait correlation models produce spurious inferences
   - **Mitigation:** Confidence thresholds (only use correlations with r>0.5, p<0.01), human-in-the-loop validation (Dev Mode tension markers for manual review), rollback capability
4. **CReDNA Compatibility:** Imported playbooks conflict with existing coach behavior
   - **Mitigation:** Diff previews before import (v2.1 CReDNA enhancement), validation heuristics (detect conflicts), rollback on import failure, user testing with 10+ import scenarios

---

## 📚 Documentation Deliverables (v2.1)

### Architecture & Design Docs (Phase-by-Phase)
**Phase 1:**
- Relationship_Graph_Design.md (ER diagrams, schema, collision handling)
- Provenance_Firewall_Design.md (internal vs. RSC layers, camouflage translation pipeline)
- Coach_Autonomy_Design.md (autonomy formula, scaling curves, governance integration)
- Holistic_Multi_User_Design.md (pattern detection, meta-trait outputs, privacy validation)

**Phase 2:**
- RSC_Protocol_Design.md (signal types, YAML templates, tone variant mapping)
- Consent_Guardian_Design.md (dual consent workflow, shadow mode, Consent Status Timeline)
- Head_Coach_Governance_Design.md (risk scoring formula, approval queue, digest format)
- Revocation_Protocol_Design.md (30-day decay timeline, purge logic, tombstone archiving)

**Phase 3:**
- Couples_Coach_Design.md (voice guidelines, micro-actions, bias detection, DV risk assessment)
- RSC_Observatory_Design.md (UI components, privacy health score, audit bundles, red-team integration)

**Phase 4:**
- Trait_Inference_Engine_v2.md (Bayesian update loops, correlation models, uncertainty quantification)
- Contradiction_Tension_Framework.md (detection logic, tension scoring, HC probing integration)
- Curiosity_Engine_v2.md (decay/rebound formulas, family weights, tension amplifier)
- Trait_Container_Expansion.md (50+ new traits, HEXACO/attachment/love languages mapping)

**Phase 5:**
- Dormancy_Deceased_Protocols.md (state machine, heir transfer workflow, RR exclusion rules)
- Sensitive_DNA_Gating.md (threshold logic, consent prompts, coach constraint validation)
- Manipulation_Detection_Penalties.md (4-tier penalty system, detection patterns, user override)
- Privacy_RedTeam_Utility.md (correlation tests, CI/CD integration, threat model updates)
- Privacy_Threat_Model.md (catalog of attacks: timing/linguistic/sentiment/topic, mitigations)

**Phase 6:**
- Persona_Maker_Design.md (export modes, frozen CReDNA, PDF generation, use cases)
- Coach_Customization_UX.md (sliders/checkboxes, preview pane, voice validation, CReDNA integration)
- External_Integrations_Design.md (API versioning, plugin registry, connector stubs, privacy controls)
- Cross_Device_Responsive_Design.md (breakpoint audit, touch optimization, performance budget)

### Milestone Reports
- **RSC_Proof_of_Concept.md** (Phase 3.2 deliverable): Design, test results (provenance integrity, correlation resistance, latency), lessons learned, demo video
- **Trait_Intelligence_Baseline_Comparison.md** (Phase 4 deliverable): RMSE comparison (v1 vs. v2), confidence calibration plots, game plan acceptance rates
- **Privacy_Health_Quarterly_Report.md** (ongoing from Phase 5.4): Aggregate camouflage effectiveness, red-team test results, failed attacks summary, mitigation updates

### User Guides
- **RSC_User_Guide.md** (Phase 3 deliverable): How RSC works, consent model (dual/shadow), privacy guarantees, relationship management, FAQ
- **Coach_Customization_Guide.md** (Phase 6.2 deliverable): How to tweak persona behaviors (tone/verbosity/proactivity), specialty focus, preview pane usage, reset to defaults
- **Persona_Maker_User_Guide.md** (Phase 6.1 deliverable): Exporting static DNAs (Full/Contextual/Public), use cases (job applications, dating profiles), frozen coach states

### API Documentation
- **External_Integrations_API.md** (Phase 6.3 deliverable): API versioning policy, plugin registry schema, connector endpoints (`/v1/integrations/{connector}`), rate limits, authentication

---

## 🎓 Lessons from v1 → v2.1

1. **Start with Infrastructure:** v1 succeeded because we built Dev Explorer, testing automation, and telemetry consolidation early. v2.1 continues this: relationship graph + provenance firewall + autonomy framework before any RSC features.
2. **Privacy Cannot Be Bolted On:** Camouflaging and red-team testing must be baked into RSC protocol from day one, not added later. Continuous CI/CD privacy tests (Phase 5.4) are non-negotiable.
3. **Governance Is a Feature:** Consent Guardian and Head Coach approval aren't bureaucratic overhead — they're trust-building features that differentiate ReDNA from "black box" AI systems.
4. **Phasing Prevents Scope Creep:** v1's six-phase roadmap kept us focused. v2.1 extends this discipline: each phase has clear entry/exit criteria, dependencies, and acceptance criteria.
5. **Documentation as Design Tool:** Writing design docs before coding clarifies requirements and surfaces edge cases early (e.g., relationship graph collision scenarios, provenance firewall translation edge cases).
6. **Measurement Matters:** v2.1 adds explicit measurement methods for all success metrics. "Improve inference accuracy" becomes "15% RMSE reduction on held-out test set" — makes quarterly reviews reproducible.
7. **Cross-Phase Linkages Prevent Duplicative Work:** Explicitly documenting dependencies (e.g., Phase 3.1 Couples Coach depends on Phase 2.1 RSC Protocol) prevents engineers from building redundant scaffolding.
8. **Bayesian Thinking = Principled Uncertainty:** v2.1's Bayesian inference hooks (Phase 4.1) replace v1's simple averaging with probabilistic updates that properly handle conflicting evidence and uncertainty quantification.

---

## 🛤️ Beyond v2.1: Interactive & Impact Tiers

### DNA Ontology Expansion (Phase 4 Foundation)
**Status:** ✅ Phase A Complete (422 containers) | **Next:** Phase B (10k containers)

**Phase A Achievements (2025-10-06):**
- ✅ 422 DNA containers across 18 namespaces (PaDNA, PsyDNA, EmDNA, CogDNA, etc.)
- ✅ Complete validation infrastructure (0 errors, 8 validation categories)
- ✅ Graph storage (358 edges in JSONL format)
- ✅ RR-integrated curiosity engine (tested with live user data)
- ✅ 6 REST API endpoints (ontology access + curiosity agendas)
- ✅ Comprehensive documentation ([CONTAINER_EXPLOSION_INDEX.md], [PHASE_A_COMPLETION.md])

**Phase B Roadmap (10,000 containers, 1-2 weeks):**
- **AI Shadow Proposal System:** Policy gate framework with safety checks, confidence thresholds, human approval workflow
- **Cross-Product Generation:** Cartesian expansions (Color × Shade, Texture × Pattern) for granular trait coverage
- **Statistical Correlation Inference:** Auto-discover `correlates_with` edges from population data (e.g., HairColor ↔ SkinTone, r=0.68)
- **Ontology Explorer UI:** Tree view with expand/collapse, search/filtering, curiosity heat map visualization
- **Performance Optimization:** <200ms load time for 10k containers, lazy loading, database backend consideration

**Phase C-D Roadmap (100k → 1M containers, 3-8 weeks):**
- **Phase C (100k):** Auto-expansion from user feedback, residual variance catchers, PostgreSQL backend
- **Phase D (1M):** Federated ontology, AI-native discovery via LLM, real-time streaming updates, graph database (Neo4j)

**Impact on Other Phases:**
- **Phase 4.1 (Trait Inference v2):** Ontology provides structured relationships for correlation discovery
- **Phase 4.3 (Curiosity Engine v2):** Missing containers from ontology drive exploration agendas
- **Interactive Standard:** Multi-user dynamics benefit from shared ontology (e.g., couple's RelationshipDNA containers)
- **Impact Standard:** Population insights require stable container definitions for longitudinal tracking

**Key Innovation:** **Curiosity Economy** — Ontology integrates with RR system (`Curiosity = 100 - RR`) to systematically identify knowledge gaps and prioritize data collection. High-curiosity containers (low RR) get AI coach attention, driving iterative refinement toward comprehensive DNA profiles.

**Documentation References:**
- Architecture: `docs/ONTOLOGY_OVERVIEW.md`
- Completion Report: `docs/PHASE_A_COMPLETION.md`
- Master Index: `docs/CONTAINER_EXPLOSION_INDEX.md`
- Code: `core/ontology/`, `core/validation/`, `core/generation/`, `core/curiosity/`

---

### Interactive Standard (Post-v2.1)
- **Multi-User Group Dynamics:** Family systems coaching (parent-child, sibling dynamics), team coaching (manager-report, peer collaboration)
- **Real-Time Collaboration:** Simultaneous coach sessions for couples (joint session with Couples Coach mediating live conversation)
- **Voice/Video Modalities:** Embodied coach presence (avatar layer from v1 future roadmap, TTS/STT integration, video chat with coach avatar)
- **External Ecosystem Integrations:** Third-party apps (calendar sync for scheduling nudges), wearables (sleep/activity data → PhysicalDNA updates)

### Impact Standard (Long-Term Vision)
- **Population-Level Insights:** Aggregate patterns across ReDNA community (e.g., "Users with secure attachment + high empathy show 40% higher relationship satisfaction")
- **Predictive Life Coaching:** Anticipate User needs before explicit request (e.g., detect early signs of burnout, proactively suggest stress management micro-actions)
- **Generational Inheritance:** Multi-decade ReDNA evolution (track User's trait changes from age 20 to 60, inform coaching strategies)
- **Societal Impact Measurement:** Track community well-being metrics (aggregate happiness, relationship health, career satisfaction) to assess ReDNA's population-level impact

### Black Mirror Tier (Aspirational, Ethical Boundary Exploration)
- **Fully Autonomous Coach Networks:** Level 5 autonomy (coaches execute complex RSC schemes with minimal human oversight, HC approval only for ethical edge cases)
- **Cross-Generational DNA Transfer:** Grandparent ReDNA informing grandchild coaching (e.g., "Your grandfather valued autonomy highly; let's explore if that resonates with you")
- **Synthetic Personality Reconstruction:** Recreate historical figures as coaches (e.g., "Socratic Coach" trained on Plato's dialogues) for philosophical guidance
- **Ethical Boundary Exploration:** Research questions: What should AI coaches never do? When does autonomy become surveillance? How do we prevent ReDNA from reinforcing societal biases?

---

## 📊 Quarterly Review Process (v2.1 Governance)

### Monthly Progress Reviews
- **First Monday of each month:** Engineering team reviews progress against roadmap
- **Metrics Dashboard:** Track phase completion %, acceptance criteria pass rate, blocker count
- **Adjustments:** Scope adjustments if blockers persist >2 weeks, re-prioritization if dependencies shift

### Quarterly Success Metric Audits
- **Weeks 12, 24, 36 of roadmap:** Governance team audits success metrics against targets
- **Technical Performance:** RSC latency, provenance integrity, camouflage correlation resistance, trait inference accuracy, privacy health score
- **User Experience:** Couples Coach satisfaction, autonomy trust, sensitivity gating acceptance, cross-device polish
- **Governance & Ethics:** Manipulation detection accuracy, consent compliance, audit completeness, privacy stress test pass rate
- **Report:** Quarterly summary (JSON + PDF) published to Dev Mode → Governance tab, shared with stakeholders

### Annual Ladder Advancement Review
- **Month 12:** Assess ReDNA Standards Ladder progression (Functional → Applied → Adaptive → Interactive → Impact)
- **Criteria:**
  - **Applied Standard:** All Phase 1-2 benchmarks complete + RSC Proof of Concept validated
  - **Adaptive Standard:** All Phase 3-4 benchmarks complete + 15% trait inference improvement achieved
  - **Interactive Standard:** Phase 5-6 complete + multi-user group dynamics operational
  - **Impact Standard:** Population-level insights + predictive coaching operational
- **Outcome:** Formal advancement declaration, updated roadmap for next tier

---

**End of Core Benchmarks Roadmap v2.1 — Operational Baseline**

_This document supersedes Core_Benchmarks_Roadmap_v2.md and becomes the canonical operative roadmap as of 2025-10-06. All development work must align with this roadmap. Monthly progress reviews and quarterly success metric audits enforce accountability and adaptability._

---

## 📌 Pending Integration: Final Addendum

**IMPORTANT:** The following refinements from `Core_Benchmarks_Roadmap_v2.1_Final_Addendum.md` are approved but not yet integrated into this document:

1. **Provenance Chain Narrative** - Insert in Phase 4.1 (Trait Inference) after Bayesian formula
2. **Meta-Trait Retention & Decay Rules** - Insert in Phase 1.4 (Holistic Review) after meta-trait schema
3. **Quarterly Audit Output Format** - Replace existing quarterly audit text in "Quarterly Review Process" section
4. **Black-Mirror Horizon Measurable Conditions** - Insert after "Black Mirror Tier" description in "Beyond v2.1" section
5. **Annual External Ethics Review** - Insert as new benchmark 5.5 after Phase 5.4

**Action Required:** Integrate these 5 refinements before locking v2.1-Final. See `Core_Benchmarks_Roadmap_v2.1_Final_Addendum.md` for complete text and integration instructions.

**Once integrated:**
- Rename file to: `Core_Benchmarks_Roadmap_v2.1-Final.md`
- Add header: `_Status: **LOCKED OPERATIONAL BASELINE** | Effective: 2025-10-06_`

---

## 🔗 Quick Reference Links

### Phase Navigation
- [Phase 0: Coach Workshop Modernization](#phase-0--coach-workshop-modernization-weeks-1-6) ← **NEW: Design complete, implementation ready**
- [Phase 1: RSC Foundation Infrastructure](#phase-1--rsc-foundation-infrastructure-months-1-2)
- [Phase 2: RSC Collaboration Protocols](#phase-2--rsc-collaboration-protocols-months-2-4)
- [Phase 3: Couples Coach MVP](#phase-3--couples-coach-mv-months-4-6)
- [Phase 4: Core Logic & Trait Resolution](#phase-4--core-logic--trait-resolution-months-5-7)
- [Phase 5: Governance & Ethical Safeguards](#phase-5--governance--ethical-safeguards-months-6-8)
- [Phase 6: Ecosystem & Extensibility](#phase-6--ecosystem--extensibility-months-8-12)

### Key Milestones
- [Two-User RSC Proof of Concept (Phase 3.2)](#32-two-user-rsc-proof-of-concept) ← **Official RSC PoC Milestone**
- [Trait Inference Engine v2 (Phase 4.1)](#41-trait-inference-engine-upgrade) ← 15% accuracy improvement target
- [Privacy Red-Team Utility (Phase 5.4)](#54-privacy-red-team-utility-continuous) ← Continuous CI/CD integration

### Success Metrics
- [Technical Performance Metrics](#technical-performance)
- [User Experience Metrics](#user-experience)
- [Governance & Ethics Metrics](#governance--ethics)

### Documentation
- [Architecture & Design Docs](#architecture--design-docs-phase-by-phase)
- [Milestone Reports](#milestone-reports)
- [User Guides](#user-guides)
- [API Documentation](#api-documentation)
