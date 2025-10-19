import pathlib
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from ReDNACoreDemo.core.api import build_app


client = TestClient(build_app())


def test_ingest_good_roundtrip():
    response = client.post(
        "/core/api/ingest_evidence",
        json={
            "user_id": "contract_user",
            "evidence": [
                {
                    "trait_id": "PaDNA.EyeDNA.IrisColor",
                    "value": {"enum": "blue"},
                    "source": "test",
                }
            ],
        },
    )
    assert response.status_code == 200, response.text

    payload = response.json()
    assert payload.get("ok") is True
    assert payload.get("ingested", 0) >= 1
    traits = payload.get("snapshot", {}).get("traits", [])
    assert any(trait.get("trait_id") == "PaDNA.EyeDNA.IrisColor" for trait in traits)


def test_ingest_bad_validation():
    response = client.post(
        "/core/api/ingest_evidence",
        json={
            "user_id": "contract_user",
            "evidence": [
                {
                    "value": {"text": "free text only"},
                }
            ],
        },
    )
    assert response.status_code == 400

    payload = response.json()
    assert payload.get("error") == "EVIDENCE_VALIDATION_FAILED"
