#!/usr/bin/env python3
"""
Synthetic Reference Population Generator

Generates synthetic CDF files for RR percentile calculations based on
configured universe baselines (low, medium, high, combined).

Phase 10.2.3: Recalibrated so demo users land in mid-range RR (30-80%)
instead of appearing near 100%.
"""

import argparse
import json
import logging
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import numpy as np
import yaml

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def generate_beta_distribution(size: int, mean: float, spread: float,
                                min_val: float = 0.0, max_val: float = 1.0,
                                seed: int = 42) -> List[float]:
    """
    Generate UCN samples using Beta distribution.

    Args:
        size: Number of samples
        mean: Target mean (0-1)
        spread: Standard deviation (higher = more spread)
        min_val: Minimum UCN value
        max_val: Maximum UCN value
        seed: Random seed for reproducibility

    Returns:
        List of sorted UCN values
    """
    np.random.seed(seed)

    # Convert mean and spread to Beta distribution alpha/beta parameters
    # For Beta(α, β): mean = α/(α+β), variance = αβ/((α+β)²(α+β+1))
    variance = spread ** 2

    # Solve for alpha and beta
    alpha = mean * ((mean * (1 - mean) / variance) - 1)
    beta = (1 - mean) * ((mean * (1 - mean) / variance) - 1)

    # Ensure valid parameters
    alpha = max(0.1, alpha)
    beta = max(0.1, beta)

    # Generate samples
    samples = np.random.beta(alpha, beta, size)

    # Scale to [min_val, max_val]
    samples = samples * (max_val - min_val) + min_val

    # Clamp and sort
    samples = np.clip(samples, 0.0, 1.0)
    samples = np.sort(samples)

    return samples.tolist()


def generate_universe(config: Dict, universe_name: str, seed_offset: int = 0) -> Dict:
    """
    Generate a single synthetic universe.

    Args:
        config: Universe configuration
        universe_name: Name of the universe
        seed_offset: Offset for random seed

    Returns:
        Dictionary with samples and metadata
    """
    logger.info(f"Generating universe: {universe_name}")
    logger.info(f"  Size: {config['size']}")
    logger.info(f"  Mean refinement: {config['mean_refinement']}")
    logger.info(f"  Spread: {config['spread']}")

    samples = generate_beta_distribution(
        size=config['size'],
        mean=config['mean_refinement'],
        spread=config['spread'],
        min_val=config.get('min_ucn', 0.0),
        max_val=config.get('max_ucn', 1.0),
        seed=config.get('seed', 42) + seed_offset
    )

    # Compute stats
    stats = {
        "n_samples": len(samples),
        "min": float(np.min(samples)),
        "max": float(np.max(samples)),
        "mean": float(np.mean(samples)),
        "median": float(np.median(samples)),
        "std": float(np.std(samples)),
        "p25": float(np.percentile(samples, 25)),
        "p50": float(np.percentile(samples, 50)),
        "p75": float(np.percentile(samples, 75)),
        "p90": float(np.percentile(samples, 90)),
        "p95": float(np.percentile(samples, 95)),
    }

    logger.info(f"  Generated stats: min={stats['min']:.4f}, mean={stats['mean']:.4f}, "
                f"p90={stats['p90']:.4f}, max={stats['max']:.4f}")

    return {
        "samples": samples,
        "stats": stats,
        "source": "SYNTHETIC",
        "universe": universe_name,
        "cohort_keys": [],
        "cohort_values": {},
        "n_samples": len(samples),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metadata": {
            "description": config.get('description', ''),
            "mean_refinement": config['mean_refinement'],
            "spread": config['spread'],
        }
    }


def generate_combined_universe(config: Dict, universes: Dict[str, Dict]) -> Dict:
    """
    Generate combined universe by sampling from other universes.

    Args:
        config: Combined universe configuration
        universes: Generated universe data

    Returns:
        Combined universe dictionary
    """
    logger.info("Generating combined universe")

    combined_samples = []
    composition = config['composition']
    total_size = config['total_size']

    for universe_name, proportion in composition.items():
        n_samples = int(total_size * proportion)
        universe_samples = universes[universe_name]['samples']

        # Sample with replacement
        sampled = random.choices(universe_samples, k=n_samples)
        combined_samples.extend(sampled)

        logger.info(f"  Sampled {n_samples} from {universe_name} ({proportion*100:.0f}%)")

    # Sort and compute stats
    combined_samples = sorted(combined_samples)

    stats = {
        "n_samples": len(combined_samples),
        "min": float(np.min(combined_samples)),
        "max": float(np.max(combined_samples)),
        "mean": float(np.mean(combined_samples)),
        "median": float(np.median(combined_samples)),
        "std": float(np.std(combined_samples)),
        "p25": float(np.percentile(combined_samples, 25)),
        "p50": float(np.percentile(combined_samples, 50)),
        "p75": float(np.percentile(combined_samples, 75)),
        "p90": float(np.percentile(combined_samples, 90)),
        "p95": float(np.percentile(combined_samples, 95)),
    }

    logger.info(f"  Combined stats: min={stats['min']:.4f}, mean={stats['mean']:.4f}, "
                f"p90={stats['p90']:.4f}, max={stats['max']:.4f}")

    return {
        "samples": combined_samples,
        "stats": stats,
        "source": "SYNTHETIC",
        "universe": "combined",
        "cohort_keys": [],
        "cohort_values": {},
        "n_samples": len(combined_samples),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metadata": {
            "description": config.get('description', ''),
            "composition": composition,
        }
    }


def save_universe(universe_data: Dict, output_dir: Path, universe_name: str):
    """Save universe data to JSON file."""
    output_path = output_dir / f"{universe_name}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(universe_data, f, indent=2)

    logger.info(f"Saved {universe_name} universe to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic reference populations")
    parser.add_argument('--config', required=True, help="Path to config.yaml")
    parser.add_argument('--output-dir', help="Override output directory")
    parser.add_argument('--seed', type=int, help="Override random seed")

    args = parser.parse_args()

    # Load configuration
    config_path = Path(args.config)
    if not config_path.exists():
        logger.error(f"Config file not found: {config_path}")
        sys.exit(1)

    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    # Override settings
    if args.output_dir:
        config['output_dir'] = args.output_dir
    if args.seed:
        config['random_seed'] = args.seed

    output_dir = Path(config['output_dir'])
    random.seed(config.get('random_seed', 42))

    logger.info("=" * 80)
    logger.info("SYNTHETIC REFERENCE POPULATION GENERATOR")
    logger.info(f"Phase: {config['generation']['phase']}")
    logger.info(f"Version: {config['generation']['version']}")
    logger.info("=" * 80)
    logger.info("")

    # Generate individual universes
    universes = {}
    for i, (name, universe_config) in enumerate(config['universes'].items()):
        universe_config['seed'] = config.get('random_seed', 42)
        universe_data = generate_universe(universe_config, name, seed_offset=i)
        universes[name] = universe_data
        save_universe(universe_data, output_dir, name)
        logger.info("")

    # Generate combined universe
    combined_data = generate_combined_universe(config['combined'], universes)
    save_universe(combined_data, output_dir, "combined")

    # Also save as generic.json for fallback
    save_universe(combined_data, output_dir, "generic")

    logger.info("")
    logger.info("=" * 80)
    logger.info("GENERATION COMPLETE")
    logger.info("=" * 80)
    logger.info(f"Output directory: {output_dir}")
    logger.info(f"Files generated: {', '.join(list(universes.keys()) + ['combined', 'generic'])}")
    logger.info("")
    logger.info("Calibration targets:")
    for target, value in config['generation']['calibration_target'].items():
        logger.info(f"  {target}: {value}")


if __name__ == "__main__":
    main()
