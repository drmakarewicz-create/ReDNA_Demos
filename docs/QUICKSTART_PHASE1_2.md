# ReDNA Phase 1 & 2 Features — Quickstart Guide

**Last Updated**: 2025-10-14
**Phase 1**: ✅ Complete (Architectural Reliability)
**Phase 2**: 🚧 In Progress (Operational Integrity)

---

## Table of Contents

1. [Overview](#overview)
2. [Phase 1 Features](#phase-1-features)
3. [Phase 2 Features](#phase-2-features)
4. [Quick Start](#quick-start)
5. [Configuration](#configuration)
6. [API Reference](#api-reference)
7. [Monitoring & Observability](#monitoring--observability)
8. [Troubleshooting](#troubleshooting)

---

## Overview

This guide covers the reliability and observability features added in Phases 1 and 2 of the Architecture Reliability Plan.

### What's New

**Phase 1 (Complete)**:
- ✅ Dynamic prompt loading with SHA256 verification
- ✅ Strict validation with actionable error messages
- ✅ UCNRR integration with fallback control
- ✅ Health endpoints with service status

**Phase 2 (In Progress)**:
- ✅ Unified JSON-structured logging
- ✅ Comprehensive metrics tracking
- ✅ `/metrics` endpoint for monitoring
- ⏸️ CP++ Troubleshooter UI (pending)
- ⏸️ CI hardening (pending)

---

## Phase 1 Features

### 1.1 UCNRR AI Activation

**What it does**: Loads UCNRR AI prompt, scores trait confidence, provides self-test capability.

**Endpoints**:
- `GET /health` — Service health + prompt metadata
- `POST /ucn/score` — Score UCN for trait evidence
- `GET /ucnrr/selftest` — Run canonical self-test

**Example**:
```bash
# Check UCNRR health and prompt status
curl -s http://127.0.0.1:8011/health | jq

# Expected output:
# {
#   "status": "healthy",
#   "prompt_sha256": "5947b0ca...",
#   "prompt_version": "1.0",
#   "llm_configured": false
# }

# Score trait confidence
curl -s -X POST http://127.0.0.1:8011/ucn/score \
  -H 'Content-Type: application/json' \
  -d '{
    "user_id": "TEST",
    "items": [
      {
        "trait_id": "PaDNA.EyeDNA.IrisColor",
        "value": {"enum": "blue"},
        "ucn_prior": 0.8,
        "source": "photo_analysis"
      }
    ]
  }' | jq

# Expected output:
# [{"trait_id": "PaDNA.EyeDNA.IrisColor", "ucn": 0.88}]
# Note: Photo analysis gets +10% boost (0.8 * 1.1 = 0.88)

# Run self-test
curl -s http://127.0.0.1:8011/ucnrr/selftest | jq

# Expected output:
# {
#   "ok": true,
#   "test_case": "blue_eyes",
#   "ucn": 0.8,
#   "ucn_in_range": true
# }
```

**Source Reliability Multipliers**:
- Photo/document analysis: **+10%** UCN boost
- User statement/chat: **neutral** (1.0x)
- Inference/third-party: **-30%** UCN reduction

---

### 1.2 Dynamic HC Prompt Loader

**What it does**: Loads Head Coach system prompt from markdown file, enables hot-reload, tracks version via SHA256.

**Endpoints**:
- `GET /health` — Includes `hc_prompt_sha256`, `hc_prompt_version`, `rr_mode`
- `POST /core/admin/reload_prompt` — Hot-reload prompt (dev-only, requires ADMIN_TOKEN)

**Example**:
```bash
# Check Core health with HC prompt info
curl -s http://127.0.0.1:8000/health | jq '{hc_prompt_sha256, hc_prompt_version, rr_mode}'

# Expected output:
# {
#   "hc_prompt_sha256": "a1b2c3d4...",
#   "hc_prompt_version": "2.0",
#   "rr_mode": "online"
# }

# Hot-reload HC prompt (dev mode)
export ADMIN_TOKEN="dev_secret"
curl -s -X POST http://127.0.0.1:8000/core/admin/reload_prompt \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq

# Expected output:
# {
#   "ok": true,
#   "reloaded": true,
#   "new_sha256": "e5f6g7h8...",
#   "new_version": "2.0",
#   "message": "HC prompt reloaded successfully"
# }
```

**Prompt File**: [prompts/head_coach_ai_ingestion_v2.md](../prompts/head_coach_ai_ingestion_v2.md)

**RR Mode Values**:
- `online` — UCNRR is reachable and healthy
- `fallback` — UCNRR unreachable, using prior UCN values
- `unavailable` — UCNRR not configured

---

### 1.3 Strict Validation Pipeline

**What it does**: Fail-closed validation with actionable error messages. Optionally requires UCNRR to be online.

**Configuration**:
```bash
# Enable strict validation (default: false)
export EVIDENCE_STRICT=true

# Require UCNRR to be online (default: false)
export UCNRR_REQUIRED=true
```

**Error Responses**:

#### 400 Validation Error
```bash
# Test invalid evidence (missing trait_id)
curl -s -X POST http://127.0.0.1:8000/ui/chat/send \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"TEST","persona":"head_coach","text":"test"}' | jq

# Expected output (in strict mode):
# {
#   "error": "NO_CANONICAL_TRAIT_ID",
#   "message": "Could not map evidence to canonical trait_id",
#   "evidence_sample": {...},
#   "suggestions": [
#     {"hint": "Use canonical trait ID", "example": "PaDNA.EyeDNA.IrisColor"}
#   ],
#   "strict_mode": true
# }
```

#### 503 UCNRR Required
```bash
# Stop UCNRR service
pkill -f ucnrr_app

# Try to ingest (with UCNRR_REQUIRED=true)
curl -s -X POST http://127.0.0.1:8000/ui/chat/send \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"TEST","persona":"head_coach","text":"I have blue eyes"}' | jq

# Expected output:
# {
#   "error": "UCNRR_REQUIRED",
#   "message": "UCNRR service required but unavailable",
#   "ucnrr_required_mode": true,
#   "action": "Ensure UCNRR service is running or disable UCNRR_REQUIRED mode"
# }
```

---

## Phase 2 Features

### 2.2 Unified Logging & Metrics

**What it does**: Centralized JSON logging and comprehensive metrics for observability.

#### Unified Logging

**Log Directory**: `.run/logs/`

**Log Files**:
- `core.jsonl` — Core API logs (JSON-structured)
- `ucnrr.jsonl` — UCNRR logs (JSON-structured)
- `devx.jsonl` — DevX logs (JSON-structured)

**Log Format**:
```json
{
  "ts": "2025-10-14T23:00:00.123Z",
  "service": "core",
  "level": "INFO",
  "logger": "core.ingest.pipeline",
  "message": "Ingestion complete",
  "user_id": "TEST",
  "req_id": "abc123",
  "event": "ingest_done"
}
```

**Example — Enable JSON Logging**:
```python
from core.logging_config import configure_logging, get_logger, LogContext

# At service startup
configure_logging("core", level="INFO")

# In your code
logger = get_logger(__name__)

# Add context to logs
with LogContext(user_id="TEST", req_id="abc123"):
    logger.info("Processing request")
    # All logs within this block will include user_id and req_id
```

#### Metrics Tracking

**Endpoint**: `GET /metrics`

**Metrics Available**:

**Counters**:
```
ingests.total              # Total ingestion attempts
ingests.success            # Successful ingestions
ingests.errors             # Failed ingestions
ingests.evidence.count     # Total evidence items processed
ingests.inferred.count     # Total inferred traits

errors.4xx                 # Client errors (400-499)
errors.5xx                 # Server errors (500-599)
errors.400.validation      # Validation errors (strict mode)
errors.503.ucnrr_required  # UCNRR unavailable errors

rr.calls                   # Total RR scoring calls
rr.success                 # Successful RR calls
rr.fallback                # Fallback to priors (RR unavailable)
rr.errors                  # RR errors

prompt.reloads             # HC prompt reload count
prompt.load_errors         # Prompt loading errors
```

**Timers** (with p50/p95/p99 percentiles):
```
ingest.duration_ms         # Ingestion pipeline duration
resolve.duration_ms        # Resolution duration
chat.duration_ms           # Chat turn duration
```

**Example — Query Metrics**:
```bash
# Get all metrics
curl -s http://127.0.0.1:8000/metrics | jq

# Expected output:
# {
#   "service": "core",
#   "timestamp": "2025-10-14T23:00:00Z",
#   "uptime_seconds": 3600,
#   "counters": {
#     "ingests.total": 42,
#     "ingests.success": 40,
#     "ingests.errors": 2,
#     "errors.4xx": 1,
#     "errors.503.ucnrr_required": 1
#   },
#   "gauges": {},
#   "timers": {
#     "ingest.duration_ms": {
#       "count": 40,
#       "mean": 125.3,
#       "min": 50,
#       "max": 300,
#       "p50": 120,
#       "p95": 200,
#       "p99": 250
#     }
#   }
# }

# Extract specific metric
curl -s http://127.0.0.1:8000/metrics | jq '.counters["ingests.total"]'
# Output: 42

# Check error rate
curl -s http://127.0.0.1:8000/metrics | \
  jq '.counters | {total: .["ingests.total"], errors: .["ingests.errors"], rate: (.["ingests.errors"] / .["ingests.total"])}'
# Output: {"total": 42, "errors": 2, "rate": 0.047619}
```

**Example — Add Metrics to Your Code**:
```python
from core.metrics import METRICS, MetricNames, Timer

# Increment counters
METRICS.increment(MetricNames.INGESTS_TOTAL)
METRICS.increment(MetricNames.ERRORS_4XX)

# Set gauges
METRICS.set_gauge("queue.depth", 42)

# Time operations
with Timer(METRICS, "operation.duration_ms"):
    # ... perform operation ...
    pass

# Manual timing
METRICS.record_time("custom.duration_ms", 123.5)
```

---

## Quick Start

### Prerequisites

```bash
# Ensure services are running
cd /path/to/ReDNA_Demos

# Start UCNRR (terminal 1)
cd UCN_RR_Demo
../.venv/bin/python -m uvicorn ucnrr_app:app --port 8011 --reload

# Start Core API (terminal 2)
cd ReDNACoreDemo
../.venv/bin/python -m uvicorn core.api:build_app --factory --port 8000 --reload
```

### Verify Installation

```bash
# Check UCNRR health
curl -s http://127.0.0.1:8011/health | jq '.status, .prompt_sha256'

# Check Core health
curl -s http://127.0.0.1:8000/health | jq '.status, .hc_prompt_sha256, .rr_mode'

# Run UCNRR self-test
curl -s http://127.0.0.1:8011/ucnrr/selftest | jq '.ok, .ucn'

# Check metrics
curl -s http://127.0.0.1:8000/metrics | jq '.service, .uptime_seconds'
```

### Test Ingestion Flow

```bash
# Normal ingestion (permissive mode)
curl -s -X POST http://127.0.0.1:8000/ui/chat/send \
  -H 'Content-Type: application/json' \
  -d '{
    "user_id": "TEST",
    "persona": "head_coach",
    "text": "I have blue eyes",
    "client_ts": 1697400000000
  }' | jq '.reply_text'

# Check metrics after ingestion
curl -s http://127.0.0.1:8000/metrics | jq '.counters | {total: .["ingests.total"], success: .["ingests.success"]}'
```

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| **Phase 1** |||
| `EVIDENCE_STRICT` | `false` | Enable fail-closed validation (400 on invalid evidence) |
| `UCNRR_REQUIRED` | `false` | Block ingestion when UCNRR unavailable (503) |
| `ADMIN_TOKEN` | `None` | Token for `/core/admin/*` endpoints (dev-only) |
| `RR_URL` | `http://127.0.0.1:8011/ucn/score` | UCNRR scoring endpoint |
| `RR_TIMEOUT` | `2.5` | UCNRR request timeout (seconds) |
| **Phase 2** |||
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG/INFO/WARNING/ERROR) |
| `LOG_DIR` | `.run/logs` | Unified log directory |

### Strict Mode Configuration

**Development** (permissive, with fallback):
```bash
export EVIDENCE_STRICT=false
export UCNRR_REQUIRED=false
```

**Production** (strict, fail-closed):
```bash
export EVIDENCE_STRICT=true
export UCNRR_REQUIRED=true
export ADMIN_TOKEN="your-secret-token-here"
```

---

## API Reference

### UCNRR Endpoints

#### `GET /health`
Returns service health and prompt metadata.

**Response**:
```json
{
  "status": "healthy",
  "service": "ucnrr",
  "version": "dev",
  "timestamp": "2025-10-14T23:00:00Z",
  "prompt_sha256": "5947b0ca...",
  "prompt_version": "1.0",
  "llm_provider": "none",
  "llm_configured": false
}
```

#### `POST /ucn/score`
Score UCN for trait evidence.

**Request**:
```json
{
  "user_id": "TEST",
  "items": [
    {
      "trait_id": "PaDNA.EyeDNA.IrisColor",
      "value": {"enum": "blue"},
      "ucn_prior": 0.8,
      "source": "photo_analysis"
    }
  ]
}
```

**Response**:
```json
[
  {
    "trait_id": "PaDNA.EyeDNA.IrisColor",
    "ucn": 0.88
  }
]
```

#### `GET /ucnrr/selftest`
Run canonical self-test.

**Response**:
```json
{
  "ok": true,
  "test_case": "blue_eyes",
  "trait_id": "PaDNA.EyeDNA.IrisColor",
  "ucn": 0.8,
  "ucn_expected_range": [0.75, 0.95],
  "ucn_in_range": true,
  "elapsed_ms": 0,
  "prompt_sha256": "5947b0ca...",
  "llm_configured": false
}
```

### Core Endpoints

#### `GET /health`
Returns service health, HC prompt metadata, and RR mode.

**Response**:
```json
{
  "status": "healthy",
  "service": "core",
  "version": "1.0.0",
  "timestamp": "2025-10-14T23: