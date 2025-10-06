from pathlib import Path

import yaml

TRAITS_FILE = Path("ReDNACoreDemo/data/config/traits_registry.yaml")


def _load_traits():
    return yaml.safe_load(TRAITS_FILE.read_text())


def test_relationship_containers_exist():
    data = _load_traits()
    assert "RelDNA" in data, "RelDNA bucket missing from registry"
    rel = data["RelDNA"]
    required = [
        "Status",
        "Goals",
        "Preferences",
        "Conflict",
        "Communication",
        "Attachment",
        "Triggers",
        "Values",
        "Boundaries",
        "Safety",
        "Context",
        "Logistics",
        "MicroActions",
    ]
    for key in required:
        assert key in rel, f"RelDNA.{key} missing"

    status = rel["Status"]
    assert status["rr_default"] == 0
    assert status["curiosity_default"] == 100


def test_socialdna_conversation_controls():
    data = _load_traits()
    soc = data.get("SocDNA") or data.get("SocialDNA")
    assert soc is not None, "SocDNA bucket missing"
    convo = soc.get("Conversation")
    assert convo is not None, "SocDNA.Conversation missing"
    assert "ToneDefault" in convo
    assert convo["ToneDefault"]["curiosity_default"] == 100
