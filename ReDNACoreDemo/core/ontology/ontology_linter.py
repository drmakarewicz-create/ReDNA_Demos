#!/usr/bin/env python3
"""
Ontology Linter - Validates DNA Registry Structure
Checks:
- Hierarchy depth ≤3 levels (Umbrella → Sub-DNA → Sub-Sub-DNA)
- Naming conventions (PascalCase + DNA suffix)
- Path structure and uniqueness
- Namespace validity
- Parent/child relationship integrity
- Sensitive/camouflage/consent flag consistency
- RR and curiosity baseline requirements
"""

import json
import re
from collections import defaultdict
from typing import Dict, List, Set, Tuple, Any
import sys


class OntologyLinter:
    """Validates DNA registry against ontology rules."""

    def __init__(self, registry_path: str, namespaces_path: str, schema_path: str):
        self.registry_path = registry_path
        self.namespaces_path = namespaces_path
        self.schema_path = schema_path
        self.errors = []
        self.warnings = []
        self.stats = defaultdict(int)

    def load_files(self) -> Tuple[Dict, Dict]:
        """Load registry and namespaces."""
        with open(self.registry_path, 'r') as f:
            registry = json.load(f)

        with open(self.namespaces_path, 'r') as f:
            import yaml
            namespaces = yaml.safe_load(f)

        return registry, namespaces

    def error(self, msg: str):
        """Record an error."""
        self.errors.append(f"❌ ERROR: {msg}")

    def warn(self, msg: str):
        """Record a warning."""
        self.warnings.append(f"⚠️  WARNING: {msg}")

    def check_naming_convention(self, path: str, container_id: str) -> bool:
        """Check that container names follow PascalCase + DNA suffix."""
        parts = path.split('.')

        # Each part must be PascalCase ending in DNA
        name_pattern = re.compile(r'^[A-Z][a-zA-Z0-9]+DNA$')

        for part in parts:
            if not name_pattern.match(part):
                self.error(f"Invalid naming: '{part}' in path '{path}' does not match PascalCase+DNA pattern")
                return False

        # Check versioned ID format
        if not container_id.endswith('.v1'):
            self.error(f"Container ID '{container_id}' must end with '.v1'")
            return False

        return True

    def check_depth(self, path: str) -> bool:
        """Check that hierarchy depth ≤ 3."""
        depth = len(path.split('.'))

        if depth > 3:
            self.error(f"Path '{path}' has depth {depth} (max allowed: 3)")
            return False

        if depth < 1:
            self.error(f"Path '{path}' has depth {depth} (min allowed: 1)")
            return False

        self.stats[f'depth_{depth}'] += 1
        return True

    def check_namespace(self, container: Dict, valid_namespaces: Set[str]) -> bool:
        """Check that namespace is valid and matches path."""
        namespace = container.get('namespace')
        path = container.get('path', '')

        if namespace not in valid_namespaces:
            self.error(f"Invalid namespace '{namespace}' for container '{path}'")
            return False

        # Namespace must match first component of path
        if not path.startswith(namespace):
            self.error(f"Namespace '{namespace}' does not match path '{path}'")
            return False

        return True

    def check_uniqueness(self, containers: List[Dict]) -> bool:
        """Check that all container IDs and paths are unique."""
        ids_seen = set()
        paths_seen = set()
        all_unique = True

        for container in containers:
            container_id = container.get('id')
            path = container.get('path')

            if container_id in ids_seen:
                self.error(f"Duplicate container ID: '{container_id}'")
                all_unique = False
            ids_seen.add(container_id)

            if path in paths_seen:
                self.error(f"Duplicate path: '{path}'")
                all_unique = False
            paths_seen.add(path)

        return all_unique

    def check_parent_relationships(self, containers: List[Dict]) -> bool:
        """Check that parent relationships are valid."""
        path_set = {c['path'] for c in containers}
        all_valid = True

        for container in containers:
            path = container.get('path', '')
            parents = container.get('parent_containers', [])

            for parent in parents:
                parent_path = parent.get('path')
                edge_type = parent.get('edge_type')

                # Check parent exists
                if parent_path not in path_set:
                    self.error(f"Container '{path}' references non-existent parent '{parent_path}'")
                    all_valid = False

                # Check edge type is valid
                valid_edges = ['is_a', 'part_of', 'derived_from']
                if edge_type not in valid_edges:
                    self.error(f"Container '{path}' has invalid edge_type '{edge_type}'")
                    all_valid = False

                # Check parent is actually a parent (shorter path)
                if not path.startswith(parent_path + '.'):
                    self.warn(f"Container '{path}' parent '{parent_path}' is not a hierarchical parent")

        return all_valid

    def check_sensitive_flags(self, container: Dict, namespace_config: Dict) -> bool:
        """Check that sensitive/camouflage/consent flags match namespace policy."""
        namespace = container.get('namespace')
        path = container.get('path')

        # Get namespace-level flags
        ns_sensitive = namespace_config.get(namespace, {}).get('sensitive', False)
        ns_camouflage = namespace_config.get(namespace, {}).get('camouflage', False)
        ns_consent = namespace_config.get(namespace, {}).get('consent_required', False)

        # Get container flags
        c_sensitive = container.get('sensitive', False)
        c_camouflage = container.get('camouflage', False)
        c_consent = container.get('consent_required', False)

        # Container should inherit namespace sensitivity
        if ns_sensitive and not c_sensitive:
            self.warn(f"Container '{path}' in sensitive namespace '{namespace}' is not marked sensitive")

        if ns_camouflage and not c_camouflage:
            self.warn(f"Container '{path}' in camouflage namespace '{namespace}' is not marked for camouflage")

        if ns_consent and not c_consent:
            self.warn(f"Container '{path}' in consent-required namespace '{namespace}' is not marked consent_required")

        return True

    def check_rr_curiosity_baselines(self, container: Dict) -> bool:
        """Check RR and curiosity baseline requirements."""
        path = container.get('path')
        rr_baseline = container.get('rr_baseline')
        curiosity_baseline = container.get('curiosity_baseline')

        # RR baseline should be null for DNA containers (no traits yet)
        if rr_baseline is not None:
            self.warn(f"Container '{path}' has rr_baseline={rr_baseline} (expected null for DNA-only containers)")

        # Curiosity baseline should be 100
        if curiosity_baseline != 100:
            self.warn(f"Container '{path}' has curiosity_baseline={curiosity_baseline} (expected 100)")

        return True

    def check_required_fields(self, container: Dict) -> bool:
        """Check that all required fields are present."""
        required = [
            'id', 'namespace', 'path', 'version', 'status', 'description',
            'sensitive', 'ai_upgradable', 'created_at', 'updated_at'
        ]

        path = container.get('path', '<unknown>')
        all_present = True

        for field in required:
            if field not in container:
                self.error(f"Container '{path}' missing required field '{field}'")
                all_present = False

        return all_present

    def generate_stats(self, containers: List[Dict]) -> Dict[str, Any]:
        """Generate statistics about the ontology."""
        stats = {
            'total_containers': len(containers),
            'by_namespace': defaultdict(int),
            'by_depth': defaultdict(int),
            'sensitive_count': 0,
            'camouflage_count': 0,
            'consent_required_count': 0,
            'umbrella_count': 0,
            'sub_dna_count': 0,
            'sub_sub_dna_count': 0
        }

        for container in containers:
            ns = container.get('namespace')
            path = container.get('path', '')
            depth = len(path.split('.'))

            stats['by_namespace'][ns] += 1
            stats['by_depth'][depth] += 1

            if container.get('sensitive'):
                stats['sensitive_count'] += 1

            if container.get('camouflage'):
                stats['camouflage_count'] += 1

            if container.get('consent_required'):
                stats['consent_required_count'] += 1

            if depth == 1:
                stats['umbrella_count'] += 1
            elif depth == 2:
                stats['sub_dna_count'] += 1
            elif depth == 3:
                stats['sub_sub_dna_count'] += 1

        return stats

    def run(self) -> bool:
        """Run all linting checks."""
        print("🔍 Ontology Linter v1.0")
        print("=" * 70)

        # Load data
        print("\n📂 Loading files...")
        registry, namespaces = self.load_files()

        containers = registry.get('containers', [])
        namespace_config = namespaces.get('namespaces', {})
        valid_namespaces = set(namespace_config.keys())

        print(f"  ✓ Loaded {len(containers)} containers")
        print(f"  ✓ Loaded {len(valid_namespaces)} namespace definitions")

        # Run checks
        print("\n🔎 Running validation checks...")

        print("  • Checking naming conventions...")
        for container in containers:
            self.check_naming_convention(container.get('path'), container.get('id'))

        print("  • Checking hierarchy depth...")
        for container in containers:
            self.check_depth(container.get('path'))

        print("  • Checking namespaces...")
        for container in containers:
            self.check_namespace(container, valid_namespaces)

        print("  • Checking uniqueness...")
        self.check_uniqueness(containers)

        print("  • Checking parent relationships...")
        self.check_parent_relationships(containers)

        print("  • Checking required fields...")
        for container in containers:
            self.check_required_fields(container)

        print("  • Checking sensitive flags...")
        for container in containers:
            self.check_sensitive_flags(container, namespace_config)

        print("  • Checking RR/curiosity baselines...")
        for container in containers:
            self.check_rr_curiosity_baselines(container)

        # Generate statistics
        print("\n📊 Generating statistics...")
        stats = self.generate_stats(containers)

        # Print results
        print("\n" + "=" * 70)
        print("📈 STATISTICS")
        print("=" * 70)
        print(f"Total containers:        {stats['total_containers']}")
        print(f"  Umbrellas (depth=1):   {stats['umbrella_count']}")
        print(f"  Sub-DNAs (depth=2):    {stats['sub_dna_count']}")
        print(f"  Sub-Sub-DNAs (depth=3): {stats['sub_sub_dna_count']}")
        print(f"\nSensitive containers:    {stats['sensitive_count']}")
        print(f"Camouflage-aware:        {stats['camouflage_count']}")
        print(f"Consent-required:        {stats['consent_required_count']}")

        print(f"\nNamespace breakdown:")
        for ns in sorted(stats['by_namespace'].keys()):
            count = stats['by_namespace'][ns]
            print(f"  {ns:12s}  {count:3d} containers")

        print(f"\nDepth histogram:")
        for depth in sorted(stats['by_depth'].keys()):
            count = stats['by_depth'][depth]
            bar = '█' * (count // 5)
            print(f"  Depth {depth}: {count:3d}  {bar}")

        # Print errors and warnings
        print("\n" + "=" * 70)
        if self.errors:
            print(f"❌ ERRORS ({len(self.errors)})")
            print("=" * 70)
            for error in self.errors:
                print(error)
        else:
            print("✅ NO ERRORS")

        print("\n" + "=" * 70)
        if self.warnings:
            print(f"⚠️  WARNINGS ({len(self.warnings)})")
            print("=" * 70)
            for warning in self.warnings[:20]:  # Limit to first 20
                print(warning)
            if len(self.warnings) > 20:
                print(f"  ... and {len(self.warnings) - 20} more warnings")
        else:
            print("✅ NO WARNINGS")

        # Final verdict
        print("\n" + "=" * 70)
        if self.errors:
            print("❌ VALIDATION FAILED")
            return False
        else:
            print("✅ VALIDATION PASSED")
            return True


def main():
    """Main entry point."""
    import sys

    linter = OntologyLinter(
        registry_path="dna_registry.json",
        namespaces_path="namespaces.yaml",
        schema_path="dna_registry.schema.json"
    )

    success = linter.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
