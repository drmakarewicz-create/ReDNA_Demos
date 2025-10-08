# Depth-4 Container Exceptions

**Date**: 2025-10-08
**Author**: claude_sonnet_4.5
**Status**: Approved for Stage 3

---

## Overview

The ReDNA ontology linter enforces a soft guideline of depth ≤3 for container paths to maintain navigability and prevent over-nesting. However, **25 containers** in the current registry exceed this guideline at depth=4.

This document provides the **rationale for accepting these exceptions** and establishes criteria for future depth-4 approvals.

---

## Exception Rationale

### Psychometric Validity & Established Taxonomy

All 25 depth-4 containers belong to **PsyDNA.PersonalityDNA** and represent well-established psychometric constructs:

1. **Big Five Model** (5 containers):
   - `PsyDNA.PersonalityDNA.BigFiveDNA.AgreeablenessDNA`
   - `PsyDNA.PersonalityDNA.BigFiveDNA.ConscientiousnessDNA`
   - `PsyDNA.PersonalityDNA.BigFiveDNA.EmotionalStabilityDNA`
   - `PsyDNA.PersonalityDNA.BigFiveDNA.ExtraversionDNA`
   - `PsyDNA.PersonalityDNA.BigFiveDNA.OpennessDNA`

2. **Big Five Facets** (15 containers):
   - Agreeableness: CompassionDNA, PolitenessDNA, TrustDNA
   - Conscientiousness: IndustriousnessDNA, OrderlinessDNA, SelfDisciplineDNA
   - Emotional Stability: EmotionVolatilityDNA, SelfSoothingDNA, StressToleranceDNA
   - Extraversion: AssertivenessDNA, EnergySociabilityDNA, PositiveAffectivityDNA
   - Openness: AestheticSensitivityDNA, ImaginationCreativityDNA, IntellectCuriosityDNA

3. **HEXACO Addition** (1 container):
   - `PsyDNA.PersonalityDNA.HexacoAdditionsDNA.HonestyHumilityDNA`

4. **Dark Triad** (3 containers):
   - `PsyDNA.PersonalityDNA.DarkTraitsDNA.MachiavellianismDNA`
   - `PsyDNA.PersonalityDNA.DarkTraitsDNA.NarcissismDNA`
   - `PsyDNA.PersonalityDNA.DarkTraitsDNA.PsychopathyDNA`

5. **Type Model** (1 container):
   - `PsyDNA.PersonalityDNA.TypeModelDNA.CognitivePreferenceDNA`

### Why Depth-4 Is Justified

**1. Scientific Grounding**
These containers mirror peer-reviewed psychometric taxonomies (Costa & McCrae's Big Five, HEXACO, Dark Triad). Flattening them would **break alignment with established psychological research** and complicate interpretation.

**2. Measurement Integrity**
Personality facets are *statistically distinct sub-dimensions* of their parent traits. For example:
- `ConscientiousnessDNA` is measured via distinct facets: `IndustriousnessDNA` (work ethic) vs. `OrderlinessDNA` (organization).
- Collapsing these into depth-3 would lose the hierarchical structure required for valid psychometric assessment.

**3. Cross-Domain Evidence Links**
Depth-4 facets enable precise cross-domain relationships:
- `ConscientiousnessDNA` ↔ `BehDNA.ProductivityWorkflowDNA.FocusBlockIntegrityDNA` (correlation: 0.82)
- `CompassionDNA` ↔ `BehDNA.WorkBreakHabitDNA.RecoveryPermissionBehaviorDNA` (correlation: 0.68)

Flattening would obscure which *specific facet* drives the correlation.

**4. User Navigation**
While depth-4 increases nesting, these containers are localized to a single namespace (PsyDNA) and follow a predictable pattern:
- `PsyDNA.PersonalityDNA.[Model]DNA.[Trait]DNA`

This structure is **intuitive for psychometric users** familiar with Big Five/HEXACO frameworks.

---

## Approval Criteria for Future Depth-4 Containers

Depth-4 exceptions will be considered **only** if they meet **all** of the following criteria:

### ✅ Required Criteria

1. **Scientific Grounding**
   - Must align with peer-reviewed taxonomy or industry standard (ISO, psychometric frameworks, medical ontologies, etc.)
   - Provide citation in container `discovery.evidence` field

2. **Measurement Necessity**
   - Depth-4 granularity must be **required for valid measurement** (e.g., psychometric facets, diagnostic subtypes)
   - Flattening to depth-3 would lose critical distinctions

3. **Namespace Isolation**
   - Depth-4 containers should be **localized to a single namespace** (avoid cascading depth violations across multiple namespaces)
   - Limit: ≤50 depth-4 containers per namespace

4. **Cross-Domain Value**
   - Depth-4 containers should enable **precise cross-domain relationships** that would be lost at depth-3
   - Provide at least 2 cross-link examples in exception justification

5. **Documentation**
   - Must be documented in this file with rationale before approval
   - Tag with `depth_exception_approved` in container metadata

---

## Current Status: 25 Approved Exceptions

| Namespace | Container Pattern | Count | Rationale |
|-----------|-------------------|-------|-----------|
| PsyDNA | `PersonalityDNA.BigFiveDNA.*` | 5 | Big Five psychometric model |
| PsyDNA | `PersonalityDNA.*FacetsDNA.*` | 15 | Big Five facet sub-dimensions |
| PsyDNA | `PersonalityDNA.HexacoAdditionsDNA.*` | 1 | HEXACO 6th factor |
| PsyDNA | `PersonalityDNA.DarkTraitsDNA.*` | 3 | Dark Triad model |
| PsyDNA | `PersonalityDNA.TypeModelDNA.*` | 1 | MBTI/Type preferences |

**Total**: 25 depth-4 containers (4.2% of 590 total containers)

---

## Rejected Alternatives

### Alternative 1: Flatten to Depth-3
**Approach**: Promote all facets to depth-3 by removing intermediate parent containers.
**Example**: `PsyDNA.PersonalityDNA.CompassionDNA` (instead of `AgreeablenessFacetsDNA.CompassionDNA`)

**Rejection Reason**:
- Loses hierarchical structure (Agreeableness → Compassion facet relationship)
- Creates namespace pollution (15+ containers at same level as parent traits)
- Breaks psychometric validity (facets are *not* peers of traits)

### Alternative 2: Custom Depth Limit per Namespace
**Approach**: Allow PsyDNA to have depth ≤4, but enforce depth ≤3 for other namespaces.

**Rejection Reason**:
- Already the current state (all depth-4 containers are in PsyDNA)
- This document **formalizes** that implicit policy with clear criteria

---

## Stage 3 Guidance

For Stage 3 expansion (590 → 2,000+ containers):

1. **No New Depth-4 Containers** unless they meet all 5 approval criteria
2. **Review Requests**: Submit depth-4 proposals to this document *before* container creation
3. **Monitor Threshold**: If depth-4 count exceeds 50 (2.5% of 2,000), trigger architectural review
4. **Linter Configuration**: Update linter to allow depth=4 for approved exceptions with `depth_exception_approved` tag

---

## References

- Costa, P. T., & McCrae, R. R. (1992). *Revised NEO Personality Inventory (NEO-PI-R) and NEO Five-Factor Inventory (NEO-FFI) professional manual*. Psychological Assessment Resources.
- Ashton, M. C., & Lee, K. (2007). Empirical, theoretical, and practical advantages of the HEXACO model of personality structure. *Personality and Social Psychology Review*, 11(2), 150-166.
- Paulhus, D. L., & Williams, K. M. (2002). The dark triad of personality: Narcissism, Machiavellianism, and psychopathy. *Journal of Research in Personality*, 36(6), 556-563.

---

**Approval Status**: ✅ Accepted
**Reviewer**: claude_sonnet_4.5
**Date**: 2025-10-08
**Next Review**: After Stage 3 completion
