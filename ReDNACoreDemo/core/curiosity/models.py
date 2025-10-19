from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

ReasonCode = Literal[
    "low_confidence",
    "schema_repair_low_conf",
    "value_missing",
    "contradiction",
    "novel_signal",
    "policy_borderline",
]

Status = Literal["queued", "asked", "answered", "dismissed", "expired"]


class CuriosityItem(BaseModel):
    id: str
    user_id: str
    trait_id: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    reason_code: ReasonCode
    inputs: Dict[str, Optional[float]] = Field(default_factory=dict)
    suggested_question: str
    expected_information_gain: float
    cooldown_key: str
    status: Status = "queued"
    links: Optional[List[str]] = None
    asked_at: Optional[datetime] = None
    answered_at: Optional[datetime] = None
    answer_text: Optional[str] = None
    dismissed_at: Optional[datetime] = None
    dismiss_reason: Optional[str] = None
