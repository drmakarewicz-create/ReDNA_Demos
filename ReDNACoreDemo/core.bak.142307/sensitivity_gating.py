"""
Sensitive DNA Gating

Manages access to sensitive traits with consent flags and threshold-based visibility.
Provides grayed preview functionality until explicit consent or threshold is met.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from . import storage


class SensitivityLevel(Enum):
    """Trait sensitivity levels."""
    PUBLIC = "public"           # No restrictions
    STANDARD = "standard"       # Normal ReDNA traits
    SENSITIVE = "sensitive"     # Requires threshold or consent
    RESTRICTED = "restricted"   # Requires explicit consent
    PRIVATE = "private"         # Never exposed without consent


class ConsentStatus(Enum):
    """Consent states for sensitive data."""
    NOT_REQUESTED = "not_requested"
    PENDING = "pending"
    GRANTED = "granted"
    DENIED = "denied"
    REVOKED = "revoked"


@dataclass
class SensitivityConfig:
    """Configuration for a sensitive trait."""
    trait_id: str
    level: SensitivityLevel
    ucn_threshold: float  # Threshold to auto-reveal (if consent not required)
    consent_required: bool  # If True, threshold doesn't override
    consent_prompt: str  # Text to show when requesting consent
    tooltip: str  # Explanation of why trait is sensitive


@dataclass
class ConsentRecord:
    """Record of user consent for a sensitive trait."""
    user_id: str
    trait_id: str
    status: ConsentStatus
    requested_at: Optional[datetime] = None
    responded_at: Optional[datetime] = None
    notes: str = ""


# Default sensitivity configurations
DEFAULT_SENSITIVE_TRAITS: Dict[str, SensitivityConfig] = {
    "HealthMetrics.mental_health_history": SensitivityConfig(
        trait_id="HealthMetrics.mental_health_history",
        level=SensitivityLevel.RESTRICTED,
        ucn_threshold=0.8,
        consent_required=True,
        consent_prompt="Mental health history is sensitive. Share for personalized wellness coaching?",
        tooltip="Mental health data requires explicit consent",
    ),
    "HealthMetrics.medical_conditions": SensitivityConfig(
        trait_id="HealthMetrics.medical_conditions",
        level=SensitivityLevel.RESTRICTED,
        ucn_threshold=0.8,
        consent_required=True,
        consent_prompt="Medical conditions help us provide better recommendations. Share?",
        tooltip="Medical data is protected",
    ),
    "FinancialProfile.income_range": SensitivityConfig(
        trait_id="FinancialProfile.income_range",
        level=SensitivityLevel.SENSITIVE,
        ucn_threshold=0.7,
        consent_required=False,
        consent_prompt="Income information helps with budgeting advice. Share?",
        tooltip="Financial data is sensitive and gated",
    ),
    "FinancialProfile.debt_level": SensitivityConfig(
        trait_id="FinancialProfile.debt_level",
        level=SensitivityLevel.SENSITIVE,
        ucn_threshold=0.7,
        consent_required=False,
        consent_prompt="Debt information enables better financial planning. Share?",
        tooltip="Financial data is sensitive and gated",
    ),
    "PersonalIdentity.sexual_orientation": SensitivityConfig(
        trait_id="PersonalIdentity.sexual_orientation",
        level=SensitivityLevel.PRIVATE,
        ucn_threshold=1.0,  # Never auto-reveal
        consent_required=True,
        consent_prompt="Sexual orientation is private. Share for personalized content?",
        tooltip="Private identity data, consent required",
    ),
    "PersonalIdentity.gender_identity": SensitivityConfig(
        trait_id="PersonalIdentity.gender_identity",
        level=SensitivityLevel.PRIVATE,
        ucn_threshold=1.0,
        consent_required=True,
        consent_prompt="Gender identity is private. Share for personalized content?",
        tooltip="Private identity data, consent required",
    ),
}


def get_consent_path(user_id: str) -> Path:
    """Get path to consent records file."""
    return storage.get_user_dir(user_id) / "consent.json"


def load_consent_records(user_id: str) -> Dict[str, ConsentRecord]:
    """Load all consent records for a user."""
    path = get_consent_path(user_id)
    if not path.exists():
        return {}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        records = {}

        for trait_id, record_data in data.items():
            status_str = record_data.get("status", "not_requested")
            try:
                status = ConsentStatus(status_str)
            except ValueError:
                status = ConsentStatus.NOT_REQUESTED

            requested_at = None
            if record_data.get("requested_at"):
                try:
                    requested_at = datetime.fromisoformat(
                        record_data["requested_at"].replace("Z", "+00:00")
                    )
                except (ValueError, AttributeError):
                    pass

            responded_at = None
            if record_data.get("responded_at"):
                try:
                    responded_at = datetime.fromisoformat(
                        record_data["responded_at"].replace("Z", "+00:00")
                    )
                except (ValueError, AttributeError):
                    pass

            records[trait_id] = ConsentRecord(
                user_id=user_id,
                trait_id=trait_id,
                status=status,
                requested_at=requested_at,
                responded_at=responded_at,
                notes=record_data.get("notes", ""),
            )

        return records

    except Exception:
        return {}


def save_consent_records(user_id: str, records: Dict[str, ConsentRecord]) -> None:
    """Save consent records for a user."""
    path = get_consent_path(user_id)
    path.parent.mkdir(parents=True, exist_ok=True)

    data = {}
    for trait_id, record in records.items():
        data[trait_id] = {
            "status": record.status.value,
            "requested_at": record.requested_at.isoformat() if record.requested_at else None,
            "responded_at": record.responded_at.isoformat() if record.responded_at else None,
            "notes": record.notes,
        }

    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_sensitivity_config(trait_id: str) -> Optional[SensitivityConfig]:
    """Get sensitivity configuration for a trait."""
    return DEFAULT_SENSITIVE_TRAITS.get(trait_id)


def is_trait_visible(
    user_id: str,
    trait_id: str,
    current_ucn: float,
) -> bool:
    """
    Determine if a trait should be visible (not gated).

    Args:
        user_id: User ID
        trait_id: Full trait path
        current_ucn: Current UCN value for the trait

    Returns:
        True if trait can be shown, False if gated
    """
    config = get_sensitivity_config(trait_id)

    # Not sensitive = always visible
    if config is None:
        return True

    # Check consent status
    consent_records = load_consent_records(user_id)
    consent = consent_records.get(trait_id)

    # If consent granted, always visible
    if consent and consent.status == ConsentStatus.GRANTED:
        return True

    # If consent denied or revoked, never visible
    if consent and consent.status in {ConsentStatus.DENIED, ConsentStatus.REVOKED}:
        return False

    # If consent required and not granted, not visible
    if config.consent_required:
        return False

    # Check UCN threshold
    return current_ucn >= config.ucn_threshold


def request_consent(user_id: str, trait_id: str) -> ConsentRecord:
    """
    Request consent for a sensitive trait.

    Returns:
        ConsentRecord with status=PENDING
    """
    config = get_sensitivity_config(trait_id)
    if config is None:
        raise ValueError(f"Trait {trait_id} is not configured as sensitive")

    records = load_consent_records(user_id)

    # Create or update consent request
    if trait_id in records:
        record = records[trait_id]
        # Don't re-request if already granted/denied
        if record.status in {ConsentStatus.GRANTED, ConsentStatus.DENIED}:
            return record
    else:
        record = ConsentRecord(
            user_id=user_id,
            trait_id=trait_id,
            status=ConsentStatus.PENDING,
            requested_at=datetime.now(timezone.utc),
        )

    record.status = ConsentStatus.PENDING
    record.requested_at = datetime.now(timezone.utc)

    records[trait_id] = record
    save_consent_records(user_id, records)

    return record


def grant_consent(user_id: str, trait_id: str, notes: str = "") -> ConsentRecord:
    """Grant consent for a sensitive trait."""
    records = load_consent_records(user_id)

    if trait_id not in records:
        record = ConsentRecord(
            user_id=user_id,
            trait_id=trait_id,
            status=ConsentStatus.GRANTED,
            responded_at=datetime.now(timezone.utc),
            notes=notes,
        )
    else:
        record = records[trait_id]
        record.status = ConsentStatus.GRANTED
        record.responded_at = datetime.now(timezone.utc)
        record.notes = notes

    records[trait_id] = record
    save_consent_records(user_id, records)

    return record


def deny_consent(user_id: str, trait_id: str, notes: str = "") -> ConsentRecord:
    """Deny consent for a sensitive trait."""
    records = load_consent_records(user_id)

    if trait_id not in records:
        record = ConsentRecord(
            user_id=user_id,
            trait_id=trait_id,
            status=ConsentStatus.DENIED,
            responded_at=datetime.now(timezone.utc),
            notes=notes,
        )
    else:
        record = records[trait_id]
        record.status = ConsentStatus.DENIED
        record.responded_at = datetime.now(timezone.utc)
        record.notes = notes

    records[trait_id] = record
    save_consent_records(user_id, records)

    return record


def revoke_consent(user_id: str, trait_id: str, notes: str = "") -> ConsentRecord:
    """Revoke previously granted consent."""
    records = load_consent_records(user_id)

    if trait_id not in records:
        raise ValueError(f"No consent record found for {trait_id}")

    record = records[trait_id]
    record.status = ConsentStatus.REVOKED
    record.responded_at = datetime.now(timezone.utc)
    record.notes = notes

    records[trait_id] = record
    save_consent_records(user_id, records)

    return record


def get_gated_preview(trait_id: str, current_ucn: float) -> Dict[str, Any]:
    """
    Get grayed preview information for a gated trait.

    Returns:
        Dict with preview information suitable for UI rendering
    """
    config = get_sensitivity_config(trait_id)

    if config is None:
        return {
            "gated": False,
            "trait_id": trait_id,
        }

    ucn_progress = min(1.0, current_ucn / config.ucn_threshold) if config.ucn_threshold > 0 else 0.0

    return {
        "gated": True,
        "trait_id": trait_id,
        "sensitivity_level": config.level.value,
        "ucn_threshold": config.ucn_threshold,
        "current_ucn": current_ucn,
        "ucn_progress": ucn_progress,
        "consent_required": config.consent_required,
        "consent_prompt": config.consent_prompt,
        "tooltip": config.tooltip,
        "unlock_message": (
            f"Consent required to view"
            if config.consent_required
            else f"UCN {current_ucn:.2f}/{config.ucn_threshold:.2f} - Continue building confidence to unlock"
        ),
    }


def list_pending_consent_requests(user_id: str) -> List[Dict[str, Any]]:
    """List all pending consent requests for a user."""
    records = load_consent_records(user_id)

    pending = []
    for trait_id, record in records.items():
        if record.status == ConsentStatus.PENDING:
            config = get_sensitivity_config(trait_id)

            pending.append({
                "trait_id": trait_id,
                "requested_at": record.requested_at.isoformat() if record.requested_at else None,
                "consent_prompt": config.consent_prompt if config else "Grant access to this data?",
                "tooltip": config.tooltip if config else "",
            })

    return pending


def get_all_sensitive_traits() -> List[str]:
    """Get list of all trait IDs configured as sensitive."""
    return list(DEFAULT_SENSITIVE_TRAITS.keys())


__all__ = [
    "SensitivityLevel",
    "ConsentStatus",
    "SensitivityConfig",
    "ConsentRecord",
    "is_trait_visible",
    "request_consent",
    "grant_consent",
    "deny_consent",
    "revoke_consent",
    "get_gated_preview",
    "list_pending_consent_requests",
    "get_all_sensitive_traits",
]
