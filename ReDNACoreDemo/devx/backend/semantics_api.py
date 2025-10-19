"""
Trait Semantics API
===================

FastAPI router powering the DevX Semantics authoring flow.

All persistence goes through change requests stored alongside the
canonical semantics registry. Low-risk document edits can be applied
directly; other changes require approval.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml
from fastapi import APIRouter, Body, HTTPException, Query, status
from jsonschema import Draft7Validator
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)

router = APIRouter()

SEMANTICS_ROOT_ENV = "REDNA_SEMANTICS_ROOT"
DEFAULT_SEMANTICS_DIR = Path(__file__).resolve().parents[2] / "core" / "ontology" / "trait_semantics"
SEMANTICS_DIR = Path(os.environ.get(SEMANTICS_ROOT_ENV, DEFAULT_SEMANTICS_DIR))
REGISTRY_PATH = SEMANTICS_DIR / "registry.yaml"
SCHEMA_PATH = SEMANTICS_DIR / "schema" / "trait_semantics.schema.json"
CHANGELOG_PATH = SEMANTICS_DIR / "CHANGELOG.md"
CR_PREFIX = "CR_"


class ChangeProposal(BaseModel):
    """Payload for proposing a semantics change."""

    path: str = Field(..., description="Trait path (e.g. BehDNA.AdaptiveRoutineIterationDNA)")
    draft: Dict[str, Any]
    notes: Optional[str] = Field(default=None, description="Author notes for reviewers")

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        if not value or value.strip() == "":
            raise ValueError("path must be a non-empty string")
        return value.strip()


class ApplyRequest(BaseModel):
    """Payload for applying a change request."""

    cr_id: str = Field(..., description="Identifier returned by propose endpoint")


def ensure_store_available() -> None:
    """Ensure the semantics store is present; raise 503 if missing."""
    missing = []
    if not REGISTRY_PATH.exists():
        missing.append(str(REGISTRY_PATH))
    if not SCHEMA_PATH.exists():
        missing.append(str(SCHEMA_PATH))
    if missing:
        message = "Trait semantics store is not available. Missing: " + ", ".join(missing)
        logger.warning(message)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=message)


def load_registry() -> Dict[str, Dict[str, Any]]:
    """Load the canonical semantics registry."""
    ensure_store_available()
    with REGISTRY_PATH.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        logger.error("registry.yaml is not a mapping. Found type: %s", type(data))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid registry format: expected top-level mapping.",
        )
    return data


def save_registry(registry: Dict[str, Dict[str, Any]]) -> None:
    """Persist the updated registry."""
    with REGISTRY_PATH.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(registry, fh, sort_keys=True, allow_unicode=False)


def safe_path_fragment(path: str) -> str:
    """Generate a filesystem-safe fragment from a trait path."""
    return "".join(ch if ch.isalnum() or ch in (".", "-", "_") else "_" for ch in path)


def build_cr_id(path: str) -> str:
    """Build a unique CR identifier."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_fragment = safe_path_fragment(path)
    return f"{CR_PREFIX}{timestamp}_{safe_fragment}"


def cr_file_path(cr_id: str) -> Path:
    """Resolve the CR file path."""
    if not cr_id.startswith(CR_PREFIX):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid change request id.")
    return SEMANTICS_DIR / f"{cr_id}.json"


@lru_cache()
def get_schema_validator() -> Draft7Validator:
    """Return (and cache) the JSON schema validator."""
    ensure_store_available()
    with SCHEMA_PATH.open("r", encoding="utf-8") as fh:
        schema = json.load(fh)
    return Draft7Validator(schema)


def validate_semantics(payload: Dict[str, Any]) -> List[str]:
    """Return validation errors for the semantics payload."""
    validator = get_schema_validator()
    errors = sorted(validator.iter_errors(payload), key=lambda err: err.path)
    formatted = []
    for err in errors:
        path_str = "/".join(str(p) for p in err.path) or "<root>"
        formatted.append(f"{path_str}: {err.message}")
    return formatted


def write_cr_document(cr_id: str, payload: Dict[str, Any]) -> None:
    """Persist a change request file."""
    document = {
        "cr_id": cr_id,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        **payload,
    }
    with cr_file_path(cr_id).open("w", encoding="utf-8") as fh:
        json.dump(document, fh, indent=2, sort_keys=True)


def read_cr_document(cr_id: str) -> Dict[str, Any]:
    """Load a change request document."""
    path = cr_file_path(cr_id)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Change request not found.")
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    return data


def append_changelog_entry(path: str, cr_id: str, applied: bool, notes: Optional[str]) -> None:
    """Append a single entry to the changelog."""
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    entry_lines = [
        f"## {timestamp}",
        f"- Path: {path}",
        f"- Change Request: {cr_id}",
        f"- Applied: {'yes' if applied else 'no'}",
    ]
    if notes:
        entry_lines.append(f"- Notes: {notes}")
    entry = "\n".join(entry_lines) + "\n\n"
    with CHANGELOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(entry)


def is_examples_extension(old: List[Any], new: List[Any]) -> bool:
    """Check whether `new` list extends `old` without modifications."""
    if not isinstance(old, list) or not isinstance(new, list):
        return False
    if len(new) < len(old):
        return False
    return old == new[: len(old)]


def is_low_risk_change(current: Dict[str, Any], proposed: Dict[str, Any]) -> bool:
    """
    Determine whether the proposed change qualifies as low-risk.

    Allowed differences:
      * definition (string)
      * scope_notes (string)
      * examples / counterexamples appended with new entries
    All other fields must match exactly.
    """
    if current is None:
        return False

    allowed_keys = {"definition", "scope_notes", "examples", "counterexamples"}
    all_keys = set(current.keys()) | set(proposed.keys())

    for key in all_keys:
        current_value = current.get(key)
        proposed_value = proposed.get(key)

        if key not in allowed_keys:
            if current_value != proposed_value:
                logger.debug("High-risk change detected on key '%s'", key)
                return False
            continue

        if key in {"definition", "scope_notes"}:
            # Always ok to edit textual fields; schema already enforces type.
            continue

        # examples / counterexamples
        if not is_examples_extension(current_value or [], proposed_value or []):
            logger.debug("Non-append change detected on '%s'", key)
            return False

    return True


def ensure_cr_valid(cr_id: str) -> Tuple[Dict[str, Any], List[str]]:
    """Load and validate a CR document."""
    doc = read_cr_document(cr_id)
    draft = doc.get("draft")
    if not isinstance(draft, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CR payload missing draft.")
    errors = validate_semantics(draft)
    return doc, errors


def get_registry_entry(path: str) -> Optional[Dict[str, Any]]:
    """Return the semantics for the provided path."""
    registry = load_registry()
    entry = registry.get(path)
    if entry is None:
        return None
    if not isinstance(entry, dict):
        logger.error("Registry entry is not an object for path '%s'", path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"registry entry for '{path}' is not an object",
        )
    return entry


@router.get("/get")
def get_semantics(path: str = Query(..., description="Trait path to fetch semantics for")) -> Dict[str, Any]:
    """Return semantics for the requested path."""
    ensure_store_available()
    registry = load_registry()
    entry = registry.get(path)
    return {"path": path, "semantics": entry}


@router.post("/propose")
def propose_change(proposal: ChangeProposal) -> Dict[str, Any]:
    """Record a change request after schema validation."""
    ensure_store_available()
    errors = validate_semantics(proposal.draft)
    if errors:
        return {
            "path": proposal.path,
            "errors": errors,
            "accepted": False,
        }

    cr_id = build_cr_id(proposal.path)
    payload = {
        "path": proposal.path,
        "draft": proposal.draft,
        "notes": proposal.notes,
    }
    write_cr_document(cr_id, payload)
    logger.info("Recorded trait semantics CR %s for path '%s'", cr_id, proposal.path)
    return {
        "path": proposal.path,
        "cr_id": cr_id,
        "accepted": True,
    }


@router.get("/validate")
def validate_change_request(cr_id: str = Query(..., description="Change request identifier")) -> Dict[str, Any]:
    """Re-run schema validation for an existing CR."""
    ensure_store_available()
    _, errors = ensure_cr_valid(cr_id)
    return {
        "cr_id": cr_id,
        "valid": len(errors) == 0,
        "errors": errors,
    }


@router.post("/apply")
def apply_change(request: ApplyRequest) -> Dict[str, Any]:
    """Attempt to apply a change request to the registry."""
    ensure_store_available()

    doc, errors = ensure_cr_valid(request.cr_id)
    if errors:
        return {
            "cr_id": request.cr_id,
            "applied": False,
            "errors": errors,
        }

    path = doc.get("path")
    draft = doc.get("draft")
    notes = doc.get("notes")
    current = get_registry_entry(path)

    if not is_low_risk_change(current, draft):
        logger.info("CR %s requires approval before applying.", request.cr_id)
        return {
            "cr_id": request.cr_id,
            "applied": False,
            "requires_approval": True,
        }

    registry = load_registry()
    registry[path] = draft
    save_registry(registry)
    append_changelog_entry(path, request.cr_id, applied=True, notes=notes)

    logger.info("Applied trait semantics CR %s for path '%s'", request.cr_id, path)
    return {
        "cr_id": request.cr_id,
        "applied": True,
        "path": path,
    }


@router.get("/schema")
def get_schema() -> Dict[str, Any]:
    """Return the trait semantics JSON schema."""
    validator = get_schema_validator()
    return validator.schema


@router.post("/seed")
def seed_semantics(path: str = Body(..., embed=True)) -> Dict[str, Any]:
    """
    Seed a minimal semantics entry for the provided trait path.

    Intended for demo environments when a trait lacks semantics.
    """
    ensure_store_available()

    trait_path = path.strip()
    if not trait_path:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Path must be provided.")

    registry = load_registry()
    if trait_path in registry:
        return {"status": "exists", "path": trait_path}

    sample_semantics = {
        "definition": f"Seeded semantics for {trait_path}. Replace with real definition.",
        "scope_notes": "Auto-seeded by DevX for demo purposes.",
        "examples": [
            {"name": "Sample positive scenario", "description": "Placeholder example for demonstrations."}
        ],
        "counterexamples": [],
        "version": "0.1.0",
        "last_reviewed": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "reviewers": ["DevX Seeder"],
    }

    validator_errors = validate_semantics(sample_semantics)
    if validator_errors:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=validator_errors)

    cr_id = build_cr_id(trait_path)
    write_cr_document(
        cr_id,
        {
            "path": trait_path,
            "draft": sample_semantics,
            "notes": "DevX seeded semantics",
        },
    )

    registry[trait_path] = sample_semantics
    save_registry(registry)
    append_changelog_entry(trait_path, cr_id, applied=True, notes="Seed semantics entry")

    return {"status": "ok", "path": trait_path, "cr_id": cr_id}


@router.get("/diagnostics")
def diagnostics() -> Dict[str, Any]:
    """Report the status of the semantics store."""
    exists = REGISTRY_PATH.exists()
    entries = 0
    if exists:
        try:
            registry = load_registry()
            entries = len(registry)
        except HTTPException:
            # load_registry already logs and raises; keep entries at zero
            registry = {}
    return {
        "store_path": str(SEMANTICS_DIR),
        "registry_path": str(REGISTRY_PATH),
        "schema_path": str(SCHEMA_PATH),
        "registry_exists": exists,
        "entry_count": entries,
    }
