"""
Permission Coach - Nightly Audit Job

Runs automated audits of user capabilities, flagging anomalies
and notifying users via Head Coach.

Schedule: Runs nightly at 2 AM (configurable)
"""

import argparse
import logging
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
import json

try:
    from .permcoach_service import PermissionCoach
except ImportError:  # pragma: no cover - direct script execution fallback
    from permcoach_service import PermissionCoach  # type: ignore

# Services are at project root
import sys
_services_root = Path(__file__).resolve().parents[4] / "services"
if str(_services_root) not in sys.path:
    sys.path.insert(0, str(_services_root.parent))

from services.consent.storage import ConsentStorage

logger = logging.getLogger(__name__)

# Audit log directory
AUDIT_LOG_DIR = Path(__file__).parent.parent.parent.parent / "data" / "consent" / "audit"
AUDIT_LOG_DIR.mkdir(parents=True, exist_ok=True)


class PermCoachAuditor:
    """Automated auditor for user capabilities."""

    def __init__(self):
        """Initialize auditor."""
        self.permcoach = PermissionCoach()
        self.storage = ConsentStorage()

    async def run_nightly_audit(self) -> Dict[str, Any]:
        """
        Run nightly audit across all users with active capabilities.

        Returns:
            Audit summary with anomalies per user
        """
        logger.info("🔍 Starting nightly capability audit...")

        # Get all users with capabilities
        all_capabilities = self.storage.list_capabilities()
        user_ids = list(set(cap.user_id for cap in all_capabilities))

        logger.info(f"Auditing capabilities for {len(user_ids)} users")

        audit_results = {
            "audit_timestamp": datetime.utcnow().isoformat() + "Z",
            "total_users": len(user_ids),
            "total_capabilities": len(all_capabilities),
            "users_with_anomalies": [],
            "summary": {},
        }

        for user_id in user_ids:
            logger.debug(f"Auditing user: {user_id}")

            # Run audit for this user
            user_audit = await self.permcoach.audit_capabilities(user_id)

            # If anomalies found, add to results
            if user_audit.get("anomalies"):
                audit_results["users_with_anomalies"].append({
                    "user_id": user_id,
                    "anomaly_count": len(user_audit["anomalies"]),
                    "severity_breakdown": self._count_by_severity(user_audit["anomalies"]),
                    "audit_summary": user_audit["summary"],
                })

                # Notify user via Head Coach (async)
                asyncio.create_task(self._notify_user(user_id, user_audit))

        # Generate summary statistics
        audit_results["summary"] = self._generate_summary(audit_results)

        # Save audit log
        self._save_audit_log(audit_results)

        logger.info(f"✅ Nightly audit complete: {len(audit_results['users_with_anomalies'])} users with anomalies")

        return audit_results

    async def audit_single_user(self, user_id: str) -> Dict[str, Any]:
        """
        Run audit for a single user (on-demand).

        Args:
            user_id: User ID to audit

        Returns:
            Audit report for user
        """
        logger.info(f"Running on-demand audit for user {user_id}")

        audit_report = await self.permcoach.audit_capabilities(user_id)

        # Save to audit log
        self._save_user_audit_log(user_id, audit_report)

        return audit_report

    def _count_by_severity(self, anomalies: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Count anomalies by severity.

        Args:
            anomalies: List of anomalies

        Returns:
            Dict with counts: {"high": 1, "medium": 3, "low": 2}
        """
        counts = {"high": 0, "medium": 0, "low": 0}

        for anomaly in anomalies:
            severity = anomaly.get("severity", "low")
            counts[severity] = counts.get(severity, 0) + 1

        return counts

    def _generate_summary(self, audit_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate summary statistics from audit results.

        Args:
            audit_results: Full audit results

        Returns:
            Summary dict
        """
        total_anomalies = sum(
            user["anomaly_count"] for user in audit_results["users_with_anomalies"]
        )

        severity_breakdown = {"high": 0, "medium": 0, "low": 0}
        for user in audit_results["users_with_anomalies"]:
            for severity, count in user["severity_breakdown"].items():
                severity_breakdown[severity] += count

        return {
            "total_anomalies": total_anomalies,
            "users_with_anomalies": len(audit_results["users_with_anomalies"]),
            "severity_breakdown": severity_breakdown,
            "requires_immediate_action": severity_breakdown["high"] > 0,
        }

    async def _notify_user(self, user_id: str, audit_report: Dict[str, Any]):
        """
        Notify user of audit findings via Head Coach.

        Args:
            user_id: User ID
            audit_report: Audit report with anomalies
        """
        # TODO: Integrate with Head Coach messaging system
        # For now, log the notification

        anomalies = audit_report.get("anomalies", [])
        if not anomalies:
            return

        high_severity = [a for a in anomalies if a.get("severity") == "high"]

        if high_severity:
            logger.warning(f"🚨 High-severity anomalies for user {user_id}: {len(high_severity)} found")
            # In production: send to Head Coach for user notification
            # await head_coach.send_message(user_id, f"PermCoach: {len(high_severity)} high-risk permissions detected. Please review.")
        else:
            logger.info(f"📋 Audit findings for user {user_id}: {len(anomalies)} anomalies (low/medium severity)")

    def _save_audit_log(self, audit_results: Dict[str, Any]):
        """
        Save audit results to log file.

        Args:
            audit_results: Full audit results
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        log_file = AUDIT_LOG_DIR / f"nightly_audit_{timestamp}.json"

        try:
            with open(log_file, "w") as f:
                json.dump(audit_results, f, indent=2)

            logger.info(f"Audit log saved: {log_file}")
        except Exception as e:
            logger.error(f"Failed to save audit log: {e}")

    def _save_user_audit_log(self, user_id: str, audit_report: Dict[str, Any]):
        """
        Save per-user audit log.

        Args:
            user_id: User ID
            audit_report: Audit report for user
        """
        user_audit_dir = AUDIT_LOG_DIR / user_id
        user_audit_dir.mkdir(exist_ok=True)

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        log_file = user_audit_dir / f"audit_{timestamp}.json"

        try:
            with open(log_file, "w") as f:
                json.dump(audit_report, f, indent=2)

            logger.debug(f"User audit log saved: {log_file}")
        except Exception as e:
            logger.error(f"Failed to save user audit log: {e}")


# Singleton instance
_auditor = PermCoachAuditor()


async def run_nightly_audit():
    """Run nightly audit (convenience function)."""
    return await _auditor.run_nightly_audit()


async def audit_user(user_id: str):
    """Audit specific user (convenience function)."""
    return await _auditor.audit_single_user(user_id)


# Scheduler integration (optional - requires APScheduler or similar)
"""
Example integration with APScheduler:

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

scheduler = AsyncIOScheduler()

# Schedule nightly audit at 2 AM
scheduler.add_job(
    run_nightly_audit,
    trigger=CronTrigger(hour=2, minute=0),
    id="nightly_capability_audit",
    name="PermCoach Nightly Audit",
    replace_existing=True,
)

scheduler.start()
"""


def _write_last_run(users_scanned: int, anomalies_found: int) -> Path:
    """
    Persist summary of the most recent manual audit.
    """
    last_run_file = AUDIT_LOG_DIR / "last_run.json"
    payload = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "users_scanned": users_scanned,
        "anomalies_found": anomalies_found,
    }

    try:
        with open(last_run_file, "w") as f:
            json.dump(payload, f, indent=2)
        logger.info(f"Last audit run recorded at {last_run_file}")
    except Exception as e:
        logger.error(f"Failed to record last audit run: {e}")

    return last_run_file


def main_cli(argv: Optional[List[str]] = None):
    """
    Manual CLI entrypoint for PermCoach audits.
    """
    parser = argparse.ArgumentParser(description="Run PermCoach capability audits.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--user", help="Run audit for a single user ID.")
    group.add_argument("--all", action="store_true", help="Run nightly audit workflow for all users.")
    args = parser.parse_args(argv)

    if args.all:
        audit_result = asyncio.run(run_nightly_audit())
        users_scanned = int(audit_result.get("total_users", 0))
        anomalies_found = int(
            audit_result.get("summary", {}).get("total_anomalies", 0)
        )
        _write_last_run(users_scanned, anomalies_found)
        print(
            f"PermCoach nightly audit complete — users: {users_scanned}, anomalies: {anomalies_found}"
        )
    else:
        user_id = args.user.strip()
        if not user_id:
            raise SystemExit("User ID cannot be empty.")
        audit_report = asyncio.run(audit_user(user_id))
        anomalies = audit_report.get("anomalies") or []
        users_scanned = 1
        anomalies_found = len(anomalies)
        _write_last_run(users_scanned, anomalies_found)

        severity_breakdown = {"high": 0, "medium": 0, "low": 0}
        for anomaly in anomalies:
            severity = (anomaly.get("severity") or "low").lower()
            if severity not in severity_breakdown:
                severity_breakdown[severity] = 0
            severity_breakdown[severity] += 1

        breakdown_str = " / ".join(
            f"{count} {level}" for level, count in severity_breakdown.items()
        )

        print(
            f"PermCoach audit for {user_id} complete — anomalies: {anomalies_found} ({breakdown_str})"
        )


if __name__ == "__main__":
    main_cli()
