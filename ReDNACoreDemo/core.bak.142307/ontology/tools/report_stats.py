#!/usr/bin/env python3
"""Generate ontology statistics JSON."""
import json
from pathlib import Path
from collections import Counter


def main():
    registry_path = Path("ReDNACoreDemo/core/ontology/dna_registry.json")
    with open(registry_path) as f:
        data = json.load(f)

    containers = data.get("containers", [])

    stats = {
        "total_containers": len(containers),
        "by_namespace": dict(Counter(c.get("namespace") for c in containers)),
        "by_status": dict(Counter(c.get("status", "unknown") for c in containers)),
        "sensitive_count": sum(1 for c in containers if c.get("sensitive", False)),
        "consent_required_count": sum(1 for c in containers if c.get("consent_required", False)),
        "ai_upgradable_count": sum(1 for c in containers if c.get("ai_upgradable", False)),
        "depth_distribution": dict(Counter(len(c.get("path", "").split(".")) for c in containers)),
        "edges_count": sum(len(c.get("edges", [])) for c in containers),
        "version": data.get("metadata", {}).get("version", "unknown")
    }

    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
