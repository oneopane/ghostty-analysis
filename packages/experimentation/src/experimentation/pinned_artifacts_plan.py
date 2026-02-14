from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from repo_routing.api import CODEOWNERS_PATH_CANDIDATES, pinned_artifact_path


def _stable_hash(obj: object) -> str:
    data = json.dumps(obj, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_relpath(path: Path, *, data_dir: str) -> str:
    try:
        return path.relative_to(Path(data_dir)).as_posix()
    except Exception:
        return path.as_posix()


def build_pinned_artifacts_plan(
    *,
    repo: str,
    data_dir: str,
    pr_base_shas: dict[str, str | None],
    artifact_paths: list[str],
    cohort_hash: str | None,
    cohort_path: str | None,
    doctor_id: str | None,
) -> dict[str, Any]:
    pr_numbers = sorted([int(k) for k in pr_base_shas.keys() if str(k).isdigit()])

    base_sha_to_prs: dict[str, list[int]] = {}
    missing_base_sha_prs: list[int] = []
    for pr in pr_numbers:
        base_sha = pr_base_shas.get(str(pr))
        if not base_sha:
            missing_base_sha_prs.append(pr)
            continue
        base_sha_to_prs.setdefault(str(base_sha), []).append(pr)

    base_shas = sorted(base_sha_to_prs.keys())
    artifact_paths_clean = [str(p) for p in artifact_paths if str(p).strip()]
    artifact_paths_clean = sorted(set(artifact_paths_clean), key=lambda s: s.lower())
    codeowners_candidates = list(CODEOWNERS_PATH_CANDIDATES)

    by_base_sha: list[dict[str, object]] = []
    path_pr_present: dict[str, int] = {p: 0 for p in artifact_paths_clean}
    path_pr_missing: dict[str, int] = {p: 0 for p in artifact_paths_clean}
    codeowners_present_prs = 0
    codeowners_missing_prs = 0

    for base_sha in base_shas:
        prs = sorted(base_sha_to_prs.get(base_sha) or [])
        present_paths: list[str] = []
        missing_paths: list[str] = []
        present_by_path: dict[str, str] = {}

        for rel in artifact_paths_clean:
            p = pinned_artifact_path(
                repo_full_name=repo,
                base_sha=base_sha,
                relative_path=rel,
                data_dir=data_dir,
            )
            if p.exists():
                present_paths.append(rel)
                present_by_path[rel] = _safe_relpath(p, data_dir=data_dir)
                path_pr_present[rel] += len(prs)
            else:
                missing_paths.append(rel)
                path_pr_missing[rel] += len(prs)

        codeowners_found_path: str | None = None
        for rel in codeowners_candidates:
            p = pinned_artifact_path(
                repo_full_name=repo,
                base_sha=base_sha,
                relative_path=rel,
                data_dir=data_dir,
            )
            if p.exists():
                codeowners_found_path = rel
                break

        codeowners_present = codeowners_found_path is not None
        if codeowners_present:
            codeowners_present_prs += len(prs)
        else:
            codeowners_missing_prs += len(prs)

        by_base_sha.append(
            {
                "base_sha": base_sha,
                "pr_numbers": prs,
                "present_paths": present_paths,
                "missing_paths": missing_paths,
                "present_by_path": {
                    k: present_by_path[k]
                    for k in sorted(present_by_path.keys(), key=lambda s: s.lower())
                },
                "counts": {
                    "pr_count": int(len(prs)),
                    "present_path_count": int(len(present_paths)),
                    "missing_path_count": int(len(missing_paths)),
                },
                "codeowners": {
                    "present": bool(codeowners_present),
                    "found_path": codeowners_found_path,
                },
            }
        )

    pr_count_total = len(pr_numbers)
    base_sha_count = len(base_shas)

    coverage_by_path: list[dict[str, object]] = []
    for rel in artifact_paths_clean:
        present_prs = int(path_pr_present.get(rel, 0))
        missing_prs = int(path_pr_missing.get(rel, 0))
        denom = present_prs + missing_prs
        present_rate = float(present_prs) / float(denom) if denom > 0 else 0.0
        coverage_by_path.append(
            {
                "path": rel,
                "present_pr_count": present_prs,
                "missing_pr_count": missing_prs,
                "present_rate": present_rate,
            }
        )
    coverage_by_path.sort(
        key=lambda r: (
            float(r.get("present_rate") or 0.0),
            str(r.get("path") or "").lower(),
        )
    )

    plan_id = _stable_hash(
        {
            "repo": repo,
            "data_dir": str(data_dir),
            "doctor_id": doctor_id,
            "cohort_hash": cohort_hash,
            "artifact_paths": artifact_paths_clean,
            "base_shas": base_shas,
            "pr_base_shas": {
                str(k): pr_base_shas.get(str(k))
                for k in sorted(pr_base_shas.keys(), key=int)
            },
        }
    )

    return {
        "schema_version": 1,
        "kind": "pinned_artifacts_plan",
        "plan_id": plan_id,
        "generated_at": _now_iso_utc(),
        "repo": repo,
        "data_dir": str(data_dir),
        "doctor_id": doctor_id,
        "cohort": {
            "hash": cohort_hash,
            "path": cohort_path,
        },
        "requested": {
            "artifact_paths": artifact_paths_clean,
            "codeowners_candidates": codeowners_candidates,
        },
        "counts": {
            "pr_count": int(pr_count_total),
            "unique_base_sha_count": int(base_sha_count),
            "missing_base_sha_pr_count": int(len(missing_base_sha_prs)),
            "codeowners_present_pr_count": int(codeowners_present_prs),
            "codeowners_missing_pr_count": int(codeowners_missing_prs),
        },
        "coverage_by_path": coverage_by_path,
        "by_base_sha": by_base_sha,
    }


__all__ = ["build_pinned_artifacts_plan"]
