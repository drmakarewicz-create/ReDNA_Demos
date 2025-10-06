"""Preferences hot-reload helpers for the Explorer UI."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

try:  # ExplorerDev is optional during unit tests / lean runtime
    from ExplorerDev.schema_utils import invalidate_system_prefs_cache
except Exception:  # pragma: no cover - fallback when Dev helpers missing
    def invalidate_system_prefs_cache() -> None:  # type: ignore
        """Fallback that does nothing when ExplorerDev isn't on path."""


@dataclass
class PrefsDiff:
    added: List[str] = field(default_factory=list)
    changed: List[str] = field(default_factory=list)
    removed: List[str] = field(default_factory=list)

    def summary(self) -> List[str]:
        keys: List[str] = []
        keys.extend(self.added)
        keys.extend(self.changed)
        keys.extend(self.removed)
        # Deduplicate while preserving order
        seen: set[str] = set()
        ordered: List[str] = []
        for key in keys:
            if key in seen:
                continue
            seen.add(key)
            ordered.append(key)
        return ordered


@dataclass
class PrefsUpdate:
    updated: bool = False
    diff: PrefsDiff = field(default_factory=PrefsDiff)
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    sha: Optional[str] = None
    mtime: Optional[float] = None


class PrefsWatcher:
    """Watch `dev_system_prefs.json` for updates with debouncing and diffing."""

    def __init__(self, path: Path | str, *, interval_sec: float = 7.0, debounce_ms: int = 300):
        self.path = Path(path)
        self.interval = max(float(interval_sec), 1.0)
        self.debounce = max(int(debounce_ms), 0) / 1000.0

        self._next_poll: float = 0.0
        self._backoff_until: float = 0.0

        self._last_hash: Optional[str] = None
        self._last_mtime: Optional[float] = None
        self._last_data: Optional[Dict[str, Any]] = None
        self._last_error: Optional[str] = None

    # ------------------------------------------------------------------
    def force_refresh(self) -> PrefsUpdate:
        """Force an immediate poll regardless of interval/backoff."""

        self._next_poll = 0.0
        return self.poll(force=True)

    # ------------------------------------------------------------------
    def poll(self, *, force: bool = False) -> PrefsUpdate:
        now = time.monotonic()
        if not force:
            if self._backoff_until and now < self._backoff_until:
                return PrefsUpdate(updated=False, error=self._last_error)
            if now < self._next_poll:
                return PrefsUpdate(updated=False)

        self._next_poll = now + self.interval

        try:
            stat = self.path.stat()
            mtime = float(stat.st_mtime)
        except FileNotFoundError:
            mtime = None
            payload_bytes = b"{}"
        except Exception as exc:  # pragma: no cover - surface error, retry later
            self._last_error = f"Prefs watcher error: {exc}"
            self._backoff_until = now + 30.0
            return PrefsUpdate(updated=False, error=self._last_error)
        else:
            try:
                payload_bytes = self.path.read_bytes()
            except Exception as exc:  # pragma: no cover - transient IO issue
                self._last_error = f"Unable to read prefs: {exc}"
                self._backoff_until = now + 5.0
                return PrefsUpdate(updated=False, error=self._last_error)

        if mtime is not None and self._last_mtime is not None:
            if mtime <= self._last_mtime:
                # No fs-level change
                return PrefsUpdate(updated=False)
            # Debounce rapid writes (e.g. editor temp files)
            if mtime - self._last_mtime < self.debounce:
                self._next_poll = time.monotonic() + max(self.debounce, 0.2)
                return PrefsUpdate(updated=False)

        sha = hashlib.sha256(payload_bytes).hexdigest()
        if sha == self._last_hash:
            # Same contents even if mtime advanced
            self._last_mtime = mtime
            return PrefsUpdate(updated=False)

        # Safe JSON parse with single retry after 100ms as per spec
        data = self._parse_payload(payload_bytes)
        if data is None:
            self._last_error = "Prefs invalid; using last good config"
            self._backoff_until = now + 30.0
            return PrefsUpdate(updated=False, error=self._last_error)

        invalidate_system_prefs_cache()

        diff = self._diff_against_last(data)
        self._last_hash = sha
        self._last_mtime = mtime
        self._last_data = data
        self._last_error = None
        self._backoff_until = 0.0

        return PrefsUpdate(
            updated=True,
            diff=diff,
            data=data,
            error=None,
            timestamp=time.time(),
            sha=sha,
            mtime=mtime,
        )

    # ------------------------------------------------------------------
    def _parse_payload(self, payload: bytes) -> Optional[Dict[str, Any]]:
        attempts = 2
        last_error: Optional[Exception] = None
        for attempt in range(attempts):
            try:
                text = payload.decode("utf-8") or "{}"
                parsed: Any = json.loads(text)
                if isinstance(parsed, dict):
                    return parsed
                return {}
            except json.JSONDecodeError as exc:
                last_error = exc
                if attempt == attempts - 1:
                    break
                time.sleep(0.1)
                try:
                    payload = self.path.read_bytes()
                except Exception:
                    break
            except Exception as exc:  # pragma: no cover - unexpected decode error
                last_error = exc
                break
        return None

    # ------------------------------------------------------------------
    def _diff_against_last(self, new_data: Dict[str, Any]) -> PrefsDiff:
        prev_flat = self._flatten_dict(self._last_data or {})
        new_flat = self._flatten_dict(new_data)

        added = [key for key in new_flat.keys() if key not in prev_flat]
        removed = [key for key in prev_flat.keys() if key not in new_flat]
        changed = [
            key
            for key in new_flat.keys()
            if key in prev_flat and new_flat[key] != prev_flat[key]
        ]
        return PrefsDiff(added=added, changed=changed, removed=removed)

    # ------------------------------------------------------------------
    def _flatten_dict(self, node: Dict[str, Any], prefix: str = "") -> Dict[str, str]:
        flat: Dict[str, str] = {}
        for key, value in node.items():
            key_str = str(key)
            new_prefix = f"{prefix}.{key_str}" if prefix else key_str
            if isinstance(value, dict):
                flat.update(self._flatten_dict(value, new_prefix))
            else:
                flat[new_prefix] = self._normalize_value(value)
        return flat

    # ------------------------------------------------------------------
    @staticmethod
    def _normalize_value(value: Any) -> str:
        if isinstance(value, (str, int, float, bool)) or value is None:
            return json.dumps(value, sort_keys=True)
        if isinstance(value, Iterable):
            try:
                return json.dumps(list(value), sort_keys=True)
            except Exception:
                pass
        return json.dumps(str(value))


__all__ = [
    "PrefsWatcher",
    "PrefsUpdate",
    "PrefsDiff",
]
