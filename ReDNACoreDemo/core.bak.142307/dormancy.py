"""
Dormancy and Lifecycle Management

Manages user lifecycle states: active, dormant (3/6/12-month tiers), and deceased.
Handles heir transfer for deceased users and RR exclusion logic.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import storage


class LifecycleState(Enum):
    """User lifecycle states."""
    ACTIVE = "active"
    DORMANT_3M = "dormant_3m"      # 3 months inactive
    DORMANT_6M = "dormant_6m"      # 6 months inactive
    DORMANT_12M = "dormant_12m"    # 12 months inactive
    DECEASED = "deceased"          # Permanently inactive, heir transfer eligible


@dataclass
class DormancyStatus:
    """Dormancy status for a user."""
    user_id: str
    state: LifecycleState
    last_activity: datetime
    days_inactive: int
    next_state: Optional[LifecycleState]
    days_until_next_state: Optional[int]
    exclude_from_rr: bool
    heir_id: Optional[str] = None
    deceased_date: Optional[datetime] = None
    notes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HeirTransfer:
    """Heir transfer configuration for deceased users."""
    deceased_user_id: str
    heir_user_id: str
    transfer_date: datetime
    transferred_traits: List[str]
    provenance: Dict[str, Any]
    status: str  # pending, completed, failed


# Thresholds in days
DORMANT_3M_DAYS = 90
DORMANT_6M_DAYS = 180
DORMANT_12M_DAYS = 365

# Exclude from RR at dormant_6m and beyond
RR_EXCLUSION_STATES = {
    LifecycleState.DORMANT_6M,
    LifecycleState.DORMANT_12M,
    LifecycleState.DECEASED,
}


def get_lifecycle_metadata_path(user_id: str) -> Path:
    """Get path to lifecycle metadata file."""
    return storage.get_user_dir(user_id) / "lifecycle.json"


def load_lifecycle_metadata(user_id: str) -> Dict[str, Any]:
    """Load lifecycle metadata for a user."""
    path = get_lifecycle_metadata_path(user_id)
    if not path.exists():
        return {}

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_lifecycle_metadata(user_id: str, metadata: Dict[str, Any]) -> None:
    """Save lifecycle metadata for a user."""
    path = get_lifecycle_metadata_path(user_id)
    path.parent.mkdir(parents=True, exist_ok=True)

    metadata["updated_at"] = datetime.now(timezone.utc).isoformat()

    path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def get_last_activity(user_id: str) -> Optional[datetime]:
    """
    Determine last activity time for a user.

    Checks (in order):
    1. lifecycle.json last_activity
    2. resolved.json updated_ts
    3. evidence.jsonl newest entry
    """
    # Check lifecycle metadata first
    metadata = load_lifecycle_metadata(user_id)
    last_activity_str = metadata.get("last_activity")
    if last_activity_str:
        try:
            return datetime.fromisoformat(last_activity_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            pass

    # Check resolved.json
    try:
        resolved, _, _ = storage.read_user_state(user_id)

        # Find newest updated_ts across all traits
        newest = None
        for trait_id, trait_data in resolved.items():
            if not isinstance(trait_data, dict):
                continue

            ts_str = trait_data.get("updated_ts") or trait_data.get("last_updated")
            if not ts_str:
                continue

            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                if newest is None or ts > newest:
                    newest = ts
            except (ValueError, AttributeError):
                continue

        if newest:
            return newest

    except Exception:
        pass

    # Fallback: assume now if no data found
    return datetime.now(timezone.utc)


def compute_dormancy_status(user_id: str) -> DormancyStatus:
    """Compute current dormancy status for a user."""
    metadata = load_lifecycle_metadata(user_id)

    # Check if marked deceased
    if metadata.get("state") == LifecycleState.DECEASED.value:
        deceased_date_str = metadata.get("deceased_date")
        deceased_date = None
        if deceased_date_str:
            try:
                deceased_date = datetime.fromisoformat(deceased_date_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass

        return DormancyStatus(
            user_id=user_id,
            state=LifecycleState.DECEASED,
            last_activity=deceased_date or datetime.now(timezone.utc),
            days_inactive=9999,
            next_state=None,
            days_until_next_state=None,
            exclude_from_rr=True,
            heir_id=metadata.get("heir_id"),
            deceased_date=deceased_date,
            notes=metadata.get("notes", {}),
        )

    # Compute based on last activity
    last_activity = get_last_activity(user_id)
    now = datetime.now(timezone.utc)
    days_inactive = (now - last_activity).days

    # Determine state based on inactivity
    if days_inactive >= DORMANT_12M_DAYS:
        state = LifecycleState.DORMANT_12M
        next_state = None
        days_until_next = None
    elif days_inactive >= DORMANT_6M_DAYS:
        state = LifecycleState.DORMANT_6M
        next_state = LifecycleState.DORMANT_12M
        days_until_next = DORMANT_12M_DAYS - days_inactive
    elif days_inactive >= DORMANT_3M_DAYS:
        state = LifecycleState.DORMANT_3M
        next_state = LifecycleState.DORMANT_6M
        days_until_next = DORMANT_6M_DAYS - days_inactive
    else:
        state = LifecycleState.ACTIVE
        next_state = LifecycleState.DORMANT_3M
        days_until_next = DORMANT_3M_DAYS - days_inactive

    exclude_from_rr = state in RR_EXCLUSION_STATES

    return DormancyStatus(
        user_id=user_id,
        state=state,
        last_activity=last_activity,
        days_inactive=days_inactive,
        next_state=next_state,
        days_until_next_state=days_until_next,
        exclude_from_rr=exclude_from_rr,
        notes=metadata.get("notes", {}),
    )


def mark_deceased(
    user_id: str,
    heir_id: Optional[str] = None,
    notes: Optional[Dict[str, Any]] = None,
) -> DormancyStatus:
    """
    Mark a user as deceased.

    Args:
        user_id: The deceased user
        heir_id: Optional heir to receive transferred data
        notes: Optional metadata about the deceased status

    Returns:
        Updated DormancyStatus
    """
    now = datetime.now(timezone.utc)

    metadata = {
        "state": LifecycleState.DECEASED.value,
        "deceased_date": now.isoformat(),
        "last_activity": now.isoformat(),
        "heir_id": heir_id,
        "notes": notes or {},
    }

    save_lifecycle_metadata(user_id, metadata)

    return compute_dormancy_status(user_id)


def update_last_activity(user_id: str, timestamp: Optional[datetime] = None) -> None:
    """
    Update last activity timestamp for a user.

    Call this whenever user takes action (evidence submission, feedback, etc.)
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)

    metadata = load_lifecycle_metadata(user_id)
    metadata["last_activity"] = timestamp.isoformat()
    metadata["state"] = LifecycleState.ACTIVE.value

    save_lifecycle_metadata(user_id, metadata)


def should_exclude_from_rr(user_id: str) -> bool:
    """
    Check if user should be excluded from RR calculations.

    Returns True for dormant_6m, dormant_12m, and deceased states.
    """
    status = compute_dormancy_status(user_id)
    return status.exclude_from_rr


def create_heir_transfer(
    deceased_user_id: str,
    heir_user_id: str,
    trait_selection: Optional[List[str]] = None,
) -> HeirTransfer:
    """
    Create heir transfer configuration.

    Args:
        deceased_user_id: The deceased user
        heir_user_id: The heir
        trait_selection: Specific traits to transfer (None = all)

    Returns:
        HeirTransfer object (status: pending)
    """
    deceased_status = compute_dormancy_status(deceased_user_id)

    if deceased_status.state != LifecycleState.DECEASED:
        raise ValueError(f"User {deceased_user_id} is not marked as deceased")

    # Load deceased user's resolved traits
    try:
        resolved, _, _ = storage.read_user_state(deceased_user_id)
        available_traits = list(resolved.keys())
    except Exception:
        available_traits = []

    # Determine traits to transfer
    if trait_selection is None:
        traits_to_transfer = available_traits
    else:
        traits_to_transfer = [t for t in trait_selection if t in available_traits]

    return HeirTransfer(
        deceased_user_id=deceased_user_id,
        heir_user_id=heir_user_id,
        transfer_date=datetime.now(timezone.utc),
        transferred_traits=traits_to_transfer,
        provenance={
            "source": "heir_transfer",
            "deceased_user": deceased_user_id,
            "transfer_initiated": datetime.now(timezone.utc).isoformat(),
        },
        status="pending",
    )


def execute_heir_transfer(transfer: HeirTransfer) -> Dict[str, Any]:
    """
    Execute heir transfer (copy traits from deceased to heir with provenance).

    Returns:
        Result dict with transfer status
    """
    try:
        # Load deceased user's data
        deceased_resolved, _, _ = storage.read_user_state(transfer.deceased_user_id)

        # Load heir's data
        heir_resolved, heir_evidence, heir_obs = storage.read_user_state(transfer.heir_user_id)

        transferred_count = 0
        for trait_id in transfer.transferred_traits:
            if trait_id not in deceased_resolved:
                continue

            deceased_trait = deceased_resolved[trait_id]

            # Create inherited version with provenance
            inherited_trait = {**deceased_trait}
            inherited_trait["provenance"] = {
                **inherited_trait.get("provenance", {}),
                "inherited_from": transfer.deceased_user_id,
                "inheritance_date": datetime.now(timezone.utc).isoformat(),
                "inheritance_method": "heir_transfer",
            }
            inherited_trait["notes"] = {
                **inherited_trait.get("notes", {}),
                "heir_transfer": f"Inherited from {transfer.deceased_user_id}",
            }

            # Only transfer if heir doesn't have this trait, or if deceased has higher UCN
            should_transfer = False
            if trait_id not in heir_resolved:
                should_transfer = True
            else:
                deceased_ucn = deceased_trait.get("ucn", 0)
                heir_ucn = heir_resolved[trait_id].get("ucn", 0)
                if deceased_ucn > heir_ucn:
                    should_transfer = True

            if should_transfer:
                heir_resolved[trait_id] = inherited_trait
                transferred_count += 1

        # Save heir's updated data
        storage.write_user_state(transfer.heir_user_id, heir_resolved, heir_evidence, heir_obs)

        transfer.status = "completed"

        return {
            "ok": True,
            "transferred_count": transferred_count,
            "heir_user_id": transfer.heir_user_id,
            "deceased_user_id": transfer.deceased_user_id,
        }

    except Exception as e:
        transfer.status = "failed"
        return {
            "ok": False,
            "error": str(e),
        }


def list_dormant_users(min_state: LifecycleState = LifecycleState.DORMANT_3M) -> List[DormancyStatus]:
    """
    List all users at or above a dormancy threshold.

    Args:
        min_state: Minimum dormancy state to include

    Returns:
        List of DormancyStatus objects
    """
    state_order = {
        LifecycleState.ACTIVE: 0,
        LifecycleState.DORMANT_3M: 1,
        LifecycleState.DORMANT_6M: 2,
        LifecycleState.DORMANT_12M: 3,
        LifecycleState.DECEASED: 4,
    }

    min_level = state_order[min_state]

    dormant_users = []

    # Scan all users
    users_dir = storage.STORAGE_ROOT / "users"
    if not users_dir.exists():
        return []

    for user_dir in users_dir.iterdir():
        if not user_dir.is_dir():
            continue

        user_id = user_dir.name
        status = compute_dormancy_status(user_id)

        if state_order[status.state] >= min_level:
            dormant_users.append(status)

    # Sort by days inactive (descending)
    dormant_users.sort(key=lambda s: s.days_inactive, reverse=True)

    return dormant_users


__all__ = [
    "LifecycleState",
    "DormancyStatus",
    "HeirTransfer",
    "compute_dormancy_status",
    "mark_deceased",
    "update_last_activity",
    "should_exclude_from_rr",
    "create_heir_transfer",
    "execute_heir_transfer",
    "list_dormant_users",
]
