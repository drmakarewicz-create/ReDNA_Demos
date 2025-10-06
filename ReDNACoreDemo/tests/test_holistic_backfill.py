from __future__ import annotations

from copy import deepcopy

from core.holistic import run_holistic
from core import rr_engine


def _loader(_: str):
    resolved = {
        "user_id": "tester",
        "resolved": {
            "PaDNA.HairDNA.Color": {
                "value": "Blonde",
                "value_type": "string",
                "provenance": {"source": "photo"},
            },
            "PaDNA.SkinDNA.Undertone": {
                "value": "Warm",
                "value_type": "string",
                "provenance": {"source": "photo"},
            },
        },
    }
    evidence = {"items": []}
    flat = {"rows": []}
    return resolved, evidence, flat


def test_run_holistic_backfills_ucn_rr():
    state_holder = {}

    def loader(user_id: str):
        if state_holder:
            return deepcopy(state_holder["resolved"]), deepcopy(state_holder["evidence"]), deepcopy(state_holder["flat"])
        resolved, evidence, flat = _loader(user_id)
        state_holder["resolved"] = resolved
        state_holder["evidence"] = evidence
        state_holder["flat"] = flat
        return deepcopy(resolved), deepcopy(evidence), deepcopy(flat)

    report, resolved_doc, _evidence_doc, flat_doc = run_holistic(
        "tester",
        loader=loader,
        baselines={"defaults": {"mean": 700.0, "std": 150.0}},
        time_budget_ms=500,
    )

    assert report["ok"] is True
    entry = resolved_doc["resolved"]["PaDNA.HairDNA.Color"]
    assert entry["ucn"] >= rr_engine.MIN_PRESENT_UCN
    assert entry["rr"] >= rr_engine.MIN_PRESENT_RR
    assert entry["curiosity"] <= 95.0
    assert report["ucn_rr_updates"], "Expected update report"
    assert flat_doc["rows"], "Flat rows should be generated"

