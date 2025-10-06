from __future__ import annotations

from src.vision.renderer_v2 import render_svg


def _bundle_from_traits(traits: dict[str, str]) -> dict[str, object]:
    descriptors = {path: {"value": value} for path, value in traits.items()}
    return {"results": {"descriptors": descriptors}}


def test_render_svg_blonde_fair_hazel():
    bundle = _bundle_from_traits(
        {
            "PaDNA.HairDNA.Color": "Light blonde",
            "PaDNA.SkinDNA.Tone": "Fair",
            "PaDNA.SkinDNA.Undertone": "Neutral",
            "PaDNA.EyeDNA.IrisColor": "Hazel",
        }
    )

    result = render_svg(bundle)

    palette = result["palette"]
    assert palette["hair"]["base"] == "#E7D18D"
    assert palette["skin"]["fill"] == "#F0CDBB"
    assert palette["eyes"]["iris"] == "#8A6E3E"

    # Apparel layer should be absent for classic style defaults.
    assert "M320,520" not in result["svg"]


def test_render_svg_brown_medium_brown():
    bundle = _bundle_from_traits(
        {
            "PaDNA.HairDNA.Color": "Brown",
            "PaDNA.SkinDNA.Tone": "Medium",
            "PaDNA.SkinDNA.Undertone": "Neutral",
            "PaDNA.EyeDNA.IrisColor": "Brown",
        }
    )

    result = render_svg(bundle)

    palette = result["palette"]
    assert palette["hair"]["base"] == "#473224"
    assert palette["skin"]["fill"] == "#C98E6B"
    assert palette["eyes"]["iris"] == "#513523"

    geometry = result["geometry"]
    assert geometry["hair"]["part"] == "center"
    assert geometry["eyes"]["shape"] in {"almond", "round"}
