import shutil
from pathlib import Path

from ReDNACoreDemo.core.ingest.pipeline import ingest_evidence_roundtrip
from ReDNACoreDemo.core.ingest.fallback_lex import fallback_extract
from ReDNACoreDemo.core.storage import USERS_DIR, CHECKPOINTS_DIR, read_user_state


def test_ingest_filters_invalid_observations():
    user_id = "test_ingest_filters"
    evidence = [
        {
            "trait_category": "preferences",
            "signal": "likes tall",
            "confidence": 80,
        },
        {
            "trait_category": "preferences",
            "signal": "neutral bald",
            "confidence": 60,
        },
        {
            "trait_id": "attributes.physical.height",
            "fact_value": "6 feet tall",
            "confidence": 100,
            "raw_text": "I am 6 feet tall and pretty bald",
            "timestamp": "2025-10-14T18:53:42+00:00",
            "extraction_method": "llm",
            "signal": "physical.height: 6 feet tall",
        },
    ]

    try:
        result = ingest_evidence_roundtrip(user_id, "chat", evidence, req_id="test-filter")
        assert result["ok"]
        assert result["ingested"] == 1
        resolved, _, _ = read_user_state(user_id)
        height = resolved.get("attributes.physical.height")
        assert height is not None
        assert height.get("value", {}).get("text") == "6 feet tall"
    finally:
        for base in (USERS_DIR, CHECKPOINTS_DIR):
            target = Path(base) / user_id
            if target.exists():
                shutil.rmtree(target, ignore_errors=True)


def test_fallback_detects_bald_statements():
    items = fallback_extract("I am 6 feet tall and pretty bald these days.")
    trait_ids = {item.get("trait_id") for item in items}
    assert "PaDNA.HairDNA.Bald" in trait_ids
