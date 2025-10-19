"""
ChatDNA Gap Logging System

Logs unmet style features during ChatDNA renders.
Privacy-preserving: stores only hashes, numeric scores, no raw text.
"""

import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional


EXTRACTOR_VERSION = "v1.2.0"


def get_prompt_hash(prompt: str) -> str:
    """Generate SHA-256 hash of prompt for privacy-preserving logging.

    Args:
        prompt: User prompt text

    Returns:
        Hash string in format "sha256:..."
    """
    hash_obj = hashlib.sha256(prompt.encode('utf-8'))
    return f"sha256:{hash_obj.hexdigest()[:16]}"


def log_unmet_features(
    user_id: str,
    prompt: str,
    intent: str,
    feature_map_version: str,
    items: List[Dict],
    rr_context: Optional[Dict] = None
) -> None:
    """Append unmet features to JSONL log.

    Args:
        user_id: User ID (anonymized if needed)
        prompt: Prompt text (will be hashed, not stored)
        intent: Intent category (casual, formal, etc.)
        feature_map_version: Feature map version hash
        items: List of {feature, type, impact_estimate, value, ...}
        rr_context: Optional RR context dict (domain RRs)
    """
    if not items:
        return  # Nothing to log

    log_dir = Path(__file__).parent
    log_dir.mkdir(parents=True, exist_ok=True)

    log_path = log_dir / "chatdna_unmet_features.jsonl"

    # Build log entry
    entry = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "user_id": user_id,
        "prompt_hash": get_prompt_hash(prompt),
        "intent": intent,
        "extractor_version": EXTRACTOR_VERSION,
        "feature_map_version": feature_map_version,
        "items": items
    }

    # Add RR context if provided
    if rr_context:
        for item in entry["items"]:
            if "rr_context" not in item:
                item["rr_context"] = rr_context

    # Append to JSONL
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry) + '\n')


def create_gap_item(
    feature: str,
    gap_type: str,  # "unmapped" or "fallback"
    value: float,
    impact_estimate: float,
    mapped_to: Optional[str] = None
) -> Dict:
    """Create a gap log item.

    Args:
        feature: Feature name
        gap_type: "unmapped" or "fallback"
        value: Feature value (numeric score)
        impact_estimate: Estimated similarity delta if feature existed
        mapped_to: Container path if type is "fallback"

    Returns:
        Gap item dict
    """
    item = {
        "feature": feature,
        "type": gap_type,
        "impact_estimate": impact_estimate,
        "value": value,
        "privacy_refs": []  # Always empty; no raw text
    }

    if mapped_to:
        item["mapped_to"] = mapped_to

    return item


def extract_mock_features(prompt: str, intent: str) -> Dict[str, float]:
    """Mock feature extractor for testing.

    In production, this would call real NLP extractors.

    Args:
        prompt: User prompt
        intent: Intent category

    Returns:
        Dict of {feature_name: score}
    """
    features = {}

    # Mock mapped features
    features["sentence_length_avg"] = len(prompt.split()) / max(1, prompt.count('.'))
    features["formality_index"] = 0.7 if intent == "formal" else 0.3
    features["hedge_rate_per_100"] = 2.5

    # Mock unmapped features (gaps)
    if "?" in prompt:
        features["parallelism_pattern_score"] = 0.64
    if "(" in prompt:
        features["parenthetical_usage_rate"] = 0.15
    if intent == "persuasive":
        features["intensifier_frequency"] = 0.45

    return features
