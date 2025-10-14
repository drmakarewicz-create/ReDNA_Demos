#!/usr/bin/env python3
"""
Fixture runner for resolver golden tests.

Supports running single fixtures or batches using glob patterns.

Usage:
    python ReDNACoreDemo/core/resolver/run_fixture.py <fixture.json> [<fixture2.json> ...]
    python ReDNACoreDemo/core/resolver/run_fixture.py tests/golden_*.json

Examples:
    # Single fixture
    python ReDNACoreDemo/core/resolver/run_fixture.py \
        ReDNACoreDemo/core/resolver/tests/golden_blue_eyes.json

    # Multiple fixtures
    python ReDNACoreDemo/core/resolver/run_fixture.py \
        ReDNACoreDemo/core/resolver/tests/golden_*.json

    # All golden tests
    python ReDNACoreDemo/core/resolver/run_fixture.py \
        ReDNACoreDemo/core/resolver/tests/golden_*.json
"""
from __future__ import annotations
import json
import sys
import uuid
import glob
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from ReDNACoreDemo.core.resolver.debug import new_trace, write_trace
from ReDNACoreDemo.core.resolver.impl import resolve_roundtrip
from ReDNACoreDemo.core.resolver.resolved_io import get_resolver_trace_dir


def run_single_fixture(fixture_path: Path) -> bool:
    """
    Run a single fixture test.

    Args:
        fixture_path: Path to fixture JSON file

    Returns:
        True if test passed, False otherwise
    """
    if not fixture_path.exists():
        print(f"ERROR: Fixture not found: {fixture_path}")
        return False

    # Load fixture
    try:
        fixture = json.loads(fixture_path.read_text())
    except Exception as e:
        print(f"ERROR: Failed to load fixture: {e}")
        return False

    user_id = fixture.get("user_id", "TEST_USER")
    evidence = fixture.get("evidence", [])
    expect = fixture.get("expect_resolved", {})

    print(f"\n=== Running fixture: {fixture_path.name} ===")
    print(f"User ID: {user_id}")
    print(f"Evidence items: {len(evidence)}")

    # Create trace
    req_id = f"fixture-{uuid.uuid4().hex[:8]}"
    trace = new_trace(req_id)

    # Run resolver
    try:
        result = resolve_roundtrip(
            user_id,
            evidence,
            source="test",
            trace=trace
        )
        resolved = result["resolved"]
        rr_ok = result["rr_ok"]
    except Exception as e:
        print(f"\n✗ FAILED: Resolver raised exception")
        print(f"  Error: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Write trace
    trace_dir = get_resolver_trace_dir(user_id)
    trace_path = write_trace(trace_dir, trace)
    print(f"Trace written: {trace_path}")

    # Validate expectations
    print(f"\n=== Validation ===")
    print(f"RR scoring: {'OK' if rr_ok else 'FALLBACK (RR offline)'}")

    failures = []
    for tid, spec in expect.items():
        print(f"\nTrait: {tid}")

        # Check trait exists
        if tid not in resolved:
            failures.append(f"  ✗ Trait not found in resolved")
            print(f"  ✗ Trait not found in resolved")
            continue

        trait = resolved[tid]
        expected_val = spec["value"]
        actual_val = trait.get("value")

        # Check value
        if actual_val != expected_val:
            failures.append(f"  ✗ Value mismatch: expected {expected_val}, got {actual_val}")
            print(f"  ✗ Value mismatch")
            print(f"    Expected: {expected_val}")
            print(f"    Got: {actual_val}")
        else:
            print(f"  ✓ Value: {actual_val}")

        # Check UCN minimum
        expected_ucn_min = spec.get("ucn_min", 0.0)
        actual_ucn = trait.get("ucn", 0.0)
        if actual_ucn < expected_ucn_min:
            failures.append(f"  ✗ UCN too low: {actual_ucn} < {expected_ucn_min}")
            print(f"  ✗ UCN too low")
            print(f"    Expected minimum: {expected_ucn_min}")
            print(f"    Got: {actual_ucn}")
        else:
            print(f"  ✓ UCN: {actual_ucn} (>= {expected_ucn_min})")

        # Show status
        print(f"  Status: {trait.get('status', 'unknown')}")
        print(f"  Sources: {trait.get('sources', [])}")

    # Summary
    print(f"\n=== Summary ===")
    if failures:
        print("✗ FAILED")
        for msg in failures:
            print(msg)
        return False
    else:
        print("✓ ALL CHECKS PASSED")
        return True


def main():
    """CLI entry point."""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    # Collect all fixture files
    fixture_paths = []
    for arg in sys.argv[1:]:
        arg_path = Path(arg)

        # Handle glob patterns
        if '*' in arg or '?' in arg:
            matched = glob.glob(arg)
            fixture_paths.extend([Path(p) for p in matched])
        else:
            fixture_paths.append(arg_path)

    if not fixture_paths:
        print("ERROR: No fixture files found")
        sys.exit(1)

    # Run all fixtures
    print(f"\n{'='*60}")
    print(f"Running {len(fixture_paths)} fixture(s)")
    print(f"{'='*60}")

    results = []
    for fixture_path in sorted(fixture_paths):
        passed = run_single_fixture(fixture_path)
        results.append((fixture_path.name, passed))

    # Print summary
    print(f"\n{'='*60}")
    print(f"FINAL SUMMARY")
    print(f"{'='*60}\n")

    passed_count = sum(1 for _, passed in results if passed)
    failed_count = len(results) - passed_count

    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}  {name}")

    print(f"\n{'='*60}")
    print(f"Total: {len(results)} tests")
    print(f"Passed: {passed_count}")
    print(f"Failed: {failed_count}")
    print(f"{'='*60}")

    # Exit with appropriate code
    sys.exit(0 if failed_count == 0 else 1)


if __name__ == "__main__":
    main()
