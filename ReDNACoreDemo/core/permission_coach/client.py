"""
Permission Coach Client

Helper module for coaches to request capabilities through PermCoach.

ALL coaches must use this client to obtain capabilities. Direct calls to
Consent Service are forbidden.
"""

import logging
from typing import List, Optional
import httpx

from .permcoach_service import request_capability_via_permcoach, revoke_capability_via_permcoach

logger = logging.getLogger(__name__)


async def ensure_capability(
    user_id: str,
    requester_id: str,
    purpose: str,
    scopes: List[str],
    suggested_ttl: str = "PT24H",
    reuse_limit: Optional[int] = None,
    export_allowed: bool = False,
) -> str:
    """
    Ensure a coach has a valid capability, requesting one if needed.

    This is the PRIMARY way for coaches to obtain capabilities. It will:
    1. Check if a valid capability already exists for this (user, coach, purpose)
    2. If not, request one via PermCoach (will require user approval)
    3. Return the JWT token if capability is granted

    Args:
        user_id: User whose data is being accessed
        requester_id: Coach requesting access (e.g., "career_coach")
        purpose: Purpose of request (e.g., "resume_builder")
        scopes: List of requested scopes (e.g., ["read:SkillDNA", "read:ProfDNA"])
        suggested_ttl: Suggested TTL (default 24 hours)
        reuse_limit: Optional reuse limit
        export_allowed: Whether export is needed

    Returns:
        JWT token string if capability granted

    Raises:
        PermissionDeniedError: If user denies request or capability cannot be obtained
        PermissionPendingError: If user approval is pending (async case)
    """
    logger.info(f"ensure_capability: user={user_id}, requester={requester_id}, purpose={purpose}")

    # Request capability via PermCoach
    result = await request_capability_via_permcoach(
        user_id=user_id,
        requester_id=requester_id,
        purpose=purpose,
        scopes=scopes,
        suggested_ttl=suggested_ttl,
        reuse_limit=reuse_limit,
        export_allowed=export_allowed,
        user_approval=False,  # Will prompt user for approval
    )

    status = result.get("status")

    if status == "granted":
        # Capability granted - return JWT
        jwt_token = result["capability"]["jwt"]
        logger.info(f"✅ Capability obtained: {requester_id} for {user_id}")
        return jwt_token

    elif status == "pending_approval":
        # User approval required - raise pending error
        explanation = result.get("explanation", "")
        raise PermissionPendingError(
            f"User approval required. {explanation}",
            request_data=result.get("request")
        )

    else:
        # Error or denial
        reason = result.get("reason", "Unknown error")
        raise PermissionDeniedError(f"Capability denied: {reason}")


class PermissionDeniedError(Exception):
    """Raised when capability is denied."""
    pass


class PermissionPendingError(Exception):
    """Raised when capability request is pending user approval."""

    def __init__(self, message: str, request_data: dict = None):
        super().__init__(message)
        self.request_data = request_data


async def revoke_capability(cap_id: str, reason: str = "Coach-initiated revocation"):
    """
    Revoke a capability.

    Args:
        cap_id: Capability ID to revoke
        reason: Reason for revocation

    Returns:
        Revocation result
    """
    return await revoke_capability_via_permcoach(cap_id=cap_id, reason=reason)


# Example usage pattern for coaches:
"""
# In a coach endpoint:

from ReDNACoreDemo.core.permission_coach.client import ensure_capability, PermissionDeniedError, PermissionPendingError

@app.post("/coach/career/generate-resume")
async def generate_resume(user_id: str, request: Request):
    try:
        # Obtain capability through PermCoach
        jwt_token = await ensure_capability(
            user_id=user_id,
            requester_id="career_coach",
            purpose="resume_builder",
            scopes=["read:SkillDNA", "read:ProfDNA"],
            suggested_ttl="PT24H"
        )

        # Attach capability to subsequent /use/* requests
        headers = {"Authorization": f"Bearer {jwt_token}"}

        # Now can safely call /use/* endpoints
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "http://localhost:8015/core/use/SkillDNA/read",
                headers=headers
            )
            skill_data = response.json()

        # Generate resume using skill_data
        resume = generate_resume_from_skills(skill_data)

        return {"resume": resume}

    except PermissionPendingError as e:
        # User approval required - return pending status to UI
        return {
            "status": "pending",
            "message": str(e),
            "request": e.request_data
        }

    except PermissionDeniedError as e:
        # User denied request
        raise HTTPException(status_code=403, detail=str(e))
"""
