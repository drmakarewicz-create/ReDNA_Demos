# 🚀 Quick Start — Phase 1 Implementations

**Last Updated:** 2025-10-10

## Overview

Two major Phase 1 systems are now available:

1. **Trait Refinement Depth** — Probabilistic trait reconciliation
2. **Jarvis-Codex Interface** — Guarded UI edit proposals

---

## Trait Refinement Depth

### Quick Usage

```python
from ReDNACoreDemo.core.refinement.refinement_resolver import create_refinement_resolver

# Initialize resolver
resolver = create_refinement_resolver()

# Resolve proposals
proposals = [
    {
        "trait": "python_fluency",
        "value": 0.85,
        "confidence": 0.75,
        "source": "chatdna_coach",
        "ts": "2025-10-10T00:00:00Z"
    }
]

outcomes = resolver.resolve_proposals("user_id", proposals)

# Check results
for outcome in outcomes:
    print(f"{outcome.trait}: {outcome.action}")
    print(f"  UCN: {outcome.prior['ucn']:.2f} → {outcome.resolved['ucn']:.2f}")
```

### API Endpoints

```bash
# Resolve proposals
curl -X POST http://localhost:8015/refinement/resolve \
  -H "Content-Type: application/json" \
  -d '{"user_id":"TEST","proposals":[...]}'

# List conflicts
curl http://localhost:8015/refinement/conflicts?user_id=TEST

# Get trait state
curl http://localhost:8015/refinement/state?user_id=TEST&trait=python_fluency
```

### Run Tests

```bash
PYTHONPATH=.:ReDNACoreDemo python3 -m pytest \
  ReDNACoreDemo/tests/test_trait_refinement_depth_phase1.py -v
```

### Documentation

- **Technical:** `ReDNACoreDemo/docs/TRAIT_REFINEMENT_DEPTH_P1.md`
- **Summary:** `TRAIT_REFINEMENT_PHASE1_COMPLETE.md`

---

## Jarvis-Codex Interface

### Quick Usage

```python
from ReDNACoreDemo.core.jarvis_codex.codex_agent import create_codex_agent

# Initialize agent
agent = create_codex_agent()

# Propose UI change
request = {
    "scope": "frontend",
    "file": "web/src/components/test.tsx",
    "intent": "Update text",
    "suggested_change": {
        "type": "text_replace",
        "before": "Old Text",
        "after": "New Text"
    },
    "confidence": 0.93,
    "source": "head_coach"
}

proposal, error = agent.generate_patch(request)

if not error:
    # Preview diff
    print(agent.get_patch_diff(proposal.proposal_id))

    # Apply
    success, error = agent.apply_patch(proposal.proposal_id, "admin")
    print("✓ Applied" if success else f"✗ {error}")
```

### API Endpoints

```bash
# Propose change
curl -X POST http://localhost:8015/jarvis_codex/propose \
  -H "Content-Type: application/json" \
  -d '{
    "scope":"frontend",
    "file":"web/src/components/test.tsx",
    "intent":"Update",
    "suggested_change":{"type":"text_replace","before":"A","after":"B"},
    "confidence":0.9,
    "source":"test"
  }'

# List proposals
curl http://localhost:8015/jarvis_codex/proposals?status=pending

# Apply proposal
curl -X POST http://localhost:8015/jarvis_codex/apply \
  -H "Content-Type: application/json" \
  -d '{"proposal_id":"uuid","user":"admin"}'

# Reject proposal
curl -X POST http://localhost:8015/jarvis_codex/reject \
  -H "Content-Type: application/json" \
  -d '{"proposal_id":"uuid","user":"admin","reason":"Not needed"}'
```

### Run Tests

```bash
PYTHONPATH=.:ReDNACoreDemo python3 -m pytest \
  ReDNACoreDemo/tests/test_jarvis_codex_phase1.py -v
```

### Documentation

- **Technical:** `ReDNACoreDemo/docs/JARVIS_CODEX_PHASE1.md`
- **Progress:** `JARVIS_CODEX_PHASE1_PROGRESS.md`
- **Summary:** `JARVIS_CODEX_PHASE1_COMPLETE.md`

---

## Configuration

### Trait Refinement

**File:** `ReDNACoreDemo/core/refinement/refinement_config.json`

```json
{
  "accept_threshold": 0.7,
  "investigate_threshold": 0.55,
  "decay_lambda": 0.015,
  "corroboration_gain": 0.15,
  "contradiction_penalty": 0.2,
  "max_gain_per_turn": 0.2
}
```

### Jarvis-Codex

**Default Config:**

```python
{
  "allowed_scopes": ["web/src/", "devx/frontend/src/"],
  "max_file_size_kb": 50,
  "min_confidence": 0.85,
  "backup_dir": "web/backups/"
}
```

**Custom Config:**

```python
from ReDNACoreDemo.core.jarvis_codex.codex_agent import create_codex_agent

agent = create_codex_agent(config={
    "min_confidence": 0.90,  # Stricter
    "allowed_scopes": ["web/src/components/"]  # Narrower
})
```

---

## Common Tasks

### View Refinement Telemetry

```bash
tail -20 prompts/insights/refinement_events.jsonl | jq .
```

### View Codex Audit Log

```bash
tail -20 prompts/insights/jarvis_codex_audit.jsonl | jq .
```

### List Codex Backups

```bash
ls -lah web/backups/*.bak
```

### Restore from Backup

```bash
cp web/backups/File.tsx_20251010T123456.bak web/src/components/File.tsx
```

---

## Troubleshooting

### Trait Refinement

**Issue:** "Proposals not resolving"
- Check confidence scores (must have proposals)
- Verify user_id exists
- Check telemetry: `tail prompts/insights/refinement_events.jsonl`

**Issue:** "Conflicts not detected"
- Verify contradicting values (must differ by >30% of dominant weight)
- Check conflict_penalty in config

### Jarvis-Codex

**Issue:** "Checksum mismatch"
- File was modified between proposal and apply
- Create new proposal with current content

**Issue:** "Low confidence rejected"
- Increase confidence score if justified
- Or adjust `min_confidence` in config

**Issue:** "Text not found in file"
- Be more specific in "before" text
- Include surrounding context
- Check file hasn't been modified

---

## Performance Benchmarks

### Trait Refinement
- Single trait: ~1-2ms
- 100 proposals (10 traits): <300ms
- API overhead: ~10-15ms

### Jarvis-Codex
- Propose (with diff): ~5-10ms
- Apply (with backup): ~15-25ms
- Total round-trip: <50ms

---

## Test Summary

```bash
# Run all tests
PYTHONPATH=.:ReDNACoreDemo python3 -m pytest \
  ReDNACoreDemo/tests/test_trait_refinement_depth_phase1.py \
  ReDNACoreDemo/tests/test_jarvis_codex_phase1.py \
  -v

# Expected:
# ===================== 18 passed in 0.73s ========================
```

---

## File Locations

### Trait Refinement

```
ReDNACoreDemo/core/refinement/
  ├── refinement_resolver.py
  └── refinement_config.json

data/users/{user_id}/
  ├── resolved.json
  ├── conflicts.json
  └── refinement/{trait}.jsonl

prompts/insights/
  └── refinement_events.jsonl
```

### Jarvis-Codex

```
ReDNACoreDemo/core/jarvis_codex/
  ├── __init__.py
  └── codex_agent.py

data/codex_patches/
  └── {proposal_id}.patch

web/backups/
  └── {filename}_{timestamp}.bak

prompts/insights/
  ├── jarvis_codex_proposals.jsonl
  ├── jarvis_codex_audit.jsonl
  └── jarvis_codex_telemetry.jsonl
```

---

## Next Steps

1. **Deploy Backend** — Both systems are production-ready
2. **Build Jarvis-Codex UI** — DevX panel (~500 LOC React)
3. **HC Integration** — Add Codex proposal capability to HC toolkit
4. **Monitor Telemetry** — Watch JSONL logs for insights
5. **Phase 2 Planning** — Advanced features (see roadmaps)

---

## Support

- **Tests:** Run test suites for working examples
- **Docs:** See component-specific documentation
- **Logs:** Check JSONL telemetry files
- **Issues:** Review test failures for debugging

---

**Quick Reference Version:** 1.0
**Systems:** Trait Refinement Depth + Jarvis-Codex Interface
**Status:** ✅ Production-Ready (Backend)
