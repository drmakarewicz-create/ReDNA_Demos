from src.vision.renderer_mappings import to_palette


def test_palette_mapping_blonde_fair_blue():
    resolved = {
        "PaDNA.HairDNA.Color": "Light blonde",
        "PaDNA.SkinDNA.Tone": "Fair",
        "PaDNA.SkinDNA.Undertone": "Neutral",
        "PaDNA.EyeDNA.IrisColor": "Blue",
        "PaDNA.FacialDNA.Lips": "Natural pink",
    }

    palette_info = to_palette(resolved)
    palette = palette_info["palette"]

    assert palette["hair"]["base"] == "#E7D18D"
    assert palette["skin"]["fill"] == "#F0CDBB"
    assert palette["eyes"]["iris"].startswith("#5A")  # blue ramp
    assert palette_info["palette_keys"]["hair"].startswith("light")
    assert palette_info["feature_toggles"]["show_freckles"] is False


def test_palette_mapping_redhead_warm_green():
    resolved = {
        "PaDNA.HairDNA.Color": "Strawberry Blonde",
        "PaDNA.SkinDNA.Tone": "Medium",
        "PaDNA.SkinDNA.Undertone": "Warm",
        "PaDNA.EyeDNA.IrisColor": "Hazel",
        "PaDNA.FacialDNA.Lips": "Rose",
        "PaDNA.SkinDNA.Freckles": "present",
    }

    palette_info = to_palette(resolved)

    assert palette_info["palette_keys"]["hair"] == "strawberry_blonde"
    assert palette_info["palette_keys"]["skin"].endswith("_warm")
    assert palette_info["palette_keys"]["eyes"] == "hazel"
    assert palette_info["feature_toggles"]["show_freckles"] is True
