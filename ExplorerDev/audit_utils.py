"""Audit utilities for Dev Explorer (JSONL tailing, encryption stub, rollbacks)."""

from __future__ import annotations

try:
    from ExplorerDev.bootstrap import ensure_explorerdev_on_path, ensure_repo_root
except Exception:  # pragma: no cover - fallback when executed directly
    import os
    import sys

    _here = os.path.dirname(os.path.abspath(__file__))
    _parent = os.path.dirname(_here)
    if _parent not in sys.path:
        sys.path.insert(0, _parent)
    from ExplorerDev.bootstrap import ensure_explorerdev_on_path, ensure_repo_root  # type: ignore

ensure_explorerdev_on_path()

import json
import os
import shutil
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Iterable, List, Optional

from ExplorerDev.write_utils import WriteProtectContext, write_guard

REPO_ROOT = ensure_repo_root()


def load_jsonl(path: Path, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Load JSONL entries tail-first (newest first) with optional limit."""

    if not path.exists():
        return []

    maxlen = None
    if isinstance(limit, int) and limit > 0:
        maxlen = limit

    buffer: deque[Dict[str, Any]]
    buffer = deque(maxlen=maxlen)

    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                    if isinstance(payload, dict):
                        buffer.append(payload)
                    elif isinstance(payload, list):
                        buffer.append({"items": payload})
                    else:
                        buffer.append({"value": payload})
                except Exception:
                    buffer.append({"raw": line})
    except FileNotFoundError:
        return []

    entries = list(buffer)
    entries.reverse()  # newest first
    return entries


def encrypt_log(
    path: Path,
    *,
    key: Optional[str] = None,
    write_context: Optional[WriteProtectContext] = None,
) -> Dict[str, Any]:
    """Stub encryption helper: records metadata that the log was marked encrypted."""

    context = write_context or SimpleNamespace(write_protect=False)
    write_guard(context, action="mark log as encrypted")

    marker = {
        "path": str(path),
        "status": "stub-encrypted",
        "key_label": key or "default",
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    meta_path = path.with_suffix((path.suffix or "") + ".meta")
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    with meta_path.open("w", encoding="utf-8") as handle:
        json.dump(marker, handle, indent=2)
    return {"ok": True, "meta_path": str(meta_path), **marker}


def _with_backup(path: Path) -> Path:
    backup = path.with_suffix((path.suffix or "") + ".bak")
    if not backup.exists():
        raise FileNotFoundError(f"No backup found at {backup}")
    return backup


def _restore_from_backup(target: Path, backup: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target.with_suffix((target.suffix or "") + ".rollback")
    shutil.copy2(backup, tmp_path)
    os.replace(tmp_path, target)


def rollback_last_change(
    module: str,
    *,
    repo_root: Optional[Path] = None,
    identifier: Optional[str] = None,
    write_context: Optional[WriteProtectContext] = None,
) -> Dict[str, Any]:
    """Restore a module's file from its backup (.bak)."""

    context = write_context or SimpleNamespace(write_protect=False)
    write_guard(context, action=f"rollback {module}")

    root = repo_root or REPO_ROOT
    module_key = module.strip().lower()

    if module_key == "rr_baselines":
        from ExplorerDev import rr_baseline_utils

        path = rr_baseline_utils.demo_baselines_path(root)
        label = "RR demo baselines"
        invalidate: Iterable[Any] = ()
    elif module_key == "credna_registry":
        from ExplorerDev.credna import credna_store

        path = credna_store.REGISTRY_PATH
        label = "CReDNA registry"

        def _invalidate() -> None:
            credna_store.load_registry()

        invalidate = (_invalidate,)
    elif module_key == "nudge_inbox":
        if not identifier:
            return {"ok": False, "error": "identifier (user_id) required for nudge_inbox rollback"}
        from ExplorerFinal.core import nudge_store

        path = nudge_store.MAILBOX_ROOT / identifier / "inbox.json"
        label = f"Inbox for {identifier}"

        def _invalidate() -> None:
            nudge_store._INBOX_CACHE.pop(identifier, None)  # type: ignore[attr-defined]

        invalidate = (_invalidate,)
    else:
        return {"ok": False, "error": f"Unsupported module '{module}'"}

    if not path.exists():
        return {"ok": False, "error": f"Target file missing: {path}"}

    try:
        backup = _with_backup(path)
    except FileNotFoundError as exc:
        return {"ok": False, "error": str(exc)}

    try:
        _restore_from_backup(path, backup)
    except Exception as exc:
        return {"ok": False, "error": f"Restore failed: {exc}"}

    for callback in invalidate:
        try:
            callback()
        except Exception:
            continue

    return {
        "ok": True,
        "module": module_key,
        "path": str(path),
        "restored_from": str(backup),
        "label": label,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


__all__ = [
    "load_jsonl",
    "encrypt_log",
    "rollback_last_change",
]
