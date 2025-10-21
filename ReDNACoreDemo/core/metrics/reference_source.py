"""
Pluggable RR Reference Population (Synthetic ↔ Actual) + Safety (Phase 10.1)

Provides a unified interface for loading reference population CDFs from:
- SYNTHETIC: Pre-generated distributions (universes: combined, low, medium, high)
- ACTUAL: Live user population data with cohort support

Features:
- Intelligent fallback (ACTUAL → SYNTHETIC if insufficient data)
- Cohort-based segmentation (age, region, language, etc.)
- Caching with TTL for performance
- Safety guards (min samples, max age, staleness checks)
- Comprehensive metadata for lineage tracking
"""

from __future__ import annotations
import bisect
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict

logger = logging.getLogger(__name__)

# Configuration (with sane defaults)
RR_REFERENCE_SOURCE = os.getenv("RR_REFERENCE_SOURCE", "SYNTHETIC").upper()
RR_REFERENCE_UNIVERSE = os.getenv("RR_REFERENCE_UNIVERSE", "combined")
RR_REFERENCE_COHORT_KEYS = os.getenv("RR_REFERENCE_COHORT_KEYS", "")  # e.g., "age,region"
RR_ACTUAL_MIN_SAMPLES = int(os.getenv("RR_ACTUAL_MIN_SAMPLES", "5000"))
RR_ACTUAL_MAX_AGE_DAYS = int(os.getenv("RR_ACTUAL_MAX_AGE_DAYS", "90"))
RR_REFERENCE_PATH = Path(os.getenv(
    "RR_REFERENCE_PATH",
    str(Path(__file__).parent.parent.parent.parent / "data" / "reference_pop")
))

# Cache with TTL (15 minutes default)
_CACHE_TTL_SECONDS = 15 * 60
_CDF_CACHE: Dict[str, Tuple[datetime, 'ReferenceCDF']] = {}


@dataclass
class ReferenceCDF:
    """
    Reference population cumulative distribution function.

    Attributes:
        samples: Sorted list of UCN values (0.0-1.0)
        n_samples: Number of samples
        source: "SYNTHETIC" or "ACTUAL"
        universe: Universe name (for synthetic) or None
        cohort_keys: List of cohort dimension names (e.g., ["age", "region"])
        cohort_values: Dict of cohort dimension values (e.g., {"age": "25-34", "region": "NA"})
        generated_at: Timestamp of CDF generation
        expiry: Optional expiration timestamp
        fallback_reason: Optional reason if fell back from ACTUAL to SYNTHETIC
        metadata: Additional metadata
    """
    samples: List[float] = field(default_factory=list)
    n_samples: int = 0
    source: str = "SYNTHETIC"  # "SYNTHETIC" or "ACTUAL"
    universe: Optional[str] = None  # "combined", "low", "medium", "high" (synthetic only)
    cohort_keys: List[str] = field(default_factory=list)
    cohort_values: Dict[str, str] = field(default_factory=dict)
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expiry: Optional[str] = None
    fallback_reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def percentile_for_ucn(self, ucn_value: float) -> float:
        """
        Compute percentile for given UCN value using CDF.

        Args:
            ucn_value: UCN value (0.0-1.0)

        Returns:
            Percentile 0-100 representing % of reference population with lower UCN
        """
        if not self.samples or self.n_samples == 0:
            return 50.0  # Default middle percentile

        # Use bisect to find position in sorted samples
        pos = bisect.bisect_left(self.samples, ucn_value)

        # Percentile = (position / total) * 100
        percentile = (pos / self.n_samples) * 100.0

        return max(0.0, min(100.0, percentile))  # Clamp to [0, 100]


def load_synthetic_reference(
    trait_id: str,
    universe: str = "combined",
    cohort_values: Optional[Dict[str, str]] = None
) -> Optional[ReferenceCDF]:
    """
    Load synthetic reference distribution from pre-generated files.

    File structure:
    - data/reference_pop/<trait_id>.json              (global/combined)
    - data/reference_pop/universes/<universe>/<trait_id>.json
    - data/reference_pop/cohorts/<cohort>/<trait_id>.json  (future)

    Args:
        trait_id: Trait identifier (e.g., "PaDNA.Chronotype")
        universe: Universe selector ("combined", "low", "medium", "high")
        cohort_values: Optional cohort dimensions (not used for synthetic in Phase 10.1)

    Returns:
        ReferenceCDF or None if not found
    """
    try:
        # Try universe-specific file first
        if universe and universe != "combined":
            universe_path = RR_REFERENCE_PATH / "universes" / universe / f"{trait_id}.json"
            if universe_path.exists():
                cdf = _load_synthetic_file(universe_path, trait_id, universe)
                if cdf:
                    return cdf

        # Try simplified trait name (e.g., "Chronotype" from "PaDNA.Chronotype")
        simplified = trait_id.split(".")[-1]

        if universe and universe != "combined":
            universe_path_simple = RR_REFERENCE_PATH / "universes" / universe / f"{simplified}.json"
            if universe_path_simple.exists():
                cdf = _load_synthetic_file(universe_path_simple, trait_id, universe)
                if cdf:
                    return cdf

        # Fallback: try global/combined distribution
        global_path = RR_REFERENCE_PATH / f"{trait_id}.json"
        if global_path.exists():
            return _load_synthetic_file(global_path, trait_id, "combined")

        # Try simplified name in global
        global_path_simple = RR_REFERENCE_PATH / f"{simplified}.json"
        if global_path_simple.exists():
            return _load_synthetic_file(global_path_simple, trait_id, "combined")

        # Fallback: try generic.json as last resort
        generic_path = RR_REFERENCE_PATH / "generic.json"
        if generic_path.exists():
            logger.warning(f"[RR-Reference] No specific distribution for {trait_id}, using generic")
            cdf = _load_synthetic_file(generic_path, trait_id, "combined")
            if cdf:
                cdf.metadata["fallback"] = "generic"
                return cdf

        logger.warning(f"[RR-Reference] No synthetic distribution found for {trait_id}")
        return None

    except Exception as e:
        logger.error(f"[RR-Reference] Failed to load synthetic reference for {trait_id}: {e}", exc_info=True)
        return None


def _load_synthetic_file(
    file_path: Path,
    trait_id: str,
    universe: str
) -> Optional[ReferenceCDF]:
    """Load and parse a synthetic reference file."""
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)

        samples = []

        if "samples" in data:
            samples = sorted(data["samples"])  # Ensure sorted

        elif "hist" in data:
            # Convert histogram to samples (expand bins)
            for bin_data in data["hist"]:
                if len(bin_data) >= 3:
                    lo, hi, count = bin_data[0], bin_data[1], int(bin_data[2])
                    if count > 0:
                        step = (hi - lo) / count if count > 1 else 0
                        for i in range(count):
                            samples.append(lo + i * step)
            samples = sorted(samples)

        if not samples:
            logger.warning(f"[RR-Reference] Empty samples in {file_path}")
            return None

        return ReferenceCDF(
            samples=samples,
            n_samples=len(samples),
            source="SYNTHETIC",
            universe=universe,
            cohort_keys=[],
            cohort_values={},
            generated_at=datetime.now(timezone.utc).isoformat(),
            metadata={
                "file_path": str(file_path),
                "trait_id": trait_id,
            }
        )

    except Exception as e:
        logger.error(f"[RR-Reference] Failed to parse {file_path}: {e}")
        return None


def load_actual_reference(
    trait_id: str,
    cohort_values: Optional[Dict[str, str]] = None
) -> Optional[ReferenceCDF]:
    """
    Load actual reference distribution from live user population.

    Scans data/users/*/resolved.json and/or belief graph snapshots to build
    a CDF from real user data.

    Args:
        trait_id: Trait identifier
        cohort_values: Optional cohort dimension values (e.g., {"age": "25-34", "region": "NA"})

    Returns:
        ReferenceCDF or None if insufficient data

    Behavior:
        - Scans all users for this trait
        - Applies filters: recency ≤ RR_ACTUAL_MAX_AGE_DAYS
        - Requires N ≥ RR_ACTUAL_MIN_SAMPLES
        - Persists histogram to data/reference_pop/actual/<cohort>/<trait>.json
        - Returns None if insufficient samples (caller should fallback to synthetic)
    """
    try:
        # Check if we have a pre-computed actual reference
        cached_actual = _load_actual_cache(trait_id, cohort_values)
        if cached_actual:
            return cached_actual

        # Build from live data
        logger.info(f"[RR-Reference] Building ACTUAL reference for {trait_id} (this may take a moment...)")

        samples = _scan_user_population(trait_id, cohort_values)

        if len(samples) < RR_ACTUAL_MIN_SAMPLES:
            logger.warning(
                f"[RR-Reference] ACTUAL has only {len(samples)} samples for {trait_id}, "
                f"need {RR_ACTUAL_MIN_SAMPLES} minimum"
            )
            return None

        samples_sorted = sorted(samples)

        # Build CDF
        cdf = ReferenceCDF(
            samples=samples_sorted,
            n_samples=len(samples_sorted),
            source="ACTUAL",
            universe=None,
            cohort_keys=list(cohort_values.keys()) if cohort_values else [],
            cohort_values=cohort_values or {},
            generated_at=datetime.now(timezone.utc).isoformat(),
            expiry=(datetime.now(timezone.utc) + timedelta(days=RR_ACTUAL_MAX_AGE_DAYS)).isoformat(),
            metadata={
                "trait_id": trait_id,
                "max_age_days": RR_ACTUAL_MAX_AGE_DAYS,
            }
        )

        # Persist to cache file
        _persist_actual_cache(trait_id, cohort_values, cdf)

        logger.info(f"[RR-Reference] Built ACTUAL reference for {trait_id}: {cdf.n_samples} samples")

        return cdf

    except Exception as e:
        logger.error(f"[RR-Reference] Failed to load actual reference for {trait_id}: {e}", exc_info=True)
        return None


def _scan_user_population(
    trait_id: str,
    cohort_values: Optional[Dict[str, str]]
) -> List[float]:
    """
    Scan user population for UCN samples of a given trait.

    Args:
        trait_id: Trait to scan for
        cohort_values: Optional cohort filters

    Returns:
        List of UCN values (0.0-1.0)
    """
    from ..storage import ensure_dirs_for_user

    samples = []
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=RR_ACTUAL_MAX_AGE_DAYS)

    # Get users directory
    data_root = Path(__file__).parent.parent.parent.parent / "data" / "users"

    if not data_root.exists():
        logger.warning(f"[RR-Reference] Users directory not found: {data_root}")
        return samples

    # Scan all user directories
    for user_dir in data_root.iterdir():
        if not user_dir.is_dir():
            continue

        user_id = user_dir.name

        # Try loading resolved.json
        resolved_path = user_dir / "resolved.json"
        if resolved_path.exists():
            try:
                with open(resolved_path, 'r') as f:
                    resolved_data = json.load(f)

                # Check trait exists and has UCN
                traits = resolved_data.get("traits", [])
                for trait in traits:
                    if trait.get("trait_id") == trait_id:
                        ucn = trait.get("ucn")
                        if ucn and isinstance(ucn, dict):
                            # Extract N (normalized UCN) as the sample value
                            n_value = ucn.get("n")
                            if n_value is not None:
                                # Check recency (if we have timestamp)
                                timestamp_str = trait.get("timestamp")
                                if timestamp_str:
                                    try:
                                        timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                                        if timestamp < cutoff_date:
                                            continue  # Too old
                                    except:
                                        pass  # Can't parse timestamp, include anyway

                                samples.append(float(n_value))
                                break  # Found trait, no need to continue

            except Exception as e:
                logger.debug(f"[RR-Reference] Failed to read {resolved_path}: {e}")

    return samples


def _load_actual_cache(
    trait_id: str,
    cohort_values: Optional[Dict[str, str]]
) -> Optional[ReferenceCDF]:
    """Load pre-computed actual reference from cache file."""
    try:
        cache_path = _get_actual_cache_path(trait_id, cohort_values)

        if not cache_path.exists():
            return None

        with open(cache_path, 'r') as f:
            data = json.load(f)

        # Check if expired
        expiry_str = data.get("expiry")
        if expiry_str:
            try:
                expiry = datetime.fromisoformat(expiry_str.replace("Z", "+00:00"))
                if datetime.now(timezone.utc) > expiry:
                    logger.info(f"[RR-Reference] ACTUAL cache expired for {trait_id}")
                    return None
            except:
                pass

        # Check minimum samples
        n_samples = data.get("n", 0)
        if n_samples < RR_ACTUAL_MIN_SAMPLES:
            logger.warning(f"[RR-Reference] ACTUAL cache has insufficient samples: {n_samples}")
            return None

        samples = data.get("samples", [])
        if not samples:
            return None

        return ReferenceCDF(
            samples=sorted(samples),
            n_samples=n_samples,
            source="ACTUAL",
            universe=None,
            cohort_keys=data.get("cohort_keys", []),
            cohort_values=data.get("cohort_values", {}),
            generated_at=data.get("generated_at", datetime.now(timezone.utc).isoformat()),
            expiry=expiry_str,
            metadata=data.get("metadata", {})
        )

    except Exception as e:
        logger.debug(f"[RR-Reference] Failed to load actual cache for {trait_id}: {e}")
        return None


def _persist_actual_cache(
    trait_id: str,
    cohort_values: Optional[Dict[str, str]],
    cdf: ReferenceCDF
) -> None:
    """Persist actual reference CDF to cache file."""
    try:
        cache_path = _get_actual_cache_path(trait_id, cohort_values)
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "generated_at": cdf.generated_at,
            "n": cdf.n_samples,
            "trait_id": trait_id,
            "cohort_keys": cdf.cohort_keys,
            "cohort_values": cdf.cohort_values,
            "expiry": cdf.expiry,
            "min_age_days": RR_ACTUAL_MAX_AGE_DAYS,
            "samples": cdf.samples,  # Store full samples for now (can optimize to histogram later)
            "metadata": cdf.metadata
        }

        with open(cache_path, 'w') as f:
            json.dump(data, f, indent=2)

        logger.debug(f"[RR-Reference] Persisted ACTUAL cache to {cache_path}")

    except Exception as e:
        logger.warning(f"[RR-Reference] Failed to persist actual cache: {e}")


def _get_actual_cache_path(
    trait_id: str,
    cohort_values: Optional[Dict[str, str]]
) -> Path:
    """Get cache file path for actual reference."""
    base_path = RR_REFERENCE_PATH / "actual"

    if cohort_values:
        # Build cohort subdirectory name from sorted keys
        cohort_parts = []
        for key in sorted(cohort_values.keys()):
            value = cohort_values[key]
            cohort_parts.append(f"{key}={value}")
        cohort_dir = ",".join(cohort_parts)
        cache_path = base_path / cohort_dir / f"{trait_id}.json"
    else:
        # Global (no cohort)
        cache_path = base_path / "global" / f"{trait_id}.json"

    return cache_path


def get_reference_cdf(
    trait_id: str,
    cohort_values: Optional[Dict[str, str]] = None
) -> Tuple[ReferenceCDF, Optional[str]]:
    """
    Get reference CDF with intelligent source selection and fallback.

    Router logic:
    1. If RR_REFERENCE_SOURCE == "ACTUAL":
       - Try load_actual_reference()
       - If N ≥ RR_ACTUAL_MIN_SAMPLES: return ACTUAL
       - Else: fallback to SYNTHETIC with fallback_reason
    2. Else (SYNTHETIC):
       - Return load_synthetic_reference()

    Args:
        trait_id: Trait identifier
        cohort_values: Optional cohort dimension values

    Returns:
        Tuple of (ReferenceCDF, fallback_reason)
        fallback_reason is set if we fell back from ACTUAL to SYNTHETIC
    """
    # Check cache first
    cache_key = _build_cache_key(trait_id, cohort_values)
    cached = _check_cache(cache_key)
    if cached:
        return cached

    fallback_reason = None

    if RR_REFERENCE_SOURCE == "ACTUAL":
        # Try actual first
        cdf = load_actual_reference(trait_id, cohort_values)

        if cdf and cdf.n_samples >= RR_ACTUAL_MIN_SAMPLES:
            # Success!
            _cache_cdf(cache_key, cdf, fallback_reason)
            return cdf, fallback_reason

        # Insufficient actual data, fallback to synthetic
        if cdf and cdf.n_samples < RR_ACTUAL_MIN_SAMPLES:
            fallback_reason = "insufficient_samples"
        elif not cdf:
            fallback_reason = "no_actual_data"

        logger.info(
            f"[RR-Reference] Falling back from ACTUAL to SYNTHETIC for {trait_id} "
            f"(reason: {fallback_reason})"
        )

    # Use synthetic (either by config or fallback)
    cdf = load_synthetic_reference(trait_id, RR_REFERENCE_UNIVERSE, cohort_values)

    if not cdf:
        # Last resort: create default CDF
        logger.warning(f"[RR-Reference] No reference found for {trait_id}, using default")
        cdf = ReferenceCDF(
            samples=[i / 100.0 for i in range(101)],  # Uniform 0-1
            n_samples=101,
            source="SYNTHETIC",
            universe="default",
            metadata={"fallback": "default_uniform"}
        )
        fallback_reason = fallback_reason or "no_reference_found"

    _cache_cdf(cache_key, cdf, fallback_reason)

    return cdf, fallback_reason


def _build_cache_key(trait_id: str, cohort_values: Optional[Dict[str, str]]) -> str:
    """Build cache key from trait_id and cohort_values."""
    if not cohort_values:
        return f"{RR_REFERENCE_SOURCE}:{trait_id}"

    cohort_parts = []
    for key in sorted(cohort_values.keys()):
        cohort_parts.append(f"{key}={cohort_values[key]}")
    cohort_str = ",".join(cohort_parts)

    return f"{RR_REFERENCE_SOURCE}:{trait_id}:{cohort_str}"


def _check_cache(cache_key: str) -> Optional[Tuple[ReferenceCDF, Optional[str]]]:
    """Check if CDF is in cache and not expired."""
    if cache_key in _CDF_CACHE:
        timestamp, cdf, fallback_reason = _CDF_CACHE[cache_key]
        age = (datetime.now(timezone.utc) - timestamp).total_seconds()

        if age < _CACHE_TTL_SECONDS:
            logger.debug(f"[RR-Reference] Cache hit for {cache_key} (age={age:.1f}s)")
            return cdf, fallback_reason

        # Expired
        logger.debug(f"[RR-Reference] Cache expired for {cache_key} (age={age:.1f}s)")
        del _CDF_CACHE[cache_key]

    return None


def _cache_cdf(cache_key: str, cdf: ReferenceCDF, fallback_reason: Optional[str]) -> None:
    """Cache CDF with timestamp."""
    _CDF_CACHE[cache_key] = (datetime.now(timezone.utc), cdf, fallback_reason)
    logger.debug(f"[RR-Reference] Cached {cache_key}")


def log_reference_config():
    """Log reference source configuration at startup."""
    cohort_keys = [k.strip() for k in RR_REFERENCE_COHORT_KEYS.split(",") if k.strip()]

    if RR_REFERENCE_SOURCE == "ACTUAL":
        logger.info(
            f"[RR-Reference] source=ACTUAL cohorts={cohort_keys} "
            f"min_samples={RR_ACTUAL_MIN_SAMPLES} max_age_days={RR_ACTUAL_MAX_AGE_DAYS}"
        )
    else:
        logger.info(
            f"[RR-Reference] source=SYNTHETIC universe={RR_REFERENCE_UNIVERSE} "
            f"cohorts={cohort_keys} path={RR_REFERENCE_PATH}"
        )
