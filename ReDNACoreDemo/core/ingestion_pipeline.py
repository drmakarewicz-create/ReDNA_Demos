"""
Unified ingestion pipeline scaffolding for Evergreen 9 (Data Ingestion Universality).

The goal of this module is to provide a single entry point for all ingestion
events across Head Coach, Core, and UCN/RR services.  It applies comfort-index
checks, stamps provenance metadata, and logs events to the telemetry archive.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

PIPELINE_VERSION = "0.1"
LEVEL_ORDER = ["open", "standard", "sensitive", "restricted", "forbidden"]


@dataclass
class NormalizedEvent:
    """Normalized ingestion payload passed through the comfort/provenance stages."""

    event_type: str
    user_id: str
    content: Dict[str, Any]
    metadata: Dict[str, Any]


class ComfortGate:
    """
    Lightweight comfort-index evaluator.

    The comfort profile is stored under:
        data/users/<user_id>/comfort_index.json

    Expected schema (extensible):
    ```
    {
        "max_level": "sensitive",
        "overrides": {
            "file_upload": "restricted",
            "chat_message": "open"
        }
    }
    ```
    """

    def __init__(self, data_root: Path):
        self.data_root = Path(data_root)

    def evaluate(self, event: NormalizedEvent) -> Tuple[bool, Dict[str, Any]]:
        profile = self._load_profile(event.user_id)
        override_level = profile.get("overrides", {}).get(event.event_type)
        effective_threshold = override_level or profile.get("max_level", "sensitive")

        event_level = event.metadata.get("sensitivity_level", "standard")
        if event.metadata.get("comfort_override") == "allow":
            return True, {
                "decision": "override_allow",
                "threshold": effective_threshold,
                "level": event_level,
            }

        if event.metadata.get("comfort_override") == "deny":
            return False, {
                "decision": "override_deny",
                "threshold": effective_threshold,
                "level": event_level,
            }

        allowed = self._rank(event_level) <= self._rank(effective_threshold)

        return allowed, {
            "decision": "threshold",
            "threshold": effective_threshold,
            "level": event_level,
        }

    def _load_profile(self, user_id: str) -> Dict[str, Any]:
        profile_path = self.data_root / "users" / user_id / "comfort_index.json"
        if not profile_path.exists():
            return {}

        try:
            return json.loads(profile_path.read_text())
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("Failed to load comfort profile for %s: %s", user_id, exc)
            return {}

    def _rank(self, level: str) -> int:
        if level in LEVEL_ORDER:
            return LEVEL_ORDER.index(level)
        return LEVEL_ORDER.index("standard")


class ProvenanceTagger:
    """Apply provenance metadata to an ingestion event."""

    def tag(
        self,
        event: NormalizedEvent,
        *,
        source: str,
        actor: str,
    ) -> Dict[str, Any]:
        payload = {
            "event_type": event.event_type,
            "content": event.content,
            "metadata": event.metadata,
        }
        raw = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        return {
            "source": source,
            "actor": actor,
            "content_hash": sha256(raw).hexdigest(),
            "received_at": datetime.now(timezone.utc).isoformat(),
        }


class IngestionPipeline:
    """Main ingestion orchestrator for Core/HC/UCN-RR services."""

    def __init__(
        self,
        *,
        data_root: Optional[Path] = None,
        telemetry_root: Optional[Path] = None,
    ):
        root = Path(__file__).resolve().parents[1] / "data" if data_root is None else Path(data_root)
        self.data_root = root
        self.telemetry_root = (
            root / "telemetry" / "ingestion" if telemetry_root is None else Path(telemetry_root)
        )
        self.telemetry_root.mkdir(parents=True, exist_ok=True)

        self.comfort_gate = ComfortGate(self.data_root)
        self.provenance = ProvenanceTagger()

    # ------------------------------------------------------------------ helpers
    def capture_chat(
        self,
        *,
        user_id: str,
        text: str,
        meta: Optional[Dict[str, Any]] = None,
        source: str = "head_coach",
        actor: str = "hc_orchestrator",
    ) -> Dict[str, Any]:
        metadata = dict(meta or {})
        metadata.setdefault("channel", "chat")
        metadata.setdefault("sensitivity_level", "standard")
        content = {"text": text}
        return self._record_event(
            event_type="chat_message",
            user_id=user_id,
            content=content,
            metadata=metadata,
            source=source,
            actor=actor,
        )

    def capture_file(
        self,
        *,
        user_id: str,
        file_name: str,
        file_bytes: Optional[bytes] = None,
        metadata: Optional[Dict[str, Any]] = None,
        source: str = "core",
        actor: str = "ingestion_daemon",
    ) -> Dict[str, Any]:
        meta = dict(metadata or {})
        byte_len = len(file_bytes) if file_bytes is not None else meta.get("size")
        meta.setdefault("size", byte_len)
        meta.setdefault("sensitivity_level", "sensitive")
        sha_value = meta.get("sha256")
        if sha_value is None and file_bytes is not None:
            sha_value = sha256(file_bytes).hexdigest()
        content = {
            "file_name": file_name,
            "size": byte_len,
            "sha256": sha_value,
            "mime_type": meta.get("mime_type", "application/octet-stream"),
        }
        return self._record_event(
            event_type="file_upload",
            user_id=user_id,
            content=content,
            metadata=meta,
            source=source,
            actor=actor,
        )

    def capture_coach_handoff(
        self,
        *,
        user_id: str,
        from_coach: str,
        to_coach: str,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        source: str = "coach_handoff",
        actor: str = "ucn_rr_ai",
    ) -> Dict[str, Any]:
        meta = dict(metadata or {})
        meta.setdefault("sensitivity_level", "standard")
        content = {
            "from": from_coach,
            "to": to_coach,
            "reason": reason,
        }
        return self._record_event(
            event_type="coach_handoff",
            user_id=user_id,
            content=content,
            metadata=meta,
            source=source,
            actor=actor,
        )

    # ------------------------------------------------------------------ internals
    def _record_event(
        self,
        *,
        event_type: str,
        user_id: str,
        content: Dict[str, Any],
        metadata: Optional[Dict[str, Any]],
        source: str,
        actor: str,
    ) -> Dict[str, Any]:
        normalized = NormalizedEvent(
            event_type=event_type,
            user_id=user_id,
            content=content,
            metadata=dict(metadata or {}),
        )

        accepted, comfort_info = self.comfort_gate.evaluate(normalized)
        provenance = self.provenance.tag(normalized, source=source, actor=actor)
        recorded_at = datetime.now(timezone.utc).isoformat()

        record = {
            "event_type": event_type,
            "user_id": user_id,
            "content": content,
            "metadata": normalized.metadata,
            "accepted": accepted,
            "comfort": comfort_info,
            "provenance": provenance,
            "recorded_at": recorded_at,
            "pipeline_version": PIPELINE_VERSION,
        }

        self._write_record(user_id=user_id, accepted=accepted, timestamp=recorded_at, record=record)
        return record

    def _write_record(self, *, user_id: str, accepted: bool, timestamp: str, record: Dict[str, Any]) -> None:
        bucket = "accepted" if accepted else "quarantined"
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        folder = self.telemetry_root / bucket / user_id / dt.strftime("%Y/%m/%d")
        folder.mkdir(parents=True, exist_ok=True)
        file_name = f"{dt.strftime('%H%M%S%f')}_{record['event_type']}.json"
        path = folder / file_name
        path.write_text(json.dumps(record, indent=2, sort_keys=True))


_PIPELINE: Optional[IngestionPipeline] = None


def get_ingestion_pipeline() -> IngestionPipeline:
    """Return a singleton ingestion pipeline instance."""
    global _PIPELINE
    if _PIPELINE is None:
        _PIPELINE = IngestionPipeline()
    return _PIPELINE


__all__ = [
    "ComfortGate",
    "IngestionPipeline",
    "NormalizedEvent",
    "get_ingestion_pipeline",
]
