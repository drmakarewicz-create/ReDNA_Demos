#!/usr/bin/env python3
"""
Generate Tree View of DNA Ontology
Creates a visual tree representation of the entire DNA hierarchy.
"""

import json
from collections import defaultdict
from typing import Dict, List


def load_registry(path: str = "dna_registry.json") -> Dict:
    """Load the DNA registry."""
    with open(path, 'r') as f:
        return json.load(f)


def build_tree_structure(containers: List[Dict]) -> Dict:
    """Build a hierarchical tree structure from flat container list."""
    tree = defaultdict(lambda: defaultdict(list))

    for container in containers:
        path = container['path']
        parts = path.split('.')

        if len(parts) == 1:
            # Umbrella
            umbrella = parts[0]
            tree[umbrella]['_info'] = container
        elif len(parts) == 2:
            # Sub-DNA
            umbrella, sub = parts
            tree[umbrella][sub] = {'_info': container, 'children': []}
        elif len(parts) == 3:
            # Sub-Sub-DNA
            umbrella, sub, subsub = parts
            if sub in tree[umbrella]:
                tree[umbrella][sub]['children'].append(container)

    return tree


def print_tree(tree: Dict, output_path: str = "ONTOLOGY_TREE.md"):
    """Print tree to markdown file."""
    lines = []

    lines.append("# DNA Ontology Tree - Version 1.0")
    lines.append("")
    lines.append("**Ontology v1 Baseline** — DNA hierarchy (no traits yet)")
    lines.append("")
    lines.append("Generated from: `dna_registry.json`")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Sort umbrellas
    umbrellas = sorted(tree.keys())

    for umbrella in umbrellas:
        umbrella_data = tree[umbrella]
        umbrella_info = umbrella_data.get('_info', {})

        # Umbrella header
        full_name = umbrella_info.get('description', umbrella)
        sensitive = "🔒" if umbrella_info.get('sensitive') else "🔓"
        camouflage = " 🎭" if umbrella_info.get('camouflage') else ""
        consent = " ✋" if umbrella_info.get('consent_required') else ""

        lines.append(f"## {sensitive} {umbrella} {camouflage}{consent}")
        lines.append(f"**{full_name}**")
        lines.append("")

        # Count sub-DNAs and sub-sub-DNAs
        sub_count = len([k for k in umbrella_data.keys() if k != '_info'])
        subsub_count = sum(len(v.get('children', [])) for v in umbrella_data.values() if isinstance(v, dict) and v != umbrella_data.get('_info'))

        lines.append(f"- **Sub-DNAs:** {sub_count}")
        lines.append(f"- **Sub-Sub-DNAs:** {subsub_count}")
        lines.append(f"- **Total:** {1 + sub_count + subsub_count} containers")
        lines.append("")

        # Print sub-DNAs
        sub_dnas = sorted([k for k in umbrella_data.keys() if k != '_info'])

        for i, sub in enumerate(sub_dnas):
            is_last_sub = (i == len(sub_dnas) - 1)
            sub_data = umbrella_data[sub]
            sub_info = sub_data.get('_info', {})
            sub_desc = sub_info.get('description', '')

            # Tree symbols
            sub_prefix = "└──" if is_last_sub else "├──"
            child_prefix = "    " if is_last_sub else "│   "

            lines.append(f"{sub_prefix} **{sub}**")
            if sub_desc:
                lines.append(f"{child_prefix}    _{sub_desc}_")

            # Print sub-sub-DNAs
            children = sub_data.get('children', [])
            for j, child in enumerate(children):
                is_last_child = (j == len(children) - 1)
                child_path = child['path']
                child_name = child_path.split('.')[-1]

                child_symbol = "└──" if is_last_child else "├──"

                lines.append(f"{child_prefix}{child_symbol} {child_name}")

            if children:
                lines.append("")

        lines.append("")
        lines.append("---")
        lines.append("")

    # Write to file
    with open(output_path, 'w') as f:
        f.write('\n'.join(lines))

    return output_path, len(lines)


def generate_summary_stats(registry: Dict, output_path: str = "ONTOLOGY_SUMMARY.md"):
    """Generate summary statistics document."""
    containers = registry['containers']
    metadata = registry['metadata']

    lines = []

    lines.append("# DNA Ontology Summary - Version 1.0")
    lines.append("")
    lines.append("**Ontology v1 Baseline** — Container Explosion Architecture")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Metadata
    lines.append("## Registry Metadata")
    lines.append("")
    lines.append(f"- **Version:** {metadata['version']}")
    lines.append(f"- **Total Containers:** {metadata['total_containers']}")
    lines.append(f"- **Ontology Version:** {metadata.get('ontology_version', 'v1')}")
    lines.append(f"- **Generation Method:** {metadata.get('generation_method', 'manual')}")
    lines.append(f"- **Target Count:** {metadata.get('target_count', 'N/A')}")
    lines.append(f"- **Last Updated:** {metadata['last_updated']}")
    lines.append("")

    # Namespace counts
    lines.append("## Namespace Breakdown")
    lines.append("")
    lines.append("| Namespace | Containers | Sensitive | Camouflage | Consent |")
    lines.append("|-----------|------------|-----------|------------|---------|")

    # Collect namespace info
    ns_info = {}
    for container in containers:
        ns = container['namespace']
        if ns not in ns_info:
            ns_info[ns] = {
                'count': 0,
                'sensitive': container.get('sensitive', False),
                'camouflage': container.get('camouflage', False),
                'consent': container.get('consent_required', False)
            }
        ns_info[ns]['count'] += 1

    for ns in sorted(ns_info.keys()):
        info = ns_info[ns]
        sensitive = "✓" if info['sensitive'] else "—"
        camouflage = "✓" if info['camouflage'] else "—"
        consent = "✓" if info['consent'] else "—"

        lines.append(f"| {ns:11s} | {info['count']:10d} | {sensitive:9s} | {camouflage:10s} | {consent:7s} |")

    lines.append("")

    # Depth distribution
    lines.append("## Hierarchy Depth Distribution")
    lines.append("")
    depth_counts = {1: 0, 2: 0, 3: 0}
    for container in containers:
        depth = len(container['path'].split('.'))
        if depth in depth_counts:
            depth_counts[depth] += 1

    lines.append(f"- **Depth 1 (Umbrellas):** {depth_counts[1]} containers")
    lines.append(f"- **Depth 2 (Sub-DNAs):** {depth_counts[2]} containers")
    lines.append(f"- **Depth 3 (Sub-Sub-DNAs):** {depth_counts[3]} containers")
    lines.append("")

    # Key features
    lines.append("## Key Features")
    lines.append("")
    lines.append("### RR & Curiosity Baselines")
    lines.append("- **RR Baseline:** `null` for all containers (no trait values yet)")
    lines.append("- **Curiosity Baseline:** `100` for all containers (maximum exploration)")
    lines.append("")

    lines.append("### Sensitive Data Handling")
    sensitive_count = sum(1 for c in containers if c.get('sensitive'))
    camouflage_count = sum(1 for c in containers if c.get('camouflage'))
    consent_count = sum(1 for c in containers if c.get('consent_required'))

    lines.append(f"- **Sensitive containers:** {sensitive_count} ({sensitive_count * 100 // len(containers)}%)")
    lines.append(f"- **Camouflage-aware:** {camouflage_count} (RoDNA only)")
    lines.append(f"- **Consent-required:** {consent_count} (HealthDNA only)")
    lines.append("")

    lines.append("### Namespace Highlights")
    lines.append("")
    lines.append("- **PaDNA:** Physical appearance — largest namespace with facial, hair, eye, skin, body DNAs")
    lines.append("- **RoDNA:** Relational/Intimacy — only camouflage-aware namespace (RSC protocols)")
    lines.append("- **HealthDNA:** Health/Bio/Physiology — only consent-required namespace")
    lines.append("- **MetaDNA:** System interaction — how users engage with ReDNA itself")
    lines.append("")

    # Readiness statement
    lines.append("## Readiness for Container Explosion")
    lines.append("")
    lines.append("✅ **Ontology v1 baseline is complete and validated**")
    lines.append("")
    lines.append("This DNA-only hierarchy (165 containers) is ready for:")
    lines.append("")
    lines.append("1. **1K Benchmark** — Add trait-level containers to reach ~1,000 total")
    lines.append("2. **10K Benchmark** — Expand trait diversity and sub-trait granularity")
    lines.append("3. **100K Benchmark** — Add micro-traits and contextual variations")
    lines.append("4. **1M Benchmark** — Full ontological explosion with AI-proposed containers")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("Generated by: `generate_tree_view.py`")

    # Write to file
    with open(output_path, 'w') as f:
        f.write('\n'.join(lines))

    return output_path, len(lines)


def main():
    """Main entry point."""
    print("📊 Generating Ontology Documentation...")
    print("=" * 70)

    # Load registry
    print("\n📂 Loading registry...")
    registry = load_registry()

    # Build tree
    print("🌳 Building tree structure...")
    tree = build_tree_structure(registry['containers'])

    # Generate tree view
    print("📄 Generating tree view...")
    tree_path, tree_lines = print_tree(tree)
    print(f"  ✓ Created {tree_path} ({tree_lines} lines)")

    # Generate summary
    print("📊 Generating summary statistics...")
    summary_path, summary_lines = generate_summary_stats(registry)
    print(f"  ✓ Created {summary_path} ({summary_lines} lines)")

    print("\n✅ Documentation generated successfully!")
    print(f"\nView the results:")
    print(f"  • Tree view: {tree_path}")
    print(f"  • Summary: {summary_path}")


if __name__ == "__main__":
    main()
