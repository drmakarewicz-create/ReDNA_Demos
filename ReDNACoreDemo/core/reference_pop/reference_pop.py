"""
Reference population percentile calculations.

Provides UCN-to-percentile mapping based on synthetic or observed
reference distributions for each trait.
"""

import json
import os
from pathlib import Path
from typing import Optional
import bisect

# Cache for loaded distributions
_DISTRIBUTION_CACHE = {}

REFERENCE_POP_DIR = Path(__file__).parent.parent.parent.parent / "data" / "reference_pop"
REFERENCE_POP_SOURCE = os.getenv("REFERENCE_POP_SOURCE", "synthetic")


def load_distribution(trait_id: str) -> Optional[list]:
    """
    Load reference distribution for a trait.

    Looks for data/reference_pop/<trait_id>.json containing:
    - {"samples": [0.0, 0.1, ..., 1.0]}  (sorted UCN values)
    OR
    - {"hist": [[lo, hi, count], ...]}   (histogram bins)

    Returns sorted samples list or None if not found.
    """
    if trait_id in _DISTRIBUTION_CACHE:
        return _DISTRIBUTION_CACHE[trait_id]

    # Try loading the distribution file
    file_path = REFERENCE_POP_DIR / f"{trait_id}.json"
    if not file_path.exists():
        # Fallback: try simplified trait name (last component)
        simplified = trait_id.split(".")[-1]
        file_path = REFERENCE_POP_DIR / f"{simplified}.json"

    if not file_path.exists():
        _DISTRIBUTION_CACHE[trait_id] = None
        return None

    try:
        with open(file_path, 'r') as f:
            data = json.load(f)

        if "samples" in data:
            samples = sorted(data["samples"])  # Ensure sorted
            _DISTRIBUTION_CACHE[trait_id] = samples
            return samples

        elif "hist" in data:
            # Convert histogram to samples (expand bins)
            samples = []
            for bin_data in data["hist"]:
                if len(bin_data) >= 3:
                    lo, hi, count = bin_data[0], bin_data[1], int(bin_data[2])
                    # Add `count` samples uniformly distributed in [lo, hi]
                    if count > 0:
                        step = (hi - lo) / count if count > 1 else 0
                        for i in range(count):
                            samples.append(lo + i * step)
            samples = sorted(samples)
            _DISTRIBUTION_CACHE[trait_id] = samples
            return samples

    except Exception as e:
        print(f"Warning: Failed to load reference distribution for {trait_id}: {e}")

    _DISTRIBUTION_CACHE[trait_id] = None
    return None


def reference_percentile_for_ucn(trait_id: str, ucn_value: float) -> float:
    """
    Compute reference population percentile for a given UCN value.

    Args:
        trait_id: Trait identifier
        ucn_value: UCN value (typically 0.0-1.0)

    Returns:
        Percentile 0-100 representing % of reference population with lower UCN
    """
    samples = load_distribution(trait_id)

    if samples is None or len(samples) == 0:
        # No reference distribution available; return middle percentile
        return 50.0

    # Use bisect to find position in sorted samples
    # bisect_left gives us the count of samples < ucn_value
    pos = bisect.bisect_left(samples, ucn_value)

    # Percentile = (position / total) * 100
    percentile = (pos / len(samples)) * 100.0

    # Clamp to 0-100
    return max(0.0, min(100.0, percentile))


def reference_percentile(trait_id: str, user_id: str) -> float:
    """
    Get reference percentile for a user's trait.

    Looks up the user's current UCN for the trait and computes percentile.

    Args:
        trait_id: Trait identifier
        user_id: User identifier

    Returns:
        Percentile 0-100
    """
    # Look up user's UCN for this trait
    ucn_value = get_user_ucn(trait_id, user_id)

    if ucn_value is None:
        # No UCN available; return middle percentile
        return 50.0

    return reference_percentile_for_ucn(trait_id, ucn_value)


def get_user_ucn(trait_id: str, user_id: str) -> Optional[float]:
    """
    Fetch user's latest UCN value for a trait.

    This is a lightweight lookup that doesn't trigger full resolver logic.
    """
    from ReDNACoreDemo.core.storage import ensure_dirs_for_user

    user_dirs = ensure_dirs_for_user(user_id)
    user_dir = user_dirs["udir"]
    resolved_path = user_dir / "resolved.json"

    if not resolved_path.exists():
        return None

    try:
        with open(resolved_path, 'r') as f:
            resolved_data = json.load(f)

        # Look for trait in resolved traits
        traits = resolved_data.get("traits", {})
        trait_data = traits.get(trait_id)

        if trait_data and "ucn" in trait_data:
            ucn = trait_data["ucn"]
            if isinstance(ucn, (int, float)):
                return float(ucn)

    except Exception as e:
        print(f"Warning: Failed to load UCN for {user_id}/{trait_id}: {e}")

    return None
