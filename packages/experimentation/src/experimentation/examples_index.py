from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from evaluation_harness.paths import repo_eval_run_dir


SCHEMA_VERSION = 1


def examples_index_sqlite_path(*, repo: str, data_dir: str) -> Path:
    owner, name = repo.split("/", 1)
    return Path(data_dir) / "github" / owner / name / "examples_index.sqlite"


def _json_compact(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def _bool_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, (int, float)):
        return 1 if bool(value) else 0
    s = str(value).strip().lower()
    if s in {"true", "yes", "1"}:
        return 1
    if s in {"false", "no", "0"}:
        return 0
    return None


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return raw if isinstance(raw, dict) else None


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute("pragma foreign_keys = on")
    conn.execute(f"pragma user_version = {SCHEMA_VERSION}")

    conn.executescript(
        """
        create table if not exists meta (
          key text primary key,
          value text not null
        );

        create table if not exists runs (
          repo text not null,
          run_id text not null,
          run_dir_rel text not null,
          generated_at text,
          cohort_hash text,
          experiment_spec_hash text,
          db_max_event_occurred_at text,
          db_max_watermark_updated_at text,
          manifest_json_sha256 text,
          report_json_sha256 text,
          per_pr_jsonl_sha256 text,
          primary key (repo, run_id)
        );

        create table if not exists examples (
          repo text not null,
          run_id text not null,
          pr_number integer not null,
          cutoff text,
          truth_status text,
          missing_issue integer,
          missing_ai_disclosure integer,
          missing_provenance integer,
          merged integer,
          primary_policy text,
          routers_json text,
          artifact_paths_json text,
          indexed_at text,
          primary key (repo, run_id, pr_number),
          foreign key (repo, run_id) references runs(repo, run_id) on delete cascade
        );

        create index if not exists idx_examples_repo_pr on examples(repo, pr_number);
        create index if not exists idx_examples_repo_truth_status on examples(repo, truth_status);
        create index if not exists idx_examples_repo_missing_issue on examples(repo, missing_issue);
        """
    )

    conn.execute(
        "insert into meta (key, value) values (?, ?) on conflict(key) do update set value=excluded.value",
        ("schema_version", str(SCHEMA_VERSION)),
    )


def index_run(
    *,
    repo: str,
    run_id: str,
    data_dir: str,
    run_dir: Path | None = None,
    sqlite_path: Path | None = None,
) -> tuple[Path, int]:
    """Index one eval run into examples_index.sqlite.

    - Offline: reads only filesystem artifacts.
    - Idempotent: upserts run + (repo, run_id, pr_number) rows.
    """

    if run_dir is None:
        run_dir = repo_eval_run_dir(
            repo_full_name=repo, data_dir=data_dir, run_id=run_id
        )
    if sqlite_path is None:
        sqlite_path = examples_index_sqlite_path(repo=repo, data_dir=data_dir)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)

    run_summary = _read_json(run_dir / "run_summary.json") or {}
    manifest = _read_json(run_dir / "manifest.json") or {}
    report = _read_json(run_dir / "report.json") or {}
    exp_manifest = _read_json(run_dir / "experiment_manifest.json") or {}

    watermark = (
        run_summary.get("watermark")
        if isinstance(run_summary.get("watermark"), dict)
        else {}
    )
    hashes = (
        run_summary.get("hashes") if isinstance(run_summary.get("hashes"), dict) else {}
    )
    inputs = (
        run_summary.get("inputs") if isinstance(run_summary.get("inputs"), dict) else {}
    )

    generated_at = run_summary.get("generated_at")
    if not isinstance(generated_at, str) or not generated_at.strip():
        generated_at = manifest.get("generated_at")
    if not isinstance(generated_at, str) or not generated_at.strip():
        generated_at = report.get("generated_at")
    generated_at_out = (
        str(generated_at)
        if isinstance(generated_at, str) and generated_at.strip()
        else None
    )

    cohort_hash = inputs.get("cohort_hash")
    if not isinstance(cohort_hash, str) or not cohort_hash.strip():
        cohort_hash = exp_manifest.get("cohort_hash")
    cohort_hash_out = (
        str(cohort_hash)
        if isinstance(cohort_hash, str) and cohort_hash.strip()
        else None
    )

    spec_hash = inputs.get("experiment_spec_hash")
    if not isinstance(spec_hash, str) or not spec_hash.strip():
        spec_hash = exp_manifest.get("experiment_spec_hash")
    spec_hash_out = (
        str(spec_hash) if isinstance(spec_hash, str) and spec_hash.strip() else None
    )

    def _get_str(d: dict[str, Any], key: str) -> str | None:
        v = d.get(key)
        return str(v) if isinstance(v, str) and v.strip() else None

    db_max_event = _get_str(watermark, "db_max_event_occurred_at")
    if db_max_event is None:
        db_max_event = _get_str(manifest, "db_max_event_occurred_at")
    if db_max_event is None:
        db_max_event = _get_str(report, "db_max_event_occurred_at")

    db_max_watermark = _get_str(watermark, "db_max_watermark_updated_at")
    if db_max_watermark is None:
        db_max_watermark = _get_str(manifest, "db_max_watermark_updated_at")
    if db_max_watermark is None:
        db_max_watermark = _get_str(report, "db_max_watermark_updated_at")

    manifest_sha = _get_str(hashes, "manifest_json_sha256")
    report_sha = _get_str(hashes, "report_json_sha256")
    per_pr_sha = _get_str(hashes, "per_pr_jsonl_sha256")

    run_dir_rel: str
    try:
        run_dir_rel = run_dir.relative_to(Path(data_dir)).as_posix()
    except Exception:
        run_dir_rel = run_dir.as_posix()

    per_pr_path = run_dir / "per_pr.jsonl"
    rows: list[dict[str, Any]] = []
    if per_pr_path.exists():
        with per_pr_path.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if isinstance(obj, dict):
                    rows.append(obj)

    indexed_at = generated_at_out

    with sqlite3.connect(str(sqlite_path)) as conn:
        _ensure_schema(conn)

        conn.execute(
            """
            insert into runs (
              repo, run_id, run_dir_rel, generated_at,
              cohort_hash, experiment_spec_hash,
              db_max_event_occurred_at, db_max_watermark_updated_at,
              manifest_json_sha256, report_json_sha256, per_pr_jsonl_sha256
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            on conflict(repo, run_id) do update set
              run_dir_rel=excluded.run_dir_rel,
              generated_at=excluded.generated_at,
              cohort_hash=excluded.cohort_hash,
              experiment_spec_hash=excluded.experiment_spec_hash,
              db_max_event_occurred_at=excluded.db_max_event_occurred_at,
              db_max_watermark_updated_at=excluded.db_max_watermark_updated_at,
              manifest_json_sha256=excluded.manifest_json_sha256,
              report_json_sha256=excluded.report_json_sha256,
              per_pr_jsonl_sha256=excluded.per_pr_jsonl_sha256
            """,
            (
                repo,
                run_id,
                run_dir_rel,
                generated_at_out,
                cohort_hash_out,
                spec_hash_out,
                db_max_event,
                db_max_watermark,
                manifest_sha,
                report_sha,
                per_pr_sha,
            ),
        )

        # Upsert per-PR rows.
        indexed_n = 0
        for row in sorted(rows, key=lambda r: int(r.get("pr_number") or -1)):
            pr_number = row.get("pr_number")
            if not isinstance(pr_number, int):
                continue
            cutoff = row.get("cutoff")
            cutoff_out = (
                str(cutoff) if isinstance(cutoff, str) and cutoff.strip() else None
            )

            truth_status = row.get("truth_status")
            truth_status_out = (
                str(truth_status)
                if isinstance(truth_status, str) and truth_status.strip()
                else None
            )

            gates = row.get("gates") if isinstance(row.get("gates"), dict) else {}
            missing_issue = _bool_int(gates.get("missing_issue"))
            missing_ai = _bool_int(gates.get("missing_ai_disclosure"))
            missing_prov = _bool_int(gates.get("missing_provenance"))
            merged = _bool_int(gates.get("merged"))

            primary_policy = None
            truth = row.get("truth") if isinstance(row.get("truth"), dict) else {}
            raw_policy = truth.get("primary_policy")
            if isinstance(raw_policy, str) and raw_policy.strip():
                primary_policy = raw_policy.strip()

            routers_payload = (
                row.get("routers") if isinstance(row.get("routers"), dict) else {}
            )
            router_ids = sorted(
                [str(k) for k in routers_payload.keys()], key=lambda s: s.lower()
            )

            pr_dir = f"prs/{pr_number}"
            artifact_paths = {
                "pr_dir": pr_dir,
                "snapshot_json": f"{pr_dir}/snapshot.json",
                "inputs_json": f"{pr_dir}/inputs.json",
                "routes_by_router": {
                    rid: f"{pr_dir}/routes/{rid}.json" for rid in router_ids
                },
            }
            repo_profile = (
                row.get("repo_profile")
                if isinstance(row.get("repo_profile"), dict)
                else {}
            )
            profile_path = repo_profile.get("profile_path")
            qa_path = repo_profile.get("qa_path")
            if isinstance(profile_path, str) and profile_path.strip():
                artifact_paths["repo_profile_profile_json"] = profile_path
            else:
                expected = run_dir / pr_dir / "repo_profile" / "profile.json"
                if expected.exists():
                    artifact_paths["repo_profile_profile_json"] = (
                        f"{pr_dir}/repo_profile/profile.json"
                    )
            if isinstance(qa_path, str) and qa_path.strip():
                artifact_paths["repo_profile_qa_json"] = qa_path
            else:
                expected = run_dir / pr_dir / "repo_profile" / "qa.json"
                if expected.exists():
                    artifact_paths["repo_profile_qa_json"] = (
                        f"{pr_dir}/repo_profile/qa.json"
                    )

            conn.execute(
                """
                insert into examples (
                  repo, run_id, pr_number,
                  cutoff, truth_status,
                  missing_issue, missing_ai_disclosure, missing_provenance,
                  merged, primary_policy,
                  routers_json, artifact_paths_json,
                  indexed_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(repo, run_id, pr_number) do update set
                  cutoff=excluded.cutoff,
                  truth_status=excluded.truth_status,
                  missing_issue=excluded.missing_issue,
                  missing_ai_disclosure=excluded.missing_ai_disclosure,
                  missing_provenance=excluded.missing_provenance,
                  merged=excluded.merged,
                  primary_policy=excluded.primary_policy,
                  routers_json=excluded.routers_json,
                  artifact_paths_json=excluded.artifact_paths_json,
                  indexed_at=excluded.indexed_at
                """,
                (
                    repo,
                    run_id,
                    int(pr_number),
                    cutoff_out,
                    truth_status_out,
                    missing_issue,
                    missing_ai,
                    missing_prov,
                    merged,
                    primary_policy,
                    _json_compact(router_ids),
                    _json_compact(artifact_paths),
                    indexed_at,
                ),
            )
            indexed_n += 1

    return sqlite_path, indexed_n


__all__ = [
    "examples_index_sqlite_path",
    "index_run",
]
