"""
DNA Graph Linker

Extracts edges from DNA registry and writes them to JSONL format for graph storage.
Supports querying and traversing the ontology graph.

Edge Format (JSONL):
{"source": "PaDNA.HairDNA.ColorDNA", "target": "PaDNA.HairDNA", "type": "is_a", "metadata": {}}
{"source": "PaDNA.HairDNA.ColorDNA", "target": "PaDNA.SkinDNA.ToneDNA", "type": "correlates_with", "metadata": {"strength": 0.68}}
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple


@dataclass
class Edge:
    """Represents an edge in the DNA ontology graph."""
    source: str
    target: str
    edge_type: str
    metadata: Dict[str, Any]

    def to_jsonl(self) -> str:
        """Serialize to JSONL format."""
        return json.dumps({
            "source": self.source,
            "target": self.target,
            "type": self.edge_type,
            "metadata": self.metadata
        })

    @classmethod
    def from_jsonl(cls, line: str) -> Edge:
        """Deserialize from JSONL format."""
        data = json.loads(line)
        return cls(
            source=data["source"],
            target=data["target"],
            edge_type=data["type"],
            metadata=data.get("metadata", {})
        )


class DNAGraphLinker:
    """Extracts and manages edges in the DNA ontology graph."""

    def __init__(self, registry_path: Path, graph_path: Path | None = None):
        self.registry_path = Path(registry_path)
        self.graph_path = Path(graph_path) if graph_path else (self.registry_path.parent / "dna_graph.jsonl")

        self.registry: Dict[str, Any] = {}
        self.edges: List[Edge] = []

        # Adjacency lists for fast querying
        self.outgoing: Dict[str, List[Edge]] = defaultdict(list)  # source -> edges
        self.incoming: Dict[str, List[Edge]] = defaultdict(list)  # target -> edges

        self._load_registry()

    def _load_registry(self) -> None:
        """Load registry JSON."""
        if not self.registry_path.exists():
            raise FileNotFoundError(f"Registry not found: {self.registry_path}")

        with open(self.registry_path) as f:
            self.registry = json.load(f)

    def extract_edges(self) -> List[Edge]:
        """
        Extract all edges from registry containers.

        Returns:
            List of Edge objects
        """
        self.edges = []
        containers = self.registry.get("containers", [])

        for container in containers:
            path = container.get("path")
            if not path:
                continue

            # Extract parent relationships (is_a, part_of, derived_from)
            for parent in container.get("parent_containers", []):
                parent_path = parent.get("path")
                edge_type = parent.get("edge_type", "is_a")

                if parent_path:
                    edge = Edge(
                        source=path,
                        target=parent_path,
                        edge_type=edge_type,
                        metadata={}
                    )
                    self.edges.append(edge)

            # Extract dependencies (derived_from edges)
            for dep in container.get("dependencies", []):
                edge = Edge(
                    source=path,
                    target=dep,
                    edge_type="derived_from",
                    metadata={}
                )
                self.edges.append(edge)

            # Extract correlations
            for corr in container.get("correlates_with", []):
                if isinstance(corr, dict):
                    corr_path = corr.get("path")
                    strength = corr.get("strength", 1.0)
                    evidence = corr.get("evidence", "")

                    if corr_path:
                        edge = Edge(
                            source=path,
                            target=corr_path,
                            edge_type="correlates_with",
                            metadata={
                                "strength": strength,
                                "evidence": evidence
                            }
                        )
                        self.edges.append(edge)

            # Extract contradictions
            for contra in container.get("contradicts", []):
                edge = Edge(
                    source=path,
                    target=contra,
                    edge_type="contradicts",
                    metadata={}
                )
                self.edges.append(edge)

        # Build adjacency lists
        self._build_adjacency_lists()

        return self.edges

    def _build_adjacency_lists(self) -> None:
        """Build adjacency lists for fast querying."""
        self.outgoing = defaultdict(list)
        self.incoming = defaultdict(list)

        for edge in self.edges:
            self.outgoing[edge.source].append(edge)
            self.incoming[edge.target].append(edge)

    def save_graph(self, output_path: Path | None = None) -> None:
        """Save edges to JSONL file."""
        output_path = Path(output_path) if output_path else self.graph_path

        with open(output_path, 'w') as f:
            for edge in self.edges:
                f.write(edge.to_jsonl() + '\n')

        print(f"✅ Saved {len(self.edges)} edges to {output_path}")

    def load_graph(self, input_path: Path | None = None) -> None:
        """Load edges from JSONL file."""
        input_path = Path(input_path) if input_path else self.graph_path

        if not input_path.exists():
            print(f"Warning: Graph file not found: {input_path}")
            return

        self.edges = []

        with open(input_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    edge = Edge.from_jsonl(line)
                    self.edges.append(edge)

        self._build_adjacency_lists()
        print(f"✅ Loaded {len(self.edges)} edges from {input_path}")

    def get_children(self, path: str, edge_type: str | None = None) -> List[str]:
        """
        Get child containers (containers that point TO this one).

        Args:
            path: Container path
            edge_type: Optional filter by edge type

        Returns:
            List of child container paths
        """
        children = []

        for edge in self.incoming.get(path, []):
            if edge_type is None or edge.edge_type == edge_type:
                children.append(edge.source)

        return children

    def get_parents(self, path: str, edge_type: str | None = None) -> List[str]:
        """
        Get parent containers (containers this one points TO).

        Args:
            path: Container path
            edge_type: Optional filter by edge type

        Returns:
            List of parent container paths
        """
        parents = []

        for edge in self.outgoing.get(path, []):
            if edge_type is None or edge.edge_type == edge_type:
                parents.append(edge.target)

        return parents

    def get_correlations(self, path: str, min_strength: float = 0.0) -> List[Tuple[str, float]]:
        """
        Get correlated containers with their correlation strengths.

        Args:
            path: Container path
            min_strength: Minimum correlation strength threshold

        Returns:
            List of (correlated_path, strength) tuples
        """
        correlations = []

        for edge in self.outgoing.get(path, []):
            if edge.edge_type == "correlates_with":
                strength = edge.metadata.get("strength", 1.0)
                if strength >= min_strength:
                    correlations.append((edge.target, strength))

        return sorted(correlations, key=lambda x: x[1], reverse=True)

    def get_ancestors(self, path: str, edge_types: List[str] | None = None) -> List[str]:
        """
        Get all ancestors (recursive parent traversal).

        Args:
            path: Container path
            edge_types: Optional filter by edge types (default: ["is_a", "part_of"])

        Returns:
            List of ancestor paths (breadth-first order)
        """
        if edge_types is None:
            edge_types = ["is_a", "part_of"]

        ancestors = []
        visited = set()
        queue = [path]

        while queue:
            current = queue.pop(0)

            if current in visited:
                continue

            visited.add(current)

            for edge in self.outgoing.get(current, []):
                if edge.edge_type in edge_types:
                    if edge.target not in visited:
                        ancestors.append(edge.target)
                        queue.append(edge.target)

        return ancestors

    def get_descendants(self, path: str, edge_types: List[str] | None = None) -> List[str]:
        """
        Get all descendants (recursive child traversal).

        Args:
            path: Container path
            edge_types: Optional filter by edge types (default: ["is_a", "part_of"])

        Returns:
            List of descendant paths (breadth-first order)
        """
        if edge_types is None:
            edge_types = ["is_a", "part_of"]

        descendants = []
        visited = set()
        queue = [path]

        while queue:
            current = queue.pop(0)

            if current in visited:
                continue

            visited.add(current)

            for edge in self.incoming.get(current, []):
                if edge.edge_type in edge_types:
                    if edge.source not in visited:
                        descendants.append(edge.source)
                        queue.append(edge.source)

        return descendants

    def get_graph_stats(self) -> Dict[str, Any]:
        """Get statistics about the graph."""
        edge_counts_by_type = defaultdict(int)

        for edge in self.edges:
            edge_counts_by_type[edge.edge_type] += 1

        return {
            "total_edges": len(self.edges),
            "unique_sources": len(self.outgoing),
            "unique_targets": len(self.incoming),
            "edge_counts_by_type": dict(edge_counts_by_type),
            "avg_out_degree": len(self.edges) / len(self.outgoing) if self.outgoing else 0,
            "avg_in_degree": len(self.edges) / len(self.incoming) if self.incoming else 0
        }


def main():
    """CLI entry point for DNA graph linker."""
    import argparse

    parser = argparse.ArgumentParser(description="Extract and manage DNA ontology graph")
    parser.add_argument(
        "--registry",
        type=Path,
        required=True,
        help="Path to dna_registry.json"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output path for dna_graph.jsonl (default: same dir as registry)"
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Print graph statistics"
    )

    args = parser.parse_args()

    linker = DNAGraphLinker(registry_path=args.registry, graph_path=args.output)

    print(f"Extracting edges from {args.registry}...")
    edges = linker.extract_edges()

    print(f"✅ Extracted {len(edges)} edges")

    linker.save_graph()

    if args.stats:
        stats = linker.get_graph_stats()
        print("\n" + "=" * 60)
        print("GRAPH STATISTICS")
        print("=" * 60)
        print(f"Total edges: {stats['total_edges']}")
        print(f"Unique source nodes: {stats['unique_sources']}")
        print(f"Unique target nodes: {stats['unique_targets']}")
        print(f"Average out-degree: {stats['avg_out_degree']:.2f}")
        print(f"Average in-degree: {stats['avg_in_degree']:.2f}")
        print("\nEdges by type:")
        for edge_type, count in sorted(stats['edge_counts_by_type'].items()):
            print(f"  {edge_type}: {count}")
        print("=" * 60)


if __name__ == "__main__":
    main()
