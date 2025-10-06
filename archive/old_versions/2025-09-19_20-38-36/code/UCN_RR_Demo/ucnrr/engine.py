# engine.py — Core demo engine with richer provenance
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List
from datetime import datetime
from .core_adapter import _normalize_path

@dataclass
class CoreEngine:
    snapshot: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.snapshot:
            self.snapshot = {
                "schema_version": "core/3.1",
                "user_id": "demo_user",
                "snapshot_id": f"snap_{int(datetime.utcnow().timestamp())}",
                "data": {}
            }

    def apply_evidence(self, evidence: List[Dict[str, Any]], provenance: Dict[str, Any]) -> None:
        data = self.snapshot.setdefault("data", {})
        now_iso = datetime.utcnow().isoformat() + "Z"
        for ev in evidence:
            bucket = (ev.get("dna") or "misc").split(".")[0] if not ev.get("dna_path") else ev["dna_path"][0]
            item = dict(ev)
            path = _normalize_path(item, bucket)
            item["dna_path"] = path
            item.pop("dna", None)
            item.setdefault("observed_at", now_iso)

            pr = dict(provenance or {})
            pr.setdefault("source", "Explorer.HeadCoach")
            pr.setdefault("method", "self-report")
            pr.setdefault("channel", "ui")
            pr.setdefault("credibility_tier", "unverified")  # new field
            pr.setdefault("applied_at", now_iso)
            item["provenance"] = pr

            data.setdefault(path[0], []).append(item)

    def last_snapshot(self) -> Dict[str, Any]:
        return self.snapshot