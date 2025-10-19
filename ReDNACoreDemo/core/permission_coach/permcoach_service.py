"""
Permission Coach Service

The exclusive conversational and programmatic interface for permissions,
consent, and capability issuance. No other coach should talk directly
to the Consent Service — they must route requests through PermCoach.

Roles:
- Guardian: Intercepts all permission requests
- Advisor: Explains requests in human terms
- Broker: Guides user through granting/limiting/revoking
- Auditor: Reviews active capabilities, flags anomalies
"""

import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
import httpx
from datetime import datetime

# Services are at project root
import sys
_services_root = Path(__file__).resolve().parents[4] / "services"
if str(_services_root) not in sys.path:
    sys.path.insert(0, str(_services_root.parent))

from services.consent.models import CapabilityRequest, CapabilitySummary, LedgerEvent
from services.consent.storage import ConsentStorage

logger = logging.getLogger(__name__)

# Consent Service URL (read from port log file)
CONSENT_PORT_LOG = Path(__file__).parent.parent.parent.parent / "data" / "consent" / "consent_port.log"


def get_consent_service_url() -> str:
    """
    Get Consent Service URL from port log.

    Returns:
        Base URL for Consent Service (e.g., "http://127.0.0.1:8200")
    """
    try:
        if CONSENT_PORT_LOG.exists():
            with open(CONSENT_PORT_LOG, "r") as f:
                port = f.read().strip()
            return f"http://127.0.0.1:{port}"
        else:
            # Default to 8200 if log not found
            logger.warning("Consent Service port log not found, using default 8200")
            return "http://127.0.0.1:8200"
    except Exception as e:
        logger.error(f"Failed to read Consent Service port log: {e}")
        return "http://127.0.0.1:8200"


class PermissionCoach:
    """
    Permission Coach - Mediator of consent and capabilities.

    All permission requests MUST go through PermCoach, not directly to Consent Service.
    """

    def __init__(self):
        """Initialize Permission Coach."""
        self.consent_service_url = get_consent_service_url()
        self.storage = ConsentStorage()
        logger.info(f"PermissionCoach initialized, Consent Service at {self.consent_service_url}")

    async def request_capability(
        self,
        user_id: str,
        requester_id: str,
        purpose: str,
        scopes: List[str],
        suggested_ttl: str = "PT24H",
        reuse_limit: Optional[int] = None,
        export_allowed: bool = False,
        user_approval: bool = False,  # Requires explicit user approval
    ) -> Dict[str, Any]:
        """
        Request a capability on behalf of a coach or feature.

        This is the ONLY way coaches can obtain capabilities. PermCoach
        will explain the request to the user and, if approved, mint a capability.

        Args:
            user_id: User whose data is being requested
            requester_id: Coach/service requesting access
            purpose: Human-readable purpose (e.g., "resume_builder")
            scopes: List of requested scopes (e.g., ["read:SkillDNA"])
            suggested_ttl: Suggested time-to-live (ISO-8601 duration)
            reuse_limit: Optional max number of uses
            export_allowed: Whether export is requested
            user_approval: Whether user has already approved (set by UI)

        Returns:
            Dict with capability JWT if approved, or denial reason if denied
        """
        logger.info(f"Capability request from {requester_id} for user {user_id}: purpose={purpose}, scopes={scopes}")

        # Generate human-readable explanation
        explanation = self._generate_explanation(
            requester_id=requester_id,
            purpose=purpose,
            scopes=scopes,
            ttl=suggested_ttl,
            export_allowed=export_allowed,
        )

        # Assess risk
        risk_level = self._assess_risk(scopes, suggested_ttl, export_allowed)

        # If user approval not provided, return explanation for UI to present
        if not user_approval:
            return {
                "status": "pending_approval",
                "explanation": explanation,
                "risk_level": risk_level,
                "request": {
                    "user_id": user_id,
                    "requester_id": requester_id,
                    "purpose": purpose,
                    "scopes": scopes,
                    "suggested_ttl": suggested_ttl,
                    "reuse_limit": reuse_limit,
                    "export_allowed": export_allowed,
                }
            }

        # User approved - proceed to grant capability
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.consent_service_url}/consent/grant",
                    json={
                        "user_id": user_id,
                        "grantee_id": requester_id,
                        "purpose": purpose,
                        "scopes": scopes,
                        "suggested_ttl": suggested_ttl,
                        "reuse_limit": reuse_limit,
                        "export_allowed": export_allowed,
                        "aggregate_only": False,
                    },
                    timeout=10.0,
                )

                if response.status_code == 200:
                    capability_data = response.json()
                    logger.info(f"✅ Capability granted: cap_id={capability_data['cap_id']}")

                    return {
                        "status": "granted",
                        "capability": capability_data,
                        "explanation": f"Access granted. {requester_id} can now access your data for {suggested_ttl}.",
                    }
                else:
                    logger.error(f"Consent Service returned error: {response.status_code} - {response.text}")
                    return {
                        "status": "error",
                        "reason": f"Consent Service error: {response.text}",
                    }

        except Exception as e:
            logger.error(f"Failed to grant capability: {e}")
            return {
                "status": "error",
                "reason": f"Failed to contact Consent Service: {e}",
            }

    async def revoke_capability(
        self,
        cap_id: str,
        reason: str = "User-initiated revocation"
    ) -> Dict[str, Any]:
        """
        Revoke a capability.

        Args:
            cap_id: Capability ID to revoke
            reason: Reason for revocation

        Returns:
            Revocation confirmation
        """
        logger.info(f"Revocation request: cap_id={cap_id}, reason={reason}")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.consent_service_url}/consent/revoke",
                    json={"cap_id": cap_id, "reason": reason},
                    timeout=10.0,
                )

                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"✅ Capability revoked: cap_id={cap_id}")
                    return {
                        "status": "revoked",
                        "cap_id": cap_id,
                        "revoked_at": result.get("revoked_at"),
                    }
                else:
                    logger.error(f"Revocation failed: {response.status_code} - {response.text}")
                    return {
                        "status": "error",
                        "reason": f"Revocation failed: {response.text}",
                    }

        except Exception as e:
            logger.error(f"Failed to revoke capability: {e}")
            return {
                "status": "error",
                "reason": f"Failed to contact Consent Service: {e}",
            }

    async def get_user_capabilities(self, user_id: str) -> List[CapabilitySummary]:
        """
        Get all active capabilities for a user.

        Args:
            user_id: User ID

        Returns:
            List of capability summaries
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.consent_service_url}/consent/capabilities",
                    params={"user_id": user_id},
                    timeout=10.0,
                )

                if response.status_code == 200:
                    capabilities = response.json()
                    logger.debug(f"Retrieved {len(capabilities)} capabilities for user {user_id}")
                    return [CapabilitySummary(**cap) for cap in capabilities]
                else:
                    logger.error(f"Failed to get capabilities: {response.status_code}")
                    return []

        except Exception as e:
            logger.error(f"Failed to get capabilities: {e}")
            return []

    async def audit_capabilities(self, user_id: str) -> Dict[str, Any]:
        """
        Audit user's capabilities and flag anomalies.

        Checks for:
        - Expired capabilities
        - Near-expiry capabilities (< 24 hours remaining)
        - Overly broad scopes (e.g., "read:*")
        - High use counts near reuse limit
        - Export permissions

        Args:
            user_id: User ID

        Returns:
            Audit report with anomalies and recommendations
        """
        logger.info(f"Running capability audit for user {user_id}")

        capabilities = await self.get_user_capabilities(user_id)

        anomalies = []
        now = datetime.utcnow()

        for cap in capabilities:
            # Check for expiration
            if cap.revoked:
                anomalies.append({
                    "type": "revoked",
                    "severity": "low",
                    "cap_id": cap.cap_id,
                    "message": f"{cap.grantee_id} had access revoked. Consider removing from list.",
                })
                continue

            # Parse expiration
            try:
                exp_dt = datetime.fromisoformat(cap.expires_at.replace("Z", "+00:00"))
            except Exception:
                logger.warning(f"Failed to parse expires_at for {cap.cap_id}")
                continue

            # Check if expired
            if exp_dt < now:
                anomalies.append({
                    "type": "expired",
                    "severity": "medium",
                    "cap_id": cap.cap_id,
                    "message": f"{cap.grantee_id} capability expired. Should be cleaned up.",
                    "recommendation": "Revoke this capability."
                })

            # Check if near expiry (< 24 hours)
            elif (exp_dt - now).total_seconds() < 86400:
                anomalies.append({
                    "type": "near_expiry",
                    "severity": "low",
                    "cap_id": cap.cap_id,
                    "message": f"{cap.grantee_id} capability expires in {(exp_dt - now).total_seconds() // 3600:.0f} hours.",
                    "recommendation": "Extend if still needed, otherwise let it expire."
                })

            # Check for overly broad scopes
            if any(scope.endswith(":*") or scope == "*:*" for scope in cap.scopes):
                anomalies.append({
                    "type": "broad_scope",
                    "severity": "high",
                    "cap_id": cap.cap_id,
                    "message": f"⚠️ {cap.grantee_id} has broad access: {cap.scopes}. This is high risk.",
                    "recommendation": "Revoke and grant more specific scopes."
                })

            # Check for export permission
            if cap.export_allowed:
                anomalies.append({
                    "type": "export_allowed",
                    "severity": "medium",
                    "cap_id": cap.cap_id,
                    "message": f"{cap.grantee_id} can export your data.",
                    "recommendation": "Review if export is still necessary."
                })

            # Check reuse limit
            if cap.reuse_limit and cap.use_count >= cap.reuse_limit * 0.9:
                anomalies.append({
                    "type": "high_use_count",
                    "severity": "medium",
                    "cap_id": cap.cap_id,
                    "message": f"{cap.grantee_id} has used this capability {cap.use_count}/{cap.reuse_limit} times.",
                    "recommendation": "Monitor for suspicious activity."
                })

        logger.info(f"Audit complete: {len(anomalies)} anomalies found for user {user_id}")

        return {
            "user_id": user_id,
            "audit_timestamp": now.isoformat() + "Z",
            "total_capabilities": len(capabilities),
            "anomalies": anomalies,
            "summary": self._generate_audit_summary(anomalies),
        }

    def _generate_explanation(
        self,
        requester_id: str,
        purpose: str,
        scopes: List[str],
        ttl: str,
        export_allowed: bool
    ) -> str:
        """
        Generate human-readable explanation of capability request.

        Args:
            requester_id: Coach requesting access
            purpose: Purpose of request
            scopes: Requested scopes
            ttl: Time-to-live
            export_allowed: Whether export is allowed

        Returns:
            Human-readable explanation
        """
        # Parse TTL to human-readable format
        ttl_human = self._parse_ttl_to_human(ttl)

        # Extract operations and namespaces from scopes
        read_namespaces = [s.split(":")[1] for s in scopes if s.startswith("read:")]
        write_namespaces = [s.split(":")[1] for s in scopes if s.startswith("write:")]

        explanation_parts = [
            f"{requester_id} is requesting access for: {purpose}.",
            "",
            "**What they want:**"
        ]

        if read_namespaces:
            explanation_parts.append(f"- **Read** access to: {', '.join(read_namespaces)}")

        if write_namespaces:
            explanation_parts.append(f"- **Write** access to: {', '.join(write_namespaces)}")

        if export_allowed:
            explanation_parts.append(f"- **Export** permission (can download your data)")

        explanation_parts.extend([
            "",
            f"**Duration:** {ttl_human}",
            "",
            "**What this means:** This access is temporary and specific to the stated purpose. You can revoke it at any time."
        ])

        return "\n".join(explanation_parts)

    def _assess_risk(self, scopes: List[str], ttl: str, export_allowed: bool) -> str:
        """
        Assess risk level of capability request.

        Args:
            scopes: Requested scopes
            ttl: Time-to-live
            export_allowed: Whether export is allowed

        Returns:
            Risk level: "low", "medium", "high"
        """
        # High risk if broad scopes or export
        if any(scope.endswith(":*") or scope == "*:*" for scope in scopes):
            return "high"

        if export_allowed:
            return "medium"

        # Medium risk if write access
        if any(scope.startswith("write:") for scope in scopes):
            return "medium"

        # Medium risk if long duration (> 7 days)
        if "P" in ttl and any(char.isdigit() and int(char) > 7 for char in ttl if char.isdigit()):
            return "medium"

        # Otherwise low risk
        return "low"

    def _parse_ttl_to_human(self, ttl: str) -> str:
        """
        Parse ISO-8601 duration to human-readable format.

        Args:
            ttl: ISO-8601 duration (e.g., "PT24H", "P7D")

        Returns:
            Human-readable string (e.g., "24 hours", "7 days")
        """
        if "PT" in ttl:
            if "H" in ttl:
                hours = ttl.split("PT")[1].split("H")[0]
                return f"{hours} hours"
            elif "M" in ttl:
                minutes = ttl.split("PT")[1].split("M")[0]
                return f"{minutes} minutes"
        elif "P" in ttl:
            if "D" in ttl:
                days = ttl.split("P")[1].split("D")[0]
                return f"{days} days"
            elif "W" in ttl:
                weeks = ttl.split("P")[1].split("W")[0]
                return f"{weeks} weeks"

        return ttl  # Fallback to raw TTL

    def _generate_audit_summary(self, anomalies: List[Dict[str, Any]]) -> str:
        """
        Generate summary of audit findings.

        Args:
            anomalies: List of anomalies found

        Returns:
            Human-readable summary
        """
        if not anomalies:
            return "✅ No anomalies found. Your permissions look healthy."

        high_severity = [a for a in anomalies if a.get("severity") == "high"]
        medium_severity = [a for a in anomalies if a.get("severity") == "medium"]
        low_severity = [a for a in anomalies if a.get("severity") == "low"]

        summary_parts = []

        if high_severity:
            summary_parts.append(f"⚠️ **{len(high_severity)} high-risk anomalies** - Review immediately")

        if medium_severity:
            summary_parts.append(f"🔶 {len(medium_severity)} medium-risk anomalies")

        if low_severity:
            summary_parts.append(f"🔵 {len(low_severity)} low-risk items")

        return " | ".join(summary_parts)


# Singleton instance
_permission_coach = PermissionCoach()


async def request_capability_via_permcoach(*args, **kwargs):
    """Convenience function to request capability via PermCoach."""
    return await _permission_coach.request_capability(*args, **kwargs)


async def revoke_capability_via_permcoach(*args, **kwargs):
    """Convenience function to revoke capability via PermCoach."""
    return await _permission_coach.revoke_capability(*args, **kwargs)


async def audit_user_capabilities(*args, **kwargs):
    """Convenience function to audit user capabilities."""
    return await _permission_coach.audit_capabilities(*args, **kwargs)
