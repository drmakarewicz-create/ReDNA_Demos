# Evergreen Sprint Prompts — ReDNA (Autonomous Sprint Plan)

## Purpose
This document defines active autonomous tasks for Claude and Codex to execute, prioritize, and refine throughout the day.
Each section represents a perpetual development objective (Evergreen) aligned with ReDNA’s long-term intelligence and human impact goals.

Agents:
- Claude (planning, reasoning, documentation, human-interaction simulation)
- Codex (engineering, implementation, system verification)

## Sections

### Evergreen 9 — Data Ingestion Universality
**Goal:** The Head Coach and Core should automatically and persistently ingest all available data:
- Chat patterns, tone, pacing, emoji usage
- File uploads and metadata
- Data shared across coach modes
- Information shared about a User by others

**Tasks:**
1. Claude → Draft ingestion pipeline extensions and Core/HC collaboration logic.
2. Codex → Implement ingestion expansions with safe provenance tagging.
3. Both → Ensure “Comfort Index” logic is applied before ingestion (user safety and control).
4. Update `hc_orchestrator.py`, `core_ingestion.py`, `ucnrr_service_with_ai.py`, and `core_ai.md` to reflect this new ingestion architecture.

---

### Evergreen 6 — Curiosity Engine Expansion
**Goal:** Expand Core + UCN/RR curiosity generation for empty/unrefined containers.
**Tasks:**
1. Claude → Design `Curiosity v3` flowchart showing Core–UCNRR–HC interactions.
2. Codex → Implement prototype in `curiosity_engine_v3.py`.
3. Add hooks for:
   - Dynamic curiosity reprioritization
   - “Curiosity debt” tracking (unexplored topics)
   - Daily HC prompts to explore unfilled containers

---

### Evergreen 2 — Head Coach Human Bonding Mandate
**Goal:** Make HC actively persuade, inspire, and build trust.
**Tasks:**
1. Claude → Refine tone, persuasion, and empathy models in `head_coach_ai.md`.
2. Codex → Update HC orchestration to monitor satisfaction metrics, generate emotional intelligence reports, and adjust communication tone dynamically.
3. Implement `hc_empathy_monitor.py` to track emotional patterns and success of “bonding” efforts.

---

### Evergreen 1 — HC Empowerment and Tools
**Goal:** Equip HC with tools that make “life improvement” tangible.
**Tasks:**
1. Claude → Define new functional modules (e.g., Financial Planner, Mood Tracker, Goal Engine, Habit Loop).
2. Codex → Scaffold these as optional sub-agents accessible from the HC dashboard.
3. Integrate via `hc_tool_registry.json` and new `tools/` folder for modular expansion.

---

### Evergreen 3 — Container and Edge Growth
**Goal:** Continue to grow the ontology intelligently.
**Tasks:**
1. Claude → Generate new container patterns for underrepresented namespaces (HealthDNA, EnvDNA, SocialDNA).
2. Codex → Run `expansion_engine_v7.py` to generate + validate 10K containers.
3. Claude → Review and create new edge taxonomy for nuanced relationships (motivation, empathy, causation, contradiction).
4. Codex → Extend correlation_engine_v2.py to accommodate new edge classes.

---

### Evergreen 10 — Continuous Model Optimization
**Goal:** Improve all AI reasoning through better LLM prompts and context construction.
**Tasks:**
1. Claude → Rewrite core .md prompts with improved structure, hierarchy, and reasoning clarity.
2. Codex → Version, store, and evaluate LLM responses with prompt/response audit logging.

---

## Coordination Instructions

- Claude and Codex will reference this file **every hour** to determine next available work item.
- Each will append progress reports in the same document under `### Daily Progress Log`.
- Every 3–4 hours, Claude will summarize progress to `docs/ops/EVERGREEN_SPRINT_LOG_<DATE>.md`.
- At the end of the session, Codex will push commits and generate:
  - A summary (`EVERGREEN_SPRINT_SUMMARY.md`)
  - Updated state manifest (`_system_state.json`)
  - Health report (`DAILY_HEALTH_REPORT.md`)

---

## Daily Progress Log

### 2025-10-12 (Session 1)

**Completed by Claude:**

✅ **Evergreen 9 - Data Ingestion Universality:**
- [x] Drafted complete data ingestion pipeline architecture (EVERGREEN_9_DATA_INGESTION_ARCHITECTURE.md)
  - Defined 6-stage pipeline: Pre-Process → Comfort → Provenance → Storage → Enrichment → Distribution
  - Specified Core/HC collaboration logic and API contracts
  - Created provenance tagging schema with full audit trail
- [x] Designed comprehensive ingestion flowcharts (EVERGREEN_9_INGESTION_FLOWCHART.md)
  - Complete pipeline flow with decision trees
  - Stage-by-stage detailed logic diagrams
  - Core/HC collaboration sequence diagrams
  - Error handling and recovery flows
- [x] Created Comfort Index integration specification (EVERGREEN_9_COMFORT_INDEX_SPEC.md)
  - 10-level sensitivity taxonomy
  - User control interface design
  - PII detection and anonymization logic
  - Review queue system architecture
  - Dynamic learning and adaptation system

**Deliverable:** 3 comprehensive design documents totaling ~15,000 words saved to docs/designs/

✅ **Evergreen 6 - Curiosity Engine v3:**
- [x] Designed Curiosity v3 architecture (EVERGREEN_6_CURIOSITY_ENGINE_V3.md)
  - 7-component system: Core Analysis, UCN/RR Analysis, Coordinator, Debt Tracker, Prioritization, Question Generation, HC Integration
  - Complete flow diagrams showing Core-UCNRR-HC interactions
  - Curiosity debt tracking methodology
  - Question effectiveness evaluation system
- [x] Specified dynamic reprioritization logic (EVERGREEN_6_DYNAMIC_REPRIORITIZATION_SPEC.md)
  - 8 reprioritization trigger types with handlers
  - Temporal reprioritization (time-of-day, weekly, seasonal)
  - Daily HC prompt generation system
  - Question quality feedback loop
  - Real-time context adaptation

**Deliverable:** 2 comprehensive design documents totaling ~10,000 words saved to docs/designs/

✅ **Evergreen 2 - HC Human Bonding:**
- [x] Refined empathy model specification (EVERGREEN_2_HC_EMPATHY_BONDING_SPEC.md)
  - Multi-dimensional empathy framework (cognitive, emotional, compassionate)
  - EmpathyEngine implementation with signal collection and state detection
  - Persuasion framework using 6 core techniques (reciprocity, commitment, social proof, authority, liking, scarcity)
  - MotivationEngine for strategic user motivation
- [x] Designed bonding metrics and monitoring system
  - 15 relationship health metrics across trust, engagement, emotion, growth, stability
  - BondingMonitor with automated tracking
  - Dynamic tone adaptation based on user state and relationship stage
  - Continuous feedback and improvement loops

**Deliverable:** 1 comprehensive design document totaling ~8,000 words saved to docs/designs/

✅ **Evergreen 1 - HC Tools & Empowerment:**
- [x] Defined functional modules (EVERGREEN_1_HC_TOOLS_EMPOWERMENT.md)
  - Financial Planner: Budget tracking, expense categorization, savings goals, insights
  - Mood Tracker: Pattern detection, trigger identification, correlation analysis, recommendations
  - Goal Engine: SMART goal creation, milestone generation, progress tracking, weekly reviews
  - Habit Loop Designer: Cue-routine-reward framework, streak tracking, daily prompts
- [x] Designed tool registry and modular expansion architecture
  - JSON-based tool registry schema
  - ToolManager for orchestration and permission management
  - HC integration layer for natural tool suggestions
  - API endpoint specifications for each tool

**Deliverable:** 1 comprehensive design document totaling ~9,000 words saved to docs/designs/

---

**Summary Statistics:**
- **Total Documents Created:** 7 comprehensive design specifications
- **Total Content:** ~42,000 words of detailed architecture and logic
- **Total Time:** Approximately 3 hours
- **Evergreens Completed:** 4 (Evergreen 9, 6, 2, 1)
- **Deliverables Location:** docs/designs/

**Design Artifacts Created:**
1. EVERGREEN_9_DATA_INGESTION_ARCHITECTURE.md
2. EVERGREEN_9_INGESTION_FLOWCHART.md
3. EVERGREEN_9_COMFORT_INDEX_SPEC.md
4. EVERGREEN_6_CURIOSITY_ENGINE_V3.md
5. EVERGREEN_6_DYNAMIC_REPRIORITIZATION_SPEC.md
6. EVERGREEN_2_HC_EMPATHY_BONDING_SPEC.md
7. EVERGREEN_1_HC_TOOLS_EMPOWERMENT.md

**Next Steps for Codex (Implementation Phase):**
1. Begin Evergreen 9 implementation (data ingestion pipeline)
2. Create curiosity_engine_v3.py module
3. Implement empathy_engine.py and bonding_monitor.py
4. Build tool modules (financial_planner.py, mood_tracker.py, goal_engine.py, habit_loop_designer.py)
5. Update hc_orchestrator.py with all integrations

---

### 2025-10-13
- [ ] Claude: Draft ingestion pipeline enhancements.
- [ ] Codex: Implement ingestion scaffolding in Core + HC.
- [ ] Claude: Curiosity Engine v3 flow design.
- [ ] Codex: Implement Curiosity v3 prototype.
- [ ] Claude: Expand empathy model.
- [ ] Codex: Implement empathy tracker + bonding metrics.
- [x] Codex: Wire empathy & curiosity telemetry into Life OS DevX + chat surfaces.

### Evergreen Integration Telemetry Tests (2025-10-13)

```
$ pytest ReDNACoreDemo/tests/test_hc_human_intel.py -q
..                                                                       [100%]
2 passed, 4 warnings in 0.22s
```

> Note: `npm run build` in `ReDNACoreDemo/devx/frontend` still fails due to pre-existing TypeScript warnings unrelated to this change (unused imports, legacy interfaces).

### Evergreen 9 Test Results (2025-10-12)

```
$ pytest ReDNACoreDemo/tests/test_ingestion_pipeline.py
============================= test session starts ==============================
platform darwin -- Python 3.13.7, pytest-8.4.2, pluggy-1.6.0
rootdir: /Users/davidmakarewicz/Documents/ReDNA_Demos
configfile: pytest.ini
plugins: asyncio-1.2.0, anyio-4.10.0
collected 3 items

ReDNACoreDemo/tests/test_ingestion_pipeline.py ...                       [100%]

============================== 3 passed in 0.03s ===============================
```

### Evergreen 6 Test Results (2025-10-12)

```
$ python3 -m pytest ReDNACoreDemo/tests/test_curiosity_engine_v3.py
============================== test session starts ==============================
platform darwin -- Python 3.13.7, pytest-8.4.2, pluggy-1.6.0
rootdir: /Users/davidmakarewicz/Documents/ReDNA_Demos
configfile: pytest.ini
plugins: asyncio-1.2.0, anyio-4.10.0
collected 3 items

ReDNACoreDemo/tests/test_curiosity_engine_v3.py ...                      [100%]

=============================== 3 passed in 0.03s ===============================
```

### Evergreen 2 Test Results (2025-10-12)

```
$ python3 -m pytest ReDNACoreDemo/tests/test_empathy_monitor.py
============================== test session starts ==============================
platform darwin -- Python 3.13.7, pytest-8.4.2, pluggy-1.6.0
rootdir: /Users/davidmakarewicz/Documents/ReDNA_Demos
configfile: pytest.ini
plugins: asyncio-1.2.0, anyio-4.10.0
collected 2 items

ReDNACoreDemo/tests/test_empathy_monitor.py ..                           [100%]

=============================== 2 passed in 0.02s ===============================
```

### Evergreen 1 Test Results (2025-10-12)

```
$ python3 -m pytest ReDNACoreDemo/tests/test_tool_manager.py
============================== test session starts ==============================
platform darwin -- Python 3.13.7, pytest-8.4.2, pluggy-1.6.0
rootdir: /Users/davidmakarewicz/Documents/ReDNA_Demos
configfile: pytest.ini
plugins: asyncio-1.2.0, anyio-4.10.0
collected 2 items

ReDNACoreDemo/tests/test_tool_manager.py ..                              [100%]

=============================== 2 passed in 0.02s ===============================
```
