"""
Consent Service - Data Models

Defines capability tokens, ledger events, and consent data structures.
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum


class ScopeType(str, Enum):
    """Valid capability scopes."""
    READ_SKILLDNA = "read:SkillDNA"
    READ_PROFDNA = "read:ProfDNA"
    READ_PSYDNA = "read:PsyDNA"
    READ_BELIEFDNA = "read:BeliefDNA"
    READ_CHATDNA = "read:ChatDNA"
    READ_RELATIONSHIPDNA = "read:RelationshipDNA"
    READ_ALL = "read:*"

    WRITE_GOALS = "write:Goals"
    WRITE_EVIDENCE = "write:Evidence"
    WRITE_NOTES = "write:Notes"
    WRITE_ALL = "write:*"

    EXPORT = "export"
    NO_EXPORT = "no_export"
    AGGREGATE_ONLY = "aggregate_only"
    REMOTE_OK = "remote_ok"


class DataPolicy(BaseModel):
    """Data handling policy for a capability."""
    export: bool = Field(False, description="Allow data export/download")
    aggregate_only: bool = Field(False, description="Only aggregated data, no individual records")
    remote_access: bool = Field(False, description="Allow remote/non-localhost access")


class CapabilityToken(BaseModel):
    """
    Capability token (JWT payload).

    This is the core authorization artifact. Every /use/* request must present
    a valid, non-revoked capability token that covers the requested operation.
    """
    cap_id: str = Field(..., description="Unique capability ID (UUID)")
    user_id: str = Field(..., description="User whose data is being accessed")
    grantee_id: str = Field(..., description="Coach/service/client granted access")
    purpose: str = Field(..., description="Human-readable purpose (e.g., 'resume_builder')")
    scopes: List[str] = Field(..., description="List of permission scopes")
    ttl: str = Field(..., description="Time-to-live (ISO-8601 duration, e.g., 'PT24H')")
    reuse_limit: Optional[int] = Field(None, description="Max number of uses (None = unlimited)")
    data_policy: DataPolicy = Field(default_factory=DataPolicy, description="Data handling policy")

    issued_at: int = Field(..., description="Unix timestamp of issuance")
    exp: int = Field(..., description="Unix timestamp of expiration")
    audit_id: str = Field(..., description="Ledger event ID for issuance")

    # Runtime state (not in JWT, managed by Consent Service)
    use_count: int = Field(default=0, description="Number of times capability has been used")
    revoked: bool = Field(default=False, description="Whether capability has been revoked")


class CapabilityRequest(BaseModel):
    """Request to grant a new capability."""
    user_id: str
    grantee_id: str
    purpose: str
    scopes: List[str]
    suggested_ttl: str = "PT24H"  # Default 24 hours
    reuse_limit: Optional[int] = None
    export_allowed: bool = False
    aggregate_only: bool = False


class CapabilityResponse(BaseModel):
    """Response containing a capability JWT."""
    cap_id: str
    jwt: str  # Signed JWT token
    issued_at: str
    expires_at: str
    scopes: List[str]
    purpose: str


class LedgerEventType(str, Enum):
    """Types of consent ledger events."""
    GRANT = "grant"
    REVOKE = "revoke"
    USE = "use"
    DENY = "deny"
    EXPIRE = "expire"


class LedgerEvent(BaseModel):
    """
    Append-only ledger event.

    All consent-related actions are logged to the ledger for audit.
    """
    event_id: str = Field(..., description="Unique event ID (UUID)")
    timestamp: str = Field(..., description="ISO-8601 timestamp")
    event_type: LedgerEventType
    user_id: str
    cap_id: Optional[str] = None
    grantee_id: Optional[str] = None
    purpose: Optional[str] = None
    scopes: Optional[List[str]] = None
    ttl: Optional[str] = None
    reason: Optional[str] = None  # For deny/revoke events
    metadata: Optional[Dict[str, Any]] = None


class CapabilitySummary(BaseModel):
    """Summary of a capability for UI display."""
    cap_id: str
    grantee_id: str
    purpose: str
    scopes: List[str]
    issued_at: str
    expires_at: str
    ttl: str
    use_count: int
    reuse_limit: Optional[int]
    revoked: bool
    export_allowed: bool


class RevocationRequest(BaseModel):
    """Request to revoke a capability."""
    cap_id: str
    reason: Optional[str] = "User-initiated revocation"
