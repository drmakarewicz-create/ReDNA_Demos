"""Trait graph helpers for Coach ReDNA."""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any, Dict, Iterable, List, Mapping, Optional, Set, Tuple


def _iter_traits(coach: Mapping[str, Any]) -> Iterable[Tuple[str, Mapping[str, Any], Mapping[str, Any]]]:
    containers = coach.get("containers")
    if not isinstance(containers, list):
        return []
    bundle: List[Tuple[str, Mapping[str, Any], Mapping[str, Any]]] = []
    for container in containers:
        if not isinstance(container, Mapping):
            continue
        container_id = str(container.get("id") or "").strip()
        traits = container.get("traits")
        if not container_id or not isinstance(traits, list):
            continue
        for trait in traits:
            if not isinstance(trait, Mapping):
                continue
            trait_id = str(trait.get("id") or "").strip()
            if not trait_id:
                continue
            node_id = f"{container_id}.{trait_id}" if container_id else trait_id
            bundle.append((node_id, container, trait))
    return bundle


def to_graph(coach: Mapping[str, Any]) -> Dict[str, Any]:
    """Return a lightweight graph representation for visualisation.

    Structure:
        {
            "nodes": [{"id": ..., "label": ..., "weight": ..., "has_templates": bool, ...}, ...],
            "edges": [{"type": "implies"|"depends_on", "source": ..., "target": ..., "weight": float|None}],
        }
    """

    nodes: List[Dict[str, Any]] = []
    for node_id, container, trait in _iter_traits(coach):
        templates = trait.get("templates") if isinstance(trait.get("templates"), Mapping) else {}
        has_templates = any(
            isinstance(value, str) and value.strip()
            for value in (templates or {}).values()
        )
        curiosity = trait.get("curiosity") if isinstance(trait.get("curiosity"), Mapping) else {}
        node = {
            "id": node_id,
            "container": container.get("id"),
            "container_label": container.get("label"),
            "label": trait.get("label", node_id.split(".")[-1]),
            "weight": float(trait.get("weight", 0.0) or 0.0),
            "core_trait": trait.get("core_trait"),
            "has_templates": has_templates,
            "curiosity": {
                "default": curiosity.get("default"),
                "decay_days": curiosity.get("decay_days"),
            },
        }
        nodes.append(node)

    edges: List[Dict[str, Any]] = []
    links = coach.get("links") if isinstance(coach.get("links"), Mapping) else {}
    implies = links.get("implies") if isinstance(links.get("implies"), list) else []
    for link in implies:
        if not isinstance(link, Mapping):
            continue
        source = str(link.get("from") or "").strip()
        target = str(link.get("to") or "").strip()
        if not source or not target:
            continue
        edges.append(
            {
                "type": "implies",
                "source": source,
                "target": target,
                "weight": link.get("weight"),
            }
        )

    depends = links.get("depends_on") if isinstance(links.get("depends_on"), list) else []
    for link in depends:
        if not isinstance(link, Mapping):
            continue
        source = str(link.get("from") or "").strip()
        target = str(link.get("on") or "").strip()
        if not source or not target:
            continue
        edges.append(
            {
                "type": "depends_on",
                "source": source,
                "target": target,
                "weight": link.get("weight"),
            }
        )

    return {"nodes": nodes, "edges": edges}


def validate_graph(coach: Mapping[str, Any]) -> List[str]:
    """Return a list of string issues identified within the coach graph."""

    issues: List[str] = []
    traits = list(_iter_traits(coach))
    node_ids = [node_id for node_id, _, _ in traits]
    duplicates = _find_duplicates(node_ids)
    if duplicates:
        issues.append(
            "Duplicate trait identifiers detected: " + ", ".join(sorted(duplicates))
        )

    node_set = set(node_ids)
    graph = to_graph(coach)
    for edge in graph["edges"]:
        if edge["source"] not in node_set:
            issues.append(f"Edge source `{edge['source']}` not present in trait registry.")
        if edge["target"] not in node_set:
            issues.append(f"Edge target `{edge['target']}` not present in trait registry.")

    cycle_paths = _detect_cycles(graph["edges"], node_set)
    for path in cycle_paths:
        issues.append("Cycle detected: " + " -> ".join(path))

    return issues


def _find_duplicates(values: Iterable[str]) -> Set[str]:
    seen: Set[str] = set()
    dupes: Set[str] = set()
    for value in values:
        if value in seen:
            dupes.add(value)
        else:
            seen.add(value)
    return dupes


def _detect_cycles(edges: List[Dict[str, Any]], nodes: Set[str]) -> List[List[str]]:
    adjacency: Dict[str, List[str]] = defaultdict(list)
    for edge in edges:
        if edge.get("type") != "implies":
            continue
        source = edge.get("source")
        target = edge.get("target")
        if source in nodes and target in nodes:
            adjacency[source].append(target)

    cycles: List[List[str]] = []
    for node in nodes:
        visited: Set[str] = set()
        stack: List[str] = []
        if _dfs_cycle(node, adjacency, visited, stack, cycles):
            break
    return cycles


def _dfs_cycle(
    start: str,
    adjacency: Mapping[str, List[str]],
    visited: Set[str],
    stack: List[str],
    cycles: List[List[str]],
) -> bool:
    if start in stack:
        cycle_start_index = stack.index(start)
        cycles.append(stack[cycle_start_index:] + [start])
        return True
    if start in visited:
        return False
    visited.add(start)
    stack.append(start)
    for neighbour in adjacency.get(start, []):
        if _dfs_cycle(neighbour, adjacency, visited, stack, cycles):
            return True
    stack.pop()
    return False


def compute_coverage(
    coach: Mapping[str, Any],
    core_resolved: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Return simple coverage metrics for the given coach."""

    traits = list(_iter_traits(coach))
    total_traits = len(traits)
    mapped_to_core = 0
    with_templates = 0
    weights: List[float] = []

    mapped_lookup: Set[str] = set()
    for node_id, _container, trait in traits:
        if trait.get("core_trait"):
            mapped_to_core += 1
            mapped_lookup.add(node_id)
        templates = trait.get("templates") if isinstance(trait.get("templates"), Mapping) else {}
        if any(isinstance(value, str) and value.strip() for value in (templates or {}).values()):
            with_templates += 1
        try:
            weights.append(float(trait.get("weight", 0.0) or 0.0))
        except (TypeError, ValueError):
            weights.append(0.0)

    coverage_stats = {
        "total_traits": total_traits,
        "mapped_to_core": mapped_to_core,
        "unmapped": max(total_traits - mapped_to_core, 0),
        "with_templates": with_templates,
        "missing_templates": max(total_traits - with_templates, 0),
    }

    if weights:
        coverage_stats["weights_stats"] = {
            "min": min(weights),
            "max": max(weights),
            "avg": sum(weights) / len(weights),
        }
    else:
        coverage_stats["weights_stats"] = {"min": 0.0, "max": 0.0, "avg": 0.0}

    if core_resolved:
        coverage_stats["core_trait_hits"] = _resolve_core_hits(mapped_lookup, core_resolved)

    return coverage_stats


def _resolve_core_hits(
    mapped_lookup: Set[str],
    core_resolved: Mapping[str, Any],
) -> Dict[str, int]:
    """Return how many mapped traits currently appear in the resolved Core snapshot."""

    resolved_traits: Set[str] = set()
    if isinstance(core_resolved, Mapping):
        candidates = []
        if isinstance(core_resolved.get("traits"), list):
            candidates.extend(core_resolved.get("traits") or [])
        if isinstance(core_resolved.get("items"), list):
            candidates.extend(core_resolved.get("items") or [])
        for entry in candidates:
            if not isinstance(entry, Mapping):
                continue
            container = str(entry.get("container") or entry.get("container_id") or "").strip()
            trait = str(entry.get("trait") or entry.get("trait_id") or "").strip()
            node_id = f"{container}.{trait}" if container and trait else trait or container
            if node_id:
                resolved_traits.add(node_id)

    hits = len(mapped_lookup & resolved_traits)
    return {"hits": hits, "resolved_total": len(resolved_traits)}


__all__ = ["to_graph", "validate_graph", "compute_coverage"]
