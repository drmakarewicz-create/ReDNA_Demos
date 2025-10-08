# Codex Handoff: Stage 3 Wave 1 Full Expansion

**Date**: 2025-10-08T06:30:00Z
**From**: Claude Sonnet 4.5
**To**: Codex
**Task**: Expand Wave 1 from 16 → 400 containers

---

## Context

Phase A (legacy remediation) is complete. I've created a working Wave 1 generator that produces high-quality containers, validated with 16 pilot containers successfully applied to the remediated registry.

**Current Status**:
- ✅ Phase A complete: 341 → 25 warnings (92.7% reduction)
- ✅ Remediated registry: `dna_registry_stage2_remediated.json` (590 containers, 0 errors, 25 approved warnings)
- ✅ Wave 1 pilot script: `build_stage3_wave1.py` (16 containers generated, all pass quality gates)
- ✅ Pilot patch applied successfully: 590 → 605 containers, linter still clean (0 errors, 25 warnings)

---

## Your Task: Generate 384 More Container Specs

**Goal**: Expand `build_stage3_wave1.py` to generate **400 total containers** (currently at 16, need +384 more).

### Target Distribution

| Namespace | Current | Target | Remaining |
|-----------|---------|--------|-----------|
| **ProfDNA** | 6 | 96 | +90 |
| **BehDNA** | 4 | 120 | +116 |
| **CogDNA** | 3 | 110 | +107 |
| **PsyDNA** | 3 | 102 | +99 |
| **Total** | 16 | 400 | +384 |

---

## Quality Requirements (CRITICAL)

### 1. Description Length
- **Range**: 39-60 words (enforced by `build_description()`)
- **Target**: 45-55 words (matching Stage 2 average of 45.7)
- **Format**: 3-sentence pattern:
  1. "This container examines {focus}."
  2. "It {method} evidence from {signals} to {goal}."
  3. "These insights {impact}."

### 2. Depth Constraint
- **Maximum depth**: 3 (no depth-4 containers)
- **Format**: `{Namespace}.{Parent}.{Child}` or `{Namespace}.{Child}`
- **Validation**: Enforced in `build_container()` - will raise error if depth > 3

### 3. Consent Hygiene
- Mark containers as `sensitive=True` if they contain:
  - Personal identity narratives
  - Psychological traits (beliefs, values, mental health)
  - Relationship patterns
  - Financial or socioeconomic data
  - Biographical or historical data
- Auto-sets `consent_required=True` when `sensitive=True`

### 4. Container Naming
- Use `DNA` suffix (e.g., `DecisionVelocityDNA`)
- CamelCase format
- Descriptive, specific names (avoid generic terms)

### 5. Status & Tags
- All containers: `status="prototype"` (v1 convention)
- Tags: Include namespace tag + `"stage3"` + `"wave1"`

---

## Container Spec Structure

Use the `cs()` helper function with these parameters:

```python
cs(
    namespace="ProfDNA",                    # Target namespace
    parent_path="ProfDNA.WorkStyleDecisionDNA",  # Parent container path
    name="DecisionVelocityDNA",             # Container name
    focus="how quickly professionals commit to decisions under ambiguity when deadlines compress timelines",
    signals="decision logs, sprint retrospectives, escalation patterns, commit timestamps from delivery cycles",
    goal="quantify decision latency distributions identifying adaptive versus paralyzed response modes",
    impact="help teams calibrate decision cadences matching urgency without sacrificing alignment",
    method="synthesizes",                   # Default: "synthesizes" (can vary)
    value_type="ordinal",                   # Default: "ordinal"
    tags=None,                              # Auto-generated if None
    sensitive=False                         # Set to True for sensitive data
)
```

---

## Namespace-Specific Guidance

### ProfDNA (+90 containers)
**Themes**: Career, work outcomes, collaboration, professional context, delivery, domain knowledge

**Parent Paths** (use these as anchors):
- `ProfDNA.WorkStyleDecisionDNA` (decision-making patterns)
- `ProfDNA.CollaborationCadenceDNA` (meeting load, sync rhythms, async-sync balance)
- `ProfDNA.WorkOutcomeDNA` (deliverable quality, impact, stakeholder satisfaction)
- `ProfDNA.OccupationRoleDNA` (role fit, specialization, seniority)
- `ProfDNA.DomainKnowledgeMapDNA` (technical expertise, domain depth)
- `ProfDNA.SeniorityTenureDNA` (experience levels, progression)
- `ProfDNA.CareerAspirationsMobilityDNA` (growth goals, mobility preferences)
- `ProfDNA.ComplianceRiskGovernanceDNA` (policy adherence, risk management)

**Example Ideas**:
- Stakeholder communication frequency preferences
- Code review thoroughness patterns
- Documentation quality signatures
- Technical debt tolerance
- Cross-functional collaboration effectiveness
- Remote work adaptability
- Onboarding speed patterns
- Knowledge transfer effectiveness

### BehDNA (+116 containers)
**Themes**: Productivity workflows, habits, routines, daily rhythms, micro-behaviors

**Parent Paths**:
- `BehDNA.ProductivityWorkflowDNA` (focus blocks, task management, workflow patterns)
- `BehDNA.HabitRoutinesDNA` (morning/evening routines, exercise, nutrition, sleep habits)
- `BehDNA.DailyRhythmChronoDNA` (energy peaks, chronotype patterns, circadian rhythms)
- `BehDNA.ProcrastinationStyleDNA` (avoidance patterns, deadline behaviors)
- `BehDNA.RiskTakingSafetyDNA` (behavioral risk patterns)
- `BehDNA.MicroBehaviorTicksDNA` (small observable behaviors)
- `BehDNA.AddictivePatternDNA` (compulsive behaviors)

**Example Ideas**:
- Email response latency patterns
- Meeting preparation behaviors
- Break-taking frequency
- Task-switching tolerance
- Notification management strategies
- Physical activity integration
- Hydration and meal timing patterns
- Screen time management

### CogDNA (+107 containers)
**Themes**: Reasoning, problem-solving, learning, attention, memory, cognitive styles

**Parent Paths**:
- `CogDNA.ReasoningProblemSolvingDNA` (analytical thinking, problem decomposition)
- `CogDNA.LearningStyleStrategyDNA` (learning preferences, skill acquisition)
- `CogDNA.AttentionControlDNA` (focus, distraction management, multitasking)
- `CogDNA.MemorySystemsDNA` (working memory, recall patterns)
- `CogDNA.ProcessingDynamicsDNA` (processing speed, cognitive load management)
- `CogDNA.CreativityDivergenceDNA` (creative thinking, ideation)
- `CogDNA.LanguageCognitionDNA` (verbal reasoning, language processing)
- `CogDNA.MetacognitionInsightDNA` (self-awareness, thinking about thinking)

**Example Ideas**:
- Abstract reasoning capacity
- Pattern recognition speed
- Debugging strategy preferences
- Information synthesis approaches
- Conceptual chunking patterns
- Analogical reasoning strength
- Mental model construction
- Cognitive flexibility under pressure

### PsyDNA (+99 containers)
**Themes**: Motivation, self-concept, identity, risk tolerance, beliefs, values, personality

**Parent Paths**:
- `PsyDNA.MotivationDNA` (autonomy, goal orientation, purpose alignment, novelty-seeking)
- `PsyDNA.SelfConceptSchemaDNA` (professional identity, self-esteem, self-efficacy)
- `PsyDNA.RiskToleranceDNA` (career risks, financial risks, uncertainty tolerance)
- `PsyDNA.BeliefValueDNA` (moral foundations, philosophical stances) - **SENSITIVE**
- `PsyDNA.GritPersistenceDNA` (perseverance, resilience)
- `PsyDNA.NeuroticismDNA` (anxiety, depression, emotional volatility) - **SENSITIVE**

**Example Ideas**:
- Mastery orientation strength
- Self-efficacy in technical domains
- Imposter syndrome patterns
- Growth mindset indicators
- Failure recovery patterns
- Feedback receptivity
- Achievement motivation
- Status sensitivity

**IMPORTANT**: Most PsyDNA containers dealing with beliefs, values, mental health, or deep identity should be marked `sensitive=True`.

---

## Implementation Approach

### Option 1: Manual Expansion (Recommended for Quality)
Expand the existing `build_wave1_specs()` function by adding container specs in batches:

```python
def build_wave1_specs() -> List[ContainerSpec]:
    specs = []

    # ProfDNA: +90 containers (currently 6)
    prof_specs = [
        cs("ProfDNA", "ProfDNA.WorkStyleDecisionDNA", "DecisionVelocityDNA", ...),
        cs("ProfDNA", "ProfDNA.CollaborationCadenceDNA", "StandupEngagementDNA", ...),
        # ... add 90 more
    ]
    specs.extend(prof_specs)

    # BehDNA: +116 containers (currently 4)
    beh_specs = [
        cs("BehDNA", "BehDNA.ProductivityWorkflowDNA", "DeepWorkBlockProtectionDNA", ...),
        # ... add 116 more
    ]
    specs.extend(beh_specs)

    # CogDNA: +107 containers (currently 3)
    # PsyDNA: +99 containers (currently 3)

    return specs
```

### Option 2: Template-Based Generation (For Scale)
Create container templates and generate systematically:

```python
def generate_batch_from_template(namespace, parent_paths, count_per_parent):
    """Generate containers using templates and variations."""
    # Your implementation here
    pass
```

### Recommended: Hybrid Approach
1. Manually define **100-150 high-value containers** (critical professional, behavioral, cognitive, psychological patterns)
2. Use **templates for systematic coverage** (250-300 containers covering common variations)

---

## Validation Checklist

Before finalizing, ensure:

- [ ] Total containers = 400 (ProfDNA: 96, BehDNA: 120, CogDNA: 110, PsyDNA: 102)
- [ ] All descriptions 39-60 words
- [ ] No depth-4 containers (max depth = 3)
- [ ] Sensitive containers marked with `sensitive=True`
- [ ] All containers have unique paths (no duplicates)
- [ ] All parent paths exist in base registry (validate against `dna_registry_stage2_remediated.json`)
- [ ] Run script: `python3 build_stage3_wave1.py` should output `stage3_wave1.patch.json` with 400 containers
- [ ] All tags include `stage3`, `wave1`

---

## Output Deliverable

**File**: `ReDNACoreDemo/core/ontology/stage3_wave1.patch.json`
- 400 containers total
- JSON structure: `{"containers": [...]}`
- Each container follows the schema from Stage 2 pilot

**Success Criteria**:
- Script runs without errors
- Linter passes: 0 errors (warnings OK for approved depth-4 exceptions)
- Description quality: 39-60 words, avg ~50
- Depth compliance: All new containers depth ≤3

---

## Reference Files

**Base Registry**: `ReDNACoreDemo/core/ontology/dna_registry_stage2_remediated.json`
- 590 containers (use to check parent path existence)
- All namespaces represented

**Pilot Script**: `ReDNACoreDemo/core/ontology/tools/build_stage3_wave1.py`
- 16 working container specs (reference for format)
- `cs()` helper function
- `build_description()` validation logic

**Stage 2 Reference**: `ReDNACoreDemo/core/ontology/tools/build_stage2_assets.py`
- 2,943 lines, generated 210 containers
- Shows large-scale spec patterns

---

## Next Steps After Completion

Once you've generated the 400-container patch:

1. Run the generator: `python3 build_stage3_wave1.py`
2. Apply patch: `python3 scripts/apply_registry_patch.py --registry core/ontology/dna_registry_stage2_remediated.json --patch core/ontology/stage3_wave1.patch.json --out core/ontology/dna_registry_wave1.json`
3. Validate: `python3 core/ontology/linter.py --registry core/ontology/dna_registry_wave1.json --report core/ontology/reports/LINT_WAVE1.txt`
4. Report stats in completion summary

---

## Questions?

If you encounter any issues:
- Check parent path existence in base registry
- Validate description word counts (39-60 range)
- Ensure depth ≤3 for all new containers
- Mark sensitive containers appropriately

**Target Completion**: 400 containers, all passing quality gates, ready for Phase B Wave 2 handoff.

Good luck! 🚀
