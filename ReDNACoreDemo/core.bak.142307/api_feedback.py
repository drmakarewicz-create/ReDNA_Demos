"""
Feedback Analytics API Endpoints

Exposes feedback data and analytics to inform Head Coach planning.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from . import feedback_analytics


# Response models
class FeedbackSummaryResponse(BaseModel):
    ok: bool
    summary: Optional[Dict[str, Any]] = None
    by_persona: Optional[Dict[str, Dict[str, Any]]] = None
    days_analyzed: Optional[int] = None
    user_filter: Optional[str] = None
    persona_filter: Optional[str] = None
    error: Optional[str] = None


class TraitFeedbackResponse(BaseModel):
    ok: bool
    traits: Optional[list] = None
    high_performers: Optional[list] = None
    low_performers: Optional[list] = None
    neutral: Optional[list] = None
    total_traits_analyzed: Optional[int] = None
    min_feedback_threshold: Optional[int] = None
    error: Optional[str] = None


class PlanningWeightsResponse(BaseModel):
    ok: bool
    weights: Optional[Dict[str, float]] = None
    trait_count: Optional[int] = None
    user_id: Optional[str] = None
    error: Optional[str] = None


class ToleranceResponse(BaseModel):
    ok: bool
    user_id: Optional[str] = None
    tolerance: Optional[float] = None
    confidence: Optional[str] = None
    error: Optional[str] = None


# Create router
router = APIRouter(prefix="/feedback", tags=["feedback"])


def _get_write_protect() -> bool:
    """Get write_protect status from environment."""
    wp = os.getenv("WRITE_PROTECT", "").strip().lower()
    return wp in {"true", "1", "yes", "on"}


@router.get("/summary", response_model=FeedbackSummaryResponse)
def get_feedback_summary(
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    persona_id: Optional[str] = Query(None, description="Filter by persona ID"),
    days: int = Query(30, ge=1, le=365, description="Days to analyze"),
):
    """
    Get feedback summary statistics.

    Returns overall feedback stats and per-persona breakdown.
    """
    if not feedback_analytics.is_feedback_available():
        raise HTTPException(
            status_code=503,
            detail="Feedback system not available",
        )

    result = feedback_analytics.load_feedback_summary(
        user_id=user_id,
        persona_id=persona_id,
        days=days,
        write_protect=_get_write_protect(),
    )

    return FeedbackSummaryResponse(**result)


@router.get("/traits/{user_id}", response_model=TraitFeedbackResponse)
def get_trait_feedback_analysis(
    user_id: str,
    min_feedback: int = Query(2, ge=1, le=20, description="Minimum feedback count"),
):
    """
    Analyze feedback by trait to identify high/low performers.

    Returns traits sorted by feedback score, categorized into:
    - high_performers: score > 0.3
    - low_performers: score < -0.3
    - neutral: -0.3 <= score <= 0.3
    """
    if not feedback_analytics.is_feedback_available():
        raise HTTPException(
            status_code=503,
            detail="Feedback system not available",
        )

    result = feedback_analytics.load_trait_feedback_analysis(
        user_id=user_id,
        min_feedback_count=min_feedback,
        write_protect=_get_write_protect(),
    )

    return TraitFeedbackResponse(**result)


@router.get("/planning_weights/{user_id}", response_model=PlanningWeightsResponse)
def get_planning_weights(user_id: str):
    """
    Get trait planning weights based on feedback.

    Returns weight multipliers (0.5 to 1.5) for each trait:
    - 1.5: Consistently helpful (boost in planning)
    - 1.0: Neutral
    - 0.5: Consistently not helpful (down-weight in planning)

    Head Coach can use these weights to adjust curiosity-driven planning.
    """
    if not feedback_analytics.is_feedback_available():
        raise HTTPException(
            status_code=503,
            detail="Feedback system not available",
        )

    weights = feedback_analytics.get_planning_weights(
        user_id=user_id,
        write_protect=_get_write_protect(),
    )

    return PlanningWeightsResponse(
        ok=True,
        weights=weights,
        trait_count=len(weights),
        user_id=user_id,
    )


@router.get("/tolerance/{user_id}", response_model=ToleranceResponse)
def get_tolerance_for_nudging(
    user_id: str,
    days: int = Query(30, ge=7, le=365, description="Days to analyze"),
):
    """
    Compute ToleranceForNudging as an emergent trait.

    Returns a value between 0.0 (low tolerance) and 1.0 (high tolerance) based on:
    - Overall helpfulness rate
    - Acceptance vs dismissal ratio
    - Feedback engagement level

    This can be stored as a derived ReDNA trait.
    """
    if not feedback_analytics.is_feedback_available():
        raise HTTPException(
            status_code=503,
            detail="Feedback system not available",
        )

    tolerance = feedback_analytics.compute_tolerance_for_nudging(
        user_id=user_id,
        days=days,
        write_protect=_get_write_protect(),
    )

    if tolerance is None:
        return ToleranceResponse(
            ok=False,
            user_id=user_id,
            error="Insufficient data to compute tolerance",
        )

    # Determine confidence based on data volume
    summary = feedback_analytics.load_feedback_summary(
        user_id=user_id,
        days=days,
        write_protect=_get_write_protect(),
    )

    total_feedback = summary.get("summary", {}).get("total_feedback", 0)

    if total_feedback < 5:
        confidence = "low"
    elif total_feedback < 15:
        confidence = "medium"
    else:
        confidence = "high"

    return ToleranceResponse(
        ok=True,
        user_id=user_id,
        tolerance=tolerance,
        confidence=confidence,
    )


@router.get("/health")
def feedback_health():
    """Health check for feedback analytics system."""
    return {
        "ok": True,
        "available": feedback_analytics.is_feedback_available(),
        "write_protect": _get_write_protect(),
    }


# Export router for inclusion in main app
def create_feedback_router() -> APIRouter:
    """Create and return the feedback analytics router."""
    return router


__all__ = ["router", "create_feedback_router"]
