from ExplorerFinal.ui.persona_router import compose_system_prompt


def test_relationship_coach_identity_guard():
    persona = {
        "id": "relationship_coach",
        "title": "Relationship Coach",
        "prompt": "Voice: warm and plain.",
    }
    prompt = compose_system_prompt(
        persona,
        dev_mode=False,
        user_context={},
        persona_id="relationship_coach",
        display_name="Relationship Coach",
    )
    assert "Relationship Coach" in prompt
    assert "You are NOT the Head Coach" in prompt
    assert "As your Head Coach" not in prompt


def test_to_plain_handles_dataclass_for_telemetry():
    from dataclasses import dataclass

    from ReDNACoreDemo.core.persona_registry import to_plain

    @dataclass
    class Sample:
        value: str = "demo"

    assert to_plain(Sample()) == {"value": "demo"}
