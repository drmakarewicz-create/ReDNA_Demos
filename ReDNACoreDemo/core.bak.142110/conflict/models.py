"""Data models for the conflict resolution subsystem."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


EvidenceSource = Literal["core", "ucnrr", "coach", "third_party", "sensor", "user_assertion"]
ConflictKind = Literal["trait", "interpretation", "policy", "permission", "system"]
ConflictSeverity = Literal["low", "medium", "high", "critical"]
ConflictStatus = Literal["open", "auto_resolved", "resolved", "denied", "escalated"]


class Evidence(BaseModel):
    """Generic evidence payload used to weigh conflicting signals."""

    evidence_id: str
    source_type: EvidenceSource
    module: Optional[str] = None
    timestamp: datetime
    value: Any
    ucn: Optional[float] = None
    rr: Optional[float] = None
    provenance: Dict[str, Any] = Field(default_factory=dict)
    weight: Optional[float] = None


class UserAssertion(Evidence):
    """User provided self-report evidence."""

    evidence_type: Literal["user_assertion"] = "user_assertion"
    assertion_text: str
    assertion_strength: Literal["casual", "emphatic", "sworn"] = "casual"
    setting: Literal["private", "1to1", "small_group", "public"] = "private"
    stakes: Literal["low", "moderate", "high"] = "low"
    anonymity: bool = False


class Outcome(BaseModel):
    """Resolution result for a conflict."""

    resolver: str
    resolved_value: Optional[Any] = None
    resolved_ucn: Optional[float] = None
    reason: str
    timestamp: datetime = Field(default_factory=lambda: datetime.utcnow())
    audit_refs: Dict[str, Any] = Field(default_factory=dict)


class Conflict(BaseModel):
    """Conflict entity representing competing signals for a trait/policy."""

    conflict_id: str
    user_id: str
    kind: ConflictKind
    path: Optional[str] = None
    created_at: datetime
    severity: ConflictSeverity
    status: ConflictStatus = "open"
    participants: List[str] = Field(default_factory=list)
    signals: Dict[str, Any] = Field(default_factory=dict)
    evidence: List[Evidence] = Field(default_factory=list)
    outcome: Optional[Outcome] = None

    def add_evidence(self, item: Evidence) -> None:
        """Append a piece of evidence to the conflict."""

        self.evidence.append(item)

    @property
    def is_sensitive(self) -> bool:
        """Return True when the conflict touches a sensitive trait path."""

        if not self.path:
            return False
        return self.path.startswith("BeliefValueDNA.") or self.path.startswith("HealthDNA.")

    def distinct_sources(self) -> int:
        """Count distinct evidence sources."""

        return len({ev.source_type for ev in self.evidence})

    def signal_count(self) -> int:
        """Total number of evidence items supplied."""

        return len(self.evidence)

