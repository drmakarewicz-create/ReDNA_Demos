import pathlib
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from ReDNACoreDemo.core.ingest.policy import should_persist_raw


def iso_days_ago(days: int) -> str:
    ts = datetime.now(timezone.utc) - timedelta(days=days)
    return ts.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def test_high_importance_conflict_is_hot():
    evidence = {
        "trait_id": "PaDNA.EyeDNA.IrisColor",
        "value": {"enum": "green"},
        "source": "photo:analysis",
        "ts": iso_days_ago(1),
    }
    existing = {
        "value": {"enum": "blue"},
        "status": "stable",
    }

    decision = should_persist_raw(evidence, existing=existing)
    assert decision["tier"] == "hot"
    assert decision["ttl_days"] == 365
    assert decision["conflict"] is True


def test_low_priority_redundant_is_cold_or_drop():
    evidence = {
        "trait_id": "PaDNA.LifestyleDNA.SleepSchedule",
        "value": {"enum": "early_riser"},
        "source": "chat:user",
        "ts": iso_days_ago(10),
    }
    existing = {
        "value": {"enum": "early_riser"},
        "status": "stable",
    }

    decision = should_persist_raw(evidence, existing=existing)
    assert decision["tier"] in {"cold", "drop"}
    if decision["tier"] == "drop":
        assert decision["ttl_days"] == 0


def test_old_evidence_drops_when_no_conflict():
    evidence = {
        "trait_id": "PaDNA.InterestsDNA.Reading",
        "value": {"enum": "low"},
        "source": "chat:user",
        "ts": iso_days_ago(400),
    }

    decision = should_persist_raw(evidence, existing=None)
    assert decision["tier"] == "drop"
    assert decision["ttl_days"] == 0


def test_pending_resolution_kept_hot():
    evidence = {
        "trait_id": "PaDNA.EyeDNA.IrisColor",
        "value": {"enum": "green"},
        "source": "chat:user",
        "ts": iso_days_ago(2),
    }
    existing = {
        "value": {"enum": "blue"},
        "status": "contradicted",
    }

    decision = should_persist_raw(evidence, existing=existing)
    assert decision["tier"] == "hot"


def test_ttl_variants_cover_all_tiers():
    evidence = {
        "trait_id": "PaDNA.FitnessDNA.Preferences",
        "value": {"enum": "gym"},
        "source": "coach:auto",
        "ts": iso_days_ago(5),
    }
    decision = should_persist_raw(evidence, existing=None)
    tiers = {
        "hot": 365,
        "warm": 180,
        "cold": 60,
        "drop": 0,
    }
    assert decision["ttl_days"] == tiers[decision["tier"]]
