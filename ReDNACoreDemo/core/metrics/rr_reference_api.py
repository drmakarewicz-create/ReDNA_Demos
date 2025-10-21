"""
RR Reference Population Debug Endpoint (Phase 10.1).

Provides observability into reference source configuration, cache status,
and runtime behavior for the pluggable RR reference population system.
"""

from typing import Dict, Any, List
import os
from datetime import datetime, timezone
from fastapi import APIRouter

from .reference_source import (
    get_reference_cdf,
    log_reference_config,
    RR_REFERENCE_SOURCE,
    RR_REFERENCE_UNIVERSE,
    RR_REFERENCE_COHORT_KEYS,
    RR_ACTUAL_MIN_SAMPLES,
    RR_ACTUAL_MAX_AGE_DAYS,
    _CDF_CACHE,
)

router = APIRouter()


@router.get("/core/rr/reference/status")
def rr_reference_status() -> Dict[str, Any]:
    """
    GET /core/rr/reference/status

    Returns comprehensive status for RR reference population system.

    **Response:**
    ```json
    {
      "config": {
        "source": "SYNTHETIC|ACTUAL",
        "universe": "combined|low|medium|high|null",
        "cohort_keys": ["age", "region"] | [],
        "actual_min_samples": 5000,
        "actual_max_age_days": 90
      },
      "cache": {
        "enabled": true,
        "ttl_seconds": 900,
        "entries": 5,
        "keys": ["PaDNA.Chronotype", "PaDNA.Height", ...]
      },
      "test_traits": [
        {
          "trait_id": "PaDNA.Chronotype",
          "cdf_source": "SYNTHETIC",
          "n_samples": 10000,
          "fallback_reason": null,
          "generated_at": "2025-10-20T20:51:00Z"
        }
      ],
      "timestamp": "2025-10-20T20:51:00Z"
    }
    ```

    **Auth:** Public (no auth required - debug endpoint)
    """
    # Build config section
    config = {
        "source": RR_REFERENCE_SOURCE,
        "universe": RR_REFERENCE_UNIVERSE if RR_REFERENCE_UNIVERSE else None,
        "cohort_keys": RR_REFERENCE_COHORT_KEYS.split(",") if RR_REFERENCE_COHORT_KEYS else [],
        "actual_min_samples": RR_ACTUAL_MIN_SAMPLES,
        "actual_max_age_days": RR_ACTUAL_MAX_AGE_DAYS,
    }

    # Build cache section
    cache_keys = list(_CDF_CACHE.keys())
    cache_info = {
        "enabled": True,
        "ttl_seconds": 900,  # 15 minutes
        "entries": len(cache_keys),
        "keys": cache_keys[:20],  # Limit to first 20 keys
    }

    # Test a few common traits to verify system is working
    test_trait_ids = [
        "PaDNA.Chronotype",
        "PaDNA.Height",
        "PaDNA.EyeDNA.IrisColor",
    ]

    test_results: List[Dict[str, Any]] = []

    for trait_id in test_trait_ids:
        try:
            cdf, fallback_reason = get_reference_cdf(trait_id, cohort_values=None)
            test_results.append({
                "trait_id": trait_id,
                "cdf_source": cdf.source,
                "n_samples": cdf.n_samples,
                "universe": cdf.universe,
                "fallback_reason": fallback_reason,
                "generated_at": cdf.generated_at,
                "status": "ok"
            })
        except Exception as e:
            test_results.append({
                "trait_id": trait_id,
                "status": "error",
                "error": str(e)
            })

    return {
        "config": config,
        "cache": cache_info,
        "test_traits": test_results,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def log_rr_reference_startup() -> None:
    """
    Log RR reference configuration at startup for visibility.

    Calls log_reference_config() from reference_source.py.
    """
    log_reference_config()
