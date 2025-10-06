"""Batch writer for cohort RR percentiles.

Scans stored user resolutions to extract cohort metadata (age range,
primary language, region) along with their associated Relationship Readiness
(RR) scores. Aggregates the RR distributions per cohort and writes summary
percentiles to ``data/_stats/cohort_rr.json``.

Usage::

    python3 ReDNACoreDemo/scripts/write_cohort_rr.py

The script is idempotent and will create the ``data/_stats`` directory when
needed.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


BASE_DIR = Path(__file__).resolve().parents[1]
USERS_STORAGE_DIR = BASE_DIR / "data" / "storage" / "users"
OUTPUT_DIR = BASE_DIR / "data" / "_stats"
OUTPUT_PATH = OUTPUT_DIR / "cohort_rr.json"

PERCENTILES = (0.1, 0.25, 0.5, 0.75, 0.9)


@dataclass(frozen=True)
class CohortSample:
    cohort_value: str
    rr: float


def _safe_percentile(sorted_values: List[float], fraction: float) -> float:
    """Return the percentile for a sorted list using linear interpolation."""

    if not sorted_values:
        raise ValueError("Cannot compute percentile on empty list")

    if len(sorted_values) == 1:
        return float(sorted_values[0])

    index = (len(sorted_values) - 1) * fraction
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return float(sorted_values[int(index)])

    lower_value = sorted_values[lower]
    upper_value = sorted_values[upper]
    return float(lower_value + (upper_value - lower_value) * (index - lower))


def _extract_entry(resolved_section: Dict[str, dict], key: str) -> Tuple[str | None, float | None]:
    entry = resolved_section.get(key) or {}
    value = entry.get("value") or entry.get("resolved_value") or entry.get("raw_value")
    if isinstance(value, str):
        value = value.strip()
    rr_value = entry.get("rr")
    if isinstance(rr_value, (int, float)):
        rr_value = float(rr_value)
    else:
        rr_value = None
    return value if value else None, rr_value


def collect_samples() -> Tuple[Dict[str, List[CohortSample]], Dict[str, int]]:
    cohorts: Dict[str, List[CohortSample]] = {"age": [], "language": [], "region": []}
    user_counts = {"age": 0, "language": 0, "region": 0}

    if not USERS_STORAGE_DIR.exists():
        return cohorts, user_counts

    for user_dir in USERS_STORAGE_DIR.iterdir():
        if not user_dir.is_dir():
            continue

        resolved_path = user_dir / "resolved.json"
        if not resolved_path.exists():
            continue

        try:
            payload = json.loads(resolved_path.read_text())
        except (json.JSONDecodeError, OSError):
            continue

        resolved_section = payload.get("resolved")
        if not isinstance(resolved_section, dict):
            continue

        age_value, age_rr = _extract_entry(resolved_section, "SocDNA.Demographics.AgeRange")
        lang_value, lang_rr = _extract_entry(resolved_section, "SocDNA.Prefs.LanguagePrimary")
        region_value, region_rr = _extract_entry(resolved_section, "SocDNA.Demographics.Region")

        if age_value and age_rr is not None:
            cohorts["age"].append(CohortSample(age_value, age_rr))
            user_counts["age"] += 1

        if lang_value and lang_rr is not None:
            cohorts["language"].append(CohortSample(lang_value, lang_rr))
            user_counts["language"] += 1

        if region_value and region_rr is not None:
            cohorts["region"].append(CohortSample(region_value, region_rr))
            user_counts["region"] += 1

    return cohorts, user_counts


def summarise(values: Iterable[float]) -> Dict[str, float | int]:
    data = sorted(float(v) for v in values)
    count = len(data)
    if count == 0:
        raise ValueError("Cannot summarise empty cohort")

    summary: Dict[str, float | int] = {
        "count": count,
        "mean": round(sum(data) / count, 3),
        "min": round(data[0], 3),
        "max": round(data[-1], 3),
    }

    for fraction in PERCENTILES:
        key = f"p{int(fraction * 100)}"
        summary[key] = round(_safe_percentile(data, fraction), 3)

    return summary


def build_payload() -> Dict[str, object]:
    cohorts, user_counts = collect_samples()
    cohort_stats: Dict[str, Dict[str, Dict[str, float | int]]] = {}

    for group, samples in cohorts.items():
        buckets: Dict[str, List[float]] = {}
        for sample in samples:
            buckets.setdefault(sample.cohort_value, []).append(sample.rr)

        stats = {
            bucket: summarise(values)
            for bucket, values in buckets.items()
        }
        cohort_stats[group] = dict(sorted(stats.items()))

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "storage/users",
        "sample_counts": user_counts,
        "percentiles": [int(p * 100) for p in PERCENTILES],
        "cohorts": cohort_stats,
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = build_payload()
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(f"[write_cohort_rr] wrote {OUTPUT_PATH.relative_to(BASE_DIR)}")


if __name__ == "__main__":
    main()
