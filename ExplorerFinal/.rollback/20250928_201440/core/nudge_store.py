"""Shared helpers for nudge inbox persistence and auditing."""

from __future__ import annotations

import csv
import json
import os
import shutil
import time
import uuid
import hashlib
from collections import deque
from datetime import datetime, timezone, timedelta, time as dt_time
from io import StringIO
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

# Paths -----------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
MAILBOX_ROOT = REPO_ROOT / "data" / "dev_mailbox"
LOGS_ROOT = REPO_ROOT / "data" / "dev_logs"
FEEDBACK_LOG_NAME = "feedback.jsonl"

_SCHEMA_VERSION = 1
_DUPLICATE_WINDOW_SECONDS = 2.0
_RATE_WINDOW_SECONDS = 60.0
_OPS_SCHEMA_VERSION = 1

# In-memory caches used when WRITE_PROTECT=true ---------------------------------

_INBOX_CACHE: Dict[str, List[Dict[str, Any]]] = {}
_ARCHIVE_CACHE: Dict[str, List[Dict[str, Any]]] = {}
_RATE_CACHE: Dict[str, List[float]] = {}
_DRAFT_CHAT_CACHE: Dict[str, List[Dict[str, Any]]] = {}
_LAST_ACTION_CACHE: Dict[Tuple[str, str, str], float] = {}
_OPS_CACHE: Dict[str, Dict[str, Any]] = {}
_FEEDBACK_SESSION_CACHE: List[Dict[str, Any]] = []
_FEEDBACK_CACHE: List[Dict[str, Any]] = []
_FEEDBACK_CACHE_MTIME: Optional[float] = None
_FEEDBACK_AGGREGATE_CACHE: Dict[str, Tuple[Optional[float], Dict[str, Dict[str, Any]]]] = {}
_JSONL_CACHE: Dict[str, Tuple[float, List[Dict[str, Any]]]] = {}

_DEFAULT_TTL_MIN = int(float(os.getenv("NUDGE_TTL_MIN", "1440") or 1440))
_DEFAULT_SNOOZE_MIN = int(float(os.getenv("NUDGE_SNOOZE_MIN", "120") or 120))

# Utilities ---------------------------------------------------------------------


def _ensure_mailbox(user_id: str) -> Path:
    mailbox_dir = MAILBOX_ROOT / user_id
    mailbox_dir.mkdir(parents=True, exist_ok=True)
    return mailbox_dir


def _ensure_logs_dir() -> None:
    LOGS_ROOT.mkdir(parents=True, exist_ok=True)


def _inbox_path(user_id: str) -> Path:
    return _ensure_mailbox(user_id) / "inbox.json"


def _archive_path(user_id: str) -> Path:
    return _ensure_mailbox(user_id) / "archive.jsonl"


def _rate_path(user_id: str) -> Path:
    return _ensure_mailbox(user_id) / "rate.json"


def _draft_chat_path(user_id: str) -> Path:
    return _ensure_mailbox(user_id) / "draft_chat.json"


def _log_path() -> Path:
    _ensure_logs_dir()
    return LOGS_ROOT / "nudges.jsonl"


def _actions_log_path() -> Path:
    _ensure_logs_dir()
    return LOGS_ROOT / "nudge_actions.jsonl"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)


def _short_id() -> str:
    return uuid.uuid4().hex[:4]


# Hashing & dedupe -------------------------------------------------------------


def compute_bundle_hash(payload: Dict[str, Any]) -> str:
    persona_id = str(payload.get("persona_id") or "")
    mode = str(payload.get("mode") or "")
    tone_meta = str(payload.get("tone_meta") or "")
    items = payload.get("items") or []
    texts: List[str] = []
    for item in items:
        if isinstance(item, dict):
            texts.append(str(item.get("text") or ""))
    base = "\u0001".join([persona_id, mode, tone_meta, "\u0002".join(texts)])
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


# Generic JSON helpers ---------------------------------------------------------


def _load_json_array(path: Path) -> List[Any]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            return data["items"]
    except Exception:
        pass
    return []


def _write_json_array(path: Path, rows: Sequence[Any]) -> None:
    tmp_path = path.with_suffix(".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        backup_path = path.with_suffix((path.suffix or "") + ".bak")
        try:
            shutil.copy2(path, backup_path)
        except Exception:
            try:
                backup_path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
            except Exception:
                pass
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(list(rows), handle, indent=2)
    os.replace(tmp_path, path)


def _append_jsonl(path: Path, record: Dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")
    _JSONL_CACHE.pop(_resolve_jsonl_cache_key(path), None)


def _resolve_jsonl_cache_key(path: Path) -> str:
    try:
        return str(path.resolve())
    except Exception:
        return str(path)


def _load_jsonl_records(path: Path) -> List[Dict[str, Any]]:
    key = _resolve_jsonl_cache_key(path)
    try:
        mtime = path.stat().st_mtime
    except FileNotFoundError:
        _JSONL_CACHE.pop(key, None)
        return []
    cached = _JSONL_CACHE.get(key)
    if cached and cached[0] == mtime:
        return [dict(row) for row in cached[1]]

    records: List[Dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    value = json.loads(line)
                    if isinstance(value, dict):
                        records.append(value)
                    else:
                        records.append({"value": value})
                except Exception:
                    records.append({"raw": line})
    except FileNotFoundError:
        records = []
    _JSONL_CACHE[key] = (mtime, records)
    return [dict(row) for row in records]


def _load_jsonl_tail(path: Path, *, limit: Optional[int] = None, newest_first: bool = False) -> List[Dict[str, Any]]:
    records = _load_jsonl_records(path)
    if limit is not None and limit >= 0:
        records = records[-limit:]
    if newest_first:
        records = list(reversed(records))
    return records


def _feedback_log_path() -> Path:
    _ensure_logs_dir()
    return LOGS_ROOT / FEEDBACK_LOG_NAME


def _feedback_cache(write_protect: bool) -> List[Dict[str, Any]]:
    if write_protect:
        return [dict(entry) for entry in _FEEDBACK_SESSION_CACHE]

    path = _feedback_log_path()
    global _FEEDBACK_CACHE, _FEEDBACK_CACHE_MTIME
    try:
        mtime = path.stat().st_mtime
    except FileNotFoundError:
        _FEEDBACK_CACHE = []
        _FEEDBACK_CACHE_MTIME = None
        return []

    if _FEEDBACK_CACHE_MTIME == mtime:
        return [dict(entry) for entry in _FEEDBACK_CACHE]

    entries = _load_jsonl_records(path)
    _FEEDBACK_CACHE = entries
    _FEEDBACK_CACHE_MTIME = mtime
    return [dict(entry) for entry in entries]


def get_feedback_log_path() -> Path:
    """Return the feedback log path (ensures directory exists)."""

    return _feedback_log_path()


def log_feedback(
    *,
    user_id: str,
    nudge_id: str,
    persona_id: str,
    rating: str,
    note: str = "",
    mode: str = "live",
    snapshot_id: Optional[str] = None,
    traits: Optional[Sequence[Mapping[str, Any]]] = None,
    write_protect: bool,
) -> Dict[str, Any]:
    """Append a feedback entry to the log or in-memory cache when write-protected."""

    normalized_rating = rating.strip().lower()
    if normalized_rating not in {"helpful", "not_helpful"}:
        raise ValueError("rating must be 'helpful' or 'not_helpful'")

    record: Dict[str, Any] = {
        "ts": _now_iso(),
        "user_id": user_id,
        "nudge_id": nudge_id,
        "persona_id": persona_id,
        "rating": normalized_rating,
        "note": note.strip(),
        "mode": mode,
    }
    if snapshot_id:
        record["snapshot_id"] = snapshot_id

    normalized_traits: List[Dict[str, str]] = []
    if traits:
        for entry in traits:
            if not isinstance(entry, Mapping):
                continue
            container = str(entry.get("container") or entry.get("container_id") or "").strip()
            trait_id = str(entry.get("trait_id") or entry.get("trait") or "").strip()
            if not container and not trait_id:
                continue
            path = "".join([container, f".{trait_id}" if trait_id else ""]).strip(".")
            normalized_traits.append(
                {
                    "container": container,
                    "trait_id": trait_id,
                    "path": path,
                }
            )
    if normalized_traits:
        record["traits"] = normalized_traits

    if write_protect:
        _FEEDBACK_SESSION_CACHE.append(record)
        return {"ok": True, "dry_run": True, "record": record}

    path = _feedback_log_path()
    _append_jsonl(path, record)
    global _FEEDBACK_CACHE_MTIME
    _FEEDBACK_CACHE_MTIME = None
    return {"ok": True, "path": str(path), "record": record}


def load_feedback_entries(
    *,
    limit: Optional[int] = None,
    user_id: Optional[str] = None,
    persona_id: Optional[str] = None,
    mode: Optional[str] = None,
    newest_first: bool = True,
    write_protect: bool,
) -> List[Dict[str, Any]]:
    """Return feedback entries filtered by optional facets."""

    entries = _feedback_cache(write_protect)
    if not write_protect and _FEEDBACK_SESSION_CACHE:
        entries = entries + [dict(entry) for entry in _FEEDBACK_SESSION_CACHE]

    def _matches(entry: Mapping[str, Any]) -> bool:
        if user_id and str(entry.get("user_id")) != user_id:
            return False
        if persona_id and str(entry.get("persona_id")) != persona_id:
            return False
        if mode and str(entry.get("mode")) != mode:
            return False
        return True

    filtered = [dict(entry) for entry in entries if _matches(entry)]

    def _sort_key(entry: Mapping[str, Any]) -> Tuple:
        ts = entry.get("ts")
        if isinstance(ts, str):
            return (ts, entry.get("nudge_id"))
        return ("", entry.get("nudge_id"))

    filtered.sort(key=_sort_key, reverse=newest_first)

    if limit is not None and limit >= 0:
        filtered = filtered[:limit]
    return filtered


def _normalize_trait_path(entry: Mapping[str, Any]) -> Optional[Tuple[str, str, str]]:
    if not isinstance(entry, Mapping):
        return None
    container = str(entry.get("container") or entry.get("container_id") or "").strip()
    trait_id = str(entry.get("trait_id") or entry.get("trait") or "").strip()
    path = str(entry.get("path") or "").strip()
    if not path:
        if container and trait_id:
            path = f"{container}.{trait_id}"
        elif trait_id:
            path = trait_id
        elif container:
            path = container
    if not path:
        return None
    if not container and "." in path:
        container, trait_id = path.split(".", 1)
    return path, container, trait_id


def _compute_feedback_aggregates(entries: Sequence[Mapping[str, Any]]) -> Dict[str, Dict[str, Any]]:
    aggregates: Dict[str, Dict[str, Any]] = {}
    for entry in entries:
        traits = entry.get("traits")
        if not isinstance(traits, Sequence):
            continue
        ts = str(entry.get("ts") or "").strip()
        rating = str(entry.get("rating") or "").strip().lower()
        for trait in traits:
            normalized = _normalize_trait_path(trait)
            if not normalized:
                continue
            path, container_id, trait_id = normalized
            payload = aggregates.setdefault(
                path,
                {
                    "container": container_id,
                    "trait_id": trait_id,
                    "helpful": 0,
                    "not_helpful": 0,
                    "last_ts": None,
                },
            )
            if rating == "helpful":
                payload["helpful"] += 1
            elif rating == "not_helpful":
                payload["not_helpful"] += 1
            # track last timestamp (most recent)
            if ts:
                prev = payload.get("last_ts")
                if not prev or ts > prev:
                    payload["last_ts"] = ts

    for payload in aggregates.values():
        helpful = int(payload.get("helpful", 0) or 0)
        not_helpful = int(payload.get("not_helpful", 0) or 0)
        total = max(1, helpful + not_helpful)
        payload["score"] = (helpful - not_helpful) / float(total)

    return aggregates


def load_feedback_aggregates(
    *,
    user_id: Optional[str] = None,
    write_protect: bool,
) -> Dict[str, Dict[str, Any]]:
    """Aggregate feedback statistics per trait for the specified user."""

    entries = load_feedback_entries(
        limit=None,
        user_id=user_id,
        persona_id=None,
        mode=None,
        newest_first=False,
        write_protect=write_protect,
    )

    # Append in-memory session entries when present (dry-run mode)
    if _FEEDBACK_SESSION_CACHE:
        entries = list(entries) + [dict(row) for row in _FEEDBACK_SESSION_CACHE]

    if write_protect:
        return _compute_feedback_aggregates(entries)

    cache_key = user_id or "__ALL__"
    path = _feedback_log_path()
    try:
        mtime = path.stat().st_mtime
    except FileNotFoundError:
        mtime = None

    cached = _FEEDBACK_AGGREGATE_CACHE.get(cache_key)
    if cached and cached[0] == mtime and not _FEEDBACK_SESSION_CACHE:
        return {key: dict(value) for key, value in cached[1].items()}

    aggregates = _compute_feedback_aggregates(entries)
    _FEEDBACK_AGGREGATE_CACHE[cache_key] = (mtime, aggregates)
    return {key: dict(value) for key, value in aggregates.items()}
def load_nudge_actions_log(*, limit: Optional[int] = None, newest_first: bool = False) -> List[Dict[str, Any]]:
    """Load nudge_actions.jsonl entries with optional limit."""

    return _load_jsonl_tail(_actions_log_path(), limit=limit, newest_first=newest_first)


def load_enqueue_log(*, limit: Optional[int] = None, newest_first: bool = False) -> List[Dict[str, Any]]:
    """Load nudges.jsonl records (enqueue history)."""

    return _load_jsonl_tail(_log_path(), limit=limit, newest_first=newest_first)


def list_ops_configs(*, write_protect: bool) -> Dict[str, Dict[str, Any]]:
    """Return per-user ops scheduler configs."""

    results: Dict[str, Dict[str, Any]] = {}
    if not MAILBOX_ROOT.exists():
        return results
    for entry in MAILBOX_ROOT.iterdir():
        if not entry.is_dir():
            continue
        user_id = entry.name
        config = _load_ops(user_id, write_protect=write_protect)
        if config:
            results[user_id] = config
    return results


def list_mailbox_users() -> List[str]:
    """List user ids that currently have mailboxes on disk."""

    if not MAILBOX_ROOT.exists():
        return []
    return sorted(entry.name for entry in MAILBOX_ROOT.iterdir() if entry.is_dir())

def _ops_path(user_id: str) -> Path:
    return _ensure_mailbox(user_id) / "ops.json"


# Loading / saving inbox -------------------------------------------------------


def _load_inbox(user_id: str, *, write_protect: bool) -> List[Dict[str, Any]]:
    if write_protect:
        return [dict(item) for item in _INBOX_CACHE.get(user_id, [])]
    inbox = _load_json_array(_inbox_path(user_id))
    _INBOX_CACHE[user_id] = [dict(item) for item in inbox]
    return [dict(item) for item in inbox]


def _save_inbox(user_id: str, entries: Sequence[Dict[str, Any]], *, write_protect: bool) -> None:
    snapshot = [dict(entry) for entry in entries]
    if write_protect:
        _INBOX_CACHE[user_id] = snapshot
        return
    _write_json_array(_inbox_path(user_id), snapshot)
    _INBOX_CACHE[user_id] = snapshot


def _load_archive(user_id: str, *, write_protect: bool) -> List[Dict[str, Any]]:
    if write_protect:
        return list(_ARCHIVE_CACHE.get(user_id, []))
    path = _archive_path(user_id)
    if not path.exists():
        _ARCHIVE_CACHE[user_id] = []
        return []
    try:
        with path.open("r", encoding="utf-8") as handle:
            rows = [json.loads(line) for line in handle if line.strip()]
    except Exception:
        rows = []
    _ARCHIVE_CACHE[user_id] = rows
    return list(rows)


def _append_archive(user_id: str, record: Dict[str, Any], *, write_protect: bool) -> None:
    if write_protect:
        history = _ARCHIVE_CACHE.setdefault(user_id, [])
        history.append(record)
        return
    _append_jsonl(_archive_path(user_id), record)
    _ARCHIVE_CACHE.setdefault(user_id, []).append(record)


def _load_ops(user_id: str, *, write_protect: bool) -> Dict[str, Any]:
    if write_protect:
        return dict(_OPS_CACHE.get(user_id, {}))
    path = _ops_path(user_id)
    if not path.exists():
        _OPS_CACHE[user_id] = {}
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            _OPS_CACHE[user_id] = payload
            return dict(payload)
    except Exception:
        pass
    _OPS_CACHE[user_id] = {}
    return {}


def _save_ops(user_id: str, payload: Mapping[str, Any], *, write_protect: bool) -> None:
    data = dict(payload)
    if write_protect:
        _OPS_CACHE[user_id] = data
        return
    path = _ops_path(user_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
    os.replace(tmp, path)
    _OPS_CACHE[user_id] = data


# Ops scheduling helpers -------------------------------------------------------


_WEEKDAY_MAP = {
    "mon": 0,
    "monday": 0,
    "tue": 1,
    "tues": 1,
    "tuesday": 1,
    "wed": 2,
    "wednesday": 2,
    "thu": 3,
    "thur": 3,
    "thurs": 3,
    "thursday": 3,
    "fri": 4,
    "friday": 4,
    "sat": 5,
    "saturday": 5,
    "sun": 6,
    "sunday": 6,
}


def _default_ops_config() -> Dict[str, Any]:
    return {"schema_version": _OPS_SCHEMA_VERSION, "entries": []}


def _coerce_iso(value: Any) -> Optional[str]:
    if isinstance(value, str):
        text = value.strip()
        if text:
            return text
    return None


def _coerce_cohort(value: Any) -> Optional[str]:
    if isinstance(value, str):
        token = value.strip().upper()
        if token in {"A", "B"}:
            return token
    return None


def _normalize_weekdays(values: Optional[Iterable[Any]]) -> List[int]:
    if not values:
        return list(range(7))
    resolved: List[int] = []
    for item in values:
        if isinstance(item, (int, float)):
            resolved.append(int(item) % 7)
            continue
        token = str(item or "").strip().lower()
        if not token:
            continue
        if token.isdigit():
            resolved.append(int(token) % 7)
            continue
        mapped = _WEEKDAY_MAP.get(token)
        if mapped is not None:
            resolved.append(mapped)
    if not resolved:
        return list(range(7))
    return sorted({val % 7 for val in resolved})


def _normalize_ops_entry(entry: Mapping[str, Any]) -> Dict[str, Any]:
    persona_id = str(entry.get("persona_id") or "").strip() or "default"
    label = str(entry.get("label") or "").strip() or f"Schedule · {persona_id}"
    hour = int(entry.get("hour", 9) or 9)
    minute = int(entry.get("minute", 0) or 0)
    hour = min(max(hour, 0), 23)
    minute = min(max(minute, 0), 59)

    normalized = {
        "id": str(entry.get("id") or f"ops_{_short_id()}_{_short_id()}"),
        "persona_id": persona_id,
        "label": label,
        "weekdays": _normalize_weekdays(entry.get("weekdays")),
        "hour": hour,
        "minute": minute,
        "last_run_ts": _coerce_iso(entry.get("last_run_ts")),
        "next_run_ts": _coerce_iso(entry.get("next_run_ts")),
        "notes": str(entry.get("notes") or ""),
        "cohort": _coerce_cohort(entry.get("cohort")),
        "created_ts": _coerce_iso(entry.get("created_ts")) or _now_iso(),
    }
    return normalized


def compute_next_run(entry: Mapping[str, Any], *, after: Optional[datetime] = None) -> Optional[str]:
    now = after or datetime.now(timezone.utc)
    try:
        hour = int(entry.get("hour", 9) or 9)
        minute = int(entry.get("minute", 0) or 0)
        target_time = dt_time(hour=hour, minute=minute, tzinfo=timezone.utc)
    except Exception:
        return None

    weekdays_raw = entry.get("weekdays")
    if isinstance(weekdays_raw, Iterable):
        weekdays = [int(day) % 7 for day in weekdays_raw]
    else:
        weekdays = list(range(7))
    if not weekdays:
        weekdays = list(range(7))

    for offset in range(0, 14):
        candidate_date = (now + timedelta(days=offset)).date()
        if candidate_date.weekday() not in weekdays:
            continue
        candidate_dt = datetime.combine(candidate_date, target_time)
        if candidate_dt <= now:
            continue
        return candidate_dt.isoformat()

    fallback_date = (now + timedelta(days=1)).date()
    fallback_dt = datetime.combine(fallback_date, target_time)
    return fallback_dt.isoformat()


def load_ops(user_id: str, *, write_protect: bool) -> Dict[str, Any]:
    raw = _load_ops(user_id, write_protect=write_protect)
    if not raw:
        config = _default_ops_config()
    else:
        config = _default_ops_config()
        config["schema_version"] = int(raw.get("schema_version", _OPS_SCHEMA_VERSION) or _OPS_SCHEMA_VERSION)
        entries: List[Dict[str, Any]] = []
        raw_entries = raw.get("entries") if isinstance(raw, Mapping) else None
        if isinstance(raw_entries, list):
            for item in raw_entries:
                if not isinstance(item, Mapping):
                    continue
                normalized = _normalize_ops_entry(item)
                normalized["next_run_ts"] = normalized.get("next_run_ts") or compute_next_run(normalized)
                entries.append(normalized)
        config["entries"] = entries
    _OPS_CACHE[user_id] = dict(config)
    return dict(config)


def upsert_ops_entry(
    user_id: str,
    entry: Mapping[str, Any],
    *,
    write_protect: bool,
) -> Dict[str, Any]:
    config = load_ops(user_id, write_protect=write_protect)
    normalized = _normalize_ops_entry(entry)
    normalized["next_run_ts"] = compute_next_run(normalized)

    entries: List[Dict[str, Any]] = config.get("entries", [])
    replaced = False
    for idx, existing in enumerate(entries):
        if existing.get("id") == normalized["id"]:
            entries[idx] = normalized
            replaced = True
            break
    if not replaced:
        entries.append(normalized)

    config["entries"] = entries
    config["schema_version"] = _OPS_SCHEMA_VERSION
    _save_ops(user_id, config, write_protect=write_protect)
    return normalized


def delete_ops_entry(user_id: str, entry_id: str, *, write_protect: bool) -> None:
    config = load_ops(user_id, write_protect=write_protect)
    entries = [entry for entry in config.get("entries", []) if entry.get("id") != entry_id]
    config["entries"] = entries
    _save_ops(user_id, config, write_protect=write_protect)


def mark_ops_run(user_id: str, entry_id: str, *, write_protect: bool) -> Optional[Dict[str, Any]]:
    config = load_ops(user_id, write_protect=write_protect)
    updated: Optional[Dict[str, Any]] = None
    now_iso = _now_iso()
    for entry in config.get("entries", []):
        if entry.get("id") == entry_id:
            entry["last_run_ts"] = now_iso
            entry["next_run_ts"] = compute_next_run(entry, after=datetime.now(timezone.utc))
            updated = entry
            break
    if updated is not None:
        _save_ops(user_id, config, write_protect=write_protect)
    return updated


# Rate limiting ----------------------------------------------------------------
# Rate limiting ----------------------------------------------------------------


def _load_rate(user_id: str, *, write_protect: bool) -> List[float]:
    if write_protect:
        return list(_RATE_CACHE.get(user_id, []))
    path = _rate_path(user_id)
    if not path.exists():
        _RATE_CACHE[user_id] = []
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("actions"), list):
            actions = [float(val) for val in data["actions"]]
        elif isinstance(data, list):
            actions = [float(val) for val in data]
        else:
            actions = []
    except Exception:
        actions = []
    _RATE_CACHE[user_id] = actions
    return list(actions)


def _save_rate(user_id: str, timestamps: Sequence[float], *, write_protect: bool) -> None:
    values = list(timestamps)
    if write_protect:
        _RATE_CACHE[user_id] = values
        return
    payload = {"window": int(_RATE_WINDOW_SECONDS), "actions": values}
    tmp_path = _rate_path(user_id).with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    os.replace(tmp_path, _rate_path(user_id))
    _RATE_CACHE[user_id] = values


def _purge_rate(timestamps: List[float]) -> List[float]:
    now = time.time()
    lower = now - _RATE_WINDOW_SECONDS
    return [stamp for stamp in timestamps if stamp >= lower]


def enforce_rate_limit(
    user_id: str,
    action: str,
    limit_per_minute: int,
    *,
    write_protect: bool,
) -> Dict[str, Any]:
    timestamps = _purge_rate(_load_rate(user_id, write_protect=write_protect))
    count = len(timestamps)
    if count >= limit_per_minute:
        oldest = min(timestamps) if timestamps else time.time()
        retry_in = max(1, int(_RATE_WINDOW_SECONDS - (time.time() - oldest)))
        return {"ok": False, "retry_in": retry_in, "remaining": 0}
    return {"ok": True, "remaining": max(0, limit_per_minute - count)}


def _record_rate_action(user_id: str, *, write_protect: bool) -> None:
    timestamps = _purge_rate(_load_rate(user_id, write_protect=write_protect))
    timestamps.append(time.time())
    _save_rate(user_id, timestamps, write_protect=write_protect)


# Draft chat helpers -----------------------------------------------------------


def _load_draft_chat(user_id: str, *, write_protect: bool) -> List[Dict[str, Any]]:
    if write_protect:
        return [dict(entry) for entry in _DRAFT_CHAT_CACHE.get(user_id, [])]
    messages = _load_json_array(_draft_chat_path(user_id))
    _DRAFT_CHAT_CACHE[user_id] = [dict(entry) for entry in messages]
    return [dict(entry) for entry in messages]


def _save_draft_chat(user_id: str, messages: Sequence[Dict[str, Any]], *, write_protect: bool) -> None:
    snapshot = [dict(entry) for entry in messages]
    if write_protect:
        _DRAFT_CHAT_CACHE[user_id] = snapshot
        return
    _write_json_array(_draft_chat_path(user_id), snapshot)
    _DRAFT_CHAT_CACHE[user_id] = snapshot


def _append_chat_entries(
    user_id: str,
    bundle: Dict[str, Any],
    *,
    write_protect: bool,
) -> List[str]:
    messages = _load_draft_chat(user_id, write_protect=write_protect)
    chat_ids: List[str] = []
    for idx, item in enumerate(bundle.get("items", []), start=1):
        entry_id = f"dc_{bundle['id']}_{idx}_{_short_id()}"
        messages.append(
            {
                "id": entry_id,
                "ts": _now_iso(),
                "from": "head_coach",
                "nudge_id": bundle["id"],
                "text": item.get("text"),
            }
        )
        chat_ids.append(entry_id)
    _save_draft_chat(user_id, messages, write_protect=write_protect)
    return chat_ids


def _remove_chat_entries(
    user_id: str,
    chat_entry_ids: Sequence[str],
    *,
    write_protect: bool,
) -> None:
    if not chat_entry_ids:
        return
    ids = set(chat_entry_ids)
    messages = [msg for msg in _load_draft_chat(user_id, write_protect=write_protect) if msg.get("id") not in ids]
    _save_draft_chat(user_id, messages, write_protect=write_protect)


# Logging ----------------------------------------------------------------------


def _log_enqueue(record: Dict[str, Any], *, write_protect: bool) -> None:
    if write_protect:
        return
    try:
        _append_jsonl(_log_path(), record)
    except Exception:
        pass


def _log_action(record: Dict[str, Any], *, write_protect: bool) -> None:
    if write_protect:
        return
    try:
        _append_jsonl(_actions_log_path(), record)
    except Exception:
        pass


# Duplicate guard --------------------------------------------------------------


def _record_duplicate_guard(user_id: str, nudge_id: str, action: str) -> bool:
    key = (user_id, nudge_id, action)
    now = time.time()
    last = _LAST_ACTION_CACHE.get(key)
    if last and (now - last) < _DUPLICATE_WINDOW_SECONDS:
        return False
    _LAST_ACTION_CACHE[key] = now
    return True


# Public API -------------------------------------------------------------------


def add_bundle(
    user_id: str,
    payload: Dict[str, Any],
    *,
    write_protect: bool,
) -> Dict[str, Any]:
    inbox = _load_inbox(user_id, write_protect=write_protect)
    bundle_hash = compute_bundle_hash(payload)
    latest = inbox[0] if inbox else None
    if latest and latest.get("hash") == bundle_hash and latest.get("status") == "inbox":
        record = {
            "ts": _now_iso(),
            "action": "enqueue_skip",
            "user_id": user_id,
            "nudge_id": latest.get("id"),
            "hash": bundle_hash,
        }
        _append_archive(user_id, record, write_protect=write_protect)
        _log_enqueue({**record, "reason": "duplicate"}, write_protect=write_protect)
        return {"duplicate": True, "bundle": latest}

    timestamp = _now_iso()
    bundle_id = f"nudge_{timestamp.replace(':', '-')}_{_short_id()}"
    ttl_minutes = payload.get("ttl_minutes")
    try:
        ttl_minutes = int(ttl_minutes)
    except (TypeError, ValueError):
        ttl_minutes = _DEFAULT_TTL_MIN
    ttl_minutes = max(1, ttl_minutes)
    expires_at = (_now_dt() + timedelta(minutes=ttl_minutes)).isoformat(timespec="seconds")

    cohort = payload.get("cohort")
    if isinstance(cohort, str):
        cohort = cohort.strip().upper() or None
        if cohort not in {"A", "B"}:
            cohort = None
    else:
        cohort = None

    bundle = {
        "id": bundle_id,
        "ts": timestamp,
        "persona_id": payload.get("persona_id"),
        "mode": payload.get("mode"),
        "tone_meta": payload.get("tone_meta"),
        "snapshot_id": payload.get("snapshot_id"),
        "items": payload.get("items", []),
        "provenance": payload.get("provenance", {}),
        "status": "inbox",
        "hash": bundle_hash,
        "last_action_ts": timestamp,
        "schema_version": _SCHEMA_VERSION,
        "expires_at": expires_at,
        "ttl_minutes": ttl_minutes,
        "cohort": cohort,
        "resume_at": None,
        "snoozed_minutes": None,
    }

    inbox.insert(0, bundle)
    _save_inbox(user_id, inbox, write_protect=write_protect)

    archive_record = {
        "ts": timestamp,
        "action": "enqueue",
        "user_id": user_id,
        "nudge_id": bundle_id,
        "hash": bundle_hash,
        "mode": bundle["mode"],
        "persona_id": bundle["persona_id"],
        "count": len(bundle.get("items", [])),
        "snapshot_id": bundle.get("snapshot_id"),
        "cohort": bundle.get("cohort"),
    }
    _append_archive(user_id, archive_record, write_protect=write_protect)
    _log_enqueue(archive_record, write_protect=write_protect)

    return {"duplicate": False, "bundle": bundle}


def list_inbox(
    user_id: str,
    *,
    status_filter: str = "inbox",
    limit: int = 100,
    write_protect: bool = False,
) -> List[Dict[str, Any]]:
    inbox = _load_inbox(user_id, write_protect=write_protect)
    now = _now_dt()
    dirty = False
    for entry in inbox:
        expires_at = entry.get("expires_at")
        expired = False
        if expires_at:
            try:
                expiry_dt = datetime.fromisoformat(expires_at)
            except ValueError:
                expiry_dt = None
            if expiry_dt is not None and expiry_dt <= now:
                expired = True
        entry["expired"] = expired

        if entry.get("status") == "inbox_snoozed":
            resume_at = entry.get("resume_at")
            resume_dt = None
            if resume_at:
                try:
                    resume_dt = datetime.fromisoformat(resume_at)
                except ValueError:
                    resume_dt = None
            if resume_dt is not None and resume_dt <= now:
                entry["status"] = "inbox"
                entry["resume_at"] = None
                entry["last_action_ts"] = _now_iso()
                dirty = True
    if dirty:
        _save_inbox(user_id, inbox, write_protect=write_protect)

    if status_filter == "all":
        rows = inbox
    else:
        tokens = {token.strip() for token in status_filter.split(",")}
        rows = [row for row in inbox if row.get("status") in tokens]
    return rows[:limit]


def _set_status(
    user_id: str,
    nudge_id: str,
    status: str,
    *,
    write_protect: bool,
) -> Optional[Dict[str, Any]]:
    inbox = _load_inbox(user_id, write_protect=write_protect)
    updated: Optional[Dict[str, Any]] = None
    for entry in inbox:
        if entry.get("id") == nudge_id:
            entry["status"] = status
            entry["last_action_ts"] = _now_iso()
            updated = entry
            break
    if updated is None:
        return None
    _save_inbox(user_id, inbox, write_protect=write_protect)
    return updated


def accept(
    user_id: str,
    nudge_id: str,
    *,
    write_protect: bool,
    deliver_to_chat: bool,
) -> Dict[str, Any]:
    if not _record_duplicate_guard(user_id, nudge_id, "accept"):
        return {"ok": False, "duplicate": True}

    bundle = _set_status(user_id, nudge_id, "accepted", write_protect=write_protect)
    if bundle is None:
        return {"ok": False, "error": "not_found"}

    chat_entry_ids: List[str] = []
    if deliver_to_chat:
        chat_entry_ids = _append_chat_entries(user_id, bundle, write_protect=write_protect)
        bundle["chat_entry_ids"] = chat_entry_ids

    inbox = _load_inbox(user_id, write_protect=write_protect)
    for entry in inbox:
        if entry.get("id") == nudge_id:
            entry["resume_at"] = None
            entry["snoozed_minutes"] = None
            break
    _save_inbox(user_id, inbox, write_protect=write_protect)
    bundle["resume_at"] = None
    bundle["snoozed_minutes"] = None

    record = {
        "ts": _now_iso(),
        "action": "accept",
        "user_id": user_id,
        "nudge_id": nudge_id,
        "actor": "main_explorer",
        "chat_entry_ids": chat_entry_ids,
        "cohort": bundle.get("cohort"),
    }
    _append_archive(user_id, record, write_protect=write_protect)
    _log_action(record, write_protect=write_protect)
    _record_rate_action(user_id, write_protect=write_protect)

    return {"ok": True, "bundle": bundle, "chat_entry_ids": chat_entry_ids}


def dismiss(
    user_id: str,
    nudge_id: str,
    *,
    write_protect: bool,
) -> Dict[str, Any]:
    if not _record_duplicate_guard(user_id, nudge_id, "dismiss"):
        return {"ok": False, "duplicate": True}

    bundle = _set_status(user_id, nudge_id, "dismissed", write_protect=write_protect)
    if bundle is None:
        return {"ok": False, "error": "not_found"}

    inbox = _load_inbox(user_id, write_protect=write_protect)
    for entry in inbox:
        if entry.get("id") == nudge_id:
            entry["resume_at"] = None
            entry["snoozed_minutes"] = None
            break
    _save_inbox(user_id, inbox, write_protect=write_protect)
    bundle["resume_at"] = None
    bundle["snoozed_minutes"] = None

    record = {
        "ts": _now_iso(),
        "action": "dismiss",
        "user_id": user_id,
        "nudge_id": nudge_id,
        "actor": "main_explorer",
        "cohort": bundle.get("cohort"),
    }
    _append_archive(user_id, record, write_protect=write_protect)
    _log_action(record, write_protect=write_protect)
    _record_rate_action(user_id, write_protect=write_protect)

    return {"ok": True, "bundle": bundle}


def undo(
    user_id: str,
    nudge_id: str,
    *,
    write_protect: bool,
    deliver_to_chat: bool,
) -> Dict[str, Any]:
    bundle = _set_status(user_id, nudge_id, "inbox", write_protect=write_protect)
    if bundle is None:
        return {"ok": False, "error": "not_found"}

    if deliver_to_chat and bundle.get("chat_entry_ids"):
        _remove_chat_entries(user_id, bundle.get("chat_entry_ids", []), write_protect=write_protect)
        bundle["chat_entry_ids"] = []

    inbox = _load_inbox(user_id, write_protect=write_protect)
    for entry in inbox:
        if entry.get("id") == nudge_id:
            entry["resume_at"] = None
            entry["snoozed_minutes"] = None
            break
    _save_inbox(user_id, inbox, write_protect=write_protect)
    bundle["resume_at"] = None
    bundle["snoozed_minutes"] = None

    record = {
        "ts": _now_iso(),
        "action": "undo",
        "user_id": user_id,
        "nudge_id": nudge_id,
        "actor": "main_explorer",
        "cohort": bundle.get("cohort"),
    }
    _append_archive(user_id, record, write_protect=write_protect)
    _log_action(record, write_protect=write_protect)

    return {"ok": True, "bundle": bundle}


def snooze(
    user_id: str,
    nudge_id: str,
    minutes: Optional[int] = None,
    *,
    write_protect: bool,
) -> Dict[str, Any]:
    if minutes is None:
        minutes = _DEFAULT_SNOOZE_MIN
    try:
        minutes = max(1, int(minutes))
    except (TypeError, ValueError):
        minutes = _DEFAULT_SNOOZE_MIN

    if not _record_duplicate_guard(user_id, nudge_id, "snooze"):
        return {"ok": False, "duplicate": True}

    bundle = _set_status(user_id, nudge_id, "inbox_snoozed", write_protect=write_protect)
    if bundle is None:
        return {"ok": False, "error": "not_found"}

    resume_at = (_now_dt() + timedelta(minutes=minutes)).isoformat(timespec="seconds")
    inbox = _load_inbox(user_id, write_protect=write_protect)
    for entry in inbox:
        if entry.get("id") == nudge_id:
            entry["resume_at"] = resume_at
            entry["snoozed_minutes"] = minutes
            break
    _save_inbox(user_id, inbox, write_protect=write_protect)
    bundle["resume_at"] = resume_at
    bundle["snoozed_minutes"] = minutes

    record = {
        "ts": _now_iso(),
        "action": "snooze",
        "user_id": user_id,
        "nudge_id": nudge_id,
        "minutes": minutes,
        "resume_at": resume_at,
        "cohort": bundle.get("cohort"),
    }
    _append_archive(user_id, record, write_protect=write_protect)
    _log_action(record, write_protect=write_protect)
    return {"ok": True, "bundle": bundle}


def resume(
    user_id: str,
    nudge_id: str,
    *,
    write_protect: bool,
) -> Dict[str, Any]:
    if not _record_duplicate_guard(user_id, nudge_id, "resume"):
        return {"ok": False, "duplicate": True}

    bundle = _set_status(user_id, nudge_id, "inbox", write_protect=write_protect)
    if bundle is None:
        return {"ok": False, "error": "not_found"}

    inbox = _load_inbox(user_id, write_protect=write_protect)
    for entry in inbox:
        if entry.get("id") == nudge_id:
            entry["resume_at"] = None
            entry["snoozed_minutes"] = None
            break
    _save_inbox(user_id, inbox, write_protect=write_protect)
    bundle["resume_at"] = None
    bundle["snoozed_minutes"] = None

    record = {
        "ts": _now_iso(),
        "action": "resume",
        "user_id": user_id,
        "nudge_id": nudge_id,
        "cohort": bundle.get("cohort"),
    }
    _append_archive(user_id, record, write_protect=write_protect)
    _log_action(record, write_protect=write_protect)
    return {"ok": True, "bundle": bundle}


def dismiss_expired(
    user_id: str,
    *,
    write_protect: bool,
) -> Dict[str, Any]:
    inbox = _load_inbox(user_id, write_protect=write_protect)
    now = _now_dt()
    dismissed_ids: List[str] = []

    for entry in inbox:
        if entry.get("status") != "inbox":
            continue
        expires_at = entry.get("expires_at")
        if not expires_at:
            continue
        try:
            expiry_dt = datetime.fromisoformat(expires_at)
        except ValueError:
            continue
        if expiry_dt > now:
            continue
        entry["status"] = "dismissed"
        entry["last_action_ts"] = _now_iso()
        entry["resume_at"] = None
        entry["snoozed_minutes"] = None
        dismissed_ids.append(str(entry.get("id")))

    if not dismissed_ids:
        return {"ok": True, "dismissed": []}

    _save_inbox(user_id, inbox, write_protect=write_protect)
    for entry in inbox:
        if entry.get("id") not in dismissed_ids:
            continue
        record = {
            "ts": _now_iso(),
            "action": "dismiss_expired",
            "user_id": user_id,
            "nudge_id": entry.get("id"),
            "cohort": entry.get("cohort"),
            "expires_at": entry.get("expires_at"),
        }
        _append_archive(user_id, record, write_protect=write_protect)
        _log_action(record, write_protect=write_protect)

    return {"ok": True, "dismissed": dismissed_ids}


def export_visible(user_id: str, bundles: Sequence[Dict[str, Any]]) -> Tuple[bytes, bytes]:
    json_bytes = json.dumps(list(bundles), indent=2).encode("utf-8")

    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "nudge_id",
        "timestamp",
        "persona_id",
        "mode",
        "status",
        "trait_path",
        "text",
        "template_source",
        "snapshot_id",
        "cohort",
        "expires_at",
        "resume_at",
        "expired",
    ])
    for bundle in bundles:
        entries = bundle.get("items") or [{}]
        for item in entries:
            container = item.get("container") or ""
            trait_id = item.get("trait_id") or ""
            trait_path = f"{container}.{trait_id}" if container and trait_id else trait_id or container
            writer.writerow([
                bundle.get("id"),
                bundle.get("ts"),
                bundle.get("persona_id"),
                bundle.get("mode"),
                bundle.get("status"),
                trait_path,
                item.get("text"),
                item.get("template_source"),
                bundle.get("snapshot_id"),
                bundle.get("cohort"),
                bundle.get("expires_at"),
                bundle.get("resume_at"),
                bundle.get("expired"),
            ])
    csv_bytes = buffer.getvalue().encode("utf-8")
    return csv_bytes, json_bytes


def get_enqueue_log_path() -> Path:
    return _log_path()


def get_action_log_path() -> Path:
    return _actions_log_path()


def get_draft_chat(user_id: str, *, write_protect: bool) -> List[Dict[str, Any]]:
    return _load_draft_chat(user_id, write_protect=write_protect)


__all__ = [
    "add_bundle",
    "list_inbox",
    "accept",
    "dismiss",
    "undo",
    "snooze",
    "resume",
    "dismiss_expired",
    "export_visible",
    "enforce_rate_limit",
    "compute_bundle_hash",
    "get_enqueue_log_path",
    "get_action_log_path",
    "get_draft_chat",
    "load_ops",
    "list_ops_configs",
    "list_mailbox_users",
    "upsert_ops_entry",
    "delete_ops_entry",
    "mark_ops_run",
    "compute_next_run",
    "get_feedback_log_path",
    "log_feedback",
    "load_feedback_entries",
    "load_feedback_aggregates",
    "load_nudge_actions_log",
    "load_enqueue_log",
]
