"""
DNA Registry Linter

Validates DNA container registry against JSON Schema and additional business rules:
- Schema compliance (dna_registry.schema.json)
- Uniqueness constraints (no duplicate IDs or paths)
- Referential integrity (dependencies/correlations point to valid containers)
- Cycle detection (no circular dependencies in is_a/part_of/derived_from edges)
- Namespace compliance (paths match namespace naming patterns)
- Status transition rules (valid status lifecycle transitions)
- Privacy rules (sensitive namespaces marked correctly)
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

try:
    import jsonschema
    from jsonschema import Draft7Validator, ValidationError
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False
    print("Warning: jsonschema not installed. Schema validation disabled.")

import yaml


class LintError:
    """Represents a validation error found during linting."""

    def __init__(
        self,
        severity: str,  # "error", "warning", "info"
        category: str,  # "schema", "uniqueness", "integrity", "cycles", "namespace", "status", "privacy"
        message: str,
        container_id: str | None = None,
        location: str | None = None
    ):
        self.severity = severity
        self.category = category
        self.message = message
        self.container_id = container_id
        self.location = location

    def __str__(self) -> str:
        parts = [f"[{self.severity.upper()}]", f"[{self.category}]"]
        if self.container_id:
            parts.append(f"[{self.container_id}]")
        if self.location:
            parts.append(f"at {self.location}")
        parts.append(self.message)
        return " ".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "severity": self.severity,
            "category": self.category,
            "message": self.message,
            "container_id": self.container_id,
            "location": self.location
        }


class RegistryLinter:
    """Validates DNA registry for correctness and consistency."""

    def __init__(
        self,
        ontology_dir: Path,
        schema_path: Path | None = None,
        namespaces_path: Path | None = None
    ):
        self.ontology_dir = Path(ontology_dir)
        self.schema_path = schema_path or (self.ontology_dir / "dna_registry.schema.json")
        self.namespaces_path = namespaces_path or (self.ontology_dir / "namespaces.yaml")

        self.errors: List[LintError] = []
        self.schema: Dict | None = None
        self.namespaces: Dict | None = None
        self.validator: Draft7Validator | None = None

        # Load schema and namespaces
        self._load_schema()
        self._load_namespaces()

    def _load_schema(self) -> None:
        """Load JSON Schema for validation."""
        if not self.schema_path.exists():
            self.errors.append(LintError(
                severity="error",
                category="schema",
                message=f"Schema file not found: {self.schema_path}"
            ))
            return

        try:
            with open(self.schema_path) as f:
                self.schema = json.load(f)

            if HAS_JSONSCHEMA:
                self.validator = Draft7Validator(self.schema)
        except Exception as e:
            self.errors.append(LintError(
                severity="error",
                category="schema",
                message=f"Failed to load schema: {e}"
            ))

    def _load_namespaces(self) -> None:
        """Load namespace definitions from YAML."""
        if not self.namespaces_path.exists():
            self.errors.append(LintError(
                severity="error",
                category="namespace",
                message=f"Namespaces file not found: {self.namespaces_path}"
            ))
            return

        try:
            with open(self.namespaces_path) as f:
                self.namespaces = yaml.safe_load(f)
        except Exception as e:
            self.errors.append(LintError(
                severity="error",
                category="namespace",
                message=f"Failed to load namespaces: {e}"
            ))

    def lint_registry(self, registry_path: Path) -> Tuple[bool, List[LintError]]:
        """
        Lint the entire registry.

        Returns:
            (is_valid, errors): True if no errors, list of all errors/warnings
        """
        self.errors = []

        if not registry_path.exists():
            self.errors.append(LintError(
                severity="error",
                category="schema",
                message=f"Registry file not found: {registry_path}"
            ))
            return False, self.errors

        # Load registry
        try:
            with open(registry_path) as f:
                registry = json.load(f)
        except Exception as e:
            self.errors.append(LintError(
                severity="error",
                category="schema",
                message=f"Failed to parse registry JSON: {e}"
            ))
            return False, self.errors

        # Run all validation checks
        self._validate_schema(registry)
        self._validate_uniqueness(registry)
        self._validate_referential_integrity(registry)
        self._validate_cycles(registry)
        self._validate_namespaces(registry)
        self._validate_status_transitions(registry)
        self._validate_privacy_rules(registry)
        self._validate_metadata_consistency(registry)

        # Check if any errors (not just warnings)
        has_errors = any(e.severity == "error" for e in self.errors)
        return not has_errors, self.errors

    def _validate_schema(self, registry: Dict) -> None:
        """Validate against JSON Schema."""
        if not HAS_JSONSCHEMA or not self.validator:
            self.errors.append(LintError(
                severity="warning",
                category="schema",
                message="JSON Schema validation skipped (jsonschema not installed)"
            ))
            return

        try:
            self.validator.validate(registry)
        except ValidationError as e:
            self.errors.append(LintError(
                severity="error",
                category="schema",
                message=f"Schema validation failed: {e.message}",
                location=".".join(str(p) for p in e.path)
            ))

    def _validate_uniqueness(self, registry: Dict) -> None:
        """Check for duplicate IDs and paths."""
        containers = registry.get("containers", [])

        seen_ids: Set[str] = set()
        seen_paths: Set[str] = set()

        for i, container in enumerate(containers):
            container_id = container.get("id")
            path = container.get("path")

            # Check duplicate IDs
            if container_id in seen_ids:
                self.errors.append(LintError(
                    severity="error",
                    category="uniqueness",
                    message=f"Duplicate container ID: {container_id}",
                    container_id=container_id,
                    location=f"containers[{i}]"
                ))
            else:
                seen_ids.add(container_id)

            # Check duplicate paths (warn, not error, since versioning allows same path)
            if path in seen_paths:
                self.errors.append(LintError(
                    severity="warning",
                    category="uniqueness",
                    message=f"Duplicate path (multiple versions): {path}",
                    container_id=container_id,
                    location=f"containers[{i}]"
                ))
            else:
                seen_paths.add(path)

    def _validate_referential_integrity(self, registry: Dict) -> None:
        """Check that all referenced containers exist."""
        containers = registry.get("containers", [])

        # Build set of valid paths (without version)
        valid_paths = {c.get("path") for c in containers if c.get("path")}

        for i, container in enumerate(containers):
            container_id = container.get("id")
            path = container.get("path")

            # Check dependencies
            for dep in container.get("dependencies", []):
                if dep not in valid_paths:
                    self.errors.append(LintError(
                        severity="error",
                        category="integrity",
                        message=f"Dependency not found: {dep}",
                        container_id=container_id,
                        location=f"containers[{i}].dependencies"
                    ))

            # Check correlations
            for corr in container.get("correlates_with", []):
                corr_path = corr.get("path") if isinstance(corr, dict) else None
                if corr_path and corr_path not in valid_paths:
                    self.errors.append(LintError(
                        severity="error",
                        category="integrity",
                        message=f"Correlation target not found: {corr_path}",
                        container_id=container_id,
                        location=f"containers[{i}].correlates_with"
                    ))

            # Check contradictions
            for contra in container.get("contradicts", []):
                if contra not in valid_paths:
                    self.errors.append(LintError(
                        severity="error",
                        category="integrity",
                        message=f"Contradiction target not found: {contra}",
                        container_id=container_id,
                        location=f"containers[{i}].contradicts"
                    ))

            # Check parent containers
            for parent in container.get("parent_containers", []):
                parent_path = parent.get("path") if isinstance(parent, dict) else None
                if parent_path and parent_path not in valid_paths:
                    self.errors.append(LintError(
                        severity="error",
                        category="integrity",
                        message=f"Parent container not found: {parent_path}",
                        container_id=container_id,
                        location=f"containers[{i}].parent_containers"
                    ))

    def _validate_cycles(self, registry: Dict) -> None:
        """Detect cycles in is_a, part_of, and derived_from edges."""
        containers = registry.get("containers", [])

        # Build adjacency list for hierarchical edges
        graph: Dict[str, List[str]] = defaultdict(list)

        for container in containers:
            path = container.get("path")
            if not path:
                continue

            # Add parent relationships
            for parent in container.get("parent_containers", []):
                parent_path = parent.get("path") if isinstance(parent, dict) else None
                edge_type = parent.get("edge_type") if isinstance(parent, dict) else None

                # Only check hierarchical edges (is_a, part_of, derived_from)
                if parent_path and edge_type in ["is_a", "part_of", "derived_from"]:
                    graph[path].append(parent_path)

            # Add dependencies (derived_from edges)
            for dep in container.get("dependencies", []):
                graph[path].append(dep)

        # DFS cycle detection
        visited: Set[str] = set()
        rec_stack: Set[str] = set()

        def has_cycle_dfs(node: str, path_trace: List[str]) -> bool:
            visited.add(node)
            rec_stack.add(node)
            path_trace.append(node)

            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if has_cycle_dfs(neighbor, path_trace):
                        return True
                elif neighbor in rec_stack:
                    # Found cycle
                    cycle_start = path_trace.index(neighbor)
                    cycle = path_trace[cycle_start:] + [neighbor]
                    self.errors.append(LintError(
                        severity="error",
                        category="cycles",
                        message=f"Cycle detected: {' -> '.join(cycle)}",
                        container_id=node
                    ))
                    return True

            path_trace.pop()
            rec_stack.remove(node)
            return False

        for node in graph:
            if node not in visited:
                has_cycle_dfs(node, [])

    def _validate_namespaces(self, registry: Dict) -> None:
        """Validate namespace compliance and naming patterns."""
        if not self.namespaces:
            return

        containers = registry.get("containers", [])
        namespace_defs = self.namespaces.get("namespaces", {})

        for i, container in enumerate(containers):
            container_id = container.get("id")
            namespace = container.get("namespace")
            path = container.get("path")

            if not namespace or not path:
                continue

            # Check namespace exists
            if namespace not in namespace_defs:
                self.errors.append(LintError(
                    severity="error",
                    category="namespace",
                    message=f"Unknown namespace: {namespace}",
                    container_id=container_id,
                    location=f"containers[{i}].namespace"
                ))
                continue

            ns_def = namespace_defs[namespace]

            # Check naming pattern
            naming_pattern = ns_def.get("naming_pattern")
            if naming_pattern:
                pattern = re.compile(naming_pattern)
                if not pattern.match(path):
                    self.errors.append(LintError(
                        severity="error",
                        category="namespace",
                        message=f"Path does not match namespace pattern: {path}",
                        container_id=container_id,
                        location=f"containers[{i}].path"
                    ))

            # Check max depth
            max_depth = ns_def.get("max_depth")
            if max_depth:
                depth = len(path.split("."))
                if depth > max_depth:
                    self.errors.append(LintError(
                        severity="error",
                        category="namespace",
                        message=f"Path exceeds max depth ({depth} > {max_depth}): {path}",
                        container_id=container_id,
                        location=f"containers[{i}].path"
                    ))

    def _validate_status_transitions(self, registry: Dict) -> None:
        """Validate status lifecycle transitions (requires changelog)."""
        containers = registry.get("containers", [])

        if not self.namespaces:
            return

        valid_transitions = self.namespaces.get("status_transitions", {})

        for i, container in enumerate(containers):
            container_id = container.get("id")
            status = container.get("status")
            changelog = container.get("changelog", [])

            if not changelog or len(changelog) < 2:
                continue  # No transitions to validate

            # Check each transition in changelog
            for j in range(len(changelog) - 1):
                prev_entry = changelog[j]
                next_entry = changelog[j + 1]

                prev_status = prev_entry.get("status")
                next_status = next_entry.get("status")

                if not prev_status or not next_status:
                    continue

                # Check if transition is valid
                allowed_next = valid_transitions.get(prev_status, {}).get("next", [])
                if next_status not in allowed_next:
                    self.errors.append(LintError(
                        severity="error",
                        category="status",
                        message=f"Invalid status transition: {prev_status} -> {next_status}",
                        container_id=container_id,
                        location=f"containers[{i}].changelog[{j}]"
                    ))

    def _validate_privacy_rules(self, registry: Dict) -> None:
        """Validate privacy and sensitivity settings."""
        if not self.namespaces:
            return

        containers = registry.get("containers", [])
        sensitive_namespaces = set(
            self.namespaces.get("privacy_rules", {}).get("sensitive_namespaces", [])
        )

        for i, container in enumerate(containers):
            container_id = container.get("id")
            namespace = container.get("namespace")
            sensitive = container.get("sensitive")

            # Containers in sensitive namespaces should be marked sensitive
            if namespace in sensitive_namespaces and not sensitive:
                self.errors.append(LintError(
                    severity="warning",
                    category="privacy",
                    message=f"Container in sensitive namespace not marked sensitive",
                    container_id=container_id,
                    location=f"containers[{i}].sensitive"
                ))

    def _validate_metadata_consistency(self, registry: Dict) -> None:
        """Validate metadata consistency with container counts."""
        metadata = registry.get("metadata", {})
        containers = registry.get("containers", [])

        # Check total count
        declared_total = metadata.get("total_containers")
        actual_total = len(containers)

        if declared_total != actual_total:
            self.errors.append(LintError(
                severity="error",
                category="schema",
                message=f"Metadata total_containers ({declared_total}) doesn't match actual count ({actual_total})",
                location="metadata.total_containers"
            ))

        # Check namespace counts
        namespace_counts = metadata.get("namespace_counts", {})
        actual_counts = defaultdict(int)

        for container in containers:
            namespace = container.get("namespace")
            if namespace:
                actual_counts[namespace] += 1

        for namespace, declared_count in namespace_counts.items():
            actual_count = actual_counts.get(namespace, 0)
            if declared_count != actual_count:
                self.errors.append(LintError(
                    severity="error",
                    category="schema",
                    message=f"Namespace count mismatch for {namespace}: declared {declared_count}, actual {actual_count}",
                    location=f"metadata.namespace_counts.{namespace}"
                ))

    def print_report(self, errors: List[LintError] | None = None) -> None:
        """Print a formatted lint report."""
        errors = errors or self.errors

        if not errors:
            print("✅ Registry validation passed with no errors or warnings")
            return

        # Group by severity
        by_severity = defaultdict(list)
        for error in errors:
            by_severity[error.severity].append(error)

        # Print summary
        print("\n" + "=" * 80)
        print("DNA REGISTRY LINT REPORT")
        print("=" * 80)

        for severity in ["error", "warning", "info"]:
            count = len(by_severity[severity])
            if count > 0:
                symbol = "❌" if severity == "error" else "⚠️" if severity == "warning" else "ℹ️"
                print(f"{symbol} {count} {severity}(s)")

        print("=" * 80)

        # Print errors by category
        by_category = defaultdict(list)
        for error in errors:
            by_category[error.category].append(error)

        for category, category_errors in sorted(by_category.items()):
            print(f"\n{category.upper()}:")
            for error in category_errors:
                print(f"  {error}")

        print("\n" + "=" * 80)

        # Final verdict
        has_errors = any(e.severity == "error" for e in errors)
        if has_errors:
            print("❌ VALIDATION FAILED - Fix errors before proceeding")
        else:
            print("✅ VALIDATION PASSED - Only warnings/info messages")

        print("=" * 80 + "\n")


def main():
    """CLI entry point for registry linter."""
    import argparse

    parser = argparse.ArgumentParser(description="Lint DNA container registry")
    parser.add_argument(
        "registry",
        type=Path,
        help="Path to dna_registry.json file"
    )
    parser.add_argument(
        "--ontology-dir",
        type=Path,
        help="Path to ontology directory (default: auto-detect from registry path)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output errors as JSON"
    )

    args = parser.parse_args()

    # Auto-detect ontology dir if not provided
    ontology_dir = args.ontology_dir or args.registry.parent

    linter = RegistryLinter(ontology_dir=ontology_dir)
    is_valid, errors = linter.lint_registry(args.registry)

    if args.json:
        output = {
            "valid": is_valid,
            "error_count": sum(1 for e in errors if e.severity == "error"),
            "warning_count": sum(1 for e in errors if e.severity == "warning"),
            "errors": [e.to_dict() for e in errors]
        }
        print(json.dumps(output, indent=2))
    else:
        linter.print_report(errors)

    return 0 if is_valid else 1


if __name__ == "__main__":
    exit(main())
