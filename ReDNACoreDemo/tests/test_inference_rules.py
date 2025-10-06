from __future__ import annotations

from core import inference_rules


def test_inference_rules_generate_suggestion():
    resolved = {
        "PaDNA.HairDNA.Color": {"value": "Blonde"},
        "PaDNA.SkinDNA.Undertone": {"value": "Warm"},
    }
    suggestions = inference_rules.infer(resolved)
    assert any(s.path == "PaDNA.EyeDNA.Brows" for s in suggestions), "Expected brow suggestion"


def test_rule_count_exposed():
    assert inference_rules.rule_count() >= 0
