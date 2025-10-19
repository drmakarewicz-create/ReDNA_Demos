"""
Generate Core Benchmarks Roadmap v3.0 diagrams (SVG + PNG) for documentation.

The script renders 10 diagrams to docs/images/roadmap_v3/ using a shared
visual language so SVG and PNG variants stay in sync without external tools.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFont

# -----------------------------------------------------------------------------
# Shared styling primitives
# -----------------------------------------------------------------------------

OUTPUT_DIR = Path("docs/images/roadmap_v3")
SOURCES_DIR = OUTPUT_DIR / "_sources"

WIDTH = 1200
HEIGHT = 720
BACKGROUND = "#FFFFFF"
FONT_FAMILY = "Arial, Helvetica, sans-serif"
FONT_PATH = "/System/Library/Fonts/Supplemental/Arial.ttf"

PALETTE = {
    "ink": "#0B1B34",
    "muted": "#53627C",
    "track1": "#1F77B4",
    "track2": "#FF7F0E",
    "track3": "#2CA02C",
    "track4": "#9467BD",
    "neutral_bg": "#F2F4F7",
    "accent": "#D62728",
    "gold": "#E0B422",
    "teal": "#17BECF",
}


def ensure_dirs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SOURCES_DIR.mkdir(parents=True, exist_ok=True)


_font_cache: dict[Tuple[int, bool], ImageFont.ImageFont] = {}


def get_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    """Load and cache fonts for Pillow rendering."""
    key = (size, bold)
    if key in _font_cache:
        return _font_cache[key]
    try:
        font = ImageFont.truetype(FONT_PATH, size=size)
    except OSError:
        font = ImageFont.load_default()
    _font_cache[key] = font
    return font


def text_width(text: str, font: ImageFont.ImageFont) -> float:
    if hasattr(font, "getlength"):
        return font.getlength(text)
    dummy = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(dummy)
    return draw.textlength(text, font=font)


def wrap_text(text: str, font: ImageFont.ImageFont, max_width: Optional[float]) -> List[str]:
    if max_width is None:
        lines = []
        for paragraph in text.splitlines() or [""]:
            if paragraph == "":
                lines.append("")
            else:
                lines.append(paragraph)
        return lines

    wrapped: List[str] = []
    for paragraph in text.splitlines() or [""]:
        words = paragraph.split()
        if not words:
            wrapped.append("")
            continue
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if text_width(candidate, font) <= max_width:
                current = candidate
            else:
                wrapped.append(current)
                current = word
        wrapped.append(current)
    return wrapped


def escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# -----------------------------------------------------------------------------
# Canvas implementations
# -----------------------------------------------------------------------------


class SvgCanvas:
    def __init__(self, width: int, height: int, background: str = BACKGROUND) -> None:
        self.width = width
        self.height = height
        self.background = background
        self.elements: List[str] = [
            f'<rect x="0" y="0" width="{width}" height="{height}" fill="{background}" />'
        ]

    def rectangle(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        fill: str,
        stroke: str,
        stroke_width: float = 2,
        radius: float = 12,
        opacity: float = 1.0,
    ) -> None:
        self.elements.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
            f'rx="{radius:.1f}" ry="{radius:.1f}" fill="{fill}" fill-opacity="{opacity:.2f}" '
            f'stroke="{stroke}" stroke-width="{stroke_width:.1f}" />'
        )

    def line(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        color: str,
        width: float = 2,
        dash: Optional[Sequence[float]] = None,
    ) -> None:
        dash_attr = ""
        if dash:
            dash_attr = f' stroke-dasharray="{",".join(str(d) for d in dash)}"'
        self.elements.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{color}" stroke-width="{width:.1f}"{dash_attr} />'
        )

    def arrow(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        color: str,
        width: float = 2,
        head: float = 12,
    ) -> None:
        angle = math.atan2(y2 - y1, x2 - x1)
        hx1 = x2 - head * math.cos(angle - math.pi / 6)
        hy1 = y2 - head * math.sin(angle - math.pi / 6)
        hx2 = x2 - head * math.cos(angle + math.pi / 6)
        hy2 = y2 - head * math.sin(angle + math.pi / 6)
        self.elements.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{color}" stroke-width="{width:.1f}" />'
        )
        self.elements.append(
            '<polygon points="%.1f,%.1f %.1f,%.1f %.1f,%.1f" fill="%s" />'
            % (x2, y2, hx1, hy1, hx2, hy2, color)
        )

    def circle(
        self,
        x: float,
        y: float,
        r: float,
        fill: str,
        stroke: str,
        stroke_width: float = 2,
    ) -> None:
        self.elements.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{stroke_width:.1f}" />'
        )

    def text(
        self,
        x: float,
        y: float,
        text: str,
        font_size: int = 20,
        color: str = PALETTE["ink"],
        align: str = "left",
        max_width: Optional[float] = None,
        bold: bool = False,
        leading: float = 1.3,
    ) -> None:
        font = get_font(font_size, bold=bold)
        lines = wrap_text(text, font, max_width)
        anchor_map = {"left": "start", "center": "middle", "right": "end"}
        anchor = anchor_map.get(align, "start")
        line_height = font_size * leading
        attributes = (
            f'x="{x:.1f}" y="{y:.1f}" fill="{color}" font-size="{font_size}" '
            f'font-family="{FONT_FAMILY}" text-anchor="{anchor}"'
        )
        content = []
        for idx, line in enumerate(lines):
            if idx == 0:
                content.append(escape(line))
            else:
                content.append(
                    f'<tspan x="{x:.1f}" dy="{line_height:.1f}">{escape(line)}</tspan>'
                )
        self.elements.append(f"<text {attributes}>{''.join(content)}</text>")

    def save(self, path: Path) -> None:
        header = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" '
            f'height="{self.height}" viewBox="0 0 {self.width} {self.height}">'
        )
        content = "\n".join(self.elements)
        path.write_text(f"{header}\n{content}\n</svg>\n")


class PngCanvas:
    def __init__(self, width: int, height: int, background: str = BACKGROUND) -> None:
        self.width = width
        self.height = height
        self.image = Image.new("RGB", (width, height), background)
        self.draw = ImageDraw.Draw(self.image)

    def rectangle(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        fill: str,
        stroke: str,
        stroke_width: float = 2,
        radius: float = 12,
        opacity: float = 1.0,
    ) -> None:
        fill_color = fill
        if opacity < 1.0:
            # Blend against background manually
            fill_color = blend_color(fill, BACKGROUND, opacity)
        self.draw.rounded_rectangle(
            [(x, y), (x + w, y + h)],
            radius=radius,
            fill=fill_color,
            outline=stroke,
            width=int(round(stroke_width)),
        )

    def line(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        color: str,
        width: float = 2,
        dash: Optional[Sequence[float]] = None,
    ) -> None:
        if dash:
            total_len = math.dist((x1, y1), (x2, y2))
            dx = (x2 - x1) / total_len if total_len else 0
            dy = (y2 - y1) / total_len if total_len else 0
            pattern = list(dash)
            pos = 0.0
            pattern_idx = 0
            current_x, current_y = x1, y1
            while pos < total_len:
                length = pattern[pattern_idx % len(pattern)]
                pattern_idx += 1
                next_pos = min(pos + length, total_len)
                nx = x1 + dx * next_pos
                ny = y1 + dy * next_pos
                if pattern_idx % 2 == 1:
                    self.draw.line(
                        [(current_x, current_y), (nx, ny)],
                        fill=color,
                        width=int(round(width)),
                    )
                current_x, current_y = nx, ny
                pos = next_pos
        else:
            self.draw.line(
                [(x1, y1), (x2, y2)], fill=color, width=int(round(width))
            )

    def arrow(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        color: str,
        width: float = 2,
        head: float = 12,
    ) -> None:
        self.draw.line(
            [(x1, y1), (x2, y2)], fill=color, width=int(round(width))
        )
        angle = math.atan2(y2 - y1, x2 - x1)
        hx1 = x2 - head * math.cos(angle - math.pi / 6)
        hy1 = y2 - head * math.sin(angle - math.pi / 6)
        hx2 = x2 - head * math.cos(angle + math.pi / 6)
        hy2 = y2 - head * math.sin(angle + math.pi / 6)
        self.draw.polygon([(x2, y2), (hx1, hy1), (hx2, hy2)], fill=color)

    def circle(
        self,
        x: float,
        y: float,
        r: float,
        fill: str,
        stroke: str,
        stroke_width: float = 2,
    ) -> None:
        self.draw.ellipse(
            [(x - r, y - r), (x + r, y + r)],
            fill=fill,
            outline=stroke,
            width=int(round(stroke_width)),
        )

    def text(
        self,
        x: float,
        y: float,
        text: str,
        font_size: int = 20,
        color: str = PALETTE["ink"],
        align: str = "left",
        max_width: Optional[float] = None,
        bold: bool = False,
        leading: float = 1.3,
    ) -> None:
        font = get_font(font_size, bold=bold)
        lines = wrap_text(text, font, max_width)
        line_height = font_size * leading
        for idx, line in enumerate(lines):
            if align == "center":
                tx = x - text_width(line, font) / 2
            elif align == "right":
                tx = x - text_width(line, font)
            else:
                tx = x
            ty = y + idx * line_height
            self.draw.text((tx, ty), line, font=font, fill=color)

    def save(self, path: Path) -> None:
        self.image.save(path, format="PNG")


def blend_color(fg: str, bg: str, alpha: float) -> str:
    def hex_to_rgb(code: str) -> Tuple[int, int, int]:
        code = code.lstrip("#")
        return tuple(int(code[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore

    def rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
        return "#%02x%02x%02x" % rgb

    fr, fg_val, fb = hex_to_rgb(fg)
    br, bg_val, bb = hex_to_rgb(bg)
    rr = int(fr * alpha + br * (1 - alpha))
    rg = int(fg_val * alpha + bg_val * (1 - alpha))
    rb = int(fb * alpha + bb * (1 - alpha))
    return rgb_to_hex((rr, rg, rb))


# -----------------------------------------------------------------------------
# Canvas pair helper
# -----------------------------------------------------------------------------


@dataclass
class CanvasPair:
    name: str
    svg: SvgCanvas
    png: PngCanvas

    def rectangle(self, *args, **kwargs) -> None:
        self.svg.rectangle(*args, **kwargs)
        self.png.rectangle(*args, **kwargs)

    def line(self, *args, **kwargs) -> None:
        self.svg.line(*args, **kwargs)
        self.png.line(*args, **kwargs)

    def arrow(self, *args, **kwargs) -> None:
        self.svg.arrow(*args, **kwargs)
        self.png.arrow(*args, **kwargs)

    def circle(self, *args, **kwargs) -> None:
        self.svg.circle(*args, **kwargs)
        self.png.circle(*args, **kwargs)

    def text(self, *args, **kwargs) -> None:
        self.svg.text(*args, **kwargs)
        self.png.text(*args, **kwargs)

    def save(self) -> None:
        svg_path = OUTPUT_DIR / f"{self.name}.svg"
        png_path = OUTPUT_DIR / f"{self.name}.png"
        self.svg.save(svg_path)
        self.png.save(png_path)


def new_canvas(name: str, width: int = WIDTH, height: int = HEIGHT) -> CanvasPair:
    return CanvasPair(name=name, svg=SvgCanvas(width, height), png=PngCanvas(width, height))


# -----------------------------------------------------------------------------
# Diagram builders
# -----------------------------------------------------------------------------


def add_title(pair: CanvasPair, title: str, subtitle: Optional[str] = None) -> None:
    pair.text(600, 40, title, font_size=32, align="center", bold=True)
    if subtitle:
        pair.text(600, 80, subtitle, font_size=20, color=PALETTE["muted"], align="center")


def build_track_philosophy(pair: CanvasPair) -> None:
    add_title(pair, "Track-Based Development Philosophy", "Parallel execution with milestone convergence")

    top = 130
    left_margin = 100
    right_margin = 100
    lane_width = (WIDTH - left_margin - right_margin) / 4
    lane_height = 450

    milestones = [
        ("Month 1", 0.1),
        ("M1 (Month 3)", 0.3),
        ("M2 (Month 6)", 0.55),
        ("M3 (Month 12)", 0.85),
    ]

    timeline_y = top - 40
    pair.line(left_margin, timeline_y, WIDTH - right_margin, timeline_y, color=PALETTE["muted"], width=3)
    for label, relative in milestones:
        x = left_margin + (WIDTH - left_margin - right_margin) * relative
        pair.line(x, timeline_y - 10, x, timeline_y + 10, color=PALETTE["muted"], width=2)
        pair.text(x, timeline_y - 34, label, font_size=18, color=PALETTE["muted"], align="center")
        pair.line(x, timeline_y + 10, x, top + lane_height, color="#CBD2E1", width=1, dash=[6, 8])

    tracks = [
        ("Track 1: Core Intelligence", PALETTE["track1"], [
            ("M1: Ontology V6 bootstrapped", 0.25),
            ("M2: Inference V3 live", 0.55),
            ("M3: Adaptive analytics + RL rollout", 0.80),
        ]),
        ("Track 2: Human Interface", PALETTE["track2"], [
            ("M1: Life OS hub beta", 0.22),
            ("M2: Coach catalog AI handoffs", 0.52),
            ("M3: UX polish + mobile ready", 0.78),
        ]),
        ("Track 3: Ecosystem & Ethics", PALETTE["track3"], [
            ("M1: Consent guardian foundation", 0.28),
            ("M2: Collaborative intelligence pilot", 0.6),
            ("M3: Ethics review + transparency UI", 0.82),
        ]),
        ("Track 4: Maintenance & Operations", PALETTE["track4"], [
            ("M1: DevX platform launch", 0.25),
            ("M2: Observability & reliability SLAs", 0.58),
            ("M3: Autonomous ops + chaos drills", 0.85),
        ]),
    ]

    for idx, (track_title, color, milestones_defs) in enumerate(tracks):
        x = left_margin + idx * lane_width
        pair.rectangle(x + 10, top, lane_width - 20, lane_height, fill=PALETTE["neutral_bg"], stroke="#E0E5EE")
        pair.text(x + lane_width / 2, top + 16, track_title, font_size=22, color=color, align="center", bold=True)
        for text, rel in milestones_defs:
            box_x = left_margin + (WIDTH - left_margin - right_margin) * rel - lane_width * 0.35
            box_w = lane_width * 0.7
            box_y = top + 70 + idx * 0  # align at similar vertical positions by row, not offset
            step_y = top + 120 + milestones_defs.index((text, rel)) * 110
            pair.rectangle(box_x, step_y, box_w, 80, fill="#FFFFFF", stroke=color, stroke_width=3, radius=12)
            pair.text(box_x + box_w / 2, step_y + 16, text, font_size=18, align="center", max_width=box_w - 24)

    pair.text(
        WIDTH / 2,
        top + lane_height + 20,
        "Tracks progress independently but sync at each milestone integration checkpoint.",
        font_size=18,
        color=PALETTE["muted"],
        align="center",
    )


def build_milestone_timeline(pair: CanvasPair) -> None:
    add_title(pair, "Milestone Timeline", "Gantt view across tracks")

    left = 160
    right = 80
    top = 140
    row_height = 80
    timeline_width = WIDTH - left - right

    months = [1, 3, 6, 12]
    month_labels = ["Month 1", "Month 3 (M1)", "Month 6 (M2)", "Month 12 (M3)"]

    def month_to_x(month: float) -> float:
        return left + (month - 1) / (12 - 1) * timeline_width

    # timeline grid
    for idx, month in enumerate(months):
        x = month_to_x(month)
        pair.line(x, top - 20, x, top + row_height * 4 + 20, color="#CBD2E1", width=1, dash=[6, 8])
        pair.text(x, top - 40, month_labels[idx], font_size=16, color=PALETTE["muted"], align="center")

    tracks = [
        ("Track 1: Core Intelligence", PALETTE["track1"],
         [("Benchmark 1.1", 1, 4), ("Benchmark 1.2", 4, 7), ("Benchmark 1.3", 5, 9), ("Benchmark 1.4", 9, 12)]),
        ("Track 2: Human Interface", PALETTE["track2"],
         [("Benchmark 2.1", 1, 6), ("Benchmark 2.2", 4, 8), ("Benchmark 2.3", 8, 12)]),
        ("Track 3: Ecosystem & Ethics", PALETTE["track3"],
         [("Benchmark 3.1", 2, 8), ("Benchmark 3.2", 8, 12), ("Benchmark 3.3", 6, 12)]),
        ("Track 4: Maintenance & Operations", PALETTE["track4"],
         [("Benchmark 4.1", 1, 9), ("Benchmark 4.2", 3, 12)]),
    ]

    for row, (track_label, color, bars) in enumerate(tracks):
        y = top + row * row_height
        pair.text(left - 20, y + row_height / 2 - 20, track_label, font_size=18, color=color, align="right")
        for label, start, end in bars:
            x1 = month_to_x(start)
            x2 = month_to_x(end)
            pair.rectangle(
                x1,
                y,
                x2 - x1,
                row_height - 20,
                fill=blend_color(color, BACKGROUND, 0.2),
                stroke=color,
                radius=10,
            )
            pair.text(
                (x1 + x2) / 2,
                y + 10,
                f"{label} ({start}-{end})",
                font_size=16,
                align="center",
                max_width=x2 - x1 - 16,
            )

    # Milestone diamonds
    for month, label in [(3, "M1 Gate"), (6, "M2 Gate"), (12, "M3 Gate")]:
        x = month_to_x(month)
        y_center = top + row_height * 4 + 10
        diamond = [
            (x, y_center - 12),
            (x + 12, y_center),
            (x, y_center + 12),
            (x - 12, y_center),
        ]
        pair.png.draw.polygon(diamond, fill=PALETTE["accent"])
        pair.svg.elements.append(
            '<polygon points="%.1f,%.1f %.1f,%.1f %.1f,%.1f %.1f,%.1f" fill="%s" />'
            % (diamond[0][0], diamond[0][1], diamond[1][0], diamond[1][1],
               diamond[2][0], diamond[2][1], diamond[3][0], diamond[3][1], PALETTE["accent"])
        )
        pair.text(x, y_center + 20, label, font_size=16, align="center", color=PALETTE["accent"])


def build_maturity_model(pair: CanvasPair) -> None:
    add_title(pair, "Platform Maturity Model", "Five-stage evolution toward ecosystem readiness")

    base_x = 160
    base_y = 560
    step_width = 180
    step_height = 80
    gap = 4

    levels = [
        ("Level 0: Prototype", "Pre-v2.1 • ✅ Complete", PALETTE["muted"]),
        ("Level 1: Foundation", "v2.1 • 2K containers, RSC, Consent", PALETTE["track1"]),
        ("Level 2: Intelligence", "v3.0 M1-M2 • 6-8K containers, Predictions, Cross-Coach", PALETTE["gold"]),
        ("Level 3: Production", "v3.0 M3 • 99.9% uptime, WCAG AA, Ethics Review", PALETTE["track2"]),
        ("Level 4: Ecosystem", "Post-v3.0 • API platform, 3rd-party, Longitudinal", PALETTE["track4"]),
    ]

    for idx, (title, desc, color) in enumerate(levels):
        x = base_x + idx * (step_width + gap)
        y = base_y - (idx + 1) * (step_height + 20)
        pair.rectangle(
            x,
            y,
            step_width,
            step_height,
            fill=blend_color(color, BACKGROUND, 0.2),
            stroke=color,
            radius=10,
        )
        pair.text(x + step_width / 2, y + 12, title, font_size=18, align="center", color=color, bold=True)
        pair.text(
            x + step_width / 2,
            y + 38,
            desc,
            font_size=15,
            align="center",
            max_width=step_width - 20,
        )

    pair.text(
        WIDTH / 2,
        620,
        "Status: Levels 0-1 complete, Level 2 in progress, Levels 3-4 planned/future.",
        font_size=18,
        color=PALETTE["muted"],
        align="center",
    )


def build_ontology_arch(pair: CanvasPair) -> None:
    add_title(pair, "Ontology V6 Architecture", "High-throughput knowledge graph pipeline")
    y = 200
    x_positions = [120, 340, 560, 780, 1000]
    components = [
        ("Expansion Engine V6", "Generates container candidates\nwith namespace signals"),
        ("Registry V6", "8K containers • namespace indexed\nversioned schemas"),
        ("Correlation Engine", "Cross-domain correlation scoring\ntrait relationship weighting"),
        ("Edge Storage", "120K-150K edges\nsemantic, hierarchy, cross-domain"),
        ("Semantic Search & API", "<50ms p95 queries\npattern detector + 4 endpoints"),
    ]

    for idx, (title, body) in enumerate(components):
        pair.rectangle(
            x_positions[idx] - 110,
            y - 40,
            220,
            160,
            fill=PALETTE["neutral_bg"],
            stroke=PALETTE["track1"],
            radius=14,
        )
        pair.text(x_positions[idx], y - 24, title, font_size=20, align="center", color=PALETTE["track1"], bold=True)
        pair.text(
            x_positions[idx],
            y + 6,
            body,
            font_size=16,
            align="center",
            max_width=180,
        )
        if idx < len(components) - 1:
            pair.arrow(
                x_positions[idx] + 110,
                y + 40,
                x_positions[idx + 1] - 110,
                y + 40,
                color=PALETTE["track1"],
                width=3,
            )

    pair.text(
        WIDTH / 2,
        420,
        "Pipeline: Expansion → Registry → Correlation → Edge Storage → Search/Patterns/API",
        font_size=18,
        color=PALETTE["muted"],
        align="center",
    )


def build_inference_arch(pair: CanvasPair) -> None:
    add_title(pair, "Inference V3 Architecture", "Predictive modeling pipeline")
    y = 220
    boxes = [
        (150, "Historical Trait Data", "30/60/90 day windows\nnormalized feature sets"),
        (360, "Time-Series Analyzer", "Trend detection • seasonality\nanomaly tagging"),
        (570, "Bayesian Belief Network", "Trait dependency graph • temporal priors"),
        (780, "Prediction Engine", "Bayesian updates with decay\nscenario-ready outputs"),
        (990, "Delivery Tier", "Confidence calibrator (90% CI)\nScenario modeler • Goal success API"),
    ]
    for x, title, desc in boxes:
        pair.rectangle(
            x - 110,
            y - 40,
            220,
            150,
            fill=PALETTE["neutral_bg"],
            stroke=PALETTE["track2"],
            radius=14,
        )
        pair.text(x, y - 20, title, font_size=20, align="center", color=PALETTE["track2"], bold=True)
        pair.text(x, y + 10, desc, font_size=16, align="center", max_width=180)
    for idx in range(len(boxes) - 1):
        pair.arrow(boxes[idx][0] + 110, y + 35, boxes[idx + 1][0] - 110, y + 35, color=PALETTE["track2"], width=3)

    pair.text(
        WIDTH / 2,
        430,
        "Outputs feed Life OS goals, coach scenarios, and platform APIs in <200ms p95.",
        font_size=18,
        color=PALETTE["muted"],
        align="center",
    )


def build_collab_platform(pair: CanvasPair) -> None:
    add_title(pair, "Collaborative Intelligence Platform", "Consent-aware multi-coach coordination")
    layers = [
        ("Collaboration UI", "Shared panels • badges • activity feed", PALETTE["track2"], 520),
        ("Consent Guardian + Provenance Firewall", "Unified approvals • audit trails • redaction rules", PALETTE["track3"], 360),
        ("RSC V2 Engine + Cross-Persona API", "State sync • persona routing • shared insights bus", PALETTE["track1"], 220),
    ]
    for title, desc, color, y in layers:
        pair.rectangle(
            200,
            y - 60,
            WIDTH - 400,
            120,
            fill=blend_color(color, BACKGROUND, 0.18),
            stroke=color,
            radius=16,
        )
        pair.text(WIDTH / 2, y - 30, title, font_size=22, align="center", color=color, bold=True)
        pair.text(WIDTH / 2, y + 2, desc, font_size=17, align="center", max_width=760)

    pair.arrow(600, 260, 600, 300, color=PALETTE["muted"], width=3)
    pair.arrow(600, 400, 600, 440, color=PALETTE["muted"], width=3)
    pair.text(
        WIDTH / 2,
        610,
        "End-to-end: RSC V2 intelligence → consent enforcement → human-facing collaboration.",
        font_size=18,
        color=PALETTE["muted"],
        align="center",
    )


def build_life_os(pair: CanvasPair) -> None:
    add_title(pair, "Life OS Hub Architecture", "Unified productivity + intelligence hub")
    center_x = WIDTH / 2
    center_y = 320
    pair.circle(center_x, center_y, 80, fill="#FFFFFF", stroke=PALETTE["track2"], stroke_width=4)
    pair.text(center_x, center_y - 30, "Life OS Core", font_size=22, align="center", color=PALETTE["track2"], bold=True)
    pair.text(
        center_x,
        center_y,
        "Goals • Projects • Tasks • Todos",
        font_size=18,
        align="center",
        max_width=180,
    )

    spokes = [
        (center_x - 320, 180, "Analytics Integration Panel", "Inference V3 predictions\nrisk & opportunity surfacing", PALETTE["track1"]),
        (center_x + 320, 180, "Cross-Coach Insights Feed", "Career stress ↔ Head Coach rest suggestions\nPersona-aware nudges", PALETTE["track3"]),
        (center_x - 320, 460, "Contextual Recommendations", "ML-driven timing • priority ordering\nExplainable prompts", PALETTE["track4"]),
        (center_x + 320, 460, "Unified Dashboard UI", "Single pane view • filters • quick actions\nLife OS + coach states", PALETTE["track2"]),
    ]

    for x, y, title, desc, color in spokes:
        pair.rectangle(
            x - 130,
            y - 60,
            260,
            140,
            fill=PALETTE["neutral_bg"],
            stroke=color,
            radius=14,
        )
        pair.text(x, y - 30, title, font_size=20, align="center", color=color, bold=True)
        pair.text(x, y + 4, desc, font_size=16, align="center", max_width=220)
        pair.arrow(center_x + math.copysign(80, x - center_x), center_y, x - math.copysign(130, x - center_x), y, color=color, width=3)

    pair.text(
        WIDTH / 2,
        600,
        "Life OS evolves from standalone tracker to intelligence hub orchestrating cross-coach actions.",
        font_size=18,
        color=PALETTE["muted"],
        align="center",
    )


def build_kpi_dashboard(pair: CanvasPair) -> None:
    add_title(pair, "Success Metrics Dashboard Mockup", "Illustrative layout for KPIs")

    pair.rectangle(100, 140, 1000, 460, fill=PALETTE["neutral_bg"], stroke="#E0E5EE", radius=20)

    # Milestone status
    pair.rectangle(130, 170, 940, 120, fill="#FFFFFF", stroke=PALETTE["track1"], radius=16)
    pair.text(150, 190, "Milestone Progress", font_size=20, color=PALETTE["track1"], bold=True)
    milestones = [("M1", 65, PALETTE["track1"]), ("M2", 40, PALETTE["track2"]), ("M3", 15, PALETTE["track4"])]
    for idx, (label, percent, color) in enumerate(milestones):
        x = 150 + idx * 300
        pair.text(x, 220, f"{label} Completion", font_size=18, color=color, bold=True)
        pair.rectangle(x, 250, 220, 24, fill=blend_color(color, BACKGROUND, 0.18), stroke=color, radius=12)
        bar_width = 220 * percent / 100
        pair.rectangle(x, 250, bar_width, 24, fill=color, stroke=color, radius=12)
        pair.text(x + 110, 282, f"{percent}% of scope", font_size=16, align="center", color=color)

    # Left KPIs
    pair.rectangle(130, 310, 280, 270, fill="#FFFFFF", stroke=PALETTE["track3"], radius=16)
    pair.text(150, 330, "Platform KPIs", font_size=20, color=PALETTE["track3"], bold=True)
    bullets = [
        "Ontology coverage: 5,200 / 8,000 (65%)",
        "Edges indexed: 92,410 (target 120K)",
        "Uptime: 99.92% (target 99.9%) ✅",
        "Trust score: 4.3 / 4.5 🟡",
    ]
    for i, bullet in enumerate(bullets):
        pair.text(150, 360 + i * 40, bullet, font_size=16, color=PALETTE["muted"], max_width=240)

    # Center track metrics
    pair.rectangle(430, 310, 320, 270, fill="#FFFFFF", stroke=PALETTE["track2"], radius=16)
    pair.text(450, 330, "Track Metrics", font_size=20, color=PALETTE["track2"], bold=True)
    track_metrics = [
        ("Track 1", "Ontology velocity + predictive accuracy", PALETTE["track1"]),
        ("Track 2", "Coach NPS + Life OS retention", PALETTE["track2"]),
        ("Track 3", "Consent latency + audit completion", PALETTE["track3"]),
        ("Track 4", "Deploy frequency + MTTR", PALETTE["track4"]),
    ]
    for i, (label, desc, color) in enumerate(track_metrics):
        y = 360 + i * 55
        pair.rectangle(450, y - 6, 280, 44, fill=blend_color(color, BACKGROUND, 0.16), stroke=color, radius=10)
        pair.text(460, y, label, font_size=17, color=color, bold=True)
        pair.text(460, y + 24, desc, font_size=15, color=PALETTE["muted"], max_width=260)

    # Right qualitative metrics
    pair.rectangle(770, 310, 300, 270, fill="#FFFFFF", stroke=PALETTE["track4"], radius=16)
    pair.text(790, 330, "Qualitative Signals", font_size=20, color=PALETTE["track4"], bold=True)
    gauges = [
        ("Transparency", "3.8 / 4.5 target"),
        ("Ethics Board Readiness", "M2 charter drafted"),
        ("Stakeholder Satisfaction", "4.2 / 5 survey"),
    ]
    for i, (label, value) in enumerate(gauges):
        y = 370 + i * 70
        pair.circle(820, y, 26, fill=blend_color(PALETTE["track4"], BACKGROUND, 0.2), stroke=PALETTE["track4"], stroke_width=3)
        pair.text(820, y - 10, label[:2], font_size=16, align="center", color=PALETTE["track4"])
        pair.text(860, y - 12, label, font_size=17, color=PALETTE["muted"])
        pair.text(860, y + 16, value, font_size=16, color=PALETTE["muted"])


def build_governance_flow(pair: CanvasPair) -> None:
    add_title(pair, "Governance & Ethics Integration Flow", "Escalation and review cadence")
    start_x = 200
    start_y = 180
    box_w = 260
    box_h = 100
    spacing_x = 300
    spacing_y = 140

    quarterly = (start_x, start_y, "Quarterly Reviews", "Weeks 12, 24, 36 → JSON audit + Markdown report", PALETTE["track3"])
    monthly = (start_x + spacing_x, start_y, "Monthly Check-Ins", "Every 4 weeks → Track owner updates", PALETTE["track2"])
    ethics = (start_x + 2 * spacing_x, start_y, "Annual Ethics Review", "M2 board established • M3 review • +90d changes • public report", PALETTE["track4"])

    for x, y, title, desc, color in [quarterly, monthly, ethics]:
        pair.rectangle(x, y, box_w, box_h, fill="#FFFFFF", stroke=color, radius=14)
        pair.text(x + box_w / 2, y + 12, title, font_size=20, align="center", color=color, bold=True)
        pair.text(x + box_w / 2, y + 40, desc, font_size=16, align="center", max_width=box_w - 20)

    pair.arrow(start_x + box_w, start_y + box_h / 2, start_x + spacing_x, start_y + box_h / 2, color=PALETTE["muted"], width=3)
    pair.arrow(start_x + spacing_x + box_w, start_y + box_h / 2, start_x + 2 * spacing_x, start_y + box_h / 2, color=PALETTE["muted"], width=3)

    escalation_y = start_y + spacing_y
    pair.rectangle(180, escalation_y, 840, 160, fill=PALETTE["neutral_bg"], stroke="#E0E5EE", radius=16)
    pair.text(600, escalation_y + 16, "Risk Escalation Flow", font_size=20, align="center", color=PALETTE["muted"], bold=True)

    flows = [
        ("Low / Medium", "Track owner mitigation", 220),
        ("High", "Escalate to quarterly review → CTO sign-off", 420),
        ("Critical", "Immediate escalation → CTO + Ethics Board", 620),
    ]

    for label, desc, x in flows:
        pair.rectangle(
            x - 120,
            escalation_y + 50,
            240,
            80,
            fill="#FFFFFF",
            stroke=PALETTE["accent"] if "Critical" in label else PALETTE["track3"],
            radius=12,
        )
        pair.text(x, escalation_y + 64, label, font_size=18, align="center", bold=True)
        pair.text(x, escalation_y + 88, desc, font_size=15, align="center", max_width=200)


def build_track_dependencies(pair: CanvasPair) -> None:
    add_title(pair, "Track Interdependencies", "How capabilities flow across tracks")
    positions = {
        "Track 1": (360, 260),
        "Track 2": (840, 220),
        "Track 3": (840, 400),
        "Track 4": (360, 480),
    }
    descriptions = {
        "Track 1": "Core Intelligence\nData models • inference APIs",
        "Track 2": "Human Interface\nCoach UX • Life OS surfaces",
        "Track 3": "Ecosystem & Ethics\nConsent • collaboration • governance",
        "Track 4": "Maintenance & Operations\nInfrastructure • reliability • tooling",
    }
    colors = {
        "Track 1": PALETTE["track1"],
        "Track 2": PALETTE["track2"],
        "Track 3": PALETTE["track3"],
        "Track 4": PALETTE["track4"],
    }

    for track, (x, y) in positions.items():
        pair.rectangle(
            x - 150,
            y - 70,
            300,
            140,
            fill="#FFFFFF",
            stroke=colors[track],
            radius=16,
        )
        pair.text(x, y - 40, track, font_size=22, align="center", color=colors[track], bold=True)
        pair.text(x, y - 10, descriptions[track], font_size=17, align="center", max_width=240)

    # arrows
    pair.arrow(510, 260, 690, 220, color=PALETTE["track1"], width=4)
    pair.arrow(510, 260, 690, 400, color=PALETTE["track1"], width=4)
    pair.arrow(360, 410, 360, 340, color=PALETTE["track4"], width=4)
    pair.arrow(360, 410, 360, 450, color=PALETTE["track4"], width=4)
    pair.arrow(690, 220, 510, 260, color=PALETTE["track2"], width=2)
    pair.arrow(690, 400, 510, 260, color=PALETTE["track3"], width=2)

    pair.text(
        WIDTH / 2,
        580,
        "Track 1 intelligence powers Track 2 & 3. Track 4 enables and stabilizes every track.",
        font_size=18,
        color=PALETTE["muted"],
        align="center",
    )


def build_diagrams() -> None:
    ensure_dirs()
    diagram_builders = [
        ("01_track_philosophy", build_track_philosophy),
        ("02_milestone_timeline", build_milestone_timeline),
        ("03_maturity_model", build_maturity_model),
        ("04_ontology_v6_arch", build_ontology_arch),
        ("05_inference_v3_arch", build_inference_arch),
        ("06_collab_intel_platform", build_collab_platform),
        ("07_life_os_hub", build_life_os),
        ("08_kpi_dashboard_mock", build_kpi_dashboard),
        ("09_governance_ethics_flow", build_governance_flow),
        ("10_track_dependencies", build_track_dependencies),
    ]
    for name, builder in diagram_builders:
        pair = new_canvas(name)
        builder(pair)
        pair.save()


if __name__ == "__main__":
    build_diagrams()
