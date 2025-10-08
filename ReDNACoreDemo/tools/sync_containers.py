#!/usr/bin/env python3
"""
Sync DNA container definitions across the ReDNA system.

This script ensures consistency between:
1. Backend trait registry (core/hierarchy.py)
2. Frontend UI (web/src/components/rr-dna-panel.tsx)
3. Documentation (docs/RR_BASELINE_REQUIREMENT.md)

Run this script whenever you modify REGISTRY in hierarchy.py.

Usage:
    python tools/sync_containers.py [--dry-run] [--mode=merge|replace]

Options:
    --dry-run          Show what would change without modifying files
    --mode=merge       Add backend containers to frontend (preserve planned containers) [default]
    --mode=replace     Replace frontend with only backend containers (remove unimplemented)
"""

import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

# Paths relative to repo root
REPO_ROOT = Path(__file__).parent.parent.parent
HIERARCHY_FILE = REPO_ROOT / "ReDNACoreDemo" / "core" / "hierarchy.py"
RR_PANEL_FILE = REPO_ROOT / "web" / "src" / "components" / "rr-dna-panel.tsx"
BASELINE_DOC = REPO_ROOT / "docs" / "RR_BASELINE_REQUIREMENT.md"


# Container display configuration
# Maps backend container keys to frontend display names and icons
CONTAINER_CONFIG = {
    "Identity": {"icon": "🪪", "sensitive": False},
    "PaDNA": {"icon": "👤", "sensitive": False},
    "Writing": {"icon": "✍️", "sensitive": False},
    "Personality": {"icon": "🎭", "sensitive": False},
    "Emotion": {"icon": "💭", "sensitive": False},
    "Social": {"icon": "👥", "sensitive": False},
    "Family": {"icon": "👪", "sensitive": True},
    "Cognitive": {"icon": "🧠", "sensitive": False},
    "Work": {"icon": "💼", "sensitive": False},
    "Taste": {"icon": "🎬", "sensitive": False},
    "Gaming": {"icon": "🎮", "sensitive": False},
    "Health": {"icon": "🏥", "sensitive": True},
    "Finance": {"icon": "💰", "sensitive": True},
    "Routine": {"icon": "📅", "sensitive": False},
    "Learning": {"icon": "📚", "sensitive": False},
    "Behavior": {"icon": "⚡", "sensitive": False},
    "Values": {"icon": "⭐", "sensitive": True},
    "Digital": {"icon": "💻", "sensitive": False},
    "Cultural": {"icon": "🌍", "sensitive": True},
    "Environmental": {"icon": "🌱", "sensitive": False},
    "Motivations": {"icon": "🎯", "sensitive": False},
    "Safety": {"icon": "🛡️", "sensitive": False},

    # Backend hierarchy containers (map to frontend display names)
    "PaDNA.HairDNA": {"parent": "PaDNA"},
    "PaDNA.EyeDNA": {"parent": "PaDNA"},
    "PaDNA.SkinDNA": {"parent": "PaDNA"},
    "PaDNA.FacialDNA": {"parent": "PaDNA"},
    "PaDNA.BodyDNA": {"parent": "PaDNA"},
    "PaDNA.Other": {"parent": "PaDNA"},
    "PsyDNA.PersonalityDNA": {"parent": "Personality"},
    "PsyDNA.MotivationDNA": {"parent": "Motivations"},
    "PsyDNA.BeliefDNA": {"parent": "Values"},
    "EmDNA": {"parent": "Emotion"},
    "CogDNA": {"parent": "Cognitive"},
    "SocDNA": {"parent": "Social"},
    "BehDNA": {"parent": "Behavior"},
    "HistDNA": {"parent": "Identity"},
    "PrefDNA": {"parent": "Taste"},
    "SkillDNA": {"parent": "Work"},
    "MetaDNA": {"parent": "Digital"},
}


def extract_registry_containers() -> Set[str]:
    """Extract all top-level container keys from hierarchy.py REGISTRY."""
    if not HIERARCHY_FILE.exists():
        print(f"❌ Error: {HIERARCHY_FILE} not found")
        sys.exit(1)

    content = HIERARCHY_FILE.read_text()

    # Find REGISTRY dict
    registry_match = re.search(r'REGISTRY:\s*Dict\[str,\s*List\[str\]\]\s*=\s*\{(.*?)\n\}', content, re.DOTALL)
    if not registry_match:
        print("❌ Error: Could not find REGISTRY dict in hierarchy.py")
        sys.exit(1)

    registry_content = registry_match.group(1)

    # Extract all quoted keys (container names)
    containers = set()
    for match in re.finditer(r'"([^"]+)":', registry_content):
        container_key = match.group(1)
        containers.add(container_key)

    return containers


def map_backend_to_frontend(backend_containers: Set[str]) -> List[Tuple[str, str, str, bool]]:
    """
    Map backend container keys to frontend display format.

    Returns list of tuples: (key, display_name, icon, sensitive)
    """
    frontend_containers = {}

    for backend_key in backend_containers:
        if backend_key in CONTAINER_CONFIG:
            config = CONTAINER_CONFIG[backend_key]

            # If it's a parent mapping, map to the parent container
            if "parent" in config:
                parent = config["parent"]
                if parent not in frontend_containers:
                    parent_config = CONTAINER_CONFIG.get(parent, {"icon": "📦", "sensitive": False})
                    frontend_containers[parent] = (
                        parent,
                        parent,  # Use same key as display name
                        parent_config["icon"],
                        parent_config["sensitive"]
                    )
            else:
                # Top-level container
                frontend_containers[backend_key] = (
                    backend_key,
                    backend_key,  # Use same key as display name
                    config["icon"],
                    config["sensitive"]
                )

    # Sort by key for consistent output
    return sorted(frontend_containers.values(), key=lambda x: x[0])


def extract_existing_frontend_containers() -> Dict[str, Tuple[str, str, str, bool]]:
    """Extract currently defined containers from rr-dna-panel.tsx."""
    if not RR_PANEL_FILE.exists():
        return {}

    content = RR_PANEL_FILE.read_text()
    pattern = r'const DNA_CONTAINERS = \[(.*?)\];'
    match = re.search(pattern, content, re.DOTALL)

    if not match:
        return {}

    containers_str = match.group(1)
    containers = {}

    # Parse each container entry
    # Format: { key: 'PaDNA', name: 'Physical Appearance', icon: '👤', sensitive: false },
    entry_pattern = r"\{\s*key:\s*'([^']+)',\s*name:\s*'([^']+)',\s*icon:\s*'([^']+)',\s*sensitive:\s*(true|false)\s*\}"

    for match in re.finditer(entry_pattern, containers_str):
        key = match.group(1)
        name = match.group(2)
        icon = match.group(3)
        sensitive = match.group(4) == 'true'
        containers[key] = (key, name, icon, sensitive)

    return containers


def update_frontend_containers(containers: List[Tuple[str, str, str, bool]], dry_run: bool = False, mode: str = "merge") -> bool:
    """Update DNA_CONTAINERS array in rr-dna-panel.tsx.

    Args:
        containers: List of backend containers to sync
        dry_run: If True, only show what would change
        mode: 'merge' to preserve planned containers, 'replace' to remove unimplemented
    """
    if not RR_PANEL_FILE.exists():
        print(f"⚠️  Warning: {RR_PANEL_FILE} not found, skipping frontend update")
        return False

    content = RR_PANEL_FILE.read_text()

    if mode == "merge":
        # Get existing frontend containers
        existing = extract_existing_frontend_containers()

        # Merge: backend containers + planned frontend-only containers
        merged = existing.copy()
        backend_keys = {key for key, _, _, _ in containers}

        # Update with backend containers (but preserve existing display names/icons if they exist)
        for key, name, icon, sensitive in containers:
            if key in existing:
                # Container exists in frontend - preserve its display customizations
                merged[key] = existing[key]
            else:
                # New container from backend - add it
                merged[key] = (key, name, icon, sensitive)

        # Sort by key for consistent output
        final_containers = sorted(merged.values(), key=lambda x: x[0])

        planned_keys = set(existing.keys()) - backend_keys
        if planned_keys:
            print(f"   Preserving {len(planned_keys)} planned container(s) not yet in backend: {', '.join(sorted(planned_keys))}")
    else:
        # Replace mode: only use backend containers
        final_containers = containers

    # Generate new DNA_CONTAINERS array
    container_lines = []
    for key, name, icon, sensitive in final_containers:
        sensitive_str = "true" if sensitive else "false"
        container_lines.append(f"  {{ key: '{key}', name: '{name}', icon: '{icon}', sensitive: {sensitive_str} }},")

    new_containers = "const DNA_CONTAINERS = [\n" + "\n".join(container_lines) + "\n];"

    # Replace existing DNA_CONTAINERS array
    pattern = r'const DNA_CONTAINERS = \[.*?\];'
    new_content = re.sub(pattern, new_containers, content, flags=re.DOTALL)

    if new_content == content:
        print("✅ Frontend containers already up to date")
        return False

    if dry_run:
        print("📝 Would update frontend containers:")
        print(new_containers)
        return True

    RR_PANEL_FILE.write_text(new_content)
    print(f"✅ Updated frontend containers in {RR_PANEL_FILE.relative_to(REPO_ROOT)}")
    return True


def update_baseline_doc(containers: List[Tuple[str, str, str, bool]], dry_run: bool = False) -> bool:
    """Update container list in RR_BASELINE_REQUIREMENT.md."""
    if not BASELINE_DOC.exists():
        print(f"⚠️  Warning: {BASELINE_DOC} not found, skipping doc update")
        return False

    content = BASELINE_DOC.read_text()

    # Generate new container list for documentation
    container_list = []
    for key, name, icon, sensitive in containers:
        sensitive_tag = " (SENSITIVE)" if sensitive else ""
        container_list.append(f"- **{icon} {name}**{sensitive_tag}")

    new_list = "\n".join(container_list)

    # Find and replace the container list section
    # Look for marker comments or specific section heading
    marker_start = "<!-- CONTAINER_LIST_START -->"
    marker_end = "<!-- CONTAINER_LIST_END -->"

    if marker_start in content and marker_end in content:
        # Markers exist, replace between them
        pattern = f"{re.escape(marker_start)}.*?{re.escape(marker_end)}"
        replacement = f"{marker_start}\n{new_list}\n{marker_end}"
        new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    else:
        # No markers, insert them after "### 1. Diverse Fictional Users" section
        section_pattern = r'(### 1\. Diverse Fictional Users.*?\n\n)'
        if re.search(section_pattern, content, re.DOTALL):
            replacement = f"\\1{marker_start}\n{new_list}\n{marker_end}\n\n"
            new_content = re.sub(section_pattern, replacement, content, flags=re.DOTALL)
        else:
            print("⚠️  Warning: Could not find insertion point in baseline doc")
            return False

    if new_content == content:
        print("✅ Baseline documentation already up to date")
        return False

    if dry_run:
        print("📝 Would update baseline documentation with:")
        print(new_list)
        return True

    BASELINE_DOC.write_text(new_content)
    print(f"✅ Updated container list in {BASELINE_DOC.relative_to(REPO_ROOT)}")
    return True


def main():
    dry_run = "--dry-run" in sys.argv

    # Parse mode argument
    mode = "merge"  # Default to merge mode (preserve planned containers)
    for arg in sys.argv:
        if arg.startswith("--mode="):
            mode = arg.split("=")[1]
            if mode not in ["merge", "replace"]:
                print(f"❌ Error: Invalid mode '{mode}'. Use 'merge' or 'replace'")
                sys.exit(1)

    print("🔍 Scanning hierarchy.py for container definitions...")
    backend_containers = extract_registry_containers()
    print(f"   Found {len(backend_containers)} backend containers")

    print("\n📋 Mapping backend containers to frontend display format...")
    frontend_containers = map_backend_to_frontend(backend_containers)
    print(f"   Mapped to {len(frontend_containers)} frontend containers")

    print(f"\n🔄 Syncing container definitions (mode: {mode})...")

    frontend_changed = update_frontend_containers(frontend_containers, dry_run, mode)
    doc_changed = update_baseline_doc(frontend_containers, dry_run)

    if dry_run:
        if frontend_changed or doc_changed:
            print("\n⚠️  Dry run complete. Re-run without --dry-run to apply changes.")
            sys.exit(1)
        else:
            print("\n✅ Dry run complete. No changes needed.")
            sys.exit(0)
    else:
        if frontend_changed or doc_changed:
            print("\n✅ Container sync complete!")
            print("\n📝 Next steps:")
            print("   1. Review changes in git diff")
            print("   2. Run: npm run typecheck (in web/)")
            print("   3. Commit changes with message: 'chore: sync DNA containers'")
        else:
            print("\n✅ All containers already in sync!")


if __name__ == "__main__":
    main()
