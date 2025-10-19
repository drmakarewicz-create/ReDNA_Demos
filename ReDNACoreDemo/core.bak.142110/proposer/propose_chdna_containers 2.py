#!/usr/bin/env python3
"""
ChatDNA Container Proposer

Aggregates gap logs and proposes new containers based on frequency × impact.
Runs nightly to identify high-value ontology extensions.

Usage:
    python propose_chdna_containers.py
    python propose_chdna_containers.py --dry-run
    python propose_chdna_containers.py --date 2025-10-07
"""

import json
import yaml
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List
import statistics


def load_config() -> Dict:
    """Load proposer configuration."""
    config_path = Path(__file__).parent / "proposer_config.yaml"
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def load_schema() -> Dict:
    """Load candidate container JSON schema."""
    schema_path = Path(__file__).parent.parent.parent / "schemas" / "candidate_container.schema.json"
    with open(schema_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def read_gap_logs(log_path: Path) -> List[Dict]:
    """Read JSONL gap log file.

    Args:
        log_path: Path to chatdna_unmet_features.jsonl

    Returns:
        List of log entries
    """
    if not log_path.exists():
        return []

    entries = []
    with open(log_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return entries


def aggregate_gaps(entries: List[Dict]) -> Dict[str, Dict]:
    """Aggregate gap log entries by feature.

    Args:
        entries: List of gap log entries

    Returns:
        Dict of {feature_name: {count, impacts, contexts, users, types}}
    """
    aggregated = defaultdict(lambda: {
        "count": 0,
        "impacts": [],
        "contexts": [],
        "users": set(),
        "types": set(),
        "values": []
    })

    for entry in entries:
        user_id = entry.get("user_id", "unknown")
        intent = entry.get("intent", "unknown")

        for item in entry.get("items", []):
            feature = item.get("feature")
            if not feature:
                continue

            agg = aggregated[feature]
            agg["count"] += 1
            agg["impacts"].append(item.get("impact_estimate", 0))
            agg["contexts"].append(intent)
            agg["users"].add(user_id)
            agg["types"].add(item.get("type", "unknown"))
            agg["values"].append(item.get("value", 0))

    # Convert sets to counts
    for feature, agg in aggregated.items():
        agg["unique_users"] = len(agg["users"])
        agg["users"] = list(agg["users"])  # Convert to list for JSON
        agg["types"] = list(agg["types"])

    return dict(aggregated)


def calculate_scores(aggregated: Dict[str, Dict], config: Dict) -> Dict[str, float]:
    """Calculate proposal scores for each feature.

    Args:
        aggregated: Aggregated gap data
        config: Proposer configuration

    Returns:
        Dict of {feature_name: score}
    """
    scores = {}

    # Get all counts and impacts for normalization
    all_counts = [agg["count"] for agg in aggregated.values()]
    all_impacts = [statistics.mean(agg["impacts"]) for agg in aggregated.values() if agg["impacts"]]

    max_count = max(all_counts) if all_counts else 1
    max_impact = max(all_impacts) if all_impacts else 1

    freq_weight = config["weights"]["freq_weight"]
    impact_weight = config["weights"]["impact_weight"]

    for feature, agg in aggregated.items():
        # Normalize frequency (0-1)
        norm_freq = agg["count"] / max_count if max_count > 0 else 0

        # Normalize impact (0-1)
        avg_impact = statistics.mean(agg["impacts"]) if agg["impacts"] else 0
        norm_impact = avg_impact / max_impact if max_impact > 0 else 0

        # Combined score
        score = (freq_weight * norm_freq) + (impact_weight * norm_impact)
        scores[feature] = score

    return scores


def filter_proposals(aggregated: Dict[str, Dict], scores: Dict[str, float], config: Dict) -> List[str]:
    """Filter features that meet proposal thresholds.

    Args:
        aggregated: Aggregated gap data
        scores: Calculated scores
        config: Proposer configuration

    Returns:
        List of feature names sorted by score (descending)
    """
    min_count = config["thresholds"]["min_count"]
    min_impact = config["thresholds"]["min_impact"]
    min_users = config["thresholds"].get("min_users", 1)

    candidates = []

    for feature, agg in aggregated.items():
        # Apply thresholds
        if agg["count"] < min_count:
            continue
        if agg["unique_users"] < min_users:
            continue

        avg_impact = statistics.mean(agg["impacts"]) if agg["impacts"] else 0
        if avg_impact < min_impact:
            continue

        # Only include unmapped features
        if "unmapped" not in agg["types"]:
            continue

        candidates.append(feature)

    # Sort by score descending
    candidates.sort(key=lambda f: scores.get(f, 0), reverse=True)

    # Limit to max proposals
    max_proposals = config["max_proposals_per_night"]
    return candidates[:max_proposals]


def generate_container_id(feature_name: str, parent: str, version: int = 1) -> str:
    """Generate container ID from feature name.

    Args:
        feature_name: Feature name (e.g., parallelism_pattern_score)
        parent: Parent domain (e.g., LanguageStyleDNA)
        version: Version number

    Returns:
        Container ID (e.g., LanguageStyleDNA.ParallelismRhetoricDNA.v1)
    """
    # Convert snake_case to PascalCase
    words = feature_name.replace('_', ' ').title().replace(' ', '')
    container_name = f"{words}DNA"

    return f"{parent}.{container_name}.v{version}"


def determine_governance(feature_name: str, config: Dict) -> Dict:
    """Determine governance flags for a feature.

    Args:
        feature_name: Feature name
        config: Proposer configuration

    Returns:
        Governance dict with sensitive, consent_required, notes
    """
    sensitive_keywords = config["governance"]["sensitive_keywords"]
    consent_keywords = config["governance"]["consent_keywords"]

    feature_lower = feature_name.lower()

    sensitive = any(keyword in feature_lower for keyword in sensitive_keywords)
    consent_required = any(keyword in feature_lower for keyword in consent_keywords)

    governance = {
        "sensitive": sensitive,
        "consent_required": consent_required,
        "notes": ""
    }

    if sensitive or consent_required:
        governance["notes"] = "Requires ethics review for potential dialect/accent sensitivity"

    return governance


def create_proposal(feature: str, agg: Dict, config: Dict, feature_map: Dict) -> Dict:
    """Create a container proposal from aggregated data.

    Args:
        feature: Feature name
        agg: Aggregated data for feature
        config: Proposer configuration
        feature_map: Feature mapping data

    Returns:
        Candidate container proposal dict
    """
    # Determine parent from feature map or config
    unmapped_info = feature_map.get("unmapped_features", {}).get(feature, {})
    potential_parent = unmapped_info.get("potential_parent", "LanguageStyleDNA")

    # Generate container ID
    container_id = generate_container_id(feature, potential_parent, config["namespaces"]["default_version"])

    # Calculate stats
    avg_impact = statistics.mean(agg["impacts"]) if agg["impacts"] else 0
    avg_value = statistics.mean(agg["values"]) if agg["values"] else 0

    # Determine expected value type
    if avg_value < 0.3:
        expected_value = "low|medium|high"
    elif avg_value > 0.7:
        expected_value = "0.0-1.0 score"
    else:
        expected_value = "low|medium|high"

    # Get most common intents
    intent_counts = defaultdict(int)
    for intent in agg["contexts"]:
        intent_counts[intent] += 1
    top_intents = sorted(intent_counts.keys(), key=lambda k: intent_counts[k], reverse=True)[:3]

    # Determine UCN seed based on confidence
    ucn_seed = int(min(1000, max(300, avg_impact * 10000)))

    # Get description from feature map
    description = unmapped_info.get("description", f"Feature: {feature}")

    # Determine governance
    governance = determine_governance(feature, config)

    proposal = {
        "id": container_id,
        "parent": potential_parent,
        "status": config["namespaces"]["default_status"],
        "ai_upgradable": config["namespaces"]["default_ai_upgradable"],
        "description": description,
        "scoring_plan": {
            "extractor_feature": feature,
            "method": "pattern detector + statistical analysis",
            "expected_value": expected_value,
            "ucn_seed": ucn_seed
        },
        "evidence_summary": {
            "daily_count": agg["count"],
            "avg_impact": round(avg_impact, 3),
            "top_intents": top_intents,
            "sample_users": agg["unique_users"]
        },
        "governance": governance
    }

    return proposal


def save_proposals(proposals: List[Dict], output_dir: Path, date_str: str):
    """Save proposals to dated JSON file.

    Args:
        proposals: List of proposal dicts
        output_dir: Output directory
        date_str: Date string (YYYY-MM-DD)
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{date_str}_proposals.json"

    output_data = {
        "date": date_str,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "proposal_count": len(proposals),
        "proposals": proposals
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2)

    print(f"✅ Saved {len(proposals)} proposal(s) to: {output_path}")


def save_aggregation(aggregated: Dict, output_path: Path):
    """Save aggregation rollup.

    Args:
        aggregated: Aggregated gap data
        output_path: Output file path
    """
    output_data = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "feature_count": len(aggregated),
        "features": aggregated
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2)

    print(f"✅ Saved aggregation to: {output_path}")


def print_summary(proposals: List[Dict], aggregated: Dict):
    """Print proposal summary table.

    Args:
        proposals: List of proposals
        aggregated: Aggregated gap data
    """
    print("\n" + "="*80)
    print(f"ChatDNA Container Proposals - Top {len(proposals)}")
    print("="*80)
    print(f"{'Container ID':<50} {'Count':>8} {'Impact':>10}")
    print("-"*80)

    for proposal in proposals:
        container_id = proposal["id"]
        evidence = proposal["evidence_summary"]
        print(f"{container_id:<50} {evidence['daily_count']:>8} {evidence['avg_impact']:>10.3f}")

    print("-"*80)
    print(f"Total features analyzed: {len(aggregated)}")
    print(f"Proposals generated: {len(proposals)}")
    print("="*80)


def main():
    parser = argparse.ArgumentParser(description="ChatDNA Container Proposer")
    parser.add_argument("--dry-run", action="store_true", help="Run without saving outputs")
    parser.add_argument("--date", help="Date for proposals (YYYY-MM-DD), default: today")
    args = parser.parse_args()

    # Load configuration
    config = load_config()
    print("📋 Loaded proposer configuration")

    # Load feature map
    from ReDNACoreDemo.core.feature_map import load_feature_map
    feature_map = load_feature_map()
    print(f"🗺️  Loaded feature map (version: {feature_map['version_hash']})")

    # Read gap logs
    log_dir = Path(__file__).parent.parent / "gap_logs"
    log_path = log_dir / "chatdna_unmet_features.jsonl"
    entries = read_gap_logs(log_path)
    print(f"📊 Read {len(entries)} gap log entries")

    if not entries:
        print("⚠️  No gap logs found. Run some ChatDNA renders first.")
        return

    # Aggregate
    aggregated = aggregate_gaps(entries)
    print(f"🔍 Aggregated {len(aggregated)} unique features")

    # Calculate scores
    scores = calculate_scores(aggregated, config)

    # Filter proposals
    candidate_features = filter_proposals(aggregated, scores, config)
    print(f"✨ {len(candidate_features)} features meet proposal thresholds")

    # Generate proposals
    proposals = []
    for feature in candidate_features:
        agg = aggregated[feature]
        proposal = create_proposal(feature, agg, config, feature_map)
        proposals.append(proposal)

    # Print summary
    print_summary(proposals, aggregated)

    # Save outputs
    if not args.dry_run:
        date_str = args.date if args.date else datetime.now().strftime("%Y-%m-%d")

        # Save proposals
        proposals_dir = Path(__file__).parent / "proposals"
        save_proposals(proposals, proposals_dir, date_str)

        # Save aggregation
        agg_path = log_dir / "chatdna_unmet_features_agg.json"
        save_aggregation(aggregated, agg_path)
    else:
        print("\n🔶 Dry run - no outputs saved")


if __name__ == "__main__":
    main()
