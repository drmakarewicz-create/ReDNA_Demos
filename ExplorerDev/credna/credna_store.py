"""Persistence helpers for Coach ReDNA registries."""

from __future__ import annotations

try:
    from ExplorerDev.bootstrap import ensure_explorerdev_on_path, ensure_repo_root
except Exception:  # pragma: no cover
    import os
    import sys

    _here = os.path.dirname(os.path.abspath(__file__))
    _parent = os.path.dirname(_here)
    if _parent not in sys.path:
        sys.path.insert(0, _parent)
    from ExplorerDev.bootstrap import ensure_explorerdev_on_path, ensure_repo_root  # type: ignore

ensure_explorerdev_on_path()

import copy
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Optional

try:  # optional dependency — fall back to JSON when PyYAML missing
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None  # type: ignore

try:  # Streamlit available when running Dev Explorer UI
    import streamlit as st  # type: ignore
except Exception:  # pragma: no cover
    st = None  # type: ignore

from ExplorerDev import schema_utils
from ExplorerDev.write_utils import WriteProtectContext, write_guard


REPO_ROOT = ensure_repo_root()
DEFAULT_REGISTRY_PATH = Path(__file__).resolve().with_name("credna_schema.yaml")
DATA_DIR = REPO_ROOT / "data" / "dev_credna"
REGISTRY_PATH = DATA_DIR / "credna_registry.yaml"
AUDIT_LOG_PATH = REPO_ROOT / "data" / "dev_logs" / "credna.jsonl"

SESSION_REGISTRY_KEY = "_credna_registry"
SESSION_HISTORY_KEY = "_credna_registry_history"
MAX_HISTORY = 25


def _session_state() -> MutableMapping[str, Any]:
    if st is not None:
        return st.session_state
    # fallback for non-Streamlit contexts (e.g. tests, compile)
    global _SESSION_CACHE
    try:
        cache = _SESSION_CACHE  # type: ignore[name-defined]
    except NameError:  # pragma: no cover - first import path
        _SESSION_CACHE = {}
        cache = _SESSION_CACHE
    return cache  # type: ignore[return-value]


def _deepcopy(obj: Any) -> Any:
    try:
        return copy.deepcopy(obj)
    except Exception:  # pragma: no cover - defensive copy fallback
        return json.loads(json.dumps(obj)) if isinstance(obj, (dict, list)) else obj


def _load_yaml(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        if yaml is not None:
            with path.open("r", encoding="utf-8") as handle:
                data = yaml.safe_load(handle) or {}
        else:
            data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _dump_yaml(path: Path, payload: Mapping[str, Any]) -> None:
    text: str
    if yaml is not None:
        text = yaml.safe_dump(
            payload,
            sort_keys=False,
            allow_unicode=True,
        )
    else:
        text = json.dumps(payload, indent=2, ensure_ascii=False)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        backup_path = path.with_suffix(path.suffix + ".bak")
        try:
            shutil.copy2(path, backup_path)
        except Exception:
            try:
                backup_path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
            except Exception:
                pass
    with tmp_path.open("w", encoding="utf-8") as handle:
        handle.write(text)
    os.replace(tmp_path, path)


def _append_audit(record: Mapping[str, Any]) -> None:
    try:
        AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with AUDIT_LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")
    except Exception:  # pragma: no cover - audit best-effort
        pass


def _ensure_history(store: MutableMapping[str, Any]) -> None:
    if SESSION_HISTORY_KEY not in store:
        store[SESSION_HISTORY_KEY] = []


def _push_history(previous: Mapping[str, Any]) -> None:
    store = _session_state()
    _ensure_history(store)
    history: Iterable[Any] = store.get(SESSION_HISTORY_KEY, [])
    snapshots = list(history)
    snapshots.append(_deepcopy(previous))
    if len(snapshots) > MAX_HISTORY:
        snapshots = snapshots[-MAX_HISTORY:]
    store[SESSION_HISTORY_KEY] = snapshots


def default_registry() -> Dict[str, Any]:
    payload = _load_yaml(DEFAULT_REGISTRY_PATH)
    return _deepcopy(payload) if isinstance(payload, dict) else {"schemaVersion": 1, "coaches": {}}


def load_registry(context: Optional[WriteProtectContext] = None, *, force: bool = False) -> Dict[str, Any]:
    """Return the working Coach ReDNA registry, seeding from disk or defaults."""

    store = _session_state()
    if not force and SESSION_REGISTRY_KEY in store:
        return _deepcopy(store[SESSION_REGISTRY_KEY])

    registry = _load_yaml(REGISTRY_PATH)
    if registry is None:
        registry = default_registry()

    store[SESSION_REGISTRY_KEY] = _deepcopy(registry)
    _ensure_history(store)
    # Reset history when reloading from source
    store[SESSION_HISTORY_KEY] = []
    return _deepcopy(registry)


def set_registry(registry: Mapping[str, Any]) -> None:
    """Replace the in-session registry snapshot, storing undo history."""

    store = _session_state()
    current = store.get(SESSION_REGISTRY_KEY)
    if isinstance(current, Mapping):
        _push_history(current)
    store[SESSION_REGISTRY_KEY] = _deepcopy(registry)


def revert_last() -> Optional[Dict[str, Any]]:
    """Pop the most recent history entry and restore it as the working registry."""

    store = _session_state()
    history = list(store.get(SESSION_HISTORY_KEY, []))
    if not history:
        return None
    previous = history.pop()
    store[SESSION_HISTORY_KEY] = history
    store[SESSION_REGISTRY_KEY] = _deepcopy(previous)
    return _deepcopy(previous)


def is_save_enabled() -> bool:
    value, _ = schema_utils.get_flag_bool("CREDNA_SAVE_ENABLED", False)
    return bool(value)


def save_registry(
    registry: Mapping[str, Any],
    context: WriteProtectContext,
    *,
    note: Optional[str] = None,
) -> None:
    """Persist the registry to disk if writes are permitted and flag-enabled."""

    if not is_save_enabled():
        raise PermissionError(
            "CREDNA_SAVE_ENABLED=false — enable the flag in CP+ to persist CReDNA changes."
        )
    write_guard(context, action="save the CReDNA registry")
    payload = _deepcopy(registry)
    _dump_yaml(REGISTRY_PATH, payload)
    audit_record = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "action": "save_registry",
        "path": str(REGISTRY_PATH),
        "note": note,
    }
    _append_audit(audit_record)


def get_registry(context: Optional[WriteProtectContext] = None) -> Dict[str, Any]:
    """Convenience wrapper returning a deep copy of the working registry."""

    return _deepcopy(load_registry(context))


__all__ = [
    "load_registry",
    "get_registry",
    "set_registry",
    "save_registry",
    "revert_last",
    "default_registry",
    "is_save_enabled",
    "can_revert",
]


def can_revert() -> bool:
    """Return True when there is an in-session snapshot to roll back to."""

    store = _session_state()
    history = store.get(SESSION_HISTORY_KEY, [])
    return bool(history)
