# ReDNA Debug Surface

**Version:** 1.1
**Generated:** 2025-10-20
**Updated:** 2025-10-20 (Added authentication requirements)
**Status:** Active in development mode, requires auth in production

## Overview

The ReDNA Debug Surface provides diagnostic endpoints and tools for developers to inspect the internal state of the system, trace data flows, and validate AI-driven decisions. These endpoints **require authentication** via token header or can be disabled entirely for production deployments.

---

## Security & Authentication

### Configuration Flags

**`DEBUG_ROUTES_ENABLED`** (default: `true`)
- Controls whether debug routes are mounted
- Set to `false` in production to completely disable debug endpoints
- When `false`, all debug endpoints return 503

**`X_REDNA_DEBUG_TOKEN`** (default: empty)
- Shared bearer token for debug endpoint authentication
- If empty: no auth required (dev mode, **not safe for production**)
- If set: all requests must include `X-REDNA-DEBUG-TOKEN` header with matching value

### Authentication Model

```bash
# Development mode (no token set)
DEBUG_ROUTES_ENABLED=true
X_REDNA_DEBUG_TOKEN=  # empty = no auth

curl http://127.0.0.1:8004/core/debug/health
# ✅ Allowed

# Production mode (token required)
DEBUG_ROUTES_ENABLED=true
X_REDNA_DEBUG_TOKEN=your-secret-token-here

curl http://127.0.0.1:8004/core/debug/health
# ❌ 403 Forbidden

curl -H "X-REDNA-DEBUG-TOKEN: your-secret-token-here" \
  http://127.0.0.1:8004/core/debug/health
# ✅ Allowed

# Production locked mode (routes disabled)
DEBUG_ROUTES_ENABLED=false

curl -H "X-REDNA-DEBUG-TOKEN: any-token" \
  http://127.0.0.1:8004/core/debug/health
# ❌ 503 Service Unavailable (routes not mounted)
```

### Startup Logging

On server startup, you'll see:

```
[DebugRoutes] enabled=true, guard=disabled   # Dev mode: no auth
[DebugRoutes] enabled=true, guard=token      # Prod: token required
[DebugRoutes] enabled=false, guard=disabled  # Prod: routes disabled
```

---

## Core API Debug Endpoints

**Base URL:** `http://127.0.0.1:8004`
**Auth:** All endpoints require `X-REDNA-DEBUG-TOKEN` header (if token is configured)

### 1. RR Normalization Audit

**Endpoint:** `GET /core/debug/rr_audit/{user_id}?dry_run=true`
**Auth Required:** Yes (if `X_REDNA_DEBUG_TOKEN` is set)

**Purpose:** Audit RR/Curiosity normalization for Phase 9 compliance. Checks for legacy 0-1000 scale values, curiosity formula correctness, and missing RR values.

**Returns:**
```json
{
  "status": "ok",
  "user_id": "ai_ready_probe",
  "dry_run": true,
  "summary": {
    "total_nodes": 150,
    "trait_nodes": 42,
    "nodes_with_issues": 5,
    "critical": 2,
    "warnings": 1,
    "info": 2,
    "would_normalize": 3,
    "would_correct": 2
  },
  "issues": [
    {
      "trait_id": "PaDNA.HairDNA.Color",
      "ucn": {"u": 0.85, "c": 0.92, "n": 0.78},
      "rr_score": 456.78,
      "rr": 456.78,
      "curiosity": 54.32,
      "issue": "rr=456.78 > 100, likely 0-1000 scale (should divide by 10)",
      "severity": "critical"
    }
  ],
  "message": "Found 2 critical RR/Curiosity issues. Apply normalization."
}
```

**Use Cases:**
- Detect legacy 0-1000 scale RR values in user data
- Verify curiosity = 100 - RR formula
- Find missing RR when rr_score is present
- Audit Phase 9 normalization compliance

---

### 2. UCN Propagation Audit

**Endpoint:** `GET /core/debug/ucn_propagation/{user_id}`
**Auth Required:** Yes (if `X_REDNA_DEBUG_TOKEN` is set)

**Purpose:** Audit parent-child UCN propagation consistency. Flags divergences >200 points where Why-Cards should explain AI reasoning (Phase 9 AI-First policy).

**Returns:**
```json
{
  "status": "ok",
  "user_id": "ai_ready_probe",
  "summary": {
    "total_nodes": 150,
    "parent_child_pairs": 8,
    "divergent": 1
  },
  "divergences": [
    {
      "parent_trait_id": "PaDNA.HairDNA",
      "parent_ucn": 650.0,
      "child_ucn_avg": 875.0,
      "child_count": 3,
      "divergence": -225.0,
      "explanation": "Parent UCN (650.0) significantly lower than child avg (875.0). Why-Card should explain contradictions or parent-level discounting."
    }
  ],
  "message": "Found 1 parent-child UCN divergences. Review Why-Cards for explanations."
}
```

**Use Cases:**
- Detect parent-child UCN divergences >200 points
- Flag missing Why-Card explanations
- Validate AI-First propagation policy (not formula-based)
- Audit hierarchical confidence consistency

---

### 3. Debug Health Check

**Endpoint:** `GET /core/debug/health`
**Auth Required:** Yes (if `X_REDNA_DEBUG_TOKEN` is set)

**Purpose:** Health check endpoint that reports debug routes configuration status.

**Returns:**
```json
{
  "status": "healthy",
  "module": "debug",
  "enabled": true,
  "auth_required": true,
  "endpoints": [
    "/core/debug/rr_audit/{user_id}",
    "/core/debug/ucn_propagation/{user_id}",
    "/core/debug/health"
  ]
}
```

**Use Cases:**
- Verify debug routes are enabled
- Check if auth is required
- List available debug endpoints

---

### Future Debug Endpoints (Planned)

The following endpoints are documented in the original DebugSurface.md but **not yet implemented**. They are planned for future phases:

- `GET /core/debug/ontology/stats` - Ontology statistics
- `GET /core/debug/belief/{user_id}` - Belief graph inspector
- `GET /core/debug/provenance/{user_id}/{trait_path}` - Provenance chain tracer
- `GET /core/debug/pipeline/health` - Pipeline health check
- `GET /core/debug/curiosity/{user_id}` - Curiosity engine diagnostics

**Currently Implemented:** 3 endpoints (rr_audit, ucn_propagation, health)

---

### ~~3. Ontology Statistics~~ (Not Yet Implemented)

**Endpoint:** `GET /core/debug/ontology/stats`

**Purpose:** Get summary statistics about the ontology graph structure.

**Returns:**
```json
{
  "version": "2.0",
  "total_nodes": 10,
  "trait_nodes": 5,
  "value_nodes": 0,
  "category_nodes": 6,
  "total_edges": 9,
  "edge_types": {
    "is_parent_of": 9,
    "correlates": 0,
    "contradicts": 0
  },
  "categories": {
    "Physical": 4,
    "Behavioral": 0,
    "Social": 1
  },
  "hierarchy_depth": 2,
  "root_node": "ont_redna_root"
}
```

**Use Cases:**
- Validate Phase 10 hierarchy structure
- Verify ontology loading
- Debug edge relationships
- Inspect category distribution

---

### 4. Belief Graph Inspector

**Endpoint:** `GET /core/debug/belief/{user_id}`

**Purpose:** View the user's complete belief graph structure (nodes + edges).

**Returns:**
```json
{
  "user_id": "ai_ready_probe",
  "belief_graph": {
    "nodes": [
      {
        "node_id": "bg_001",
        "node_type": "trait_belief",
        "trait_id": "PaDNA.HairDNA.Color",
        "value": "Brown",
        "ucn": 850.0,
        "rr": 45.2
      }
    ],
    "edges": [
      {
        "edge_id": "be_001",
        "from_node": "bg_001",
        "to_node": "bg_002",
        "edge_type": "evidence_for",
        "confidence": 0.95,
        "source": "photo_analysis"
      }
    ]
  },
  "stats": {
    "total_nodes": 42,
    "total_edges": 67,
    "evidence_edges": 45,
    "contradiction_edges": 2
  }
}
```

**Use Cases:**
- Visualize belief graph structure
- Debug provenance chains
- Inspect evidence relationships
- Validate graph consistency

---

### 5. Provenance Chain Tracer

**Endpoint:** `GET /core/debug/provenance/{user_id}/{trait_path}`

**Purpose:** Trace the complete provenance chain for a specific trait.

**Returns:**
```json
{
  "trait_path": "PaDNA.HairDNA.Color",
  "value": "Brown",
  "provenance_chain": [
    {
      "step": 1,
      "source": "photo_upload",
      "timestamp": "2025-10-19T14:30:00Z",
      "evidence": "photo_12345.jpg",
      "confidence": 0.95
    },
    {
      "step": 2,
      "source": "head_coach_inference",
      "timestamp": "2025-10-19T14:31:15Z",
      "reasoning": "Hair color appears brown in photo with good lighting",
      "confidence": 0.92
    },
    {
      "step": 3,
      "source": "ucnrr_validation",
      "timestamp": "2025-10-19T14:31:20Z",
      "ucn": 850.0,
      "rr": 45.2,
      "validation_notes": "Confidence validated against source quality"
    },
    {
      "step": 4,
      "source": "core_synthesis",
      "timestamp": "2025-10-19T14:31:25Z",
      "promoted": true,
      "promotion_reason": "UCN 850 > threshold 500"
    }
  ],
  "why_cards": [
    {
      "card_id": "why_hair_001",
      "question": "Why is my hair color marked as Brown?",
      "answer": "Your hair color was identified from a photo you uploaded on Oct 19, 2025..."
    }
  ]
}
```

**Use Cases:**
- Debug trait promotion logic
- Trace evidence through pipeline stages
- Validate Why-Card generation
- Audit timestamp sequencing

---

### 6. Pipeline Health Check

**Endpoint:** `GET /core/debug/pipeline/health`

**Purpose:** Check the health status of all pipeline components.

**Returns:**
```json
{
  "status": "healthy",
  "components": [
    {
      "name": "Core API",
      "status": "healthy",
      "uptime_seconds": 3600,
      "last_request": "2025-10-20T10:45:32Z"
    },
    {
      "name": "Head Coach",
      "status": "healthy",
      "port": 8017,
      "response_time_ms": 45
    },
    {
      "name": "UCN/RR Service",
      "status": "healthy",
      "port": 8018,
      "response_time_ms": 32
    },
    {
      "name": "Curiosity Engine",
      "status": "healthy",
      "port": 8100,
      "response_time_ms": 28
    },
    {
      "name": "Resolver",
      "status": "healthy",
      "port": 8511,
      "response_time_ms": 41
    }
  ],
  "warnings": [],
  "errors": []
}
```

**Use Cases:**
- Monitor service health
- Debug inter-service communication
- Validate response times
- Detect service failures

---

### 7. Curiosity Engine Diagnostics

**Endpoint:** `GET /core/debug/curiosity/{user_id}`

**Purpose:** Inspect the curiosity loop question generation process.

**Returns:**
```json
{
  "user_id": "ai_ready_probe",
  "current_profile_coverage": {
    "total_traits": 42,
    "tier_0_coverage": 1.0,
    "tier_1_coverage": 0.65,
    "tier_2_coverage": 0.42
  },
  "question_candidates": [
    {
      "trait_path": "PaDNA.Exercise.PreferredTime",
      "question": "When do you prefer to exercise?",
      "curiosity_score": 87.5,
      "rationale": "High rarity (12.5%) and ontology neighbor of known Chronotype",
      "strategy": "ontology_guided"
    }
  ],
  "ontology_neighbors": [
    {
      "from_trait": "PaDNA.Chronotype",
      "to_trait": "PaDNA.Exercise.PreferredTime",
      "edge_type": "suggests_question",
      "weight": 0.7
    }
  ]
}
```

**Use Cases:**
- Debug question ranking logic
- Validate ontology-guided exploration
- Inspect curiosity scoring
- Trace question generation strategies

---

## Data File Debugging

### 1. JSONL Audit Logs

**Location:** `data/users/{user_id}/`

**Files:**
- `curiosity.jsonl` - Curiosity loop history
- `evidence.json` - Raw evidence storage
- `resolved.json` - Resolution decisions
- `belief_graph.jsonl` - Belief graph updates (Phase 10)
- `normalize_audit.jsonl` - RR normalization audit trail (Phase 9)
- `why_cards.jsonl` - Why-Card generation log (Phase 7)
- `resolver_traces/` - Detailed resolution traces

**Reading JSONL:**
```bash
# View last 10 curiosity events
tail -n 10 data/users/ai_ready_probe/curiosity.jsonl | jq .

# Inspect normalize audit for a trait
grep "PaDNA.HairDNA.Color" data/users/ai_ready_probe/normalize_audit.jsonl | jq .
```

---

### 2. Ontology Storage

**Location:** `data/ontology/`

**Files:**
- `seed_ontology.json` - Seed ontology (Phase 10 hierarchy)
- `ontology_state.jsonl` - Append-only ontology updates

**Inspection:**
```bash
# View current seed version
jq '.version' data/ontology/seed_ontology.json

# Count nodes and edges
jq '{nodes:(.nodes|length), edges:(.edges|length)}' data/ontology/seed_ontology.json

# List all tier-1 DNA categories
jq '.nodes[] | select(.metadata.tier == 1) | .trait_id' data/ontology/seed_ontology.json
```

---

## Control Panel++ (CPPP) Debug Features

**Port:** 8510
**URL:** `http://127.0.0.1:8510`

### Features:
1. **Nuclear Restart** - Full system reset with diagnostic output
2. **Service Health Dashboard** - Real-time service status
3. **Manifest Inspector** - View workspace configuration
4. **Flag Override Panel** - Runtime flag adjustments
5. **Trace Viewer** - Visual trace of data pipeline flows

---

## Production Safety

### Option 1: Disable Debug Routes Entirely

**Recommended for production:** Completely unmount debug routes.

Add to `.env`:
```bash
DEBUG_ROUTES_ENABLED=false
```

**Effect:**
- All `/core/debug/*` endpoints return 503
- Routes not mounted in FastAPI app
- No attack surface for debug endpoints
- Startup log: `[DebugRoutes] enabled=false, guard=disabled`

### Option 2: Require Authentication

**For staging/internal tools:** Keep routes enabled but require token auth.

Add to `.env`:
```bash
DEBUG_ROUTES_ENABLED=true
X_REDNA_DEBUG_TOKEN=your-secret-token-here
```

**Effect:**
- All `/core/debug/*` endpoints require `X-REDNA-DEBUG-TOKEN` header
- Returns 403 if token missing or invalid
- Startup log: `[DebugRoutes] enabled=true, guard=token`

**Example authenticated request:**
```bash
curl -H "X-REDNA-DEBUG-TOKEN: your-secret-token-here" \
  http://127.0.0.1:8004/core/debug/rr_audit/ai_ready_probe
```

### Production Recommendations

**✅ DO:**
- Set `DEBUG_ROUTES_ENABLED=false` in production
- Use strong random token for staging (e.g., `openssl rand -hex 32`)
- Rotate tokens periodically
- Log all debug endpoint access attempts
- Monitor for 403 errors (potential attacks)

**❌ DON'T:**
- Leave `X_REDNA_DEBUG_TOKEN` empty in production
- Use weak tokens like "debug" or "test"
- Share tokens in public repositories
- Expose debug endpoints to public internet

### What Stays Enabled in Production

Even with `DEBUG_ROUTES_ENABLED=false`, these remain available:
- `/health` - Core API health check (always enabled)
- `/core/graph/ontology` - Ontology GET endpoint (not debug-specific)
- Why-Cards API - User-facing feature
- Core provenance API - Filtered for user safety

---

## Common Debug Workflows

### Workflow 1: Debug UCN/RR Mismatch

1. Audit RR normalization: `GET /core/debug/rr_audit/{user_id}`
2. Check for critical issues in response (RR > 100, curiosity mismatch)
3. Inspect normalize audit: `grep {trait_path} data/users/{user_id}/normalize_audit.jsonl`
4. Verify promotion threshold: Check `.env` for `RR_PROMOTE_MIN_*`

### Workflow 2: Debug Parent-Child UCN Divergence

1. Audit UCN propagation: `GET /core/debug/ucn_propagation/{user_id}`
2. Review divergences > 200 points
3. Check if Why-Cards explain the divergence
4. Inspect AI reasoning in Why-Card content

### Workflow 3: Debug Missing Trait

1. Check ingestion result: `POST /core/ingest` (review response)
2. Audit RR normalization: `GET /core/debug/rr_audit/{user_id}`
3. Check promotion threshold: Trait may be pending due to low RR
4. View pending traits: `GET /core/traits/{user_id}` (includes pending)

### Workflow 4: Debug Ontology Not Loading

1. Check ontology status: `GET /core/graph/ontology`
2. Force reload: `POST /core/graph/ontology/load?force=true`
3. Verify seed file: `jq . data/ontology/seed_ontology.json`
4. Check startup logs for ontology loading errors

---

## Consent Service Health Monitoring

**Phase 10 Addition:** Real-time monitoring of Consent JWT service status.

**Auth:** ⚠️ **NOT AUTH-GUARDED** - This is a public health check endpoint, not a debug endpoint. No token required.

### GET /core/consent/health

**Purpose:** Report Consent service JWT health and configuration status with detailed diagnostics

**Response (200 OK):**
```json
{
  "status": "healthy" | "degraded" | "error",
  "has_secret": true | false,
  "ttl_minutes": 60 | null,
  "roundtrip_ok": true | false,
  "warning": "dev secret in use" | null,
  "error_reason": "specific error message" | null,
  "config": {
    "algorithm": "HS256",
    "secret_encoding": "raw" | "hex" | "base64",
    "leeway_seconds": 30,
    "has_audience": false,
    "has_issuer": false
  }
}
```

**Fields:**
- **status**: Overall health status
  - `"healthy"`: Production secret configured, JWT operations working
  - `"degraded"`: Dev secret in use (functional but insecure)
  - `"error"`: JWT sign/verify roundtrip failed (see `error_reason`)
- **has_secret**: Whether `CONSENT_JWT_SECRET` is set to production value (not dev default)
- **ttl_minutes**: Token TTL from `CONSENT_JWT_TTL_MINUTES`, or `null` if not configured
- **roundtrip_ok**: Whether in-memory JWT sign/verify test passed
- **warning**: Human-readable warning message, or `null` if none
- **error_reason**: Specific diagnostic message when `roundtrip_ok` is `false`, `null` otherwise
  - Examples: `"JWT verify failed: InvalidSignatureError (key or algorithm mismatch)"`
  - Examples: `"Asymmetric algorithm RS256 not supported in health check roundtrip"`
- **config**: Configuration transparency object
  - **algorithm**: JWT algorithm in use (e.g., "HS256")
  - **secret_encoding**: How secret was parsed ("raw", "hex", or "base64")
  - **leeway_seconds**: Clock skew tolerance for token verification
  - **has_audience**: Whether `CONSENT_JWT_AUD` is configured
  - **has_issuer**: Whether `CONSENT_JWT_ISS` is configured

**Configuration:**
```bash
# Development (default)
CONSENT_JWT_SECRET=  # empty = dev default
# Result: status="degraded", warning="dev secret in use"

# Production - Raw String
CONSENT_JWT_SECRET=your-strong-secret-min-32-chars
CONSENT_JWT_TTL_MINUTES=60
# Result: status="healthy", config.secret_encoding="raw"

# Production - Hex-Encoded (auto-detected)
CONSENT_JWT_SECRET=ea7b50ce8665c9e7423b8bbc6ffe702b00257c0a45d839568be8ddaec2833ce8
CONSENT_JWT_TTL_MINUTES=60
# Result: status="healthy", config.secret_encoding="hex"

# Production - Base64-Encoded (requires flag)
CONSENT_JWT_SECRET=6ne1DOZlyed...
CONSENT_JWT_SECRET_B64=true
CONSENT_JWT_TTL_MINUTES=60
# Result: status="healthy", config.secret_encoding="base64"

# Advanced Configuration
CONSENT_JWT_ALG=HS256  # or CONSENT_JWT_ALGORITHM
CONSENT_JWT_LEEWAY_SECONDS=30
CONSENT_JWT_AUD=my-audience  # optional
CONSENT_JWT_ISS=my-issuer    # optional
```

**Performance:**
- No external calls
- In-memory JWT roundtrip only
- Target response time: < 50ms

**Use Cases:**
- DevX System Monitor dashboard
- Production health checks
- Deployment validation
- Security audit verification

**Startup Logging:**
```
[Consent] has_secret=False, ttl_minutes=None
[Consent] ⚠️  dev secret in use
```

**Example:**
```bash
# Check Consent status
curl -s http://127.0.0.1:8004/core/consent/health | jq .

# DevX health aggregator can now poll this instead of guessing
```

**Security Note:** This endpoint does not expose the actual secret value, only whether a production secret is configured.

---

## Notes

- Debug endpoints are **not authenticated** in demo mode
- Production systems should require API keys for debug access
- Trace files can grow large - implement rotation in production
- JSONL audit logs are append-only for integrity
- Phase 9: Normalize audit logs track RR 0-1000 → 0-100 conversions
- Phase 10: Ontology stats should show 10 nodes, 9 edges (ReDNA hierarchy)
- Phase 10: Consent health endpoint provides real-time JWT status monitoring
