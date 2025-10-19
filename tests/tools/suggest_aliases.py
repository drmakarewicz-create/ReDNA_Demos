#!/usr/bin/env python3
"""
Suggest Trait ID Aliases

Analyzes the full golden dataset to identify high-confidence trait IDs from
Core responses that aren't in the golden vocabulary. Suggests additional
TRAIT_ALIASES mappings to improve recall.

Usage:
    python tests/tools/suggest_aliases.py
"""
from __future__ import annotations

import json
import re
import time
from collections import Counter
from pathlib import Path

import requests

# Configuration
GOLDEN_DATASET = Path(__file__).parent.parent / "golden" / "extraction_golden_v1.json"
CORE_BASE = "http://127.0.0.1:8004"
MIN_RR = 500.0
REQUEST_TIMEOUT = 30.0


def canon_guess(tid: str) -> str:
    """
    Apply basic canonicalization (insert *DNA after first segment if missing).
    This is what _canon_id does before checking TRAIT_ALIASES.
    """
    if not tid:
        return ""
    tid = tid.strip()
    # Insert *DNA after the first segment if missing
    tid = re.sub(r"^PaDNA\.([A-Z][a-z]+)\.(.+)$", r"PaDNA.\1DNA.\2", tid)
    return tid


def main():
    # Load golden dataset
    cases = json.loads(GOLDEN_DATASET.read_text())

    # Build golden vocabulary
    golden_vocab = set()
    for c in cases:
        for e in c.get("expected_extractions", []):
            golden_vocab.add(e["trait_id"])

    print(f"\nLoaded {len(cases)} golden test cases")
    print(f"Golden vocabulary: {len(golden_vocab)} canonical trait IDs\n")
    print("Processing all cases to identify unknown high-confidence trait IDs...")
    print(f"(MIN_RR threshold: {MIN_RR})\n")

    # Track unknown trait IDs and examples
    unknown = Counter()
    examples = {}

    # Process each golden case
    for i, c in enumerate(cases, 1):
        case_id = c["id"]
        user_message = c["user_message"]

        # Generate unique user_id
        uid = f"suggest_{case_id}_{int(time.time() * 1000)}"

        try:
            # Ingest via Core API
            r = requests.post(
                f"{CORE_BASE}/core/api/ingest_text",
                json={
                    "user_id": uid,
                    "text": user_message,
                    "source": "alias_suggest"
                },
                timeout=REQUEST_TIMEOUT
            )
            r.raise_for_status()
            resp = r.json()

            # Extract rr_by_trait
            rr = (resp.get("rescore", {}) or {}).get("rr_by_trait", {}) or {}

            for raw_id, score in rr.items():
                try:
                    score = float(score)
                except Exception:
                    score = 0.0

                # Skip low-confidence traits
                if score < MIN_RR:
                    continue

                # Apply basic canonicalization
                guess = canon_guess(raw_id)

                # Already in vocab? Skip
                if guess in golden_vocab:
                    continue

                # Record unknown key and one example where it occurred
                unknown[raw_id] += 1
                if raw_id not in examples:
                    examples[raw_id] = (case_id, user_message)

            # Progress indicator
            if i % 10 == 0:
                print(f"  Processed {i}/{len(cases)} cases...")

        except Exception as exc:
            print(f"  Warning: Case {case_id} failed: {exc}")
            continue

    print(f"\nProcessing complete. Found {len(unknown)} unique unknown trait IDs.\n")

    # Print results
    print("="*100)
    print("Unknown rr_by_trait IDs above MIN_RR (suggest mapping to golden IDs)")
    print("="*100)
    print(f"{'Raw ID':<40} {'Canon Guess':<40} {'Count':>5}  Example")
    print("-"*100)

    for tid, cnt in unknown.most_common(30):
        cid = canon_guess(tid)
        case_id, msg = examples[tid]
        # Truncate message for display
        msg_display = msg if len(msg) <= 50 else msg[:47] + "..."
        print(f"{tid:<40} {cid:<40} {cnt:>5}  {case_id} | {msg_display}")

    print("\n" + "="*100)
    print("Suggested Actions:")
    print("="*100)
    print("1. Review the top unknown IDs and identify correct golden ID mappings")
    print("2. Add 1-3 new entries to TRAIT_ALIASES in tests/test_extraction_quality.py")
    print("3. Re-run baseline test: pytest tests/test_extraction_quality.py::test_golden_dataset_baseline -v -s")
    print("4. If recall is still low, repeat this process or consider lowering MIN_RR slightly")
    print("\nExample alias entries:")
    print("    'PaDNA.UnknownID': 'PaDNA.KnownDNA.CorrectID',")
    print("="*100 + "\n")


if __name__ == "__main__":
    main()
