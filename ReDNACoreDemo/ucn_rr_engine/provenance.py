"""
Provenance Logger

Tracks all evidence attempts (successes AND failures) for complete audit trail.

Key principles:
- Log ALL gap-resolution attempts
- Failed attempts reveal user behavior patterns
- Tiered storage: hot (90 days), warm (2 years), cold (forever)
- Context for Head Coach decision-making
"""

import json
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum


class AttemptType(Enum):
    """Types of evidence gathering attempts."""
    PHOTO_UPLOAD = "photo_upload"
    VIDEO_CAPTURE = "video_capture"
    FORM_SUBMISSION = "form_submission"
    CHAT_MESSAGE = "chat_message"
    THIRD_PARTY_REQUEST = "third_party_request"
    DEVICE_SENSOR = "device_sensor"
    BEHAVIORAL_OBSERVATION = "behavioral_observation"
    INFERENCE = "inference"
    AI_ANALYSIS = "ai_analysis"
    EXTERNAL_APP = "external_app"


class AttemptStatus(Enum):
    """Status of evidence gathering attempt."""
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"


@dataclass
class ProvenanceEntry:
    """Single provenance log entry."""
    trait_path: str
    timestamp: str  # ISO format
    attempt_id: str
    attempt_type: AttemptType
    attempt_status: AttemptStatus
    source_type: str
    source_id: str
    evidence_quality: Optional[float] = None
    extracted_value: Optional[Any] = None
    confidence_assigned: Optional[float] = None
    ucn_before: Optional[int] = None
    ucn_after: Optional[int] = None
    corroboration_sources: Optional[List[str]] = None
    contradiction_sources: Optional[List[str]] = None
    decay_half_life_applied: Optional[float] = None
    failure_reason: Optional[str] = None
    user_behavior_indicators: Optional[Dict[str, Any]] = None
    head_coach_notes: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ProvenanceLogger:
    """Logs and manages provenance entries with tiered storage."""

    def __init__(self, storage_dir: Optional[Path] = None):
        """
        Initialize provenance logger.

        Args:
            storage_dir: Directory for provenance storage (defaults to data/provenance/)
        """
        if storage_dir is None:
            storage_dir = Path(__file__).parent.parent / "data" / "provenance"

        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # Tiered storage directories
        self.hot_dir = self.storage_dir / "hot"
        self.warm_dir = self.storage_dir / "warm"
        self.cold_dir = self.storage_dir / "cold"

        for dir in [self.hot_dir, self.warm_dir, self.cold_dir]:
            dir.mkdir(exist_ok=True)

    def log_attempt(
        self,
        user_id: str,
        trait_path: str,
        attempt_type: AttemptType,
        attempt_status: AttemptStatus,
        source_type: str,
        source_id: str,
        evidence_quality: Optional[float] = None,
        extracted_value: Optional[Any] = None,
        confidence_assigned: Optional[float] = None,
        ucn_before: Optional[int] = None,
        ucn_after: Optional[int] = None,
        corroboration_sources: Optional[List[str]] = None,
        contradiction_sources: Optional[List[str]] = None,
        decay_half_life_applied: Optional[float] = None,
        failure_reason: Optional[str] = None,
        user_behavior_indicators: Optional[Dict[str, Any]] = None,
        head_coach_notes: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Log an evidence gathering attempt.

        Args:
            user_id: User ID
            trait_path: Full trait path
            attempt_type: Type of attempt
            attempt_status: Success/failure/partial
            source_type: Evidence source type
            source_id: Evidence source ID
            (... additional optional fields ...)

        Returns:
            attempt_id (UUID)
        """
        attempt_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()

        entry = ProvenanceEntry(
            trait_path=trait_path,
            timestamp=timestamp,
            attempt_id=attempt_id,
            attempt_type=attempt_type,
            attempt_status=attempt_status,
            source_type=source_type,
            source_id=source_id,
            evidence_quality=evidence_quality,
            extracted_value=extracted_value,
            confidence_assigned=confidence_assigned,
            ucn_before=ucn_before,
            ucn_after=ucn_after,
            corroboration_sources=corroboration_sources or [],
            contradiction_sources=contradiction_sources or [],
            decay_half_life_applied=decay_half_life_applied,
            failure_reason=failure_reason,
            user_behavior_indicators=user_behavior_indicators or {},
            head_coach_notes=head_coach_notes,
            metadata=metadata or {}
        )

        # Write to hot tier (recent data)
        self._write_to_hot(user_id, entry)

        return attempt_id

    def _write_to_hot(self, user_id: str, entry: ProvenanceEntry) -> None:
        """Write provenance entry to hot tier (recent data)."""
        user_file = self.hot_dir / f"{user_id}.jsonl"

        # Append to JSONL file (one JSON object per line)
        entry_dict = asdict(entry)
        # Convert Enums to strings
        entry_dict['attempt_type'] = entry.attempt_type.value
        entry_dict['attempt_status'] = entry.attempt_status.value

        with open(user_file, 'a') as f:
            f.write(json.dumps(entry_dict) + '\n')

    def get_provenance(
        self,
        user_id: str,
        trait_path: Optional[str] = None,
        lookback_days: Optional[int] = 90,
        tier: str = 'hot'
    ) -> List[ProvenanceEntry]:
        """
        Retrieve provenance entries for a user.

        Args:
            user_id: User ID
            trait_path: Filter by trait path (optional)
            lookback_days: Look back N days (optional, None = all)
            tier: Storage tier ('hot', 'warm', 'cold', 'all')

        Returns:
            List of provenance entries
        """
        entries = []

        # Determine which tiers to query
        if tier == 'all':
            dirs = [self.hot_dir, self.warm_dir, self.cold_dir]
        elif tier == 'hot':
            dirs = [self.hot_dir]
        elif tier == 'warm':
            dirs = [self.warm_dir]
        elif tier == 'cold':
            dirs = [self.cold_dir]
        else:
            raise ValueError(f"Invalid tier: {tier}")

        # Calculate cutoff date
        cutoff_date = None
        if lookback_days is not None:
            cutoff_date = datetime.now() - timedelta(days=lookback_days)

        # Read from each tier
        for dir in dirs:
            user_file = dir / f"{user_id}.jsonl"
            if not user_file.exists():
                continue

            with open(user_file, 'r') as f:
                for line in f:
                    entry_dict = json.loads(line)

                    # Filter by trait path
                    if trait_path and entry_dict['trait_path'] != trait_path:
                        continue

                    # Filter by date
                    if cutoff_date:
                        entry_time = datetime.fromisoformat(entry_dict['timestamp'])
                        if entry_time < cutoff_date:
                            continue

                    # Convert back to ProvenanceEntry
                    # Convert string enums back to Enum objects
                    entry_dict['attempt_type'] = AttemptType(entry_dict['attempt_type'])
                    entry_dict['attempt_status'] = AttemptStatus(entry_dict['attempt_status'])

                    entry = ProvenanceEntry(**entry_dict)
                    entries.append(entry)

        # Sort by timestamp (most recent first)
        entries.sort(key=lambda e: e.timestamp, reverse=True)

        return entries

    def get_user_behavior_patterns(
        self,
        user_id: str,
        lookback_days: int = 90
    ) -> Dict[str, Any]:
        """
        Analyze user behavior patterns from provenance log.

        Returns patterns like:
        - Upload success rate
        - Technical ability indicators
        - Engagement patterns
        - Conscientiousness indicators

        Args:
            user_id: User ID
            lookback_days: Look back N days

        Returns:
            Dictionary of behavior patterns
        """
        entries = self.get_provenance(user_id, lookback_days=lookback_days)

        if not entries:
            return {
                'total_attempts': 0,
                'success_rate': 0.0,
                'engagement': 'none'
            }

        # Count attempts by status
        total_attempts = len(entries)
        successes = sum(1 for e in entries if e.attempt_status == AttemptStatus.SUCCESS)
        failures = sum(1 for e in entries if e.attempt_status == AttemptStatus.FAILURE)

        # Success rate
        success_rate = successes / total_attempts if total_attempts > 0 else 0.0

        # Photo upload specific patterns
        photo_attempts = [e for e in entries if e.attempt_type == AttemptType.PHOTO_UPLOAD]
        photo_success_rate = 0.0
        if photo_attempts:
            photo_successes = sum(1 for e in photo_attempts if e.attempt_status == AttemptStatus.SUCCESS)
            photo_success_rate = photo_successes / len(photo_attempts)

        # Technical ability (inferred from failure patterns)
        technical_ability = 'unknown'
        if photo_success_rate >= 0.8:
            technical_ability = 'high'
        elif photo_success_rate >= 0.5:
            technical_ability = 'medium'
        elif len(photo_attempts) >= 3:
            technical_ability = 'low'

        # Engagement level (based on attempt frequency)
        days_span = (
            datetime.fromisoformat(entries[0].timestamp) -
            datetime.fromisoformat(entries[-1].timestamp)
        ).days or 1
        attempts_per_day = total_attempts / days_span

        if attempts_per_day >= 2:
            engagement = 'very_high'
        elif attempts_per_day >= 1:
            engagement = 'high'
        elif attempts_per_day >= 0.5:
            engagement = 'medium'
        elif attempts_per_day >= 0.1:
            engagement = 'low'
        else:
            engagement = 'very_low'

        # Conscientiousness (completion rate, quality)
        avg_quality = 0.0
        quality_entries = [e for e in entries if e.evidence_quality is not None]
        if quality_entries:
            avg_quality = sum(e.evidence_quality for e in quality_entries) / len(quality_entries)

        return {
            'total_attempts': total_attempts,
            'successes': successes,
            'failures': failures,
            'success_rate': round(success_rate, 3),
            'photo_upload_success_rate': round(photo_success_rate, 3),
            'technical_ability': technical_ability,
            'engagement': engagement,
            'attempts_per_day': round(attempts_per_day, 2),
            'avg_evidence_quality': round(avg_quality, 3),
            'lookback_days': lookback_days
        }

    def tier_maintenance(self) -> Dict[str, int]:
        """
        Perform tiered storage maintenance.

        Move entries:
        - Hot (< 90 days): Full raw data
        - Warm (90 days - 2 years): Aggregated summaries
        - Cold (2+ years): High-level summaries

        Returns:
            Dictionary with counts of moved entries
        """
        now = datetime.now()
        hot_cutoff = now - timedelta(days=90)
        warm_cutoff = now - timedelta(days=730)  # 2 years

        moved_to_warm = 0
        moved_to_cold = 0

        # Process each user file in hot tier
        for user_file in self.hot_dir.glob("*.jsonl"):
            user_id = user_file.stem

            hot_entries = []
            warm_entries = []

            with open(user_file, 'r') as f:
                for line in f:
                    entry_dict = json.loads(line)
                    entry_time = datetime.fromisoformat(entry_dict['timestamp'])

                    if entry_time >= hot_cutoff:
                        # Stay in hot
                        hot_entries.append(entry_dict)
                    else:
                        # Move to warm
                        warm_entries.append(entry_dict)
                        moved_to_warm += 1

            # Rewrite hot tier (without moved entries)
            with open(user_file, 'w') as f:
                for entry in hot_entries:
                    f.write(json.dumps(entry) + '\n')

            # Append to warm tier
            if warm_entries:
                warm_file = self.warm_dir / f"{user_id}.jsonl"
                with open(warm_file, 'a') as f:
                    for entry in warm_entries:
                        # Could aggregate/compress here
                        f.write(json.dumps(entry) + '\n')

        # Process warm tier → cold tier (similar logic)
        # For now, we'll keep warm tier as-is and implement cold tier migration later

        return {
            'moved_to_warm': moved_to_warm,
            'moved_to_cold': moved_to_cold
        }


def update_evidence(
    user_id: str,
    trait_path: str,
    source_type: str,
    source_id: str,
    extracted_value: Any,
    evidence_quality: float,
    timestamp: str,
    ucn_before: Optional[int] = None,
    ucn_after: Optional[int] = None,
    logger: Optional[ProvenanceLogger] = None
) -> str:
    """
    Convenience function to log a successful evidence update.

    Args:
        user_id: User ID
        trait_path: Full trait path
        source_type: Evidence source type
        source_id: Evidence source ID
        extracted_value: Extracted trait value
        evidence_quality: Quality score (0.0-1.0)
        timestamp: Timestamp (ISO format)
        ucn_before: UCN before update (optional)
        ucn_after: UCN after update (optional)
        logger: ProvenanceLogger instance (optional, creates new if None)

    Returns:
        attempt_id
    """
    if logger is None:
        logger = ProvenanceLogger()

    # Infer attempt type from source type
    attempt_type_map = {
        'photo': AttemptType.PHOTO_UPLOAD,
        'photo_single': AttemptType.PHOTO_UPLOAD,
        'photo_series': AttemptType.PHOTO_UPLOAD,
        'webcam_video': AttemptType.VIDEO_CAPTURE,
        'self_report_text': AttemptType.CHAT_MESSAGE,
        'self_report_structured': AttemptType.FORM_SUBMISSION,
        'third_party_attestation': AttemptType.THIRD_PARTY_REQUEST,
        'device_sensor': AttemptType.DEVICE_SENSOR,
        'behavioral_observation': AttemptType.BEHAVIORAL_OBSERVATION,
        'inference_single': AttemptType.INFERENCE,
        'inference_multiple': AttemptType.INFERENCE,
        'ai_analysis': AttemptType.AI_ANALYSIS,
    }
    attempt_type = attempt_type_map.get(source_type, AttemptType.EXTERNAL_APP)

    return logger.log_attempt(
        user_id=user_id,
        trait_path=trait_path,
        attempt_type=attempt_type,
        attempt_status=AttemptStatus.SUCCESS,
        source_type=source_type,
        source_id=source_id,
        evidence_quality=evidence_quality,
        extracted_value=extracted_value,
        ucn_before=ucn_before,
        ucn_after=ucn_after,
        metadata={'timestamp': timestamp}
    )
