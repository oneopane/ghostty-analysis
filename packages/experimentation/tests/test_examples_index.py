from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from experimentation.examples_index import index_run


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, sort_keys=True, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )


def test_examples_index_indexes_per_pr_rows(tmp_path: Path) -> None:
    repo = "acme/widgets"
    run_id = "run-x"
    data_dir = tmp_path / "data"
    run_dir = data_dir / "github" / "acme" / "widgets" / "eval" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    _write_json(
        run_dir / "run_summary.json",
        {
            "schema_version": 1,
            "kind": "run_summary",
            "repo": repo,
            "run_id": run_id,
            "generated_at": "2024-01-01T00:00:00Z",
            "watermark": {},
            "inputs": {
                "cohort_hash": None,
                "experiment_spec_hash": None,
                "routers": [],
            },
            "counts": {"pr_count": 1, "per_pr_row_count": 1},
            "artifacts": {"per_pr_jsonl": "per_pr.jsonl", "report_json": "report.json"},
            "hashes": {},
            "headline_metrics": {},
            "gates": {"truth_coverage_counts": {}, "warnings": []},
            "drill": {"prs_dir": "prs"},
        },
    )

    (run_dir / "report.json").write_text("{}\n", encoding="utf-8")
    (run_dir / "per_pr.jsonl").write_text(
        json.dumps(
            {
                "repo": repo,
                "run_id": run_id,
                "pr_number": 17,
                "cutoff": "2024-01-01T00:00:00Z",
                "truth_status": "observed",
                "truth": {"primary_policy": "first_approval_v1", "policies": {}},
                "gates": {
                    "missing_issue": False,
                    "missing_ai_disclosure": True,
                    "missing_provenance": None,
                    "merged": True,
                },
                "routers": {"mentions": {}, "popularity": {}},
                "repo_profile": {
                    "profile_path": "prs/17/repo_profile/profile.json",
                    "qa_path": "prs/17/repo_profile/qa.json",
                },
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    sqlite_path, indexed_n = index_run(
        repo=repo,
        run_id=run_id,
        data_dir=str(data_dir),
        run_dir=run_dir,
    )
    assert indexed_n == 1
    assert sqlite_path.exists()

    conn = sqlite3.connect(str(sqlite_path))
    try:
        cur = conn.execute(
            "select truth_status, missing_issue, missing_ai_disclosure, missing_provenance, merged, routers_json "
            "from examples where repo = ? and run_id = ? and pr_number = ?",
            (repo, run_id, 17),
        )
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "observed"
        assert row[1] == 0
        assert row[2] == 1
        assert row[3] is None
        assert row[4] == 1
        assert json.loads(row[5]) == ["mentions", "popularity"]
    finally:
        conn.close()
