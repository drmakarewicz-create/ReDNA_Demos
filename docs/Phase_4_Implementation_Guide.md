# ReDNA Phase 4 — Implementation Guide

**Version**: 1.0
**Date**: 2025-10-16
**Status**: Ready for execution

This guide provides detailed implementation steps for Phase 4, broken into actionable tasks.

---

## Quick Start: First 2 Weeks

### Week 1: Golden Datasets & Instrumentation

#### Task 4.0a.1.1: Create Extraction Golden Dataset

**File**: `tests/golden/extraction_test_cases.json`

```json
[
  {
    "id": "direct_fact_001",
    "category": "direct_fact",
    "user_message": "I am 6 feet tall",
    "expected_extractions": [
      {
        "trait_id": "PaDNA.BodyDNA.Height",
        "value": {"text": "6 feet tall"},
        "confidence_llm_min": 0.7,
        "confidence_llm_max": 0.95,
        "extraction_context": "Direct self-report"
      }
    ]
  },
  {
    "id": "direct_fact_002",
    "category": "direct_fact",
    "user_message": "I have blue eyes",
    "expected_extractions": [
      {
        "trait_id": "PaDNA.EyeDNA.IrisColor",
        "value": {"enum": "blue"},
        "confidence_llm_min": 0.8,
        "confidence_llm_max": 0.95
      }
    ]
  },
  {
    "id": "qualified_fact_001",
    "category": "qualified_fact",
    "user_message": "I think I'm about six feet tall",
    "expected_extractions": [
      {
        "trait_id": "PaDNA.BodyDNA.Height",
        "value": {"text": "about six feet tall"},
        "confidence_llm_min": 0.4,
        "confidence_llm_max": 0.7,
        "ambiguity_flags": ["hedging_language"]
      }
    ]
  },
  {
    "id": "ambiguous_001",
    "category": "ambiguous",
    "user_message": "My eyes are kind of blueish gray",
    "expected_extractions": [
      {
        "trait_id": "PaDNA.EyeDNA.IrisColor",
        "value": {"enum": "blue-gray"},
        "confidence_llm_min": 0.3,
        "confidence_llm_max": 0.6,
        "ambiguity_flags": ["multiple_interpretations"],
        "requires_confirmation": true
      }
    ]
  },
  {
    "id": "preference_001",
    "category": "preference",
    "user_message": "I love pizza",
    "expected_extractions": [
      {
        "trait_id": "PreferenceDNA.Food.Pizza",
        "value": {"text": "likes"},
        "confidence_llm_min": 0.6,
        "confidence_llm_max": 0.9
      }
    ]
  },
  {
    "id": "behavior_001",
    "category": "behavior",
    "user_message": "I go hiking every weekend",
    "expected_extractions": [
      {
        "trait_id": "BehaviorDNA.Exercise.Outdoor",
        "value": {"text": "frequent"},
        "confidence_llm_min": 0.6,
        "confidence_llm_max": 0.85
      },
      {
        "trait_id": "BehaviorDNA.Exercise.Frequency",
        "value": {"text": "weekly"},
        "confidence_llm_min": 0.7,
        "confidence_llm_max": 0.9
      }
    ]
  },
  {
    "id": "indirect_001",
    "category": "indirect_signal",
    "user_message": "I take cold showers every morning",
    "expected_extractions": [
      {
        "trait_id": "BehaviorDNA.Wellness.ColdTherapy",
        "value": {"text": "daily"},
        "confidence_llm_min": 0.6,
        "confidence_llm_max": 0.85
      }
    ]
  },
  {
    "id": "multi_trait_001",
    "category": "multi_trait",
    "user_message": "I'm a 30-year-old woman with brown hair and green eyes",
    "expected_extractions": [
      {
        "trait_id": "BasicDNA.Age",
        "value": {"number": 30},
        "confidence_llm_min": 0.85,
        "confidence_llm_max": 0.95
      },
      {
        "trait_id": "BasicDNA.Gender",
        "value": {"enum": "female"},
        "confidence_llm_min": 0.85,
        "confidence_llm_max": 0.95
      },
      {
        "trait_id": "PaDNA.HairDNA.Color.Natural",
        "value": {"enum": "brown"},
        "confidence_llm_min": 0.8,
        "confidence_llm_max": 0.95
      },
      {
        "trait_id": "PaDNA.EyeDNA.IrisColor",
        "value": {"enum": "green"},
        "confidence_llm_min": 0.8,
        "confidence_llm_max": 0.95
      }
    ]
  },
  {
    "id": "conversational_001",
    "category": "conversational",
    "user_message": "How are you doing today?",
    "expected_extractions": []
  },
  {
    "id": "meta_001",
    "category": "meta_trait",
    "user_message": "I don't know my exact height",
    "expected_extractions": [
      {
        "trait_id": "PaDNA.BodyDNA.Height",
        "value": {"text": "unknown"},
        "confidence_llm_min": 0.0,
        "confidence_llm_max": 0.2,
        "meta_signal": "uncertainty_high"
      }
    ]
  }
]
```

**Action Items**:
1. Create directory: `mkdir -p tests/golden`
2. Create this file with 50+ test cases (expand above examples)
3. Cover all categories: direct, qualified, ambiguous, preference, behavior, indirect, multi-trait, conversational, meta
4. Include edge cases: contradictions, corrections, numeric values, units

---

#### Task 4.0a.1.2: Implement Extraction Quality Tests

**File**: `tests/test_extraction_quality.py`

```python
"""
Extraction Quality Tests — Phase 4.0a.1

Tests HC extraction against golden dataset to measure precision and recall.
"""
import json
import pytest
from pathlib import Path
from typing import List, Dict, Any

# Import HC extraction function
from ReDNACoreDemo.core.ingest.extractors.preference_extractor import extract_from_message

GOLDEN_DATA_PATH = Path(__file__).parent / "golden" / "extraction_test_cases.json"


def load_golden_data() -> List[Dict[str, Any]]:
    """Load golden test cases."""
    with open(GOLDEN_DATA_PATH) as f:
        return json.load(f)


def normalize_trait_id(trait_id: str) -> str:
    """Normalize trait ID for comparison (handle legacy vs. canonical)."""
    from ReDNACoreDemo.core.traits.trait_id_mapper import canonicalize_trait_id
    return canonicalize_trait_id(trait_id)


def compute_precision_recall(extracted: List[Dict], expected: List[Dict]) -> Dict[str, float]:
    """
    Compute precision and recall for extraction.

    Precision = (true positives) / (true positives + false positives)
    Recall = (true positives) / (true positives + false negatives)
    """
    if not expected:
        # No expected extractions — precision is 100% if we extracted nothing, 0% otherwise
        return {"precision": 1.0 if not extracted else 0.0, "recall": 1.0}

    if not extracted:
        # Expected items but got nothing — 0 recall
        return {"precision": 1.0, "recall": 0.0}

    # Normalize trait IDs
    extracted_ids = {normalize_trait_id(e.get("trait_id", "")) for e in extracted}
    expected_ids = {normalize_trait_id(e.get("trait_id", "")) for e in expected}

    true_positives = len(extracted_ids & expected_ids)
    false_positives = len(extracted_ids - expected_ids)
    false_negatives = len(expected_ids - extracted_ids)

    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0.0

    return {"precision": precision, "recall": recall}


def validate_confidence_range(extracted: Dict, expected: Dict) -> bool:
    """Check if extracted confidence is within expected range."""
    conf = extracted.get("confidence_llm", extracted.get("confidence", 0))
    min_conf = expected.get("confidence_llm_min", 0)
    max_conf = expected.get("confidence_llm_max", 1.0)
    return min_conf <= conf <= max_conf


@pytest.mark.parametrize("test_case", load_golden_data(), ids=lambda tc: tc["id"])
def test_extraction_quality(test_case: Dict[str, Any]):
    """Test extraction quality against golden data."""
    user_message = test_case["user_message"]
    expected = test_case["expected_extractions"]

    # Run extraction
    extracted = extract_from_message(user_message, user_id="test_user")

    # Compute metrics
    metrics = compute_precision_recall(extracted, expected)

    # Assertions
    assert metrics["precision"] >= 0.95, f"Precision too low: {metrics['precision']:.2f} for '{user_message}'"
    assert metrics["recall"] >= 0.85, f"Recall too low: {metrics['recall']:.2f} for '{user_message}'"

    # Validate confidence ranges
    for exp_item in expected:
        trait_id = normalize_trait_id(exp_item["trait_id"])
        matching = [e for e in extracted if normalize_trait_id(e.get("trait_id", "")) == trait_id]

        if matching:
            assert validate_confidence_range(matching[0], exp_item), \
                f"Confidence out of range for {trait_id}: {matching[0].get('confidence_llm')}"


def test_extraction_aggregate_metrics():
    """Test aggregate precision/recall across all golden cases."""
    golden_data = load_golden_data()

    total_precision = 0.0
    total_recall = 0.0
    count = 0

    for test_case in golden_data:
        user_message = test_case["user_message"]
        expected = test_case["expected_extractions"]

        extracted = extract_from_message(user_message, user_id="test_user")
        metrics = compute_precision_recall(extracted, expected)

        total_precision += metrics["precision"]
        total_recall += metrics["recall"]
        count += 1

    avg_precision = total_precision / count if count > 0 else 0.0
    avg_recall = total_recall / count if count > 0 else 0.0

    print(f"\n=== Extraction Quality Metrics ===")
    print(f"Average Precision: {avg_precision:.2%}")
    print(f"Average Recall: {avg_recall:.2%}")
    print(f"Test Cases: {count}")

    assert avg_precision >= 0.95, f"Average precision too low: {avg_precision:.2%}"
    assert avg_recall >= 0.85, f"Average recall too low: {avg_recall:.2%}"


def test_zero_extraction_rate():
    """Test that we don't miss too many factual statements."""
    golden_data = load_golden_data()

    # Only consider test cases where we expect extractions
    factual_cases = [tc for tc in golden_data if tc["expected_extractions"]]

    zero_extractions = 0
    for test_case in factual_cases:
        extracted = extract_from_message(test_case["user_message"], user_id="test_user")
        if not extracted:
            zero_extractions += 1
            print(f"MISS: '{test_case['user_message']}' (ID: {test_case['id']})")

    zero_rate = zero_extractions / len(factual_cases) if factual_cases else 0.0

    print(f"\nZero-Extraction Rate: {zero_rate:.2%} ({zero_extractions}/{len(factual_cases)})")

    assert zero_rate < 0.10, f"Zero-extraction rate too high: {zero_rate:.2%}"
```

**Action Items**:
1. Create this test file
2. Run tests: `pytest tests/test_extraction_quality.py -v`
3. Identify failing cases and iterate on HC prompt/extraction logic
4. Add to CI pipeline

---

## Implementation Plan: Detailed Timeline

### Week 1: Foundation & Baselines

**Monday-Tuesday**: Golden Dataset Creation
- [ ] Create `tests/golden/extraction_test_cases.json` with 50+ cases
- [ ] Include all 10 categories from above
- [ ] Add 10+ edge cases (conflicts, corrections, units)

**Wednesday-Thursday**: Test Infrastructure
- [ ] Implement `tests/test_extraction_quality.py`
- [ ] Run baseline tests (document current metrics)
- [ ] Add extraction metrics to `core/metrics.py`

**Friday**: Analysis & Planning
- [ ] Analyze failure modes (which test cases fail?)
- [ ] Document baseline: precision, recall, zero-extraction rate
- [ ] Plan HC prompt improvements for Week 2

---

### Week 2: UCNRR Validation & HC v3.0

**Monday-Tuesday**: UCNRR Testing
- [ ] Create `tests/test_ucnrr_consistency.py`
- [ ] Test idempotency, source multipliers, latency
- [ ] Expand UCNRR self-test to 10+ cases

**Wednesday-Thursday**: HC Prompt v3.0
- [ ] Draft HC prompt v3.0 (see next section)
- [ ] Update HC loader to use v3.0
- [ ] Test with 10 sample conversations

**Friday**: Integration & Feedback
- [ ] Deploy HC v3.0 to dev environment
- [ ] Gather team feedback (tone, naturalness)
- [ ] Document areas for iteration

---

## HC Prompt v3.0: Full Specification

Let me now provide the complete HC Prompt v3.0 with conversational intelligence...

