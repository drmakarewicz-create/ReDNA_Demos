"""
History Logger — Self-Improvement Loop Audit Trail
==================================================

Thread-safe logging for prompt tuning decisions (approve/reject).

Features:
    - JSONL append with automatic file rotation (10,000 entries)
    - Chronological retrieval with filtering
    - Thread-safe writes with file locking
    - Integration with apply-suggestion workflow

Author: ReDNA Core Team
Created: 2025-10-09
Benchmark: #8 Self-Improvement Loop (Phase 2)
"""

import json
import threading
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, asdict


@dataclass
class HistoryEntry:
    """Single decision history entry."""
    coach_id: str
    suggestion_id: str
    action: str  # "approve" or "reject"
    confidence: float
    user: str
    timestamp: str
    old_hash: Optional[str] = None
    new_hash: Optional[str] = None
    reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class HistoryLogger:
    """Thread-safe logger for self-improvement decisions."""

    # File rotation threshold
    MAX_ENTRIES_PER_FILE = 10000

    def __init__(self, insights_dir: Path):
        """
        Initialize history logger.

        Args:
            insights_dir: Path to prompts/insights directory
        """
        self.insights_dir = Path(insights_dir)
        self.insights_dir.mkdir(parents=True, exist_ok=True)

        self.history_file = self.insights_dir / "self_improvement_history.jsonl"
        self._lock = threading.Lock()

    def log_decision(
        self,
        coach_id: str,
        suggestion_id: str,
        action: str,
        confidence: float,
        user: str,
        old_hash: Optional[str] = None,
        new_hash: Optional[str] = None,
        reason: Optional[str] = None
    ) -> HistoryEntry:
        """
        Log a decision (approve/reject) to history.

        Args:
            coach_id: Coach identifier
            suggestion_id: Suggestion ID being acted upon
            action: "approve" or "reject"
            confidence: Confidence score of suggestion
            user: User who made the decision
            old_hash: SHA-256 hash of old prompt (if approved)
            new_hash: SHA-256 hash of new prompt (if approved)
            reason: Optional comment/reason

        Returns:
            HistoryEntry that was logged
        """
        entry = HistoryEntry(
            coach_id=coach_id,
            suggestion_id=suggestion_id,
            action=action,
            confidence=confidence,
            user=user,
            timestamp=datetime.now(timezone.utc).isoformat(),
            old_hash=old_hash,
            new_hash=new_hash,
            reason=reason
        )

        # Thread-safe append
        with self._lock:
            # Check if rotation needed
            self._maybe_rotate_file()

            # Append entry
            with open(self.history_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry.to_dict()) + '\n')

        return entry

    def get_history(
        self,
        coach_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Retrieve history entries (most recent first).

        Args:
            coach_id: Optional filter by coach
            limit: Maximum entries to return

        Returns:
            List of history entry dictionaries
        """
        if not self.history_file.exists():
            return []

        entries = []

        # Read all entries
        with open(self.history_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    entry = json.loads(line)

                    # Filter by coach if specified
                    if coach_id and entry.get("coach_id") != coach_id:
                        continue

                    entries.append(entry)

                except json.JSONDecodeError:
                    continue

        # Sort by timestamp descending (most recent first)
        entries.sort(key=lambda e: e.get("timestamp", ""), reverse=True)

        # Apply limit
        return entries[:limit]

    def get_stats(self, coach_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get summary statistics from history.

        Args:
            coach_id: Optional filter by coach

        Returns:
            Statistics dictionary
        """
        history = self.get_history(coach_id=coach_id, limit=10000)

        if not history:
            return {
                "total_decisions": 0,
                "approvals": 0,
                "rejections": 0,
                "approval_rate": 0.0,
                "avg_confidence_approved": 0.0,
                "avg_confidence_rejected": 0.0
            }

        approvals = [e for e in history if e.get("action") == "approve"]
        rejections = [e for e in history if e.get("action") == "reject"]

        # Compute averages
        avg_conf_approved = 0.0
        if approvals:
            avg_conf_approved = sum(e.get("confidence", 0) for e in approvals) / len(approvals)

        avg_conf_rejected = 0.0
        if rejections:
            avg_conf_rejected = sum(e.get("confidence", 0) for e in rejections) / len(rejections)

        return {
            "total_decisions": len(history),
            "approvals": len(approvals),
            "rejections": len(rejections),
            "approval_rate": round(len(approvals) / len(history), 3) if history else 0.0,
            "avg_confidence_approved": round(avg_conf_approved, 3),
            "avg_confidence_rejected": round(avg_conf_rejected, 3)
        }

    def _maybe_rotate_file(self) -> None:
        """Rotate history file if it exceeds MAX_ENTRIES_PER_FILE."""
        if not self.history_file.exists():
            return

        # Count entries
        entry_count = 0
        with open(self.history_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    entry_count += 1

        # Rotate if needed
        if entry_count >= self.MAX_ENTRIES_PER_FILE:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            archive_file = self.insights_dir / f"self_improvement_history_{timestamp}.jsonl"

            # Move current file to archive
            self.history_file.rename(archive_file)

            print(f"📦 Rotated history file: {archive_file.name} ({entry_count} entries)")

    def get_coach_summary(self) -> Dict[str, Dict[str, Any]]:
        """
        Get per-coach decision summaries.

        Returns:
            Dictionary mapping coach_id to stats
        """
        history = self.get_history(limit=10000)

        # Group by coach
        by_coach = {}
        for entry in history:
            coach_id = entry.get("coach_id")
            if not coach_id:
                continue

            if coach_id not in by_coach:
                by_coach[coach_id] = []

            by_coach[coach_id].append(entry)

        # Compute stats per coach
        summaries = {}
        for coach_id, entries in by_coach.items():
            approvals = sum(1 for e in entries if e.get("action") == "approve")
            rejections = sum(1 for e in entries if e.get("action") == "reject")

            summaries[coach_id] = {
                "total_decisions": len(entries),
                "approvals": approvals,
                "rejections": rejections,
                "approval_rate": round(approvals / len(entries), 3) if entries else 0.0
            }

        return summaries


# Singleton instance
_history_logger_instance = None
_instance_lock = threading.Lock()


def get_history_logger(insights_dir: Optional[Path] = None) -> HistoryLogger:
    """
    Get singleton HistoryLogger instance.

    Args:
        insights_dir: Path to insights directory (only used on first call)

    Returns:
        HistoryLogger instance
    """
    global _history_logger_instance

    if _history_logger_instance is None:
        with _instance_lock:
            if _history_logger_instance is None:
                # Default to prompts/insights
                if insights_dir is None:
                    from ReDNACoreDemo.core.storage import CORE_DATA_ROOT
                    insights_dir = CORE_DATA_ROOT.parent / "prompts" / "insights"

                _history_logger_instance = HistoryLogger(insights_dir)

    return _history_logger_instance


def main():
    """CLI entry point for history viewing."""
    logger = get_history_logger()

    print("📜 Self-Improvement Decision History\n")

    # Get overall stats
    stats = logger.get_stats()
    print("Overall Statistics:")
    print(f"  Total Decisions: {stats['total_decisions']}")
    print(f"  Approvals: {stats['approvals']}")
    print(f"  Rejections: {stats['rejections']}")
    print(f"  Approval Rate: {stats['approval_rate']:.1%}")
    print(f"  Avg Confidence (Approved): {stats['avg_confidence_approved']:.2f}")
    print(f"  Avg Confidence (Rejected): {stats['avg_confidence_rejected']:.2f}")

    # Get per-coach summary
    print("\nPer-Coach Summary:")
    coach_summaries = logger.get_coach_summary()
    for coach_id, summary in coach_summaries.items():
        print(f"  {coach_id}:")
        print(f"    Decisions: {summary['total_decisions']}")
        print(f"    Approval Rate: {summary['approval_rate']:.1%}")

    # Recent history
    print("\nRecent Decisions (last 10):")
    recent = logger.get_history(limit=10)
    for entry in recent:
        action_symbol = "✅" if entry["action"] == "approve" else "❌"
        print(f"  {action_symbol} {entry['coach_id']} | "
              f"{entry['suggestion_id'][:8]} | "
              f"conf={entry['confidence']:.2f} | "
              f"by {entry['user']} | "
              f"{entry['timestamp'][:19]}")


if __name__ == "__main__":
    main()
