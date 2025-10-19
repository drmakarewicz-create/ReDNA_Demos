# ReDNA Architecture Reliability Plan

**Version**: 1.0
**Last Updated**: 2025-10-14
**Status**: Phase 1 In Progress

---

## Executive Summary

This document operationalizes ReDNA's reliability-first architectural roadmap across three phases. **Phase 1 (Architectural Reliability)** establishes fail-closed validation, dynamic AI prompt loading, and UCNRR integration with full observability. **Phase 2 (Operational Integrity)** delivers API-only operation with CP++ troubleshooting UI, unified logging, and CI hardening. **Phase 3 (Intelligence Layer)** activates curiosity-driven exploration and AI-assisted trait curation. The system defaults to **Strict mode** (UCNRR required, no silent failures) with explicit configuration needed for permissive operation. All tasks specify owner (Claude vs. Codex), acceptance criteria, and embedded prompts for delegation.

---

## Decision Log

| Date | Decision | Rationale | Status |
|------|----------|-----------|--------|
| 2025-10-14 | **Strict Mode Default** | UCNRR_REQUIRED=true, EVIDENCE_STRICT=true; fail-closed prevents silent data corruption | ✅ Adopted |
| 2025-10-14 | **Dynamic Prompt Loading** | HC and UCNRR prompts loaded from markdown files with SHA verification | ✅ Adopted |
| 2025-10-14 | **API-Only Architecture** | No terminal/subprocess dependencies; CP++ provides full lifecycle management | ✅ Adopted |
| 2025-10-14 | **Claude=Backend, Codex=UI** | Claude handles Python/AI logic; Codex handles React/DevX/CI wiring | ✅ Adopted |
| 2025-10-14 | **No Headless Ingestion** | All evidence flows through validated API endpoints with error feedback | ✅ Adopted |

---

## Phase 1 — Architectural Reliability

**Goal**: Establish foundational reliability through validation, observability, and fail-closed operation.

| # | Task | Owner | Scope | Acceptance | Status |
|---|------|-------|-------|------------|--------|
| **1.1** | UCNRR AI activation + endpoint alignment | **Claude** | Load `prompts/ucn_rr_ai.md`, expose prompt hash, align endpoints, add selftest | `/health` shows `prompt_sha256`, `/ucn/score` works, `/selftest` returns scored trait | ☐ In Progress |
| **1.2** | Dynamic HC prompt loader | **Claude** | Replace hard-coded prompt with loader from `prompts/head_coach_ai_ingestion_v2.md` | `/health` shows `hc_prompt_sha256`, editing .md changes behavior | ☐ Pending |
| **1.3** | Strict validation pipeline | **Claude** | Fail-closed validation: 400 on invalid evidence, 503 if UCNRR down (Strict mode) | Invalid evidence → 400 with suggestions; UCNRR down → 503; no silent drops | ☐ Pending |

### Task 1.1: UCNRR AI Activation + Endpoint Alignment

**Owner**: Claude
**Files**:
- `UCN_RR_Demo/ucnrr_app.py`
- `prompts/ucn_rr_ai.md` (create if missing)
- `ReDNACoreDemo/core/rr/client.py`

**Scope**:
1. Create `prompts/ucn_rr_ai.md` with UCNRR system prompt (AI-driven statistical reasoning)
2. Add prompt loader to UCNRR startup that computes SHA256 hash
3. Expose `GET /health` with `prompt_sha256`, `llm_provider`, `llm_model`, `version`
4. Add `POST /ucn/score` endpoint (may alias to existing `/api/rescore`)
5. Add `GET /ucnrr/selftest` that scores canonical test case: "I have blue eyes" → `PaDNA.EyeDNA.IrisColor`
6. Update Core's `core/rr/client.py` to use `/ucn/score` as primary endpoint

**Acceptance Criteria**:
```bash
# Health check shows prompt loaded
curl -s http://127.0.0.1:8011/health | jq
# Expected: {"status": "healthy", "prompt_sha256": "abc123...", "llm_provider": "anthropic", ...}

# Score endpoint works
curl -s -X POST http://127.0.0.1:8011/ucn/score \
  -H 'Content-Type: application/json' \
  -d '{
    "user_id": "TEST",
    "items": [
      {"trait_id": "PaDNA.EyeDNA.IrisColor", "value": {"enum": "blue"}, "ucn_prior": 0.8, "source": "test"}
    ]
  }' | jq
# Expected: [{"trait_id": "PaDNA.EyeDNA.IrisColor", "ucn": 0.85}]

# Selftest works
curl -s http://127.0.0.1:8011/ucnrr/selftest | jq
# Expected: {"ok": true, "test_case": "blue_eyes", "ucn": 0.85, "elapsed_ms": 120}

# Core logs show RR online
tail -f /tmp/core_pipeline.log | grep rr_mode
# Expected: rr_mode:"online"
```

**Test Plan**:
1. Unit test: `tests/test_ucnrr_prompt_loader.py` verifies prompt SHA matches file content
2. Integration test: `tests/test_ucnrr_selftest.py` validates `/selftest` returns expected UCN
3. E2E test: Chat "I have blue eyes" and verify Core logs `rr_mode:"online"`

---

### Task 1.2: Dynamic HC Prompt Loader

**Owner**: Claude
**Files**:
- `ReDNACoreDemo/core/api.py` (lines 688-695)
- `prompts/head_coach_ai_ingestion_v2.md`
- `ReDNACoreDemo/core/hc_prompt_loader.py` (new)

**Scope**:
1. Create `core/hc_prompt_loader.py` with function `load_hc_prompt(path: Path) -> dict` returning `{"text": str, "sha256": str, "version": str}`
2. Replace hard-coded `SYSTEM_PROMPT` in `core/api.py:688` with call to prompt loader
3. Add `hc_prompt_sha256` and `hc_prompt_version` to Core `/health` endpoint
4. Add dev-only `POST /core/admin/reload_prompt` (requires `ADMIN_TOKEN` env var)
5. Parse version from prompt markdown frontmatter: `**Version**: 2.0`

**Acceptance Criteria**:
```bash
# Health check shows HC prompt loaded
curl -s http://127.0.0.1:8000/health | jq '.hc_prompt_sha256, .hc_prompt_version'
# Expected: "a1b2c3...", "2.0"

# Edit prompt file
echo "Test change" >> prompts/head_coach_ai_ingestion_v2.md

# Reload prompt (dev mode)
curl -s -X POST http://127.0.0.1:8000/core/admin/reload_prompt \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" | jq
# Expected: {"ok": true, "new_sha256": "d4e5f6...", "version": "2.0"}

# Health shows new hash
curl -s http://127.0.0.1:8000/health | jq '.hc_prompt_sha256'
# Expected: "d4e5f6..."

# Chat behavior changes based on prompt edit
```

**Test Plan**:
1. Unit test: `tests/test_hc_prompt_loader.py` verifies SHA computation and version parsing
2. Integration test: Modify prompt, reload, verify new SHA in /health
3. E2E test: Change prompt tone (e.g., add "Always respond in pirate speak"), chat, verify style change

---

### Task 1.3: Strict Validation Pipeline

**Owner**: Claude
**Files**:
- `ReDNACoreDemo/core/ingest/pipeline.py`
- `ReDNACoreDemo/core/ingest/evidence_schema.py`
- `ReDNACoreDemo/core/traits/trait_id_mapper.py`
- `ReDNACoreDemo/core/api.py` (error handling)

**Scope**:
1. Add `EVIDENCE_STRICT` env var (default: `"true"`)
2. In `validate_batch()`: if Strict mode, raise `ValidationError` (400) on:
   - Missing `trait_id` after canonicalization
   - Missing or invalid `value` (must be `{enum: str}`, `{number: float}`, or `{text: str}`)
   - Unknown trait_id with no mapper rule
3. Add `UCNRR_REQUIRED` env var (default: `"true"`)
4. In `resolve_roundtrip()`: if UCNRR_REQUIRED and RR client fails, raise `ServiceUnavailable` (503)
5. On unknown trait_id, return 400 with:
   ```json
   {
     "error": "NO_CANONICAL_TRAIT_ID",
     "evidence_sample": {"trait_id": "attributes.physical.eye_sparkle", "value": {"enum": "sparkly"}},
     "suggestions": ["PaDNA.EyeDNA.IrisColor", "PaDNA.EyeDNA.Brightness"],
     "message": "Unknown trait ID after canonicalization. Suggested matches or create new trait spec."
   }
   ```
6. Remove silent `logger.warning()` drops; all evidence rejections return HTTP errors

**Acceptance Criteria**:
```bash
# Test 1: Missing trait_id
curl -s -X POST http://127.0.0.1:8000/core/api/ingest_text \
  -H 'Content-Type: application/json' \
  -d '{
    "user_id": "TEST",
    "text": "test",
    "evidence": [{"value": {"enum": "blue"}, "source": "test"}]
  }' | jq
# Expected: HTTP 400, {"error": "MISSING_TRAIT_ID", "evidence_sample": {...}}

# Test 2: Invalid value type
curl -s -X POST http://127.0.0.1:8000/core/api/ingest_text \
  -H 'Content-Type: application/json' \
  -d '{
    "user_id": "TEST",
    "text": "test",
    "evidence": [{"trait_id": "PaDNA.EyeDNA.IrisColor", "value": "blue", "source": "test"}]
  }' | jq
# Expected: HTTP 400, {"error": "INVALID_VALUE_SHAPE", "expected": "dict with enum|number|text"}

# Test 3: Unknown trait_id
curl -s -X POST http://127.0.0.1:8000/core/api/ingest_text \
  -H 'Content-Type: application/json' \
  -d '{
    "user_id": "TEST",
    "text": "test",
    "evidence": [{"trait_id": "UnknownDNA.Fake.Trait", "value": {"enum": "x"}, "source": "test"}]
  }' | jq
# Expected: HTTP 400, {"error": "NO_CANONICAL_TRAIT_ID", "suggestions": [...]}

# Test 4: UCNRR down in Strict mode
pkill -f ucnrr_app  # Stop UCNRR
curl -s -X POST http://127.0.0.1:8000/core/api/ingest_text \
  -H 'Content-Type: application/json' \
  -d '{
    "user_id": "TEST",
    "text": "I have blue eyes",
    "source": "test"
  }' | jq
# Expected: HTTP 503, {"error": "UCNRR_REQUIRED", "message": "UCN/RR service unavailable in Strict mode"}

# Test 5: Permissive mode fallback (if UCNRR_REQUIRED=false)
UCNRR_REQUIRED=false uvicorn ...
# Same request should succeed with ucn = ucn_prior
```

**Test Plan**:
1. Unit test: `tests/test_strict_validation.py` covers all 400 cases
2. Integration test: `tests/test_ucnrr_required.py` validates 503 behavior
3. Regression test: `tests/test_pipeline_blue_eyes.py` (existing) must still pass in Strict mode

---

## Phase 2 — Operational Integrity

**Goal**: API-only operation with full lifecycle management via CP++, unified logging, and CI hardening.

| # | Task | Owner | Scope | Acceptance | Status |
|---|------|-------|-------|------------|--------|
| **2.1** | API-only mode + CP++ Troubleshooter | **Codex** | Health gate in DevX/CP++, Stack Status tiles, Troubleshooter wizard (diagnose/restart/selftest) | No terminal needed; Down→Up via CP++ UI | ☐ Pending |
| **2.2** | Unified logging + basic metrics | **Claude** | Consistent log locations, minimal counters (ingests, 4xx, 5xx, rr_fallback) | Single log source; observable success/error rates | ☐ Pending |
| **2.3** | CI hardening | **Codex** | Import canaries, schema tests, blue-eyes golden; fail on absolute imports or schema drift | CI fails before runtime on regressions | ☐ Pending |

### Task 2.1: API-Only Mode + CP++ Troubleshooter

**Owner**: Codex
**Files**:
- `ReDNACoreDemo/devx/frontend/components/StackStatus.tsx` (new)
- `ReDNACoreDemo/devx/frontend/components/Troubleshooter.tsx` (new)
- `ReDNACoreDemo/devx/backend/health_api.py`
- `scripts/cppp_bootstrap.py` (new)

**Codex Prompt**:

```markdown
**Task**: Implement CP++ Stack Status + Troubleshooter UI for API-only operation

**Context**: Users currently need terminal access to diagnose/restart ReDNA services. Create a web UI in DevX that provides full lifecycle management without terminal dependency.

**Requirements**:

1. **Stack Status Dashboard** (`devx/frontend/components/StackStatus.tsx`):
   - Grid of service tiles: Core API, UCNRR, DevX Backend
   - Each tile shows:
     - Status: 🟢 Healthy / 🟠 Degraded / 🔴 Down
     - Port number
     - Prompt SHA (for Core/UCNRR)
     - RR mode (online/fallback)
     - Uptime
   - Poll `/devx/api/stack/status` every 5s
   - Click tile → open detail modal with logs + metrics

2. **Troubleshooter Wizard** (`devx/frontend/components/Troubleshooter.tsx`):
   - Multi-step wizard triggered when service is 🔴 Down
   - Step 1: Diagnose
     - Check port availability (`lsof -ti:{port}`)
     - Check process running (`ps aux | grep {service}`)
     - Display results with ✅/❌ icons
   - Step 2: Restart
     - Button: "Kill & Restart on Port {port}"
     - Button: "Choose New Port" (auto-detect available port 8000-8099)
     - Show restart logs in real-time
   - Step 3: Self-Test
     - Run `/selftest` endpoint (or equivalent health check)
     - For Core: POST test chat message "I have blue eyes"
     - Display ingestion trace (evidence → resolver → UCNRR → resolved)
     - Green checkmarks on each step, red X on failures
   - Step 4: Logs Viewer
     - Tail last 100 lines from `/tmp/core_pipeline.log` or `.run/{service}.log`
     - Auto-refresh every 2s
     - Filter by log level (INFO/WARN/ERROR)

3. **Backend API** (`devx/backend/health_api.py`):
   - `GET /devx/api/stack/status` → aggregates health from all services
   - `POST /devx/api/stack/restart` → kills and restarts specified service
   - `POST /devx/api/stack/change_port` → updates port config and restarts
   - `GET /devx/api/stack/logs/{service}` → returns recent log lines
   - `POST /devx/api/stack/selftest/{service}` → runs service-specific self-test

4. **Bootstrap Script** (`scripts/cppp_bootstrap.py`):
   - Launched by CP++ on startup
   - Auto-starts Core, UCNRR, DevX in correct order
   - Writes PID files to `.run/*.pid`
   - Validates health checks before proceeding to next service
   - Returns JSON status to CP++ for display

**Acceptance**:
```bash
# Open DevX UI
open http://127.0.0.1:3100/stack

# Stack Status shows all services 🟢 Healthy

# Kill UCNRR manually
pkill -f ucnrr_app

# Stack Status shows UCNRR 🔴 Down within 5s

# Click UCNRR tile → Troubleshooter opens
# Click "Kill & Restart on Port 8011"
# Wizard shows restart logs, then self-test passes, status → 🟢

# No terminal commands used
```

**Files to create**:
- `ReDNACoreDemo/devx/frontend/components/StackStatus.tsx`
- `ReDNACoreDemo/devx/frontend/components/Troubleshooter.tsx`
- `ReDNACoreDemo/devx/frontend/pages/stack.tsx`
- `ReDNACoreDemo/devx/backend/stack_api.py`
- `scripts/cppp_bootstrap.py`

**Tech stack**: React + Next.js (frontend), FastAPI (backend), Python subprocess management

**Test**: CI should include E2E test that kills UCNRR, uses Troubleshooter API to restart, verifies green status.
```

---

### Task 2.2: Unified Logging + Basic Metrics

**Owner**: Claude
**Files**:
- `ReDNACoreDemo/core/logging_config.py` (new)
- `UCN_RR_Demo/logging_config.py` (new)
- `ReDNACoreDemo/core/metrics.py` (new)

**Scope**:
1. Create unified log directory: `.run/logs/` (all services write here)
2. Structured JSON logging format: `{"ts": "...", "service": "core", "level": "INFO", "event": "ingest_start", "req_id": "...", ...}`
3. Core writes to: `.run/logs/core.jsonl`
4. UCNRR writes to: `.run/logs/ucnrr.jsonl`
5. DevX writes to: `.run/logs/devx.jsonl`
6. Add minimal metrics module:
   ```python
   from core.metrics import METRICS
   METRICS.increment("ingests.total")
   METRICS.increment("ingests.errors.4xx")
   METRICS.increment("rr.fallback")
   ```
7. Expose metrics via `GET /metrics` (Prometheus-compatible or JSON)

**Acceptance Criteria**:
```bash
# All logs in one place
ls -lh .run/logs/
# Expected: core.jsonl, ucnrr.jsonl, devx.jsonl

# Logs are JSON-parseable
tail -1 .run/logs/core.jsonl | jq
# Expected: {"ts": "2025-10-14T...", "service": "core", "event": "ingest_done", ...}

# Metrics endpoint works
curl -s http://127.0.0.1:8000/metrics | jq
# Expected:
# {
#   "ingests_total": 42,
#   "ingests_errors_4xx": 3,
#   "ingests_errors_5xx": 0,
#   "rr_fallback_count": 0,
#   "rr_online_count": 42
# }
```

**Test Plan**:
1. Unit test: Verify log entries are valid JSON
2. Integration test: Ingest 10 items, verify `ingests_total` increments
3. E2E test: Kill UCNRR, ingest, verify `rr_fallback_count` increments

---

### Task 2.3: CI Hardening

**Owner**: Codex
**Files**:
- `.github/workflows/test-suite.yml`
- `tests/test_import_canaries.py` (new)
- `tests/test_schema_stability.py` (new)
- `tests/golden/blue_eyes_chat.json` (new)

**Codex Prompt**:

```markdown
**Task**: Harden CI pipeline with import canaries, schema tests, and golden file validation

**Context**: Prevent runtime regressions by failing CI on absolute imports, schema drift, and broken ingestion.

**Requirements**:

1. **Import Canary Test** (`tests/test_import_canaries.py`):
   - Scan all Python files in `ReDNACoreDemo/core/` and `ReDNACoreDemo/ucn_rr_engine/`
   - Fail if any file uses absolute imports within the same package
   - Example failure: `from ReDNACoreDemo.core.resolver import resolve` should be `from .resolver import resolve`
   - Allowed: `from ReDNACoreDemo.core import api` (package entry point)
   - Use AST parsing to detect import statements

2. **Schema Stability Test** (`tests/test_schema_stability.py`):
   - Load `tests/golden/evidence_schema_v1.json` (canonical schema)
   - Generate current schema from `core/ingest/evidence_schema.py`
   - Compare required fields, value types, and nesting structure
   - Fail if breaking changes detected (e.g., removed required field)
   - Allow additive changes (new optional fields)
   - On failure, show schema diff and update instructions

3. **Golden File Test** (`tests/test_blue_eyes_golden.py`):
   - Load `tests/golden/blue_eyes_chat.json`:
     ```json
     {
       "user_message": "I have blue eyes",
       "expected_evidence": [
         {"trait_id": "PaDNA.EyeDNA.IrisColor", "value": {"enum": "blue"}}
       ],
       "expected_inferences": [
         {"trait_id": "PaDNA.SkinDNA.Freckles", "value": {"enum": "higher_likelihood"}}
       ],
       "expected_ucn_min": 0.7
     }
     ```
   - Simulate chat ingestion with mock LLM (return canned HC response)
   - Verify evidence extracted matches expected
   - Verify inferences generated match expected
   - Verify resolved UCN >= expected_ucn_min
   - Fail if any assertion fails

4. **CI Workflow Update** (`.github/workflows/test-suite.yml`):
   - Add job: `import-canaries`
   - Add job: `schema-validation`
   - Add job: `golden-tests`
   - Run on every PR and push to main
   - Block merge if any job fails

**Acceptance**:
```bash
# Run import canary locally
pytest tests/test_import_canaries.py -v
# Expected: PASSED (or FAILED with specific file/line of bad import)

# Run schema test
pytest tests/test_schema_stability.py -v
# Expected: PASSED (schema unchanged)

# Run golden test
pytest tests/test_blue_eyes_golden.py -v
# Expected: PASSED (blue eyes chat works end-to-end)

# CI workflow runs all tests
gh workflow run test-suite.yml
# Expected: All jobs green
```

**Files to create**:
- `tests/test_import_canaries.py`
- `tests/test_schema_stability.py`
- `tests/test_blue_eyes_golden.py`
- `tests/golden/evidence_schema_v1.json`
- `tests/golden/blue_eyes_chat.json`
- Update `.github/workflows/test-suite.yml`

**Tech stack**: pytest, AST parsing, JSON schema validation

**Test**: Create a PR with an absolute import, verify CI fails with clear error message.
```

---

## Phase 3 — Intelligence Layer

**Goal**: Activate curiosity-driven exploration and AI-assisted trait curation (deferred until Phases 1-2 complete).

| # | Task | Owner | Scope | Status |
|---|------|-------|-------|--------|
| **3.1** | Curiosity Engine activation | Claude | Compute `curiosity = importance × (1 - UCN) × recency_decay`; persist to `curiosity_queue.json` | 🔒 Design Complete |
| **3.2** | AI Trait Curator (intro) | Claude | On 400 NO_CANONICAL_TRAIT_ID, Curator decides approve/deny/defer; if approve → create trait spec | 🔒 Design Complete |
| **3.3** | Curator auto-approval policy | Claude | Multi-signal sufficiency, two-model consensus (Curator + UCNRR) | 🔒 Design Complete |
| **3.4** | Meta-learning feedback | Claude | HC adjusts extraction/curiosity based on trait adoption outcomes | 🔒 Design Complete |

**Note**: Detailed implementation specs for Phase 3 will be finalized after Phase 1 and Phase 2 are complete and stable. High-level design principles:

- **Curiosity Engine**: Prioritizes trait exploration based on importance × uncertainty × recency
- **AI Curator**: Acts as approval gate for new trait proposals; validates ontology fit and safety
- **Auto-approval**: Multi-signal consensus (source diversity, typing, 2-model agreement) enables automatic trait creation
- **Meta-learning**: HC/UCNRR adapt extraction confidence and curiosity thresholds based on historical outcomes

**Acceptance (Phase 3)**: Deferred until Phases 1-2 are green.

---

## Known Risks & Mitigations

| Risk | Impact | Mitigation | Status |
|------|--------|------------|--------|
| **Schema drift between Core/UCNRR** | Evidence rejected silently; traits lost | CI schema stability tests (Task 2.3) | ☐ Pending |
| **UCNRR falls back to priors silently** | UCN scores inaccurate; no visibility | Strict mode + `rr_mode` flag in logs (Task 1.1, 1.3) | ☐ Pending |
| **Absolute imports break module** | Import errors at runtime | Import canary CI test (Task 2.3) | ☐ Pending |
| **Port conflicts on startup** | Services fail to start | CP++ Troubleshooter auto-detects ports (Task 2.1) | ☐ Pending |
| **HC prompt changes break extraction** | Evidence extraction fails | Dynamic prompt loader + version SHA (Task 1.2) | ☐ Pending |
| **Evidence without trait_id dropped** | Data loss, silent failures | Strict validation with 400 errors (Task 1.3) | ☐ Pending |
| **No observability of ingestion pipeline** | Debugging requires log spelunking | Unified JSON logs + metrics (Task 2.2) | ☐ Pending |
| **CI doesn't catch regressions** | Bugs reach production | Golden file tests + schema validation (Task 2.3) | ☐ Pending |

---

## Implementation Status

### Phase 1 Progress

- [x] Architecture Reality Check complete (see [ARCHITECTURE_REALITY_CHECK.md](./ARCHITECTURE_REALITY_CHECK.md))
- [ ] Task 1.1: UCNRR AI activation — **In Progress**
- [ ] Task 1.2: Dynamic HC prompt loader — **Pending**
- [ ] Task 1.3: Strict validation pipeline — **Pending**

### Phase 2 Progress

- [ ] Task 2.1: CP++ Troubleshooter — **Pending** (Codex assigned)
- [ ] Task 2.2: Unified logging — **Pending**
- [ ] Task 2.3: CI hardening — **Pending** (Codex assigned)

### Phase 3 Progress

- [x] Design complete — **Implementation deferred**

---

## Appendix A — Codex Prompts

### Codex Prompt A1: CP++ Stack Status + Troubleshooter

[See Task 2.1 above for full prompt]

### Codex Prompt A2: CI Hardening

[See Task 2.3 above for full prompt]

---

## Appendix B — Testing Strategy

### Unit Tests
- Prompt loader SHA computation
- Evidence schema validation
- Trait ID canonicalization
- Import canary detection

### Integration Tests
- UCNRR `/selftest` endpoint
- HC prompt reload
- UCNRR required mode (503 handling)
- Metrics increment on ingestion

### E2E Tests
- Blue-eyes golden file test (chat → evidence → resolver → resolved)
- Stack Status UI shows service states
- Troubleshooter restarts downed service
- Strict mode rejects invalid evidence with 400

### Golden Files
- `tests/golden/evidence_schema_v1.json` — Canonical evidence schema
- `tests/golden/blue_eyes_chat.json` — Reference chat ingestion trace
- `tests/golden/ucnrr_selftest.json` — Expected UCNRR selftest output

---

## Appendix C — Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `EVIDENCE_STRICT` | `"true"` | Fail-closed validation (400 on invalid evidence) |
| `UCNRR_REQUIRED` | `"true"` | Require UCNRR online (503 if unavailable) |
| `ADMIN_TOKEN` | `None` | Token for `/core/admin/*` endpoints (dev only) |
| `RR_URL` | `"http://127.0.0.1:8011/ucn/score"` | UCNRR scoring endpoint |
| `LLM_PROVIDER` | `None` | UCNRR LLM provider (`anthropic`, `openai`) |
| `LLM_API_KEY` | `None` | UCNRR LLM API key |
| `OPENAI_API_KEY` | `None` | HC LLM key (OpenAI) |
| `ANTHROPIC_API_KEY` | `None` | HC LLM key (Anthropic) |
| `LOG_DIR` | `.run/logs` | Unified log directory |

---

## Appendix D — File Structure

```
ReDNA_Demos/
├── docs/
│   ├── Architecture_Reliability_Plan.md  ← This file
│   ├── STATUS.md                          ← Live dashboard
│   └── ARCHITECTURE_REALITY_CHECK.md      ← System analysis
├── prompts/
│   ├── head_coach_ai_ingestion_v2.md      ← HC system prompt
│   └── ucn_rr_ai.md                       ← UCNRR system prompt (new)
├── ReDNACoreDemo/
│   ├── core/
│   │   ├── api.py                         ← Core FastAPI app
│   │   ├── hc_prompt_loader.py            ← Dynamic prompt loader (new)
│   │   ├── logging_config.py              ← Unified logging (new)
│   │   ├── metrics.py                     ← Metrics tracking (new)
│   │   ├── ingest/
│   │   │   ├── pipeline.py                ← Ingestion pipeline
│   │   │   └── evidence_schema.py         ← Schema validation
│   │   ├── rr/
│   │   │   └── client.py                  ← UCNRR client
│   │   └── retention/
│   │       └── policy.yaml                ← Retention config (new)
│   ├── devx/
│   │   ├── frontend/
│   │   │   ├── components/
│   │   │   │   ├── StackStatus.tsx        ← Service status UI (new)
│   │   │   │   └── Troubleshooter.tsx     ← Troubleshooter wizard (new)
│   │   │   └── pages/
│   │   │       └── stack.tsx              ← Stack management page (new)
│   │   └── backend/
│   │       ├── stack_api.py               ← Stack management API (new)
│   │       └── health_api.py              ← Health aggregation
│   └── tests/
│       ├── test_import_canaries.py        ← Import validation (new)
│       ├── test_schema_stability.py       ← Schema regression tests (new)
│       ├── test_blue_eyes_golden.py       ← Golden file test (new)
│       └── golden/
│           ├── evidence_schema_v1.json    ← Canonical schema (new)
│           └── blue_eyes_chat.json        ← Reference trace (new)
├── UCN_RR_Demo/
│   ├── ucnrr_app.py                       ← UCNRR FastAPI app
│   ├── logging_config.py                  ← Unified logging (new)
│   └── prompts/
│       └── ucn_rr_ai.md                   ← UCNRR prompt (symlink or copy)
├── scripts/
│   └── cppp_bootstrap.py                  ← CP++ service launcher (new)
├── data/
│   └── users/
│       └── template_user/
│           └── curiosity_queue.json       ← Curiosity queue (new)
└── .github/
    └── workflows/
        └── test-suite.yml                 ← CI pipeline (updated)
```

---

**End of Plan Document**
