"""
Language Feature Mapping System

Maps low-level extractor features to DNA container paths.
Tracks unmapped features for gap analysis and container proposals.
"""

import yaml
import hashlib
from pathlib import Path
from typing import Dict, Optional, Tuple


_FEATURE_MAP_CACHE = None
_FEATURE_MAP_VERSION = None


def load_feature_map() -> Dict:
    """Load language feature map with caching.

    Returns:
        Dict with 'features' (mapped), 'unmapped_features', 'governance', 'version_hash'
    """
    global _FEATURE_MAP_CACHE, _FEATURE_MAP_VERSION

    if _FEATURE_MAP_CACHE is not None:
        return _FEATURE_MAP_CACHE

    map_path = Path(__file__).parent / "language_feature_map.yaml"

    with open(map_path, 'r', encoding='utf-8') as f:
        content = f.read()
        feature_map = yaml.safe_load(content)

    # Compute version hash (SHA-1 of content)
    version_hash = hashlib.sha1(content.encode('utf-8')).hexdigest()[:8]
    _FEATURE_MAP_VERSION = version_hash

    feature_map['version_hash'] = version_hash
    _FEATURE_MAP_CACHE = feature_map

    return feature_map


def get_feature_map_version() -> str:
    """Get the current feature map version hash."""
    if _FEATURE_MAP_VERSION is None:
        load_feature_map()
    return _FEATURE_MAP_VERSION


def lookup_container(feature_name: str) -> Optional[str]:
    """Look up container path for a feature.

    Args:
        feature_name: Extractor feature name

    Returns:
        Container path string, or None if unmapped
    """
    feature_map = load_feature_map()

    # Check mapped features
    if feature_name in feature_map.get('features', {}):
        feature_info = feature_map['features'][feature_name]
        return feature_info.get('container')

    # Check unmapped features
    if feature_name in feature_map.get('unmapped_features', {}):
        return None  # Explicitly unmapped

    # Unknown feature
    return None


def is_unmapped(feature_name: str) -> bool:
    """Check if a feature is explicitly unmapped.

    Args:
        feature_name: Extractor feature name

    Returns:
        True if feature is in unmapped_features list
    """
    feature_map = load_feature_map()
    return feature_name in feature_map.get('unmapped_features', {})


def get_unmapped_features() -> Dict:
    """Get all unmapped features with metadata.

    Returns:
        Dict of {feature_name: {unmapped, description, potential_parent}}
    """
    feature_map = load_feature_map()
    return feature_map.get('unmapped_features', {})


def is_sensitive_feature(feature_name: str) -> bool:
    """Check if a feature is marked as sensitive.

    Args:
        feature_name: Extractor feature name

    Returns:
        True if feature requires special governance
    """
    feature_map = load_feature_map()
    governance = feature_map.get('governance', {})
    sensitive = governance.get('sensitive_features', [])
    return feature_name in sensitive


def requires_consent(feature_name: str) -> bool:
    """Check if a feature requires explicit user consent.

    Args:
        feature_name: Extractor feature name

    Returns:
        True if feature requires consent
    """
    feature_map = load_feature_map()
    governance = feature_map.get('governance', {})
    consent = governance.get('consent_requirements', [])
    return feature_name in consent
