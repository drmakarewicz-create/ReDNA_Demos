# ReDNA UCN Propagation Policy (AI-First Hierarchical)

**Version:** 1.0 (Phase 9)
**Generated:** 2025-10-20
**Source:** `ReDNACoreDemo/core/ucn_rr_service.py` (lines 30-66)

## Overview

This document describes the **AI-First Hierarchical UCN Propagation** policy introduced in Phase 9. This policy governs how UCN (Universal Confidence Number) values propagate from child traits to parent DNA categories in the ReDNA hierarchy.

**Key Principle:** AI reasoning layer determines parent UCN using child UCNs as **strong priors**, NOT via hard formulas.

---

## Phase 10 Context

### ReDNA Hierarchy

```
ReDNA (root, tier-0)
├── RelDNA (tier-1)
├── PaDNA (tier-1)
│   ├── HairDNA (tier-2)
│   │   ├── Color (tier-3)
│   │   └── Texture (tier-3)
│   └── EyeDNA (tier-2)
│       └── Color (tier-3)
├── BehDNA (tier-1)
├── CogDNA (tier-1)
└── EmoDNA (tier-1)
```

**UCN Scale:**
- Internal: 0-1000 (stored in system)
- User-facing: Normalized to percentiles via Why-Cards

**RR Scale (Phase 9 separation):**
- Internal: 0-1000 (legacy, computed by rr_engine)
- User-facing: 0-100 percentile (via `rr_to_percentile()` adapter at egress)

---

## The Five Guiding Principles

### 1. READ Child Trait UCNs as Strong Priors

**Guidance:** When assigning or updating a parent DNA's UCN, the AI reasoning layer should start by reading child trait UCNs.

**Examples:**

- **Scenario A: High Consensus**
  - `PaDNA.HairDNA.Color` UCN = 850
  - `PaDNA.HairDNA.Texture` UCN = 800
  - `PaDNA.HairDNA.Length` UCN = 820
  - **Implication:** Parent `PaDNA.HairDNA` should have high UCN (e.g., 820-850)

- **Scenario B: Mixed Confidence**
  - `PaDNA.EyeDNA.Color` UCN = 900 (photo evidence)
  - `PaDNA.EyeDNA.Shape` UCN = 450 (weak inference)
  - **Implication:** Consider what mixed confidence means - strong evidence for one aspect, weak for another

- **Scenario C: No Child Traits Yet**
  - `BehDNA` has no child traits
  - **Implication:** Start with LOW parent UCN until evidence emerges

**Key Point:** Child UCNs are NOT blindly averaged - they inform AI reasoning about parent confidence.

---

### 2. WEIGH Parent-Level Evidence Separately

**Guidance:** Direct observations about the parent category should be considered independently of child traits.

**Factors to Consider:**

- **Recency of Child Evidence:**
  - If child trait was observed 2 years ago → lower parent confidence
  - Recent child evidence → higher parent confidence

- **Contradictions Between Children:**
  - If `PaDNA.HairDNA.Color` has conflicting values (e.g., "Brown" vs "Black")
  - Parent `PaDNA.HairDNA` UCN should be LOWER until conflict is resolved

- **Direct Parent Observations:**
  - Example: User says "My hair is very distinctive"
  - This is parent-level evidence about `PaDNA.HairDNA` overall, not about Color/Texture specifically
  - Should boost parent UCN even if child UCNs are mixed

**Key Point:** Parent UCN is not purely a function of children - parent-level signals matter.

---

### 3. USE DISCRETION Over Formulas

**Guidance:** Do NOT compute parent UCN as `mean(child UCNs)`. Instead, reason about what the child UCNs imply.

**Anti-Pattern (WRONG):**
```python
# DON'T DO THIS
parent_ucn = sum(child.ucn for child in children) / len(children)
```

**Correct Approach (AI Reasoning):**

```python
# Example reasoning trace (pseudocode)
if all_children_high_ucn(>750):
    parent_ucn = high (750-850)
    reasoning = "All child traits have strong evidence"
elif mixed_ucn:
    if recent_evidence_is_high:
        parent_ucn = medium_high (600-750)
        reasoning = "Recent evidence is strong, older evidence is weak"
    else:
        parent_ucn = medium (500-600)
        reasoning = "Mixed evidence quality across children"
elif no_children:
    parent_ucn = low (0-300)
    reasoning = "No child traits observed yet"
```

**Example from Phase 9:**

```
PaDNA.HairDNA.Color UCN = 850
PaDNA.HairDNA.Texture UCN = 800

AI reasoning:
- Both children have high UCN (>750)
- Evidence is recent (within 30 days)
- No contradictions detected
- Direct parent evidence: User uploaded clear hair photo

→ PaDNA.HairDNA UCN = 820-850 (high confidence in hair traits overall)
```

**Key Point:** AI discretion, not mathematical formulas, determines parent UCN.

---

### 4. EXPLAIN Divergences via Why-Cards

**Guidance:** If parent UCN diverges significantly from child consensus, create a Why-Card explaining the reasoning.

**Divergence Threshold:** ±200 points (0-1000 scale)

**What to Explain in Why-Card:**

1. **What child UCNs were considered?**
   - List all children and their UCNs
   - Note any outliers or conflicts

2. **What parent-level signals were weighed?**
   - Recent evidence?
   - Direct parent observations?
   - Contradictions or conflicts?

3. **Why does the parent UCN differ from simple averaging?**
   - Recency weighting?
   - Conflict resolution?
   - Parent-level evidence override?

4. **What new data would increase/decrease confidence?**
   - Suggestions for curiosity loop
   - What evidence gaps exist?

**Example Why-Card (Divergence Scenario):**

```
Trait: PaDNA.HairDNA
Parent UCN: 650
Child UCNs: Color=850, Texture=450

Q: Why is my HairDNA confidence only 650 when Color has 850?

A: Your hair color has strong evidence from a recent photo (UCN=850),
   but hair texture has weak evidence (UCN=450) because the photo
   lighting made texture hard to assess. We're waiting for better
   evidence about texture before marking the overall HairDNA category
   as highly confident.

   To increase confidence: Upload a photo with better lighting or
   answer the question "How would you describe your hair texture?"
```

**Key Point:** Transparency through Why-Cards builds user trust in AI reasoning.

---

### 5. NEVER Expose UCN as RR

**Guidance (Phase 9 Critical Fix):** UCN and RR are separate concepts with different scales.

**Correct Usage:**

- **UCN (Universal Confidence Number):**
  - Scale: 0-1000 (internal only)
  - Meaning: How confident we are in this trait value
  - Never shown directly to users

- **RR (Rarity Rating):**
  - Scale: 0-100 (user-facing percentile)
  - Meaning: How rare/common this trait is in the population
  - Shown to users in UI and Why-Cards

- **Adapter at Egress:**
  - Always use `rr_to_percentile()` when returning RR to user
  - Converts internal 0-1000 scale to user-facing 0-100 percentile

**Anti-Pattern (WRONG - Phase 9 Bug):**
```python
# DON'T DO THIS
user_data = {
    "rr": trait.ucn  # BUG! This exposes UCN as RR
}
```

**Correct Pattern:**
```python
# DO THIS
from . import rr_engine

user_data = {
    "rr": rr_engine.rr_to_percentile(trait.rr_score),  # Normalized to 0-100
    "curiosity": 100 - rr_engine.rr_to_percentile(trait.rr_score)  # 0-100 scale
}
# UCN is NOT exposed to user
```

**Key Point:** UCN is internal confidence. RR is user-facing rarity percentile. Never mix them.

---

## Soft Scaffolding (Not Hard Constraints)

**Guideline:** Parent UCN should generally be within ±200 points of child average (0-1000 scale).

**When to Diverge:**
- Strong parent-level evidence overrides children
- Major recency differences between children
- Unresolved conflicts between children

**What Happens on Large Divergence (>200 points):**
- Automatically trigger Why-Card generation
- Log reasoning trace for debugging
- Flag for manual review if divergence is extreme (>400 points)

**No Parent UCN Assigned If:**
- No child data exists AND
- No direct parent-level evidence exists
- → Parent trait not included in snapshot until evidence emerges

---

## Implementation Notes

### Where This Policy is Applied

**Service:** `ReDNACoreDemo/core/ucn_rr_service.py`

**Function:** `assess_observations_and_inferences()`

**Pipeline Stage:** UCN/RR Validation (after Head Coach inference, before Core synthesis)

### AI Reasoning Hooks

**Current Implementation (Phase 9):**
- Head Coach proposes inferences with confidence scores
- UCN/RR service validates and adjusts UCN based on:
  - Source observation quality
  - Known correlations in population data
  - Consistency with existing profile

**Future Enhancement (Phase 10+):**
- Add parent-child propagation logic to UCN/RR service
- Implement Why-Card generation on divergence
- Add recency weighting for child traits
- Support hierarchical normalization for ontology navigation

### Integration with Ontology (Phase 10)

**Hierarchy Traversal:**
```python
from ReDNACoreDemo.core.graph import ontology

# Get parent node
parent_node = ontology.get_parent(trait_path="PaDNA.HairDNA.Color")
# Returns: PaDNA.HairDNA

# Get all children
children = ontology.get_children(trait_path="PaDNA.HairDNA")
# Returns: [PaDNA.HairDNA.Color, PaDNA.HairDNA.Texture, ...]

# Calculate parent UCN using AI reasoning
parent_ucn = ai_reason_parent_ucn(
    children=[child.ucn for child in children],
    parent_evidence=get_parent_observations(parent_node),
    recency_weights=calculate_recency_weights(children)
)
```

---

## Examples

### Example 1: High Consensus (No Divergence)

**Scenario:**
- `PaDNA.EyeDNA.Color` UCN = 900 (photo evidence, 5 days ago)
- `PaDNA.EyeDNA.Shape` UCN = 850 (photo evidence, 5 days ago)

**AI Reasoning:**
- Both children high UCN (>750) ✓
- Recent evidence (within 7 days) ✓
- No contradictions ✓
- No direct parent evidence

**Result:**
- Parent `PaDNA.EyeDNA` UCN = 875 (average-ish, within ±200 range)
- No Why-Card needed (no divergence)

---

### Example 2: Mixed Confidence (Moderate Divergence)

**Scenario:**
- `PaDNA.HairDNA.Color` UCN = 850 (photo, 2 days ago)
- `PaDNA.HairDNA.Texture` UCN = 450 (weak inference, 2 days ago)
- `PaDNA.HairDNA.Length` UCN = 600 (user statement, 30 days ago)

**AI Reasoning:**
- Mixed UCN (850, 600, 450) → avg = 633
- Recent evidence for Color and Texture (within 7 days)
- Older evidence for Length (30 days)
- Color has strongest evidence → weight higher
- No parent-level evidence

**Result:**
- Parent `PaDNA.HairDNA` UCN = 650 (weighted toward recent high-confidence child)
- Why-Card: "Your hair color has strong evidence (UCN=850), but texture is less certain (UCN=450)..."
- Divergence: |650 - 633| = 17 points (< 200 threshold, but Why-Card generated due to mixed children)

---

### Example 3: Conflict (Large Divergence)

**Scenario:**
- `PaDNA.EyeDNA.Color` (candidate 1) = "Blue", UCN = 820 (photo, 5 days ago)
- `PaDNA.EyeDNA.Color` (candidate 2) = "Green", UCN = 680 (user statement, 10 days ago)
- Conflict detected, resolution pending

**AI Reasoning:**
- Children have conflicting values
- Conflict unresolved → high uncertainty
- Photo evidence usually stronger than statement
- But user knows their own eye color

**Result:**
- Parent `PaDNA.EyeDNA` UCN = 500 (low confidence due to unresolved conflict)
- Child avg would be ~750, but conflict → -250 penalty
- Why-Card: "Your eye color has conflicting evidence (photo says Blue, you said Green). We need clarification before marking this as confident."
- Divergence: |500 - 750| = 250 points (> 200 threshold, Why-Card required)

---

### Example 4: No Children (Placeholder Parent)

**Scenario:**
- `BehDNA` has no child traits yet
- No direct observations about BehDNA

**AI Reasoning:**
- No children → no evidence
- No parent-level evidence
- Cannot assign meaningful UCN

**Result:**
- Parent `BehDNA` NOT included in snapshot
- No UCN assigned (or UCN = 0 if stored)
- Why-Card: Not applicable (user hasn't seen this DNA category yet)

---

## Phase 9 Critical Fixes

### Fix 1: UCN ≠ RR

**Problem:** Phase 8 code sometimes exposed `ucn` as `rr` to users.

**Fix:** Phase 9 added 5 runtime guards:
1. Trait egress normalization (`rr_to_percentile()`)
2. Curiosity formula: `curiosity = 100 - RR` (0-100 scale)
3. API response validation (ensure RR is 0-100)
4. Why-Card generation uses normalized RR
5. Frontend expects RR as 0-100 percentile

### Fix 2: Guarded Normalization

**Problem:** RR was inconsistently scaled (sometimes 0-1000, sometimes 0-100).

**Fix:** Phase 9 added **normalize_audit.jsonl** to track all RR conversions:
```jsonl
{
  "trait_path": "PaDNA.HairDNA.Color",
  "rr_internal": 456.78,
  "rr_percentile": 45.68,
  "conversion": "rr_to_percentile",
  "timestamp": "2025-10-19T14:32:00Z"
}
```

### Fix 3: No Deterministic Bypasses

**Problem:** Phase 7 had `READINESS_SKIP_CORE_HEALTH` flag to bypass health checks.

**Fix:** Phase 7 removed all deterministic bypasses. No flags should skip validation logic.

---

## Testing Propagation Logic

### Unit Tests

**Location:** `tests/graph/test_ucn_propagation.py` (future)

**Test Cases:**
1. High consensus → high parent UCN
2. Mixed confidence → weighted parent UCN
3. No children → no parent UCN
4. Conflict detected → low parent UCN + Why-Card
5. Large divergence (>200) → Why-Card required
6. Recent vs old evidence → recency weighting

### Integration Tests

**Location:** `tests/api/test_hierarchy_ucn.py` (future)

**Test Cases:**
1. Ingest photo → child traits get UCN → parent traits get propagated UCN
2. Resolve conflict → parent UCN updates accordingly
3. Why-Card generation on divergence
4. Ontology navigation (get parent/children)

---

## Future Enhancements

### Phase 11+: Machine Learning

**Idea:** Train ML model to predict parent UCN from child UCNs + context.

**Inputs:**
- Child UCN values
- Child evidence sources
- Child recency (days since observation)
- Parent-level observations (if any)
- Historical resolution patterns

**Output:**
- Predicted parent UCN
- Confidence in prediction
- Explanation (SHAP values for Why-Card)

### Phase 12+: Temporal Dynamics

**Idea:** Model UCN decay over time.

**Examples:**
- Physical traits (hair color) may change → UCN decays over months
- Stable traits (eye color) → UCN persists for years
- Behavioral traits → UCN decays over weeks

### Phase 13+: Cross-Tier Correlations

**Idea:** Use correlations across tier-1 systems to boost confidence.

**Example:**
- High UCN for `PaDNA.Chronotype=Morning` correlates with `BehDNA.Exercise.PreferredTime=Morning`
- If both observed → boost parent `BehDNA` UCN due to consistency

---

## Summary

**AI-First Propagation Policy (Phase 9):**

1. **Read** child UCNs as strong priors (not hard rules)
2. **Weigh** parent-level evidence separately (recency, conflicts, observations)
3. **Use discretion** over formulas (AI reasoning, not `mean()`)
4. **Explain** divergences via Why-Cards (transparency)
5. **Never expose** UCN as RR (separate concepts, separate scales)

**Soft Scaffolding:**
- Parent UCN generally within ±200 of child avg
- Large divergence (>200) triggers Why-Card
- No parent UCN if no children + no parent evidence

**Key Principle:** AI reasoning determines parent UCN. Child UCNs inform but don't dictate.
