import json
from datetime import datetime, timezone
from pathlib import Path

from ReDNACoreDemo.core.curiosity.curiosity_engine_v3 import CuriosityEngineV3, ReprioritizationEvent, ReprioritizationTrigger


def _sample_agenda() -> dict:
    return {
        "user_id": "demo",
        "items": [
            {
                "target": "CareerDNA.ManagementDNA",
                "priority": 0.4,
                "reason": "High data gap",
                "suggested_coach": "career_coach",
                "suggested_prompt": "Tell me about your current leadership responsibilities.",
                "evidence_refs": [],
            },
            {
                "target": "HealthDNA.SleepDNA",
                "priority": 0.35,
                "reason": "Moderate gap",
                "suggested_coach": "head_coach",
                "suggested_prompt": "Walk me through your sleep routine.",
                "evidence_refs": [],
            },
        ],
    }


def test_agenda_incorporates_debt(tmp_path: Path) -> None:
    engine = CuriosityEngineV3(data_root=tmp_path / "data")
    base = _sample_agenda()

    # Prime debt file and manually boost one container
    engine.generate_agenda("test_user", base_agenda=base)
    debt_file = tmp_path / "data" / "curiosity" / "debt" / "test_user.json"
    payload = json.loads(debt_file.read_text())
    sleep_entry = payload.setdefault("items", {}).setdefault(
        "HealthDNA.SleepDNA",
        {"score": 0.5, "last_seen": None},
    )
    sleep_entry["score"] = 0.9
    debt_file.write_text(json.dumps(payload))

    agenda = engine.generate_agenda(
        "test_user",
        limit=2,
        min_priority=0.2,
        base_agenda=base,
    )

    priorities = [item["priority"] for item in agenda["items"]]
    assert priorities[0] >= base["items"][0]["priority"]
    assert debt_file.exists()


def test_dynamic_reprioritisation_boost(tmp_path: Path) -> None:
    engine = CuriosityEngineV3(data_root=tmp_path / "data")
    base = _sample_agenda()
    event = ReprioritizationEvent(
        trigger=ReprioritizationTrigger.USER_MENTION,
        timestamp=datetime.now(timezone.utc),
        context={"topic": "sleep"},
    )

    agenda = engine.generate_agenda(
        "demo_user",
        limit=2,
        base_agenda=base,
        triggers=[event],
    )

    boosted_item = next(item for item in agenda["items"] if item["target"].endswith("SleepDNA"))
    assert boosted_item["priority"] > base["items"][1]["priority"]
    assert any(annotation["type"] == "trigger_boost" for annotation in boosted_item.get("annotations", []))


def test_daily_prompt_returns_top_debt(tmp_path: Path) -> None:
    engine = CuriosityEngineV3(data_root=tmp_path / "data")
    base = _sample_agenda()
    engine.generate_agenda("alice", base_agenda=base)

    prompt_payload = engine.generate_daily_prompt("alice")
    assert prompt_payload["prompt"] is not None
    assert prompt_payload["items"]
