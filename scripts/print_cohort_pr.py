#!/usr/bin/env python3
"""Print PR number(s) from a cohort JSON artifact.

Examples:
  python3 scripts/print_cohort_pr.py artifacts/examples/ghostty-e2e/cohort.v1.json
  python3 scripts/print_cohort_pr.py artifacts/examples/ghostty-e2e/cohort.v1.json --index 3
  python3 scripts/print_cohort_pr.py artifacts/examples/ghostty-e2e/cohort.v1.json --all
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read PR numbers from cohort JSON")
    parser.add_argument("cohort", type=Path, help="Path to cohort JSON")
    parser.add_argument(
        "--index",
        type=int,
        default=0,
        help="Zero-based index to print when not using --all (default: 0)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Print all PR numbers, one per line",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.cohort.exists():
        print(f"error: cohort file not found: {args.cohort}", file=sys.stderr)
        return 1

    payload = json.loads(args.cohort.read_text(encoding="utf-8"))
    pr_numbers = payload.get("pr_numbers")

    if not isinstance(pr_numbers, list) or not pr_numbers:
        print("error: cohort JSON has no non-empty 'pr_numbers' list", file=sys.stderr)
        return 1

    if args.all:
        for value in pr_numbers:
            print(value)
        return 0

    if args.index < 0 or args.index >= len(pr_numbers):
        print(
            f"error: --index {args.index} out of range for {len(pr_numbers)} PRs",
            file=sys.stderr,
        )
        return 1

    print(pr_numbers[args.index])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
