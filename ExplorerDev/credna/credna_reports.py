"""Reporting utilities for Coach ReDNA coverage."""

from __future__ import annotations

import csv
import io
import json
from typing import Any, Dict, List, Mapping

from ExplorerDev.credna.credna_ops import coach_trait_iterator, get_coach


def generate_template_report(registry: Mapping[str, Any], coach_id: str) -> Dict[str, Any]:
    coach = get_coach(registry, coach_id)
    if coach is None:
        return {"ok": False, "error": f"Coach `{coach_id}` not found."}

    rows: List[Dict[str, Any]] = []
    missing_templates = 0
    mapped_traits = 0

    for trait_id, trait in coach_trait_iterator(coach):
        templates = trait.get("templates") if isinstance(trait.get("templates"), Mapping) else {}
        has_neutral = _has_template(templates, "neutral")
        has_gentle = _has_template(templates, "gentle")
        has_blunt = _has_template(templates, "blunt")
        mapped_to_core = bool(str(trait.get("core_trait") or "").strip())
        issues: List[str] = []
        if not (has_neutral or has_gentle or has_blunt):
            issues.append("missing templates")
            missing_templates += 1
        if not mapped_to_core:
            issues.append("missing core mapping")
        else:
            mapped_traits += 1
        rows.append(
            {
                "trait": trait_id,
                "label": trait.get("label", trait_id.split(".")[-1]),
                "weight": trait.get("weight", 0.0),
                "core_trait": trait.get("core_trait"),
                "has_neutral": has_neutral,
                "has_gentle": has_gentle,
                "has_blunt": has_blunt,
                "issues": issues,
            }
        )

    rows.sort(key=lambda row: row["trait"])
    summary = {
        "total_traits": len(rows),
        "mapped_to_core": mapped_traits,
        "unmapped": len(rows) - mapped_traits,
        "complete_templates": len(rows) - missing_templates,
        "missing_templates": missing_templates,
    }
    return {"ok": True, "coach_id": coach_id, "rows": rows, "summary": summary}


def export_report_csv(report: Mapping[str, Any]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "trait",
            "label",
            "weight",
            "core_trait",
            "has_neutral",
            "has_gentle",
            "has_blunt",
            "issues",
        ]
    )
    for row in report.get("rows", []):
        issues = row.get("issues") if isinstance(row.get("issues"), list) else []
        writer.writerow(
            [
                row.get("trait"),
                row.get("label"),
                row.get("weight"),
                row.get("core_trait"),
                _bool_str(row.get("has_neutral")),
                _bool_str(row.get("has_gentle")),
                _bool_str(row.get("has_blunt")),
                ", ".join(str(issue) for issue in issues),
            ]
        )
    return buffer.getvalue().encode("utf-8")


def export_report_json(report: Mapping[str, Any]) -> bytes:
    return json.dumps(report, indent=2, ensure_ascii=False).encode("utf-8")


def _has_template(templates: Mapping[str, Any], tone: str) -> bool:
    if not isinstance(templates, Mapping):
        return False
    value = templates.get(tone)
    return isinstance(value, str) and bool(value.strip())


def _bool_str(value: Any) -> str:
    return "yes" if bool(value) else "no"


__all__ = [
    "generate_template_report",
    "export_report_csv",
    "export_report_json",
]
