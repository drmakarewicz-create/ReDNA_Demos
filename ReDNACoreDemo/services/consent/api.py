"""
Consent Service - FastAPI Application

This service is the exclusive authority for capability issuance and revocation.
NO other service should mint capabilities directly.

Key responsibilities:
- Issue capability JWTs upon request (from PermCoach or user)
- Revoke capabilities
- Maintain append-only consent ledger
- Provide capability summaries for Privacy Dashboard

Default deny: All requests denied unless valid capability presented.
"""

import os
import time
from collections import defaultdict, deque
from typing import List, Optional, Deque, Dict

from fastapi import FastAPI, HTTPException, Query, Body, Request
from fastapi.middleware.cors import CORSMiddleware
import logging
from datetime import datetime
import uuid

from .models import (
    CapabilityRequest,
    CapabilityResponse,
    CapabilitySummary,
    RevocationRequest,
    LedgerEvent,
    LedgerEventType,
    CapabilityToken,
    DataPolicy,
)
from .storage import ConsentStorage
from .jwt_utils import sign_capability, compute_expiration, parse_ttl_to_seconds

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Consent Service",
    description="Capability issuance, revocation, and consent ledger management",
    version="1.0.0"
)

# CORS middleware (allow DevX and other local services)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3100",  # DevX frontend
        "http://localhost:3001",  # React HC
        "http://127.0.0.1:3100",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize storage
storage = ConsentStorage()

# Naive in-memory rate limiting (per-IP within window)
RATE_LIMIT_MAX_REQUESTS = int(os.getenv("CONSENT_RATE_LIMIT_MAX_REQUESTS", "60"))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("CONSENT_RATE_LIMIT_WINDOW_SECONDS", "60"))
_rate_limit_buckets: Dict[str, Deque[float]] = defaultdict(deque)


def enforce_rate_limit(request: Request) -> None:
    """
    Enforce a simple per-IP rate limit for sensitive consent operations.
    """
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW_SECONDS

    bucket = _rate_limit_buckets[client_ip]
    while bucket and bucket[0] < window_start:
        bucket.popleft()

    if len(bucket) >= RATE_LIMIT_MAX_REQUESTS:
        logger.warning(f"Rate limit exceeded for Consent Service IP={client_ip}")
        raise HTTPException(status_code=429, detail="Too many requests. Please retry shortly.")

    bucket.append(now)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "consent-service",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }


@app.post("/consent/grant", response_model=CapabilityResponse)
async def grant_capability(capability_request: CapabilityRequest, request: Request):
    """
    Grant a new capability token.

    This is the ONLY way to obtain a capability. All requests should route
    through Permission Coach, which calls this endpoint.
    """
    try:
        enforce_rate_limit(request)
        logger.info(
            f"Capability grant request: user={capability_request.user_id}, "
            f"grantee={capability_request.grantee_id}, purpose={capability_request.purpose}"
        )

        cap_id = str(uuid.uuid4())
        issued_at = int(datetime.utcnow().timestamp())
        exp = compute_expiration(capability_request.suggested_ttl)

        audit_event = storage.create_ledger_event(
            event_type=LedgerEventType.GRANT,
            user_id=capability_request.user_id,
            cap_id=cap_id,
            grantee_id=capability_request.grantee_id,
            purpose=capability_request.purpose,
            scopes=capability_request.scopes,
            ttl=capability_request.suggested_ttl,
        )

        data_policy = DataPolicy(
            export=capability_request.export_allowed,
            aggregate_only=capability_request.aggregate_only,
            remote_access=False,
        )

        capability = CapabilityToken(
            cap_id=cap_id,
            user_id=capability_request.user_id,
            grantee_id=capability_request.grantee_id,
            purpose=capability_request.purpose,
            scopes=capability_request.scopes,
            ttl=capability_request.suggested_ttl,
            reuse_limit=capability_request.reuse_limit,
            data_policy=data_policy,
            issued_at=issued_at,
            exp=exp,
            audit_id=audit_event.event_id,
            use_count=0,
            revoked=False,
        )

        storage.save_capability(capability)

        jwt_payload = {
            "cap_id": cap_id,
            "user_id": capability_request.user_id,
            "grantee_id": capability_request.grantee_id,
            "purpose": capability_request.purpose,
            "scopes": capability_request.scopes,
            "ttl": capability_request.suggested_ttl,
            "reuse_limit": capability_request.reuse_limit,
            "data_policy": data_policy.model_dump(),
            "iat": issued_at,
            "exp": exp,
            "audit_id": audit_event.event_id,
        }

        jwt_token = sign_capability(jwt_payload)

        logger.info(f"Capability granted: cap_id={cap_id}, jwt_signed=True")

        return CapabilityResponse(
            cap_id=cap_id,
            jwt=jwt_token,
            issued_at=datetime.fromtimestamp(issued_at).isoformat() + "Z",
            expires_at=datetime.fromtimestamp(exp).isoformat() + "Z",
            scopes=capability_request.scopes,
            purpose=capability_request.purpose,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to grant capability: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to grant capability: {str(e)}")


@app.post("/consent/revoke")
async def revoke_capability(revoke_request: RevocationRequest, request: Request):
    """
    Revoke a capability.

    Once revoked, the capability JWT becomes invalid and will be rejected
    by the Policy Engine.
    """
    try:
        enforce_rate_limit(request)
        logger.info(f"Revocation request: cap_id={revoke_request.cap_id}, reason={revoke_request.reason}")

        capability = storage.get_capability(revoke_request.cap_id)

        if not capability:
            raise HTTPException(status_code=404, detail=f"Capability not found: {revoke_request.cap_id}")

        if capability.revoked:
            raise HTTPException(status_code=400, detail=f"Capability already revoked: {revoke_request.cap_id}")

        capability.revoked = True
        storage.save_capability(capability)

        storage.create_ledger_event(
            event_type=LedgerEventType.REVOKE,
            user_id=capability.user_id,
            cap_id=revoke_request.cap_id,
            grantee_id=capability.grantee_id,
            reason=revoke_request.reason,
        )

        logger.info(f"Capability revoked: cap_id={revoke_request.cap_id}")

        return {
            "status": "revoked",
            "cap_id": revoke_request.cap_id,
            "reason": revoke_request.reason,
            "revoked_at": datetime.utcnow().isoformat() + "Z",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to revoke capability: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to revoke capability: {str(e)}")


@app.get("/consent/capabilities", response_model=List[CapabilitySummary])
async def list_capabilities(
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    grantee_id: Optional[str] = Query(None, description="Filter by grantee ID"),
):
    """
    List active capabilities.

    Args:
        user_id: Optional user ID filter
        grantee_id: Optional grantee ID filter

    Returns:
        List of capability summaries
    """
    try:
        capabilities = storage.list_capabilities(user_id=user_id, grantee_id=grantee_id)

        summaries = []
        for cap in capabilities:
            summary = CapabilitySummary(
                cap_id=cap.cap_id,
                grantee_id=cap.grantee_id,
                purpose=cap.purpose,
                scopes=cap.scopes,
                issued_at=datetime.fromtimestamp(cap.issued_at).isoformat() + "Z",
                expires_at=datetime.fromtimestamp(cap.exp).isoformat() + "Z",
                ttl=cap.ttl,
                use_count=cap.use_count,
                reuse_limit=cap.reuse_limit,
                revoked=cap.revoked,
                export_allowed=cap.data_policy.export,
            )
            summaries.append(summary)

        logger.debug(f"Listed {len(summaries)} capabilities (user={user_id}, grantee={grantee_id})")
        return summaries

    except Exception as e:
        logger.error(f"Failed to list capabilities: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list capabilities: {str(e)}")


@app.get("/consent/ledger", response_model=List[LedgerEvent])
async def get_ledger(
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    cap_id: Optional[str] = Query(None, description="Filter by capability ID"),
    event_type: Optional[LedgerEventType] = Query(None, description="Filter by event type"),
):
    """
    Get consent ledger events (append-only log).

    Args:
        user_id: Optional user ID filter
        cap_id: Optional capability ID filter
        event_type: Optional event type filter

    Returns:
        List of ledger events
    """
    try:
        events = storage.read_ledger(user_id=user_id, cap_id=cap_id, event_type=event_type)
        logger.debug(f"Retrieved {len(events)} ledger events")
        return events

    except Exception as e:
        logger.error(f"Failed to read ledger: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to read ledger: {str(e)}")


@app.post("/consent/use")
async def log_capability_use(
    cap_id: str = Body(..., embed=True),
    scope_used: str = Body(..., embed=True),
):
    """
    Log a capability use event.

    Called by the Policy Engine whenever a capability is successfully used.

    Args:
        cap_id: Capability ID
        scope_used: Scope that was exercised (e.g., "read:SkillDNA")

    Returns:
        Success confirmation
    """
    try:
        # Load capability
        capability = storage.get_capability(cap_id)

        if not capability:
            raise HTTPException(status_code=404, detail=f"Capability not found: {cap_id}")

        # Increment use count
        capability.use_count += 1
        storage.save_capability(capability)

        # Log use event
        storage.create_ledger_event(
            event_type=LedgerEventType.USE,
            user_id=capability.user_id,
            cap_id=cap_id,
            grantee_id=capability.grantee_id,
            metadata={"scope_used": scope_used, "use_count": capability.use_count},
        )

        logger.info(f"Capability use logged: cap_id={cap_id}, scope={scope_used}, use_count={capability.use_count}")

        # Check if reuse limit exceeded
        if capability.reuse_limit and capability.use_count >= capability.reuse_limit:
            logger.warning(f"Capability {cap_id} has reached reuse limit ({capability.reuse_limit})")
            return {
                "status": "use_logged",
                "cap_id": cap_id,
                "use_count": capability.use_count,
                "warning": "Reuse limit reached"
            }

        return {
            "status": "use_logged",
            "cap_id": cap_id,
            "use_count": capability.use_count,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to log capability use: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to log capability use: {str(e)}")
