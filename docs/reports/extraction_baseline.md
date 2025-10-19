# ReDNA Extraction Quality Baseline Report

**Date**: 2025-10-16 20:02:11
**Dataset**: extraction_golden_v1.json
**Total Cases**: 52
**Runtime**: 141.10s
**Model**: Ollama (llama3.1:8b)
**Phase**: 4.0a Week 1

---

## Executive Summary

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| **Precision** | 89.47% | ≥ 95% | ❌ FAIL |
| **Recall** | 23.94% | ≥ 85% | ❌ FAIL |
| **F1 Score** | 37.78% | - | - |

---

## Confusion Matrix

| Metric | Count | Description |
|--------|-------|-------------|
| True Positives (TP) | 17 | Correctly extracted expected traits |
| False Positives (FP) | 2 | Extracted traits not expected |
| False Negatives (FN) | 54 | Expected traits not extracted |
| Total Expected | 71 | All traits expected across test cases |
| Total Extracted | 19 | All traits extracted by system |

**Accuracy**: 23.94% of expected traits were correctly extracted.

---

## Category Breakdown

Performance by test case category:

| Category | Cases | Precision | Recall | F1 | TP | FP | FN |
|----------|-------|-----------|--------|----|----|----|----|
| correction | 1 | 100.00% | 100.00% | 100.00% | 1 | 0 | 0 |
| edge_case | 4 | 100.00% | 60.00% | 75.00% | 3 | 0 | 2 |
| direct_fact | 8 | 100.00% | 37.50% | 54.55% | 3 | 0 | 5 |
| ambiguous | 4 | 100.00% | 25.00% | 40.00% | 1 | 0 | 3 |
| multi_trait | 4 | 100.00% | 25.00% | 40.00% | 4 | 0 | 12 |
| behavior | 8 | 75.00% | 23.08% | 35.29% | 3 | 1 | 10 |
| qualified_fact | 5 | 100.00% | 20.00% | 33.33% | 1 | 0 | 4 |
| indirect_signal | 5 | 100.00% | 12.50% | 22.22% | 1 | 0 | 7 |
| conversational | 4 | 0.00% | 0.00% | 0.00% | 0 | 1 | 0 |
| meta_trait | 4 | 0.00% | 0.00% | 0.00% | 0 | 0 | 4 |
| preference | 5 | 0.00% | 0.00% | 0.00% | 0 | 0 | 7 |

---

## Failed Cases

**Total Failures**: 38 (73.1% of test cases)

Cases where extraction differed from expectations:


### 1. ambiguous_002 (ambiguous)

**User Message**: "I'm pretty tall"

- **Expected traits**: PaDNA.BodyDNA.Height
- **Extracted traits**: None
- **Missing** (FN): PaDNA.BodyDNA.Height
- **Extra** (FP): None


### 2. ambiguous_003 (ambiguous)

**User Message**: "I'm in decent shape"

- **Expected traits**: BehaviorDNA.Fitness.Level
- **Extracted traits**: None
- **Missing** (FN): BehaviorDNA.Fitness.Level
- **Extra** (FP): None


### 3. ambiguous_004 (ambiguous)

**User Message**: "I'm an introvert but I like going to parties sometimes"

- **Expected traits**: BehaviorDNA.Social.Style
- **Extracted traits**: None
- **Missing** (FN): BehaviorDNA.Social.Style
- **Extra** (FP): None


### 4. behavior_003 (behavior)

**User Message**: "I usually stay in and read on weekends"

- **Expected traits**: PreferenceDNA.Social.GroupSize, BehaviorDNA.Leisure.Indoor
- **Extracted traits**: None
- **Missing** (FN): PreferenceDNA.Social.GroupSize, BehaviorDNA.Leisure.Indoor
- **Extra** (FP): None


### 5. behavior_004 (behavior)

**User Message**: "I start work at 6 AM and finish by 2 PM"

- **Expected traits**: BehaviorDNA.Schedule.WorkHours, BehaviorDNA.Sleep.Chronotype
- **Extracted traits**: BehaviorDNA.Work.Location
- **Missing** (FN): BehaviorDNA.Schedule.WorkHours, BehaviorDNA.Sleep.Chronotype
- **Extra** (FP): BehaviorDNA.Work.Location


### 6. behavior_005 (behavior)

**User Message**: "I meal prep every Sunday for the week"

- **Expected traits**: BehaviorDNA.Organization.Level, BehaviorDNA.Health.Diet
- **Extracted traits**: None
- **Missing** (FN): BehaviorDNA.Organization.Level, BehaviorDNA.Health.Diet
- **Extra** (FP): None


### 7. behavior_006 (behavior)

**User Message**: "I always reply to texts within an hour"

- **Expected traits**: BehaviorDNA.Communication.ResponseStyle
- **Extracted traits**: None
- **Missing** (FN): BehaviorDNA.Communication.ResponseStyle
- **Extra** (FP): None


### 8. behavior_007 (behavior)

**User Message**: "I drink three cups of coffee every morning"

- **Expected traits**: BehaviorDNA.Health.CaffeineIntake, BehaviorDNA.Routine.Morning
- **Extracted traits**: None
- **Missing** (FN): BehaviorDNA.Health.CaffeineIntake, BehaviorDNA.Routine.Morning
- **Extra** (FP): None


### 9. behavior_008 (behavior)

**User Message**: "I learn best by doing hands-on projects"

- **Expected traits**: BehaviorDNA.Learning.Style
- **Extracted traits**: None
- **Missing** (FN): BehaviorDNA.Learning.Style
- **Extra** (FP): None


### 10. conversational_004 (conversational)

**User Message**: "Got it, thanks!"

- **Expected traits**: None
- **Extracted traits**: BehaviorDNA.Work.Location
- **Missing** (FN): None
- **Extra** (FP): BehaviorDNA.Work.Location


### 11. direct_fact_001 (direct_fact)

**User Message**: "I am 6 feet tall"

- **Expected traits**: PaDNA.BodyDNA.Height
- **Extracted traits**: None
- **Missing** (FN): PaDNA.BodyDNA.Height
- **Extra** (FP): None


### 12. direct_fact_004 (direct_fact)

**User Message**: "I'm 30 years old"

- **Expected traits**: BasicDNA.Age
- **Extracted traits**: None
- **Missing** (FN): BasicDNA.Age
- **Extra** (FP): None


### 13. direct_fact_005 (direct_fact)

**User Message**: "I'm a woman"

- **Expected traits**: BasicDNA.Gender
- **Extracted traits**: None
- **Missing** (FN): BasicDNA.Gender
- **Extra** (FP): None


### 14. direct_fact_006 (direct_fact)

**User Message**: "I live in San Francisco"

- **Expected traits**: BasicDNA.Location.City
- **Extracted traits**: None
- **Missing** (FN): BasicDNA.Location.City
- **Extra** (FP): None


### 15. direct_fact_007 (direct_fact)

**User Message**: "I work as a software engineer"

- **Expected traits**: BasicDNA.Occupation
- **Extracted traits**: None
- **Missing** (FN): BasicDNA.Occupation
- **Extra** (FP): None


### 16. edge_case_001 (edge_case)

**User Message**: "I'm 183 centimeters tall"

- **Expected traits**: PaDNA.BodyDNA.Height
- **Extracted traits**: None
- **Missing** (FN): PaDNA.BodyDNA.Height
- **Extra** (FP): None


### 17. edge_case_004 (edge_case)

**User Message**: "I'm usually up by 5:30 AM and in bed by 9 PM"

- **Expected traits**: BehaviorDNA.Sleep.Chronotype, BehaviorDNA.Sleep.Duration
- **Extracted traits**: BehaviorDNA.Sleep.Chronotype
- **Missing** (FN): BehaviorDNA.Sleep.Duration
- **Extra** (FP): None


### 18. indirect_001 (indirect_signal)

**User Message**: "I take cold showers every morning"

- **Expected traits**: BehaviorDNA.Wellness.ColdTherapy
- **Extracted traits**: None
- **Missing** (FN): BehaviorDNA.Wellness.ColdTherapy
- **Extra** (FP): None


### 19. indirect_003 (indirect_signal)

**User Message**: "Ugh, it's raining again, I was hoping to go for a run"

- **Expected traits**: BehaviorDNA.Exercise.Outdoor, BehaviorDNA.Exercise.Type
- **Extracted traits**: None
- **Missing** (FN): BehaviorDNA.Exercise.Outdoor, BehaviorDNA.Exercise.Type
- **Extra** (FP): None


### 20. indirect_004 (indirect_signal)

**User Message**: "Looking forward to a quiet weekend with no plans"

- **Expected traits**: BehaviorDNA.Social.Style, PreferenceDNA.Social.GroupSize
- **Extracted traits**: None
- **Missing** (FN): BehaviorDNA.Social.Style, PreferenceDNA.Social.GroupSize
- **Extra** (FP): None


*...and 18 more failures (see full test output)*

---

## Recommendations

Based on the baseline results:

- ⚠️ **Precision below target** (89.47% < 95%): System is extracting traits that weren't expected. Review false positive patterns to identify over-extraction issues.
- ⚠️ **Recall below target** (23.94% < 85%): System is missing expected trait extractions. Review false negative patterns to identify under-extraction issues.

### Category-Specific Issues

- **direct_fact**: F1=54.55% (Precision=100.00%, Recall=37.50%)
- **ambiguous**: F1=40.00% (Precision=100.00%, Recall=25.00%)
- **multi_trait**: F1=40.00% (Precision=100.00%, Recall=25.00%)
- **behavior**: F1=35.29% (Precision=75.00%, Recall=23.08%)
- **qualified_fact**: F1=33.33% (Precision=100.00%, Recall=20.00%)
- **indirect_signal**: F1=22.22% (Precision=100.00%, Recall=12.50%)
- **meta_trait**: F1=0.00% (Precision=0.00%, Recall=0.00%)
- **preference**: F1=0.00% (Precision=0.00%, Recall=0.00%)

---

## Next Steps

1. Review failed cases and adjust extraction logic or golden dataset expectations
2. Implement confidence calibration analysis
3. Add timing metrics for each extraction hop
4. Set up automated regression testing in CI/CD
5. Begin Phase 4.0b observability panel development

---

*Generated by test_extraction_quality.py*
