#!/usr/bin/env python3
"""
Persona Panel Config Diagnostic Tool

Validates and reports on the persona panel configuration system.
Generates a comprehensive debug report for troubleshooting.

Usage:
    python3 scripts/devx/debug_persona_config.py

Output:
    docs/ops/RIGHT_PANE_DEBUG_REPORT.md
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def load_user_layout(user_id: str) -> Optional[Dict[str, Any]]:
    """Load user-specific right pane layout if it exists."""
    layout_file = PROJECT_ROOT / "data" / "users" / user_id / "ui" / "right_pane_layout.json"

    if not layout_file.exists():
        return None

    try:
        with open(layout_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return {"_error": str(e)}


def get_test_users() -> List[str]:
    """Get list of test users with data directories."""
    users_dir = PROJECT_ROOT / "data" / "users"

    if not users_dir.exists():
        return []

    users = []
    for user_dir in users_dir.iterdir():
        if user_dir.is_dir() and not user_dir.name.startswith('.'):
            users.append(user_dir.name)

    return sorted(users)


def analyze_persona_config() -> Dict[str, Any]:
    """
    Analyze the persona panel configuration system.

    Returns:
        Dictionary containing analysis results
    """

    # Define known personas and their expected panels
    # This mirrors the PERSONA_PANEL_CONFIG in persona-panels-config.ts
    personas = {
        "head_coach": {
            "lifeOS": "full",
            "panels": [],
            "description": "Orchestrator - shows full Life OS"
        },
        "relationship_coach": {
            "lifeOS": "relationship",
            "panels": [],
            "description": "Shows filtered Life OS (relationship items only)"
        },
        "photo_coach": {
            "lifeOS": "hidden",
            "panels": ["photo"],
            "description": "Photo upload and trait extraction"
        },
        "photo": {
            "lifeOS": "hidden",
            "panels": ["photo"],
            "description": "Photo Coach (alternate key)"
        },
        "padna_coach": {
            "lifeOS": "hidden",
            "panels": ["padna"],
            "description": "Portrait renderer from PaDNA traits"
        },
        "padna": {
            "lifeOS": "hidden",
            "panels": ["padna"],
            "description": "PaDNA Coach (alternate key)"
        },
        "rendering": {
            "lifeOS": "hidden",
            "panels": ["avatar", "portrait"],
            "description": "Avatar and portrait rendering"
        },
        "career_coach": {
            "lifeOS": "hidden",
            "panels": ["career_snapshot", "skill_map"],
            "description": "Career insights and skill curiosity"
        },
        "personality_test_coach": {
            "lifeOS": "hidden",
            "panels": ["personality_snapshot", "personality_map"],
            "description": "Personality traits and map visualization"
        },
        "chatdna_coach": {
            "lifeOS": "hidden",
            "panels": ["chatdna_snapshot", "language_style"],
            "description": "Communication style and language patterns"
        },
        "beliefdna_coach": {
            "lifeOS": "hidden",
            "panels": [],
            "description": "Philosophy and values (rendered via renderPersonaTools)"
        },
        "permission_coach": {
            "lifeOS": "hidden",
            "panels": [],
            "description": "Consent and privacy (uses DynamicCoachPanes)"
        },
        "*": {
            "lifeOS": "hidden",
            "panels": [],
            "description": "Default fallback for unknown personas"
        }
    }

    return {
        "personas": personas,
        "total_personas": len(personas),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


def generate_report() -> str:
    """Generate comprehensive debug report in Markdown format."""

    analysis = analyze_persona_config()
    test_users = get_test_users()

    report = []
    report.append("# Persona Panel Config Debug Report")
    report.append("")
    report.append(f"**Generated**: {analysis['timestamp']}")
    report.append(f"**Total Personas**: {analysis['total_personas']}")
    report.append(f"**Test Users Found**: {len(test_users)}")
    report.append("")
    report.append("---")
    report.append("")

    # Section 1: Persona Configuration Summary
    report.append("## 1. Persona Configuration Summary")
    report.append("")
    report.append("| Persona | Life OS | Panels | Description |")
    report.append("|---------|---------|--------|-------------|")

    for persona_key, config in analysis["personas"].items():
        life_os = config["lifeOS"]
        panels = ", ".join(config["panels"]) if config["panels"] else "(none)"
        desc = config["description"]
        report.append(f"| `{persona_key}` | `{life_os}` | {panels} | {desc} |")

    report.append("")
    report.append("---")
    report.append("")

    # Section 2: User Override Summary
    report.append("## 2. User Override Summary")
    report.append("")

    if not test_users:
        report.append("*No test users found with data directories.*")
    else:
        users_with_overrides = []
        users_without_overrides = []

        for user_id in test_users:
            layout = load_user_layout(user_id)
            if layout:
                if "_error" in layout:
                    users_with_overrides.append((user_id, f"❌ Error: {layout['_error']}"))
                else:
                    num_overrides = len(layout.get("overrides", {}))
                    users_with_overrides.append((user_id, f"✅ {num_overrides} persona(s) overridden"))
            else:
                users_without_overrides.append(user_id)

        if users_with_overrides:
            report.append("### Users with Custom Layouts")
            report.append("")
            for user_id, status in users_with_overrides:
                report.append(f"- **{user_id}**: {status}")
            report.append("")

        if users_without_overrides:
            report.append("### Users with Default Layouts")
            report.append("")
            for user_id in users_without_overrides:
                report.append(f"- {user_id}")
            report.append("")

    report.append("---")
    report.append("")

    # Section 3: Detailed User Overrides
    report.append("## 3. Detailed User Overrides")
    report.append("")

    for user_id in test_users:
        layout = load_user_layout(user_id)
        if layout and "_error" not in layout:
            report.append(f"### User: `{user_id}`")
            report.append("")
            report.append(f"**Version**: {layout.get('version', 'unknown')}")
            report.append("")

            overrides = layout.get("overrides", {})
            if overrides:
                report.append("**Overrides**:")
                report.append("")
                for persona_key, override_config in overrides.items():
                    report.append(f"#### `{persona_key}`")
                    report.append("")
                    report.append("```json")
                    report.append(json.dumps(override_config, indent=2))
                    report.append("```")
                    report.append("")

                    # Analyze the override
                    issues = []

                    # Check if persona exists in base config
                    if persona_key not in analysis["personas"]:
                        issues.append(f"⚠️ Unknown persona: `{persona_key}` not in base config")

                    # Check panel IDs
                    order = override_config.get("order", [])
                    visible = override_config.get("visible", {})

                    if order:
                        base_panels = analysis["personas"].get(persona_key, {}).get("panels", [])
                        for panel_id in order:
                            if panel_id not in base_panels and panel_id != "life_os":
                                issues.append(f"⚠️ Panel `{panel_id}` in order but not in base config")

                    if visible:
                        base_panels = analysis["personas"].get(persona_key, {}).get("panels", [])
                        for panel_id in visible.keys():
                            if panel_id not in base_panels and panel_id != "life_os":
                                issues.append(f"⚠️ Panel `{panel_id}` in visible but not in base config")

                    if issues:
                        report.append("**Validation Issues**:")
                        report.append("")
                        for issue in issues:
                            report.append(f"- {issue}")
                        report.append("")
                    else:
                        report.append("✅ **Valid override**")
                        report.append("")
            else:
                report.append("*No persona overrides defined.*")
                report.append("")

    report.append("---")
    report.append("")

    # Section 4: Component Mapping Validation
    report.append("## 4. Component Mapping Validation")
    report.append("")
    report.append("Checking if panel components exist in codebase...")
    report.append("")

    component_map = {
        "photo": "web/src/components/photo/photo-panel.tsx",
        "padna": "web/src/components/padna/portrait-render-card.tsx",
        "avatar": "web/src/components/rendering/avatar-render-panel.tsx",
        "portrait": "web/src/components/padna/portrait-render-card.tsx",
        "career_snapshot": "web/src/components/career/career-snapshot-card.tsx",
        "skill_map": "web/src/components/career/skill-curiosity-map.tsx",
        "personality_snapshot": "web/src/components/personality/personality-snapshot-card.tsx",
        "personality_map": "web/src/components/personality/personality-map-visualization.tsx",
        "chatdna_snapshot": "web/src/components/chatdna-snapshot-card.tsx",
        "language_style": "web/src/components/language-style-panel.tsx"
    }

    report.append("| Panel ID | Component Path | Status |")
    report.append("|----------|----------------|--------|")

    for panel_id, component_path in component_map.items():
        full_path = PROJECT_ROOT / component_path
        status = "✅ EXISTS" if full_path.exists() else "❌ MISSING"
        report.append(f"| `{panel_id}` | `{component_path}` | {status} |")

    report.append("")
    report.append("---")
    report.append("")

    # Section 5: Recommendations
    report.append("## 5. Recommendations")
    report.append("")

    recommendations = []

    # Check for common issues
    for user_id in test_users:
        layout = load_user_layout(user_id)
        if layout and "_error" in layout:
            recommendations.append(
                f"Fix JSON syntax error in `data/users/{user_id}/ui/right_pane_layout.json`"
            )

    # Check for missing components
    for panel_id, component_path in component_map.items():
        full_path = PROJECT_ROOT / component_path
        if not full_path.exists():
            recommendations.append(
                f"Missing component file: `{component_path}` (panel ID: `{panel_id}`)"
            )

    if recommendations:
        for i, rec in enumerate(recommendations, 1):
            report.append(f"{i}. {rec}")
    else:
        report.append("✅ **No issues found** — All configurations valid!")

    report.append("")
    report.append("---")
    report.append("")

    # Section 6: Quick Actions
    report.append("## 6. Quick Actions")
    report.append("")
    report.append("### Create Test Override")
    report.append("```bash")
    report.append("mkdir -p data/users/TEST/ui")
    report.append("cat > data/users/TEST/ui/right_pane_layout.json << 'EOF'")
    report.append("{")
    report.append('  "version": 2,')
    report.append('  "overrides": {')
    report.append('    "photo_coach": {')
    report.append('      "visible": {"life_os": false}')
    report.append("    }")
    report.append("  }")
    report.append("}")
    report.append("EOF")
    report.append("```")
    report.append("")

    report.append("### Validate All User Layouts")
    report.append("```bash")
    report.append("for user_dir in data/users/*/ui; do")
    report.append("  if [ -f \"$user_dir/right_pane_layout.json\" ]; then")
    report.append("    echo \"Validating $user_dir/right_pane_layout.json\"")
    report.append("    cat \"$user_dir/right_pane_layout.json\" | python3 -m json.tool > /dev/null")
    report.append("  fi")
    report.append("done")
    report.append("```")
    report.append("")

    report.append("### Reset User Layout")
    report.append("```bash")
    report.append("rm data/users/TEST/ui/right_pane_layout.json")
    report.append("# Or via API:")
    report.append("curl -X DELETE http://localhost:8000/ui/config/TEST/right_pane_layout")
    report.append("```")
    report.append("")

    report.append("---")
    report.append("")
    report.append("**End of Report**")

    return "\n".join(report)


def main():
    """Main entry point."""
    print("🔍 Analyzing persona panel configuration system...")
    print("")

    # Generate report
    report_content = generate_report()

    # Write to file
    output_dir = PROJECT_ROOT / "docs" / "ops"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / "RIGHT_PANE_DEBUG_REPORT.md"

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(report_content)

    print(f"✅ Report generated: {output_file}")
    print("")
    print("Summary:")

    # Print quick summary
    analysis = analyze_persona_config()
    test_users = get_test_users()

    users_with_overrides = sum(
        1 for user_id in test_users if load_user_layout(user_id) is not None
    )

    print(f"  - Total personas: {analysis['total_personas']}")
    print(f"  - Test users: {len(test_users)}")
    print(f"  - Users with overrides: {users_with_overrides}")
    print("")
    print(f"📄 View full report: docs/ops/RIGHT_PANE_DEBUG_REPORT.md")


if __name__ == "__main__":
    main()
