from __future__ import annotations


def backfill_semantic_artifacts(
    *,
    repo: str,
    prompt_id: str,
    since: str,
    data_dir: str = "data",
    dry_run: bool = False,
) -> dict[str, object]:
    return {
        "repo": repo,
        "prompt_id": prompt_id,
        "since": since,
        "dry_run": dry_run,
        "would_compute": 0,
        "computed": 0,
        "cache_hits": 0,
    }
