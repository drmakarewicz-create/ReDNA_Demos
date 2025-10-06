#!/usr/bin/env python3
"""
Batch Rescore Tool
- Re-runs UCN/RR + Core AI for existing Core checkpoint events using current prompts.
- Writes new JSON artifacts alongside your existing structure using Explorer persistence.
- Filters: --user, --since, --until, --limit
- Label runs for easy auditing: --label "prompt-v4-test"
- Dry-run support: --dry-run

Examples:
  REDNA_AI_ENABLED=true python batch_rescore.py --user TEST --label "ucn-v2"
  REDNA_AI_ENABLED=true python batch_rescore.py --since 2025-09-01 --limit 50
"""

from __future__ import annotations
import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CORE_DIR = ROOT / "ReDNACoreDemo" / "data" / "checkpoints"
UCNRR_DIR = ROOT / "UCN_RR_Demo" / "data" / "users"

# Re-use existing helpers
from ExplorerDemo.explorer_ai_bridge import (
    NodeSpec, EvidenceSpec, ai_score_node, ai_core_propagation
)
from ExplorerDemo.explorer_persistence import persist_everything

AI_ON = os.getenv("REDNA_AI_ENABLED", "false").lower() == "true"


def read_json(p: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def list_users() -> List[str]:
    if not CORE_DIR.exists():
        return []
    return sorted([p.name for p in CORE_DIR.iterdir() if p.is_dir()])


def list_events(user_id: str) -> List[Path]:
    ev_dir = CORE_DIR / user_id / "events"
    if not ev_dir.exists():
        return []
    return sorted(ev_dir.glob("*.json"), key=lambda p: p.stem)


def parse_date(s: Optional[str]) -> Optional[int]:
    if not s:
        return None
    # Accept YYYY-MM-DD or integer timestamp
    s = s.strip()
    if s.isdigit():
        return int(s)
    return int(datetime.strptime(s, "%Y-%m-%d").timestamp())


def build_neighborhood_from_path(path: str) -> Dict[str, Any]:
    parts = path.split(".") if path else []
    parents = [".".join(parts[:i]) for i in range(1, len(parts))]
    # We don’t know siblings unless you have a graph index; keep empty (safe), 
    # and include demo cross_links to keep parity with Explorer demos.
    return {
        "parents": parents,
        "siblings": [],
        "cross_links": ["PaDNA.ContactsLensDNA", "EmDNA.MoodDNA"]
    }


def rescore_event(user: str, event_path: Path, label: str, dry_run: bool = False) -> Dict[str, Any]:
    data = read_json(event_path) or {}
    change_event = data.get("change_event", {})
    prev_ucnrr = data.get("ucnrr_result", {})

    ce_path = str(change_event.get("path", "PaDNA"))
    neighborhood = build_neighborhood_from_path(ce_path)

    # Prior defaults to previously stored UCN/RR if present
    node = NodeSpec(
        path=ce_path,
        prior_ucn=float(prev_ucnrr.get("ucn", 400.0)),
        prior_rr=float(prev_ucnrr.get("rr", 0.5)),
        preset="Normal"
    )
    # We don’t have historic raw evidence—use conservative neutral defaults
    evidence = EvidenceSpec(confirmations=1, neutrals=1, contradictions=0, half_life_days=90)

    # Re-run AI helpers
    score = ai_score_node(node, evidence)
    plan = ai_core_propagation(change_event, neighborhood)

    # Annotate with run label for traceability
    change_event_labeled = dict(change_event)
    change_event_labeled["rescore_label"] = label
    score_labeled = dict(score)
    score_labeled["rescore_label"] = label
    plan_labeled = dict(plan)
    # don't mutate schema, just add label inside a recognized place:
    if "checks" in plan_labeled and isinstance(plan_labeled["checks"], list):
        plan_labeled["checks"].append({"prompt": f"[meta] rescore: {label}"})

    written = {"core": None, "ucnrr": None}
    if not dry_run:
        written = persist_everything(user, change_event_labeled, score_labeled, plan_labeled)

    return {
        "event": event_path.as_posix(),
        "user": user,
        "label": label,
        "dry_run": dry_run,
        "written": written,
        "ucn": score.get("ucn"),
        "rr": score.get("rr"),
    }


def main():
    ap = argparse.ArgumentParser(description="Batch rescore Core events with current prompts.")
    ap.add_argument("--user", help="Only process this user ID")
    ap.add_argument("--since", help="Only events with ts >= date (YYYY-MM-DD) or unix ts")
    ap.add_argument("--until", help="Only events with ts <= date (YYYY-MM-DD) or unix ts")
    ap.add_argument("--limit", type=int, default=0, help="Max number of events to process")
    ap.add_argument("--label", default=time.strftime("run-%Y%m%d-%H%M%S"), help="Run label for traceability")
    ap.add_argument("--dry-run", action="store_true", help="Do not write outputs; just print what would happen")
    args = ap.parse_args()

    if not AI_ON:
        print("WARNING: REDNA_AI_ENABLED is not true. You will likely get baseline outputs.", file=sys.stderr)

    since_ts = parse_date(args.since)
    until_ts = parse_date(args.until)

    users = [args.user] if args.user else list_users()
    total = 0
    processed = 0

    for user in users:
        events = list_events(user)
        for ev in events:
            data = read_json(ev) or {}
            ce = data.get("change_event", {})
            ts = ce.get("ts", None)
            if isinstance(ts, str) and ts.isdigit():
                ts = int(ts)

            # Date filters
            if since_ts is not None and ts is not None and ts < since_ts:
                continue
            if until_ts is not None and ts is not None and ts > until_ts:
                continue

            total += 1
            out = rescore_event(user, ev, label=args.label, dry_run=args.dry_run)
            processed += 1
            print(json.dumps(out, ensure_ascii=False))

            if args.limit and processed >= args.limit:
                break
        if args.limit and processed >= args.limit:
            break

    print(f"\nDONE. Considered {total} events, processed {processed}. Label={args.label}")


if __name__ == "__main__":
    main()