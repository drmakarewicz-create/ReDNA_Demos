# ReDNA System Architecture Reality Check
**Date**: 2025-10-14
**Status**: AS-BUILT (not as-designed)

This document describes the ReDNA system **as it currently exists in running code**, not as designed on paper.

---

## 🧩 1. Service Overview

### 1.1 Currently Running Services

| Service | Process | Port | Status |
|---------|---------|------|--------|
| **Core API** | `uvicorn ReDNACoreDemo.core.api:build_app --factory --port 8015` | 8015 | ✅ Running |
| **UCNRR Service** | `uvicorn ucnrr_app:app --host 0.0.0.0 --port 8011 --reload` | 8011 | ✅ Running |
| **Northstar UI** | Next.js dev server | 3000 | ✅ Running |
| **CP++ (Control Panel)** | `streamlit run control_panel_plus_plus.py` | 8501 | ✅ Running (2 instances) |

### 1.2 Service Startup Methods

**Core API**:
```bash
python3 -m uvicorn ReDNACoreDemo.core.api:build_app --factory --port 8015
```
- Factory pattern (`build_app()` function)
- No auto-reload by default
- Logs to stdout (piped to `/tmp/uvicorn.log` if nohup)

**UCNRR**:
```bash
python3 -m uvicorn ucnrr_app:app --host 0.0.0.0 --port 8011 --reload
```
- Direct app instance
- Auto-reload enabled (`--reload`)
- Binds to all interfaces (0.0.0.0)

**Northstar UI**:
```bash
cd web && npm run dev
```
- Next.js development server
- Hot reload enabled
- Proxies API calls to Core (port 8015)

**CP++**:
```bash
cd PhotoRefinementCoach && streamlit run control_panel_plus_plus.py
```
- Streamlit app
- Multiple instances running (legacy issue)
- Manages Core and UCNRR startup

### 1.3 Dependencies

**Core requires**:
- No external services (self-contained)
- Optional: UCNRR service for RR scoring (falls back to priors if unavailable)

**UCNRR requires**:
- No external services
- **CRITICAL**: Does NOT currently load any AI model/prompt

**Northstar UI requires**:
- Core API running on port 8015

**CP++ requires**:
- Core API running (monitors via health endpoint)
- UCNRR API running (monitors via health endpoint)

---

## 🧠 2. Head Coach (Northstar)

### 2.1 Current System Prompt

**Location**: None explicitly loaded

The HC uses default LLM behavior with conversation history. There is **NO system prompt file currently being loaded** into the HC agent.

**New prompt exists but not integrated**: `prompts/head_coach_ai_ingestion_v2.md` (created but not wired up)

### 2.2 HC Data Flow

**Current Reality**:
```
User types message in Northstar UI
  ↓
POST /ui/chat/send (Core API)
  ↓
LLM extractors (preference_extractor, conversation_analyzer)
  ↓
Fallback lexical extractor (if primary returns 0)
  ↓
ingest_evidence_roundtrip() called
  ↓
[RESOLVER CRASHES HERE - Import error]
  ↓
Exception caught, logged
  ↓
Chat response returned (user sees nothing wrong)
```

**HC does NOT call**:
- `/core/api/ingest_text` directly
- `/core/api/ingest_evidence` directly
- UCNRR endpoints directly

Instead, it calls internal Python function `ingest_evidence_roundtrip()` which is supposed to handle everything.

### 2.3 UCNRR Integration

**Reality**: HC/Core does **NOT** directly call UCNRR during chat ingestion.

**What Core calls**:
```python
# In resolver/impl.py (line 14 tries to import but fails)
from .rr.client import score_ucn_safe

# Which calls:
POST http://127.0.0.1:8011/ucn/score  # ❌ DOES NOT EXIST
```

**Actual UCNRR endpoints**:
- `/health` ✅ Exists
- `/users/list` ✅ Exists
- `/ingest_text` ✅ Exists (but unused)
- `/api/rescore` ✅ Exists (but unused)
- `/ucn/score` ❌ **MISSING** (this is what Core expects!)

### 2.4 Evidence Schema from HC

**Current extraction output**:
```json
{
  "trait_id": "attributes.physical.eye_color",
  "fact_value": "blue",
  "confidence": 100,
  "raw_text": "I have blue eyes",
  "timestamp": "2025-10-14T18:20:17.488000+00:00",
  "extraction_method": "llm",
  "signal": "physical.eye_color: blue"
}
```

**Note**: Uses legacy `fact_value` instead of canonical `value: {enum: "blue"}`

---

## 🔬 3. UCNRR Service

### 3.1 AI Model/Prompt Loading

**❌ REALITY**: UCNRR does **NOT** load any AI model or prompt on startup.

**Evidence**:
- No `anthropic`, `claude`, `openai` imports
- No prompt file loading
- Comment in code: `# Your real model should parse text` (line 94)
- Current implementation: Simple string matching and keyword detection

### 3.2 Actual UCNRR Endpoints

| Endpoint | Method | Purpose | Used By |
|----------|--------|---------|---------|
| `/health` | GET | Health check | CP++ |
| `/users/list` | GET | List all users | CP++ |
| `/users/init` | POST | Initialize user storage | CP++ |
| `/ingest_text` | POST | Ingest raw text | **UNUSED** |
| `/api/rescore` | POST | Rescore traits (Northstar Phase 2) | **UNUSED** |
| `/legacy_import` | POST | Export user traits | **UNUSED** |
| `/ucn/score` | POST | Score UCN for traits | **MISSING** ❌ |

### 3.3 Is UCNRR Called from Core?

**NO** - Currently BYPASSED due to missing endpoint.

**Intended call path** (from `resolver/impl.py` → `rr/client.py`):
```python
RR_URL = os.getenv("RR_URL", "http://127.0.0.1:8011/ucn/score")

def score_ucn(user_id, items):
    response = requests.post(RR_URL, json={...})  # ❌ 404 Not Found
```

**Actual behavior**:
```python
def score_ucn_safe(...):
    try:
        scores = score_ucn(...)  # Fails
    except Exception:
        # ALWAYS takes this path
        scores = [{"trait_id": item["trait_id"], "ucn": item["ucn_prior"]}]
        return scores, False  # rr_ok = False
```

**Result**: All UCN scores use fallback priors (default 0.2), UCNRR is never invoked.

### 3.4 UCNRR Output Format

**When `/api/rescore` is called** (currently never):
```json
{
  "ok": true,
  "user_id": "...",
  "rr_by_trait": {
    "BasicDNA.Age": 95.0,
    "BasicDNA.Gender": 85.0
  },
  "curiosity_by_trait": {
    "BasicDNA.Age": 15.0,
    "BasicDNA.Gender": 20.0
  },
  "traits_updated": 2,
  "timestamp": "2025-10-14T..."
}
```

**What Core expects** (from `/ucn/score`):
```json
[
  {"trait_id": "PaDNA.EyeDNA.IrisColor", "ucn": 0.75},
  {"trait_id": "BasicDNA.Age", "ucn": 0.85}
]
```

**Schema mismatch**: Even if endpoint existed, format doesn't match Core's expectation.

### 3.5 UCNRR AI Usage Logs

**None** - Because UCNRR doesn't use any AI.

**What UCNRR actually does**:
```python
# ucnrr_app.py:153-170
if "25" in text or "age" in text_lower:
    rr_by_trait["BasicDNA.Age"] = 95.0

if "love" in text_lower or "enjoy" in text_lower:
    rr_by_trait["InterestDNA.Hobbies"] = 70.0
```

Simple keyword matching, no LLM involved.

---

## ⚙️ 4. Core (Resolution and Storage)

### 4.1 Actual Ingestion Flow

**CURRENT (BROKEN) FLOW**:
```
User: "I am 6 feet tall"
  ↓
Northstar UI → POST /ui/chat/send
  ↓
[ReDNACoreDemo/core/api.py:2800-2920]
  ↓
LLM Extraction (preference_extractor.extract_from_message)
  Returns: [{trait_id: "attributes.physical.height", fact_value: "6 feet tall", ...}]
  ↓
Fallback check (if 0 items, runs fallback_lex)
  ↓
Call ingest_evidence_roundtrip(user_id, source="chat", evidence=[...], req_id)
  ↓
[ReDNACoreDemo/core/ingest/pipeline.py:20-138]
  ↓
Canonicalize trait IDs (trait_id_mapper)
  ↓
Validate schema (evidence_schema)
  ↓
Store evidence to evidence.json ✅
  ↓
Call _resolve_direct(user_id, evidence, req_id)
  ↓
[ReDNACoreDemo/core/ingest/pipeline.py:184]
  from ..resolver.impl import resolve_roundtrip
    ↓
  [ReDNACoreDemo/core/resolver/__init__.py:7]
    from .impl import resolve_roundtrip  ← Fixed in __init__.py
      ↓
    [ReDNACoreDemo/core/resolver/impl.py:14]
      from core.resolver.contracts import Evidence  ← ❌ CRASHES HERE
      ↓
ModuleNotFoundError: No module named 'core.resolver'
  ↓
Exception caught in api.py:2910
  ↓
CRITICAL error logged
  ↓
resolved.json NEVER UPDATED ❌
  ↓
Chat response returned to user ✅ (user doesn't see error)
```

### 4.2 Key Functions

**Entry point**: `chat_send()` - `api.py:2766-2920`

**Extraction**:
- `preference_extractor.extract_from_message()` - LLM-based
- `conversation_analyzer.analyze_conversation()` - Keyword-based
- `fallback_lex.fallback_extract()` - Regex patterns

**Ingestion**: `ingest_evidence_roundtrip()` - `ingest/pipeline.py:20-138`

**Resolution**: `resolve_roundtrip()` - `resolver/impl.py:26-150` (NEVER REACHED due to import error)

**Inference**: `run_inference()` - `traits/inference_engine.py:13-79` (NEVER REACHED)

### 4.3 UCNRR in the Flow?

**NO** - Even if resolver ran, UCNRR call would fail:

```python
# In resolver/impl.py:105-130 (never reached)
from .rr.client import score_ucn_safe

scores, rr_ok = score_ucn_safe(user_id, items)
# Always returns rr_ok=False due to missing /ucn/score endpoint
# Falls back to using ucn_prior values (0.2 default)
```

### 4.4 Inference Triggers

**When**: After first resolution pass completes

**Condition**: `if ev_inf_raw:` (if inference engine returns proposals)

**Currently**: **NEVER RUNS** because resolver crashes before reaching inference step.

**If it worked**:
```python
# pipeline.py:82-120
ev_inf_raw = run_inference(ev2)  # Check blue eyes → infer freckles
if ev_inf_raw:
    # Filter by UCN threshold (0.3)
    # Store inferred traits
    # Re-resolve with inferences included
```

### 4.5 UCN Determination

**Current Reality**:
1. Uses `ucn_prior` from evidence (default 0.2)
2. RR service is NEVER successfully called
3. All traits get UCN = 0.2 (their prior)

**Intended**:
1. Evidence has `ucn_prior` (initial guess)
2. RR service analyzes trait relationships
3. RR returns computed UCN score (could be higher or lower)
4. Resolved trait stores final UCN

**Example** (if it worked):
```
Evidence: eye_color=blue, ucn_prior=0.2
  ↓
RR service: Analyzes user's history, other traits, confidence patterns
  ↓
RR returns: ucn=0.75 (higher confidence after relational analysis)
  ↓
Resolved: eye_color=blue, ucn=0.75
```

---

## 💾 5. Data Layer and Schema

### 5.1 Current Canonical Evidence Schema

**What extractor produces**:
```json
{
  "trait_id": "attributes.physical.eye_color",
  "fact_value": "blue",
  "confidence": 100,
  "raw_text": "I have blue eyes",
  "timestamp": "2025-10-14T...",
  "extraction_method": "llm",
  "signal": "physical.eye_color: blue"
}
```

**What pipeline expects**:
```json
{
  "trait_id": "PaDNA.EyeDNA.IrisColor",
  "value": {"enum": "blue"},
  "source": "chat",
  "ts": "2025-10-14T...",
  "ucn_prior": 0.2
}
```

**What gets stored in evidence.json** (after validation):
```json
{
  "trait_id": "PaDNA.EyeDNA.IrisColor",
  "confidence": 100,
  "raw_text": "I have blue eyes",
  "timestamp": "2025-10-14T18:20:17.488000+00:00",
  "extraction_method": "llm",
  "signal": "physical.eye_color: blue",
  "value": {"enum": "blue"},
  "source": "chat",
  "ts": "2025-10-14T18:20:23+00:00"
}
```

### 5.2 Typical resolved.json (Currently)

**Broken state** (resolver never runs):
```json
{
  "profile": {
    "label": "OB10",
    "created_ts": "2025-10-14T18:19:31.330057+00:00"
  }
}
```

**Expected state** (if resolver worked):
```json
{
  "profile": {
    "label": "OB10",
    "created_ts": "2025-10-14T18:19:31.330057+00:00"
  },
  "PaDNA.EyeDNA.IrisColor": {
    "value": {"enum": "blue"},
    "ucn": 0.2,
    "sources": ["chat"],
    "status": "resolved",
    "last_updated": "2025-10-14T18:20:23+00:00"
  },
  "PaDNA.SkinDNA.Freckles": {
    "value": {"enum": "higher_likelihood"},
    "ucn": 0.2,
    "sources": ["chat:inference"],
    "status": "inferred",
    "last_updated": "2025-10-14T18:20:23+00:00"
  }
}
```

### 5.3 Trait History

**Currently**: Only stores latest value per trait_id

**evidence.json**: Append-only history (all values preserved)

**resolved.json**: Latest snapshot (single value per trait)

### 5.4 trait_id_map.json Usage

**Location**: `ReDNACoreDemo/core/traits/trait_id_map.json`

**Used by**: `trait_id_mapper.canonicalize()` in pipeline

**Purpose**: Maps legacy/alternative trait IDs to canonical IDs

**Example mappings**:
```json
{
  "attributes.physical.eye_color": "PaDNA.EyeDNA.IrisColor",
  "attributes.physical.hair_color": "PaDNA.HairDNA.Color.Natural",
  "attributes.physical.height": "PaDNA.BodyDNA.Height",
  "attributes.age": "BasicDNA.Age"
}
```

**Currently working**: ✅ Canonicalization step runs before resolver crash

### 5.5 Dropped Traits?

**Yes** - Traits are being dropped due to resolver crash:

1. Evidence stored correctly ✅
2. Canonicalization works ✅
3. Resolver crashes ❌
4. resolved.json never updated ❌
5. **ALL traits lost** from user perspective (UI shows nothing)

---

## 🧰 6. Observability and Logging

### 6.1 Active Logs

| Log File | Content | Status |
|----------|---------|--------|
| `/tmp/core_pipeline.log` | Application logs (INFO, ERROR) | ✅ Active |
| `/tmp/uvicorn.log` | HTTP access logs | ✅ Active (if nohup used) |
| `/tmp/uvicorn_new.log` | Latest restart logs | ✅ Active |
| UCNRR logs | No dedicated log file | ❌ Stdout only |

### 6.2 UCNRR Logs

**Currently**: UCNRR has NO dedicated log file

**Where logs go**: Stdout (lost unless captured)

**What UCNRR logs**:
```python
# ucnrr_app.py:85-91, 137-143
_write_json(udir / f"llmdebug_{timestamp}.json", log)
_write_json(udir / f"rescore_{timestamp}.json", log)
```

Files written to `data/storage/{user_id}/` but never rotated or monitored.

### 6.3 Resolver Exception Logging

**Current behavior**:
```python
# api.py:2909-2911
except Exception as e:
    logger.exception(f"CRITICAL: Failed to process chat evidence...")
    logger.error(f"Evidence that failed: {all_observations[:2]}")
```

**Where logged**: `/tmp/core_pipeline.log`

**What's captured**:
- Full stack trace ✅
- User ID ✅
- Request ID ✅
- Sample evidence (first 2 items) ✅

**Example**:
```
2025-10-14 14:53:42,979 - CRITICAL: Failed to process chat evidence for user ob10, req_id=fe535d58
Traceback (most recent call last):
  ...
ModuleNotFoundError: No module named 'core.resolver'
```

### 6.4 Key Log Prefixes

| Prefix | Meaning | File |
|--------|---------|------|
| `chat_extract{req_id=..., items=N}` | Extraction completed | api.py:2890 |
| `chat_store{req_id=..., count=N}` | Evidence stored | pipeline.py:157 |
| `chat_resolve{wrote_resolved=true}` | Resolver succeeded | api.py:2918 |
| `ingest_start{req_id=..., items_in=N}` | Pipeline started | pipeline.py:31 |
| `ingest_done{wrote_resolved=true}` | Pipeline completed | pipeline.py:135 |
| `CRITICAL: Failed to process` | Pipeline crashed | api.py:2910 |

### 6.5 Live Metrics

**Currently**: ❌ No metrics collection

**What exists**: None

**What's needed**:
- Extraction rate (items/message)
- Ingestion success rate (%)
- Resolver success rate (%)
- Average UCN scores
- Pipeline latency (ms)

---

## 🧱 7. DevX and CP++

### 7.1 CP++ Control Mechanism

**Current Reality**: CP++ does NOT directly control Core/UCNRR startup

**What CP++ does**:
- Monitors health endpoints (`/health`)
- Displays service status
- **User manually starts services** separately

**No automated**:
- Service startup
- Process management
- Auto-restart on crash

### 7.2 Health Checks

**Core**:
```bash
GET http://127.0.0.1:8015/health
```
Returns: `{status: "healthy", service: "core", version: "2.0.0", features: {...}}`

**UCNRR**:
```bash
GET http://127.0.0.1:8011/health
```
Returns: `{ok: true, service: "ucnrr", version: "ucnrr-demo/1.1.0", endpoints: [...]}`

**No deep health checks** - doesn't verify:
- Resolver module loads correctly
- RR service reachable
- AI models loaded
- Data directories writable

### 7.3 UCNRR Startup Logging

**CP++ does NOT log UCNRR startup** because it doesn't start it.

Services are started manually in separate terminals.

### 7.4 Missing UCNRR Prompt Awareness

**CP++ has NO visibility into**:
- Whether UCNRR loaded an AI model
- What prompts are active
- RR service connectivity
- Pipeline success rates

**Would need**:
- `/health/deep` endpoint that checks all dependencies
- Prompt version in health response
- Last successful RR call timestamp

### 7.5 DevX Interaction with Core

**No DevX service** currently running.

**Path mentioned in code**: `ReDNACoreDemo/devx/backend/api.py` exists but not running.

**If it existed**, would provide:
- Trait inspection UI
- Log aggregation
- Pipeline visualization
- Test data injection

---

## 🔒 8. Current Weak Points

### 8.1 Silent Failure Points

1. **Resolver import error** (CRITICAL)
   - Evidence stored ✅
   - Resolver crashes ❌
   - Exception caught, logged
   - User sees nothing wrong
   - NO traits ever resolved

2. **UCNRR endpoint mismatch**
   - Core expects `/ucn/score` ❌
   - UCNRR provides `/api/rescore` ✅
   - Falls back to priors