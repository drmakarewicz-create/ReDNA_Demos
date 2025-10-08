# Stage 3: Full Ontology Expansion - Execution Plan

**Date**: 2025-10-08
**Author**: claude_sonnet_4.5
**Objective**: Scale from 590 → 2,000+ containers with cross-domain relationship network

---

## Prerequisites ✅

**Stage 1**: Foundation tooling complete
- Linter, stats reporter, diff summary, patch application, rollback scripts
- CI validation harness (`validate_ontology.sh`)
- Cross-link schema

**Stage 2**: Pilot expansion validated
- 210 containers generated across 7 namespaces (BehDNA +37, CogDNA +35, SocDNA +33, SkillDNA +30, PrefDNA +29, HistDNA +28, MetaDNA +18)
- 25 cross-domain edges with evidence citations
- 0 linter errors, quality metrics within guidelines
- Average description length: 45.7 words (39–52 range)

---

## Stage 3 Scope

### Target Outcomes
1. **Container Expansion**: 380 → 2,000+ containers (~1,620 new additions)
2. **Cross-Link Network**: 25 → 200+ edges across all namespace pairs
3. **Depth Optimization**: Remediate 25 depth-4 violations, maintain depth ≤3 for new containers
4. **Consent Hygiene**: Fix 151 sensitive-without-consent warnings
5. **Status Alignment**: Convert 165 v1-stable warnings to prototype status

### Namespace Targets (Final Totals)

| Namespace | Current | Target | New Additions |
|-----------|---------|--------|---------------|
| **BehDNA** | 60 | 180 | +120 |
| **CogDNA** | 60 | 170 | +110 |
| **SocDNA** | 60 | 160 | +100 |
| **SkillDNA** | 70 | 180 | +110 |
| **PrefDNA** | 60 | 150 | +90 |
| **HistDNA** | 50 | 140 | +90 |
| **MetaDNA** | 40 | 120 | +80 |
| **PsyDNA** | 78 | 180 | +102 |
| **ProfDNA** | 24 | 120 | +96 |
| **EmDNA** | 26 | 100 | +74 |
| **EnvDNA** | 11 | 80 | +69 |
| **HealthDNA** | 8 | 80 | +72 |
| **PaDNA** | 35 | 120 | +85 |
| **RoDNA** | 8 | 80 | +72 |
| **Total** | 590 | 1,960 | +1,370 |

---

## Execution Strategy

### Phase A: Legacy Remediation (Pre-Expansion)
**Duration**: 2–3 sessions
**Goal**: Clean up 341 warnings to establish quality baseline

#### Task A1: Consent Flag Remediation
- Auto-fix 151 sensitive containers missing `consent_required=true`
- Scope: EmDNA, HistDNA, PsyDNA, RoDNA, SocDNA namespaces
- Script: `ReDNACoreDemo/tools/fix_consent_flags.py`
- Validation: Re-run linter, expect 151 fewer warnings

#### Task A2: Status Alignment Fix
- Convert 165 v1 containers from `status=stable` → `status=prototype`
- Rationale: v1 containers are early versions, should be prototype by convention
- Script: `ReDNACoreDemo/tools/align_v1_status.py`
- Validation: Linter should clear 165 warnings

#### Task A3: Depth-4 Refactoring
- Review 25 depth-4 containers (mostly PsyDNA.PersonalityDNA subtrees)
- Options: (a) flatten by promoting to depth-3, or (b) mark as accepted exceptions with justification
- Manual review recommended for BigFive facets (psychometric validity concern)
- Document decisions in `DEPTH_EXCEPTIONS.md`

**Phase A Exit Criteria**: Linter warnings reduced from 341 → ~25 documented exceptions

---

### Phase B: Batch Container Generation
**Duration**: 5–8 sessions
**Goal**: Generate 1,370 new containers in waves of 200–300

#### Wave 1: High-Priority Namespaces (400 containers)
- **ProfDNA**: +96 (career, work outcomes, collaboration)
- **BehDNA**: +120 (productivity, habits, micro-behaviors)
- **CogDNA**: +110 (reasoning, learning, attention)
- **PsyDNA**: +102 (motivation, self-concept, risk)

#### Wave 2: Mid-Priority Namespaces (420 containers)
- **SkillDNA**: +110 (technical, interpersonal, managerial)
- **SocDNA**: +100 (stakeholder, team, influence)
- **HistDNA**: +90 (career trajectory, formative experiences)
- **PrefDNA**: +90 (tooling, aesthetics, work environment)

#### Wave 3: Foundation Namespaces (380 containers)
- **MetaDNA**: +80 (engagement, feedback, system trust)
- **PaDNA**: +85 (face, body, voice morphology)
- **HealthDNA**: +72 (vitals, conditions, sleep)
- **EnvDNA**: +69 (digital context, physical environment)
- **EmDNA**: +74 (regulation, attachment, reactivity)

#### Wave 4: Specialized Namespaces (170 containers)
- **RoDNA**: +72 (partnering, attachment, boundary)

**Generation Method**:
- Extend `build_stage2_assets.py` → `build_stage3_batch.py`
- Parameterize by wave, namespace, and count
- Maintain quality thresholds: description 40–55 words, depth ≤3, proper tags
- Auto-tag with `stage3_waveN` for traceability

---

### Phase C: Cross-Link Network Expansion
**Duration**: 3–4 sessions
**Goal**: Build 200+ cross-domain edges with evidence

#### Cross-Link Targets by Domain Pair

| Domain Pair | Current | Target | New Edges |
|-------------|---------|--------|-----------|
| PsyDNA ↔ BehDNA | 9 | 40 | +31 |
| SkillDNA ↔ ProfDNA | 6 | 35 | +29 |
| CogDNA ↔ SocDNA | 4 | 30 | +26 |
| PrefDNA ↔ BehDNA | 3 | 25 | +22 |
| HistDNA ↔ PsyDNA | 3 | 25 | +22 |
| EmDNA ↔ PsyDNA | 0 | 20 | +20 |
| HealthDNA ↔ BehDNA | 0 | 15 | +15 |
| EnvDNA ↔ PrefDNA | 0 | 15 | +15 |
| **Total** | 25 | 205 | +180 |

**Evidence Standards**:
- Prefer peer-reviewed citations or industry benchmark reports
- Confidence scores: 0.6–0.9 (based on evidence strength)
- Each edge must include: `from`, `to`, `type`, `evidence`, `confidence`

**Script**: `ReDNACoreDemo/core/ontology/tools/generate_cross_links.py`

---

### Phase D: Validation & CI Integration
**Duration**: 2 sessions
**Goal**: Lock in quality gates and enable continuous validation

#### Task D1: Cross-Link Validator
- Extend `validate_ontology.sh` to validate `cross_links.yaml` against schema
- Verify all referenced container IDs exist in registry
- Check for orphaned or duplicate edges
- Script: `ReDNACoreDemo/core/ontology/validate_cross_links.py`

#### Task D2: Diff Dashboard
- Generate visual diff report: `reports/STAGE3_DIFF.html`
- Show before/after namespace distributions, depth profiles, sensitive container breakdown
- Highlight top 20 new containers by curiosity/RR potential

#### Task D3: Smoke Tests
- Validate serialization/deserialization of expanded registry
- Test patch application and rollback on Stage 3 dataset
- Ensure no regression in existing container IDs or paths

---

## Quality Gates

### Container Quality Requirements
- ✅ **Description**: 40–55 words, actionable, evidence-grounded
- ✅ **Depth**: ≤3 (except documented exceptions)
- ✅ **Sensitive Handling**: `sensitive=true` → `consent_required=true`
- ✅ **Status**: v1 containers → `prototype`, v2+ may be `stable`
- ✅ **Tags**: Include namespace, stage marker (`stage3_waveN`), domain-specific tags
- ✅ **Discovery Metadata**: `method`, `confidence`, `evidence`, `proposer`

### Cross-Link Quality Requirements
- ✅ **Coverage**: ≥200 edges across 8+ domain pairs
- ✅ **Evidence**: Citation or benchmark reference for each edge
- ✅ **Confidence**: 0.6–0.9 range, justified by evidence strength
- ✅ **Type Distribution**: 60% `correlates_with`, 30% `derived_from`, 10% `contradicts`
- ✅ **Validation**: All referenced containers exist in registry

### Linter Exit Criteria
- **Errors**: 0 (blocking)
- **Warnings**: ≤50 (only documented depth/consent exceptions)

---

## Deliverables

1. **Expanded Registry**: `dna_registry_v2.json` (2,000+ containers)
2. **Cross-Link Network**: `cross_links_v2.yaml` (200+ edges)
3. **Patch Files**: `stage3_wave{1,2,3,4}.patch.json`
4. **Validation Reports**:
   - `LINT_STAGE3.txt`
   - `STATS_STAGE3.json`
   - `DIFF_STAGE3.md`
   - `CROSS_LINK_VALIDATION.txt`
5. **Remediation Scripts**:
   - `fix_consent_flags.py`
   - `align_v1_status.py`
   - `validate_cross_links.py`
6. **Documentation**:
   - `DEPTH_EXCEPTIONS.md` (rationale for depth-4 containers)
   - `STAGE3_COMPLETION_SUMMARY.md`

---

## Risk Mitigation

### Risk: Quality Degradation at Scale
- **Mitigation**: Batch validation after each wave, gate next wave on linter pass
- **Rollback**: Use `rollback_registry.sh` to revert to Stage 2 baseline if needed

### Risk: Cross-Link Integrity Drift
- **Mitigation**: Validate cross-links after each container batch, auto-flag orphans
- **Rollback**: Maintain versioned `cross_links_v{1,2,3}.yaml` snapshots

### Risk: Namespace Imbalance
- **Mitigation**: Track namespace distributions in `STATS_STAGE3.json`, adjust wave targets dynamically
- **Monitoring**: Dashboard showing actual vs. target distributions per wave

---

## Timeline Estimate

| Phase | Duration | Sessions | Dependencies |
|-------|----------|----------|--------------|
| **Phase A**: Legacy Remediation | 2–3 days | 3 | Stage 2 complete |
| **Phase B**: Batch Generation | 5–8 days | 8 | Phase A complete |
| **Phase C**: Cross-Links | 3–4 days | 4 | Phase B waves 1–2 complete |
| **Phase D**: Validation & CI | 2 days | 2 | Phase C complete |
| **Total** | 12–17 days | 17 | — |

---

## Success Metrics

- ✅ Registry grows from 590 → 2,000+ containers (240% increase)
- ✅ Cross-link network expands from 25 → 200+ edges (700% increase)
- ✅ Linter warnings reduced from 341 → ≤50 (85% reduction)
- ✅ All new containers pass quality gates (depth, consent, description length)
- ✅ CI pipeline validates both registry + cross-links on every commit
- ✅ Rollback capability tested and documented

---

## Next Immediate Action

**Start Phase A, Task A1**: Auto-fix 151 consent flag warnings
- Create `ReDNACoreDemo/tools/fix_consent_flags.py`
- Apply fix to `dna_registry_stage2.json` → `dna_registry_stage2_patched.json`
- Run linter, confirm 151 warnings cleared
- Commit with message: "fix: auto-remediate 151 sensitive consent warnings"

Ready to proceed? 🚀
