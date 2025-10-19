"""Snapshot Exporter: Freezes user's PaDNA into timestamped JSON bundles."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import json

from . import storage

_SNAPSHOTS_DIR = "snapshots"
_INDEX_FILENAME = "index.json"
_VERSION = "1.0.0"


@dataclass
class SnapshotMeta:
    """Lightweight snapshot metadata for listings."""
    id: str
    user_id: str
    created_at: str
    scope: str  # "full" or "partial"
    families: List[str]
    size_bytes: int
    trait_count: int
    label: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Snapshot:
    """Complete snapshot of user's PaDNA."""
    id: str
    user_id: str
    created_at: str
    version: str
    scope: str  # "full" or "partial"
    families: List[str]
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.id,
            "user_id": self.user_id,
            "created_at": self.created_at,
            "version": self.version,
            "scope": self.scope,
            "families": self.families,
            "metadata": self.metadata,
            "data": self.data,
        }

    def to_meta(self) -> SnapshotMeta:
        """Convert to lightweight metadata."""
        return SnapshotMeta(
            id=self.id,
            user_id=self.user_id,
            created_at=self.created_at,
            scope=self.scope,
            families=self.families,
            size_bytes=self.metadata.get("size_bytes", 0),
            trait_count=self.metadata.get("trait_count", 0),
            label=self.metadata.get("label"),
        )


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _read_user_state(user_id: str) -> tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """Read user state files directly (simplified version)."""
    from pathlib import Path

    base_dir = Path("data/users") / user_id

    # Read observations
    obs_path = base_dir / "observations.json"
    obs_dict = storage.load_json(obs_path, default={}) if obs_path.exists() else {}

    # Read resolved
    resolved_path = base_dir / "resolved.json"
    resolved_dict = storage.load_json(resolved_path, default={}) if resolved_path.exists() else {}

    # Read evidence
    evidence_path = base_dir / "evidence.jsonl"
    evidence_dict = {}
    if evidence_path.exists():
        try:
            with open(evidence_path, "r") as f:
                for line in f:
                    if line.strip():
                        entry = json.loads(line)
                        trait = entry.get("trait")
                        if trait:
                            if trait not in evidence_dict:
                                evidence_dict[trait] = []
                            evidence_dict[trait].append(entry)
        except Exception:
            pass

    return obs_dict, resolved_dict, evidence_dict


def _make_snapshot_id(timestamp: str) -> str:
    """Generate snapshot ID from timestamp."""
    # Format: snapshot_20251004T123045
    clean_ts = timestamp.replace(":", "").replace("-", "").split(".")[0]
    return f"snapshot_{clean_ts}"


def _extract_family(trait_path: str) -> Optional[str]:
    """Extract family from trait path (e.g., PaDNA.LooksDNA.EyeColor → LooksDNA)."""
    parts = trait_path.split(".")
    if len(parts) >= 2:
        return parts[1]
    return None


def _filter_by_families(data: Dict[str, Any], families: List[str]) -> Dict[str, Any]:
    """Filter trait data by family list."""
    if not families:
        return data

    families_set = set(families)
    filtered = {}

    for trait_path, value in data.items():
        family = _extract_family(trait_path)
        if family and family in families_set:
            filtered[trait_path] = value

    return filtered


def _compute_metadata(data: Dict[str, Any], label: Optional[str] = None) -> Dict[str, Any]:
    """Compute metadata for snapshot."""
    # Count traits
    trait_count = len(data.get("observations", {}))

    # Estimate size (rough approximation)
    json_str = json.dumps(data)
    size_bytes = len(json_str.encode("utf-8"))

    # Extract families
    families_set = set()
    for trait_path in data.get("observations", {}).keys():
        family = _extract_family(trait_path)
        if family:
            families_set.add(family)

    return {
        "trait_count": trait_count,
        "family_count": len(families_set),
        "size_bytes": size_bytes,
        "export_method": "api",
        "label": label,
    }


def export_snapshot(
    user_id: str,
    families: Optional[List[str]] = None,
    label: Optional[str] = None,
) -> Snapshot:
    """
    Export user's PaDNA as a timestamped snapshot.

    Args:
        user_id: User identifier
        families: Optional list of trait families to include (e.g., ["LooksDNA", "StyleDNA"])
                 If None, exports full PaDNA
        label: Optional human-readable label

    Returns:
        Snapshot object with complete data

    Example:
        >>> snapshot = export_snapshot("test_user", families=["LooksDNA"])
        >>> print(snapshot.scope)
        'partial'
        >>> print(snapshot.families)
        ['LooksDNA']
    """
    # Load user state
    try:
        obs_dict, resolved_dict, evidence_dict = _read_user_state(user_id)
    except Exception:
        # User has no data yet
        obs_dict = {}
        resolved_dict = {}
        evidence_dict = {}

    # Determine scope
    scope = "partial" if families else "full"

    # Filter data if partial
    if families:
        obs_dict = _filter_by_families(obs_dict, families)
        resolved_dict = _filter_by_families(resolved_dict, families)
        evidence_dict = _filter_by_families(evidence_dict, families)
        included_families = families
    else:
        # Full export - extract all families
        families_set = set()
        for trait_path in obs_dict.keys():
            family = _extract_family(trait_path)
            if family:
                families_set.add(family)
        included_families = sorted(families_set)

    # Build data bundle
    data = {
        "observations": obs_dict,
        "resolved": resolved_dict,
        "evidence": evidence_dict,
    }

    # Add UCN/RR summary if available
    try:
        ucn_total = sum(
            obs.get("ucn", 0) for obs in obs_dict.values() if isinstance(obs, dict)
        )
        rr_values = [
            obs.get("rr", 0) for obs in obs_dict.values() if isinstance(obs, dict) and obs.get("rr")
        ]
        avg_rr = sum(rr_values) / len(rr_values) if rr_values else 0.0
        avg_ucn = ucn_total / len(obs_dict) if obs_dict else 0.0

        data["ucn_rr_summary"] = {
            "avg_ucn": round(avg_ucn, 2),
            "avg_rr": round(avg_rr, 4),
            "curiosity_score": round(1.0 - avg_rr, 4) if avg_rr > 0 else 0.0,
            "total_traits": len(obs_dict),
        }
    except Exception:
        pass

    # Add provenance
    data["provenance"] = {
        "export_source": "snapshot_exporter",
        "export_timestamp": _iso(_now()),
        "write_protect_mode": True,  # Assume write-protect for safety
    }

    # Compute metadata
    metadata_dict = _compute_metadata(data, label=label)

    # Create timestamp and ID
    now = _now()
    timestamp = _iso(now)
    snapshot_id = _make_snapshot_id(timestamp)

    # Create Snapshot
    snapshot = Snapshot(
        id=snapshot_id,
        user_id=user_id,
        created_at=timestamp,
        version=_VERSION,
        scope=scope,
        families=included_families,
        data=data,
        metadata=metadata_dict,
    )

    # Persist snapshot
    _persist_snapshot(user_id, snapshot)

    return snapshot


def _persist_snapshot(user_id: str, snapshot: Snapshot) -> None:
    """Save snapshot to storage and update index."""
    paths = storage.ensure_dirs_for_user(user_id)
    snapshots_dir = paths["udir"] / _SNAPSHOTS_DIR
    snapshots_dir.mkdir(exist_ok=True)

    # Save full snapshot
    snapshot_filename = f"{snapshot.id}.json"
    snapshot_path = snapshots_dir / snapshot_filename
    storage.save_json(snapshot_path, snapshot.as_dict())

    # Update index
    index_path = snapshots_dir / _INDEX_FILENAME
    index = storage.load_json(index_path, default=[])
    if not isinstance(index, list):
        index = []

    # Add metadata to index
    meta = snapshot.to_meta()
    # Remove old entry if exists
    index = [item for item in index if item.get("id") != snapshot.id]
    index.insert(0, meta.as_dict())  # Most recent first

    # Keep only last 100 snapshots in index
    index = index[:100]
    storage.save_json(index_path, index)


def list_snapshots(user_id: str, limit: int = 20) -> List[SnapshotMeta]:
    """
    List snapshot metadata for user (most recent first).

    Args:
        user_id: User identifier
        limit: Max number of snapshots to return

    Returns:
        List of SnapshotMeta objects
    """
    paths = storage.ensure_dirs_for_user(user_id)
    snapshots_dir = paths["udir"] / _SNAPSHOTS_DIR
    index_path = snapshots_dir / _INDEX_FILENAME

    if not index_path.exists():
        return []

    index = storage.load_json(index_path, default=[])
    if not isinstance(index, list):
        return []

    metas: List[SnapshotMeta] = []
    for item in index[:limit]:
        if not isinstance(item, dict):
            continue

        meta = SnapshotMeta(
            id=item.get("id", ""),
            user_id=item.get("user_id", user_id),
            created_at=item.get("created_at", ""),
            scope=item.get("scope", "unknown"),
            families=item.get("families", []),
            size_bytes=item.get("size_bytes", 0),
            trait_count=item.get("trait_count", 0),
            label=item.get("label"),
        )
        metas.append(meta)

    return metas


def load_snapshot(user_id: str, snapshot_id: str) -> Optional[Snapshot]:
    """
    Load full snapshot data.

    Args:
        user_id: User identifier
        snapshot_id: Snapshot ID

    Returns:
        Snapshot object or None if not found
    """
    paths = storage.ensure_dirs_for_user(user_id)
    snapshots_dir = paths["udir"] / _SNAPSHOTS_DIR
    snapshot_path = snapshots_dir / f"{snapshot_id}.json"

    if not snapshot_path.exists():
        return None

    snapshot_data = storage.load_json(snapshot_path, default={})
    if not isinstance(snapshot_data, dict):
        return None

    return Snapshot(
        id=snapshot_data.get("snapshot_id", snapshot_id),
        user_id=snapshot_data.get("user_id", user_id),
        created_at=snapshot_data.get("created_at", ""),
        version=snapshot_data.get("version", _VERSION),
        scope=snapshot_data.get("scope", "unknown"),
        families=snapshot_data.get("families", []),
        data=snapshot_data.get("data", {}),
        metadata=snapshot_data.get("metadata", {}),
    )


def delete_snapshot(user_id: str, snapshot_id: str) -> bool:
    """
    Delete snapshot file and remove from index.

    Args:
        user_id: User identifier
        snapshot_id: Snapshot ID

    Returns:
        True if deleted, False if not found
    """
    paths = storage.ensure_dirs_for_user(user_id)
    snapshots_dir = paths["udir"] / _SNAPSHOTS_DIR
    snapshot_path = snapshots_dir / f"{snapshot_id}.json"

    if not snapshot_path.exists():
        return False

    # Delete file
    snapshot_path.unlink()

    # Update index
    index_path = snapshots_dir / _INDEX_FILENAME
    if index_path.exists():
        index = storage.load_json(index_path, default=[])
        if isinstance(index, list):
            index = [item for item in index if item.get("id") != snapshot_id]
            storage.save_json(index_path, index)

    return True


__all__ = [
    "Snapshot",
    "SnapshotMeta",
    "export_snapshot",
    "list_snapshots",
    "load_snapshot",
    "delete_snapshot",
]
