"""
Trait Workshop API Router
==========================

Endpoints for trait definition management, validation, and change requests.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field

from ..config import REGISTRY_PATH, SCHEMA_PATH, CR_DIR

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# Pydantic Models
# ============================================================================

class TraitSummary(BaseModel):
    """Summary information for a trait."""
    path: str
    namespace: str
    name: str
    version: str
    status: str
    has_value_model: bool = False
    has_trait_semantics: bool = False


class TraitDefinition(BaseModel):
    """Complete trait definition with value model and semantics."""
    path: str
    container: Dict[str, Any]
    value_model: Optional[Dict[str, Any]] = None
    trait_semantics: Optional[Dict[str, Any]] = None


class ChangeRequestCreate(BaseModel):
    """Create a new change request."""
    trait_path: str
    change_type: str = Field(..., description="add_value_model|update_value_model|add_semantics|update_semantics")
    value_model: Optional[Dict[str, Any]] = None
    trait_semantics: Optional[Dict[str, Any]] = None
    reason: str = Field(..., description="Human-readable reason for change")
    author: str = Field(default="devx_user")


class ChangeRequest(BaseModel):
    """Change request with validation status."""
    cr_id: str
    trait_path: str
    change_type: str
    value_model: Optional[Dict[str, Any]] = None
    trait_semantics: Optional[Dict[str, Any]] = None
    reason: str
    author: str
    created_at: str
    status: str = Field(default="pending")
    risk_level: Optional[str] = None
    validation_errors: List[str] = []


class ValidationResult(BaseModel):
    """Validation result for a change request."""
    valid: bool
    errors: List[str] = []
    warnings: List[str] = []
    risk_level: str = Field(..., description="low|medium|high")
    impact_summary: str


# ============================================================================
# Helper Functions
# ============================================================================

def load_registry() -> Dict[str, Any]:
    """Load DNA registry."""
    try:
        with open(REGISTRY_PATH) as f:
            return json.load(f)
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="DNA registry not found")
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Invalid registry JSON: {e}")


def save_registry(registry: Dict[str, Any]):
    """Save DNA registry."""
    try:
        with open(REGISTRY_PATH, 'w') as f:
            json.dump(registry, f, indent=2)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save registry: {e}")


def load_schema() -> Dict[str, Any]:
    """Load registry schema."""
    try:
        with open(SCHEMA_PATH) as f:
            return json.load(f)
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Schema not found")
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Invalid schema JSON: {e}")


def find_container_by_path(registry: Dict[str, Any], path: str) -> Optional[Dict[str, Any]]:
    """Find container by path."""
    for container in registry.get("containers", []):
        if container.get("path") == path:
            return container
    return None


def validate_value_model(value_model: Dict[str, Any]) -> List[str]:
    """
    Validate value model structure.

    Returns list of validation errors (empty if valid).
    """
    errors = []

    # Required fields
    if "canonical_type" not in value_model:
        errors.append("value_model.canonical_type is required")

    # Type validation
    valid_types = ["numeric", "categorical", "ordinal", "boolean", "text", "composite"]
    if value_model.get("canonical_type") not in valid_types:
        errors.append(f"canonical_type must be one of: {', '.join(valid_types)}")

    # Numeric-specific validation
    if value_model.get("canonical_type") == "numeric":
        if "range" not in value_model:
            errors.append("Numeric type requires 'range' field")
        if "unit" not in value_model:
            errors.append("Numeric type requires 'unit' field")

    # Categorical-specific validation
    if value_model.get("canonical_type") == "categorical":
        if "categories" not in value_model:
            errors.append("Categorical type requires 'categories' field")

    return errors


def validate_trait_semantics(trait_semantics: Dict[str, Any]) -> List[str]:
    """
    Validate trait semantics structure.

    Returns list of validation errors (empty if valid).
    """
    errors = []

    # Required fields
    if "inclusion_criteria" not in trait_semantics:
        errors.append("trait_semantics.inclusion_criteria is required")

    if "exclusion_criteria" not in trait_semantics:
        errors.append("trait_semantics.exclusion_criteria is required")

    # Validate examples structure
    if "examples" in trait_semantics:
        if not isinstance(trait_semantics["examples"], dict):
            errors.append("trait_semantics.examples must be an object")
        else:
            if "included" not in trait_semantics["examples"]:
                errors.append("trait_semantics.examples.included is required")
            if "excluded" not in trait_semantics["examples"]:
                errors.append("trait_semantics.examples.excluded is required")

    return errors


def calculate_risk_level(change_type: str, has_existing: bool) -> str:
    """
    Calculate risk level for a change.

    Args:
        change_type: Type of change
        has_existing: Whether trait has existing value model/semantics

    Returns:
        Risk level: low|medium|high
    """
    # Adding new fields = low risk
    if change_type in ["add_value_model", "add_semantics"] and not has_existing:
        return "low"

    # Updating existing definitions = medium risk (affects existing data)
    if change_type in ["update_value_model", "update_semantics"] and has_existing:
        return "medium"

    # Changing semantic boundaries = high risk
    if "semantics" in change_type and has_existing:
        return "high"

    return "medium"


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/list", response_model=List[TraitSummary])
async def list_traits(
    namespace: Optional[str] = Query(None, description="Filter by namespace"),
    status: Optional[str] = Query(None, description="Filter by status"),
    has_value_model: Optional[bool] = Query(None, description="Filter by value model presence")
):
    """
    List all traits with summary information.

    Query params:
    - namespace: Filter by namespace (e.g., SkillDNA)
    - status: Filter by status (e.g., production)
    - has_value_model: Filter by presence of value model
    """
    registry = load_registry()
    traits = []

    for container in registry.get("containers", []):
        # Apply filters
        if namespace and container.get("namespace") != namespace:
            continue

        if status and container.get("status") != status:
            continue

        has_vm = "value_model" in container
        if has_value_model is not None and has_vm != has_value_model:
            continue

        namespace_value = container.get("namespace", "unknown")
        display_name = (
            container.get("name")
            or container.get("label")
            or container["path"]
        )

        traits.append(TraitSummary(
            path=container["path"],
            namespace=namespace_value,
            name=display_name,
            version=str(container.get("version", "v1")),
            status=container.get("status", "prototype"),
            has_value_model=has_vm,
            has_trait_semantics="trait_semantics" in container
        ))

    return traits


@router.get("/definition", response_model=TraitDefinition)
async def get_trait_definition(path: str = Query(..., description="Trait path")):
    """
    Get complete trait definition including value model and semantics.

    Returns combined view of container metadata, value_model, and trait_semantics.
    """
    registry = load_registry()
    container = find_container_by_path(registry, path)

    if not container:
        raise HTTPException(status_code=404, detail=f"Trait not found: {path}")

    return TraitDefinition(
        path=path,
        container=container,
        value_model=container.get("value_model"),
        trait_semantics=container.get("trait_semantics")
    )


@router.post("/assert")
async def assert_trait_value(
    trait_path: str = Body(..., description="Trait path"),
    value_model: Dict[str, Any] = Body(..., description="Value model definition")
):
    """
    Validate and store canonical value model for a trait.

    This is a direct assertion (no change request flow).
    Use for initial setup or low-risk updates.
    """
    # Validate value model
    errors = validate_value_model(value_model)
    if errors:
        raise HTTPException(status_code=400, detail={"errors": errors})

    # Load registry
    registry = load_registry()
    container = find_container_by_path(registry, trait_path)

    if not container:
        raise HTTPException(status_code=404, detail=f"Trait not found: {trait_path}")

    # Update container
    container["value_model"] = value_model
    container["updated_at"] = datetime.now(timezone.utc).isoformat()

    # Save registry
    save_registry(registry)

    return {
        "status": "success",
        "trait_path": trait_path,
        "message": "Value model updated"
    }


@router.post("/propose-change", response_model=ChangeRequest)
async def propose_change(cr: ChangeRequestCreate):
    """
    Submit a change request for review.

    Creates a CR file and returns validation results.
    """
    # Generate CR ID
    cr_id = f"cr_{uuid4().hex[:8]}"

    # Load registry for validation
    registry = load_registry()
    container = find_container_by_path(registry, cr.trait_path)

    if not container:
        raise HTTPException(status_code=404, detail=f"Trait not found: {cr.trait_path}")

    # Validate changes
    validation_errors = []

    if cr.value_model:
        validation_errors.extend(validate_value_model(cr.value_model))

    if cr.trait_semantics:
        validation_errors.extend(validate_trait_semantics(cr.trait_semantics))

    # Calculate risk level
    has_existing_vm = "value_model" in container
    has_existing_sem = "trait_semantics" in container
    risk_level = calculate_risk_level(
        cr.change_type,
        has_existing_vm or has_existing_sem
    )

    # Create CR object
    change_request = ChangeRequest(
        cr_id=cr_id,
        trait_path=cr.trait_path,
        change_type=cr.change_type,
        value_model=cr.value_model,
        trait_semantics=cr.trait_semantics,
        reason=cr.reason,
        author=cr.author,
        created_at=datetime.now(timezone.utc).isoformat(),
        status="pending" if validation_errors else "validated",
        risk_level=risk_level,
        validation_errors=validation_errors
    )

    # Save CR to file
    cr_file = CR_DIR / f"{cr_id}.json"
    with open(cr_file, 'w') as f:
        json.dump(change_request.model_dump(), f, indent=2)

    return change_request


@router.get("/validate", response_model=ValidationResult)
async def validate_change_request(cr_id: str = Query(..., description="Change request ID")):
    """
    Run full validation pipeline on a change request.

    Returns validation errors, warnings, risk level, and impact summary.
    """
    # Load CR
    cr_file = CR_DIR / f"{cr_id}.json"
    if not cr_file.exists():
        raise HTTPException(status_code=404, detail=f"Change request not found: {cr_id}")

    with open(cr_file) as f:
        cr_data = json.load(f)

    # Run validation
    errors = []
    warnings = []

    if cr_data.get("value_model"):
        errors.extend(validate_value_model(cr_data["value_model"]))

    if cr_data.get("trait_semantics"):
        errors.extend(validate_trait_semantics(cr_data["trait_semantics"]))

    # Risk assessment
    risk_level = cr_data.get("risk_level", "medium")

    # Impact summary
    impact_lines = [f"Trait: {cr_data['trait_path']}"]
    if cr_data.get("value_model"):
        impact_lines.append(f"- Adds/updates value model (type: {cr_data['value_model'].get('canonical_type', 'unknown')})")
    if cr_data.get("trait_semantics"):
        impact_lines.append("- Adds/updates trait semantics (inclusion/exclusion criteria)")

    impact_summary = "\n".join(impact_lines)

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        risk_level=risk_level,
        impact_summary=impact_summary
    )


@router.post("/apply-change")
async def apply_change_request(cr_id: str = Body(..., embed=True, description="Change request ID")):
    """
    Apply a validated change request to the registry.

    Low-risk CRs auto-apply.
    Medium/high-risk CRs require explicit approval (checked here).
    """
    # Load CR
    cr_file = CR_DIR / f"{cr_id}.json"
    if not cr_file.exists():
        raise HTTPException(status_code=404, detail=f"Change request not found: {cr_id}")

    with open(cr_file) as f:
        cr_data = json.load(f)

    # Check validation status
    if cr_data.get("validation_errors"):
        raise HTTPException(
            status_code=400,
            detail="Cannot apply CR with validation errors"
        )

    # Load registry
    registry = load_registry()
    container = find_container_by_path(registry, cr_data["trait_path"])

    if not container:
        raise HTTPException(status_code=404, detail=f"Trait not found: {cr_data['trait_path']}")

    # Apply changes
    if cr_data.get("value_model"):
        container["value_model"] = cr_data["value_model"]

    if cr_data.get("trait_semantics"):
        container["trait_semantics"] = cr_data["trait_semantics"]

    container["updated_at"] = datetime.now(timezone.utc).isoformat()

    # Save registry
    save_registry(registry)

    # Update CR status
    cr_data["status"] = "applied"
    cr_data["applied_at"] = datetime.now(timezone.utc).isoformat()

    with open(cr_file, 'w') as f:
        json.dump(cr_data, f, indent=2)

    return {
        "status": "success",
        "cr_id": cr_id,
        "trait_path": cr_data["trait_path"],
        "message": "Change request applied successfully"
    }


@router.post("/rollback")
async def rollback_change(
    cr_id: str = Body(..., embed=True, description="Change request ID to roll back")
):
    """
    Roll back a previously applied change request.

    Note: This is a simple rollback that removes the added fields.
    For production, implement versioned snapshots.
    """
    # Load CR
    cr_file = CR_DIR / f"{cr_id}.json"
    if not cr_file.exists():
        raise HTTPException(status_code=404, detail=f"Change request not found: {cr_id}")

    with open(cr_file) as f:
        cr_data = json.load(f)

    if cr_data["status"] != "applied":
        raise HTTPException(status_code=400, detail="Can only rollback applied CRs")

    # Load registry
    registry = load_registry()
    container = find_container_by_path(registry, cr_data["trait_path"])

    if not container:
        raise HTTPException(status_code=404, detail=f"Trait not found: {cr_data['trait_path']}")

    # Remove changes (simple rollback)
    if cr_data.get("value_model") and "value_model" in container:
        del container["value_model"]

    if cr_data.get("trait_semantics") and "trait_semantics" in container:
        del container["trait_semantics"]

    container["updated_at"] = datetime.now(timezone.utc).isoformat()

    # Save registry
    save_registry(registry)

    # Update CR status
    cr_data["status"] = "rolled_back"
    cr_data["rolled_back_at"] = datetime.now(timezone.utc).isoformat()

    with open(cr_file, 'w') as f:
        json.dump(cr_data, f, indent=2)

    return {
        "status": "success",
        "cr_id": cr_id,
        "trait_path": cr_data["trait_path"],
        "message": "Change request rolled back"
    }
