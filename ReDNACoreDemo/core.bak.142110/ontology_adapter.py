"""
Ontology Adapter for Head Coach
Connects Head Coach to the 2,000-container registry and 200-edge cross-link network.
"""

import json
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

REGISTRY_PATH = Path(__file__).parent / "ontology" / "dna_registry.json"
CROSS_LINKS_PATH = Path(__file__).parent / "ontology" / "cross_links.yaml"


class OntologyAdapter:
    """Adapter to access ReDNA Ontology V2.0 from Head Coach."""

    def __init__(self):
        """Initialize the ontology adapter."""
        self.registry = self._load_registry()
        self.cross_links = self._load_cross_links()

        # Build indices for fast lookup
        self._build_indices()

    def _load_registry(self) -> Dict:
        """Load the DNA registry."""
        with open(REGISTRY_PATH) as f:
            return json.load(f)

    def _load_cross_links(self) -> Dict:
        """Load the cross-link network."""
        with open(CROSS_LINKS_PATH) as f:
            return yaml.safe_load(f)

    def _build_indices(self):
        """Build lookup indices for fast access."""
        # Path index
        self.containers_by_path = {c['path']: c for c in self.registry['containers']}

        # Namespace index
        self.containers_by_namespace = defaultdict(list)
        for c in self.registry['containers']:
            self.containers_by_namespace[c['namespace']].append(c)

        # Parent-child index
        self.children_by_parent = defaultdict(list)
        for c in self.registry['containers']:
            if 'parent_containers' in c and c['parent_containers']:
                parent_path = c['parent_containers'][0]['path']
                self.children_by_parent[parent_path].append(c)

        # Edge indices
        self.edges_from = defaultdict(list)
        self.edges_to = defaultdict(list)
        for edge in self.cross_links.get('edges', []):
            self.edges_from[edge['from']].append(edge)
            self.edges_to[edge['to']].append(edge)

        # Sensitive container index
        self.sensitive_containers = [c for c in self.registry['containers'] if c.get('sensitive', False)]

    # ========================================================================
    # Container Queries
    # ========================================================================

    def get_container(self, path: str) -> Optional[Dict]:
        """Get a container by its path."""
        return self.containers_by_path.get(path)

    def get_containers_by_namespace(self, namespace: str) -> List[Dict]:
        """Get all containers in a namespace."""
        return self.containers_by_namespace.get(namespace, [])

    def get_children(self, parent_path: str) -> List[Dict]:
        """Get all children of a container."""
        return self.children_by_parent.get(parent_path, [])

    def search_containers(self, query: str, limit: int = 10) -> List[Dict]:
        """Search containers by description or path."""
        query_lower = query.lower()
        results = []

        for container in self.registry['containers']:
            if query_lower in container['path'].lower() or \
               query_lower in container.get('description', '').lower():
                results.append(container)
                if len(results) >= limit:
                    break

        return results

    def get_sensitive_containers(self) -> List[Dict]:
        """Get all sensitive containers."""
        return self.sensitive_containers

    # ========================================================================
    # Cross-Link Queries
    # ========================================================================

    def get_related_containers(self, path: str, edge_type: Optional[str] = None) -> List[Tuple[Dict, str, float]]:
        """
        Get containers related to the given path via cross-links.
        Returns list of (container, edge_type, confidence) tuples.
        """
        related = []

        # Outgoing edges
        for edge in self.edges_from.get(path, []):
            if edge_type is None or edge['type'] == edge_type:
                related_container = self.get_container(edge['to'])
                if related_container:
                    related.append((related_container, edge['type'], edge['confidence']))

        # Incoming edges
        for edge in self.edges_to.get(path, []):
            if edge_type is None or edge['type'] == edge_type:
                related_container = self.get_container(edge['from'])
                if related_container:
                    related.append((related_container, edge['type'], edge['confidence']))

        # Sort by confidence descending
        related.sort(key=lambda x: x[2], reverse=True)

        return related

    def get_semantic_neighbors(self, path: str, max_depth: int = 2) -> List[Dict]:
        """
        Get semantic neighbors via cross-link traversal.
        Returns containers within max_depth hops.
        """
        visited = set()
        neighbors = []
        queue = [(path, 0)]

        while queue:
            current_path, depth = queue.pop(0)

            if current_path in visited or depth > max_depth:
                continue

            visited.add(current_path)

            if depth > 0:  # Don't include the starting container
                container = self.get_container(current_path)
                if container:
                    neighbors.append(container)

            # Add connected containers to queue
            for edge in self.edges_from.get(current_path, []):
                if edge['to'] not in visited:
                    queue.append((edge['to'], depth + 1))

            for edge in self.edges_to.get(current_path, []):
                if edge['from'] not in visited:
                    queue.append((edge['from'], depth + 1))

        return neighbors

    def find_semantic_path(self, from_path: str, to_path: str, max_depth: int = 5) -> Optional[List[str]]:
        """
        Find shortest semantic path between two containers via cross-links.
        Returns list of container paths or None if no path found.
        """
        if from_path == to_path:
            return [from_path]

        visited = set()
        queue = [(from_path, [from_path])]

        while queue:
            current_path, path = queue.pop(0)

            if len(path) > max_depth:
                continue

            if current_path in visited:
                continue

            visited.add(current_path)

            # Check all connected containers
            for edge in self.edges_from.get(current_path, []):
                if edge['to'] == to_path:
                    return path + [to_path]
                if edge['to'] not in visited:
                    queue.append((edge['to'], path + [edge['to']]))

            for edge in self.edges_to.get(current_path, []):
                if edge['from'] == to_path:
                    return path + [to_path]
                if edge['from'] not in visited:
                    queue.append((edge['from'], path + [edge['from']]))

        return None

    # ========================================================================
    # Head Coach Integration
    # ========================================================================

    def get_awareness_context(self, user_traits: Dict[str, float]) -> Dict:
        """
        Build awareness context from user's trait values.
        Maps user traits to ontology containers and related concepts.
        """
        high_rr_traits = []
        low_rr_traits = []
        related_concepts = []

        for trait_path, value in user_traits.items():
            container = self.get_container(trait_path)
            if not container:
                continue

            # Categorize by value
            if value >= 70:
                high_rr_traits.append({
                    'path': trait_path,
                    'value': value,
                    'description': container.get('description', ''),
                    'namespace': container['namespace']
                })
            elif value <= 30:
                low_rr_traits.append({
                    'path': trait_path,
                    'value': value,
                    'description': container.get('description', ''),
                    'namespace': container['namespace']
                })

            # Get related concepts via cross-links
            related = self.get_related_containers(trait_path, edge_type='correlates_with')
            for related_container, edge_type, confidence in related[:3]:  # Top 3
                if confidence >= 0.70:
                    related_concepts.append({
                        'from': trait_path,
                        'to': related_container['path'],
                        'confidence': confidence,
                        'description': related_container.get('description', '')
                    })

        return {
            'high_rr_traits': high_rr_traits,
            'low_rr_traits': low_rr_traits,
            'related_concepts': related_concepts[:10],  # Top 10
            'total_containers': len(self.registry['containers']),
            'total_edges': len(self.cross_links.get('edges', []))
        }

    def suggest_exploration_paths(self, current_focus: str, limit: int = 5) -> List[Dict]:
        """
        Suggest exploration paths from current focus area.
        Returns related containers with high-confidence edges.
        """
        suggestions = []
        related = self.get_related_containers(current_focus)

        for container, edge_type, confidence in related[:limit]:
            suggestions.append({
                'path': container['path'],
                'namespace': container['namespace'],
                'description': container.get('description', ''),
                'edge_type': edge_type,
                'confidence': confidence,
                'reasoning': f"Related via {edge_type} (confidence: {confidence:.2f})"
            })

        return suggestions

    def get_jpi_ontology_coverage(self, user_data: Dict) -> Dict:
        """
        Calculate JPI ontology coverage metrics.
        Measures how well user data covers the ontology.
        """
        # Count containers with user data
        populated_containers = 0
        total_containers = len(self.registry['containers'])

        # Namespace coverage
        namespace_coverage = {}
        for ns in self.containers_by_namespace.keys():
            ns_containers = self.containers_by_namespace[ns]
            # Check how many have values in user data
            populated = sum(1 for c in ns_containers if c['path'] in user_data)
            namespace_coverage[ns] = {
                'populated': populated,
                'total': len(ns_containers),
                'coverage': populated / len(ns_containers) if ns_containers else 0
            }
            populated_containers += populated

        return {
            'overall_coverage': populated_containers / total_containers if total_containers else 0,
            'populated_containers': populated_containers,
            'total_containers': total_containers,
            'namespace_coverage': namespace_coverage
        }

    # ========================================================================
    # Statistics
    # ========================================================================

    def get_stats(self) -> Dict:
        """Get ontology statistics."""
        return {
            'total_containers': len(self.registry['containers']),
            'total_edges': len(self.cross_links.get('edges', [])),
            'namespaces': len(self.containers_by_namespace),
            'sensitive_containers': len(self.sensitive_containers),
            'network_density': len(self.cross_links.get('edges', [])) / len(self.registry['containers']) if self.registry['containers'] else 0
        }


# Singleton instance
_ontology_adapter = None


def get_ontology_adapter() -> OntologyAdapter:
    """Get the singleton ontology adapter instance."""
    global _ontology_adapter
    if _ontology_adapter is None:
        _ontology_adapter = OntologyAdapter()
    return _ontology_adapter
