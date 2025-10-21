#!/usr/bin/env python3
"""
Synthetic Reference Population Calibration Report

Analyzes synthetic CDF files and compares them against sample demo UCNs
to verify calibration targets are met.

Phase 10.2.3: Ensure demo users with UCN 0.7-0.9 land in RR 30-80% range.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import bisect


def load_cdf(file_path: Path) -> Dict:
    """Load CDF from JSON file."""
    with open(file_path, 'r') as f:
        return json.load(f)


def percentile_for_ucn(samples: List[float], ucn: float) -> float:
    """Calculate percentile for given UCN."""
    pos = bisect.bisect_left(samples, ucn)
    return (pos / len(samples)) * 100.0


def analyze_universe(cdf_data: Dict) -> Dict:
    """Analyze a single universe CDF."""
    samples = cdf_data['samples']
    stats = cdf_data.get('stats', {})

    # Test calibration points
    test_ucns = [0.50, 0.60, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95]
    calibration = {}

    for ucn in test_ucns:
        rr = percentile_for_ucn(samples, ucn)
        calibration[f"ucn_{ucn:.2f}"] = round(rr, 1)

    return {
        "stats": stats,
        "calibration": calibration,
        "metadata": cdf_data.get('metadata', {}),
    }


def print_table(universes: Dict[str, Dict]):
    """Print formatted table of universe statistics."""
    print("\n" + "=" * 100)
    print("UNIVERSE STATISTICS")
    print("=" * 100)
    print()

    # Header
    print(f"{'Universe':<15} {'Min':>8} {'Mean':>8} {'Median':>8} {'P90':>8} {'Max':>8} {'Std':>8}")
    print("-" * 100)

    # Data rows
    for name, data in sorted(universes.items()):
        stats = data['stats']
        print(f"{name:<15} "
              f"{stats.get('min', 0):.4f}   "
              f"{stats.get('mean', 0):.4f}   "
              f"{stats.get('median', 0):.4f}   "
              f"{stats.get('p90', 0):.4f}   "
              f"{stats.get('max', 0):.4f}   "
              f"{stats.get('std', 0):.4f}")

    print()


def print_calibration_table(universes: Dict[str, Dict]):
    """Print UCN → RR calibration table."""
    print("=" * 100)
    print("CALIBRATION: UCN → RR PERCENTILE")
    print("=" * 100)
    print()

    # Header
    test_ucns = [0.50, 0.60, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95]
    header = f"{'Universe':<15}"
    for ucn in test_ucns:
        header += f" UCN{ucn:.2f}:RR"
    print(header)
    print("-" * 100)

    # Data rows
    for name, data in sorted(universes.items()):
        row = f"{name:<15}"
        for ucn in test_ucns:
            key = f"ucn_{ucn:.2f}"
            rr = data['calibration'].get(key, 0)
            row += f"    {rr:>5.1f}%"
        print(row)

    print()

    # Highlight key calibration targets
    print("KEY TARGETS (for combined universe):")
    combined = universes.get('combined', {})
    cal = combined.get('calibration', {})

    targets = [
        ("UCN=0.70 → RR", cal.get('ucn_0.70', 0), "50-60%"),
        ("UCN=0.80 → RR", cal.get('ucn_0.80', 0), "75-85%"),
        ("UCN=0.90 → RR", cal.get('ucn_0.90', 0), "90-95%"),
    ]

    for label, actual, target in targets:
        status = "✓" if check_target(actual, target) else "✗"
        print(f"  {status} {label}: {actual:.1f}% (target: {target})")

    print()


def check_target(actual: float, target_range: str) -> bool:
    """Check if actual value falls within target range."""
    # Parse "50-60%" format
    low, high = target_range.rstrip('%').split('-')
    return float(low) <= actual <= float(high)


def generate_markdown_report(universes: Dict[str, Dict], output_path: Path):
    """Generate markdown calibration report."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    md = f"""# Synthetic Reference Population Calibration Report

**Generated:** {timestamp}
**Phase:** 10.2.3
**Purpose:** Verify demo users with moderate UCNs land in mid-range RR (30-80%)

## Universe Statistics

| Universe | Min | Mean | Median | P90 | Max | Std |
|----------|-----|------|--------|-----|-----|-----|
"""

    for name, data in sorted(universes.items()):
        stats = data['stats']
        md += (f"| {name} | "
               f"{stats.get('min', 0):.4f} | "
               f"{stats.get('mean', 0):.4f} | "
               f"{stats.get('median', 0):.4f} | "
               f"{stats.get('p90', 0):.4f} | "
               f"{stats.get('max', 0):.4f} | "
               f"{stats.get('std', 0):.4f} |\n")

    md += "\n## Calibration: UCN → RR Percentile\n\n"
    md += "| Universe | UCN=0.50 | UCN=0.60 | UCN=0.70 | UCN=0.75 | UCN=0.80 | UCN=0.85 | UCN=0.90 | UCN=0.95 |\n"
    md += "|----------|----------|----------|----------|----------|----------|----------|----------|----------|\n"

    test_ucns = [0.50, 0.60, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95]
    for name, data in sorted(universes.items()):
        row = f"| {name} |"
        for ucn in test_ucns:
            key = f"ucn_{ucn:.2f}"
            rr = data['calibration'].get(key, 0)
            row += f" {rr:.1f}% |"
        md += row + "\n"

    md += "\n## Calibration Targets (Combined Universe)\n\n"

    combined = universes.get('combined', {})
    cal = combined.get('calibration', {})

    targets = [
        ("UCN=0.70 → RR", cal.get('ucn_0.70', 0), "50-60%"),
        ("UCN=0.80 → RR", cal.get('ucn_0.80', 0), "75-85%"),
        ("UCN=0.90 → RR", cal.get('ucn_0.90', 0), "90-95%"),
    ]

    for label, actual, target in targets:
        status = "✅" if check_target(actual, target) else "❌"
        md += f"- {status} **{label}**: {actual:.1f}% (target: {target})\n"

    md += "\n## Summary\n\n"

    all_pass = all(check_target(actual, target) for _, actual, target in targets)
    if all_pass:
        md += "✅ **All calibration targets met!** Demo users with moderate UCNs will land in mid-range RR values.\n"
    else:
        md += "⚠️ **Some calibration targets not met.** Review universe configuration and regenerate.\n"

    md += "\n## Next Steps\n\n"
    md += "1. Restart Core API to reload synthetic populations: `make cp-nuclear`\n"
    md += "2. Verify with demo user: `curl -s http://127.0.0.1:8004/ui/unabridged?user_id=TEST | jq '.traits[] | {trait_id, ucn, rr}'`\n"
    md += "3. Expect RR values distributed roughly 30-80% for mid-range UCNs\n"

    with open(output_path, 'w') as f:
        f.write(md)

    print(f"Markdown report saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Generate calibration report for synthetic populations")
    parser.add_argument('--data-dir', default='data/reference_pop', help="Path to reference_pop directory")
    parser.add_argument('--output', help="Output path for markdown report")

    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        print(f"ERROR: Data directory not found: {data_dir}")
        sys.exit(1)

    print("=" * 100)
    print("SYNTHETIC REFERENCE POPULATION CALIBRATION REPORT")
    print("Phase 10.2.3")
    print("=" * 100)

    # Load all universe CDFs
    universes = {}
    for cdf_file in ['low.json', 'medium.json', 'high.json', 'combined.json', 'generic.json']:
        cdf_path = data_dir / cdf_file
        if cdf_path.exists():
            universe_name = cdf_file.replace('.json', '')
            cdf_data = load_cdf(cdf_path)
            universes[universe_name] = analyze_universe(cdf_data)
            print(f"Loaded: {universe_name}")

    if not universes:
        print("ERROR: No CDF files found in data directory")
        sys.exit(1)

    print()

    # Print tables
    print_table(universes)
    print_calibration_table(universes)

    # Generate markdown report
    if args.output:
        output_path = Path(args.output)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = Path(f"docs/Intel/SyntheticPopReport_{timestamp}.md")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    generate_markdown_report(universes, output_path)

    print("=" * 100)
    print("REPORT COMPLETE")
    print("=" * 100)


if __name__ == "__main__":
    main()
