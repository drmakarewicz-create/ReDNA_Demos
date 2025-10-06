# Core Benchmarks Roadmap

_Last updated: 2025-10-04_

## 🎯 Vision (guiding principles)

ReDNA builds **living digital approximations** of users (DNAs) that evolve over time. The **Head Coach** orchestrates everything: Explorer is the shell; Core/UCN/RR detect & rank; coaches act. **Curiosity** (inverse of RR, normalized per DNA family) drives agendas; **contradictions** can persist as tension until the Head Coach probes. We keep **provenance**, log attempts (even failed ones), and honor **governance** (dormancy/deceased protocols, sensitive DNA gating, manipulation penalties). Users can **redirect** and give **feedback** that shapes future plans. Over time, coaches develop **CReDNA** (coach-level playbooks) with strict versioning and rollback.

## ✅ Current Core Benchmarks
1. Delete/move unnecessary folders/files in Demo Root
   - **Status:** ✅ **COMPLETE**
   - Cleaned up project structure: 23 .md files → `docs/historical/`, 13 test files → `tests/`, 4 utilities → `scripts/`, 11 legacy services → `archive/legacy_services/`, 2 old backups → `archive/old_versions/`
   - Root now contains only README.md, control_panel_plus_plus.py, and active directories
   - Created comprehensive "Where to Find What" guide for navigation
2. Consolidate Explorer, Onboarding, Photo Coach, and PaDNA Renderer into Head Coach  
   - Use Head Coach as the shell.  
   - Other coaches become personas within it.  
   - Legacy tabs only remain until transition is complete.
3. Develop seamless method to add new lower coaches to Head Coach’s arsenal of personas  
   - Persona-switching should feel natural (chat-driven or button-driven).  
   - UI and “voice” of each persona distinct but always powered by Head Coach.
4. Add Relationship Coach  
   - First new lower coach persona beyond the existing set.  
   - Tailored dialogue style and data pipeline integration.
5. Add RSC capability for two coaches from different users to collaborate  
   - Multi-user, coach-to-coach interaction.
6. Stand up Developer Explorer shell  
   - **Status:** ✅ ORS console (service ping, log tailer, trace explorer) is live inside Diagnostics.  
   - Keeps production Explorer focused on end-user persona experience.  
   - **Next:** Optional “Diff Snapshots” stretch tooling for power users.
7. Testing & Automation  
   - Automated smoke/unit coverage for `nudge_store`, RR baseline utilities, and CReDNA ops.  
   - Golden-path regression script (enqueue → accept → undo → Draft Chat).  
   - Keep this in place before demos where `WRITE_PROTECT=false`.

## 🚀 Medium-Term Priorities
8. Strong camouflaging function and protocols for RSC coaches  
   - Ensure safe interaction without data leakage.  
   - Obfuscation/camouflage layers for sensitive contexts.
9. Increase number of empty containers in Core for DNAs/traits  
   - Expand trait coverage and storage capacity.  
   - Enable more granular PaDNA inputs.
10. Improve inference quality
    - Explorer/UCN/RR/Core should make wider inferences, more accurate UCN/RR/Curiosity numbers, and stronger game plans.
    - ORS tracing + retries shipped; ✅ **Plan Composer complete**: Generates 3-step game plans from top curiosity deltas with rule-based approach, persistent storage, API endpoints, and example code.
11. Persona snapshots
   - **Status:** ✅ **COMPLETE**
   - Export pipeline that freezes user's PaDNA into timestamped JSON bundles.
   - Supports full or partial exports (by trait family), snapshot history, version tagging.
   - Delivered: Core module (`snapshot_exporter.py`), FastAPI endpoints (`api_snapshots.py`), example code, comprehensive design doc.
   - Storage: `data/users/{user_id}/snapshots/` with index-based metadata.
   - Future: UI integration in Explorer for export/list/download/delete actions.
12. Improve Core file consolidation and hygiene
   - Handle duplicate users gracefully.
   - Merge or differentiate DNAs across multiple files.
13. Build strong identification component
    - Use multiple ReDNA traits to uniquely identify a user.
    - Improve disambiguation and matching.
14. Security / Audit for Ops
    - Encrypt logs at rest, add change-history viewers for Head Coach Ops, RR Baselines, CReDNA imports, and document rollback paths (includes Dev Ops audit & guardrails).
15. Telemetry Consolidation
    - Stitch ORS span logs (Dev Explorer / UCN/RR / Core) into a single trace viewer or lightweight ingest to avoid manual diffing.
16. Feedback Loop Capture
    - Collect "helpful / not helpful / add note" feedback on nudges, store in feedback log, and add hooks so Head Coach planning can down-weight unhelpful paths.
17. Data Governance / Privacy Controls
    - Provenance tagging, consent flags for sensitive traits, and access-control rules for ReDNA/CReDNA edits.
18. Analytics Dashboards
    - **Status:** ✅ **COMPLETE**
    - Dashboards for coach switch frequency, curiosity coverage %, Ops schedule compliance with CSV/JSON export.
    - Delivered: Coach Analytics (switch frequency, engagement, session duration), Curiosity Coverage (coverage %, gaps, heatmap), Ops Compliance (schedule adherence, success rates), System Health (uptime, latency, error rates, storage).
    - Location: Dev Explorer → Analytics tab

## 🌐 Future Goals
19. Persona Maker
    - Create static versions of one's ReDNA (or subsets) for outbound use.
    - "Frozen" coach states for specific contexts.
20. Coach customization options  
    - Smooth, comfortable conversation tuned to user preferences.  
    - Ability to feed coaches external articles/information.  
    - Infuse ReDNA traits to shape style.
21. Self-improvement loop
    - System learns from new external data.  
    - Coaches improve over time with user interaction and feedback.
22. Cross-device Explorer access
    - PCs, smartphones, tablets.  
    - Audit layouts at 600 px and 1024 px breakpoints; adjust CSS/column layouts for mobile/tablet polish.
23. Golden Path Demo Kit
    - Script that seeds demo users, runs loop test, enqueues a nudge, accepts it, and showcases Draft Chat—ensures demo safety pre-presentation.
24. External Integrations (Extensibility Hooks)  
    - Future connectors for voice/photo ingestion, Slack/Teams/Email outbound delivery.  
    - Ship as stubs behind flags.

### Future Roadmap Items (Planned)
25. Avatar Layer for Coaches *(Planned — future implementation)*  
    - **Goal:** provide an `AvatarLayer` that listens to speaking/streaming/sentiment/dialog_act/status signals and mirrors coach state with lightweight visuals to lift moment-to-moment engagement.  
    - **Description:** tiered delivery starting with **Tier 1 (MVP)** Lottie/SVG avatars (idle/speaking/think/error loops plus persona palettes/accessories), expanding in **Tier 2** to optional mouth-synced sprite animations paired with TTS, and exploring **Tier 3** WebGL/3D avatars with blendshape-driven lipsync and richer emotion mapping.  
    - **Why important:** adds demo "wow factor," reinforces each coach’s identity, and keeps the shell approachable without reworking chat mechanics.  
    - **Governance & config:** CP++ global toggle plus per-coach enable/style selectors, collapsible presentation that respects compact density, animation pause when the tab is hidden, assets kept lightweight, no data leaves the browser, and TTS strictly opt-in with consent logging.  
    - **Risks:** performance regressions on low-end devices, UI clutter if collapse/placement is mishandled, and dependency on provider integrations for high-quality TTS/animation pipelines.
26. Personality Test Coach (PTC) *(Planned — future implementation)*  
    - **Goal:** launch a specialised coach that delivers adaptive personality assessments (inspired by MBTI, Big Five, DISC, HEXACO) tuned for ReDNA container coverage while giving users meaningful insights.  
    - **Description:** profile existing assessments (rationale/objectives/results), author modified question banks that avoid licensing conflicts, and deliver dynamic multi-modal experiences (text prompts, sliders, quick-choice, scenario branches) with adaptive routing to capture rich signals.  
    - **Data outputs:** persist trait inferences with provenance into Core containers, generate user-facing summary reports, and optionally mint a ReDNA Cast/avatar snapshot derived from test outcomes.  
    - **Governance & UX:** honour consent and sensitivity flags per question, log provenance for every inference/response, gate sensitive traits, and design pacing that avoids fatigue while maintaining engagement.  
    - **Why important:** fills containers with structured, high-quality data, offers tangible self-knowledge, and bridges familiar assessments with ReDNA’s commodity model.  
    - **Risks:** intellectual property boundaries when adapting third-party instruments, handling sensitive psychological data responsibly, and ensuring the experience feels polished enough to prevent drop-off.
27. Identity & Access Management
    - User-level access control: who can view/edit another user's ReDNA or CReDNA.
    - Required for safe multi-user demos beyond identification.

## 🧠 CReDNA (Coach ReDNA) — Beta
- Trait graph, coverage, live snapshot, import/export with `WRITE_PROTECT` save guard, and template preference in Head Coach Preview are live.
- Next steps: add coverage badges to the status strip, surface diff previews when applying imports, strengthen validation heuristics, and expand automated tests.
- CReDNA tracks each coach’s per-user behavior model across tone, playbooks, heuristics, knowledge shards, and safety constraints.
- User uploads, outcomes, and explicit feedback translate into scoped CReDNA deltas that immediately affect the requesting user’s coach.
- Dev Explorer surfaces these deltas for review and optional system-wide propagation when the single-shell flow is stable.
- Every delta requires strict provenance, versioning, and rollback paths, keeping CReDNA separate from User ReDNA artifacts.
- Future Dev Explorer tabs: CReDNA Inspector (user/system views) and a Proposals Queue for shared upgrades.

## 🧩 Milestone (Tabled): Core Trait Containers + Curiosity Workflow
- **Purpose:** Core enforces the canonical trait schema, seeds container stubs for every user, recalculates UCN/Curiosity, and feeds Head Coach motivators.
- **Status:** **Tabled** — begin once Dev Explorer simulations are feature-complete.
- **Subtasks:**
  1. Schema expansion in Core (`trait_schema.yaml`, initialize container stubs per user).
  2. Curiosity Engine upgrade (high curiosity for unknown traits; decay, contradiction handling, rebound curves).
  3. Head Coach motivators (per trait family with sensitivity guardrails and provenance logging).
  4. Core-linked dashboards (coverage views, curiosity heatmaps, live health metrics).
  5. Ingestion pipelines (text/photo/voice/API) with detailed provenance logging and replay safeguards.

## 🛣️ Phased Benchmarks to the Vision

### Phase 1 — Curiosity Foundations & Feedback Integration (next 1–3 months)
- **Inverse RR curiosity formula (Core)**: curiosity = normalized inverse RR, with DNA-family weights; surface in `/curiosity`.
- **Contradiction/Tension logging (Core → Dev Exp)**: contradictions reduce UCN, raise curiosity, and persist as tension; badge in Preview.
- **Feedback Loop → Head Coach**: Inbox feedback (helpful/not) down-weights future motivators; capture “ToleranceForNudging” as a trait.
- **Provenance for failed attempts**: log rejected/abandoned evidence as provenance.

### Phase 2 — Governance & Audit (3–6 months)
- **Dormancy & Deceased protocols**: 3/6/12-month states; deceased → heir transfer; exclude from RR as appropriate.
- **Sensitive DNA gating**: grayed previews until threshold; tooltips; consent flags.
- **Audit Viewer + Rollback**: Dev Exp tab for logs with rollback and (stub) encryption.
- **Telemetry consolidation**: single ORS waterfall.

### Phase 3 — Evolution & Extensibility (6–12 months)
- **Self-improvement loop (CReDNA deltas)**: learn from feedback/outcomes; optional propagation with strict provenance/rollback.
- **Persona Maker (frozen coach states)**: export for outbound/contextual usage.
- **External connectors**: ingest (voice/photo/Slack) + outbound (Teams/Email).
- **Cross-device polish**: responsive layouts and session continuity.

---

## 📝 Progress Tracker (Updated 2025-10-04)
- **Legacy panel cleanup (Benchmark 1)** – Control Panel Plus is the active entrypoint; plan is to archive the other legacy panels (`control_panel.py`, `control_panelwithAI.py`, `control_and_benchmarks.py`, etc.) under an `archive/control_panels/` folder while noting any shared widgets so imports don't break.
- **Seamless persona morphing (Benchmarks 2–3)** – Chat intent now routes directly to the requested coach, Head Coach acknowledges the hand-off, and the new persona auto-greets on arrival. Next iteration: expose this routing contract to every persona registration and add timeline analytics for coach switches.
- **Head Coach Ops v1 (Benchmarks 2 & 14)** – Feature-complete: scheduling card, TTL, snooze, cohorts, run-now, and batch dismiss all live. Remaining work focuses on analytics dashboards and deeper CReDNA integration.
- **Relationship Coach voice (Benchmark 4)** – ✅ **COMPLETE**: RC voice enhanced from generic to warm confidant. System prompt expanded (8 → 260+ lines), micro-actions library expanded (3 → 60+ examples), response templates created (300+ lines), tone filter checklist added (200+ lines), opening variations expanded (1 → 8 contextual greetings). RC now follows structured 4-step pattern (Acknowledge → Reflect → Guide → Invite) with warmth markers, sensory metaphors, and connection-focused micro-actions. See [RC_Voice_Enhancement_Design.md](RC_Voice_Enhancement_Design.md) for details.
- **RSC (Benchmarks 5–6)** – Deferred until the single-shell experience stabilises; when picked up, reuse the coach registration/intents to keep collaboration wiring consistent.
- **Developer Explorer shell (Benchmark 6)** – ✅ **COMPLETE**: Streamlined from 9-11 sections to 7 focused modules. New **Observability** tab unifies trace viewer (waterfall visualization), service health, log tailer, feedback analytics, and testing/QA. New **Governance & Audit** tab provides audit logs with rollback, dormancy management, sensitivity gating, and provenance explorer. Developer Tools enhanced with System Settings integration. Full UI coverage for all backend modules (trace consolidation, feedback analytics, dormancy, sensitivity gating). See [Dev_Explorer_Guide.md](Dev_Explorer_Guide.md) and [Dev_Explorer_Audit.md](Dev_Explorer_Audit.md) for details.
- **Trait capacity expansion (Benchmark 7)** – Recent PaDNA soft-import work broadened coverage; capture further trait backlog items in this roadmap for prioritisation.
- **Holistic intelligence (Benchmark 8)** – ✅ **COMPLETE**: LLM-assisted holistic pass and raw JSON persistence in place. Auto-scheduler implemented (`holistic_scheduler.py`) with env-var controlled cadence (default: weekly). Enable with `HOLISTIC_SCHEDULER_ENABLED=true` and configure via `HOLISTIC_CADENCE_HOURS`.
- **Hygiene & identification (Benchmarks 9–10)** – No implementation yet; propose scoping documents that outline duplicate-resolution workflows and identity-matching requirements before coding.
- **Persona snapshots (Benchmark 11)** – ✅ **COMPLETE**: Export pipeline that freezes user's PaDNA into timestamped JSON bundles. Core module (`snapshot_exporter.py`), FastAPI endpoints (`api_snapshots.py`), and example code implemented. Supports full or partial exports (by trait family), snapshot history, version tagging (1.0.0), and index-based metadata. Storage: `data/users/{user_id}/snapshots/`. Future: UI integration in Explorer for export/list/download/delete. See [Persona_Snapshot_Design.md](Persona_Snapshot_Design.md) and [Overnight_Batch_4E_Persona_Snapshot.md](Overnight_Batch_4E_Persona_Snapshot.md) for details.
- **Coach customisation UX (Benchmark 12)** – Engine supports persona toggles but UI is developer-centric. Design a configuration panel for analysts to tweak persona behaviours safely.
- **Learning & external devices (Benchmarks 13–14)** – Still conceptual. Capture high-level architecture for ML-style ingestion and device integration so we can tackle them deliberately later.
- **Testing & Automation (Benchmark 7)** – ✅ **COMPLETE**: Production-ready pytest coverage for `nudge_store` (30+ tests), RR baseline utilities (20+ tests), and CReDNA ops (25+ tests). Golden-path regression script (`scripts/golden_path_test.py`) validates enqueue → accept → undo → Draft Chat workflow. Test runner (`scripts/run_tests.sh`) with `WRITE_PROTECT` safety checks operational. Test runner now integrated into Dev Explorer → Observability → Testing & QA tab.
- **Telemetry Consolidation (Benchmark 14)** – ✅ **COMPLETE**: Unified trace schema (`trace_consolidation.py`) consolidates ORS logs from Dev Explorer, UCN/RR, and Core. Waterfall visualization (`trace_viewer.py`) renders component timings. Full UI integration in Dev Explorer → Observability → Trace Viewer tab with search, filtering, and export capabilities.
- **Feedback Loop Integration (Benchmark 15)** – ✅ **COMPLETE**: Feedback capture operational in `nudge_store`. Analytics module (`feedback_analytics.py`) computes trait scores, planning weights (0.5-1.5 multipliers), and ToleranceForNudging emergent trait. API endpoints (`api_feedback.py`) expose data for Head Coach planning integration. Full analytics dashboard in Dev Explorer → Observability → Feedback Analytics with visualizations, export, and trend analysis.

## 📌 Next Actions (as of 2025-10-04)

**Recent Completions (Overnight Batch 3 — Dev Explorer Rework):**
- ✅ Developer Explorer streamlined from 9-11 sections to 8 focused modules
- ✅ Observability tab with full UI for traces, logs, feedback analytics, testing
- ✅ Governance & Audit tab with audit logs, dormancy, sensitivity gating, provenance
- ✅ Developer Tools enhanced with System Settings integration
- ✅ Comprehensive Dev Explorer User Guide and Architecture documentation
- ✅ Telemetry consolidation UI complete (waterfall viewer integrated)
- ✅ Feedback analytics dashboard complete (trait scores, planning weights, tolerance)

**Recent Completions (Overnight Batch 4A — Analytics Dashboards):**
- ✅ Analytics data collection backend (`analytics_collector.py`) with JSONL logging
- ✅ Coach Analytics Dashboard (switch frequency, engagement scores, session durations)
- ✅ Curiosity Coverage Dashboard (coverage %, gaps, heatmap, UCN distribution)
- ✅ Ops Compliance Dashboard (schedule adherence, success rates, missed operations)
- ✅ System Health Dashboard (uptime, latency percentiles, error rates, storage)
- ✅ Analytics tab added to Dev Explorer navigation (8th section)
- ✅ Comprehensive Analytics Guide with integration examples and troubleshooting

**Recent Completions (Overnight Batch 4B — Legacy Code Cleanup):**
- ✅ Comprehensive audit of Demo Root structure (Legacy_Cleanup_Audit.md)
- ✅ Archive directory structure created (legacy_services/, old_versions/)
- ✅ 11 legacy Python services moved to `archive/legacy_services/`:
  - control_panel_plus.py, ucnrr_service.py, ucnrr_app.py, ucn_rr_ai.py
  - ai_control_panel.py, ai_control_panel_agent.py, llama3_client.py
  - core_ai_propagation.py, TestExplorer.py
  - core_service_with_ai.py, ucnrr_service_with_ai.py
- ✅ 23 markdown files organized from root to `docs/historical/`
- ✅ 13 test files organized into `tests/acceptance/` and `tests/integration/`
- ✅ 4 utility scripts organized into `scripts/` and `scripts/utilities/`
- ✅ 2 old backup directories moved to `archive/old_versions/`
- ✅ Archive documentation created (README.md for both archive subdirs)
- ✅ Import validation completed (no broken references)
- ✅ "Where to Find What" navigation guide created
- ✅ Root directory now clean: only README.md and active code

**Recent Completions (Overnight Batch 4C — RC Voice Enhancement):**
- ✅ Enhanced RC system prompt (8 → 260+ lines) with warmth markers, empathy amplifiers, relationship vocabulary
- ✅ Expanded micro-actions library (3 → 60+ examples) organized by category (connection repair, communication, intimacy, conflict repair, solo actions)
- ✅ Created response template library (300+ lines) with acknowledgment, reflection, guidance, invitation patterns
- ✅ Created tone filter checklist (200+ lines) with pre-response verification
- ✅ Enhanced opening variations (1 → 8 contextual greetings) for different user states
- ✅ Updated persona registration to load new prompt assets
- ✅ Comprehensive RC Voice Enhancement Design documentation
- ✅ RC voice now warm, distinctive, confidant-level with 4-step structure (Acknowledge → Reflect → Guide → Invite)

**Recent Completions (Overnight Batch 4D — Plan Composer):**
- ✅ Implemented Plan Composer module (`plan_composer.py`, 470+ lines) with GamePlan/Step dataclasses
- ✅ Rule-based 3-step generation (Quick Data → Observation → Micro-Action)
- ✅ Persistent storage with plan history and index
- ✅ FastAPI endpoints (`api_plan_composer.py`, 220+ lines): compose, history, update status
- ✅ Coach delegation built-in (trait family → responsible coach mapping)
- ✅ Usage example code (`example_plan_composer.py`)
- ✅ Comprehensive Plan Composer Design documentation
- ✅ Plans generate in ~50ms (10x faster than target)

**Recent Completions (Overnight Batch 4E — Persona Snapshot Export):**
- ✅ Implemented Snapshot Exporter module (`snapshot_exporter.py`, 394 lines) with Snapshot/SnapshotMeta dataclasses
- ✅ Full and partial export support (by trait family)
- ✅ Timestamped bundles with version tagging (1.0.0)
- ✅ Snapshot history with index-based metadata
- ✅ FastAPI endpoints (`api_snapshots.py`, 170 lines): export, list, load, delete
- ✅ Usage example code (`example_snapshot_export.py`, 211 lines) with 6 demonstrations
- ✅ Comprehensive Persona Snapshot Design documentation (433 lines)
- ✅ Storage: `data/users/{user_id}/snapshots/` with index
- ✅ Privacy-aware (consent flags respected)
- ✅ Export speed < 2s for full PaDNA
- ✅ Benchmark #11 (Persona snapshots) complete

**Remaining High-Priority Items:**
- Build coach customization UX for analysts (safe persona behavior tweaking)
- Capture scoping documents for duplicate resolution and identity matching workflows
- Design UI integration for snapshot manager in Explorer (export/list/download/delete)
