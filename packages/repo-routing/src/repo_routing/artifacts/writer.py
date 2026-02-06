from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from ..history.reader import HistoryReader
from ..inputs.builder import build_pr_input_bundle
from ..inputs.models import PRInputBuilderOptions, PRInputBundle
from ..paths import repo_db_path
from ..registry import RouterSpec, load_router
from ..router.base import RouteResult
from ..time import dt_sql_utc, parse_dt_utc, require_dt_utc
from .models import PRSnapshotArtifact, RouteArtifact
from .paths import (
    pr_features_path,
    pr_inputs_path,
    pr_llm_step_path,
    pr_route_result_path,
    pr_snapshot_path,
)


def _write_json_deterministic(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(
        obj,
        sort_keys=True,
        indent=2,
        ensure_ascii=True,
    )
    path.write_text(data + "\n", encoding="utf-8")


@dataclass(frozen=True)
class ArtifactWriter:
    repo: str
    data_dir: str | Path = "data"
    run_id: str = "run"

    def pr_snapshot_path(self, *, pr_number: int) -> Path:
        return pr_snapshot_path(
            repo_full_name=self.repo,
            data_dir=self.data_dir,
            run_id=self.run_id,
            pr_number=pr_number,
        )

    def pr_inputs_path(self, *, pr_number: int) -> Path:
        return pr_inputs_path(
            repo_full_name=self.repo,
            data_dir=self.data_dir,
            run_id=self.run_id,
            pr_number=pr_number,
        )

    def route_result_path(self, *, pr_number: int, baseline: str) -> Path:
        return pr_route_result_path(
            repo_full_name=self.repo,
            data_dir=self.data_dir,
            run_id=self.run_id,
            pr_number=pr_number,
            baseline=baseline,
        )

    def features_path(self, *, pr_number: int, router_id: str) -> Path:
        return pr_features_path(
            repo_full_name=self.repo,
            data_dir=self.data_dir,
            run_id=self.run_id,
            pr_number=pr_number,
            router_id=router_id,
        )

    def llm_step_path(self, *, pr_number: int, router_id: str, step: str) -> Path:
        return pr_llm_step_path(
            repo_full_name=self.repo,
            data_dir=self.data_dir,
            run_id=self.run_id,
            pr_number=pr_number,
            router_id=router_id,
            step=step,
        )

    def write_pr_snapshot(self, artifact: PRSnapshotArtifact) -> Path:
        p = self.pr_snapshot_path(pr_number=artifact.pr_number)
        _write_json_deterministic(p, artifact.model_dump(mode="json"))
        return p

    def write_pr_inputs(self, bundle: PRInputBundle) -> Path:
        p = self.pr_inputs_path(pr_number=bundle.pr_number)
        _write_json_deterministic(p, bundle.model_dump(mode="json"))
        return p

    def write_features(
        self, *, pr_number: int, router_id: str, features: dict[str, object]
    ) -> Path:
        p = self.features_path(pr_number=pr_number, router_id=router_id)
        _write_json_deterministic(p, features)
        return p

    def write_llm_step(
        self,
        *,
        pr_number: int,
        router_id: str,
        step: str,
        payload: dict[str, object],
    ) -> Path:
        p = self.llm_step_path(pr_number=pr_number, router_id=router_id, step=step)
        _write_json_deterministic(p, payload)
        return p

    def write_route_result(self, artifact: RouteArtifact) -> Path:
        p = self.route_result_path(
            pr_number=artifact.result.pr_number, baseline=artifact.baseline
        )
        _write_json_deterministic(p, artifact.model_dump(mode="json"))
        return p


def build_pr_snapshot_artifact(
    *, repo: str, pr_number: int, as_of: datetime, data_dir: str | Path = "data"
) -> PRSnapshotArtifact:
    as_of_utc = require_dt_utc(as_of, name="as_of")
    with HistoryReader(repo_full_name=repo, data_dir=data_dir) as reader:
        pr = reader.pull_request_snapshot(number=pr_number, as_of=as_of_utc)

    changed_files = sorted(pr.changed_files, key=lambda f: f.path)
    review_requests = sorted(
        pr.review_requests,
        key=lambda rr: (rr.reviewer_type, rr.reviewer.lower()),
    )
    return PRSnapshotArtifact(
        repo=repo,
        pr_number=pr_number,
        as_of=as_of_utc,
        author=pr.author_login,
        title=pr.title,
        body=pr.body,
        base_sha=pr.base_sha,
        head_sha=pr.head_sha,
        changed_files=changed_files,
        review_requests=review_requests,
    )


def build_pr_inputs_artifact(
    *,
    repo: str,
    pr_number: int,
    as_of: datetime,
    data_dir: str | Path = "data",
    options: PRInputBuilderOptions | None = None,
) -> PRInputBundle:
    return build_pr_input_bundle(
        repo=repo,
        pr_number=pr_number,
        cutoff=as_of,
        data_dir=data_dir,
        options=options,
    )


def build_route_result(
    *,
    baseline: str | None = None,
    router_spec: RouterSpec | None = None,
    repo: str,
    pr_number: int,
    as_of: datetime,
    data_dir: str | Path = "data",
    top_k: int = 5,
    config_path: str | Path | None = None,
) -> RouteResult:
    spec = router_spec
    if spec is None:
        if baseline is None:
            raise ValueError("baseline or router_spec is required")
        spec = RouterSpec(
            type="builtin",
            name=baseline,
            config_path=None if config_path is None else str(config_path),
        )

    router = load_router(spec)
    return router.route(
        repo=repo,
        pr_number=pr_number,
        as_of=require_dt_utc(as_of, name="as_of"),
        data_dir=str(data_dir),
        top_k=top_k,
    )


def build_route_artifact(
    *,
    baseline: str,
    repo: str,
    pr_number: int,
    as_of: datetime,
    data_dir: str | Path = "data",
    top_k: int = 5,
    config_path: str | Path | None = None,
) -> RouteArtifact:
    result = build_route_result(
        baseline=baseline,
        repo=repo,
        pr_number=pr_number,
        as_of=as_of,
        data_dir=data_dir,
        top_k=top_k,
        config_path=config_path,
    )
    return RouteArtifact(baseline=baseline, result=result)


def iter_pr_numbers_created_in_window(
    *,
    repo: str,
    data_dir: str | Path,
    start_at: datetime | None,
    end_at: datetime | None,
) -> Iterable[int]:
    db_path = repo_db_path(repo_full_name=repo, data_dir=data_dir)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "select id from repos where full_name = ?", (repo,)
        ).fetchone()
        if row is None:
            raise KeyError(f"repo not found in db: {repo}")
        repo_id = int(row["id"])

        where = ["repo_id = ?", "created_at is not null"]
        params: list[object] = [repo_id]
        if start_at is not None:
            where.append("created_at >= ?")
            params.append(dt_sql_utc(start_at))
        if end_at is not None:
            where.append("created_at <= ?")
            params.append(dt_sql_utc(end_at))

        sql = (
            "select number from pull_requests where "
            + " and ".join(where)
            + " order by created_at asc, number asc"
        )
        for r in conn.execute(sql, tuple(params)):
            yield int(r["number"])
    finally:
        conn.close()


def pr_created_at(
    *, repo: str, data_dir: str | Path, pr_number: int
) -> datetime | None:
    db_path = repo_db_path(repo_full_name=repo, data_dir=data_dir)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "select id from repos where full_name = ?", (repo,)
        ).fetchone()
        if row is None:
            raise KeyError(f"repo not found in db: {repo}")
        repo_id = int(row["id"])
        pr = conn.execute(
            "select created_at from pull_requests where repo_id = ? and number = ?",
            (repo_id, pr_number),
        ).fetchone()
        if pr is None:
            raise KeyError(f"pr not found: {repo}#{pr_number}")
        return parse_dt_utc(pr["created_at"])
    finally:
        conn.close()
