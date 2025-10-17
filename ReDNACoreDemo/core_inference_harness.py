"""Offline inference regression harness.

Usage::

    python -m ReDNACoreDemo.core_inference_harness --suite smoke

The harness loads golden fixtures from ``ReDNACoreDemo/tests/data/golden`` and
replays them through ``redna_core.resolve_traits``. Any deviation from the
expected resolved traits or priority scores is reported with a human readable
summary so regressions are easy to diagnose without spinning up the full API.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from ReDNACoreDemo.core import redna_core

GOLDEN_ROOT = Path(__file__).resolve().parent / "tests" / "data" / "golden"
DEFAULT_TOLERANCE = 1e-3


@dataclass
class CaseResult:
    name: str
    path: Path
    passed: bool
    details: List[str]


def _load_cases(suite: str, only: Iterable[str] | None = None) -> List[Tuple[Path, Dict[str, Any]]]:
    suite_dir = GOLDEN_ROOT / suite
    if not suite_dir.exists():
        raise FileNotFoundError(f"Golden suite '{suite}' not found under {suite_dir.parent}")

    filters = {c.strip() for c in (only or []) if c.strip()}
    cases: List[Tuple[Path, Dict[str, Any]]] = []
    for candidate in sorted(suite_dir.glob("*.json")):
        with candidate.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        name = str(payload.get("name") or candidate.stem)
        if filters and name not in filters:
            continue
        cases.append((candidate, payload))
    if not cases:
        raise ValueError("No golden cases resolved for the requested filters.")
    return cases


def _format_value(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.4f}"
    return repr(value)


def _compare_scalar(expected: Any, actual: Any, tolerance: float) -> bool:
    if isinstance(expected, float):
        try:
            return abs(float(actual) - expected) <= tolerance
        except (TypeError, ValueError):
            return False
    return actual == expected


def _diff_case(payload: Dict[str, Any], tolerance: float) -> List[str]:
    inputs = payload.get("inputs") or {}
    expected = payload.get("expected") or {}

    result, _, _ = redna_core.resolve_traits(
        inputs.get("prior_resolved") or {},
        inputs.get("prior_evidence") or {"items": []},
        inputs.get("prior_observations") or {"items": [], "by_trait": {}},
        inputs.get("new_observations") or [],
    )

    diffs: List[str] = []
    resolved_expectations: Dict[str, Dict[str, Any]] = expected.get("resolved") or {}
    actual_resolved: Dict[str, Dict[str, Any]] = result.get("resolved", {})

    for trait, expectation in resolved_expectations.items():
        actual_payload = actual_resolved.get(trait)
        if actual_payload is None:
            diffs.append(f"resolved[{trait}]: missing in actual output")
            continue
        for field, expected_value in expectation.items():
            actual_value = actual_payload.get(field)
            if not _compare_scalar(expected_value, actual_value, tolerance):
                diffs.append(
                    f"resolved[{trait}].{field}: expected {_format_value(expected_value)} "
                    f"got {_format_value(actual_value)}"
                )

    priority_expectations: Dict[str, Any] = expected.get("priorities") or {}
    priorities_actual: Dict[str, Any] = result.get("priorities", {})
    for trait, expected_value in priority_expectations.items():
        actual_value = priorities_actual.get(trait)
        if not _compare_scalar(expected_value, actual_value, tolerance):
            diffs.append(
                f"priorities[{trait}]: expected {_format_value(expected_value)} "
                f"got {_format_value(actual_value)}"
            )

    return diffs


def run_suite(suite: str, only: Iterable[str] | None, tolerance: float) -> List[CaseResult]:
    case_payloads = _load_cases(suite, only=only)
    results: List[CaseResult] = []
    for path, payload in case_payloads:
        name = str(payload.get("name") or path.stem)
        diffs = _diff_case(payload, tolerance)
        results.append(CaseResult(name=name, path=path, passed=not diffs, details=diffs))
    return results


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ReDNA Core inference regression harness")
    parser.add_argument(
        "--suite",
        default="smoke",
        help="Golden suite folder to execute (default: smoke)",
    )
    parser.add_argument(
        "--case",
        action="append",
        help="Optional case name filter; may be provided multiple times.",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=DEFAULT_TOLERANCE,
        help="Floating point tolerance for UCN / priority comparisons (default: 1e-3)",
    )

    args = parser.parse_args(argv)

    try:
        results = run_suite(args.suite, only=args.case, tolerance=args.tolerance)
    except Exception as exc:  # pragma: no cover - CLI guard
        print(f"Harness error: {exc}", file=sys.stderr)
        return 2

    failures = [r for r in results if not r.passed]
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        print(f"[{status}] {r.name} ({r.path.relative_to(GOLDEN_ROOT.parent.parent)})")
        if r.details:
            for line in r.details:
                print(f"    • {line}")

    if failures:
        print(f"\n{len(failures)} case(s) failed.")
        return 1

    print(f"\nAll {len(results)} case(s) passed.")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    sys.exit(main())
