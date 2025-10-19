"""Entry points for running conflict learning jobs from scripts."""

from __future__ import annotations

import argparse

from .learning import run_nightly_learning


def main() -> None:
    parser = argparse.ArgumentParser(description="Run conflict calibration jobs")
    parser.add_argument("user", nargs="*", help="Optional list of user IDs to process")
    args = parser.parse_args()
    user_ids = args.user or []
    snapshot = run_nightly_learning(user_ids)
    print("Conflict learning snapshot")
    print(snapshot)


if __name__ == "__main__":
    main()

