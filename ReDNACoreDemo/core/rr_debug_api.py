"""
RR Reference Percentile Debug API

Provides detailed diagnostics for RR percentile calculations, including:
- UCN normalization path
- CDF file selection and statistics
- Exact percentile calculation
- Edge case detection (above max, below min)
"""

from typing import Optional, Dict, Any
from fastapi import APIRouter, Query
import os
import logging

from .metrics.reference_source import get_reference_cdf
from .metrics.rr_adapter import _normalize_ucn_for_reference
from . import storage

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_normalization_path(ucn_raw: Optional[float]) -> Dict[str, Any]:
    """Determine how ucn_raw would be normalized and return the path taken."""
    if ucn_raw is None:
        return {"ucn": 0.5, "path": "default (None)"}

    if 0.0 <= ucn_raw <= 1.0:
        return {"ucn": ucn_raw, "path": "passthrough (already normalized)"}

    if 1.0 < ucn_raw <= 100.0:
        return {"ucn": ucn_raw / 100.0, "path": "percent (÷100)"}

    if 100.0 < ucn_raw <= 1000.0:
        return {"ucn": ucn_raw / 1000.0, "path": "score (÷1000)"}

    # Out of range
    clamped = max(0.0, min(1.0, ucn_raw / 1000.0))
    return {"ucn": clamped, "path": f"out_of_range (clamped to {clamped:.4f})"}


def _get_cdf_stats(cdf) -> Dict[str, float]:
    """Extract statistics from a ReferenceCDF."""
    samples = cdf.samples
    n = len(samples)

    return {
        "min": samples[0],
        "median": samples[n // 2],
        "p90": samples[int(n * 0.90)] if n > 10 else samples[-1],
        "p95": samples[int(n * 0.95)] if n > 20 else samples[-1],
        "max": samples[-1],
    }


def _detect_edge_cases(ucn_norm: float, cdf) -> list:
    """Detect if UCN is outside CDF range."""
    edges = []

    if ucn_norm < cdf.samples[0]:
        edges.append("below_min")

    if ucn_norm > cdf.samples[-1]:
        edges.append("above_max")

    return edges


def _get_user_ucn(user_id: str, trait_id: str) -> Optional[float]:
    """Get current UCN for a user's trait from resolved.json."""
    try:
        resolved_path = storage._user_file(user_id, storage.RESOLVED_FILENAME)
        resolved = storage.load_json(resolved_path, default={})

        # Handle both wrapped and unwrapped formats
        if isinstance(resolved.get("resolved"), dict):
            resolved = resolved["resolved"]

        trait_data = resolved.get(trait_id, {})
        return trait_data.get("ucn")
    except Exception as e:
        logger.debug(f"Could not load user UCN: {e}")
        return None


@router.get("/core/rr/reference/debug_percentile")
async def debug_percentile(
    trait_id: str = Query(..., description="Trait ID to debug"),
    ucn: Optional[float] = Query(None, description="UCN value to test (overrides user_id)"),
    user_id: Optional[str] = Query(None, description="User ID to fetch current UCN from"),
    cohort_keys: Optional[str] = Query(None, description="Comma-separated cohort keys (e.g., 'age,region')")
) -> Dict[str, Any]:
    """
    Debug RR percentile calculation for a trait.

    Provides detailed breakdown of:
    - UCN normalization path
    - CDF file selection and statistics
    - Exact percentile calculation
    - Edge case detection

    Examples:
    - /core/rr/reference/debug_percentile?trait_id=PaDNA.Height&ucn=80.0
    - /core/rr/reference/debug_percentile?trait_id=PaDNA.Height&user_id=test_user
    """
    # Parse cohort values if provided
    cohort_values = None
    if cohort_keys is not None and isinstance(cohort_keys, str):
        cohort_values = {}
        # For now, just track keys; actual values would come from user profile
        for key in cohort_keys.split(","):
            cohort_values[key.strip()] = "unknown"

    # Determine UCN source
    ucn_raw = ucn
    user_ucn_raw = None
    user_ucn_norm = None

    if user_id and ucn is None:
        # Get UCN from user data
        user_ucn_raw = _get_user_ucn(user_id, trait_id)
        ucn_raw = user_ucn_raw
    elif user_id:
        # Both provided - show user's UCN separately
        user_ucn_raw = _get_user_ucn(user_id, trait_id)
        if user_ucn_raw is not None:
            user_norm = _get_normalization_path(user_ucn_raw)
            user_ucn_norm = user_norm["ucn"]

    # Normalize input UCN
    normalized = _get_normalization_path(ucn_raw)
    ucn_norm = normalized["ucn"]

    # Get reference CDF
    try:
        cdf, fallback_reason = get_reference_cdf(trait_id, cohort_values)

        # Calculate percentile
        percentile = cdf.percentile_for_ucn(ucn_norm)

        # Find position in samples
        import bisect
        pos = bisect.bisect_left(cdf.samples, ucn_norm)

        # Get CDF stats
        stats = _get_cdf_stats(cdf)

        # Detect edge cases
        edges = _detect_edge_cases(ucn_norm, cdf)

        # Build CDF path info
        cdf_path = f"data/reference_pop/{cdf.universe}/"
        if cdf.cohort_keys:
            cdf_path += f"{trait_id}_{'_'.join(cdf.cohort_keys)}.json"
        else:
            cdf_path += f"{trait_id}.json" if cdf.universe != "generic" else "generic.json"

        # Build response
        response = {
            "trait_id": trait_id,
            "input": {
                "ucn_raw": ucn_raw,
                "scale": "reference_percentile",
            },
            "normalized": {
                "ucn": ucn_norm,
                "path": normalized["path"],
            },
            "reference": {
                "source": cdf.source,
                "universe": cdf.universe,
                "cohort_keys": cdf.cohort_keys,
                "cohort_values": cdf.cohort_values,
                "cdf_path": cdf_path,
                "n_samples": cdf.n_samples,
                "stats": stats,
            },
            "calc": {
                "pos": pos,
                "percentile": round(percentile, 2),
            },
            "rr": round(percentile, 2),
            "notes": [],
        }

        # Add fallback info
        if fallback_reason:
            response["notes"].append(f"fallback: {fallback_reason}")
        else:
            response["notes"].append("no_fallback")

        # Add edge case warnings
        if edges:
            response["notes"].extend(edges)
            response["edge_cases"] = edges

        # Add user UCN comparison if available
        if user_ucn_raw is not None:
            response["user_context"] = {
                "user_id": user_id,
                "ucn_raw": user_ucn_raw,
                "ucn_norm": user_ucn_norm,
            }

            # If we calculated with a different UCN, show user's RR too
            if user_ucn_norm and user_ucn_norm != ucn_norm:
                user_percentile = cdf.percentile_for_ucn(user_ucn_norm)
                user_pos = bisect.bisect_left(cdf.samples, user_ucn_norm)
                response["user_context"]["rr"] = round(user_percentile, 2)
                response["user_context"]["pos"] = user_pos

        return response

    except Exception as e:
        logger.exception(f"Error debugging percentile for {trait_id}")
        return {
            "trait_id": trait_id,
            "error": str(e),
            "input": {
                "ucn_raw": ucn_raw,
                "scale": "reference_percentile",
            },
            "normalized": normalized,
        }
