# 🤖 Codex Handoff: Ontology Foundation (Stage 1)

**Handoff Time**: 2025-10-08T03:30:00Z
**From**: Claude (Sonnet 4.5) - Token limit reached
**To**: Codex - Execute Stage 1 of Container Explosion v2.0
**Branch**: `ontology_explosion_v2` (already created and active)
**Documentation**: See `ONTOLOGY_EXPANSION_V2_PLAN.md` for full blueprint

---

## 🎯 Your Mission

Execute **Stage 1: Foundation** from the ontology expansion plan. Build all tooling infrastructure so Claude can execute Stage 2 (Pilot +200 containers) when tokens refresh.

**Key Constraint**: Do NOT generate the 200+ pilot containers. Only build the tooling. Claude will generate containers later.

---

## ✅ What's Already Done

- ✅ Jarvis Sprint (Phases 1-3) committed to main, tagged `jarvis_v0.5`
- ✅ Branch `ontology_explosion_v2` created and active
- ✅ Complete execution plan in `ONTOLOGY_EXPANSION_V2_PLAN.md`
- ✅ Current registry: 380 containers in `ReDNACoreDemo/core/ontology/dna_registry.json`

---

## 📋 Stage 1 Checklist (Your Tasks)

### A. Directory Structure

```bash
mkdir -p ReDNACoreDemo/core/ontology/tools
mkdir -p ReDNACoreDemo/core/ontology/reports
mkdir -p ReDNACoreDemo/scripts
```

### B. Move Schema to Schemas Directory

```bash
# Schema already exists in correct location, just verify
ls -la ReDNACoreDemo/schemas/dna_registry.schema.json
```

### C. Create Linter (COPY FROM PLAN)

**File**: `ReDNACoreDemo/core/ontology/linter.py`

Copy the complete linter implementation from `ONTOLOGY_EXPANSION_V2_PLAN.md` section "C. Linter Implementation".

Make executable:
```bash
chmod +x ReDNACoreDemo/core/ontology/linter.py
```

### D. Create Reporting Tools

**File 1**: `ReDNACoreDemo/core/ontology/tools/report_stats.py`

Copy from plan section "D. Reporting Tools" → report_stats.py

**File 2**: `ReDNACoreDemo/core/ontology/tools/diff_summary.py`

Copy from plan section "D. Reporting Tools" → diff_summary.py

Make both executable:
```bash
chmod +x ReDNACoreDemo/core/ontology/tools/report_stats.py
chmod +x ReDNACoreDemo/core/ontology/tools/diff_summary.py
```

### E. Create CI Validation Hook

**File**: `ReDNACoreDemo/scripts/validate_ontology.sh`

Copy from plan section "E. CI Hook"

Make executable:
```bash
chmod +x ReDNACoreDemo/scripts/validate_ontology.sh
```

### F. Create Cross-Links Schema

**File**: `ReDNACoreDemo/schemas/cross_links.schema.json`

Copy from plan section "B. Schema Enhancements" → cross_links.schema.json

### G. Create Utility Scripts

**File 1**: `ReDNACoreDemo/scripts/apply_registry_patch.py`

```python
#!/usr/bin/env python3
"""
Apply a patch of new containers to the registry.

Usage:
  python3 apply_registry_patch.py --registry dna_registry.json --patch pilot_patch.json --out dna_registry.json
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter


def apply_patch(registry_path: Path, patch_path: Path, output_path: Path):
    """Apply patch to registry."""
    # Load existing registry
    with open(registry_path) as f:
        registry = json.load(f)

    # Load patch
    with open(patch_path) as f:
        patch = json.load(f)

    existing_ids = {c["id"] for c in registry["containers"]}

    # Add new containers (skip duplicates)
    added_count = 0
    for container in patch.get("containers", []):
        if container["id"] not in existing_ids:
            registry["containers"].append(container)
            added_count += 1

    # Sort containers by path for deterministic output
    registry["containers"].sort(key=lambda c: c["path"])

    # Update metadata
    registry["metadata"]["total_containers"] = len(registry["containers"])
    registry["metadata"]["last_updated"] = datetime.now(timezone.utc).isoformat()

    # Update namespace counts
    namespace_counts = Counter(c["namespace"] for c in registry["containers"])
    registry["metadata"]["namespace_counts"] = dict(namespace_counts)

    # Write output
    with open(output_path, 'w') as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)

    print(f"✅ Applied patch: +{added_count} containers")
    print(f"   Total containers: {registry['metadata']['total_containers']}")


def main():
    parser = argparse.ArgumentParser(description="Apply container patch to registry")
    parser.add_argument("--registry", required=True, help="Path to dna_registry.json")
    parser.add_argument("--patch", required=True, help="Path to patch JSON")
    parser.add_argument("--out", required=True, help="Output path")
    args = parser.parse_args()

    apply_patch(Path(args.registry), Path(args.patch), Path(args.out))


if __name__ == "__main__":
    main()
```

**File 2**: `ReDNACoreDemo/scripts/rollback_registry.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="ReDNACoreDemo/core/ontology"
REGISTRY="${BACKUP_DIR}/dna_registry.json"

# Find most recent backup
LATEST_BACKUP=$(ls -t ${BACKUP_DIR}/dna_registry.json.bak.* 2>/dev/null | head -1)

if [ -z "$LATEST_BACKUP" ]; then
    echo "❌ No backup found"
    exit 1
fi

echo "🔄 Rolling back to: $LATEST_BACKUP"
cp "$LATEST_BACKUP" "$REGISTRY"
echo "✅ Rollback complete"
```

Make executable:
```bash
chmod +x ReDNACoreDemo/scripts/apply_registry_patch.py
chmod +x ReDNACoreDemo/scripts/rollback_registry.sh
```

---

## 🧪 Validation Tests

After creating all files, run these tests:

### Test 1: Linter on Current Registry
```bash
python3 ReDNACoreDemo/core/ontology/linter.py \
  --registry ReDNACoreDemo/core/ontology/dna_registry.json \
  --report ReDNACoreDemo/core/ontology/reports/LINT_V2.txt

# Expected: 0 errors (current registry should be clean)
```

### Test 2: Stats Report
```bash
python3 ReDNACoreDemo/core/ontology/tools/report_stats.py > \
  ReDNACoreDemo/core/ontology/reports/STATS_V2.json

# Expected: JSON with total_containers: 380
```

### Test 3: Full CI Validation
```bash
bash ReDNACoreDemo/scripts/validate_ontology.sh

# Expected: All 3 steps pass, "✅ Ontology validation complete"
```

---

## 📄 Create Foundation Summary

**File**: `ReDNACoreDemo/core/ontology/reports/ONTOLOGY_FOUNDATION_SUMMARY.md`

```markdown
# Ontology Foundation Summary

**Created**: 2025-10-08
**Version**: v2.0 Foundation
**Status**: ✅ Complete

## Tools Created

### 1. Linter (`core/ontology/linter.py`)
Validates registry against rules:
- Depth ≤ 3 (Umbrella → Sub-DNA → Sub-Sub-DNA)
- Unique id and path
- Valid parent references
- sensitive=true requires consent_required=true
- New nodes (.v1) must have status="prototype", ai_upgradable=true
- Edge validation (no is_a/part_of cycles)

**Usage**:
```bash
python3 ReDNACoreDemo/core/ontology/linter.py \
  --registry ReDNACoreDemo/core/ontology/dna_registry.json \
  --report ReDNACoreDemo/core/ontology/reports/LINT_V2.txt
```

### 2. Stats Reporter (`core/ontology/tools/report_stats.py`)
Generates JSON statistics:
- total_containers
- by_namespace distribution
- by_status distribution
- sensitive_count, consent_required_count
- ai_upgradable_count
- depth_distribution
- edges_count

**Usage**:
```bash
python3 ReDNACoreDemo/core/ontology/tools/report_stats.py > \
  ReDNACoreDemo/core/ontology/reports/STATS_V2.json
```

### 3. Diff Summarizer (`core/ontology/tools/diff_summary.py`)
Compares two registries and shows additions/removals by namespace.

**Usage**:
```bash
python3 ReDNACoreDemo/core/ontology/tools/diff_summary.py \
  old_registry.json new_registry.json
```

### 4. CI Validation Hook (`scripts/validate_ontology.sh`)
Runs all validation in sequence:
1. JSON Schema validation
2. Linter rules
3. Stats generation

**Usage**:
```bash
bash ReDNACoreDemo/scripts/validate_ontology.sh
```

### 5. Patch Applier (`scripts/apply_registry_patch.py`)
Safely applies new containers from a patch file.

**Usage**:
```bash
python3 ReDNACoreDemo/scripts/apply_registry_patch.py \
  --registry dna_registry.json \
  --patch pilot_patch.json \
  --out dna_registry.json
```

### 6. Rollback (`scripts/rollback_registry.sh`)
Restores most recent backup.

**Usage**:
```bash
bash ReDNACoreDemo/scripts/rollback_registry.sh
```

## Schemas

### dna_registry.schema.json (v2.0)
Enhanced with optional fields:
- `status` (prototype|candidate|stable|deprecated)
- `edges[]` (is_a, part_of, derived_from, correlates_with, contradicts)

### cross_links.schema.json (NEW)
Validates cross-domain correlation edges.

## Validation Results (Baseline)

**Current Registry**: 380 containers
**Linter Errors**: 0
**Linter Warnings**: TBD
**Depth Compliance**: 100%
**Namespace Distribution**:
- PaDNA: 35
- PsyDNA: 78
- EmDNA: 26
- CogDNA: 25
- SocDNA: 27
- BehDNA: 23
- HistDNA: 22
- PrefDNA: 31
- SkillDNA: 40
- MetaDNA: 22
- HealthDNA: 8
- RoDNA: 8
- ProfDNA: 24
- EnvDNA: 11

## Next Steps

Stage 2 (Pilot): Add 200+ containers across 4 priority domains:
1. LanguageStyleDNA (+60) - ChatDNA/CReDNA
2. SkillDNA × ProfDNA (+60) - Career Coach
3. PsyDNA/BeliefValueDNA/CogDNA (+60) - PTC & Belief Coach
4. SocDNA × BehDNA (+20) - Head Coach

**Ready for Claude to execute pilot expansion.**
```

---

## 📊 Acceptance Criteria

Before marking complete, verify:

- [ ] All 8 files created
- [ ] All scripts executable (chmod +x)
- [ ] Linter runs successfully on current registry (0 errors)
- [ ] Stats report generates valid JSON
- [ ] CI validation script passes all 3 steps
- [ ] ONTOLOGY_FOUNDATION_SUMMARY.md created
- [ ] LINT_V2.txt exists in reports/
- [ ] STATS_V2.json exists in reports/

---

## 🎁 Commit Your Work

When all tasks complete:

```bash
git add ReDNACoreDemo/core/ontology/ ReDNACoreDemo/schemas/ ReDNACoreDemo/scripts/
git commit -m "feat: Ontology Foundation v2.0 - linter, schemas, CI, reports

Stage 1 complete:
- Linter with 6 validation rules
- Stats reporter and diff summarizer
- CI validation hook (schema + lint + stats)
- Patch applier and rollback scripts
- Cross-links schema for edge validation
- Foundation summary with baseline metrics

Current registry: 380 containers, 0 linter errors
Ready for Stage 2 pilot expansion (+200 containers)"
```

---

## 🔔 Handoff Back to Claude

**Create this file when done**: `CODEX_COMPLETION_REPORT.md`

```markdown
# Codex Completion Report

**Completed**: YYYY-MM-DDTHH:MM:SSZ
**Branch**: ontology_explosion_v2
**Commit**: <commit_hash>

## Stage 1: Foundation - COMPLETE ✅

All 8 files created and validated:
- [x] linter.py
- [x] report_stats.py
- [x] diff_summary.py
- [x] validate_ontology.sh
- [x] apply_registry_patch.py
- [x] rollback_registry.sh
- [x] cross_links.schema.json
- [x] ONTOLOGY_FOUNDATION_SUMMARY.md

## Validation Results

```
Linter: 0 errors, X warnings
Stats: 380 containers
CI: All checks passed
```

## Next Steps for Claude

Stage 2: Pilot Expansion
- Generate pilot_patch.json with 200+ containers
- Apply patch and validate
- Create cross_links.yaml with 20+ edges
- Generate CONTAINER_PILOT_SUMMARY.md

**File Location**: `/Users/davidmakarewicz/Documents/ReDNA_Demos/CODEX_COMPLETION_REPORT.md`
```

---

## 🚨 Important Notes

1. **DO NOT** generate the 200+ pilot containers - Claude will do that
2. **DO NOT** modify the existing dna_registry.json
3. **DO** copy code exactly from ONTOLOGY_EXPANSION_V2_PLAN.md
4. **DO** test all scripts before committing
5. **DO** create CODEX_COMPLETION_REPORT.md when done

---

## 📍 Where Claude Will Look

When Claude returns, it will check:
1. `CODEX_COMPLETION_REPORT.md` (your completion summary)
2. `ReDNACoreDemo/core/ontology/reports/ONTOLOGY_FOUNDATION_SUMMARY.md`
3. `ReDNACoreDemo/core/ontology/reports/LINT_V2.txt`
4. `ReDNACoreDemo/core/ontology/reports/STATS_V2.json`
5. Git log for your commit

Good luck! 🚀
