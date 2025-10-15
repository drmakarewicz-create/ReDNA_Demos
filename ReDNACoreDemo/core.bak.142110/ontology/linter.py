#!/usr/bin/env python3
"""
DNA Registry Linter
===================

Validates dna_registry.json against rules:
1. Depth ≤ 3 (Umbrella → Sub → Sub-Sub)
2. Unique id and path
3. Valid parent references
4. sensitive=true requires consent_required=true
5. New nodes (.v1) must have status="prototype", ai_upgradable=true
6. Edge validation (no is_a/part_of cycles)
"""

import argparse
import json
import sys
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set, Tuple


class DNALinter:
    def __init__(self, registry_path: Path):
        self.registry_path = registry_path
        with open(registry_path) as f:
            self.data = json.load(f)

        self.containers = self.data.get("containers", [])
        self.errors = []
        self.warnings = []

    def lint(self) -> Tuple[List[str], List[str]]:
        """Run all linter rules."""
        self._check_depth()
        self._check_uniqueness()
        self._check_parent_refs()
        self._check_sensitive_consent()
        self._check_prototype_standards()
        self._check_edges()

        return self.errors, self.warnings

    def _check_depth(self):
        """Rule: depth ≤ 3 (Umbrella.Sub.SubSub)"""
        for container in self.containers:
            path = container.get("path", "")
            depth = len(path.split("."))
            if depth > 3:
                self.warnings.append(
                    f"Depth advisory: {path} has depth {depth} (>3)"
                )

    def _check_uniqueness(self):
        """Rule: unique id and path"""
        seen_ids = set()
        seen_paths = set()

        for container in self.containers:
            cid = container.get("id")
            path = container.get("path")

            if cid in seen_ids:
                self.errors.append(f"Duplicate ID: {cid}")
            seen_ids.add(cid)

            if path in seen_paths:
                self.errors.append(f"Duplicate path: {path}")
            seen_paths.add(path)

    def _check_parent_refs(self):
        """Rule: parent must exist for child nodes"""
        paths = {c.get("path") for c in self.containers}

        for container in self.containers:
            path = container.get("path", "")
            parts = path.split(".")

            if len(parts) > 1:
                parent_path = ".".join(parts[:-1])
                if parent_path not in paths:
                    self.errors.append(
                        f"Missing parent: {path} requires {parent_path}"
                    )

    def _check_sensitive_consent(self):
        """Rule: sensitive=true requires consent_required=true"""
        for container in self.containers:
            if container.get("sensitive", False):
                if not container.get("consent_required", False):
                    self.warnings.append(
                        f"Sensitive without consent: {container.get('id')}"
                    )

    def _check_prototype_standards(self):
        """Rule: .v1 nodes must be prototype, ai_upgradable"""
        for container in self.containers:
            cid = container.get("id", "")
            version = container.get("version", 0)

            if version == 1 and cid.endswith(".v1"):
                status = container.get("status")
                ai_upgradable = container.get("ai_upgradable", False)

                if status != "prototype":
                    self.warnings.append(
                        f"V1 without prototype status: {cid} (status={status})"
                    )

                if not ai_upgradable:
                    self.warnings.append(
                        f"V1 without ai_upgradable: {cid}"
                    )

    def _check_edges(self):
        """Rule: validate edges, no is_a/part_of cycles"""
        graph = defaultdict(list)

        for container in self.containers:
            cid = container.get("id")
            edges = container.get("edges", [])

            for edge in edges:
                edge_type = edge.get("type")
                target = edge.get("to")

                if edge_type in ["is_a", "part_of"]:
                    graph[cid].append(target)

        visited = set()
        rec_stack = set()

        def has_cycle(node):
            visited.add(node)
            rec_stack.add(node)

            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True

            rec_stack.remove(node)
            return False

        for node in graph:
            if node not in visited:
                if has_cycle(node):
                    self.errors.append(f"Cycle detected in is_a/part_of edges involving {node}")

    def write_report(self, report_path: Path):
        """Write linter report to file."""
        with open(report_path, 'w') as f:
            f.write("DNA Registry Linter Report\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"Registry: {self.registry_path}\n")
            f.write(f"Total containers: {len(self.containers)}\n\n")

            if self.errors:
                f.write(f"ERRORS ({len(self.errors)}):\n")
                for error in self.errors:
                    f.write(f"  ❌ {error}\n")
                f.write("\n")
            else:
                f.write("✅ No errors found\n\n")

            if self.warnings:
                f.write(f"WARNINGS ({len(self.warnings)}):\n")
                for warning in self.warnings:
                    f.write(f"  ⚠️  {warning}\n")
                f.write("\n")
            else:
                f.write("✅ No warnings\n\n")

            f.write(f"\nLinter exit code: {1 if self.errors else 0}\n")


def main():
    parser = argparse.ArgumentParser(description="Lint DNA registry")
    parser.add_argument("--registry", required=True, help="Path to dna_registry.json")
    parser.add_argument("--report", required=True, help="Output report path")
    args = parser.parse_args()

    linter = DNALinter(Path(args.registry))
    errors, warnings = linter.lint()
    linter.write_report(Path(args.report))

    if errors:
        print(f"❌ Linter found {len(errors)} error(s)")
        sys.exit(1)
    else:
        print(f"✅ Linter passed (0 errors, {len(warnings)} warnings)")
        sys.exit(0)


if __name__ == "__main__":
    main()
