# Phase 9: RR Normalization and Reference Population Percentiles

## Overview

Phase 9 introduces **RR normalization** and **reference population percentiles** to ensure consistent, semantically clear metrics across the ReDNA system.

## Canonical Semantics

### RR (Readiness/Reliability)
- **Definition**: Percentile rank (0-100) representing the % of the reference population with **lower UCN** than this user for this trait
- **Scale**: Always 0-100 in API responses
- **Interpretation**: Higher RR = rarer/more confident trait

### Curiosity
- **Definition**: `Curiosity = 100 - RR`
- **Scale**: Always 0-100 in API responses
- **Interpretation**: Inverse of RR; higher curiosity = more uncertainty, more questions to ask

### Legacy RR Scores
- **Internal**: Some modules may still compute RR on 0-1000 scale internally
- **Egress**: All API responses normalize to 0-100 via the RR adapter
- **Backward Compat**: `rr_score` field preserved in schemas; new `rr` and `curiosity` fields added

## Feature Flags

Set these environment variables to control behavior:

```bash
# Enable/disable RR adapter (default: true)
export RR_ADAPTER_ENABLED=true

# Enable/disable reference population percentiles (default: true)
export REFERENCE_POP_ENABLED=true

# Reference population source: "synthetic" or "observed" (default: synthetic)
export REFERENCE_POP_SOURCE=synthetic
```

## API Response Shape

All API endpoints that return trait beliefs now include:

```json
{
  "trait_id": "PaDNA.Chronotype",
  "value": "Morning Lark",

  "rr_score": 800,  // Legacy 0-1000 (backward compat)

  "rr": 80.0,  // NEW: Normalized 0-100 percentile
  "curiosity": 20.0,  // NEW: 100 - rr
  "rr_meta": {  // NEW: Metadata for transparency
    "rr_raw": 800.0,
    "scale": "0_1000",
    "source": "adapter",
    "trait_id": "PaDNA.Chronotype",
    "user_id": "ai_ready_probe"
  }
}
```

## Reference Population

### Synthetic Distributions

Phase 9 ships with synthetic reference distributions for common traits:
- **Chronotype**: Bimodal (early birds / night owls)
- **EyeColor**: Roughly uniform
- **Generic**: Symmetric beta for fallback

Distributions are stored in `data/reference_pop/<trait>.json`:

```json
{
  "samples": [0.05, 0.12, 0.18, ..., 0.92, 0.98],
  "n": 1000,
  "trait_id": "Chronotype"
}
```

### Generating Distributions

```bash
python tools/gen_reference_pop.py --output data/reference_pop --n-samples 1000
```

### Using Observed Distributions

To switch from synthetic to observed distributions:

1. Set `REFERENCE_POP_SOURCE=observed`
2. Collect real UCN distributions from your user population
3. Generate `.json` files with same format as synthetic distributions
4. Place in `data/reference_pop/` directory

## Architecture

### Egress Normalization

RR normalization happens **at API egress only**:
- Internal modules may use 0-1000 scale for historical continuity
- Adapters normalize to 0-100 before returning API responses
- Historical data files (`resolved.json`, `belief_graph.jsonl`) remain unchanged

### Key Modules

1. **`ReDNACoreDemo/core/metrics/rr_adapter.py`**
   - `rr_to_percentile()`: Normalize RR from any scale to 0-100
   - Computes `Curiosity = 100 - RR`
   - Returns metadata for transparency

2. **`ReDNACoreDemo/core/reference_pop/reference_pop.py`**
   - `reference_percentile_for_ucn()`: UCN → percentile lookup
   - `load_distribution()`: Load/cache reference distributions
   - Used when RR scale is `None` or `"reference_percentile"`

3. **`ReDNACoreDemo/core/graph/normalize_egress.py`**
   - `normalize_belief_graph()`: Normalize entire belief graph
   - `normalize_belief_node()`: Normalize individual nodes
   - Wired into graph API at `/core/graph/user/{user_id}`

### Integration Points

**Graph API** (`ReDNACoreDemo/core/graph/api_graph.py`):
```python
from .normalize_egress import normalize_belief_graph

@router.get("/user/{user_id}")
async def get_user_belief_graph(user_id: str) -> BeliefGraph:
    graph = storage.load_user_graph(user_id)
    graph = normalize_belief_graph(graph, user_id)  # Phase 9
    return graph
```

**Schemas** (`ReDNACoreDemo/core/graph/schemas.py`):
```python
class BeliefNode(BaseModel):
    rr_score: Optional[float] = None  # Legacy 0-1000
    rr: Optional[float] = None  # NEW: 0-100 percentile
    curiosity: Optional[float] = None  # NEW: 100 - rr
    rr_meta: Optional[Dict[str, Any]] = None  # NEW: metadata
```

## Testing

### Unit Tests

```bash
# RR adapter tests
pytest tests/metrics/test_rr_adapter.py -v

# Reference population tests
pytest tests/reference_pop/test_percentiles.py -v
```

### Integration Tests

```bash
# Verify normalized RR in graph API
U=ai_ready_probe
curl -s http://127.0.0.1:8004/core/graph/user/$U | jq '
  [.nodes[] | select(.node_type=="trait_belief" and .trait_id=="PaDNA.Chronotype")] | last
  | {rr, curiosity, rr_meta}'

# Expected output:
# {
#   "rr": 80.0,
#   "curiosity": 20.0,
#   "rr_meta": {"rr_raw": 800.0, "scale": "0_1000", ...}
# }
```

## Migration Guide

### For Clients

1. **Start reading `rr` and `curiosity` fields** (0-100) instead of `rr_score`
2. **Use `rr_meta.rr_raw`** if you need the original 0-1000 value
3. **Update any hardcoded thresholds**:
   - Old: `if rr_score > 800` → New: `if rr > 80`
   - Old: `if curiosity < 0.3` → New: `if curiosity < 30`

### For Internal Modules

Phase 9 does **not require** changing internal logic immediately. Modules can:
- Continue computing RR on 0-1000 scale internally
- Rely on egress normalization to handle API responses
- Migrate incrementally to use `rr_adapter.rr_to_percentile()` directly

## Limitations & Future Work

1. **Reference pop**: Currently synthetic; should migrate to observed distributions
2. **Partial egress coverage**: Not all API endpoints normalized yet (see audit report)
3. **UCN → Percentile**: Simple bisect; could use more sophisticated ranking algorithms
4. **Trait-specific distributions**: Only a few common traits have dedicated distributions

## References

- [Phase 9 Audit Report](/tmp/rr_audit_full.txt): Complete list of RR/Curiosity touchpoints
- [RR Adapter Tests](../tests/metrics/test_rr_adapter.py): Normalization test cases
- [Reference Pop Tests](../tests/reference_pop/test_percentiles.py): Percentile test cases
