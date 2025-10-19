"""Replay stored observation events to reconstruct resolved state snapshots.

The storage layer persists per-user observation "events" under
``data/checkpoints/<user>/events`` via :func:`storage.event_checkpoint`.  Each
event is expected to include either a ``new_observations`` list or an
``observations`` payload that can be fed into
``redna_core.resolve_traits``.  This module provides a small CLI utility that
replays those events up to a requested timestamp and prints a summary of the
resulting resolved traits.

Examples::

    python -m ReDNACoreDemo.core.provenance_replay --user demo_user \
        --until 2025-09-14T18:00:00Z

"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from . import redna_core, storage

ISO_FORMATS = ["%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ"]


def _parse_iso(ts: str | None) -> _dt.datetime | None:
    if not ts:
        return None
    for fmt in ISO_FORMATS:
        try:
            return _dt.datetime.strptime(ts, fmt).replace(tzinfo=_dt.timezone.utc)
        except ValueError:
            continue
    try:
        return _dt.datetime.fromisoformat(ts)
    except ValueError:
        return None


def _event_timestamp(payload: Dict[str, Any], fallback: Path) -> _dt.datetime | None:
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    for key in ("ts", "timestamp", "when", "created_at"):
        parsed = _parse_iso(meta.get(key))
        if parsed:
            return parsed
    if "ts" in payload:
        parsed = _parse_iso(payload.get("ts"))
        if parsed:
            return parsed
    # try filename e.g. event-2025-09-14T18-22-11Z.json
    stem = fallback.stem
    for token in stem.split("-"):
        parsed = _parse_iso(token)
        if parsed:
            return parsed
    return None


def _extract_observations(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    candidates: Iterable[Any] = []
    if isinstance(payload.get("new_observations"), list):
        candidates = payload["new_observations"]
    elif isinstance(payload.get("observations"), list):
        candidates = payload["observations"]
    elif isinstance(payload.get("observations"), dict):
        maybe_items = payload["observations"].get("items")
        if isinstance(maybe_items, list):
            candidates = maybe_items
    else:
        data = payload.get("data")
        if isinstance(data, dict):
            maybe_items = data.get("observations") or data.get("new_observations")
            if isinstance(maybe_items, list):
                candidates = maybe_items

    return [item for item in candidates if isinstance(item, dict)]


def replay_user_events(
    user_id: str,
    *,
    until: _dt.datetime | None = None,
    include_state: bool = True,
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], List[Path]]:
    """Replay stored events for ``user_id`` up to ``until``.

    Returns a tuple ``(resolved, evidence, observations, applied_paths)``.
    """

    dirs = storage.ensure_dirs_for_user(user_id)
    events_dir = dirs["events"]
    event_paths = sorted(events_dir.glob("*.json"))

    if include_state:
        resolved, evidence, observations = storage.read_user_state(user_id)
    else:
        resolved, evidence, observations = {}, {"items": []}, {"items": [], "by_trait": {}}

    applied: List[Path] = []

    for path in event_paths:
        payload = storage.load_json(path, default={})
        ts = _event_timestamp(payload, path)
        if until and ts and ts > until:
            break

        new_observations = _extract_observations(payload)
        if not new_observations:
            continue

        resolved_tuple = redna_core.resolve_traits(
            resolved,
            evidence,
            observations,
            new_observations,
        )
        resolved, evidence, observations = resolved_tuple
        applied.append(path)

    return resolved, evidence, observations, applied


def _format_summary(resolved: Dict[str, Any], traits: Iterable[str]) -> str:
    rows = []
    for trait in traits:
        payload = resolved.get(trait) or {}
        value = payload.get("resolved_value")
        ucn = payload.get("ucn")
        rows.append(f"{trait}: value={value!r} ucn={ucn}")
    return "\n".join(rows)


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Replay stored observation checkpoints")
    parser.add_argument("--user", required=True, help="User identifier to replay")
    parser.add_argument(
        "--until",
        help="Optional ISO8601 timestamp; stop replay once events beyond this point are reached.",
    )
    parser.add_argument(
        "--traits",
        nargs="*",
        help="Optional trait keys to print in summary (default: show traits touched during replay)",
    )
    parser.add_argument(
        "--no-baseline",
        action="store_true",
        help="Start from an empty baseline instead of existing storage state.",
    )

    args = parser.parse_args(argv)
    until_dt = _parse_iso(args.until) if args.until else None

    resolved, evidence, observations, applied = replay_user_events(
        args.user,
        until=until_dt,
        include_state=not args.no_baseline,
    )

    if not applied:
        print("No events applied; state unchanged.")
        return 0

    print(f"Applied {len(applied)} event(s):")
    for path in applied:
        print(f"  - {path}")

    traits_to_print: Iterable[str]
    if args.traits:
        traits_to_print = args.traits
    else:
        traits_to_print = [trait for trait in resolved.keys() if trait in redna_core.hierarchy.all_trait_keys()]

    summary = _format_summary(resolved, traits_to_print)
    if summary:
        print("\nResolved summary:\n" + summary)

    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
