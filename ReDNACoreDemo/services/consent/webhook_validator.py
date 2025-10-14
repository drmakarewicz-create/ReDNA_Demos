"""
Webhook Validator - Phase 5.C

Secure signature validation for incoming external webhooks.

Supported webhook types:
- capability_refresh: External service requests capability renewal
- consent_revocation: External service revokes consent
- audit_request: External auditor requests data export

Security:
- HMAC-SHA256 signature verification
- Timestamp validation (reject old requests)
- Replay attack prevention
- Rate limiting per webhook source

Architecture:
- Webhook signing key stored in env var WEBHOOK_SECRET
- Signature sent in X-Webhook-Signature header
- Timestamp sent in X-Webhook-Timestamp header
- Replay window: 5 minutes (configurable)
"""

import os
import hmac
import hashlib
import time
import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict, deque
from enum import Enum
from pydantic import BaseModel, Field
import json
from pathlib import Path

logger = logging.getLogger(__name__)

# Webhook configuration
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "dev-webhook-secret-change-in-production")
REPLAY_WINDOW_SECONDS = int(os.getenv("WEBHOOK_REPLAY_WINDOW", "300"))  # 5 minutes
WEBHOOK_RATE_LIMIT = int(os.getenv("WEBHOOK_RATE_LIMIT", "100"))  # per hour

# Rate limiting
_webhook_buckets: Dict[str, deque] = defaultdict(deque)


class WebhookType(str, Enum):
    """Supported webhook types."""

    CAPABILITY_REFRESH = "capability_refresh"
    CONSENT_REVOCATION = "consent_revocation"
    AUDIT_REQUEST = "audit_request"
    CAPABILITY_USED = "capability_used"
    CONSENT_GRANTED = "consent_granted"


class WebhookPayload(BaseModel):
    """Standard webhook payload."""

    webhook_type: WebhookType
    webhook_id: str = Field(..., description="Unique webhook ID (for replay detection)")
    timestamp: str = Field(..., description="ISO-8601 timestamp of webhook creation")
    source: str = Field(..., description="Source service/system")
    user_id: Optional[str] = None
    cap_id: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict, description="Webhook-specific data")


class WebhookValidationError(Exception):
    """Raised when webhook validation fails."""

    pass


def _compute_signature(payload: bytes, secret: str) -> str:
    """
    Compute HMAC-SHA256 signature for webhook payload.

    Args:
        payload: Raw webhook payload bytes
        secret: Webhook signing secret

    Returns:
        Hex-encoded signature
    """
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def _check_rate_limit(source: str) -> bool:
    """
    Check if webhook source is within rate limit.

    Args:
        source: Webhook source identifier

    Returns:
        True if within limit, False if exceeded
    """
    now = time.time()
    bucket = _webhook_buckets[source]

    # Remove old entries (older than 1 hour)
    while bucket and bucket[0] < now - 3600:
        bucket.popleft()

    # Check limit
    if len(bucket) >= WEBHOOK_RATE_LIMIT:
        return False

    # Add current request
    bucket.append(now)
    return True


def _audit_webhook(
    webhook_type: str,
    source: str,
    valid: bool,
    reason: Optional[str] = None,
    webhook_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> None:
    """
    Audit webhook validation to system audit log.

    Args:
        webhook_type: Type of webhook
        source: Source service
        valid: Whether webhook was valid
        reason: Reason for rejection (if invalid)
        webhook_id: Unique webhook ID
        user_id: Associated user ID (if applicable)
    """
    audit_dir = Path("data/audit")
    audit_dir.mkdir(parents=True, exist_ok=True)
    audit_file = audit_dir / "webhook_audit.jsonl"

    event = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "event_type": "webhook_received",
        "webhook_type": webhook_type,
        "source": source,
        "valid": valid,
        "reason": reason,
        "webhook_id": webhook_id,
        "user_id": user_id,
    }

    try:
        with open(audit_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
    except Exception as e:
        logger.error(f"Failed to audit webhook: {e}")


def validate_webhook_signature(
    payload: bytes,
    signature: str,
    timestamp: str,
    source: str = "unknown",
) -> Tuple[bool, Optional[str]]:
    """
    Validate webhook signature and timestamp.

    Args:
        payload: Raw webhook payload bytes
        signature: HMAC-SHA256 signature from X-Webhook-Signature header
        timestamp: ISO-8601 timestamp from X-Webhook-Timestamp header
        source: Source service (for rate limiting)

    Returns:
        Tuple of (valid, error_reason)
        - (True, None) if valid
        - (False, "reason") if invalid

    Raises:
        WebhookValidationError: If validation fails
    """
    # Check rate limit first
    if not _check_rate_limit(source):
        _audit_webhook(
            "unknown", source, False, "rate_limit_exceeded", None, None
        )
        return False, "rate_limit_exceeded"

    # Validate timestamp format
    try:
        webhook_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except (ValueError, AttributeError) as e:
        _audit_webhook(
            "unknown", source, False, f"invalid_timestamp: {str(e)}", None, None
        )
        return False, f"invalid_timestamp: {str(e)}"

    # Check timestamp is within replay window
    now = datetime.utcnow()
    age = (now - webhook_time.replace(tzinfo=None)).total_seconds()

    if age > REPLAY_WINDOW_SECONDS:
        _audit_webhook(
            "unknown",
            source,
            False,
            f"timestamp_too_old: {age}s > {REPLAY_WINDOW_SECONDS}s",
            None,
            None,
        )
        return False, f"timestamp_too_old: {age}s"

    if age < -60:  # Allow 1 minute clock skew
        _audit_webhook(
            "unknown",
            source,
            False,
            f"timestamp_in_future: {age}s",
            None,
            None,
        )
        return False, "timestamp_in_future"

    # Compute expected signature
    expected_signature = _compute_signature(payload, WEBHOOK_SECRET)

    # Constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(signature, expected_signature):
        _audit_webhook(
            "unknown", source, False, "signature_mismatch", None, None
        )
        return False, "signature_mismatch"

    # All checks passed
    return True, None


def validate_webhook(
    payload: bytes,
    signature: str,
    timestamp: str,
    source: str = "unknown",
) -> WebhookPayload:
    """
    Validate webhook and parse payload.

    Args:
        payload: Raw webhook payload bytes
        signature: HMAC-SHA256 signature
        timestamp: ISO-8601 timestamp
        source: Source service

    Returns:
        Parsed WebhookPayload

    Raises:
        WebhookValidationError: If validation fails
    """
    # Validate signature
    valid, reason = validate_webhook_signature(payload, signature, timestamp, source)
    if not valid:
        raise WebhookValidationError(f"Webhook validation failed: {reason}")

    # Parse payload
    try:
        payload_dict = json.loads(payload)
        webhook = WebhookPayload(**payload_dict)
    except (json.JSONDecodeError, ValueError) as e:
        _audit_webhook(
            "unknown", source, False, f"invalid_payload: {str(e)}", None, None
        )
        raise WebhookValidationError(f"Invalid payload: {str(e)}")

    # Audit successful validation
    _audit_webhook(
        webhook.webhook_type,
        source,
        True,
        None,
        webhook.webhook_id,
        webhook.user_id,
    )

    logger.info(
        f"Webhook validated: type={webhook.webhook_type}, "
        f"source={source}, id={webhook.webhook_id}"
    )

    return webhook


def sign_webhook(payload: Dict[str, Any], secret: Optional[str] = None) -> Dict[str, str]:
    """
    Sign a webhook payload for outgoing webhooks.

    Args:
        payload: Webhook payload dictionary
        secret: Signing secret (defaults to WEBHOOK_SECRET)

    Returns:
        Dictionary with signature and timestamp headers
    """
    if secret is None:
        secret = WEBHOOK_SECRET

    # Add timestamp
    timestamp = datetime.utcnow().isoformat() + "Z"

    # Serialize payload
    payload_bytes = json.dumps(payload, sort_keys=True).encode()

    # Compute signature
    signature = _compute_signature(payload_bytes, secret)

    return {
        "X-Webhook-Signature": signature,
        "X-Webhook-Timestamp": timestamp,
    }


# Replay attack prevention
_seen_webhook_ids: deque = deque(maxlen=10000)  # Track last 10k webhook IDs


def is_replay(webhook_id: str) -> bool:
    """
    Check if webhook ID has been seen before (replay attack detection).

    Args:
        webhook_id: Unique webhook ID

    Returns:
        True if this is a replay, False otherwise
    """
    if webhook_id in _seen_webhook_ids:
        logger.warning(f"Replay attack detected: webhook_id={webhook_id}")
        return True

    _seen_webhook_ids.append(webhook_id)
    return False


def validate_and_process_webhook(
    payload: bytes,
    signature: str,
    timestamp: str,
    source: str = "unknown",
) -> WebhookPayload:
    """
    Validate webhook with full security checks including replay detection.

    Args:
        payload: Raw webhook payload bytes
        signature: HMAC-SHA256 signature
        timestamp: ISO-8601 timestamp
        source: Source service

    Returns:
        Parsed and validated WebhookPayload

    Raises:
        WebhookValidationError: If any validation check fails
    """
    # Standard validation
    webhook = validate_webhook(payload, signature, timestamp, source)

    # Replay detection
    if is_replay(webhook.webhook_id):
        _audit_webhook(
            webhook.webhook_type,
            source,
            False,
            "replay_detected",
            webhook.webhook_id,
            webhook.user_id,
        )
        raise WebhookValidationError("Replay attack detected: webhook_id already seen")

    return webhook


__all__ = [
    "WebhookType",
    "WebhookPayload",
    "WebhookValidationError",
    "validate_webhook",
    "validate_webhook_signature",
    "validate_and_process_webhook",
    "sign_webhook",
    "is_replay",
]
