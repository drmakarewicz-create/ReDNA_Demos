# ReDNA Workspace Map

## Core Paths

### Backend Services

```
ReDNACoreDemo/core/api.py                         # Main Core API, promotion builder, debug routes
ReDNACoreDemo/core/ingest/value_normalizer.py     # Conservative value validators for Tier-1+ traits
ReDNACoreDemo/core/logutil.py                     # Structured logging (stack_log)

UCN_RR_Demo/ucnrr_app.py                          # UCNRR service: env loader, health, score, debug routes
UCN_RR_Demo/data/config/dna_weights.yaml          # DNA category weights for scoring

prompts/ucn_rr_ai.md                              # UCNRR AI prompt for trait extraction
```

### Frontend

```
web/src/app/page-client.tsx                       # Main Northstar UI client
web/src/app/tools/llm-benchmarks/page.client.tsx  # LLM Benchmarks page
web/src/components/metrics/RoundtripChart.tsx     # Hop-timing visualization
web/src/components/metrics/GlobalMetricsContext.tsx # Shared metrics context
web/src/lib/llmBenchApi.ts                        # LLM Bench API client
```

### Documentation

```
docs/STATUS.md                                    # Overall project status
docs/PHASE5_STATUS.md                             # Phase 5 status and goals
docs/ARCHITECTURE_REALITY_CHECK.md                # System architecture overview
docs/UCNRR_LLM_Config_Logic.md                   # UCNRR LLM configuration truth table
docs/WORKSPACE_MAP.md                             # This file
```

### Test & Verification

```
scripts/tier1_verify.py                           # Tier-1 trait verification automation
scripts/tier2_verify.py                           # Tier-2 trait verification
scripts/roundtrip_capture.py                      # Capture roundtrip metrics
tests/integration/test_tier2_smoke.py             # Tier-2 integration tests
tests/test_value_normalizer_tier2.py              # Value normalizer unit tests
docs/reports/tier1_verify_summary.md              # Tier-1 verification results
```

### Data & Storage

```
data/                                             # Repo-level data root
data/dev_logs/trace_ucnrr.jsonl                   # UCNRR tracing logs
data/users/                                       # User data storage
data/storage/                                     # Core storage root

UCN_RR_Demo/data/                                 # UCNRR data root
UCN_RR_Demo/data/users/                           # UCNRR user snapshots
UCN_RR_Demo/data/dev_logs/ucnrr_forward.log       # UCNRR forwarding log
```

## Environment Files

### Main .env Location

```
/Users/davidmakarewicz/Documents/ReDNA_Demos/.env
```

**This is the primary .env file** used by all services. It contains:
- Core toggles: `PROMOTE_ENABLE_*`, `RR_PROMOTE_MIN_*`
- UCNRR config: `LLM_PROVIDER`, `LLM_MODEL`, `LLM_BASE_URL`
- Service ports and URLs
- Feature flags

### Other .env Files (not actively used)

```
UCN_RR_Demo/.env                                  # Does NOT exist (uses repo root .env)
web/.env.local                                    # Next.js env (NEXT_PUBLIC_* only)
.env.bak                                          # Backup
archive_env/.env.template                         # Template
archive_env/.env.example                          # Example
```

## Service Ports

| Service | Default Port | Env Override |
|---------|-------------|--------------|
| Core API | 8004 | CORE_PORT |
| UCNRR | 8011 | UCNRR_PORT |
| DevX Backend | 8012 | DEVX_PORT |
| Next.js (web) | 3000 | - |
| Ollama | 11434 | - |

## Key Debug Endpoints

### UCNRR Debug Endpoints (NEW)

```
GET  /ucnrr/debug/config     # Effective runtime config, env paths, LLM status
GET  /ucnrr/debug/probe      # LLM connectivity tests (/api/tags, /api/generate)
POST /ucnrr/debug/trace      # End-to-end scoring trace for given text
GET  /health                 # Health check with llm_configured status
GET  /ucnrr/selftest         # Cached selftest with UCN validation
```

### Core Debug Endpoints

```
GET  /core/api/debug/promotion_state  # Active promotion policies (already existed)
POST /core/api/debug/reload_promotions # Reload promotion rules from env
GET  /core/api/debug/envvars          # Show PROMOTE_* env vars
GET  /core/api/debug/resolver         # UCNRR resolver config (NEW)
GET  /health                          # Health check with rr_mode, ucnrr_enabled
GET  /core/api/metrics                # Core metrics (roundtrip hops, etc.)
```

### DevX Backend Endpoints

```
GET  /devx/api/stack/status           # Status of all services
GET  /devx/api/stack/ucnrr/status     # UCNRR-specific status
GET  /metrics/roundtrip               # Roundtrip hop timing metrics
```

## Log Files

### Core Logs

```
/tmp/core_p5.log                      # Main Core log (promotion_eval, promotion_value)
```

### UCNRR Logs

```
data/dev_logs/trace_ucnrr.jsonl       # Roundtrip tracing (if ROUNDTRIP_TRACING_ENABLED)
UCN_RR_Demo/data/dev_logs/ucnrr_forward.log  # Forward events
```

### DevX Logs

```
/tmp/devx_backend.log                 # DevX backend service log
/tmp/nextjs_dev.log                   # Next.js dev server log
```

## Git Branches

- **Current branch**: `feat/cppp_devx_bootstrap`
- **Main branch**: (not specified - typically `main` or `master`)

## Important Constants

### Tier-1 Traits (Precision Allowlist)

```python
TIER1_TRAITS = [
    "PaDNA.HairDNA.Color.Natural",        # RR ≥ 500
    "BasicDNA.Age",                       # RR ≥ 500
    "BasicDNA.RelationshipStatus",        # RR ≥ 540
    "PaDNA.BodyDNA.Height",               # RR ≥ 650
]
```

### Tier-2 Traits (Next Priority)

```python
TIER2_TRAITS = [
    "BehaviorDNA.Sleep.Chronotype",       # RR ≥ 830 (with injector)
    "BasicDNA.Gender",                    # RR TBD
    "BasicDNA.Occupation",                # RR TBD
]
```

### Chronotype Injection

- **Location**: `UCN_RR_Demo/ucnrr_app.py:96-100`
- **Function**: `_maybe_inject_chronotype()`
- **RR Value**: 830.0
- **Patterns**: morning person, early riser, night owl, stay up late, etc.

### Value Normalizers

- **Location**: `ReDNACoreDemo/core/ingest/value_normalizer.py`
- **Functions**:
  - `_normalize_hair()` (line 60)
  - `_normalize_age()` (line 80)
  - `_normalize_rel()` (line 93)
  - `_normalize_height()` (line 103)
  - `_normalize_chronotype()` (line 50)

## Startup Order

Recommended startup sequence:

```bash
# 1. Start Ollama (background daemon)
ollama serve

# 2. Start Core
cd /Users/davidmakarewicz/Documents/ReDNA_Demos
source .venv/bin/activate
CORE_PORT=8004 uvicorn ReDNACoreDemo.core.api:app --host 127.0.0.1 --port 8004

# 3. Start UCNRR
UCNRR_PORT=8011 uvicorn UCN_RR_Demo.ucnrr_app:app --host 127.0.0.1 --port 8011

# 4. Start DevX Backend
DEVX_PORT=8012 DEVX_CORE_BASE=http://127.0.0.1:8004 DEVX_UCNRR_BASE=http://127.0.0.1:8011 \
  uvicorn ReDNACoreDemo.devx.backend.api:app --host 127.0.0.1 --port 8012

# 5. Start Next.js frontend
cd web
npm run dev
```
