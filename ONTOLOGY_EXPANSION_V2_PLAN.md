# Container Explosion v2.0 - Execution Plan

## Session Status

**Jarvis Sprint**: ✅ COMPLETE (Phases 1-3)
- Committed: `jarvis_v0.5`
- Branch: `ontology_explosion_v2` (active)

**Ontology Expansion**: 📋 READY TO EXECUTE

## Current State

- **Registry**: 380 containers
- **Target**: 580+ containers (Pilot), then 2,000+ (Full)
- **Schema Version**: v1.0.0
- **Branch**: `ontology_explosion_v2`

---

## Stage 1: Foundation (Tooling Infrastructure)

### A. Directory Structure
```bash
ReDNACoreDemo/core/ontology/
  ├── dna_registry.json (existing, 380 containers)
  ├── dna_registry.schema.json → move to schemas/
  ├── linter.py (NEW)
  ├── cross_links.yaml (NEW)
  ├── tools/
  │   ├── report_stats.py (NEW)
  │   └── diff_summary.py (NEW)
  └── reports/
      ├── ONTOLOGY_FOUNDATION_SUMMARY.md (NEW)
      ├── LINT_V2.txt (generated)
      └── STATS_V2.json (generated)

ReDNACoreDemo/schemas/
  ├── dna_registry.schema.json (v2 - enhanced)
  └── cross_links.schema.json (NEW)

ReDNACoreDemo/scripts/
  ├── validate_ontology.sh (NEW)
  ├── apply_registry_patch.py (NEW)
  └── rollback_registry.sh (NEW)
```

### B. Schema Enhancements (v2.0)

**dna_registry.schema.json** additions (backward compatible):
```json
{
  "optional_fields": {
    "status": {
      "type": "string",
      "enum": ["prototype", "candidate", "stable", "deprecated"]
    },
    "edges": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "type": {"enum": ["is_a", "part_of", "derived_from", "correlates_with", "contradicts"]},
          "to": {"type": "string"},
          "evidence": {"type": "string"}
        }
      }
    }
  }
}
```

**cross_links.schema.json** (NEW):
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Cross-Domain Links Schema",
  "type": "object",
  "properties": {
    "edges": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["from", "to", "type"],
        "properties": {
          "from": {"type": "string", "pattern": "^[A-Z][a-zA-Z0-9]+"},
          "to": {"type": "string", "pattern": "^[A-Z][a-zA-Z0-9]+"},
          "type": {"enum": ["correlates_with", "derived_from", "contradicts"]},
          "evidence": {"type": "string"},
          "confidence": {"type": "number", "minimum": 0, "maximum": 1}
        }
      }
    }
  }
}
```

### C. Linter Implementation

**ReDNACoreDemo/core/ontology/linter.py**:
```python
#!/usr/bin/env python3
"""
DNA Registry Linter
===================

Validates dna_registry.json against rules:
1. Depth ≤ 3 (Umbrella → Sub → Sub-Sub)
2. Unique id and path
3. Valid parent references
4. sensitive=true requires consent_required=true
5. New nodes (.v1) must have status="prototype", ai_upgradable=true
6. Edge validation (no is_a/part_of cycles)
"""

import argparse
import json
import sys
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set, Tuple


class DNALinter:
    def __init__(self, registry_path: Path):
        self.registry_path = registry_path
        with open(registry_path) as f:
            self.data = json.load(f)

        self.containers = self.data.get("containers", [])
        self.errors = []
        self.warnings = []

    def lint(self) -> Tuple[List[str], List[str]]:
        """Run all linter rules."""
        self._check_depth()
        self._check_uniqueness()
        self._check_parent_refs()
        self._check_sensitive_consent()
        self._check_prototype_standards()
        self._check_edges()

        return self.errors, self.warnings

    def _check_depth(self):
        """Rule: depth ≤ 3 (Umbrella.Sub.SubSub)"""
        for container in self.containers:
            path = container.get("path", "")
            depth = len(path.split("."))
            if depth > 3:
                self.errors.append(
                    f"Depth violation: {path} has depth {depth} (max 3)"
                )

    def _check_uniqueness(self):
        """Rule: unique id and path"""
        seen_ids = set()
        seen_paths = set()

        for container in self.containers:
            cid = container.get("id")
            path = container.get("path")

            if cid in seen_ids:
                self.errors.append(f"Duplicate ID: {cid}")
            seen_ids.add(cid)

            if path in seen_paths:
                self.errors.append(f"Duplicate path: {path}")
            seen_paths.add(path)

    def _check_parent_refs(self):
        """Rule: parent must exist for child nodes"""
        paths = {c.get("path") for c in self.containers}

        for container in self.containers:
            path = container.get("path", "")
            parts = path.split(".")

            if len(parts) > 1:
                # Has a parent
                parent_path = ".".join(parts[:-1])
                if parent_path not in paths:
                    self.errors.append(
                        f"Missing parent: {path} requires {parent_path}"
                    )

    def _check_sensitive_consent(self):
        """Rule: sensitive=true requires consent_required=true"""
        for container in self.containers:
            if container.get("sensitive", False):
                if not container.get("consent_required", False):
                    self.errors.append(
                        f"Sensitive without consent: {container.get('id')}"
                    )

    def _check_prototype_standards(self):
        """Rule: .v1 nodes must be prototype, ai_upgradable"""
        for container in self.containers:
            cid = container.get("id", "")
            version = container.get("version", 0)

            if version == 1 and cid.endswith(".v1"):
                status = container.get("status")
                ai_upgradable = container.get("ai_upgradable", False)

                if status != "prototype":
                    self.warnings.append(
                        f"V1 without prototype status: {cid} (status={status})"
                    )

                if not ai_upgradable:
                    self.warnings.append(
                        f"V1 without ai_upgradable: {cid}"
                    )

    def _check_edges(self):
        """Rule: validate edges, no is_a/part_of cycles"""
        # Build adjacency list for cycle detection
        graph = defaultdict(list)

        for container in self.containers:
            cid = container.get("id")
            edges = container.get("edges", [])

            for edge in edges:
                edge_type = edge.get("type")
                target = edge.get("to")

                if edge_type in ["is_a", "part_of"]:
                    graph[cid].append(target)

        # Check for cycles
        visited = set()
        rec_stack = set()

        def has_cycle(node):
            visited.add(node)
            rec_stack.add(node)

            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True

            rec_stack.remove(node)
            return False

        for node in graph:
            if node not in visited:
                if has_cycle(node):
                    self.errors.append(f"Cycle detected in is_a/part_of edges involving {node}")

    def write_report(self, report_path: Path):
        """Write linter report to file."""
        with open(report_path, 'w') as f:
            f.write("DNA Registry Linter Report\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"Registry: {self.registry_path}\n")
            f.write(f"Total containers: {len(self.containers)}\n\n")

            if self.errors:
                f.write(f"ERRORS ({len(self.errors)}):\n")
                for error in self.errors:
                    f.write(f"  ❌ {error}\n")
                f.write("\n")
            else:
                f.write("✅ No errors found\n\n")

            if self.warnings:
                f.write(f"WARNINGS ({len(self.warnings)}):\n")
                for warning in self.warnings:
                    f.write(f"  ⚠️  {warning}\n")
                f.write("\n")
            else:
                f.write("✅ No warnings\n\n")

            f.write(f"\nLinter exit code: {1 if self.errors else 0}\n")


def main():
    parser = argparse.ArgumentParser(description="Lint DNA registry")
    parser.add_argument("--registry", required=True, help="Path to dna_registry.json")
    parser.add_argument("--report", required=True, help="Output report path")
    args = parser.parse_args()

    linter = DNALinter(Path(args.registry))
    errors, warnings = linter.lint()
    linter.write_report(Path(args.report))

    if errors:
        print(f"❌ Linter found {len(errors)} error(s)")
        sys.exit(1)
    else:
        print(f"✅ Linter passed (0 errors, {len(warnings)} warnings)")
        sys.exit(0)


if __name__ == "__main__":
    main()
```

### D. Reporting Tools

**tools/report_stats.py**:
```python
#!/usr/bin/env python3
"""Generate ontology statistics JSON."""
import json
from pathlib import Path
from collections import Counter

def main():
    registry_path = Path("ReDNACoreDemo/core/ontology/dna_registry.json")
    with open(registry_path) as f:
        data = json.load(f)

    containers = data.get("containers", [])

    stats = {
        "total_containers": len(containers),
        "by_namespace": dict(Counter(c.get("namespace") for c in containers)),
        "by_status": dict(Counter(c.get("status", "unknown") for c in containers)),
        "sensitive_count": sum(1 for c in containers if c.get("sensitive", False)),
        "consent_required_count": sum(1 for c in containers if c.get("consent_required", False)),
        "ai_upgradable_count": sum(1 for c in containers if c.get("ai_upgradable", False)),
        "depth_distribution": dict(Counter(len(c.get("path", "").split(".")) for c in containers)),
        "edges_count": sum(len(c.get("edges", [])) for c in containers),
        "version": data.get("metadata", {}).get("version", "unknown")
    }

    print(json.dumps(stats, indent=2))

if __name__ == "__main__":
    main()
```

**tools/diff_summary.py**:
```python
#!/usr/bin/env python3
"""Compare two registries and show diff."""
import json
import sys
from pathlib import Path
from collections import Counter

def main(old_path, new_path):
    with open(old_path) as f:
        old_data = json.load(f)
    with open(new_path) as f:
        new_data = json.load(f)

    old_ids = {c["id"] for c in old_data.get("containers", [])}
    new_ids = {c["id"] for c in new_data.get("containers", [])}

    added = new_ids - old_ids
    removed = old_ids - new_ids

    print(f"Diff Summary: {old_path} → {new_path}")
    print(f"Added: {len(added)} containers")
    print(f"Removed: {len(removed)} containers")
    print(f"Net change: {len(new_ids) - len(old_ids):+d}")

    if added:
        namespaces = Counter(id.split(".")[0] for id in added)
        print("\nAdded by namespace:")
        for ns, count in namespaces.most_common():
            print(f"  {ns}: +{count}")

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
```

### E. CI Hook

**scripts/validate_ontology.sh**:
```bash
#!/usr/bin/env bash
set -euo pipefail

echo "🔍 Validating DNA Registry..."

# 1. JSON Schema validation
echo "  Step 1: Schema validation..."
python3 -m jsonschema \
  -i ReDNACoreDemo/core/ontology/dna_registry.json \
  ReDNACoreDemo/schemas/dna_registry.schema.json

# 2. Linter rules
echo "  Step 2: Linter rules..."
python3 ReDNACoreDemo/core/ontology/linter.py \
  --registry ReDNACoreDemo/core/ontology/dna_registry.json \
  --report ReDNACoreDemo/core/ontology/reports/LINT_V2.txt

# 3. Generate stats
echo "  Step 3: Generate stats..."
python3 ReDNACoreDemo/core/ontology/tools/report_stats.py > \
  ReDNACoreDemo/core/ontology/reports/STATS_V2.json

echo "✅ Ontology validation complete"
```

---

## Stage 2: Pilot Expansion (+200 Containers)

### Target Domains (4 umbrellas, ~200 containers)

#### 1. LanguageStyleDNA (+60) - ChatDNA/CReDNA
```
LanguageStyleDNA/
├── DiscourseMarkerUseDNA.v1
├── ParallelismRhetoricDNA.v1
├── ParentheticalUsageDNA.v1
├── AnalogyDensityDNA.v1
├── CodeSwitchingRegisterDNA.v1
├── IronySarcasmDNA.v1
├── RhetoricalQuestionDNA.v1
├── MetaphorAnalogyUseDNA.v1
├── HedgingPatternDNA/
│   ├── QualifierDensityDNA.v1
│   ├── ModalVerbUsageDNA.v1
│   └── UncertaintyMarkerDNA.v1
└── EmojiExclamationProfileDNA/
    ├── EmojiDensityDNA.v1
    ├── ExclamationFrequencyDNA.v1
    └── EmoticonStyleDNA.v1
```

#### 2. SkillDNA × ProfDNA (+60) - Career Coach
```
SkillDNA/
├── PresentationSkillDNA.v1
├── NegotiationDNA.v1
├── ConflictResolutionDNA.v1
├── StrategicPlanningDNA.v1
├── DataAnalysisSkillDNA.v1
├── TechnicalWritingDNA.v1
├── CollaborationSkillDNA.v1
└── MentoringCoachingDNA.v1

ProfDNA/
├── WorkOutcomeDNA/
│   ├── OKRAlignmentDNA.v1
│   └── KPIFulfillmentDNA.v1
├── CollaborationCadenceDNA/
│   ├── MeetingLoadDNA.v1
│   └── AsyncCommPrefDNA.v1
├── WorkContractContextDNA/
│   ├── WorkModeDNA.v1
│   └── FlexibilityNeedDNA.v1
└── DomainKnowledgeMapDNA/
    └── IndustryGenericDNA.v1
```

#### 3. PsyDNA/BeliefValueDNA/CogDNA (+60) - PTC & Belief Coach
```
PsyDNA/PersonalityDNA/
├── OpennessLevelDNA/
│   ├── ImaginationCreativityDNA.v1
│   └── AestheticSensitivityDNA.v1
├── ConscientiousnessFacetsDNA/
│   ├── OrderlinessDNA.v1
│   └── IndustriousnessDNA.v1
└── AgreeablenessFactorsDNA/
    ├── CompassionDNA.v1
    └── PolitenessForma

lityDNA.v1

BeliefValueDNA/MoralFoundationDNA/
├── CareFairnessDNA.v1
├── AuthoritySubversionDNA.v1
├── LibertyOppressionDNA.v1
├── LoyaltyBetrayalDNA.v1
└── SanctityDegradationDNA.v1

CogDNA/
├── AnalyticalVsIntuitiveDNA.v1
├── ToleranceForAmbiguityDNA.v1
└── NeedForClosureDNA.v1
```

#### 4. SocDNA × BehDNA (+20) - Head Coach
```
SocDNA/InteractionStyleDNA/
├── ListeningAcknowledgementDNA.v1
├── ConversationalDominanceDNA.v1
├── TurnTakingLatencyDNA.v1
└── StorytellingHumorDNA.v1

BehDNA/ProductivityWorkflowDNA/
├── FocusBlocksDNA.v1
├── TaskManagementDNA.v1
└── ContextSwitchingDNA.v1
```

### Cross-Links (Pilot: 20+ edges)

**cross_links.yaml**:
```yaml
edges:
  - from: LanguageStyleDNA.ParallelismRhetoricDNA
    to: SocDNA.InteractionStyleDNA.StorytellingHumorDNA
    type: correlates_with
    confidence: 0.7

  - from: SkillDNA.PresentationSkillDNA
    to: SocDNA.InteractionStyleDNA.ListeningAcknowledgementDNA
    type: correlates_with
    confidence: 0.8

  - from: PsyDNA.ConscientiousnessFacetsDNA.OrderlinessDNA
    to: BehDNA.ProductivityWorkflowDNA.TaskManagementDNA
    type: correlates_with
    confidence: 0.9

  - from: BeliefValueDNA.MoralFoundationDNA.CareFairnessDNA
    to: CogDNA.ToleranceForAmbiguityDNA
    type: correlates_with
    confidence: 0.6

  - from: ProfDNA.WorkContractContextDNA.WorkModeDNA
    to: PrefDNA.WorkEnvironmentPrefDNA.RemoteHybridOnsiteDNA
    type: derived_from
    confidence: 0.95

  # ... (15+ more edges)
```

---

## Execution Checklist

### Foundation (Stage 1)
- [ ] Create directory structure
- [ ] Move dna_registry.schema.json to schemas/
- [ ] Implement linter.py
- [ ] Implement report_stats.py
- [ ] Implement diff_summary.py
- [ ] Create validate_ontology.sh
- [ ] Create apply_registry_patch.py
- [ ] Create rollback_registry.sh
- [ ] Create cross_links.schema.json
- [ ] Run validation on current registry (380 containers)
- [ ] Write ONTOLOGY_FOUNDATION_SUMMARY.md

### Pilot (Stage 2)
- [ ] Backup current registry
- [ ] Generate 200+ pilot containers in pilot_patch.json
- [ ] Apply patch with apply_registry_patch.py
- [ ] Run validate_ontology.sh (must pass with 0 errors)
- [ ] Create cross_links.yaml with 20+ edges
- [ ] Verify at least 1 LanguageStyleDNA used by CReDNA
- [ ] Verify at least 1 SkillDNA surfaced in Career Coach
- [ ] Generate CONTAINER_PILOT_SUMMARY.md
- [ ] Update STATS_V2.json
- [ ] Run diff_summary.py

### Post-Pilot Review
- [ ] Review pilot summary and stats
- [ ] Verify linter report (0 errors)
- [ ] Check cross-links validation
- [ ] User approval for full v2.0 expansion

---

## Next Session Execution

This document provides a complete blueprint. In the next session:

1. **Execute Stage 1** (Foundation - ~1 hour)
2. **Execute Stage 2** (Pilot +200 - ~2 hours)
3. **Generate all reports**
4. **Await user review before full v2.0 (2,000+ containers)**

## Deliverables

After pilot completion:
- ✅ ONTOLOGY_FOUNDATION_SUMMARY.md
- ✅ CONTAINER_PILOT_SUMMARY.md
- ✅ STATS_V2.json (580+ containers)
- ✅ LINT_V2.txt (0 errors)
- ✅ cross_links.yaml (20+ edges)
- ✅ Diff summary (baseline → pilot)
