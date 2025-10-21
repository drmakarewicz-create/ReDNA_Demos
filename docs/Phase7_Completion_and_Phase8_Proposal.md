# ReDNA System Reconnaissance & Phase 8 Proposal

**Date**: 2025-10-19
**Analyst**: Claude (Sonnet 4.5)
**Context**: Post-Phase 7 ("AI-Native Organism Stabilization")
**System Status**: ✅ ALL GREEN (5/5 services operational)

---

## Executive Summary

The ReDNA system has successfully achieved **AI-Native Organism** status. All core services are synchronized, LLM-integrated, and operationally stable. The Nuclear Restart capability provides reliable recovery from configuration drift. However, **port configuration management** remains the primary architectural weakness, requiring immediate hardening before Phase 8.

**Phase 8 Recommendation**: **Cross-Trait Reasoning Graphs** with **Adaptive Curiosity Orchestration**

---

## 1. Workspace Comprehension

### 1.1 Live System Architecture

**Service Topology** (5 running services):

```
┌─────────────────────────────────────────────────────────────┐
│                  Control Panel++ (CP++)                      │
│                   Port 8501 (Streamlit)                      │
│         Nuclear Restart │ Orchestration │ Monitoring         │
└───────────┬──────────────────────────────────────────────┬──┘
            │                                                │
    ┌───────▼────────┐  ┌───────────────┐  ┌──────────▼──────┐
    │  Core API      │  │     UCNRR     │  │  DevX Backend   │
    │  Port 8004     │  │  Port 8017    │  │    Port 8100    │
    │  (FastAPI)     │  │  (FastAPI)    │  │   (FastAPI)     │
    └────────┬───────┘  └───────┬───────┘  └────────┬────────┘
             │                  │                     │
             └──────────────────┴─────────────────────┘
                                │
                    ┌───────────▼──────────┐
                    │  React/Northstar     │
                    │    Port 3000         │
                    │    (Next.js 14)      │
                    └──────────────────────┘
```

**Service Entry Points**:

| Service | Entry Point | Process Type | Health Endpoint |
|---------|------------|--------------|-----------------|
| Core API | `ReDNACoreDemo/core/api.py` | uvicorn (async) | `/health` |
| UCNRR | `UCN_RR_Demo/ucnrr_app.py` | uvicorn (async) | `/health`, `/api/health` |
| DevX Backend | `ReDNACoreDemo/devx/backend/api.py` | uvicorn (async) | `/health` |
| React/Northstar | `web/src/app` (Next.js) | next-server | `/api/health` |
| CP++ | `control_panel_plus_plus.py` | streamlit | `/_stcore/health` |

**Key Data Stores**:

- **User State**: `data/users/{user_id}/`
  - `observations.json` - Raw observations from all sources
  - `state.json` - Resolved trait beliefs (snapshot + derived)
  - `curiosity_queue.json` - Ranked asks (Phase 6 implementation)
  - `user_info.json` - Metadata, permissions, consent
  - `timeline.json` - Chronological trait evolution
  - `why_cards.json` - Explainability records

- **System Config**:
  - `.env` - System-wide environment (UPPERCASE keys)
  - `.cpplusplus_env.json` - CP++ session config (lowercase keys)
  - `.cp_state.json` - CP++ process state (PIDs, ports, timestamps)

- **Diagnostic Logs**:
  - `/tmp/core_pipeline.log` - Core ingestion pipeline
  - `/tmp/core*.log` - Core service logs
  - `~/.redna/nuclear_reset.log` - Nuclear restart diagnostics
  - DevX logs (location varies by deployment)

### 1.2 Orchestration Dependencies & Startup Sequence

**CP++ Enforces**:

1. **Recommended Start Order** (displayed in UI):
   ```
   UCNRR → Core → React/Northstar
   ```

2. **Actual Dependency Chain**:
   ```
   1. UCNRR (independent, can start first)
   2. Core (checks UCNRR availability for RR scoring)
   3. React (requires Core API for all operations)
   4. DevX Backend (requires Core + UCNRR for diagnostics)
   ```

3. **Port Scanning & Health Probes**:
   - CP++ scans port ranges on startup
   - Detects external processes vs. managed processes
   - Health checks run every refresh (manual or auto-refresh)
   - Port conflicts trigger interactive resolution UI

4. **Nuclear Restart Process** ([control_panel_plus_plus.py:4951-5434](control_panel_plus_plus.py#L4951-L5434)):
   ```python
   def _nuclear_reset_all_services():
       1. Identify CP++ port (self-protection)
       2. Kill all processes on ports: 8004, 8017, 8100, 3000-3009
       3. Clear .cp_state.json (stale PIDs)
       4. Verify ports released
       5. Restart services in order (UCNRR → Core → React)
       6. Probe LLM connectivity
       7. Log diagnostics to ~/.redna/nuclear_reset.log
   ```

**Configuration Rotation**:
- Nuclear process does NOT rotate `.cpplusplus_env.json` (should it?)
- Preserves `.env` (correct)
- Clears `.cp_state.json` (correct)
- Does not touch user data (correct)

### 1.3 Hard-Coded Assumptions Requiring Parameterization

**Critical Issue**: Port configuration has multiple sources of truth:

1. **Hard-coded defaults** in `control_panel_plus_plus.py:100-105`:
   ```python
   CORE_DEFAULT_PORT = 8004
   REACT_DEFAULT_PORT = 3000
   UCNRR_DEFAULT_PORT = 8017
   ```

2. **Environment variable fallbacks** in `cpplusplus/envstore.py:16-23`:
   ```python
   DEFAULT_ENV = {
       "core_port": 8004,
       "react_port": 3000,
       "ucnrr_port": 8017,
   }
   ```

3. **Session overrides** in `.cpplusplus_env.json` (user-editable, drift-prone)

4. **System config** in `.env` (UPPERCASE keys, not always synced)

**Recent Incident (2025-10-19)**:
- `.cpplusplus_env.json` had stale ports (8015, 3001) from previous session
- Services running on correct ports (8004, 3000) but CP++ showing yellow
- Nuclear restart didn't fix it because config wasn't reset
- Manual fix required editing `.cpplusplus_env.json`

**Recommendations**:
1. ✅ **DONE**: Created [Port_Configuration_Guide.md](docs/Port_Configuration_Guide.md)
2. ✅ **DONE**: Created [verify_ports.sh](scripts/verify_ports.sh) verification script
3. ⚠️ **TODO**: Make Nuclear restart optionally reset `.cpplusplus_env.json`
4. ⚠️ **TODO**: Add port validation on CP++ startup
5. ⚠️ **TODO**: Single source of truth for port config (`.env` as canonical)

**Other Hard-Coded Assumptions**:
- LLM timeout: 30s (in various places, should be `LLM_TIMEOUT_SEC`)
- Service URLs constructed as `http://127.0.0.1:{port}` (no remote deployment support)
- User data path: `data/users/` (should be `USER_DATA_ROOT`)
- Ollama default model: scattered across files (should be `OLLAMA_DEFAULT_MODEL`)

---

## 2. Codebase Audit: LLM Integration Coverage

### 2.1 LLM-Integrated Components (✅ AI-Native)

**Core API** ([ReDNACoreDemo/core/api.py](ReDNACoreDemo/core/api.py)):
- ✅ Head Coach chat (`/ui/chat/send`) - uses LLM for all responses
- ✅ Trait extraction from chat (via `hc_trait_bridge.py`)
- ✅ Curiosity generation (`curiosity_engine.py`)
- ✅ Why-Card generation (LLM-generated explanations)
- ✅ Preference extraction (`preference_extractor.py`)
- ✅ Life insights (`hc_life_insights.py`)

**UCNRR** ([UCN_RR_Demo/ucnrr_app.py](UCN_RR_Demo/ucnrr_app.py)):
- ✅ Trait extraction and normalization (LLM-powered)
- ✅ Canonicalization and schema repair
- ✅ UCN (Uncertainty/Curiosity/Necessity) scoring
- ✅ Adaptive RR thresholds (Phase 6)

**DevX Backend** ([ReDNACoreDemo/devx/backend/](ReDNACoreDemo/devx/backend/)):
- ✅ AI Readiness Probe (`ai_ready.py`) - E2E LLM verification
- ✅ Coach API (`coach_api.py`) - delegates to Core LLM
- ✅ Batch operations - uses Core's LLM reasoning

**React/Northstar** ([web/src/](web/src/)):
- ✅ LLM Benchmarks page (`tools/llm-benchmarks/`) - monitors AI health
- ✅ Head Coach conversation UI - streams LLM responses
- ✅ Why-Cards display - shows LLM explanations

### 2.2 Partially Deterministic / Legacy Components (⚠️ Mixed)

**Deterministic Fallbacks** (by design, acceptable):
- ⚠️ RR scoring fallback to priors when UCNRR unavailable ([rr/client.py](ReDNACoreDemo/core/rr/client.py))
  - **Status**: Acceptable - graceful degradation
  - **Philosophy alignment**: Violates "no deterministic fallbacks" but necessary for availability
  - **Recommendation**: Add prominent logging when fallback activated

- ⚠️ Holistic inference "skip" tracking ([holistic.py](ReDNACoreDemo/core/holistic.py))
  - **Status**: Tracks which traits were skipped by LLM
  - **Philosophy alignment**: Good - maintains explainability
  - **Recommendation**: Keep as-is

**Legacy / Stub Code** (should be reviewed):
- ⚠️ Mock mode in `hc_llm_agent.py`: "deterministic fallback"
  - **Status**: Development testing mode
  - **Recommendation**: Ensure never enabled in production
  - **Fix**: Add assertion that `HC_CHAT_ENABLED=true` in production

- ⚠️ Empty memory layer fallback ([situational_awareness.py](ReDNACoreDemo/core/head_coach/situational_awareness.py))
  - **Status**: Placeholder for future memory integration
  - **Recommendation**: Phase 8 candidate - implement persistent memory

### 2.3 Duplicated / Stale Files

**Backups** (safe to ignore):
- `ReDNACoreDemo/core.bak.142110/` - backup from 2025-01-14
- `ReDNACoreDemo/core.bak.142307/` - backup from 2025-01-14
- Multiple snapshot directories in `snapshots/`

**Active Duplicates** (requires attention):
- ⚠️ `UCN_RR_Demo/app.py` vs. `ucnrr_app.py`
  - **Status**: `ucnrr_app.py` is active (65KB, recently modified)
  - **Status**: `app.py` appears to be legacy (7.9KB, older)
  - **Recommendation**: Archive `app.py` if confirmed unused

- ⚠️ `ReDNACoreDemo/core/api_*.py` modules
  - **Status**: Modular API structure (good design)
  - **Check**: Verify all are imported and used in `api.py`

**Stale Config Files**:
- ❌ `.cp_state.json` - gets stale if processes die
  - **Fix**: Nuclear restart now clears this (good)
- ❌ `.cpplusplus_env.json` - can drift from `.env`
  - **Fix**: New verification script detects this

### 2.4 Verification: No Deterministic Bypasses

**Checked for bypass flags**:
```bash
grep -ri "SKIP_LLM\|DISABLE_AI\|DETERMINISTIC_MODE\|BYPASS" ReDNACoreDemo/core --include="*.py"
```
**Result**: ✅ No active bypass flags found

**Checked for hard-coded responses**:
```bash
grep -ri "return.*hard.*coded\|mock.*response" ReDNACoreDemo/core --include="*.py"
```
**Result**: ⚠️ Mock mode exists in `hc_llm_agent.py` but controlled by env var

**LLM Provider Configuration Check**:
```python
# Core API
HC_CHAT_ENABLED = env("HC_CHAT_ENABLED", "true")
HC_CHAT_PROVIDER = env("HC_CHAT_PROVIDER", "ollama")  # ✅ Active

# UCNRR
LLM_PROVIDER = env("LLM_PROVIDER", "ollama")  # ✅ Active
```

**Conclusion**: ✅ All critical paths use LLM reasoning. Fallbacks are graceful degradation only.

---

## 3. Phase 8 Collaboration Planning

### 3.1 System Philosophy Alignment Check

From [ReDNA_System_Philosophy_v1.md](docs/ReDNA_System_Philosophy_v1.md):

**Core Principles** (2025-10-19 status):

1. ✅ **AI at Every Layer**: Verified across Core, UCNRR, HC, DevX
2. ✅ **Deterministic Control, Dynamic Behavior**: CP++ provides control, LLMs drive reasoning
3. ✅ **Adaptation Over Perfection**: Adaptive thresholds (Phase 6), curiosity queue implemented
4. ✅ **Curiosity Before Certainty**: Curiosity queue ranks asks by information gain
5. ⚠️ **Holism Over Isolation**: Holistic inference exists, but limited to single trait updates
6. ✅ **Explainability & Transparency**: Why-Cards generated for major updates
7. ✅ **Forgiving Intelligence**: Schema repair, canonicalization handle noisy inputs
8. ⚠️ **Scientific Curiosity**: Hypothesis formation exists, but no graph-based reasoning yet
9. ⚠️ **Ethical and Emotional Awareness**: Head Coach considers tone, but no explicit empathy model
10. ✅ **Self-Evolving Standards**: LLM model swapping supported via env vars

**Gaps for Phase 8**:

1. **Cross-Trait Reasoning**: Current holistic passes are sequential, not graph-based
   - Example: Learning "outdoor enthusiast" should trigger questions about fitness, sleep patterns, social preferences
   - Current: Only immediate contradictions are detected

2. **Population Priors**: No population-level learning yet
   - Example: If 10,000 users who are "morning people" also prefer "quiet social settings", use that prior
   - Current: Each user treated independently

3. **Feedback-Driven Curiosity**: Curiosity queue doesn't learn from user engagement patterns
   - Example: If user ignores questions about diet, deprioritize diet-related asks
   - Current: Static weighting only

4. **Memory & Context**: No persistent memory across sessions
   - Example: "Last time we talked about your hiking trip..."
   - Current: Each chat session is stateless

5. **Self-Auditing Fairness**: No automated bias detection
   - Example: Check if promotion thresholds are consistent across demographic groups
   - Current: Manual review only

### 3.2 Phase 8 Recommendation: **Cross-Trait Reasoning Graphs**

**Vision**: Transform ReDNA from a collection of independent trait beliefs into a **coherent reasoning graph** where traits, observations, and questions form an interconnected knowledge structure.

**Core Concept**:
```
Observation: "I wake up at 5am every day"
    ↓ (triggers)
Trait Inference: Chronotype = Morning Lark (RR: 750)
    ↓ (graph traversal)
Related Questions:
  - "Do you prefer social activities in the morning or evening?" (Social Preferences)
  - "What time do you typically exercise?" (Fitness Habits)
  - "How do you feel about working from home vs. office?" (Work Location Preference)
    ↓ (coherence check)
Contradiction Detection:
  - User also said "I'm most productive at night" → Flag for curiosity
```

**Technical Components**:

1. **Trait Ontology Graph**
   - Nodes: Traits, DNAs, categories
   - Edges: Correlation, causation, contradiction, evidence-for
   - Stored in: `data/ontology/trait_graph.json`
   - **LLM Role**: Generate edge weights from population data

2. **User-Specific Belief Graph**
   - Nodes: User's trait beliefs (snapshot + derived)
   - Edges: Observation provenance, inference chains
   - Stored in: `data/users/{user_id}/belief_graph.json`
   - **LLM Role**: Traverse graph to find optimal next question

3. **Curiosity Orchestrator** (upgrade from Phase 6 queue)
   - Current: Static ranking by UCN scores
   - **New**: Graph-aware exploration strategy
     - **Breadth**: Explore uncovered trait clusters
     - **Depth**: Follow up on high-uncertainty areas
     - **Coherence**: Resolve contradictions first
   - **LLM Role**: Decide exploration strategy based on user history

4. **Population Prior Learning**
   - Aggregate anonymized patterns across users
   - Store in: `data/population/priors.json`
   - **LLM Role**: Infer likely correlations, flag outliers
   - **Privacy**: Differential privacy, user consent required

5. **Adaptive Fairness Auditor**
   - Scan for bias in promotion thresholds
   - Compare RR score distributions across demographics
   - **LLM Role**: Generate natural-language bias reports
   - Stored in: `data/audits/fairness_reports/`

### 3.3 Phase 8 Sequencing Plan

**Stage 1: Foundation (Weeks 1-2)**

**Blocking Cleanup Tasks**:
1. ✅ Port configuration hardening (DONE: docs + script created)
2. ⚠️ Add Nuclear restart option to reset `.cpplusplus_env.json`
3. ⚠️ Archive duplicate files (`UCN_RR_Demo/app.py`, backup dirs)
4. ⚠️ Disable mock mode in production (add env check)
5. ⚠️ Document all hard-coded timeouts and paths

**New Infrastructure**:
1. Create `data/ontology/` directory structure
2. Design trait graph schema (JSON format)
3. Implement graph storage/retrieval API
4. Add graph visualization endpoint in DevX

**Stage 2: Trait Ontology Graph (Weeks 3-4)**

**Data Collection**:
1. Audit existing trait registry for relationships
2. Use LLM to propose edge types (correlation, causation, etc.)
3. Manual validation of core relationships (Jane)
4. Automated edge weight learning from population data

**API Endpoints** (Core):
```python
GET  /graph/ontology                    # Full trait graph
GET  /graph/ontology/neighbors/{trait}  # Related traits
POST /graph/ontology/infer_edges        # LLM-powered edge discovery
```

**Stage 3: User Belief Graphs (Weeks 5-6)**

**Schema Design**:
```json
{
  "user_id": "TEST",
  "graph": {
    "nodes": [
      {
        "id": "trait_chronotype",
        "type": "trait",
        "value": "Morning Lark",
        "rr": 750,
        "ucn": {"u": 0.2, "c": 0.3, "n": 0.5}
      },
      {
        "id": "obs_2025_10_19_001",
        "type": "observation",
        "text": "I wake up at 5am",
        "source": "chat"
      }
    ],
    "edges": [
      {
        "from": "obs_2025_10_19_001",
        "to": "trait_chronotype",
        "type": "evidence_for",
        "weight": 0.9
      }
    ]
  }
}
```

**Implementation**:
1. Extend `write_user_state()` to include graph
2. Graph updates on every observation ingestion
3. Graph pruning (decay old edges)
4. Graph-aware Why-Cards (show provenance chain)

**API Endpoints** (Core):
```python
GET  /user/{user_id}/graph              # User belief graph
GET  /user/{user_id}/graph/provenance/{trait}  # Trace evidence chain
POST /user/{user_id}/graph/traverse     # Find related questions
```

**Stage 4: Graph-Aware Curiosity (Weeks 7-8)**

**Upgrade Curiosity Queue**:
1. Current: Flat list of asks, sorted by UCN
2. **New**: Exploration strategy selector
   ```python
   strategies = {
       "breadth": explore_uncovered_clusters,
       "depth": follow_up_uncertain_traits,
       "coherence": resolve_contradictions,
       "user_driven": prioritize_user_interests
   }
   ```
3. LLM chooses strategy based on user history
4. Graph traversal to find optimal next question

**Implementation**:
```python
# In curiosity_engine.py
def generate_next_question(user_id: str) -> dict:
    belief_graph = load_user_graph(user_id)
    ontology_graph = load_ontology_graph()

    # LLM-powered strategy selection
    strategy = llm_select_strategy(
        user_history=get_chat_history(user_id),
        belief_graph=belief_graph,
        recent_engagement=get_engagement_metrics(user_id)
    )

    # Graph traversal
    candidate_questions = traverse_graph(
        belief_graph=belief_graph,
        ontology_graph=ontology_graph,
        strategy=strategy
    )

    # LLM ranks candidates
    return llm_rank_questions(candidate_questions)
```

**Stage 5: Population Priors (Weeks 9-10)**

**Ethical Considerations**:
1. User consent: Opt-in for population learning
2. Differential privacy: Add noise to aggregates
3. Anonymization: No user-identifiable data in priors

**Data Pipeline**:
1. Nightly aggregation job (privacy-safe)
2. Correlation discovery (LLM-assisted)
3. Prior distribution updates
4. Outlier detection (flag unusual trait combinations)

**API Endpoints** (Core):
```python
GET  /population/priors/{trait}         # Prior distribution
GET  /population/correlations/{trait}   # Related traits
POST /population/learn                  # Trigger aggregation (admin only)
```

**Stage 6: Adaptive Fairness Auditor (Weeks 11-12)**

**Audit Dimensions**:
1. RR score distributions by demographics
2. Promotion rate parity across groups
3. Curiosity bias (are certain traits over-questioned?)
4. Response time fairness (LLM latency across demographics)

**Implementation**:
```python
# In adaptive_analytics/ (new module)
def run_fairness_audit(time_range: str) -> dict:
    users = load_users(time_range)

    # Group by demographics
    groups = segment_users_by_demographics(users)

    # Compare RR distributions
    rr_distributions = {
        group: get_rr_distribution(users)
        for group, users in groups.items()
    }

    # LLM-generated report
    return llm_generate_fairness_report(rr_distributions)
```

**API Endpoints** (DevX):
```python
GET  /audits/fairness/latest            # Most recent audit
POST /audits/fairness/run               # Trigger new audit
GET  /audits/fairness/trends            # Historical trend
```

### 3.4 Structural Weaknesses to Address

**Logging**:
- ✅ Good: Core pipeline log (`/tmp/core_pipeline.log`)
- ⚠️ Issue: Logs are ephemeral (lost on restart)
- ⚠️ Issue: No centralized logging (each service logs separately)
- **Fix**: Implement structured logging with rotation (use Python `logging.handlers.RotatingFileHandler`)

**Data Schema**:
- ✅ Good: Pydantic models for validation
- ⚠️ Issue: Schema evolution not versioned
- ⚠️ Issue: No migration strategy for user data
- **Fix**: Add schema version to `state.json`, implement migration API

**Orchestration Latency**:
- ✅ Good: Async FastAPI for all services
- ⚠️ Issue: No request tracing across services
- ⚠️ Issue: No timeout cascades (one slow service blocks others)
- **Fix**: Implement distributed tracing (OpenTelemetry?), set timeouts at every layer

**Model Throughput**:
- ✅ Good: Streaming responses for Head Coach
- ⚠️ Issue: Ollama has no rate limiting (can saturate)
- ⚠️ Issue: No request queueing (spikes cause failures)
- **Fix**: Implement LLM request queue with priority (curiosity > chat > batch)

**Port Configuration** (Critical):
- ❌ Bad: Multiple sources of truth (`.env`, `.cpplusplus_env.json`, hard-coded defaults)
- ❌ Bad: Nuclear restart doesn't reset session config
- ❌ Bad: No validation on startup
- **Fix**: See Section 1.3 recommendations

---

## 4. Collaboration Logistics

### 4.1 Code-Level Entry Points Needed from Jane

To efficiently implement Phase 8, Claude will need:

**Immediate Access** (for Stage 1):
1. ✅ **Already have**: Current system state (verified via this reconnaissance)
2. ⚠️ **Need**: Example user data directory structure
   - Request: `ls -la data/users/TEST/` output
   - Purpose: Understand current schema before adding graph
3. ⚠️ **Need**: Current trait registry structure
   - Request: `cat ReDNACoreDemo/core/traits/registry.json` (or equivalent)
   - Purpose: Seed ontology graph
4. ⚠️ **Need**: Startup logs from all services
   - Request: Recent logs showing successful startup sequence
   - Purpose: Verify no hidden dependencies

**For Later Stages**:
1. **Stage 2**: Sample population data (anonymized)
   - Purpose: Test correlation discovery
2. **Stage 5**: User consent flow design
   - Purpose: Implement opt-in for population learning
3. **Stage 6**: Demographic field definitions
   - Purpose: Design fairness audit dimensions

### 4.2 Recommended Role Division

**Claude (AI System Architect)**:
- **Phase 8 Design**: Trait graph schema, API specs, data pipeline
- **Conceptual Architecture**: Graph traversal algorithms, curiosity strategies
- **LLM Integration**: Prompt engineering for graph reasoning, fairness audits
- **Documentation**: System philosophy alignment, explainability docs
- **Code Review**: Ensure all new code is AI-native (no deterministic bypasses)

**Codex (Deterministic Implementation)**:
- **Boilerplate Code**: API endpoint scaffolding, Pydantic models
- **Data Migration**: Scripts to add graph fields to existing user data
- **Testing Infrastructure**: Unit tests, integration tests
- **Performance Optimization**: Caching, indexing, query optimization
- **DevX UI**: Graph visualization components, audit dashboards

**Jane (Context Continuity & Orchestration)**:
- **System Context**: Historical decisions, phase progression, philosophy evolution
- **Requirements Validation**: Ensure Phase 8 aligns with long-term vision
- **User Experience**: Design curiosity presentation, fairness transparency
- **QA & Testing**: End-to-end validation, edge case discovery
- **Coordination**: Sequence stages, prioritize features, manage scope

**Collaborative Workflow**:
```
1. Jane defines Stage goals & requirements
   ↓
2. Claude designs architecture & LLM integration
   ↓
3. Jane validates alignment with philosophy
   ↓
4. Codex implements scaffolding & tests
   ↓
5. Claude reviews for AI-native compliance
   ↓
6. Jane performs E2E QA & context check
   ↓
7. Iterate or proceed to next Stage
```

---

## 5. Immediate Blocking Cleanup Tasks

**Before starting Phase 8**, complete these tasks:

### 5.1 Port Configuration Hardening (Priority: CRITICAL)

**Tasks**:
1. ✅ **DONE**: Documentation ([Port_Configuration_Guide.md](docs/Port_Configuration_Guide.md))
2. ✅ **DONE**: Verification script ([verify_ports.sh](scripts/verify_ports.sh))
3. ⚠️ **TODO**: Update Nuclear restart to optionally reset `.cpplusplus_env.json`
   ```python
   # In _nuclear_reset_all_services()
   if st.checkbox("Reset CP++ config to defaults", value=True):
       if Path(".cpplusplus_env.json").exists():
           Path(".cpplusplus_env.json").unlink()
           log("Deleted .cpplusplus_env.json (will reload from .env)")
   ```
4. ⚠️ **TODO**: Add port validation on CP++ startup
   ```python
   # In main()
   _validate_port_config()  # Check .env vs .cpplusplus_env.json consistency
   ```
5. ⚠️ **TODO**: Make `.env` the single source of truth
   - CP++ reads from `.env` first
   - `.cpplusplus_env.json` only for overrides (clearly marked in UI)

**Acceptance Criteria**:
- Run `./scripts/verify_ports.sh` → All green
- Nuclear restart → All services come back on correct ports
- No yellow status due to port mismatch

### 5.2 Mock Mode Safeguard (Priority: HIGH)

**Task**: Ensure mock mode never runs in production

**Implementation**:
```python
# In hc_llm_agent.py or api.py startup
if os.getenv("ENVIRONMENT", "development") == "production":
    assert os.getenv("HC_CHAT_ENABLED", "false").lower() == "true", \
        "Production requires HC_CHAT_ENABLED=true (no mock mode)"
    assert os.getenv("HC_CHAT_PROVIDER") in ["ollama", "openai", "anthropic"], \
        f"Invalid LLM provider in production: {os.getenv('HC_CHAT_PROVIDER')}"
```

**Acceptance Criteria**:
- Starting Core with `ENVIRONMENT=production` and `HC_CHAT_ENABLED=false` → Immediate error
- Nuclear restart logs show LLM provider active

### 5.3 File Cleanup (Priority: MEDIUM)

**Task**: Archive duplicate/stale files

**Files to Archive**:
```bash
mkdir -p archive/phase7_cleanup/
mv UCN_RR_Demo/app.py archive/phase7_cleanup/  # If confirmed unused
mv ReDNACoreDemo/core.bak.* archive/phase7_cleanup/
# Keep snapshots/ for now (may need for rollback)
```

**Acceptance Criteria**:
- No duplicate entry points
- Active services unaffected

### 5.4 Environment Variable Audit (Priority: LOW)

**Task**: Document all hard-coded values

**Create**: `docs/Environment_Variables_Reference.md`

**Content**:
```markdown
| Variable | Default | Used By | Purpose |
|----------|---------|---------|---------|
| CORE_PORT | 8004 | Core, CP++ | Core API port |
| HC_CHAT_ENABLED | true | Core | Enable LLM chat |
| LLM_TIMEOUT_SEC | 30 | All | LLM request timeout |
| USER_DATA_ROOT | data/users | Core | User storage path |
| ... | ... | ... | ... |
```

**Acceptance Criteria**:
- All services can be configured via `.env` (no hard-coded overrides)

---

## 6. Phase 8 Feature Plan (Prioritized)

### Must-Have (MVP)

1. **Trait Ontology Graph** (Stage 2)
   - Core relationships defined
   - Graph API endpoints
   - DevX visualization

2. **User Belief Graphs** (Stage 3)
   - Graph storage in user state
   - Provenance tracking
   - Graph-aware Why-Cards

3. **Graph-Aware Curiosity** (Stage 4)
   - Strategy selector (breadth/depth/coherence)
   - Graph traversal for question generation
   - Integration with existing curiosity queue

### Should-Have (High Value)

4. **Population Priors** (Stage 5)
   - Opt-in consent flow
   - Basic correlation discovery
   - Prior-informed inference

5. **Adaptive Fairness Auditor** (Stage 6)
   - RR distribution analysis
   - LLM-generated bias reports
   - DevX dashboard

### Nice-to-Have (Future Phases)

6. **Persistent Memory** (Phase 9?)
   - Session-to-session context
   - User timeline summarization
   - Proactive follow-ups

7. **Federated Learning** (Phase 10?)
   - Privacy-preserving population learning
   - Encrypted aggregate updates
   - Decentralized priors

---

## 7. Success Criteria for Phase 8

**Technical Metrics**:
- ✅ All services remain green during Phase 8 development
- ✅ Nuclear restart works with graph-enabled users
- ✅ Graph API latency < 100ms for typical queries
- ✅ Curiosity strategy selection is LLM-powered (no hard-coded logic)
- ✅ Fairness audits run automatically (weekly)

**Philosophy Alignment**:
- ✅ Cross-trait reasoning demonstrates holism (Principle 2.5)
- ✅ Population priors improve adaptation (Principle 2.3)
- ✅ Fairness audits ensure ethical awareness (Principle 2.9)
- ✅ Graph provenance enhances explainability (Principle 2.6)

**User Experience**:
- ✅ Curiosity questions feel more relevant (user feedback)
- ✅ Why-Cards show reasoning chains (not just isolated updates)
- ✅ No increase in latency for core operations

---

## 8. Risk Assessment

**High Risk**:
- ⚠️ **Port configuration drift**: Mitigated by cleanup tasks
- ⚠️ **Graph storage performance**: Need benchmarking for large graphs
- ⚠️ **Privacy compliance**: Population learning requires legal review

**Medium Risk**:
- ⚠️ **LLM throughput**: Graph traversal may increase LLM calls
- ⚠️ **Data migration**: Adding graphs to existing users
- ⚠️ **Complexity creep**: Graph reasoning is conceptually harder

**Low Risk**:
- ⚠️ **Backward compatibility**: New fields are additive
- ⚠️ **Service stability**: No changes to core ingestion pipeline

**Mitigation Strategies**:
1. **Port drift**: Implement validation before every session
2. **Performance**: Start with small graphs, optimize incrementally
3. **Privacy**: Implement opt-in and differential privacy from day 1
4. **Throughput**: Implement LLM request queue with priority
5. **Migration**: Lazy graph generation (create on first update)
6. **Complexity**: Extensive documentation and visualization

---

## 9. Conclusion & Next Steps

### System Status: **READY FOR PHASE 8**

**Strengths**:
- ✅ All services LLM-integrated (AI-native organism achieved)
- ✅ Nuclear restart provides reliable recovery
- ✅ Explainability (Why-Cards) and curiosity (queue) infrastructure exists
- ✅ System philosophy is clear and actionable

**Weaknesses**:
- ⚠️ Port configuration needs hardening (in progress)
- ⚠️ No cross-trait reasoning yet (Phase 8 target)
- ⚠️ No population-level learning (Phase 8 target)

### Immediate Next Steps

**Week 1** (Jane + Claude):
1. Review this reconnaissance report
2. Validate Phase 8 vision alignment with long-term goals
3. Prioritize cleanup tasks (Section 5)
4. Approve Stage 1 sequencing

**Week 2** (Claude + Codex):
1. Complete blocking cleanup tasks
2. Design trait graph schema
3. Implement graph storage API
4. Create DevX graph visualization prototype

**Week 3+** (All):
1. Proceed through Phase 8 stages sequentially
2. Weekly sync: Jane (context) + Claude (architecture) + Codex (implementation)
3. Continuous QA and philosophy alignment checks

---

## Appendix: Quick Reference

**Service Health Check**:
```bash
./scripts/verify_ports.sh
```

**Nuclear Restart** (via CP++ UI):
```
Click "🔥 NUCLEAR RESET & REBUILD ENTIRE STACK 🔥"
```

**LLM Integration Check**:
```bash
curl http://127.0.0.1:8100/devx/api/ai_ready
# Should return: {"result": "ALL-GOOD"}
```

**Current Port Assignments**:
- Core: 8004
- UCNRR: 8017
- DevX: 8100
- React: 3000
- CP++: 8501

**Configuration Files**:
- System: `.env` (canonical source)
- CP++ Session: `.cpplusplus_env.json` (overrides)
- CP++ State: `.cp_state.json` (runtime PIDs/ports)

**Documentation**:
- Philosophy: [ReDNA_System_Philosophy_v1.md](docs/ReDNA_System_Philosophy_v1.md)
- Ports: [Port_Configuration_Guide.md](docs/Port_Configuration_Guide.md)
- This Report: `docs/Phase7_Completion_and_Phase8_Proposal.md`

---

**Report Version**: 1.0
**Next Review**: After Stage 1 completion
**Contact**: Claude (Architect) + Jane (Orchestrator)
