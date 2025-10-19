"""
Self-Improvement Learning Daemon
=================================

Autonomous scheduler that periodically:
1. Analyzes telemetry across all coaches
2. Generates prompt tuning suggestions
3. Auto-approves high-confidence suggestions (≥0.9 by default)
4. Logs all runs to telemetry and history

USAGE:
    python -m ReDNACoreDemo.core.learning.daemon [options]

OPTIONS:
    --interval HOURS        Run interval in hours (default: 6)
    --threshold FLOAT       Min confidence for auto-apply (default: 0.9)
    --dry-run              Analyze and suggest only, don't apply
    --limit INT            Max suggestions per coach (default: 5)
    --once                 Run once and exit (no loop)

FILE LOCK:
    Uses learning_daemon.lock to ensure single instance.
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import fcntl

# Add parent to path for imports
SCRIPT_DIR = Path(__file__).parent
CORE_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(CORE_DIR.parent))

from ReDNACoreDemo.core.learning.telemetry_analyzer import TelemetryAnalyzer
from ReDNACoreDemo.core.learning.prompt_tuner import PromptTuner
from ReDNACoreDemo.core.learning.history_logger import HistoryLogger
from ReDNACoreDemo.core.storage import CORE_DATA_ROOT

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


class LearningDaemon:
    """Autonomous learning daemon for self-improvement loop."""

    def __init__(
        self,
        data_dir: Path,
        interval_hours: float = 6.0,
        auto_threshold: float = 0.9,
        max_suggestions_per_coach: int = 5,
        dry_run: bool = False,
        log_path: Optional[Path] = None,
        tolerant_validation: bool = True,
    ):
        """
        Initialize daemon.

        Args:
            data_dir: Root data directory
            interval_hours: Hours between runs
            auto_threshold: Min confidence for auto-apply
            max_suggestions_per_coach: Max suggestions per coach
            dry_run: If True, analyze only (no apply)
            log_path: Path to daemon telemetry log
        """
        self.data_dir = data_dir
        self.interval_hours = interval_hours
        self.auto_threshold = auto_threshold
        self.max_suggestions_per_coach = max_suggestions_per_coach
        self.dry_run = dry_run

        # Set up paths (align with TelemetryAnalyzer expectations)
        self.prompts_dir = data_dir.parent / "prompts"
        self.insights_dir = self.prompts_dir / "insights"
        self.insights_dir.mkdir(parents=True, exist_ok=True)

        self.log_path = log_path or (self.insights_dir / "self_improvement_daemon.jsonl")
        self.lock_file = self.insights_dir / "learning_daemon.lock"

        # Components
        self.analyzer = TelemetryAnalyzer(data_dir=data_dir, tolerant_validation=tolerant_validation)
        self.history_logger = HistoryLogger(insights_dir=self.insights_dir)
        self.tolerant_validation = tolerant_validation

        self.lock_fd: Optional[int] = None

    def acquire_lock(self) -> bool:
        """
        Acquire exclusive file lock.

        Returns:
            True if lock acquired, False if another instance running
        """
        try:
            self.lock_fd = open(self.lock_file, 'w')
            fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.lock_fd.write(f"{datetime.now(timezone.utc).isoformat()}\n")
            self.lock_fd.flush()
            return True
        except IOError:
            logger.warning("Another daemon instance is running (lock held)")
            return False

    def release_lock(self):
        """Release file lock."""
        if self.lock_fd:
            try:
                fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
                self.lock_fd.close()
                self.lock_file.unlink(missing_ok=True)
            except Exception as e:
                logger.error(f"Error releasing lock: {e}")

    def run_cycle(self) -> Dict[str, Any]:
        """
        Run single improvement cycle.

        Returns:
            Dict with run summary (suggestions_generated, auto_approved, etc.)
        """
        start_time = time.time()

        logger.info("Starting self-improvement cycle...")

        # Step 1: Analyze telemetry
        logger.info("Analyzing telemetry...")
        analysis_report = self.analyzer.analyze_all_coaches()

        coaches_analyzed = len(analysis_report.get("coaches", {}))
        logger.info(f"Analyzed {coaches_analyzed} coaches")

        # Step 2: Generate suggestions
        logger.info("Generating tuning suggestions...")
        tuner = PromptTuner(analysis_report=analysis_report)
        all_suggestions = tuner.generate_suggestions()

        # Filter by confidence threshold
        eligible_suggestions = [
            s for s in all_suggestions
            if s["confidence"] >= self.auto_threshold
        ]

        logger.info(f"Generated {len(all_suggestions)} suggestions, {len(eligible_suggestions)} eligible for auto-apply")

        # Step 3: Apply suggestions (if not dry-run)
        approved_count = 0
        skipped_count = 0

        if not self.dry_run and eligible_suggestions:
            # Group by coach and limit per coach
            by_coach: Dict[str, List[Dict]] = {}
            for suggestion in eligible_suggestions:
                coach_id = suggestion["coach_id"]
                if coach_id not in by_coach:
                    by_coach[coach_id] = []
                by_coach[coach_id].append(suggestion)

            # Apply suggestions
            for coach_id, suggestions in by_coach.items():
                # Limit per coach
                suggestions_to_apply = suggestions[:self.max_suggestions_per_coach]

                for suggestion in suggestions_to_apply:
                    try:
                        self._apply_suggestion(suggestion)
                        approved_count += 1
                        logger.info(f"Auto-approved: {suggestion['id']} (confidence={suggestion['confidence']:.2f})")
                    except Exception as e:
                        logger.error(f"Error applying suggestion {suggestion['id']}: {e}")
                        skipped_count += 1

        elapsed = time.time() - start_time

        # Build summary
        summary = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "interval_hours": self.interval_hours,
            "auto_threshold": self.auto_threshold,
            "dry_run": self.dry_run,
            "coaches_analyzed": coaches_analyzed,
            "suggestions_generated": len(all_suggestions),
            "suggestions_eligible": len(eligible_suggestions),
            "suggestions_approved": approved_count,
            "suggestions_skipped": skipped_count,
            "elapsed_seconds": round(elapsed, 2)
        }

        # Log to telemetry
        self._log_run(summary)

        logger.info(f"Cycle complete: {approved_count} approved, {skipped_count} skipped, {elapsed:.2f}s")

        return summary

    def _apply_suggestion(self, suggestion: Dict[str, Any]):
        """
        Apply a tuning suggestion.

        Args:
            suggestion: Suggestion dict with id, coach_id, type, etc.
        """
        coach_id = suggestion["coach_id"]
        suggestion_id = suggestion["id"]

        # Get prompt file path
        prompts_dir = self.data_dir.parent / "prompts"
        prompt_file = prompts_dir / f"{coach_id}_ai.md"

        if not prompt_file.exists():
            raise FileNotFoundError(f"Prompt file not found: {prompt_file}")

        # Read current prompt
        with open(prompt_file, 'r', encoding='utf-8') as f:
            current_prompt = f.read()

        # Compute old hash
        import hashlib
        old_hash = hashlib.sha256(current_prompt.encode('utf-8')).hexdigest()[:16]

        # Create backup
        backup_dir = prompts_dir / "backups"
        backup_dir.mkdir(exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        backup_file = backup_dir / f"{coach_id}_ai_{timestamp}_{old_hash}.md"

        with open(backup_file, 'w', encoding='utf-8') as f:
            f.write(current_prompt)

        # Apply modification (simple append for now)
        modification = f"\n\n<!-- Applied suggestion {suggestion_id} -->\n"
        modification += f"<!-- Type: {suggestion['type']} -->\n"
        modification += f"<!-- Recommendation: {suggestion['recommended_value']} -->\n"
        modification += f"<!-- Confidence: {suggestion['confidence']:.2f} -->\n"
        modification += f"<!-- Applied: {datetime.now(timezone.utc).isoformat()} -->\n"

        new_prompt = current_prompt + modification

        # Write updated prompt
        with open(prompt_file, 'w', encoding='utf-8') as f:
            f.write(new_prompt)

        # Compute new hash
        new_hash = hashlib.sha256(new_prompt.encode('utf-8')).hexdigest()[:16]

        # Log to history
        self.history_logger.log_decision(
            coach_id=coach_id,
            suggestion_id=suggestion_id,
            action="approve",
            confidence=suggestion["confidence"],
            user="daemon",
            old_hash=old_hash,
            new_hash=new_hash,
            reason=f"Auto-approved (confidence={suggestion['confidence']:.2f} ≥ {self.auto_threshold})"
        )

    def _log_run(self, summary: Dict[str, Any]):
        """
        Log daemon run to telemetry.

        Args:
            summary: Run summary dict
        """
        try:
            entry = {
                "kind": "self_improvement_run",
                "timestamp": summary["timestamp"],
                "data": summary
            }

            with open(self.log_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry) + '\n')

        except Exception as e:
            logger.error(f"Error logging run: {e}")

    def run_forever(self):
        """Run daemon in loop with configured interval."""
        if not self.acquire_lock():
            logger.error("Cannot start: another instance is running")
            sys.exit(1)

        try:
            logger.info(f"Daemon started (interval={self.interval_hours}h, threshold={self.auto_threshold}, dry_run={self.dry_run})")

            while True:
                try:
                    self.run_cycle()
                except Exception as e:
                    logger.error(f"Cycle error: {e}", exc_info=True)

                # Sleep until next cycle
                sleep_seconds = self.interval_hours * 3600
                logger.info(f"Sleeping for {self.interval_hours}h...")
                time.sleep(sleep_seconds)

        finally:
            self.release_lock()

    def run_once(self):
        """Run single cycle and exit."""
        if not self.acquire_lock():
            logger.error("Cannot start: another instance is running")
            sys.exit(1)

        try:
            summary = self.run_cycle()
            return summary
        finally:
            self.release_lock()


def load_config(config_path: Path) -> Dict[str, Any]:
    """
    Load daemon configuration from JSON file.

    Args:
        config_path: Path to learning_config.json

    Returns:
        Config dict
    """
    if not config_path.exists():
        return {}

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Error loading config: {e}")
        return {}


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Self-Improvement Learning Daemon")
    parser.add_argument("--interval", type=float, help="Run interval in hours (default: 6)")
    parser.add_argument("--threshold", type=float, help="Min confidence for auto-apply (default: 0.9)")
    parser.add_argument("--dry-run", action="store_true", help="Analyze only, don't apply")
    parser.add_argument("--limit", type=int, help="Max suggestions per coach (default: 5)")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--strict-validation", action="store_true", help="Disable tolerant telemetry parsing.")
    parser.add_argument("--config", type=str, help="Config file path (default: learning_config.json)")

    args = parser.parse_args()

    # Load config file
    config_path = Path(args.config) if args.config else (CORE_DIR / "learning" / "learning_config.json")
    config = load_config(config_path)

    # Merge CLI args with config (CLI takes precedence)
    interval_hours = args.interval if args.interval is not None else config.get("interval_hours", 6.0)
    auto_threshold = args.threshold if args.threshold is not None else config.get("auto_threshold", 0.9)
    max_suggestions = args.limit if args.limit is not None else config.get("max_suggestions_per_coach", 5)
    dry_run = args.dry_run or config.get("dry_run", False)
    tolerant_validation = config.get("tolerant_validation", True)
    if args.strict_validation:
        tolerant_validation = False

    # Create daemon
    daemon = LearningDaemon(
        data_dir=CORE_DATA_ROOT,
        interval_hours=interval_hours,
        auto_threshold=auto_threshold,
        max_suggestions_per_coach=max_suggestions,
        dry_run=dry_run,
        tolerant_validation=tolerant_validation,
    )

    # Run
    if args.once:
        summary = daemon.run_once()
        print(json.dumps(summary, indent=2))
    else:
        daemon.run_forever()


if __name__ == "__main__":
    main()
