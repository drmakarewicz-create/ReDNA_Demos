#!/usr/bin/env python3
"""
Analyze ReDNA cross-link network topology and generate statistics
"""

import json
import yaml
from collections import defaultdict, Counter
from pathlib import Path

REGISTRY_PATH = Path("ReDNACoreDemo/core/ontology/dna_registry.json")
CROSS_LINKS_PATH = Path("ReDNACoreDemo/core/ontology/cross_links.yaml")
OUTPUT_PATH = Path("ReDNACoreDemo/core/ontology/reports/NETWORK_ANALYSIS.md")


def load_data():
    with open(REGISTRY_PATH) as f:
        registry = json.load(f)
    with open(CROSS_LINKS_PATH) as f:
        cross_links = yaml.safe_load(f)
    return registry, cross_links


def analyze_network(registry, cross_links):
    """Analyze network topology and generate statistics."""

    # Build namespace index
    containers_by_ns = defaultdict(list)
    for c in registry['containers']:
        containers_by_ns[c['namespace']].append(c)

    # Edge analysis
    edges = cross_links.get('edges', [])

    # Domain pair analysis
    domain_pairs = Counter()
    namespace_in_degree = Counter()
    namespace_out_degree = Counter()

    for edge in edges:
        from_ns = edge['from'].split('.')[0]
        to_ns = edge['to'].split('.')[0]

        domain_pairs[(from_ns, to_ns)] += 1
        namespace_out_degree[from_ns] += 1
        namespace_in_degree[to_ns] += 1

    # Container hub analysis (most connected containers)
    container_degree = Counter()
    for edge in edges:
        container_degree[edge['from']] += 1
        container_degree[edge['to']] += 1

    # Edge type by domain pair
    edge_types_by_pair = defaultdict(Counter)
    for edge in edges:
        from_ns = edge['from'].split('.')[0]
        to_ns = edge['to'].split('.')[0]
        edge_types_by_pair[(from_ns, to_ns)][edge['type']] += 1

    # Confidence by domain pair
    confidence_by_pair = defaultdict(list)
    for edge in edges:
        from_ns = edge['from'].split('.')[0]
        to_ns = edge['to'].split('.')[0]
        confidence_by_pair[(from_ns, to_ns)].append(edge['confidence'])

    return {
        'total_edges': len(edges),
        'total_containers': len(registry['containers']),
        'domain_pairs': domain_pairs,
        'namespace_in_degree': namespace_in_degree,
        'namespace_out_degree': namespace_out_degree,
        'container_hubs': container_degree.most_common(20),
        'edge_types_by_pair': edge_types_by_pair,
        'confidence_by_pair': confidence_by_pair,
        'containers_by_ns': {ns: len(containers) for ns, containers in containers_by_ns.items()},
    }


def generate_report(stats):
    """Generate markdown analysis report."""

    lines = [
        "# ReDNA Cross-Link Network Analysis",
        "",
        f"**Total Containers**: {stats['total_containers']}",
        f"**Total Edges**: {stats['total_edges']}",
        f"**Network Density**: {stats['total_edges'] / stats['total_containers']:.3f}",
        "",
        "---",
        "",
        "## Domain Pair Coverage",
        "",
        "| From → To | Edges | Avg Confidence | Primary Type |",
        "|-----------|-------|----------------|--------------|",
    ]

    for (from_ns, to_ns), count in stats['domain_pairs'].most_common():
        avg_conf = sum(stats['confidence_by_pair'][(from_ns, to_ns)]) / len(stats['confidence_by_pair'][(from_ns, to_ns)])
        primary_type = stats['edge_types_by_pair'][(from_ns, to_ns)].most_common(1)[0][0]
        lines.append(f"| {from_ns} → {to_ns} | {count} | {avg_conf:.2f} | {primary_type} |")

    lines.extend([
        "",
        "---",
        "",
        "## Namespace Connectivity",
        "",
        "| Namespace | Containers | Out-Degree | In-Degree | Total Degree |",
        "|-----------|------------|------------|-----------|--------------|",
    ])

    for ns in sorted(stats['containers_by_ns'].keys()):
        container_count = stats['containers_by_ns'][ns]
        out_deg = stats['namespace_out_degree'].get(ns, 0)
        in_deg = stats['namespace_in_degree'].get(ns, 0)
        total_deg = out_deg + in_deg
        lines.append(f"| {ns} | {container_count} | {out_deg} | {in_deg} | {total_deg} |")

    lines.extend([
        "",
        "---",
        "",
        "## Network Hubs (Top 20 Most Connected Containers)",
        "",
        "| Rank | Container | Degree |",
        "|------|-----------|--------|",
    ])

    for rank, (container, degree) in enumerate(stats['container_hubs'], 1):
        container_name = container.split('.')[-1]
        namespace = container.split('.')[0]
        lines.append(f"| {rank} | {namespace}.{container_name} | {degree} |")

    lines.extend([
        "",
        "---",
        "",
        "## Edge Type Distribution by Domain Pair",
        "",
    ])

    for (from_ns, to_ns), type_counts in sorted(stats['edge_types_by_pair'].items()):
        total = sum(type_counts.values())
        lines.append(f"### {from_ns} → {to_ns} ({total} edges)")
        lines.append("")
        for edge_type, count in type_counts.most_common():
            pct = count / total * 100
            lines.append(f"- **{edge_type}**: {count} ({pct:.1f}%)")
        lines.append("")

    lines.extend([
        "---",
        "",
        "## Network Topology Insights",
        "",
        "### Hub Namespaces (High Total Degree)",
    ])

    total_degrees = {ns: stats['namespace_out_degree'].get(ns, 0) + stats['namespace_in_degree'].get(ns, 0)
                     for ns in stats['containers_by_ns'].keys()}

    for ns, degree in sorted(total_degrees.items(), key=lambda x: x[1], reverse=True)[:5]:
        lines.append(f"- **{ns}**: {degree} edges ({degree / stats['total_edges'] * 100:.1f}% of network)")

    lines.extend([
        "",
        "### Isolated Namespaces (Low Connectivity)",
    ])

    for ns, degree in sorted(total_degrees.items(), key=lambda x: x[1])[:5]:
        if degree > 0:
            lines.append(f"- **{ns}**: {degree} edges ({degree / stats['total_edges'] * 100:.1f}% of network)")

    lines.extend([
        "",
        "### Cross-Domain Bridges (Diverse Connections)",
    ])

    # Find namespaces that connect to many others
    ns_connections = defaultdict(set)
    for (from_ns, to_ns) in stats['domain_pairs'].keys():
        ns_connections[from_ns].add(to_ns)
        ns_connections[to_ns].add(from_ns)

    for ns, connected_to in sorted(ns_connections.items(), key=lambda x: len(x[1]), reverse=True)[:5]:
        lines.append(f"- **{ns}**: Connects to {len(connected_to)} different namespaces")

    lines.extend([
        "",
        "---",
        "",
        f"*Generated from {stats['total_containers']} containers and {stats['total_edges']} edges*",
    ])

    return '\n'.join(lines)


def main():
    print("📊 Analyzing ReDNA cross-link network topology...")

    registry, cross_links = load_data()
    stats = analyze_network(registry, cross_links)
    report = generate_report(stats)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(report)

    print(f"✅ Network analysis complete")
    print(f"   Report: {OUTPUT_PATH}")
    print(f"\n📈 Summary:")
    print(f"   Total edges: {stats['total_edges']}")
    print(f"   Domain pairs: {len(stats['domain_pairs'])}")
    print(f"   Network density: {stats['total_edges'] / stats['total_containers']:.3f}")
    print(f"   Top hub: {stats['container_hubs'][0][0].split('.')[-1]} (degree {stats['container_hubs'][0][1]})")


if __name__ == "__main__":
    main()
