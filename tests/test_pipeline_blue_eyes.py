import json
import uuid
from pathlib import Path

from ReDNACoreDemo.core.resolver.impl import resolve_roundtrip


def test_pipeline_blue_eyes():
    fixture_path = Path("ReDNACoreDemo/core/resolver/tests/golden_blue_eyes.json")
    fixture = json.loads(fixture_path.read_text())

    user_id = f"test_blue_eyes_{uuid.uuid4().hex[:8]}"
    evidence = fixture["evidence"]
    trait_id = "PaDNA.EyeDNA.IrisColor"

    result = resolve_roundtrip(user_id, evidence, source="test")
    resolved_trait = result["resolved"][trait_id]

    assert resolved_trait["value"] == {"enum": "blue"}
    assert resolved_trait["ucn"] >= 0.2
