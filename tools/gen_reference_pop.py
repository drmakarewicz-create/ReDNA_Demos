#!/usr/bin/env python3
"""
Generate synthetic reference population distributions for traits.

Usage:
    python tools/gen_reference_pop.py --output data/reference_pop

Creates JSON files with synthetic UCN distributions using beta mixtures.
"""

import json
import argparse
from pathlib import Path
import numpy as np


def beta_mixture_samples(n: int, params: list) -> list:
    """
    Generate samples from a beta mixture distribution.

    Args:
        n: Number of samples
        params: List of (weight, alpha, beta) tuples

    Returns:
        List of UCN values in [0, 1]
    """
    samples = []
    for weight, alpha, beta_param in params:
        count = int(n * weight)
        beta_samples = np.random.beta(alpha, beta_param, count)
        samples.extend(beta_samples.tolist())

    # Fill remaining to reach exactly n samples
    while len(samples) < n:
        weight, alpha, beta_param = params[0]
        samples.append(np.random.beta(alpha, beta_param))

    return sorted(samples[:n])


def generate_chronotype_distribution(n: int = 1000) -> dict:
    """
    Generate Chronotype reference distribution.

    Bimodal: early birds (high UCN) and night owls (low UCN).
    """
    params = [
        (0.4, 2, 5),   # Night owls (lower UCN)
        (0.4, 5, 2),   # Morning larks (higher UCN)
        (0.2, 3, 3),   # In-between
    ]
    samples = beta_mixture_samples(n, params)
    return {"samples": samples, "n": n, "trait_id": "Chronotype"}


def generate_eye_color_distribution(n: int = 1000) -> dict:
    """
    Generate eye color UCN distribution.

    Roughly uniform with slight skew.
    """
    params = [
        (0.7, 3, 3),   # Mostly uniform
        (0.3, 2, 4),   # Slight skew
    ]
    samples = beta_mixture_samples(n, params)
    return {"samples": samples, "n": n, "trait_id": "EyeColor"}


def generate_generic_distribution(n: int = 1000) -> dict:
    """
    Generate a generic balanced distribution.

    Used as fallback for traits without specific models.
    """
    params = [(1.0, 3, 3)]  # Symmetric beta
    samples = beta_mixture_samples(n, params)
    return {"samples": samples, "n": n, "trait_id": "Generic"}


TRAIT_GENERATORS = {
    "Chronotype": generate_chronotype_distribution,
    "BehaviorDNA.Sleep.Chronotype": generate_chronotype_distribution,
    "PaDNA.Chronotype": generate_chronotype_distribution,
    "EyeColor": generate_eye_color_distribution,
    "BehaviorDNA.Appearance.EyeColor": generate_eye_color_distribution,
    "PaDNA.EyeDNA.IrisColor": generate_eye_color_distribution,
}


def main():
    parser = argparse.ArgumentParser(description="Generate reference population distributions")
    parser.add_argument("--output", type=str, default="data/reference_pop",
                        help="Output directory for reference population JSON files")
    parser.add_argument("--n-samples", type=int, default=1000,
                        help="Number of samples per distribution")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for reproducibility")

    args = parser.parse_args()

    # Set random seed
    np.random.seed(args.seed)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Generating reference populations in {output_dir}")

    # Generate distributions
    for trait_id, generator in TRAIT_GENERATORS.items():
        distribution = generator(args.n_samples)
        simplified_name = trait_id.split(".")[-1]

        output_path = output_dir / f"{simplified_name}.json"
        with open(output_path, 'w') as f:
            json.dump(distribution, f, indent=2)

        print(f"  ✓ {simplified_name}.json ({len(distribution['samples'])} samples)")

    # Generate a generic fallback
    generic_dist = generate_generic_distribution(args.n_samples)
    generic_path = output_dir / "generic.json"
    with open(generic_path, 'w') as f:
        json.dump(generic_dist, f, indent=2)
    print(f"  ✓ generic.json ({len(generic_dist['samples'])} samples)")

    print(f"\nGenerated {len(TRAIT_GENERATORS) + 1} reference distributions")


if __name__ == "__main__":
    main()
