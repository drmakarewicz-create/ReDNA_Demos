"""
Unified stack logging helpers.

Writes JSONL records to ~/.redna/logs/stack.log for Core, UCNRR, and DevX.
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

_LOG_LOCK = threading.Lock()

_REDNA_ROOT = Path(os.getenv("REDNA_HOME", Path.home() / ".redna")).expanduser()
_LOG_PATH = Path(
    os.getenv("REDNA_STACK_LOG", str((_REDNA_ROOT / "logs" / "stack.log").resolve()))
)
_EVIDENCE_LOG_PATH = Path(
    os.getenv("REDNA_EVIDENCE_LOG", str((_REDNA_ROOT / "logs" / "evidence.log").resolve()))
)
_SUPERSESSION_LOG_PATH = Path(
    os.getenv("REDNA_SUPERSESSION_LOG", str((_REDNA_ROOT / "logs" / "supersession.log").resolve()))
)


def _ensure_log_path() -> None:
    _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _EVIDENCE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _SUPERSESSION_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)


def _default(o: Any) -> Any:
    try:
        return str(o)
    except Exception:
        return "<unserializable>"


def stack_log(
    service: str,
    level: str,
    event: str,
    msg: str,
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Append a unified log record to the stack log.

    Args:
        service: Service identifier ("core", "ucnrr", "devx", etc.).
        level: Log level string (INFO/WARN/ERROR).
        event: Canonical event name.
        msg: Human-readable summary.
        meta: Optional metadata dictionary (must be JSON-serializable).
    """
    record = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "service": service,
        "level": level.upper(),
        "event": event,
        "msg": msg,
        "meta": meta or {},
    }

    try:
        payload = json.dumps(record, default=_default, ensure_ascii=False)
    except Exception:
        record["meta"] = {"error": "failed_to_serialize_meta"}
        payload = json.dumps(record)

    with _LOG_LOCK:
        _ensure_log_path()
        with _LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(payload + "\n")


def _append_jsonl(path: Path, record: Dict[str, Any]) -> None:
    _ensure_log_path()
    serialised = json.dumps(record, default=_default, ensure_ascii=False)
    with _LOG_LOCK:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(serialised + "\n")


def evidence_log(record: Dict[str, Any]) -> None:
    _append_jsonl(_EVIDENCE_LOG_PATH, record)


def supersession_log(record: Dict[str, Any]) -> None:
    _append_jsonl(_SUPERSESSION_LOG_PATH, record)


__all__ = [
    "stack_log",
    "evidence_log",
    "supersession_log",
    "_LOG_PATH",
]
