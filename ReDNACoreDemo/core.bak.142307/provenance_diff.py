"""Diff helper for comparing resolved trait checkpoints."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple

from . import storage


def _load_resolved(candidate: str) -> Tuple[Path, Dict[str, Any]]:
    path = Path(candidate).expanduser().resolve()
    if path.is_dir():
        # try resolved.json inside the directory
        resolved_path = path / storage.RESOLVED_FILENAME
        if resolved_path.exists():
            path = resolved_path
        else:
            raise FileNotFoundError(f"Directory {path} does not contain {storage.RESOLVED_FILENAME}")

    if not path.exists():
        raise FileNotFoundError(f"Checkpoint not found: {path}")

    payload = json.loads(path.read_text())
    if isinstance(payload, dict) and "resolved" in payload and isinstance(payload["resolved"], dict):
        resolved_map = payload["resolved"]
    else:
        resolved_map = payload if isinstance(payload, dict) else {}
    return path, resolved_map


def _snapshot(entry: Dict[str, Any] | None) -> Dict[str, Any]:
    if not isinstance(entry, dict):
        return {"resolved_value": None, "ucn": None, "reasons": (), "last_observed": None}
    return {
        "resolved_value": entry.get("resolved_value"),
        "ucn": entry.get("ucn"),
        "reasons": tuple(entry.get("reasons", []) or []),
        "last_observed": entry.get("last_observed"),
    }


def diff_resolved(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Dict[str, Tuple[Any, Any]]]:
    traits = set(a.keys()) | set(b.keys())
    out: Dict[str, Dict[str, Tuple[Any, Any]]] = {}
    for trait in sorted(traits):
        snap_a = _snapshot(a.get(trait))
        snap_b = _snapshot(b.get(trait))
        trait_diff: Dict[str, Tuple[Any, Any]] = {}
        for key in ("resolved_value", "ucn", "reasons", "last_observed"):
            if snap_a[key] != snap_b[key]:
                trait_diff[key] = (snap_a[key], snap_b[key])
        if trait_diff:
            out[trait] = trait_diff
    return out


def _format_trait_diff(trait: str, payload: Dict[str, Tuple[Any, Any]]) -> str:
    lines = [f"{trait}"]
    for field, (lhs, rhs) in payload.items():
        lines.append(f"  {field}: {lhs!r} → {rhs!r}")
    return "\n".join(lines)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Diff two resolved trait checkpoints")
    parser.add_argument("--a", required=True, help="Path to baseline checkpoint or directory")
    parser.add_argument("--b", required=True, help="Path to comparison checkpoint or directory")

    args = parser.parse_args(list(argv) if argv is not None else None)

    path_a, resolved_a = _load_resolved(args.a)
    path_b, resolved_b = _load_resolved(args.b)

    diffs = diff_resolved(resolved_a, resolved_b)

    print(f"Comparing {path_a} → {path_b}")
    if not diffs:
        print("No differences detected.")
        return 0

    print(f"Found {len(diffs)} differing trait(s):")
    for trait, payload in diffs.items():
        print(_format_trait_diff(trait, payload))

    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
