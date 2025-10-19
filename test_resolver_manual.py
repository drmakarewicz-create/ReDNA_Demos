#!/usr/bin/env python3
"""
Manual test of the resolver with "blue eyes" input.

This directly calls the unified pipeline to test resolver integration.
"""
import json
import sys
from pathlib import Path

# Add to path
sys.path.insert(0, str(Path(__file__).parent))

from ReDNACoreDemo.core.ingest.pipeline import ingest_evidence_roundtrip

def main():
    # Test user
    user_id = "MANUAL_BLUE_EYES"

    # Evidence: "I have blue eyes"
    evidence = [
        {
            "trait_id": "attributes.physical.eye_color",  # Legacy ID (will be canonicalized)
            "fact_value": "blue",
            "source": "test",
            "ts": "2025-10-13T00:00:00Z"
        }
    ]

    print(f"Testing resolver with user_id={user_id}")
    print(f"Evidence: {json.dumps(evidence, indent=2)}")
    print("\n" + "="*60 + "\n")

    # Run pipeline
    result = ingest_evidence_roundtrip(
        user_id=user_id,
        source="test",
        evidence=evidence
    )

    print(f"Pipeline result:")
    print(f"  OK: {result['ok']}")
    print(f"  Ingested: {result['ingested']}")
    print(f"  Inferred: {result['inferred']}")
    print(f"  Request ID: {result['req_id']}")

    # Check resolved.json
    from ReDNACoreDemo.core.storage import read_user_state
    resolved, _, _ = read_user_state(user_id)

    print(f"\n" + "="*60)
    print(f"Resolved traits ({len(resolved)} total):\n")

    for trait_id, trait in resolved.items():
        print(f"  {trait_id}:")
        print(f"    Value: {trait.get('value')}")
        print(f"    UCN: {trait.get('ucn', 0)}")
        print(f"    Status: {trait.get('status')}")
        print(f"    Sources: {trait.get('sources')}")
        print()

    # Check trace
    from ReDNACoreDemo.core.resolver.resolved_io import get_resolver_trace_dir
    trace_dir = get_resolver_trace_dir(user_id)
    traces = sorted(trace_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)

    if traces:
        latest_trace = traces[0]
        print(f"Latest resolver trace: {latest_trace}")
        trace_data = json.loads(latest_trace.read_text())
        print(f"  Steps: {len(trace_data.get('steps', []))}")
        for step in trace_data.get('steps', []):
            print(f"    - {step['name']}")

    # Validation
    print(f"\n" + "="*60)
    print("Validation:")

    eye_color_trait = resolved.get("PaDNA.EyeDNA.IrisColor")
    if not eye_color_trait:
        print("  ✗ FAIL: PaDNA.EyeDNA.IrisColor not found in resolved")
        sys.exit(1)

    ucn = eye_color_trait.get("ucn", 0)
    if ucn <= 0:
        print(f"  ✗ FAIL: UCN is {ucn} (should be > 0)")
        sys.exit(1)

    value = eye_color_trait.get("value", {})
    if value.get("enum") != "blue":
        print(f"  ✗ FAIL: Value is {value} (expected {{'enum': 'blue'}})")
        sys.exit(1)

    print(f"  ✓ PASS: Trait exists with UCN={ucn} and value={value}")
    print("\n✓ All checks passed!")
    sys.exit(0)

if __name__ == "__main__":
    main()
