"""
RR (Relational Reasoning) scoring client.

This module interfaces with the RR service to compute UCN scores
for resolved traits. Includes fallback to priors if RR is unavailable.
"""
from __future__ import annotations
from typing import List, Dict, Any
import os
import requests
from requests.exceptions import RequestException


RR_URL = os.getenv("RR_URL", "http://127.0.0.1:8011/ucn/score")


def score_ucn(user_id: str, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Score UCN for a batch of trait evidence.

    Args:
        user_id: User identifier
        items: List of trait evidence dicts with:
            - trait_id: Canonical trait ID
            - value: Trait value dict (enum/number/text)
            - ucn_prior: Prior confidence (0..1)
            - source: Evidence source

    Returns:
        List of scored traits with:
            - trait_id: Canonical trait ID
            - ucn: Computed UCN score (0..1)

    Raises:
        RequestException: If RR service is unavailable or returns error
    """
    timeout = float(os.getenv("RR_TIMEOUT", "2.5"))

    try:
        response = requests.post(
            RR_URL,
            json={"user_id": user_id, "items": items},
            timeout=timeout
        )
        response.raise_for_status()
        data = response.json()

        # Validate and normalize output shape
        out = []
        for row in data:
            if "trait_id" not in row:
                continue
            out.append({
                "trait_id": row["trait_id"],
                "ucn": float(row.get("ucn", 0.2))
            })
        return out

    except RequestException as e:
        # Re-raise so resolver can log and fallback
        raise RequestException(f"RR service error: {e}") from e


def score_ucn_safe(user_id: str, items: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], bool]:
    """
    Safe wrapper that returns fallback scores if RR fails.

    Args:
        user_id: User identifier
        items: List of trait evidence (see score_ucn)

    Returns:
        Tuple of (scores, rr_ok):
            - scores: List of trait scores
            - rr_ok: True if RR succeeded, False if fallback used
    """
    try:
        scores = score_ucn(user_id, items)
        return scores, True
    except Exception:
        # Fallback to priors
        scores = [
            {
                "trait_id": item["trait_id"],
                "ucn": float(item.get("ucn_prior", 0.2))
            }
            for item in items
        ]
        return scores, False
