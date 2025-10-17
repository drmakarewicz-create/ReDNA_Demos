#!/usr/bin/env python3
"""
Peek Golden Responses - Diagnostic Utility

Quick sanity check on the first 5 golden cases to validate extraction logic.
Shows what Core returns for each test case and what traits are extracted.

Usage:
    python tests/tools/peek_golden_responses.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

# Add parent directory to path so we can import from tests
sys.path.insert(0, str(Path(__file__).parent.parent))

from test_extraction_quality import (
    CORE_BASE,
    _canon_id,
    _golden_vocab,
    extract_traits_from_response,
    ingest_and_extract,
    load_golden_cases,
)


def peek_responses(num_cases: int = 5) -> None:
    """
    Test first N golden cases and show what Core returns.

    Args:
        num_cases: Number of test cases to peek at (default 5)
    """
    print(f"\n{'='*70}")
    print(f"Peek Golden Responses - First {num_cases} Cases")
    print(f"{'='*70}\n")

    # Load golden dataset
    cases = load_golden_cases()
    print(f"Loaded {len(cases)} golden test cases")
    print(f"Golden vocabulary size: {len(_golden_vocab())} trait IDs\n")

    # Process first N cases
    for i, case in enumerate(cases[:num_cases], 1):
        case_id = case["id"]
        category = case.get("category", "unknown")
        user_message = case["user_message"]
        expected_extractions = case.get("expected_extractions", [])
        expected_traits = {e["trait_id"] for e in expected_extractions}

        print(f"\n{'-'*70}")
        print(f"Case {i}: {case_id} ({category})")
        print(f"{'-'*70}")
        print(f"User message: \"{user_message}\"")
        print(f"Expected traits: {sorted(expected_traits) if expected_traits else 'None'}")

        # Generate unique user_id
        user_id = f"peek_test_{case_id}_{int(time.time() * 1000)}"

        try:
            # Ingest and extract
            print(f"\nSending to Core (user_id={user_id})...")
            response = ingest_and_extract(user_message, user_id=user_id)

            # Show response structure
            print(f"\nCore response keys: {list(response.keys())}")

            # Show snapshot.traits
            snap = response.get("snapshot", {}) or {}
            snap_traits = snap.get("traits") or []
            if snap_traits:
                print(f"\nsnapshot.traits ({len(snap_traits)} traits):")
                for t in snap_traits[:5]:  # Show first 5
                    tid = t.get("trait_id", "?")
                    canon = _canon_id(tid)
                    print(f"  - {tid} -> {canon}")
                if len(snap_traits) > 5:
                    print(f"  ... and {len(snap_traits) - 5} more")
            else:
                print(f"\nsnapshot.traits: None")

            # Show rescore.rr_by_trait
            rr = response.get("rescore", {}) or {}
            rr_by_trait = rr.get("rr_by_trait", {}) or {}
            if rr_by_trait:
                print(f"\nrescore.rr_by_trait ({len(rr_by_trait)} traits):")
                for tid, score in list(rr_by_trait.items())[:5]:  # Show first 5
                    canon = _canon_id(tid)
                    print(f"  - {tid} -> {canon}: {score}")
                if len(rr_by_trait) > 5:
                    print(f"  ... and {len(rr_by_trait) - 5} more")
            else:
                print(f"\nrescore.rr_by_trait: None")

            # Show extracted[]
            extracted = response.get("extracted") or []
            if extracted:
                print(f"\nextracted[] ({len(extracted)} traits):")
                for t in extracted[:5]:  # Show first 5
                    tid = t.get("trait_id", "?")
                    canon = _canon_id(tid)
                    conf = t.get("confidence", 0.0)
                    print(f"  - {tid} -> {canon}: conf={conf}")
                if len(extracted) > 5:
                    print(f"  ... and {len(extracted) - 5} more")
            else:
                print(f"\nextracted[]: None")

            # Extract traits using our robust extractor
            extracted_traits = extract_traits_from_response(response)

            print(f"\n{'='*40}")
            print(f"Extracted traits (after canonicalization & gating):")
            print(f"  {sorted(extracted_traits) if extracted_traits else 'None'}")
            print(f"\nExpected traits:")
            print(f"  {sorted(expected_traits) if expected_traits else 'None'}")

            # Calculate match
            tp = len(expected_traits & extracted_traits)
            fp = len(extracted_traits - expected_traits)
            fn = len(expected_traits - extracted_traits)

            print(f"\nMatch:")
            print(f"  TP (correct): {tp}")
            print(f"  FP (extra): {fp} - {sorted(extracted_traits - expected_traits) if fp else 'None'}")
            print(f"  FN (missing): {fn} - {sorted(expected_traits - extracted_traits) if fn else 'None'}")

            if tp == len(expected_traits) and fp == 0:
                print(f"  ✅ PERFECT MATCH")
            elif tp > 0:
                print(f"  ⚠️  PARTIAL MATCH")
            else:
                print(f"  ❌ NO MATCH")

        except Exception as exc:
            print(f"\n❌ Error: {exc}")
            import traceback
            traceback.print_exc()

    print(f"\n{'='*70}")
    print(f"Peek complete. Check output to validate extraction logic.")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    peek_responses(num_cases=5)
