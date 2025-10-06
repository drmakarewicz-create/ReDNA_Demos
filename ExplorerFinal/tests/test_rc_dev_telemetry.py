from __future__ import annotations

from types import SimpleNamespace

import pytest

import ReDNACoreDemo.core.persona_registry as pr_module
from ReDNACoreDemo.core.persona_registry import (
    PersonaRecord,
    get_last_registered,
    to_plain,
)


def test_to_plain_handles_pydantic():
    try:
        from pydantic import BaseModel
    except Exception:  # pragma: no cover - optional dependency
        pytest.skip("pydantic not available")

    class SampleModel(BaseModel):
        value: str = "demo"

    assert to_plain(SampleModel()) == {"value": "demo"}


def test_to_plain_handles_object_with_dict():
    class Sample:
        def __init__(self) -> None:
            self.value = "demo"

    assert to_plain(Sample()) == {"value": "demo"}


def test_get_last_registered_returns_latest():
    original_registry = pr_module._REGISTRY
    original_last = pr_module._LAST_REGISTERED_ID
    try:
        fake_config = SimpleNamespace(
            id="relationship_coach",
            version="0.1.0",
            data_dependencies=SimpleNamespace(bundle=["padna.traits.example"], session=[]),
            prompt_assets=SimpleNamespace(system="prompts/relationship_coach/system.md"),
            lifecycle=SimpleNamespace(beta=True, requires_head_coach_supervision=True),
        )
        pr_module._REGISTRY = {
            "relationship_coach": PersonaRecord(config=fake_config, summary=None, raw={})
        }
        pr_module._LAST_REGISTERED_ID = "relationship_coach"

        result = get_last_registered()
        assert result is fake_config
        assert get_last_registered("relationship_coach") is fake_config
    finally:
        pr_module._REGISTRY = original_registry
        pr_module._LAST_REGISTERED_ID = original_last
