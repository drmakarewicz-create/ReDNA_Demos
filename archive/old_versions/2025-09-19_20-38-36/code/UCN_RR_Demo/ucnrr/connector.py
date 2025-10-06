# ucnrr/connector.py
from __future__ import annotations
from typing import Any, Dict, Optional, Tuple
import json
import importlib

class CoreConnector:
    """
    Minimal connector stub that can:
      - load a Core snapshot from a JSON file or dict
      - connect 'live' to the Core (if importable) and request a snapshot
    """

    def __init__(self) -> None:
        self._last_snapshot: Optional[Dict[str, Any]] = None
        self._live_connected: bool = False
        self._core_version: Optional[str] = None

    def from_file(self, path: str) -> Tuple[bool, Optional[str]]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                snap = json.load(f)
            return self.from_dict(snap)
        except Exception as e:
            return False, str(e)

    def from_dict(self, snap: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        if not isinstance(snap, dict):
            return False, "Not a dict."
        self._last_snapshot = snap
        self._core_version = str(snap.get("schema_version"))
        self._live_connected = False
        return True, None

    def connect_live_core(self) -> Tuple[bool, Optional[str]]:
        """
        Tries to import a 'core' package with class ReDNACore that has snapshot().
        Stores the fetched snapshot on success.
        """
        try:
            core_mod = importlib.import_module("core")
            ReDNACore = getattr(core_mod, "ReDNACore", None)
            if ReDNACore is None:
                return False, "Could not find ReDNACore in 'core' package."

            core = ReDNACore()
            if not hasattr(core, "snapshot"):
                return False, "Core instance has no snapshot() method."

            snap = core.snapshot()
            if not isinstance(snap, dict):
                return False, "snapshot() did not return a dict."

            self._last_snapshot = snap
            self._live_connected = True
            self._core_version = str(snap.get("schema_version"))
            return True, None

        except Exception as e:
            return False, str(e)

    # ---- accessors ----
    def last_snapshot(self) -> Optional[Dict[str, Any]]:
        return self._last_snapshot

    def is_live(self) -> bool:
        return self._live_connected

    def core_schema_version(self) -> Optional[str]:
        return self._core_version