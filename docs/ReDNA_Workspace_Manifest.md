# ReDNA Workspace Manifest (v1.0)

**Generated:** 2025-10-20  
**Repository:** /Users/davidmakarewicz/Documents/ReDNA_Demos  
**Branch:** feat/cppp_devx_bootstrap  

---

## 1. Project Overview

**Project Name:** ReDNA — Replicated Digital Neural Approximation

**Version:** 2.0 (Phase 10 - Hierarchy Redefinition)

**Description:**  
ReDNA is a sophisticated trait inference and personality modeling system that uses LLM-powered coaches to extract, validate, and refine user traits from conversational evidence. The system maintains a hierarchical ontology (ReDNA → RelDNA/PaDNA/BehDNA/CogDNA/EmoDNA), scores traits with UCN (0-1000 internal confidence) and RR (0-100 user-facing percentile), and provides explainability through Why-Cards and provenance chains. Data flows through ingestion → resolution → UCN assignment → RR normalization → graph persistence → UI display.

**Primary Modules:**
- **Core API** - FastAPI backend for trait ingestion, resolution, and graph operations
- **UCN/RR Service** - Confidence scoring and refinement rating calculations
- **Head Coach** - Primary LLM-powered trait extraction and reasoning engine
- **Curiosity Loop** - Active learning system for trait refinement questions
- **Graph Storage** - JSONL-based belief graph and ontology persistence
- **DevX System** - Developer experience tools for diagnostics and testing
- **Web Frontend** - Next.js React application for user interface
- **Photo Coach** - Computer vision integration for physical trait extraction
- **Control Panel++** - Service orchestration and monitoring utilities

---

## 2. Services & Ports

| Service | Purpose | Port(s) | Entrypoint / Path | Notes |
|---------|---------|---------|-------------------|-------|
| **Core API** | Main FastAPI backend (ingestion, traits, graph) | 8004 | `ReDNACoreDemo/core/api.py` | 80+ REST endpoints |
| **UCN/RR Service** | Scoring and confidence calculations | 8017 | `ucnrr_app.py` | User data snapshot management |
| **DevX Backend** | Developer experience API (diagnostics, synthetic data) | 8100 | `ReDNACoreDemo/devx/backend/api.py` | AI readiness checks |
| **DevX Frontend** | React UI for developer tools | 8018 | `ReDNACoreDemo/devx/frontend/` | TypeScript/React |
| **React Web UI** | Main user-facing application | 3000 | `web/` | Next.js 14 |
| **Photo Coach (Streamlit)** | Photo analysis and rendering | 8510 | PhotoRefinementCoach | Streamlit app |
| **PaDNA Coach (Streamlit)** | Physical DNA trait export | 8511 | PaDNAOutboundDemo | Streamlit app |

**Base URLs (configured in `.env`):**
- Core: `http://127.0.0.1:8004`
- UCN/RR: `http://127.0.0.1:8017`
- DevX: `http://127.0.0.1:8018`
- Web: `http://localhost:3000`

---

## 3. Key Directories

| Path | Purpose |
|------|---------|
| `ReDNACoreDemo/core/` | Core API and business logic (resolver, policies, graph, UCN/RR) |
| `ReDNACoreDemo/devx/` | Developer experience backend and frontend |
| `ReDNACoreDemo/services/` | Service implementations (consent, curiosity, storage) |
| `web/` | Next.js React frontend (main UI) |
| `data/users/` | User profiles, belief graphs, resolved traits (JSONL) |
| `data/ontology/` | Trait ontology definitions (seed_ontology.json) |
| `data/reference_pop/` | Reference population data for RR percentiles |
| `data/config/` | System configuration files |
| `prompts/` | LLM system prompts for coaches and engines |
| `tests/` | Integration and end-to-end tests (50+ test files) |
| `docs/` | Documentation (100+ markdown files) |
| `tools/` | Utility scripts (audit_rr_ucn.py, etc.) |
| `scripts/` | Automation and maintenance scripts |
| `fixtures/` | Test fixtures and sample data |
| `UCN_RR_Demo/` | UCN/RR demo implementation |
| `PhotoRefinementCoach/` | Photo analysis service |
| `PaDNAOutboundDemo/` | PaDNA export functionality |
| `ExplorerFinal/` | Head Coach runtime and explorer |
| `cpplusplus/` | Control Panel++ orchestration utilities |

---

## 4. Hierarchy Model (Phase 10)

```
ReDNA (root) = Replicated Digital Neural Approximation - The complete digital organism
 ├─ RelDNA (tier-1) = Relational DNA - Social connections and relationship patterns
 ├─ PaDNA (tier-1) = Physical Attributes DNA - Observable physical characteristics
 ├─ BehDNA (tier-1) = Behavioral DNA - Behavior patterns and habits
 ├─ CogDNA (tier-1) = Cognitive DNA - Thinking patterns and mental processes
 └─ EmoDNA (tier-1) = Emotional DNA - Emotional patterns and regulation
```

**Ontology Files:**
- Primary: `data/ontology/seed_ontology.json` (Phase 10: version 2.0, 10 nodes, 9 edges)
- Loader: `ReDNACoreDemo/core/graph/ontology.py`
- Storage: `ReDNACoreDemo/core/graph/storage.py`
- Schemas: `ReDNACoreDemo/core/graph/schemas.py`

**Schema Types:**

**Node Types:**
- `dna_category` - DNA hierarchy categories (ReDNA, RelDNA, PaDNA, BehDNA, CogDNA, EmoDNA)
- `trait` - Individual traits (PaDNA.Chronotype, BehaviorDNA.Sleep.Hours, etc.)
- `trait_value` - Enumerated values for categorical traits
- `trait_belief` - User-specific trait belief nodes in graph
- `observation` - Evidence observation nodes
- `category` - General category nodes

**Edge Types (Ontology):**
- `is_parent_of` - Hierarchy edges (Phase 10: ReDNA → tier-1 categories)
- `supports` - Trait A supports belief in Trait B
- `contradicts` - Trait A contradicts Trait B
- `correlates` - Trait A correlates with Trait B (population data)
- `suggests_question` - Trait A suggests asking about Trait B
- `is_subcategory_of` - Legacy hierarchy (pre-Phase 10)

**Edge Types (Belief Graph):**
- `evidence_for` - Observation → Trait belief
- `supports` - Trait A supports Trait B (user-specific)
- `contradicts` - Trait A contradicts Trait B
- `suggests_ask` - Uncertainty in A → Ask about B
- `inferred_from` - Trait B inferred from Trait A

---

## 5. Data Pipeline

1. **Evidence Ingest** → `ReDNACoreDemo/core/api.py` (POST `/ingest_text`, `/ui/ingest/text`)
   - User provides text, photo, or JSON evidence
   - Head Coach extracts structured evidence
   
2. **Resolution & Scoring** → `ReDNACoreDemo/core/resolver/impl.py`
   - Trait resolver applies policies and thresholds
   - Promotion logic determines if trait is "resolved" (ready for user visibility)
   
3. **UCN Assignment (0-1000, ≥2 decimals)** → `ReDNACoreDemo/core/ucn_rr_service.py`
   - UCN (User Confidence Number) calculated by LLM with U/C/N breakdown
   - Internal metric, never exposed to users
   
4. **RR Conversion (0-100 via adapter)** → `ReDNACoreDemo/core/metrics/rr_adapter.py`
   - Converts UCN (0-1000) to RR (0-100 percentile) using reference population
   - Phase 9: `rr_to_percentile()` adapter function
   
5. **Egress Normalization (guards)** → `ReDNACoreDemo/core/graph/normalize_egress.py`
   - 5 runtime guards ensure RR stays 0-100, curiosity = 100 - RR
   - Guards: rr > 100 adaptation, rr_score derivation, curiosity derivation, consistency check, reference pop fallback
   
6. **Graph Persistence (JSONL)** → `ReDNACoreDemo/core/graph/storage.py`
   - Belief graphs stored as `data/users/{user_id}/belief_graph.jsonl`
   - Ontology stored as `data/ontology/seed_ontology.json`
   - Why-Cards stored as `data/users/{user_id}/why_cards.jsonl`
   
7. **UI Display** → `web/src/app/page-client.tsx`, `web/src/components/`
   - React components fetch from Core API
   - Displays RR (0-100), curiosity, provenance, Why-Cards

---

## 6. API Surface (Key Endpoints)

### User Management
| Route | Method | Purpose | Returns | Notes |
|-------|--------|---------|---------|-------|
| `/ui/users` | GET | List all users | `{users: [{id, display_name, ...}]}` | |
| `/ui/user/create` | POST | Create new user | `{user_id, ...}` | Body: `{display_name, traits?}` |
| `/ui/user/import` | POST | Import user data | `{user_id, imported_count}` | Body: JSON user data |

### Data Ingestion
| Route | Method | Purpose | Returns | Notes |
|-------|--------|---------|---------|-------|
| `/ingest_text` | POST | Ingest text evidence | `{extracted, promoted, ...}` | Body: `{user_id, text}` |
| `/ui/ingest/text` | POST | UI text ingestion | `{evidence_count, ...}` | Body: `{user_id, text}` |
| `/ui/ingest/json` | POST | UI JSON ingestion | `{imported_count}` | Body: `{user_id, data}` |
| `/core/api/ingest_evidence` | POST | Structured evidence | `{status, ...}` | Body: `{user_id, evidence[]}` |

### Traits & Resolution
| Route | Method | Purpose | Returns | Notes |
|-------|--------|---------|---------|-------|
| `/user/{user_id}/resolved` | GET | Get resolved traits | `{traits: [{trait_id, value, rr, ...}]}` | RR 0-100 normalized |
| `/ui/trait/override` | POST | Override trait value | `{trait_id, new_value}` | Body: `{user_id, trait_id, value}` |
| `/ui/trait/revert_last` | POST | Revert last change | `{reverted_trait}` | Body: `{user_id, trait_id}` |
| `/ui/trait_timeline` | GET | Trait change history | `{timeline: [{ts, trait_id, value}]}` | Query: `user_id, trait_id?` |

### Why-Cards & Provenance
| Route | Method | Purpose | Returns | Notes |
|-------|--------|---------|---------|-------|
| `/core/api/traits/{trait_id}/why` | GET | Why-card for trait | `{what, why, next}` | 3-part explanation |
| `/why-cards/{user_id}/{trait_id}` | GET | Download why-card | PDF/text file | |
| `/core/api/whycards` | GET | List all why-cards | `{cards: [{id, trait_id, ...}]}` | Query: `user_id` |
| `/core/api/user/{user_id}/provenance/{trait_id}` | GET | Trait provenance | `{trait_node, evidence_chain}` | Observation chain |
| `/ui/trait/provenance` | POST | Get provenance | `{provenance: [{node, edge}]}` | Body: `{user_id, trait_id}` |

### Graph Operations (Phase 8+)
| Route | Method | Purpose | Returns | Notes |
|-------|--------|---------|---------|-------|
| `/core/graph/ontology` | GET | Get full ontology | `OntologyGraph` | Phase 10: 10 nodes, 9 edges |
| `/core/graph/ontology/load` | POST | Load/reload ontology | `{status, nodes, edges, action}` | Query: `force=true` for replace |
| `/core/graph/ontology/stats` | GET | Ontology statistics | `{stats: {nodes, edges, ...}}` | |
| `/core/graph/user/{user_id}` | GET | User belief graph | `BeliefGraph` | RR normalized |
| `/core/graph/user/{user_id}/stats` | GET | User graph stats | `{nodes, edges, avg_rr}` | |

### Curiosity Loop
| Route | Method | Purpose | Returns | Notes |
|-------|--------|---------|---------|-------|
| `/core/api/curiosity` | GET | Get curiosity queue | `{items: [{id, question, ...}]}` | Query: `user_id` |
| `/core/api/curiosity/enqueue` | POST | Add curiosity item | `{item_id}` | Body: `{user_id, question, ...}` |
| `/core/api/curiosity/{item_id}/answer` | POST | Answer curiosity | `{status}` | Body: `{answer}` |
| `/core/api/curiosity/{item_id}/dismiss` | POST | Dismiss item | `{status}` | |

### Debug & Diagnostics (Phase 9)
| Route | Method | Purpose | Returns | Notes |
|-------|--------|---------|---------|-------|
| `/core/debug/rr_audit/{user_id}` | GET | Audit RR normalization | `{summary, issues: [{file, line, type}]}` | Query: `dry_run=true` |
| `/core/debug/ucn_propagation/{user_id}` | GET | Audit UCN propagation | `{parent_child_divergences: [...]}` | Checks >200 point gaps |

### System & Health
| Route | Method | Purpose | Returns | Notes |
|-------|--------|---------|---------|-------|
| `/health` | GET | Core health check | `{status: "healthy", ...}` | |
| `/core/graph/health` | GET | Graph module health | `{status, ontology_loaded, ...}` | |
| `/metrics` | GET | Request metrics | `{requests: [{path, duration}]}` | |
| `/core/admin/reload_prompt` | POST | Reload LLM prompts | `{status}` | Body: `{prompt_name}` |

---

## 7. AI Prompt Files

| File | Purpose |
|------|---------|
| `prompts/core_ai.md` | Core inference engine system prompt (coherent user model, UCN, contradiction handling) |
| `prompts/head_coach_ai_ingestion_v2.md` | Head Coach primary reasoning engine (v2.1.1 - evidence extraction, trait schema) |
| `prompts/head_coach_conversational_v3.0.md` | Conversational Head Coach variant |
| `prompts/ucn_rr_ai.md` | UCN/RR scoring system prompt (0-1000 scale, U/C/N breakdown) |
| `prompts/ucn_rr_confidence.md` | UCN/RR confidence calculation guidance |
| `prompts/career_coach_ai.md` | Career coach system prompt |
| `prompts/relationship_coach_ai.md` | Relationship coach system prompt |
| `prompts/permission_coach_ai.md` | Permission coach system prompt |
| `prompts/chatdna_coach_ai.md` | ChatDNA coach system prompt |
| `prompts/beliefdna_coach_ai.md` | BeliefDNA coach system prompt |
| `prompts/personality_test_coach_ai.md` | Personality test coach prompt |
| `prompts/onboarding_ai.md` | User onboarding flow prompt |

**Modular Prompts:**
- `prompts/relationship_coach/system.md` - Relationship coach system
- `prompts/relationship_coach/microactions.md` - Microactions catalog
- `prompts/relationship_coach/response_templates.md` - Response templates
- `prompts/relationship_coach/tone_filter.md` - Tone filtering
- `prompts/relationship_coach/opening.md` - Opening messages

---

## 8. Phase & Version History

| Phase | Focus | Status | Notes |
|-------|-------|--------|-------|
| **Phase 1-5** | Foundation | ✅ Complete | Core ingestion, trait extraction, basic UI |
| **Phase 6** | Why-Cards | ✅ Complete | Explainability via 3-part cards (what/why/next) |
| **Phase 7** | Holistic Inference | ✅ Complete | Cross-trait reasoning, contradiction detection |
| **Phase 8** | Graph System | ✅ Complete | Belief graphs, ontology, provenance chains |
| **Phase 9** | UCN↔RR Separation | ✅ Complete | Guarded normalization, RR 0-100, Curiosity = 100 - RR |
| **Phase 10** | Hierarchy Redefinition | ✅ Complete | ReDNA as root, RelDNA demoted to tier-1 |

**Current Version:** 2.0 (Phase 10)

**Key Milestones:**
- Phase 6: Why-Cards baseline locked (commit `554806b`)
- Phase 7: Nuclear restart + diagnostics (commit `167707f`)
- Phase 9: UCN/RR audit + cleanup (18→14 critical findings)
- Phase 10: Ontology loader fix + hierarchy (10 nodes, 9 edges)

---

## 9. Flags / Environment Variables

**LLM Configuration:**
```bash
HC_CHAT_PROVIDER=ollama                  # LLM provider (ollama, openai, anthropic)
OLLAMA_BASE=http://127.0.0.1:11434      # Ollama server URL
OLLAMA_MODEL=llama3.1:8b                # Ollama model name
UCNRR_LLM_PROVIDER=ollama               # UCN/RR service LLM provider
```

**Service Ports:**
```bash
CORE_PORT=8004                          # Core API port
UCNRR_PORT=8017                         # UCN/RR service port
REACT_PORT=3000                         # Web UI port
DEVX_BACKEND_PORT=8100                  # DevX backend port
DEVX_PORT=8018                          # DevX frontend port
STREAMLIT_PHOTO_PORT=8510               # Photo coach port
STREAMLIT_PADNA_PORT=8511               # PaDNA coach port
```

**Feature Flags:**
```bash
CORE_HOLISTIC_ON_INGEST=true            # Enable holistic inference on ingest
ENABLE_CURIOSITY_LOOP=true              # Enable curiosity queue
CORE_CURIOSITY_ENABLED=true             # Core curiosity features
DEV_EXPLORER_ENABLED=true               # Developer explorer UI
AUDIT_VIEWER_ENABLED=true               # Audit viewer UI
HC_CHAT_ENABLED=true                    # Head Coach chat interface
PERSONA_DEV_TABS=true                   # Persona development tabs
```

**Promotion Thresholds (RR 0-1000 scale - LEGACY):**
```bash
RR_PROMOTE_MIN=500.0                    # Default promotion threshold
RR_PROMOTE_MIN_HAIR=500                 # Hair color promotion
RR_PROMOTE_MIN_AGE=500                  # Age promotion
RR_PROMOTE_MIN_REL=540                  # Relationship promotion
RR_PROMOTE_MIN_HEIGHT=650               # Height promotion (higher bar)
PROMOTE_ENABLE_HAIR=true                # Enable hair promotion
PROMOTE_ENABLE_AGE=true                 # Enable age promotion
PROMOTE_ENABLE_REL=true                 # Enable relationship promotion
PROMOTE_ENABLE_HEIGHT=true              # Enable height promotion
```

**Curiosity Settings:**
```bash
CURIOSITY_DEFAULT_TTL_DAYS=30           # Default curiosity item TTL
CURIOSITY_COOLDOWN_SEC=604800           # Cooldown between same-trait questions (7 days)
CURIOSITY_MAX_OPEN_PER_USER=20          # Max open questions per user
CURIOSITY_MAX_OPEN_PER_TRAIT=2          # Max open questions per trait
```

**Data Paths:**
```bash
CORE_DATA_ROOT=data                     # Root data directory
```

---

## 10. Tests & Coverage (High-Level)

**Test Suites:** 50+ test files across `/tests/` and `/ReDNACoreDemo/tests/`

**Notable Test Suites:**
- **Phase 9 Tests** (`tests/api/test_rr_guardrails.py`) - 20/20 passing
  - RR adapter tests (0-1000 → 0-100 conversion)
  - Normalize belief node tests (5 guards)
  - UCN leak prevention tests
  - Debug endpoint tests
  
- **Phase 10 Tests** (`tests/api/test_phase10_hierarchy.py`) - 15/15 passing
  - Ontology hierarchy tests (ReDNA root, tier-1 categories)
  - Alias mapping tests (RelationalDNA → RelDNA)
  - Egress invariant tests (Phase 9 compatibility)
  - Schema support tests (dna_category, is_parent_of)
  
- **Ontology Loader Tests** (`tests/api/test_ontology_loader.py`) - 14/14 passing
  - Force load tests (replace not merge)
  - Version upgrade tests (2.0 > 1.0)
  - Phase 10 hierarchy validation

**Total Test Count:** 80+ tests across all phases

**Quick Smoke Tests:**
```bash
# Run all tests
pytest

# Run Phase 9 tests only
pytest tests/api/test_rr_guardrails.py -v

# Run Phase 10 tests only
pytest tests/api/test_phase10_hierarchy.py -v

# Run ontology loader tests
pytest tests/api/test_ontology_loader.py -v

# Run with coverage
pytest --cov=ReDNACoreDemo --cov-report=html
```

---

## 11. Known TODOs / LEGACY Markers

**Critical Items** (from Phase 9 Audit):

1. **ucn_rr_service.py:multiple** - LEGACY 0-1000 scale markers
   - `rr: float` field uses 0-1000 scale (should be 0-100 percentile)
   - Curiosity formula: `1000 - RR` (should be `100 - RR`)
   - TODO: Migrate to 0-100 scale or add adapter layer

2. **head_coach_service.py:multiple** - Curiosity formula inconsistencies
   - Some functions use `1000 - rr`, others use `100 - rr`
   - RR defaults to `1000.0` in some places, `50.0` in others
   - TODO: Standardize to `100 - RR` formula

3. **redna_core.py:multiple** - UCN→RR conflation
   - Line references UCN when calculating RR
   - TODO: Use RR field directly, not derived from UCN

4. **storage layer** - 0-1000 scale persistence
   - Files marked as "LEGACY - Phase 9: Should be 0-100 percentile"
   - TODO: Gradual migration or keep as internal-only

**Full Audit Report:** See `docs/Phase9_RR_UCN_Audit_Report.md`
- 30 total findings (14 critical, 1 warning, 15 info)
- Files scanned: 271
- Audit tool: `tools/audit_rr_ucn.py`

**Other TODOs:**
- Graph Stage 4: LLM-powered next question selection (currently STUB)
- Frontend: Update UI to display Phase 10 hierarchy tree
- Migration: Optional data migration for legacy RelationalDNA → RelDNA

---

## 12. Recent Changelogs & Key Docs

**Phase Completion Reports:**
- `docs/Phase7_Completion_and_Phase8_Proposal.md` - Phase 7 completion, Phase 8 proposal
- `docs/Phase8_Stage1_Completion_Report.md` - Phase 8 Stage 1 (ontology foundation)
- `docs/Phase8_Stage2_Completion_Report.md` - Phase 8 Stage 2 (graph API)
- `docs/Phase8_Stage3_Completion_Report.md` - Phase 8 Stage 3 (curiosity + insights)
- `docs/Phase8_Stage4_Completion_Report.md` - Phase 8 Stage 4 (Why-Cards + provenance)
- `docs/Phase9_Audit_and_Changes_Report.md` - Phase 9 UCN↔RR audit
- `docs/Phase9_RR_Normalization_and_Reference_Pop.md` - Phase 9 RR normalization
- `docs/Phase9_Shape_Harmonizer.md` - Phase 9 shape harmonization
- `docs/Phase10_ReDNA_Hierarchy_Implementation.md` - Phase 10 hierarchy redefinition
- `docs/Phase10_Ontology_Loader_Fix.md` - Phase 10 ontology loader fix

**Architecture Docs:**
- `docs/PHASE7_ARCHITECTURE_DIAGRAM.md` - Phase 7 system architecture
- `docs/PHASE10_ARCHITECTURE.md` - Phase 10 enhancements
- `docs/ARCHITECTURE_REALITY_CHECK.md` - Architecture validation
- `docs/CRITICAL_DATA_FLOW_ARCHITECTURE.md` - Data flow patterns

**Operations Guides:**
- `docs/ReDNA_Ops_Runbook_v1.0.md` - Operations runbook
- `docs/OPERATIONS.md` - General operations guide
- `docs/Testing_Guide.md` - Testing procedures
- `docs/Where_To_Find_What.md` - Navigation guide

**Benchmarks & Roadmap:**
- `docs/Core_Benchmarks_Roadmap_v3.0.md` - Comprehensive roadmap
- `docs/ReDNA_MVP_Benchmarks_v1.0.md` - MVP benchmarks

**Diagrams:**
- (none yet) - Future: Add architecture diagrams, data flow diagrams

---

## Appendix: Quick Reference

**Start Services:**
```bash
# Core API
cd ReDNACoreDemo && python -m uvicorn core.api:app --port 8004

# UCN/RR Service
python ucnrr_app.py

# Web UI
cd web && npm run dev

# DevX Backend
cd ReDNACoreDemo/devx/backend && python -m uvicorn api:app --port 8100
```

**Force Load Phase 10 Ontology:**
```bash
curl -X POST "http://localhost:8004/core/graph/ontology/load?force=true"
```

**Check Ontology Status:**
```bash
curl "http://localhost:8004/core/graph/ontology" | jq '{nodes:(.nodes|length), edges:(.edges|length), version:.version}'
```

**Run UCN/RR Audit:**
```bash
python tools/audit_rr_ucn.py
```

---

## 18. Troubleshooting & Operations

### Quick Diagnostics

**Check All Services:**
```bash
curl -s http://127.0.0.1:8004/health  # Core API
curl -s http://127.0.0.1:8017/health  # UCNRR
curl -s http://127.0.0.1:8100/health  # DevX Backend
curl -s http://127.0.0.1:8502/_stcore/health  # CP++
```

**Check Ports:**
```bash
lsof -i :8004 -i :8017 -i :8100 -i :3000 -i :8502 | grep LISTEN
```

### Common Issues

1. **"Failed to fetch" errors in UI**
   - See [FETCH_ERROR_FIX.md](FETCH_ERROR_FIX.md)
   - Test endpoint: `curl "http://127.0.0.1:8004/ui/unabridged?user_id=ai_ready_probe"`
   - Check logs: `tail -50 ~/.redna/devx_supervisor/logs/core.stdout.log`

2. **Port drift warnings**
   - See [PORT_DRIFT_FIX_SUMMARY.md](PORT_DRIFT_FIX_SUMMARY.md)
   - Verify .env: `grep PORT .env | grep -v "^#"`
   - Fix: Nuclear Reset in CP++

3. **Import errors**
   - Test: `python3 -c "from ReDNACoreDemo.core import ui_readonly; print('OK')"`
   - See [FETCH_ERROR_FIX.md](FETCH_ERROR_FIX.md) for example fix

4. **Service won't start**
   - Check logs: `tail -50 ~/.redna/devx_supervisor/logs/*.log`
   - Kill zombie: `pkill -f uvicorn`
   - Restart: Use CP++ Nuclear Reset

### Documentation Index

**Operations:**
- [TROUBLESHOOTING_QUICK_REF.md](TROUBLESHOOTING_QUICK_REF.md) - Quick diagnostic commands
- [OPERATIONS.md](OPERATIONS.md) - Operational procedures
- [PORT_ALLOCATION.md](PORT_ALLOCATION.md) - Port allocation strategy

**Recent Fixes:**
- [PORT_DRIFT_FIX_SUMMARY.md](PORT_DRIFT_FIX_SUMMARY.md) - DevX port drift resolution
- [FETCH_ERROR_FIX.md](FETCH_ERROR_FIX.md) - Import error in reference_pop module

**Architecture:**
- [Intel/ServicesAndPorts.json](Intel/ServicesAndPorts.json) - Service inventory
- [Intel/DebugSurface.md](Intel/DebugSurface.md) - Debug endpoint documentation
- [Intel/FlagsAndDefaults.json](Intel/FlagsAndDefaults.json) - Feature flags reference

**Implementation Guides:**
- Phase 7-10 completion reports in `docs/Phase*.md`
- RR/UCN audit documentation
- Why-Card system implementation
- Belief graph normalization

### Control Panel++

**Start CP++:**
```bash
./scripts/start_cp.sh  # Recommended
# Or: env STREAMLIT_SERVER_PORT=8502 streamlit run control_panel_plus_plus.py --server.port 8502
```

**Access:** http://127.0.0.1:8502

**Features:**
- Service health monitoring (5 services)
- Nuclear Reset button (rebuild entire stack)
- Port drift detection
- AI Readiness probe
- Developer Explorer (DevX) launcher
- Log viewer

---

**Manifest Version:** 1.0
**Last Updated:** 2025-10-20
**Next Review:** Phase 11 planning
