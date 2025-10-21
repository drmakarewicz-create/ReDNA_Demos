# Phase 9: Shape Harmonizer

**Status:** Implemented (ingress-only, reversible, flag-gated)
**Goal:** Normalize incoming payloads to prevent field/namespace drift from breaking demos.

## Overview

The Shape Harmonizer is a minimal, flag-gated normalization layer that runs on **ingress only** (POST /core/api/ingest_evidence). It does NOT rewrite historical files - only normalizes the incoming request before validation and persistence.

This prevents field/namespace drift issues like:
- `from` vs `source` vs `start` for edge sources
- `traitId` vs `trait_id` for trait identifiers
- `BehaviorDNA.Sleep.Chronotype` vs `PaDNA.Chronotype` namespace inconsistencies

## Key Features

### 1. Field Aliasing

Maps variant field names to canonical forms:

**Evidence fields:**
- `traitId` → `trait_id`

**Edge fields:**
- `source`, `start` → `from`
- `target`, `dest`, `destination` → `to`
- `type`, `relation` → `edge_type`

**Node fields:**
- `kind` → `node_type`
- `traitId` → `trait_id`

### 2. Namespace Normalization

Uses the existing trait alias system ([ReDNACoreDemo/core/graph/aliases.py](../ReDNACoreDemo/core/graph/aliases.py)) to normalize trait namespaces:

- `BehaviorDNA.Sleep.Chronotype` → `PaDNA.Chronotype`
- Future aliases can be added to `aliases.py` without changing harmonizer code

### 3. Default Filling

Adds minimal required fields if missing:
- `timestamp`: Current UTC timestamp
- `provenance.source`: Defaults to "unknown"

### 4. Audit Trail

All normalizations are logged to `data/users/<user_id>/normalize_audit.jsonl`:

```json
{
  "timestamp": "2025-10-19T16:00:00Z",
  "user_id": "ai_ready_probe",
  "req_id": "ui",
  "item_index": 0,
  "mutated": true,
  "audit": {
    "changed_keys": ["traitId→trait_id"],
    "alias_hits": ["traitId"],
    "namespace": "BehaviorDNA.Sleep.Chronotype→PaDNA.Chronotype",
    "defaults_added": ["timestamp", "provenance.source"]
  }
}
```

## Configuration Flags

All flags are environment variables with safe defaults:

| Flag | Default | Description |
|------|---------|-------------|
| `SHAPE_HARMONIZER` | `off` | Enable/disable the harmonizer |
| `SHAPE_HARMONIZER_DRYRUN` | `on` | Dry-run mode (audit only, no mutations) |

### Usage Examples

**Start with dry-run (safe, no behavior change):**
```bash
export SHAPE_HARMONIZER=on
export SHAPE_HARMONIZER_DRYRUN=on
# Audit trail written, but payloads unchanged
```

**Enable mutations:**
```bash
export SHAPE_HARMONIZER=on
export SHAPE_HARMONIZER_DRYRUN=off
# Payloads normalized before validation
```

**Disable harmonizer:**
```bash
export SHAPE_HARMONIZER=off
# Harmonizer skipped entirely
```

## Integration Points

### Ingress Hook

The harmonizer runs in [ReDNACoreDemo/core/api.py](../ReDNACoreDemo/core/api.py) at line ~7849, **before Pydantic validation**:

```python
# Phase 9: Shape Harmonizer - normalize incoming evidence before validation
from ReDNACoreDemo.core.graph.shape_harmonizer import (
    is_harmonizer_enabled,
    should_mutate,
    normalize_evidence_batch,
)

if is_harmonizer_enabled():
    mutate = should_mutate()
    items, harmonizer_audits = normalize_evidence_batch(items, mutate=mutate, audit=True)
    # Write audit trail to normalize_audit.jsonl
    ...
```

### No Historical Rewrites

The harmonizer is **ingress-only** and **reversible**:
- Does NOT rewrite existing JSONL files
- Does NOT modify stored graphs retroactively
- Can be disabled at any time by setting `SHAPE_HARMONIZER=off`

### Compatibility with Read-Time Aliasing

The harmonizer normalizes on **write** (ingress), while the alias system from Prompt 1 handles **read** (egress):

- **Write:** `BehaviorDNA.Sleep.Chronotype` → stored as `PaDNA.Chronotype`
- **Read:** Query with either `PaDNA.Chronotype` or `BehaviorDNA.Sleep.Chronotype` returns both

Both systems use the same [aliases.py](../ReDNACoreDemo/core/graph/aliases.py) mapping.

## Reading the Audit Trail

### Find Audit File

```bash
cat data/users/<user_id>/normalize_audit.jsonl | jq '.'
```

### Filter by Mutation Status

```bash
# See what would change in dry-run
jq 'select(.mutated == false)' data/users/<user_id>/normalize_audit.jsonl

# See actual mutations
jq 'select(.mutated == true)' data/users/<user_id>/normalize_audit.jsonl
```

### Check Specific Changes

```bash
# Find namespace changes
jq 'select(.audit.namespace != null)' data/users/<user_id>/normalize_audit.jsonl

# Find field aliasing
jq 'select(.audit.changed_keys | length > 0)' data/users/<user_id>/normalize_audit.jsonl
```

## Testing

See [tests/graph/test_harmonizer.py](../tests/graph/test_harmonizer.py) for comprehensive tests:

- Unit tests for field aliasing, namespace normalization, defaults
- Batch normalization tests
- Flag behavior tests
- Acceptance criteria tests (AC1-AC3)

Run tests:
```bash
pytest tests/graph/test_harmonizer.py -v
```

## Acceptance Criteria

✅ **AC1:** With `SHAPE_HARMONIZER=on` and `DRYRUN=on`, ingesting differently-shaped payloads does not change behavior; audit lines are written showing proposed normalizations.

✅ **AC2:** With `DRYRUN=off`, ingesting the same three payloads results in identical persisted graph (same node/edge ops) and promotions succeed.

✅ **AC3:** BehaviorDNA Chronotype evidence is normalized to PaDNA.Chronotype in the stored ops, while Why-Cards/aliases continue to resolve as before (read-time aliasing still works).

## Implementation Files

- [ReDNACoreDemo/core/graph/shape_harmonizer.py](../ReDNACoreDemo/core/graph/shape_harmonizer.py) - Core normalization logic
- [ReDNACoreDemo/core/api.py](../ReDNACoreDemo/core/api.py) - Ingress hook (line ~7849)
- [ReDNACoreDemo/core/graph/aliases.py](../ReDNACoreDemo/core/graph/aliases.py) - Trait namespace mappings (shared with Prompt 1)
- [tests/graph/test_harmonizer.py](../tests/graph/test_harmonizer.py) - Comprehensive test suite

## Future Enhancements

Potential extensions (not in current scope):

- Additional field aliases as needed
- Trait value normalization ("Morning Lark" → "morning")
- Historical file migration tool (separate opt-in script)
- Harmonizer metrics dashboard

## Rollback

To disable the harmonizer:

```bash
export SHAPE_HARMONIZER=off
# Or remove the env vars entirely
```

Historical data remains unchanged. Audit trails are preserved for analysis.
