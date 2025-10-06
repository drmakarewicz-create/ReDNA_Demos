from __future__ import annotations

from core import reconcile


def test_reconcile_noop():
    resolved = {
        "PaDNA.HairDNA.Color": {"value": "Blonde"}
    }
    issues = reconcile.find_contradictions(resolved)
    assert isinstance(issues, list)
    reconcile.apply(issues, resolved)
    assert resolved["PaDNA.HairDNA.Color"]["value"] == "Blonde"
