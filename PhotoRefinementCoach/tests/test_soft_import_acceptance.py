import json
from pathlib import Path

import pytest

from PhotoRefinementCoach.src.importer import import_padna_soft


FIXTURES = Path(__file__).resolve().parents[2] / "docs"


def test_alias_and_normalization_mapping():
    payload = {
        "user_id": "acceptance_user",
        "observations": [
            {"path": "face.shape", "value": "oval"},
            {"path": "hair_colour", "value": "dirty blonde"},
            {"path": "body.height", "value": "5'6\""},
            {"path": "body.weight", "value": "130 lb"},
        ],
    }

    result = import_padna_soft(payload, strict=False)

    assert result.errors == []
    obs = result.observations

    assert "PaDNA.FacialDNA.FaceShape" in obs
    assert obs["PaDNA.FacialDNA.FaceShape"]["resolved_value"] == "Oval"

    assert "PaDNA.HairDNA.Color" in obs
    assert obs["PaDNA.HairDNA.Color"]["resolved_value"] == "Dirty Blonde"

    assert "PaDNA.BodyDNA.HeightCM" in obs
    assert pytest.approx(obs["PaDNA.BodyDNA.HeightCM"]["resolved_value"], rel=1e-2) == 167.64

    assert "PaDNA.BodyDNA.WeightKG" in obs
    assert pytest.approx(obs["PaDNA.BodyDNA.WeightKG"]["resolved_value"], rel=1e-2) == 58.97

    assert not result.quarantined
    assert result.raw_input_count == 4


def test_large_nested_bundle_maps_traits():
    bundle_path = FIXTURES / "ab-extensive.json"
    payload = json.loads(bundle_path.read_text())

    result = import_padna_soft(payload, strict=False)

    assert result.errors == []
    assert len(result.observations) >= 20
    assert not result.quarantined
    assert result.raw_input_count >= len(result.observations)
