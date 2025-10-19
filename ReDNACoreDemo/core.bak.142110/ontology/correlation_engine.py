"""
ReDNA Ontology Correlation Engine v5.0
Generates weighted edges between containers based on semantic similarity and co-occurrence.

Phase 8B: Correlation Network
"""

import json
import logging
import time
from collections import defaultdict, Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any
import re

logger = logging.getLogger(__name__)

# Paths
ONTOLOGY_DIR = Path(__file__).parent
REGISTRY_V5_PATH = Path(__file__).parent.parent.parent / "data" / "ontology" / "registry_v5" / "dna_registry_v5.json"
EDGES_V5_PATH = Path(__file__).parent.parent.parent / "data" / "ontology" / "edges_v5.jsonl"


class CorrelationEngine:
    """
    Correlation engine for generating weighted edges between containers.

    Methods:
    - Semantic similarity based on description, tags, categories
    - Co-occurrence from telemetry (if available)
    - Cross-namespace correlations
    - Evidence-based confidence scoring
    """

    def __init__(self, registry_path: Optional[Path] = None, load_edges: bool = True):
        """Initialize correlation engine.

        Args:
            registry_path: Path to registry file
            load_edges: Whether to load existing edges from file (default True)
        """
        self.registry_path = registry_path or REGISTRY_V5_PATH
        self.edges_path = EDGES_V5_PATH

        # Load registry
        self.registry = self._load_registry()
        self.containers = {c['path']: c for c in self.registry['containers']}
        self.containers_by_namespace = defaultdict(list)

        for c in self.registry['containers']:
            self.containers_by_namespace[c['namespace']].append(c)

        # Track generated edges
        self.edges: List[Dict[str, Any]] = []
        self.edge_set: Set[Tuple[str, str]] = set()  # For deduplication

        # Stats
        self.stats = {
            'total_edges': 0,
            'semantic_edges': 0,
            'hierarchy_edges': 0,
            'cross_namespace_edges': 0,
            'start_time': None,
            'end_time': None,
        }

        # Load existing edges if requested
        if load_edges and self.edges_path.exists():
            self._load_edges()

        logger.info(f"Correlation engine initialized with {len(self.containers)} containers, {len(self.edges)} edges")

    def _load_registry(self) -> Dict:
        """Load v5 registry."""
        with open(self.registry_path) as f:
            return json.load(f)

    def _load_edges(self):
        """Load edges from JSONL file."""
        logger.info(f"Loading edges from {self.edges_path}")
        edge_count = 0

        with open(self.edges_path) as f:
            for line in f:
                if line.strip():
                    edge = json.loads(line)
                    self.edges.append(edge)

                    # Update edge set for deduplication
                    edge_key = tuple(sorted([edge['from'], edge['to']]))
                    self.edge_set.add(edge_key)

                    # Update stats based on edge type/metadata
                    edge_count += 1
                    if edge.get('metadata', {}).get('method') == 'semantic_similarity':
                        self.stats['semantic_edges'] += 1
                    elif edge.get('metadata', {}).get('method') == 'hierarchy':
                        self.stats['hierarchy_edges'] += 1
                    elif edge.get('metadata', {}).get('method') == 'cross_namespace':
                        self.stats['cross_namespace_edges'] += 1

                    # Count cross-namespace edges
                    from_ns = edge['from'].split('.')[0]
                    to_ns = edge['to'].split('.')[0]
                    if from_ns != to_ns:
                        # Only increment if not already counted by method
                        if edge.get('metadata', {}).get('method') != 'cross_namespace':
                            pass  # Already counted in cross_namespace or will be counted elsewhere

        self.stats['total_edges'] = edge_count
        logger.info(f"Loaded {edge_count} edges: {self.stats['semantic_edges']} semantic, {self.stats['hierarchy_edges']} hierarchy, {self.stats['cross_namespace_edges']} cross-namespace")

    def compute_semantic_similarity(self, container_a: Dict, container_b: Dict) -> float:
        """
        Compute semantic similarity between two containers.

        Uses:
        - Description overlap (TF-IDF-like)
        - Tag overlap (Jaccard similarity)
        - Category proximity
        - Namespace affinity

        Returns:
            Similarity score (0.0 - 1.0)
        """
        score = 0.0
        weights = []

        # Description similarity (simple word overlap)
        desc_a = set(self._tokenize(container_a.get('description', '')))
        desc_b = set(self._tokenize(container_b.get('description', '')))

        if desc_a and desc_b:
            desc_overlap = len(desc_a & desc_b) / len(desc_a | desc_b)
            score += desc_overlap * 0.4
            weights.append(0.4)

        # Tag similarity (Jaccard)
        tags_a = set(container_a.get('tags', []))
        tags_b = set(container_b.get('tags', []))

        if tags_a and tags_b:
            tag_overlap = len(tags_a & tags_b) / len(tags_a | tags_b)
            score += tag_overlap * 0.3
            weights.append(0.3)

        # Category proximity
        cat_a = self._extract_category(container_a.get('path', ''))
        cat_b = self._extract_category(container_b.get('path', ''))

        if cat_a and cat_b:
            cat_similarity = 1.0 if cat_a == cat_b else 0.5 if cat_a in cat_b or cat_b in cat_a else 0.0
            score += cat_similarity * 0.2
            weights.append(0.2)

        # Namespace affinity (same namespace = higher base similarity)
        if container_a['namespace'] == container_b['namespace']:
            score += 0.1
            weights.append(0.1)

        # Normalize by total weight
        if weights:
            return score / sum(weights) if sum(weights) > 0 else score
        return 0.0

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text into words."""
        # Simple tokenization (lowercase, alphanumeric only)
        words = re.findall(r'\b\w+\b', text.lower())
        # Remove common stop words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        return [w for w in words if w not in stop_words and len(w) > 2]

    def _extract_category(self, path: str) -> str:
        """Extract category from container path."""
        # E.g., "SkillDNA.Programming.Python" -> "Programming"
        parts = path.split('.')
        return parts[1] if len(parts) > 2 else parts[0]

    def add_edge(
        self,
        from_path: str,
        to_path: str,
        edge_type: str,
        confidence: float,
        evidence: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        Add an edge to the network.

        Args:
            from_path: Source container path
            to_path: Target container path
            edge_type: Type of relationship (correlates_with, derived_from, etc.)
            confidence: Confidence score (0.0 - 1.0)
            evidence: Optional evidence description
            metadata: Optional metadata

        Returns:
            True if added, False if duplicate
        """
        # Check for duplicate (undirected edge)
        edge_key = tuple(sorted([from_path, to_path]))
        if edge_key in self.edge_set:
            return False

        # Add edge
        edge = {
            'from': from_path,
            'to': to_path,
            'type': edge_type,
            'confidence': round(confidence, 3),
            'evidence': evidence or f"Semantic similarity ({edge_type})",
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'metadata': metadata or {}
        }

        self.edges.append(edge)
        self.edge_set.add(edge_key)
        self.stats['total_edges'] += 1

        # Track cross-namespace
        from_ns = from_path.split('.')[0]
        to_ns = to_path.split('.')[0]
        if from_ns != to_ns:
            self.stats['cross_namespace_edges'] += 1

        return True

    def generate_semantic_edges(self, min_similarity: float = 0.3, max_edges_per_container: int = 50) -> int:
        """
        Generate edges based on semantic similarity.

        Args:
            min_similarity: Minimum similarity threshold
            max_edges_per_container: Max edges per container (prevents over-connection)

        Returns:
            Number of edges generated
        """
        logger.info(f"Generating semantic edges (min_similarity={min_similarity})")
        generated = 0

        containers_list = list(self.containers.values())
        total = len(containers_list)

        for i, container_a in enumerate(containers_list):
            if i % 100 == 0:
                logger.info(f"Processing container {i}/{total}")

            # Find top-k similar containers
            similarities = []

            for j, container_b in enumerate(containers_list):
                if i == j:
                    continue

                similarity = self.compute_semantic_similarity(container_a, container_b)

                if similarity >= min_similarity:
                    similarities.append((container_b, similarity))

            # Sort by similarity and take top-k
            similarities.sort(key=lambda x: x[1], reverse=True)
            similarities = similarities[:max_edges_per_container]

            # Add edges
            for container_b, similarity in similarities:
                if self.add_edge(
                    from_path=container_a['path'],
                    to_path=container_b['path'],
                    edge_type='correlates_with',
                    confidence=similarity,
                    evidence=f"Semantic similarity score: {similarity:.3f}",
                    metadata={'method': 'semantic_similarity'}
                ):
                    generated += 1
                    self.stats['semantic_edges'] += 1

        logger.info(f"Generated {generated} semantic edges")
        return generated

    def generate_hierarchy_edges(self) -> int:
        """
        Generate edges based on container hierarchy (parent-child relationships).

        Returns:
            Number of edges generated
        """
        logger.info("Generating hierarchy edges")
        generated = 0

        for container in self.containers.values():
            parent_containers = container.get('parent_containers', [])

            for parent in parent_containers:
                parent_path = parent.get('path')
                if parent_path and parent_path in self.containers:
                    if self.add_edge(
                        from_path=container['path'],
                        to_path=parent_path,
                        edge_type='derived_from',
                        confidence=1.0,
                        evidence="Hierarchical parent-child relationship",
                        metadata={'method': 'hierarchy'}
                    ):
                        generated += 1
                        self.stats['hierarchy_edges'] += 1

        logger.info(f"Generated {generated} hierarchy edges")
        return generated

    def generate_cross_namespace_edges(self, min_confidence: float = 0.4) -> int:
        """
        Generate explicit cross-namespace edges using category matching.

        Args:
            min_confidence: Minimum confidence for cross-namespace edges

        Returns:
            Number of edges generated
        """
        logger.info("Generating cross-namespace edges")
        generated = 0

        # Define cross-namespace affinities
        affinities = {
            ('SkillDNA', 'ProfDNA'): 0.8,  # Skills correlate with professional roles
            ('BehDNA', 'PrefDNA'): 0.7,    # Behaviors correlate with preferences
            ('CogDNA', 'BehDNA'): 0.75,    # Cognitive patterns drive behaviors
            ('EmDNA', 'SocDNA'): 0.7,      # Emotions affect social interactions
            ('ProfDNA', 'SkillDNA'): 0.8,  # Symmetric
            ('PrefDNA', 'BehDNA'): 0.7,
            ('BehDNA', 'CogDNA'): 0.75,
            ('SocDNA', 'EmDNA'): 0.7,
        }

        for (ns_a, ns_b), base_confidence in affinities.items():
            containers_a = self.containers_by_namespace[ns_a]
            containers_b = self.containers_by_namespace[ns_b]

            # Sample to avoid O(n²) explosion
            sample_size = min(50, len(containers_a))
            for container_a in containers_a[:sample_size]:
                for container_b in containers_b[:50]:
                    # Compute similarity
                    similarity = self.compute_semantic_similarity(container_a, container_b)

                    # Boost with namespace affinity
                    final_confidence = min(1.0, similarity * 0.5 + base_confidence * 0.5)

                    if final_confidence >= min_confidence:
                        if self.add_edge(
                            from_path=container_a['path'],
                            to_path=container_b['path'],
                            edge_type='correlates_with',
                            confidence=final_confidence,
                            evidence=f"Cross-namespace affinity ({ns_a} ↔ {ns_b})",
                            metadata={'method': 'cross_namespace', 'ns_a': ns_a, 'ns_b': ns_b}
                        ):
                            generated += 1

        logger.info(f"Generated {generated} cross-namespace edges")
        return generated

    def run_correlation(self, target_edges: int = 50000) -> Dict[str, Any]:
        """
        Run full correlation pipeline to generate target number of edges.

        Args:
            target_edges: Target number of edges to generate

        Returns:
            Stats dictionary
        """
        logger.info(f"Starting correlation generation (target: {target_edges} edges)")
        self.stats['start_time'] = time.time()

        # Generate hierarchy edges first (high confidence)
        self.generate_hierarchy_edges()

        # Generate cross-namespace edges
        self.generate_cross_namespace_edges()

        # Generate semantic edges to reach target
        remaining = target_edges - len(self.edges)
        if remaining > 0:
            # Adjust similarity threshold to control edge count
            # Lower threshold = more edges
            estimated_edges_per_container = remaining // len(self.containers)
            max_edges = min(100, estimated_edges_per_container + 10)

            self.generate_semantic_edges(
                min_similarity=0.25,  # Lower threshold for more edges
                max_edges_per_container=max_edges
            )

        self.stats['end_time'] = time.time()
        self.stats['duration_seconds'] = self.stats['end_time'] - self.stats['start_time']

        logger.info(f"Correlation complete: {len(self.edges)} edges generated in {self.stats['duration_seconds']:.2f}s")

        return self.stats

    def save_edges(self) -> Path:
        """
        Save edges to JSONL file.

        Returns:
            Path to saved edges file
        """
        self.edges_path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.edges_path, 'w') as f:
            for edge in self.edges:
                f.write(json.dumps(edge) + '\n')

        logger.info(f"Saved {len(self.edges)} edges to {self.edges_path}")
        return self.edges_path

    def get_related_containers(self, container_path: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get containers related to the given path.

        Args:
            container_path: Container path
            limit: Maximum number of related containers

        Returns:
            List of (container, edge_type, confidence) tuples
        """
        related = []

        for edge in self.edges:
            if edge['from'] == container_path:
                related.append({
                    'container': self.containers.get(edge['to']),
                    'edge_type': edge['type'],
                    'confidence': edge['confidence'],
                    'direction': 'outgoing'
                })
            elif edge['to'] == container_path:
                related.append({
                    'container': self.containers.get(edge['from']),
                    'edge_type': edge['type'],
                    'confidence': edge['confidence'],
                    'direction': 'incoming'
                })

        # Sort by confidence and limit
        related.sort(key=lambda x: x['confidence'], reverse=True)
        return related[:limit]

    def validate(self) -> Dict[str, Any]:
        """
        Validate generated edges.

        Returns:
            Validation report
        """
        validation = {
            'total_edges': len(self.edges),
            'unique_edges': len(self.edge_set),
            'cross_namespace_edges': self.stats['cross_namespace_edges'],
            'avg_confidence': sum(e['confidence'] for e in self.edges) / max(len(self.edges), 1),
            'confidence_distribution': {
                '0.9-1.0': sum(1 for e in self.edges if e['confidence'] >= 0.9),
                '0.7-0.9': sum(1 for e in self.edges if 0.7 <= e['confidence'] < 0.9),
                '0.5-0.7': sum(1 for e in self.edges if 0.5 <= e['confidence'] < 0.7),
                '0.0-0.5': sum(1 for e in self.edges if e['confidence'] < 0.5),
            },
            'edge_types': dict(Counter(e['type'] for e in self.edges)),
            'errors': [],
            'warnings': []
        }

        # Check for orphaned edges (referencing non-existent containers)
        for edge in self.edges:
            if edge['from'] not in self.containers:
                validation['errors'].append(f"Edge references non-existent container: {edge['from']}")
            if edge['to'] not in self.containers:
                validation['errors'].append(f"Edge references non-existent container: {edge['to']}")

        # Check for self-loops
        for edge in self.edges:
            if edge['from'] == edge['to']:
                validation['errors'].append(f"Self-loop detected: {edge['from']}")

        validation['valid'] = len(validation['errors']) == 0

        return validation


# Convenience functions
def create_correlation_engine() -> CorrelationEngine:
    """Create a correlation engine instance."""
    return CorrelationEngine()


def run_correlation(target_edges: int = 50000) -> Tuple[CorrelationEngine, Dict[str, Any]]:
    """
    Run full correlation pipeline.

    Args:
        target_edges: Number of edges to generate

    Returns:
        (engine, stats)
    """
    engine = create_correlation_engine()
    stats = engine.run_correlation(target_edges=target_edges)
    return engine, stats
