#!/usr/bin/env python3
"""
BeliefDNA Evaluation Harness

Benchmarks stance consistency and similarity across belief personas.
Generates responses to philosophical prompts and evaluates:
- Stance consistency (do responses align with expected beliefs?)
- Internal coherence (are responses consistent with each other?)
- Response quality metrics

Usage:
    python eval/beliefdna/harness.py
    python eval/beliefdna/harness.py --persona persona_utilitarian
    python eval/beliefdna/harness.py --output eval/beliefdna/results.md
"""

import json
import sys
import argparse
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
import statistics

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

API_BASE = "http://127.0.0.1:8000"

PERSONAS = [
    "persona_utilitarian",
    "persona_virtue_ethics",
    "persona_deontological"
]

PERSONA_LABELS = {
    "persona_utilitarian": "Utilitarian",
    "persona_virtue_ethics": "Virtue Ethics",
    "persona_deontological": "Deontological"
}


def load_prompts(prompts_file: Path) -> List[str]:
    """Load stance prompts from file, filtering out comments and empty lines."""
    prompts = []
    with open(prompts_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                prompts.append(line)
    return prompts


def render_belief_response(user_id: str, prompt: str) -> Dict[str, Any]:
    """Call BeliefDNA Coach /render endpoint."""
    try:
        response = requests.post(
            f"{API_BASE}/api/coach/beliefdna_coach/render",
            json={
                "user_id": user_id,
                "prompt": prompt,
                "intent": "philosophical"
            },
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e)}


def calculate_stance_metrics(responses: List[Dict[str, Any]]) -> Dict[str, float]:
    """Calculate metrics for a set of responses."""
    if not responses:
        return {}

    # Extract similarity scores
    similarities = []
    reason_map_counts = []
    container_counts = []

    for resp in responses:
        if "similarity" in resp:
            similarities.append(resp["similarity"].get("overall", 0))
        if "reason_map" in resp:
            reason_map_counts.append(len(resp["reason_map"]))
        if "relevant_containers" in resp:
            container_counts.append(len(resp["relevant_containers"]))

    metrics = {}
    if similarities:
        metrics["mean_similarity"] = statistics.mean(similarities)
        metrics["std_similarity"] = statistics.stdev(similarities) if len(similarities) > 1 else 0
    if reason_map_counts:
        metrics["mean_reason_traits"] = statistics.mean(reason_map_counts)
    if container_counts:
        metrics["mean_containers"] = statistics.mean(container_counts)

    return metrics


def run_benchmark(
    personas: List[str],
    prompts: List[str],
    limit: int = None
) -> Dict[str, Any]:
    """
    Run benchmark across all personas and prompts.

    Returns:
        Dict with results per persona and aggregate stats
    """
    if limit:
        prompts = prompts[:limit]

    results = {
        "personas": {},
        "prompts_evaluated": len(prompts),
        "timestamp": datetime.now().isoformat()
    }

    print(f"🧪 Running BeliefDNA Benchmark")
    print(f"   Personas: {len(personas)}")
    print(f"   Prompts: {len(prompts)}")
    print()

    for persona_id in personas:
        persona_label = PERSONA_LABELS.get(persona_id, persona_id)
        print(f"📊 Evaluating {persona_label}...")

        responses = []
        for i, prompt in enumerate(prompts, 1):
            print(f"   [{i}/{len(prompts)}] {prompt[:60]}...", end='\r')
            resp = render_belief_response(persona_id, prompt)
            if "error" not in resp:
                responses.append({
                    "prompt": prompt,
                    "output": resp.get("output", ""),
                    "similarity": resp.get("similarity", {}),
                    "reason_map": resp.get("reason_map", []),
                    "relevant_containers": resp.get("relevant_containers", []),
                    "rr_summary": resp.get("rr_summary", {})
                })
            else:
                print(f"\n   ⚠️  Error on prompt: {resp['error']}")

        print(f"\n   ✅ Completed {len(responses)}/{len(prompts)} prompts")

        # Calculate metrics
        metrics = calculate_stance_metrics(responses)

        results["personas"][persona_id] = {
            "label": persona_label,
            "responses": responses,
            "metrics": metrics,
            "total_prompts": len(prompts),
            "successful_responses": len(responses)
        }
        print(f"   Metrics: {metrics}")
        print()

    return results


def generate_markdown_report(results: Dict[str, Any], output_path: Path):
    """Generate Markdown leaderboard and report."""
    md = []
    md.append("# BeliefDNA Stance Evaluation Results")
    md.append("")
    md.append(f"**Timestamp**: {results['timestamp']}")
    md.append(f"**Prompts Evaluated**: {results['prompts_evaluated']}")
    md.append("")

    # Leaderboard table
    md.append("## Leaderboard")
    md.append("")
    md.append("| Rank | Persona | Mean Similarity | Std Dev | Reason Traits | Containers | Success Rate |")
    md.append("|------|---------|-----------------|---------|---------------|------------|--------------|")

    # Sort by mean similarity
    persona_rows = []
    for persona_id, data in results["personas"].items():
        metrics = data["metrics"]
        success_rate = (data["successful_responses"] / data["total_prompts"]) * 100
        persona_rows.append({
            "label": data["label"],
            "mean_sim": metrics.get("mean_similarity", 0),
            "std_sim": metrics.get("std_similarity", 0),
            "reason_traits": metrics.get("mean_reason_traits", 0),
            "containers": metrics.get("mean_containers", 0),
            "success_rate": success_rate
        })

    persona_rows.sort(key=lambda x: x["mean_sim"], reverse=True)

    for rank, row in enumerate(persona_rows, 1):
        md.append(
            f"| {rank} | {row['label']} | {row['mean_sim']:.3f} | {row['std_sim']:.3f} | "
            f"{row['reason_traits']:.1f} | {row['containers']:.1f} | {row['success_rate']:.1f}% |"
        )

    md.append("")

    # Detailed persona sections
    md.append("## Detailed Results")
    md.append("")

    for persona_id, data in results["personas"].items():
        md.append(f"### {data['label']}")
        md.append("")
        md.append(f"**Success Rate**: {data['successful_responses']}/{data['total_prompts']} ({(data['successful_responses']/data['total_prompts'])*100:.1f}%)")
        md.append("")
        md.append("**Metrics**:")
        for metric_name, metric_value in data["metrics"].items():
            md.append(f"- {metric_name}: {metric_value:.3f}")
        md.append("")

        # Sample responses
        md.append("**Sample Responses** (first 3):")
        md.append("")
        for i, resp in enumerate(data["responses"][:3], 1):
            md.append(f"{i}. **Prompt**: {resp['prompt']}")
            md.append(f"   **Response**: {resp['output']}")
            md.append(f"   **Similarity**: {resp['similarity'].get('overall', 0):.3f}")
            md.append("")

        md.append("---")
        md.append("")

    # Write to file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(md))

    print(f"✅ Report written to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="BeliefDNA evaluation harness")
    parser.add_argument("--persona", help="Evaluate single persona (default: all)")
    parser.add_argument("--limit", type=int, help="Limit number of prompts to evaluate")
    parser.add_argument("--output", default="eval/beliefdna/results.md", help="Output markdown file")
    parser.add_argument("--prompts", default="fixtures/beliefdna/prompts/stance_prompts.txt", help="Prompts file")
    args = parser.parse_args()

    # Load prompts
    prompts_file = Path(args.prompts)
    if not prompts_file.exists():
        print(f"❌ Prompts file not found: {prompts_file}")
        sys.exit(1)

    prompts = load_prompts(prompts_file)
    print(f"📝 Loaded {len(prompts)} prompts from {prompts_file}")
    print()

    # Determine personas to evaluate
    personas_to_eval = [args.persona] if args.persona else PERSONAS

    # Run benchmark
    results = run_benchmark(personas_to_eval, prompts, limit=args.limit)

    # Generate report
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    generate_markdown_report(results, output_path)

    print()
    print("🎉 Evaluation complete!")


if __name__ == "__main__":
    main()
