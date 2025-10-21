"""
Admin API endpoints for RR recomputation and system maintenance (Phase 10.2).

Provides endpoints for recomputing RR values from reference population,
replacing legacy rr_score with reference-based calculations.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from .graph.normalize_egress import normalize_trait_dict, RR_PREFER_REFERENCE_OVER_SCORE

logger = logging.getLogger(__name__)

router = APIRouter()


class RecomputeResult(BaseModel):
    """Result of RR recomputation for a single user."""
    user_id: str
    traits_processed: int
    traits_updated: int
    traits_using_reference: int
    traits_using_legacy: int
    errors: List[str]


class BatchRecomputeResult(BaseModel):
    """Result of batch RR recomputation."""
    users_processed: int
    total_traits_updated: int
    total_traits_using_reference: int
    errors: List[str]
    user_results: List[RecomputeResult]


def _get_users_dir() -> Path:
    """Get the users data directory."""
    import os
    users_dir_env = os.getenv("USERS_DIR")
    if users_dir_env:
        return Path(users_dir_env)

    # Default to data/users relative to project root
    return Path(__file__).parent.parent.parent / "data" / "users"


def _recompute_user_rr(user_id: str) -> RecomputeResult:
    """
    Recompute RR for all traits of a single user.

    Args:
        user_id: User identifier

    Returns:
        RecomputeResult with statistics
    """
    users_dir = _get_users_dir()
    user_dir = users_dir / user_id
    resolved_path = user_dir / "resolved.json"

    if not resolved_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"User {user_id} not found (no resolved.json)"
        )

    # Load resolved.json
    try:
        with open(resolved_path, 'r') as f:
            resolved = json.load(f)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load resolved.json for {user_id}: {e}"
        )

    traits_processed = 0
    traits_updated = 0
    traits_using_reference = 0
    traits_using_legacy = 0
    errors = []

    # Process each trait
    updated_resolved = {}
    for trait_id, trait_data in resolved.items():
        traits_processed += 1

        if not isinstance(trait_data, dict):
            # Skip non-dict values
            updated_resolved[trait_id] = trait_data
            continue

        try:
            # Build trait dict for normalization
            trait_dict = {
                "trait_id": trait_id,
                **trait_data
            }

            # Normalize using reference preference logic
            normalized = normalize_trait_dict(trait_dict, user_id)

            # Check if RR changed
            old_rr = trait_data.get("rr")
            new_rr = normalized.get("rr")

            if old_rr != new_rr:
                traits_updated += 1

            # Track method used
            method = normalized.get("rr_meta", {}).get("method")
            if method == "reference":
                traits_using_reference += 1
            elif method in ["legacy_score", "curiosity_inverse"]:
                traits_using_legacy += 1

            # Update trait data (remove trait_id key we added)
            normalized_data = {k: v for k, v in normalized.items() if k != "trait_id"}
            updated_resolved[trait_id] = normalized_data

        except Exception as e:
            logger.error(f"[Admin] Failed to recompute {trait_id} for {user_id}: {e}")
            errors.append(f"{trait_id}: {str(e)}")
            updated_resolved[trait_id] = trait_data  # Keep original on error

    # Write updated resolved.json
    try:
        # Backup original
        backup_path = user_dir / "resolved.json.bak"
        with open(backup_path, 'w') as f:
            json.dump(resolved, f, indent=2)

        # Write updated
        with open(resolved_path, 'w') as f:
            json.dump(updated_resolved, f, indent=2)

        logger.info(
            f"[Admin] Recomputed RR for {user_id}: "
            f"{traits_processed} processed, {traits_updated} updated, "
            f"{traits_using_reference} using reference"
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to write updated resolved.json for {user_id}: {e}"
        )

    return RecomputeResult(
        user_id=user_id,
        traits_processed=traits_processed,
        traits_updated=traits_updated,
        traits_using_reference=traits_using_reference,
        traits_using_legacy=traits_using_legacy,
        errors=errors
    )


@router.post("/core/admin/recompute_rr")
def recompute_rr_endpoint(
    user_id: str = Query(..., description="User ID to recompute RR for")
) -> RecomputeResult:
    """
    POST /core/admin/recompute_rr?user_id=<id>

    Recompute RR for all traits of a user using current reference population.

    When RR_PREFER_REFERENCE_OVER_SCORE=true:
    - Traits with UCN will use reference population
    - Legacy rr_score archived in rr_meta.legacy_rr_score
    - Method tracked in rr_meta.method

    **Auth:** Admin only (TODO: Add auth guard)

    **Response:**
    ```json
    {
      "user_id": "ai_ready_probe",
      "traits_processed": 45,
      "traits_updated": 38,
      "traits_using_reference": 30,
      "traits_using_legacy": 8,
      "errors": []
    }
    ```
    """
    logger.info(f"[Admin] Recomputing RR for user: {user_id}")
    return _recompute_user_rr(user_id)


@router.post("/core/admin/recompute_rr_all")
def recompute_rr_all_endpoint(
    limit: Optional[int] = Query(None, description="Maximum users to process (for testing)"),
    dry_run: bool = Query(False, description="Preview changes without writing")
) -> BatchRecomputeResult:
    """
    POST /core/admin/recompute_rr_all?limit=10&dry_run=true

    Batch recompute RR for all users.

    **WARNING:** This operation modifies data for all users.
    Use dry_run=true to preview changes first.

    **Auth:** Admin only (TODO: Add auth guard)

    **Response:**
    ```json
    {
      "users_processed": 10,
      "total_traits_updated": 420,
      "total_traits_using_reference": 350,
      "errors": [],
      "user_results": [...]
    }
    ```
    """
    users_dir = _get_users_dir()

    if not users_dir.exists():
        raise HTTPException(
            status_code=500,
            detail=f"Users directory not found: {users_dir}"
        )

    # Find all user directories
    user_dirs = [d for d in users_dir.iterdir() if d.is_dir() and (d / "resolved.json").exists()]

    if limit:
        user_dirs = user_dirs[:limit]

    logger.info(f"[Admin] Batch recompute RR for {len(user_dirs)} users (dry_run={dry_run})")

    users_processed = 0
    total_traits_updated = 0
    total_traits_using_reference = 0
    batch_errors = []
    user_results = []

    for user_dir in user_dirs:
        user_id = user_dir.name
        try:
            if dry_run:
                # Preview only (read but don't write)
                logger.info(f"[Admin] DRY RUN: Would recompute {user_id}")
                users_processed += 1
            else:
                result = _recompute_user_rr(user_id)
                user_results.append(result)
                users_processed += 1
                total_traits_updated += result.traits_updated
                total_traits_using_reference += result.traits_using_reference

                if result.errors:
                    batch_errors.extend([f"{user_id}: {e}" for e in result.errors])

        except Exception as e:
            logger.error(f"[Admin] Failed to recompute {user_id}: {e}")
            batch_errors.append(f"{user_id}: {str(e)}")

    logger.info(
        f"[Admin] Batch recompute complete: "
        f"{users_processed} users, {total_traits_updated} traits updated, "
        f"{total_traits_using_reference} using reference"
    )

    return BatchRecomputeResult(
        users_processed=users_processed,
        total_traits_updated=total_traits_updated,
        total_traits_using_reference=total_traits_using_reference,
        errors=batch_errors,
        user_results=user_results
    )


@router.get("/core/admin/rr_preference_status")
def rr_preference_status() -> Dict[str, Any]:
    """
    GET /core/admin/rr_preference_status

    Check current RR preference configuration.

    **Response:**
    ```json
    {
      "prefer_reference_over_score": true,
      "reference_pop_enabled": true,
      "reference_source": "SYNTHETIC",
      "impact": "Traits with UCN will use reference population instead of rr_score"
    }
    ```
    """
    from .graph.normalize_egress import REFERENCE_POP_ENABLED, REFERENCE_POP_SOURCE

    return {
        "prefer_reference_over_score": RR_PREFER_REFERENCE_OVER_SCORE,
        "reference_pop_enabled": REFERENCE_POP_ENABLED,
        "reference_source": REFERENCE_POP_SOURCE.upper() if REFERENCE_POP_SOURCE else "SYNTHETIC",
        "impact": (
            "Traits with UCN will use reference population instead of rr_score"
            if RR_PREFER_REFERENCE_OVER_SCORE and REFERENCE_POP_ENABLED
            else "Using legacy rr_score when available"
        )
    }
