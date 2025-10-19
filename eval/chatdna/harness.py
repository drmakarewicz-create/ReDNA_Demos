#!/usr/bin/env python3
"""
ChatDNA Style Evaluation Harness

Runs A/A vs A/B style tests for each persona user against benchmark prompts.
Generates similarity metrics and leaderboards showing self > others signal.

Usage:
    python eval/chatdna/harness.py
    python eval/chatdna/harness.py --persona persona_hemingway
    python eval/chatdna/harness.py --mini  # Run on subset of prompts
"""

import json
import sys
import argparse
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple
import statistics

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Configuration
API_BASE = "http://127.0.0.1:8000"
PERSONAS = [
    "persona_hemingway",
    "persona_obama",
    "persona_joan_didion",
    "persona_winston_churchill",
    "persona_maya_angelou"
]


def load_benchmark_prompts(mini: bool = False) -> List[Tuple[str, str, str]]:
    """Load benchmark prompts from file.

    Returns:
        List of (category, prompt, expected_style_note) tuples
    """
    prompts_file = Path(__file__).parent.parent.parent / "fixtures" / "chatdna" / "prompts" / "benchmark_prompts.txt"

    prompts = []
    with open(prompts_file, 'r', encoding='utf-8') as f:
        current_category = "general"
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            # Category headers like "## Casual (5 prompts)"
            if line.startswith('##'):
                # Extract category name (e.g., "Casual" from "## Casual (5 prompts)")
                category_text = line[2:].strip()
                current_category = category_text.split('(')[0].strip()
            else:
                # Direct prompt line (no bullet needed in this format)
                prompts.append((current_category, line, ""))

    if mini:
        # Take 2 prompts from each category
        mini_prompts = []
        categories_seen = {}
        for cat, prompt, note in prompts:
            if cat not in categories_seen:
                categories_seen[cat] = 0
            if categories_seen[cat] < 2:
                mini_prompts.append((cat, prompt, note))
                categories_seen[cat] += 1
        return mini_prompts

    return prompts


def call_render_endpoint(user_id: str, prompt: str, intent: str = "casual") -> Dict:
    """Call ChatDNA Coach /render endpoint.

    Args:
        user_id: Persona user ID
        prompt: Prompt to render
        intent: Intent category (casual, formal, etc.)

    Returns:
        API response dict with output and similarity scores
    """
    url = f"{API_BASE}/api/coach/chatdna_coach/render"
    payload = {
        "user_id": user_id,
        "prompt": prompt,
        "intent": intent
    }

    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"⚠️  API call failed for {user_id}: {e}")
        return {
            "output": "",
            "similarity": {"linguistic": 0.0, "tone": 0.0, "overall": 0.0},
            "error": str(e)
        }


def compute_similarity_score(text_a: str, text_b: str) -> float:
    """Compute simple similarity score between two texts.

    This is a stub implementation. In production, would use:
    - Embedding cosine similarity
    - Style feature extraction
    - LLM-based similarity judgment

    For now, returns mock score based on text length similarity.
    """
    len_a, len_b = len(text_a), len(text_b)
    if len_a == 0 or len_b == 0:
        return 0.0

    # Mock similarity based on length ratio (placeholder)
    ratio = min(len_a, len_b) / max(len_a, len_b)
    return ratio * 0.8  # Cap at 0.8 for mock


def run_aa_test(user_id: str, prompts: List[Tuple[str, str, str]]) -> Dict:
    """Run A/A test: same persona rendering same prompts twice.

    Measures self-consistency (should be high).
    """
    print(f"\n🔄 Running A/A test for {user_id}...")

    aa_scores = []

    for category, prompt, _ in prompts[:5]:  # Use first 5 prompts for A/A
        intent = category.lower() if category else "casual"

        # Render twice
        response_1 = call_render_endpoint(user_id, prompt, intent)
        response_2 = call_render_endpoint(user_id, prompt, intent)

        if "error" in response_1 or "error" in response_2:
            continue

        # Compute similarity between two renders
        sim_score = compute_similarity_score(response_1.get("output", ""), response_2.get("output", ""))
        aa_scores.append(sim_score)

    aa_mean = statistics.mean(aa_scores) if aa_scores else 0.0
    print(f"   A/A self-consistency: {aa_mean:.3f}")

    return {
        "mean": aa_mean,
        "scores": aa_scores,
        "n": len(aa_scores)
    }


def run_ab_test(user_id_a: str, user_id_b: str, prompts: List[Tuple[str, str, str]]) -> Dict:
    """Run A/B test: two different personas rendering same prompts.

    Measures distinctiveness (should be lower than A/A).
    """
    ab_scores = []

    for category, prompt, _ in prompts[:5]:  # Use first 5 prompts for A/B
        intent = category.lower() if category else "casual"

        # Render with both personas
        response_a = call_render_endpoint(user_id_a, prompt, intent)
        response_b = call_render_endpoint(user_id_b, prompt, intent)

        if "error" in response_a or "error" in response_b:
            continue

        # Compute cross-persona similarity
        sim_score = compute_similarity_score(response_a.get("output", ""), response_b.get("output", ""))
        ab_scores.append(sim_score)

    ab_mean = statistics.mean(ab_scores) if ab_scores else 0.0

    return {
        "mean": ab_mean,
        "scores": ab_scores,
        "n": len(ab_scores)
    }


def run_full_evaluation(personas: List[str], prompts: List[Tuple[str, str, str]]) -> Dict:
    """Run full evaluation across all personas.

    Returns:
        Dict with A/A scores, A/B matrix, and leaderboard
    """
    print(f"📊 Running ChatDNA Evaluation Harness")
    print(f"   Personas: {len(personas)}")
    print(f"   Prompts: {len(prompts)}")

    results = {
        "timestamp": datetime.now().isoformat(),
        "personas": personas,
        "prompt_count": len(prompts),
        "aa_tests": {},
        "ab_matrix": {},
        "leaderboard": []
    }

    # Run A/A tests
    print("\n" + "="*60)
    print("A/A Tests (Self-Consistency)")
    print("="*60)

    for persona in personas:
        aa_result = run_aa_test(persona, prompts)
        results["aa_tests"][persona] = aa_result

    # Run A/B tests
    print("\n" + "="*60)
    print("A/B Tests (Cross-Persona Distinctiveness)")
    print("="*60)

    for i, persona_a in enumerate(personas):
        results["ab_matrix"][persona_a] = {}
        print(f"\n📝 {persona_a} vs others...")

        for persona_b in personas:
            if persona_a == persona_b:
                results["ab_matrix"][persona_a][persona_b] = {"mean": 1.0, "scores": [], "n": 0}
                continue

            ab_result = run_ab_test(persona_a, persona_b, prompts)
            results["ab_matrix"][persona_a][persona_b] = ab_result
            print(f"   vs {persona_b}: {ab_result['mean']:.3f}")

    # Compute leaderboard
    print("\n" + "="*60)
    print("Leaderboard (Self vs Others Delta)")
    print("="*60)

    for persona in personas:
        aa_score = results["aa_tests"][persona]["mean"]

        # Average A/B score with all others
        ab_scores = [
            results["ab_matrix"][persona][other]["mean"]
            for other in personas
            if other != persona
        ]
        avg_ab_score = statistics.mean(ab_scores) if ab_scores else 0.0

        delta = aa_score - avg_ab_score

        leaderboard_entry = {
            "persona": persona,
            "aa_score": aa_score,
            "avg_ab_score": avg_ab_score,
            "delta": delta,
            "rank": 0  # Will be set after sorting
        }
        results["leaderboard"].append(leaderboard_entry)

    # Sort by delta (higher is better)
    results["leaderboard"].sort(key=lambda x: x["delta"], reverse=True)
    for i, entry in enumerate(results["leaderboard"]):
        entry["rank"] = i + 1

    # Print leaderboard
    print("\nRank  Persona                    A/A    Avg A/B   Delta")
    print("-" * 60)
    for entry in results["leaderboard"]:
        print(f"{entry['rank']:2d}    {entry['persona']:25s} {entry['aa_score']:.3f}  {entry['avg_ab_score']:.3f}   {entry['delta']:+.3f}")

    return results


def save_results(results: Dict, output_dir: Path):
    """Save results to JSON and markdown."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save JSON
    json_path = output_dir / "metrics.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
    print(f"\n✅ Saved metrics to: {json_path}")

    # Save markdown report
    md_path = output_dir / "latest.md"
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write("# ChatDNA Evaluation Report\n\n")
        f.write(f"**Timestamp:** {results['timestamp']}  \n")
        f.write(f"**Personas:** {len(results['personas'])}  \n")
        f.write(f"**Prompts:** {results['prompt_count']}  \n\n")

        f.write("## Leaderboard (Self > Others Delta)\n\n")
        f.write("| Rank | Persona | A/A Score | Avg A/B Score | Delta |\n")
        f.write("|------|---------|-----------|---------------|-------|\n")
        for entry in results["leaderboard"]:
            f.write(f"| {entry['rank']} | {entry['persona']} | {entry['aa_score']:.3f} | {entry['avg_ab_score']:.3f} | {entry['delta']:+.3f} |\n")

        f.write("\n## A/A Test Results (Self-Consistency)\n\n")
        f.write("| Persona | Mean Score | N |\n")
        f.write("|---------|------------|---|\n")
        for persona, result in results["aa_tests"].items():
            f.write(f"| {persona} | {result['mean']:.3f} | {result['n']} |\n")

        f.write("\n## A/B Cross-Persona Matrix\n\n")
        f.write("Rows = Persona A, Columns = Persona B\n\n")

        # Table header
        f.write("| A \\ B |")
        for persona in results["personas"]:
            short_name = persona.replace("persona_", "")
            f.write(f" {short_name} |")
        f.write("\n")

        f.write("|-------|")
        for _ in results["personas"]:
            f.write("------|")
        f.write("\n")

        # Table rows
        for persona_a in results["personas"]:
            short_a = persona_a.replace("persona_", "")
            f.write(f"| {short_a} |")
            for persona_b in results["personas"]:
                score = results["ab_matrix"][persona_a][persona_b]["mean"]
                f.write(f" {score:.3f} |")
            f.write("\n")

    print(f"✅ Saved report to: {md_path}")


def main():
    parser = argparse.ArgumentParser(description="ChatDNA Evaluation Harness")
    parser.add_argument("--persona", help="Run for single persona only")
    parser.add_argument("--mini", action="store_true", help="Run on subset of prompts (faster)")
    parser.add_argument("--output-dir", default="eval/chatdna/leaderboards", help="Output directory")
    args = parser.parse_args()

    # Load prompts
    prompts = load_benchmark_prompts(mini=args.mini)

    # Determine personas to test
    if args.persona:
        personas = [args.persona]
    else:
        personas = PERSONAS

    # Run evaluation
    results = run_full_evaluation(personas, prompts)

    # Save results
    output_dir = Path(args.output_dir)
    save_results(results, output_dir)

    print("\n🎉 Evaluation complete!")


if __name__ == "__main__":
    main()
