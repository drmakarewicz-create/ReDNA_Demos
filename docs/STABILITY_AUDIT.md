# Stability Audit — 2025-10-15

Goal: capture the current state of the stability-critical path before adding guardrails.

---

## Imports Hygiene
- Searched `ReDNACoreDemo/core` for absolute `core.*` imports using `rg --pcre2 '(?<!\.)\b(from|import)\s+core\.'`.
- Findings: only legacy backups remain (`ReDNACoreDemo/core/resolver/impl.py.bak`, `ReDNACoreDemo/core/resolver/resolved_io.py.bak`). No active source files import `core.*`.

---

## Endpoint Contracts

### UCNRR Service (`UCN_RR_Demo/ucnrr_app.py`)
- **GET /health** → `200 OK`  
  ```json
  {
    "status": "healthy",
    "service": "ucnrr",
    "version": "dev",
    "llm_configured": false,
    "prompt_sha256": "5947b0ca…6713"
  }
  ```
- **POST /ucn/score**  
  - Good payload (`user_id`, canonical trait) → `200 OK`, `[{"trait_id": "...IrisColor", "ucn": 0.8}]`  
  - Bad payload (empty `user_id`, no items) → `400`, `{"detail": "user_id required"}`
- **GET /ucnrr/selftest** → `200 OK`, `{"ok": true, "ucn": 0.8, "ucn_in_range": true, ...}`
- **GET /metrics** → `200 OK`, includes counters (`rr_requests_total`, `rr_selftest_ok`) and latency summaries (`p50_ms`, `p95_ms`).

### Core Service (`ReDNACoreDemo/core/api.py`)
- **GET /health** → `200 OK`  
  ```json
  {
    "status": "healthy",
    "service": "core",
    "version": "2.0.0",
    "rr_mode": "unavailable",
    "features": {
      "photo_import": true,
      "ucnrr_enabled": false
    }
  }
  ```
- **GET /metrics** → `200 OK`, returns `{ "service": "core", "counters": {}, "gauges": {}, "timers": {} }` (no activity since start).
- **POST /core/api/ingest_evidence**  
  - Good payload (canonical trait evidence) → `200 OK`, `{"ok": true, "ingested": 1, "snapshot": {"traits": [...]}}`  
  - Bad payload (missing `trait_id`) → `400`, `{"ok": false, "error": "EVIDENCE_VALIDATION_FAILED", "bad": [{"index": 0, "error": "NO_CANONICAL_TRAIT_ID"}]}`
- **POST /ui/chat/send** → `400` with missing `text` validation (`{"error": "BAD_REQUEST", "message": "user_id and text are required."}`)

---

## UI Startup
- `web/.env.local` sets `NEXT_PUBLIC_CORE_API_BASE=http://127.0.0.1:8001`.
- No frontend dev server was listening during the audit (`curl 127.0.0.1:4173` failed). First-load request timeline is pending once the Next/Vite dev server is running again.

---

## Ports & Environment
- Active listeners snapshot (`lsof -iTCP -sTCP:LISTEN -nP | head`):
  - Node dev servers on 3101, 3102, 4173 (inactive at the time of curl check).
  - Streamlit apps on 8501/8502.
  - No listeners on 8001 (Core) or 8011 (UCNRR) — smoke script will start them on demand.
- Key environment values:
  - `.env`: `CORE_PORT=8001`, `CORE_BASE=http://127.0.0.1:8001`, `UCNRR_BASE=http://127.0.0.1:8010`, `UCNRR_PORT=8020`.
  - `web/.env.local`: mirrors Core (`CORE_API_URL=http://127.0.0.1:8001`) and UCNRR (`NEXT_PUBLIC_UCNRR_API_BASE=http://127.0.0.1:8011`).
  - Core RR client default (`ReDNACoreDemo/core/rr/client.py`): `RR_URL = os.getenv("RR_URL", "http://127.0.0.1:8011/ucn/score")`.

---

## Notes
- Ingestion pipeline executed end-to-end in-process (FastAPI `TestClient`), including inference side-effects and snapshot writeback.
- Core `/health` currently reports `rr_mode="unavailable"` because UCNRR is not running on the expected port; once UCNRR is up, the new readiness endpoint can enforce alignment.
- UCNRR self-test returns `ok=true` when invoked in-process, establishing the contract target for the forthcoming guardrail test.

---

## Readiness & Logs (Phase 3 preview)
- Core metrics now expose a five-minute rolling window (`errors_5xx_window_5m`, `requests_window_5m`, `latency_p95_ms_window_5m`). The readiness probe treats status as `warming` until the window has meaningful samples (≈ first 60s or first ingress).
- `/devx/api/stack/ready` evaluates rolling error rate (<= 2%) and p95 latency (<= 750 ms), adds fail-condition codes, recovery suggestions, and `unready_since` tracking.
- Supervisor restarts emit `restart_event` rows into `~/.redna/logs/stack.log` via `stack_log`. Core ingestion success/failure and UCNRR self-tests reuse the same unified log channel.
