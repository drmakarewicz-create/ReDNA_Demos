# Stage 2: Pilot Expansion - Codex Task Brief

**Context**: Stage 1 foundation complete. Validation pipeline passing (0 errors, 341 warnings). Ready for controlled expansion.

**Your Mission**: Generate 200+ high-quality containers across underrepresented namespaces and establish 20+ cross-domain edges.

---

## Task 1: Generate `pilot_patch.json`

**Target**: 200-250 new containers
**Output**: `ReDNACoreDemo/core/ontology/pilot_patch.json`

### Distribution Strategy (Expand Underrepresented Namespaces)

Based on current baseline:
- **SkillDNA** (40 → 70): +30 containers
  - Technical skills, soft skills, domain expertise
- **CogDNA** (25 → 60): +35 containers
  - Memory systems, attention types, processing styles
- **SocDNA** (27 → 60): +33 containers
  - Social roles, interaction styles, network preferences
- **BehDNA** (23 → 60): +37 containers
  - Habit patterns, decision-making styles, behavioral tendencies
- **PrefDNA** (31 → 60): +29 containers
  - Aesthetic preferences, lifestyle choices, consumption patterns
- **HistDNA** (22 → 50): +28 containers
  - Life events, milestones, formative experiences
- **MetaDNA** (22 → 40): +18 containers
  - Self-reflection patterns, metacognitive strategies

**Total**: ~210 new containers

### Container Generation Rules

**Every container MUST have**:
```json
{
  "id": "Namespace.ParentDNA.ChildDNA.v1",
  "namespace": "SkillDNA",
  "path": "SkillDNA.ParentDNA.ChildDNA",
  "version": 1,
  "status": "prototype",
  "description": "Detailed 20-100 word description of what this represents",
  "sensitive": false,  // true only if truly sensitive (PII, beliefs, etc)
  "consent_required": false,  // set true IF sensitive=true
  "ai_upgradable": true,
  "ucn_weight_hint": 0.01,
  "rr_baseline": null,
  "curiosity_baseline": 100,
  "created_at": "2025-10-08T04:00:00Z",
  "updated_at": "2025-10-08T04:00:00Z",
  "created_by": "codex_stage2_pilot",
  "discovery": {
    "method": "deterministic_generation",
    "confidence": 0.85,
    "evidence": "Domain literature and ReDNA taxonomy expansion",
    "proposer": "codex_agent"
  }
}
```

**Depth Guidelines**:
- Prefer depth 2-3 (Umbrella.Sub or Umbrella.Sub.SubSub)
- Avoid depth 4 unless scientifically justified
- All new containers must have valid parent paths in existing registry

**Sensitive Data**:
- Mark `sensitive=true` ONLY for: beliefs, health, relationships, private behaviors
- If `sensitive=true`, also set `consent_required=true`
- Most skills, preferences, and behaviors should be `sensitive=false`

**Quality Standards**:
- Descriptions 20-100 words (clear, specific, no jargon)
- Use scientific terminology where appropriate
- Each container should be meaningfully distinct from siblings

---

## Task 2: Create `cross_links.yaml`

**Target**: 20-30 high-value cross-domain edges
**Output**: `ReDNACoreDemo/core/ontology/cross_links.yaml`

### Edge Types & Examples

```yaml
edges:
  # Psychological → Behavioral correlations
  - from: PsyDNA.PersonalityDNA.BigFiveDNA.ConscientiousnessDNA
    to: BehDNA.HabitFormationDNA.ConsistencyPatternDNA
    type: correlates_with
    evidence: "Meta-analysis: r=0.65, p<0.001 (Roberts et al., 2014)"
    confidence: 0.85

  # Skills → Professional connections
  - from: SkillDNA.TechnicalSkillsDNA.ProgrammingDNA
    to: ProfDNA.CareerPathDNA.EngineeringDNA
    type: correlates_with
    evidence: "Career outcome studies"
    confidence: 0.75

  # Cognitive → Social derivations
  - from: CogDNA.ProcessingStyleDNA.AnalyticalThinkingDNA
    to: SocDNA.InteractionStyleDNA.DebateEngagementDNA
    type: derived_from
    evidence: "Cognitive style → social behavior pathway"
    confidence: 0.70
```

### Edge Distribution Goals
- 8-10 edges: PsyDNA ↔ BehDNA (personality → behavior)
- 5-7 edges: SkillDNA ↔ ProfDNA (skills → career)
- 3-5 edges: CogDNA ↔ SocDNA (cognition → social)
- 2-3 edges: PrefDNA ↔ BehDNA (preferences → habits)
- 2-3 edges: HistDNA ↔ PsyDNA (formative events → traits)

**Edge Rules**:
- Use existing container paths (validate against registry + patch)
- `type`: correlates_with | derived_from | contradicts
- `evidence`: Real citations or plausible research references
- `confidence`: 0.6-0.9 (be realistic about correlation strength)

---

## Task 3: Validation & Reporting

**After generating files, run**:
```bash
# Apply patch (dry run first)
python3 ReDNACoreDemo/scripts/apply_registry_patch.py \
  --registry ReDNACoreDemo/core/ontology/dna_registry.json \
  --patch ReDNACoreDemo/core/ontology/pilot_patch.json \
  --out ReDNACoreDemo/core/ontology/dna_registry_stage2.json

# Validate merged registry
python3 ReDNACoreDemo/core/ontology/linter.py \
  --registry ReDNACoreDemo/core/ontology/dna_registry_stage2.json \
  --report ReDNACoreDemo/core/ontology/reports/LINT_STAGE2.txt

# Generate diff summary
python3 ReDNACoreDemo/core/ontology/tools/diff_summary.py \
  ReDNACoreDemo/core/ontology/dna_registry.json \
  ReDNACoreDemo/core/ontology/dna_registry_stage2.json
```

**Success Criteria**:
- Linter: 0 errors (warnings allowed)
- Total containers: 580-630 (380 baseline + 200-250 new)
- No duplicate IDs or paths
- All parent references valid

---

## Task 4: Generate `CONTAINER_PILOT_SUMMARY.md`

**Output**: `ReDNACoreDemo/core/ontology/reports/CONTAINER_PILOT_SUMMARY.md`

**Include**:
1. **Overview**: Total containers added by namespace
2. **Validation Results**: Linter errors/warnings count
3. **Edge Summary**: Count by type, key correlations highlighted
4. **Quality Metrics**:
   - Average description length
   - Sensitive container count (should be <20% of new containers)
   - Depth distribution of new containers
5. **Notable Additions**: 5-10 example containers with descriptions
6. **Next Steps for Stage 3**: Recommendations for expansion targets

---

## Deliverables Checklist

- [ ] `ReDNACoreDemo/core/ontology/pilot_patch.json` (200-250 containers)
- [ ] `ReDNACoreDemo/core/ontology/cross_links.yaml` (20-30 edges)
- [ ] `ReDNACoreDemo/core/ontology/dna_registry_stage2.json` (merged, validated)
- [ ] `ReDNACoreDemo/core/ontology/reports/LINT_STAGE2.txt` (0 errors)
- [ ] `ReDNACoreDemo/core/ontology/reports/CONTAINER_PILOT_SUMMARY.md`

---

## Style & Quality Notes

**Do NOT**:
- Copy-paste similar containers with minor wording changes
- Create overly granular splits (e.g., "LeftHandTypingSkill")
- Use vague descriptions like "Relates to X behavior"
- Create depth-5+ hierarchies

**DO**:
- Think like a psychology/sociology researcher designing a taxonomy
- Use meaningful distinctions based on real cognitive/behavioral science
- Write clear, professional descriptions
- Balance breadth (many domains) with depth (useful granularity)

---

## Timeline

**Estimated effort**: 2-3 hours of careful generation work
**Deliverable format**: All files committed, validation passing

Once complete, hand back to Claude with:
- Validation output summary
- File locations
- Any issues encountered

Good luck! 🚀
