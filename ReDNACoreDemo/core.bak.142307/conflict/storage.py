"""Conflict storage and logging utilities."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .models import Conflict


SYSTEM_INDEX = Path(__file__).resolve().parents[3] / "data" / "system_logs" / "conflicts" / "INDEX.json"
SYSTEM_INDEX.parent.mkdir(parents=True, exist_ok=True)


def _user_log_path(user_id: str) -> Path:
    base = Path(__file__).resolve().parents[3] / "data" / "users" / user_id
    base.mkdir(parents=True, exist_ok=True)
    return base / "conflict_log.jsonl"


def append_conflict_record(conflict: Conflict) -> None:
    log_path = _user_log_path(conflict.user_id)
    record = conflict.model_dump(mode="json")
    record["ts"] = datetime.utcnow().isoformat() + "Z"
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")

    index_payload = _load_index()
    index_payload.setdefault("conflicts", {})[conflict.conflict_id] = {
        "user_id": conflict.user_id,
        "kind": conflict.kind,
        "status": conflict.status,
        "path": conflict.path,
        "created_at": conflict.created_at.isoformat() + "Z",
        "severity": conflict.severity,
        "resolver": conflict.outcome.resolver if conflict.outcome else None,
    }
    SYSTEM_INDEX.write_text(json.dumps(index_payload, indent=2))


def _load_index() -> Dict[str, Dict[str, dict]]:
    if SYSTEM_INDEX.exists():
        try:
            return json.loads(SYSTEM_INDEX.read_text())
        except json.JSONDecodeError:
            pass
    return {"conflicts": {}}


def list_conflicts(*, user_id: Optional[str] = None, status: Optional[str] = None, kind: Optional[str] = None) -> List[Dict[str, str]]:
    index = _load_index()["conflicts"]
    items = []
    for conflict_id, meta in index.items():
        if user_id and meta.get("user_id") != user_id:
            continue
        if status and meta.get("status") != status:
            continue
        if kind and meta.get("kind") != kind:
            continue
        items.append({"conflict_id": conflict_id, **meta})
    items.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return items


def load_conflict_detail(conflict_id: str) -> Optional[dict]:
    index = _load_index()["conflicts"]
    meta = index.get(conflict_id)
    if not meta:
        return None
    log_path = _user_log_path(meta["user_id"])
    if not log_path.exists():
        return None
    with log_path.open("r", encoding="utf-8") as handle:
        for line in reversed(handle.readlines()):
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("conflict_id") == conflict_id:
                return record
    return None


def conflict_log_path(user_id: str) -> Path:
    return _user_log_path(user_id)


def conflict_stats() -> Dict[str, Dict[str, int] | int]:
    index = _load_index()["conflicts"]
    status_counter: Counter[str] = Counter()
    kind_counter: Counter[str] = Counter()
    severity_counter: Counter[str] = Counter()

    for meta in index.values():
        status_counter.update([meta.get("status", "unknown")])
        kind_counter.update([meta.get("kind", "unknown")])
        severity_counter.update([meta.get("severity", "unknown")])

    return {
        "total": len(index),
        "by_status": dict(status_counter),
        "by_kind": dict(kind_counter),
        "by_severity": dict(severity_counter),
    }
