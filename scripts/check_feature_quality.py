#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _iter_feature_files(run_dir: Path) -> list[Path]:
    return sorted((run_dir / "prs").glob("*/features/*.json"))


def main() -> int:
    ap = argparse.ArgumentParser(description="Check feature registry/task policy health from eval artifacts")
    ap.add_argument("--run-dir", required=True, help="Path to eval run dir")
    ap.add_argument("--strict", action="store_true", help="Fail non-zero on violations/unresolved keys")
    args = ap.parse_args()

    run_dir = Path(args.run_dir)
    files = _iter_feature_files(run_dir)
    if not files:
        print("feature-quality: no feature files found")
        return 0

    unresolved_total = 0
    violations_total = 0

    for p in files:
        payload = json.loads(p.read_text(encoding="utf-8"))
        meta = payload.get("meta") if isinstance(payload, dict) else None
        if not isinstance(meta, dict):
            continue

        reg = meta.get("feature_registry")
        if isinstance(reg, dict):
            unresolved = int(reg.get("unresolved_count", 0) or 0)
            unresolved_total += unresolved
            if unresolved > 0:
                print(f"WARN unresolved_keys={unresolved} file={p}")

        pol = meta.get("task_policy")
        if isinstance(pol, dict):
            violations = int(pol.get("violation_count", 0) or 0)
            violations_total += violations
            if violations > 0:
                print(f"WARN task_policy_violations={violations} file={p}")

    print(
        "feature-quality summary:",
        f"files={len(files)}",
        f"unresolved_total={unresolved_total}",
        f"policy_violations_total={violations_total}",
    )

    if args.strict and (unresolved_total > 0 or violations_total > 0):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
