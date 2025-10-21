"""
RR (Readiness/Reliability) adapter for egress normalization.

Canonical semantics:
- RR is a percentile: 0-100, representing the % of reference population
  with lower UCN than this user for this trait
- Curiosity = 100 - RR (also 0-100)
- Legacy systems may store RR as 0-1000 raw scores; this adapter normalizes
  them to percentiles at API egress time
"""

from typing import Optional, Literal, Dict, Any
import os
import logging

logger = logging.getLogger(__name__)

Scale = Literal["0_100", "0_1000", "reference_percentile", None]

# Feature flags (safe defaults for demo)
RR_ADAPTER_ENABLED = os.getenv("RR_ADAPTER_ENABLED", "true").lower() == "true"
REFERENCE_POP_ENABLED = os.getenv("REFERENCE_POP_ENABLED", "true").lower() == "true"


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp value to [min_val, max_val] range."""
    return max(min_val, min(max_val, value))


def _normalize_ucn_for_reference(rr_raw: Optional[float]) -> float:
    """
    Normalize rr_raw to UCN [0,1] for reference_percentile mode.

    When rr_scale="reference_percentile", rr_raw may be:
    - Already normalized UCN (0-1) from belief graph
    - Legacy percentage (0-100) from old data
    - Legacy score (0-1000) from very old data

    This function handles all cases with guardrails.

    Args:
        rr_raw: Raw value that should represent UCN

    Returns:
        UCN value in [0.0, 1.0] range
    """
    if rr_raw is None:
        return 0.5

    # Already normalized UCN [0, 1]
    if 0.0 <= rr_raw <= 1.0:
        return rr_raw

    # Legacy percentage (0-100 scale) - divide by 100
    if 1.0 < rr_raw <= 100.0:
        return rr_raw / 100.0

    # Legacy 0-1000 score - divide by 1000
    if 100.0 < rr_raw <= 1000.0:
        return rr_raw / 1000.0

    # Out of range - clamp and warn once
    clamped = max(0.0, min(1.0, rr_raw / 1000.0))
    logger.warning(
        f"[RR] reference: unexpected rr_raw={rr_raw:.2f} outside expected ranges; "
        f"clamped to UCN={clamped:.4f}"
    )
    return clamped


def _coerce_legacy_rr_raw_to_ucn(rr_raw: Optional[float]) -> float:
    """
    Coerce legacy rr_raw values to normalized UCN [0,1] with guardrails.

    Used for non-reference modes where rr_raw comes from legacy storage.

    Handles multiple legacy formats:
    - None → 0.5 (default)
    - 0.0-1.0 → pass through (already UCN-normalized)
    - 1.0-100.0 → divide by 100 (treat as percentage)
    - 100.0-1000.0 → divide by 1000 (treat as legacy 0-1000 score)
    - Out of range → clamp to [0,1] and warn

    Args:
        rr_raw: Raw RR value in unknown scale

    Returns:
        UCN value in [0.0, 1.0] range
    """
    if rr_raw is None:
        return 0.5

    # Already normalized UCN
    if 0.0 <= rr_raw <= 1.0:
        return rr_raw

    # Percentage (0-100 scale)
    if 1.0 < rr_raw <= 100.0:
        return rr_raw / 100.0

    # Legacy 0-1000 score
    if 100.0 < rr_raw <= 1000.0:
        return rr_raw / 1000.0

    # Out of range - clamp and warn
    clamped = max(0.0, min(1.0, rr_raw / 1000.0))
    logger.warning(
        f"[RR] Unexpected rr_raw={rr_raw:.2f} outside expected ranges; "
        f"coerced to UCN={clamped:.4f}"
    )
    return clamped


def rr_to_percentile(
    rr_raw: Optional[float],
    rr_scale: Scale,
    trait_id: str,
    user_id: str,
    *,
    use_reference: bool = True,
    cohort_values: Optional[Dict[str, str]] = None
) -> Dict:
    """
    Normalize RR to canonical 0-100 percentile format.

    Args:
        rr_raw: Raw RR value (can be 0-1000, 0-100, or None)
        rr_scale: Scale indicator ("0_1000", "0_100", "reference_percentile", None)
        trait_id: Trait identifier for reference lookup
        user_id: User identifier for reference lookup
        use_reference: Whether to use reference population when scale is None/reference_percentile
        cohort_values: Optional cohort filters {"age": "25-34", "region": "NA"}

    Returns:
        {
            "rr": float,                # 0..100 percentile
            "curiosity": float,         # 0..100 (= 100 - rr)
            "rr_meta": {
                "rr_raw": rr_raw,
                "scale": str,
                "reference": {
                    "source": "SYNTHETIC|ACTUAL",
                    "universe": "combined|low|medium|high|null",
                    "cohort_keys": ["age","region"] | [],
                    "cohort_values": {"age":"25-34","region":"NA"} | {},
                    "n_samples": int,
                    "generated_at": "2025-10-20T20:51:00Z"
                },
                "fallback_reason": "insufficient_samples|stale_reference|null"
            }
        }

    Behavior:
        - If rr_scale == "0_1000": rr = clamp(rr_raw/10, 0, 100)
        - If rr_scale == "0_100":  rr = clamp(rr_raw, 0, 100)
        - Else (None or "reference_percentile" and use_reference):
             rr = get_reference_cdf(trait_id, cohort_values).percentile_for_ucn(ucn)
        - curiosity = 100 - rr
    """
    if not RR_ADAPTER_ENABLED:
        # Passthrough mode for testing
        rr = rr_raw if rr_raw is not None else 50.0
        return {
            "rr": rr,
            "curiosity": 100.0 - rr,
            "rr_meta": {
                "rr_raw": rr_raw,
                "scale": rr_scale or "unknown",
                "source": "passthrough",
                "trait_id": trait_id,
                "user_id": user_id
            }
        }

    # Determine normalized RR (0-100)
    if rr_scale == "0_1000":
        # Legacy 0-1000 scale: divide by 10
        if rr_raw is None:
            rr = 50.0  # Default fallback
        else:
            rr = clamp(rr_raw / 10.0, 0.0, 100.0)
        actual_scale = "0_1000"
        rr_meta = _build_basic_rr_meta(rr_raw, actual_scale, trait_id, user_id)

    elif rr_scale == "0_100":
        # Already 0-100, just clamp
        if rr_raw is None:
            rr = 50.0  # Default fallback
        else:
            rr = clamp(rr_raw, 0.0, 100.0)
        actual_scale = "0_100"
        rr_meta = _build_basic_rr_meta(rr_raw, actual_scale, trait_id, user_id)

    else:
        # rr_scale is None or "reference_percentile"
        if use_reference and REFERENCE_POP_ENABLED:
            # Use new pluggable reference population system (Phase 10.1)
            from .reference_source import get_reference_cdf

            # Phase 10.2: Normalize rr_raw to UCN [0,1] with scale-aware coercion
            # rr_raw may be normalized UCN (0-1), legacy percentage (0-100), or score (0-1000)
            if rr_scale == "reference_percentile":
                # Use reference-specific normalization (handles ambiguous formats)
                ucn = _normalize_ucn_for_reference(rr_raw)
            else:
                # Legacy handling: coerce rr_raw to UCN with guardrails
                ucn = _coerce_legacy_rr_raw_to_ucn(rr_raw)

            try:
                cdf, fallback_reason = get_reference_cdf(trait_id, cohort_values)
                rr = cdf.percentile_for_ucn(ucn)
                actual_scale = "reference_percentile"

                # Phase 10.2.2: Debug logging for reference percentile calculation
                import bisect
                pos = bisect.bisect_left(cdf.samples, ucn)
                logger.debug(
                    f"[RR] ref-calc trait={trait_id} ucn_raw={rr_raw:.4f} → ucn_norm={ucn:.4f} | "
                    f"cdf=({cdf.source}/{cdf.universe}) n={cdf.n_samples} | "
                    f"pos={pos} rr={rr:.2f} fallback={fallback_reason or 'none'}"
                )

                # Build enhanced rr_meta with reference lineage
                rr_meta = {
                    "rr_raw": rr_raw,
                    "scale": actual_scale,
                    "reference": {
                        "source": cdf.source,
                        "universe": cdf.universe,
                        "cohort_keys": cdf.cohort_keys,
                        "cohort_values": cdf.cohort_values,
                        "n_samples": cdf.n_samples,
                        "generated_at": cdf.generated_at,
                    }
                }

                # Add fallback reason if present
                if fallback_reason:
                    rr_meta["fallback_reason"] = fallback_reason

            except Exception as e:
                logger.warning(f"[RR Adapter] Failed to get reference CDF for {trait_id}: {e}")
                # Fallback to default
                rr = 50.0 if rr_raw is None else clamp(rr_raw, 0.0, 100.0)
                actual_scale = rr_scale or "0_100"
                rr_meta = _build_basic_rr_meta(rr_raw, actual_scale, trait_id, user_id)
                rr_meta["error"] = str(e)
        else:
            # Fallback: assume 0-100 if we have a value, else 50
            if rr_raw is None:
                rr = 50.0
            else:
                rr = clamp(rr_raw, 0.0, 100.0)
            actual_scale = rr_scale or "0_100"
            rr_meta = _build_basic_rr_meta(rr_raw, actual_scale, trait_id, user_id)

    # Compute curiosity as 100 - rr (canonical relationship)
    curiosity = 100.0 - rr

    return {
        "rr": rr,
        "curiosity": curiosity,
        "rr_meta": rr_meta
    }


def _build_basic_rr_meta(
    rr_raw: Optional[float],
    scale: str,
    trait_id: str,
    user_id: str
) -> Dict[str, Any]:
    """Build basic rr_meta for non-reference-based conversions."""
    return {
        "rr_raw": rr_raw,
        "scale": scale,
        "source": "adapter",
        "trait_id": trait_id,
        "user_id": user_id
    }
