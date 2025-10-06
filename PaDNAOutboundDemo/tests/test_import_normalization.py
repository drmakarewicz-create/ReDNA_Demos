from __future__ import annotations

from pathlib import Path

from PhotoRefinementCoach.src.importer import load_and_validate

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


def json_bytes(obj: dict) -> bytes:
    import json

    return json.dumps(obj).encode("utf-8")


def test_import_normalizes_map_shape():
    payload = {
        "user_id": "test-user",
        "observations": {
            "Hair.Color": {"resolved_value": "Honey", "ucn": 840},
            "PaDNA.EyeDNA.IrisColor": {"value": "Hazel"},
        },
    }

    normalized, report, errors = load_and_validate(json_bytes(payload))

    assert not errors
    observations = normalized["observations"]
    assert observations["PaDNA.HairDNA.Color"]["resolved_value"] == "Honey"
    assert observations["PaDNA.EyeDNA.IrisColor"]["resolved_value"] == "Hazel"
    assert report["observations"]["count"] == 2


def test_import_normalizes_list_shape():
    payload = {
        "user_id": "list-user",
        "observations": [
            {"path": "Skin.Tone", "resolved_value": "Fair", "ucn": 905},
            {"path": "PaDNA.ApparelDNA.Style", "resolved_value": "classic"},
        ],
    }

    normalized, report, errors = load_and_validate(json_bytes(payload))

    assert not errors
    observations = normalized["observations"]
    assert observations["PaDNA.SkinDNA.Tone"]["resolved_value"] == "Fair"
    assert observations["PaDNA.ApparelDNA.Style"]["resolved_value"] == "classic"
    assert report["observations"]["count"] == 2


def test_import_legacy_value_field():
    payload = {
        "user_id": "legacy-user",
        "observations": {
            "Hair.Length": {"value": "shoulder"}
        },
    }

    normalized, _, errors = load_and_validate(json_bytes(payload))
    assert not errors
    trait = normalized["observations"]["PaDNA.HairDNA.Length"]
    assert trait["resolved_value"] == "shoulder"


def test_import_path_mapping_to_padna():
    payload = {
        "user_id": "map-user",
        "observations": {
            "hair.color": {"resolved_value": "ash"}
        },
    }

    normalized, _, errors = load_and_validate(json_bytes(payload))
    assert not errors
    assert "PaDNA.HairDNA.Color" in normalized["observations"]


def test_import_rejects_unknown_keys_but_reports(tmp_path):
    fixture_bytes = FIXTURE_DIR.joinpath("photo_import_sample.json").read_bytes()
    normalized, report, errors = load_and_validate(fixture_bytes)

    assert not errors
    assert "PaDNA.HairDNA.Color" in normalized["observations"]
    assert "PaDNA.EyeDNA.Color" in normalized["observations"]

    discarded = normalized.get("discarded") or []
    assert any(entry.get("path") == "Unknown.Key" for entry in discarded)

    unmapped = normalized.get("unmapped") or []
    assert any(entry.get("path") == "Unknown.Key" for entry in unmapped)

    assert report["unmapped"]["count"] == 1
