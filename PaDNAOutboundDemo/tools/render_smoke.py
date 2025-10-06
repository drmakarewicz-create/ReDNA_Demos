"""Quick smoke-test harness for PaDNA renderer themes/palettes."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Dict

try:  # Optional dependency for PNG export
    import cairosvg  # type: ignore
except Exception:  # pragma: no cover - optional toolchain
    cairosvg = None  # type: ignore

from src.vision.renderer_v2 import render_svg

OUTPUT_DIR = Path(__file__).resolve().parent / "_smoke_outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SAMPLES = {
    "fair_blonde": {
        "padna": {
            "PaDNA.SkinDNA.Tone": "Fair",
            "PaDNA.SkinDNA.Undertone": "Neutral",
            "PaDNA.HairDNA.Color": "Light blonde",
            "PaDNA.EyeDNA.IrisColor": "Light brown",
            "PaDNA.FacialDNA.Lips": "Natural pink",
        },
    },
    "medium_strawberry": {
        "padna": {
            "PaDNA.SkinDNA.Tone": "Medium",
            "PaDNA.SkinDNA.Undertone": "Warm",
            "PaDNA.HairDNA.Color": "Strawberry blonde",
            "PaDNA.EyeDNA.IrisColor": "Hazel",
            "PaDNA.FacialDNA.Lips": "Rose",
            "PaDNA.SkinDNA.Freckles": "light",
        },
    },
    "deep_black": {
        "padna": {
            "PaDNA.SkinDNA.Tone": "Deep",
            "PaDNA.SkinDNA.Undertone": "Cool",
            "PaDNA.HairDNA.Color": "Black",
            "PaDNA.EyeDNA.IrisColor": "Deep brown",
            "PaDNA.FacialDNA.Lips": "Nude",
        },
    },
}


def write_output(name: str, payload: Dict[str, Dict[str, str]]) -> None:
    bundle = {
        "padna": payload.get("padna", {}),
    }
    result = render_svg(bundle)
    svg_path = OUTPUT_DIR / f"{name}.svg"
    svg_path.write_text(result["svg"], encoding="utf-8")

    if cairosvg is not None:
        png_path = OUTPUT_DIR / f"{name}.png"
        cairosvg.svg2png(bytestring=result["svg"].encode("utf-8"), write_to=str(png_path))

    data_url = result.get("data_url", "")
    if data_url.startswith("data:image/svg+xml;base64,"):
        raw = base64.b64decode(data_url.split(",", 1)[1])
        (OUTPUT_DIR / f"{name}_inline.svg").write_bytes(raw)


def main() -> None:
    for name, payload in SAMPLES.items():
        write_output(name, payload)
    print(f"Smoke outputs written to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
