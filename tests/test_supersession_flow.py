import pathlib
import sys
from datetime import datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from ReDNACoreDemo.core.ingest.policy import apply_supersession


def iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def test_conflict_then_confirmation_flow():
    trait = "PaDNA.EyeDNA.IrisColor"
    blue_record = {
        "value": {"enum": "blue"},
        "status": "stable",
        "last_confirmed_at": iso_now(),
        "history": [],
    }

    first_event = {
        "value": {"enum": "green"},
        "source": "chat:user",
        "ts": iso_now(),
        "_reliability": 0.5,
    }

    decision1 = apply_supersession(trait, blue_record, first_event)
    assert decision1.action == "contradiction"
    assert decision1.new_status == "contradicted"
    assert decision1.history_entry is not None

    photo_conflict = {
        "value": {"enum": "green"},
        "source": "photo:analysis",
        "ts": iso_now(),
        "_reliability": 0.9,
    }

    decision_supersede = apply_supersession(trait, blue_record, photo_conflict)
    assert decision_supersede.action == "superseded"
    assert decision_supersede.new_status == "superseded"

    interim_trait = {
        "value": {"enum": "green"},
        "status": decision1.new_status,
        "history": [decision1.history_entry],
    }

    decision2 = apply_supersession(trait, interim_trait, photo_conflict)
    assert decision2.action == "reinforced"
    assert decision2.new_status == "stable"
    assert decision2.last_confirmed_at is not None
