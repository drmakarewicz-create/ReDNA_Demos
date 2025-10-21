"""
Shape Harmonizer (Phase 9) - Ingress-only payload normalization.

Normalizes incoming payloads to prevent field/namespace drift from breaking demos.
Runs in dry-run mode by default (no behavior change), then can be enabled for
ingress mutation only. Does not rewrite historical files.

Key normalizations:
- Field aliases: from|source|start → from, to|target|dest → to
- Trait namespaces: BehaviorDNA.Sleep.Chronotype → PaDNA.Chronotype
- Default filling: timestamp, provenance.source

Flags (env):
- SHAPE_HARMONIZER=on (default: off)
- SHAPE_HARMONIZER_DRYRUN=on (default: on, no mutations)
"""

from __future__ import annotations
import os
import logging
from typing import Literal, Tuple, Dict, Any, List
from datetime import datetime, timezone
from copy import deepcopy

from .aliases import get_canonical_trait_id

logger = logging.getLogger(__name__)

# ============================================================================
# KEY ALIAS TABLES (extensible)
# ============================================================================

# Edge field aliases: all map to canonical form
EDGE_FIELD_ALIASES = {
    "source": "from",
    "start": "from",
    "target": "to",
    "dest": "to",
    "destination": "to",
    "type": "edge_type",
    "relation": "edge_type",
}

# Node field aliases
NODE_FIELD_ALIASES = {
    "kind": "node_type",
    "traitId": "trait_id",
}

# Evidence field aliases (for ingest_evidence payloads)
EVIDENCE_FIELD_ALIASES = {
    "traitId": "trait_id",
}


def normalize(
    payload: dict,
    kind: Literal["evidence", "node", "edge", "graph"],
    mutate: bool = False,
    audit: bool = False,
) -> Tuple[dict, dict]:
    """
    Normalize an incoming payload to canonical field names and namespaces.

    Args:
        payload: The incoming payload dict (will NOT be mutated unless mutate=True)
        kind: Type of payload ("evidence", "node", "edge", "graph")
        mutate: If True, apply normalizations. If False, dry-run (returns proposed changes only)
        audit: If True, include detailed audit metadata in return

    Returns:
        Tuple of (normalized_payload, audit_metadata)
        - normalized_payload: The normalized dict (original if mutate=False)
        - audit_metadata: {"changed_keys": [...], "alias_hits": [...], "namespace": "..."}

    Example:
        >>> payload = {"traitId": "BehaviorDNA.Sleep.Chronotype", "value": {"enum": "morning"}}
        >>> normalized, audit = normalize(payload, "evidence", mutate=True, audit=True)
        >>> normalized["trait_id"]  # "PaDNA.Chronotype"
        >>> audit["changed_keys"]  # ["traitId→trait_id"]
        >>> audit["namespace"]  # "BehaviorDNA.Sleep.Chronotype→PaDNA.Chronotype"
    """
    # Deep copy if mutating to avoid side effects
    result = deepcopy(payload) if mutate else payload

    audit_metadata: Dict[str, Any] = {
        "changed_keys": [],
        "alias_hits": [],
        "namespace": None,
        "defaults_added": [],
    }

    # Select alias table based on kind
    if kind == "evidence":
        field_aliases = EVIDENCE_FIELD_ALIASES
    elif kind == "node":
        field_aliases = NODE_FIELD_ALIASES
    elif kind == "edge":
        field_aliases = EDGE_FIELD_ALIASES
    else:  # graph
        field_aliases = {}

    # Apply field aliases
    if mutate:
        for old_key, new_key in field_aliases.items():
            if old_key in result and new_key not in result:
                result[new_key] = result.pop(old_key)
                audit_metadata["changed_keys"].append(f"{old_key}→{new_key}")
                audit_metadata["alias_hits"].append(old_key)
    else:
        # Dry-run: record what would change
        for old_key, new_key in field_aliases.items():
            if old_key in payload and new_key not in payload:
                audit_metadata["changed_keys"].append(f"{old_key}→{new_key}")
                audit_metadata["alias_hits"].append(old_key)

    # Normalize trait namespace (evidence/node)
    if kind in ("evidence", "node"):
        # Check both "trait_id" and potential aliases like "traitId"
        source_payload = result if mutate else payload
        trait_id_value = None

        if "trait_id" in source_payload:
            trait_id_value = source_payload["trait_id"]
        elif "traitId" in source_payload:
            trait_id_value = source_payload["traitId"]

        if trait_id_value:
            canonical_trait = get_canonical_trait_id(trait_id_value)

            if canonical_trait != trait_id_value:
                if mutate:
                    # Update the canonical key (trait_id)
                    result["trait_id"] = canonical_trait
                audit_metadata["namespace"] = f"{trait_id_value}→{canonical_trait}"

    # Add default timestamp if missing (evidence payloads)
    if kind == "evidence" and mutate:
        if "timestamp" not in result and "ts" not in result:
            result["timestamp"] = datetime.now(timezone.utc).isoformat()
            audit_metadata["defaults_added"].append("timestamp")

        # Add default provenance.source if missing
        if "provenance" not in result:
            result["provenance"] = {}
        if "source" not in result.get("provenance", {}):
            result["provenance"]["source"] = "unknown"
            audit_metadata["defaults_added"].append("provenance.source")

    # For dry-run, return original payload with audit
    if not mutate:
        return payload, audit_metadata

    return result, audit_metadata


def normalize_evidence_batch(
    evidence_list: List[dict],
    mutate: bool = False,
    audit: bool = False,
) -> Tuple[List[dict], List[dict]]:
    """
    Normalize a batch of evidence items.

    Args:
        evidence_list: List of evidence dicts
        mutate: If True, apply normalizations
        audit: If True, include audit metadata

    Returns:
        Tuple of (normalized_list, audit_list)
    """
    normalized = []
    audits = []

    for item in evidence_list:
        norm_item, audit_meta = normalize(item, "evidence", mutate=mutate, audit=audit)
        normalized.append(norm_item)
        audits.append(audit_meta)

    return normalized, audits


def is_harmonizer_enabled() -> bool:
    """Check if Shape Harmonizer is enabled via env flag."""
    return os.getenv("SHAPE_HARMONIZER", "off").lower() in ("on", "true", "1")


def is_dryrun_mode() -> bool:
    """Check if Shape Harmonizer is in dry-run mode (no mutations)."""
    return os.getenv("SHAPE_HARMONIZER_DRYRUN", "on").lower() in ("on", "true", "1")


def should_mutate() -> bool:
    """
    Determine if harmonizer should mutate payloads.

    Returns True only if harmonizer is enabled AND dry-run is off.
    """
    return is_harmonizer_enabled() and not is_dryrun_mode()
