"""FastAPI endpoints for Plan Composer."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

from . import plan_composer

router = APIRouter(prefix="/hc", tags=["Head Coach - Plan Composer"])


class StepResponse(BaseModel):
    number: int
    action: str
    rationale: str
    effort: str
    impact: str
    estimated_minutes: int
    coach_delegation: Optional[str] = None
    status: str


class GamePlanResponse(BaseModel):
    id: str
    user_id: str
    created_at: str
    focus_area: str
    curiosity_score: float
    goal: str
    steps: List[StepResponse]
    status: str
    metadata: Dict[str, Any]


class ComposePlanRequest(BaseModel):
    user_id: str
    focus_override: Optional[str] = None


class UpdatePlanStatusRequest(BaseModel):
    user_id: str
    plan_id: str
    status: str  # "active", "completed", "abandoned"


class UpdateStepStatusRequest(BaseModel):
    user_id: str
    plan_id: str
    step_number: int
    status: str  # "pending", "completed", "skipped"


@router.post("/compose_plan", response_model=GamePlanResponse)
async def compose_plan_endpoint(request: ComposePlanRequest):
    """
    Generate a new 3-step game plan from top curiosity delta.

    Args:
        request: ComposePlanRequest with user_id and optional focus_override

    Returns:
        GamePlanResponse with 3 steps
    """
    try:
        plan = plan_composer.compose_plan(
            user_id=request.user_id,
            focus_override=request.focus_override,
        )

        steps_response = [
            StepResponse(
                number=step.number,
                action=step.action,
                rationale=step.rationale,
                effort=step.effort,
                impact=step.impact,
                estimated_minutes=step.estimated_minutes,
                coach_delegation=step.coach_delegation,
                status=step.status,
            )
            for step in plan.steps
        ]

        return GamePlanResponse(
            id=plan.id,
            user_id=plan.user_id,
            created_at=plan.created_at,
            focus_area=plan.focus_area,
            curiosity_score=plan.curiosity_score,
            goal=plan.goal,
            steps=steps_response,
            status=plan.status,
            metadata=plan.metadata,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Plan composition failed: {exc}")


@router.get("/plan_history/{user_id}", response_model=List[GamePlanResponse])
async def get_plan_history_endpoint(user_id: str, limit: int = 10):
    """
    Retrieve plan history for user (most recent first).

    Args:
        user_id: User identifier
        limit: Max number of plans to return (default 10)

    Returns:
        List of GamePlanResponse objects
    """
    try:
        plans = plan_composer.get_plan_history(user_id=user_id, limit=limit)

        return [
            GamePlanResponse(
                id=plan.id,
                user_id=plan.user_id,
                created_at=plan.created_at,
                focus_area=plan.focus_area,
                curiosity_score=plan.curiosity_score,
                goal=plan.goal,
                steps=[
                    StepResponse(
                        number=step.number,
                        action=step.action,
                        rationale=step.rationale,
                        effort=step.effort,
                        impact=step.impact,
                        estimated_minutes=step.estimated_minutes,
                        coach_delegation=step.coach_delegation,
                        status=step.status,
                    )
                    for step in plan.steps
                ],
                status=plan.status,
                metadata=plan.metadata,
            )
            for plan in plans
        ]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load plan history: {exc}")


@router.post("/update_plan_status", response_model=GamePlanResponse)
async def update_plan_status_endpoint(request: UpdatePlanStatusRequest):
    """
    Update plan status (active, completed, abandoned).

    Args:
        request: UpdatePlanStatusRequest

    Returns:
        Updated GamePlanResponse
    """
    try:
        plan = plan_composer.update_plan_status(
            user_id=request.user_id,
            plan_id=request.plan_id,
            status=request.status,
        )

        if not plan:
            raise HTTPException(status_code=404, detail=f"Plan {request.plan_id} not found")

        return GamePlanResponse(
            id=plan.id,
            user_id=plan.user_id,
            created_at=plan.created_at,
            focus_area=plan.focus_area,
            curiosity_score=plan.curiosity_score,
            goal=plan.goal,
            steps=[
                StepResponse(
                    number=step.number,
                    action=step.action,
                    rationale=step.rationale,
                    effort=step.effort,
                    impact=step.impact,
                    estimated_minutes=step.estimated_minutes,
                    coach_delegation=step.coach_delegation,
                    status=step.status,
                )
                for step in plan.steps
            ],
            status=plan.status,
            metadata=plan.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to update plan status: {exc}")


@router.post("/update_step_status", response_model=GamePlanResponse)
async def update_step_status_endpoint(request: UpdateStepStatusRequest):
    """
    Update individual step status within a plan.

    Args:
        request: UpdateStepStatusRequest

    Returns:
        Updated GamePlanResponse
    """
    try:
        plan = plan_composer.update_step_status(
            user_id=request.user_id,
            plan_id=request.plan_id,
            step_number=request.step_number,
            status=request.status,
        )

        if not plan:
            raise HTTPException(status_code=404, detail=f"Plan {request.plan_id} not found")

        return GamePlanResponse(
            id=plan.id,
            user_id=plan.user_id,
            created_at=plan.created_at,
            focus_area=plan.focus_area,
            curiosity_score=plan.curiosity_score,
            goal=plan.goal,
            steps=[
                StepResponse(
                    number=step.number,
                    action=step.action,
                    rationale=step.rationale,
                    effort=step.effort,
                    impact=step.impact,
                    estimated_minutes=step.estimated_minutes,
                    coach_delegation=step.coach_delegation,
                    status=step.status,
                )
                for step in plan.steps
            ],
            status=plan.status,
            metadata=plan.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to update step status: {exc}")


__all__ = ["router"]
