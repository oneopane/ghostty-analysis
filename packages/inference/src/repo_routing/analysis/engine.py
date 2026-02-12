from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

from ..exports.area import AreaOverride, area_for_path, load_repo_area_overrides
from ..history.reader import HistoryReader
from ..parsing.gates import GateFields, parse_gate_fields
from ..paths import repo_db_path
from ..router.base import Evidence
from ..time import dt_sql_utc, parse_dt_utc, require_dt_utc
from ..scoring import (
    confidence_from_scores,
    decay_weight,
    linear_score,
    load_scoring_config,
    risk_from_inputs,
)
from ..scoring.config import ScoringConfig
from .models import AnalysisResult, CandidateAnalysis, CandidateFeatures


def _is_bot_login(login: str) -> bool:
    return login.lower().endswith("[bot]")


@dataclass(frozen=True)
class ActivityEvent:
    login: str
    occurred_at: datetime
    kind: str
    pr_id: int


def _candidate_pool(
    *,
    conn: sqlite3.Connection,
    repo_id: int,
    cutoff: datetime,
    lookback_days: int,
    exclude_bots: bool,
    exclude_author: bool,
    author_login: str | None,
) -> list[str]:
    start = cutoff - timedelta(days=lookback_days)
    start_s = dt_sql_utc(start, timespec="microseconds")
    cutoff_s = dt_sql_utc(cutoff, timespec="microseconds")

    rows = conn.execute(
        """
        select distinct u.login as login, u.type as type
        from comments c
        join users u on u.id = c.user_id
        where c.repo_id = ?
          and c.pull_request_id is not null
          and c.created_at is not null
          and c.created_at >= ?
          and c.created_at <= ?
          and u.login is not null
        union
        select distinct u.login as login, u.type as type
        from reviews r
        join users u on u.id = r.user_id
        where r.repo_id = ?
          and r.submitted_at is not null
          and r.submitted_at >= ?
          and r.submitted_at <= ?
          and u.login is not null
        """,
        (repo_id, start_s, cutoff_s, repo_id, start_s, cutoff_s),
    ).fetchall()

    author_login_l = author_login.lower() if author_login else None
    out: list[str] = []
    for r in rows:
        login = str(r["login"])
        if exclude_bots and (r["type"] == "Bot" or _is_bot_login(login)):
            continue
        if exclude_author and author_login_l and login.lower() == author_login_l:
            continue
        out.append(login)

    return sorted(set(out), key=lambda s: s.lower())


def _activity_events(
    *,
    conn: sqlite3.Connection,
    repo_id: int,
    cutoff: datetime,
    lookback_days: int,
) -> list[ActivityEvent]:
    start = cutoff - timedelta(days=lookback_days)
    start_s = dt_sql_utc(start, timespec="microseconds")
    cutoff_s = dt_sql_utc(cutoff, timespec="microseconds")

    events: list[ActivityEvent] = []

    review_rows = conn.execute(
        """
        select r.pull_request_id as pr_id,
               r.submitted_at as occurred_at,
               u.login as login
        from reviews r
        join users u on u.id = r.user_id
        where r.repo_id = ?
          and r.submitted_at is not null
          and r.submitted_at >= ?
          and r.submitted_at <= ?
          and u.login is not null
        """,
        (repo_id, start_s, cutoff_s),
    ).fetchall()
    for r in review_rows:
        occurred_at = parse_dt_utc(r["occurred_at"])
        if occurred_at is None:
            continue
        events.append(
            ActivityEvent(
                login=str(r["login"]),
                occurred_at=occurred_at,
                kind="review_submitted",
                pr_id=int(r["pr_id"]),
            )
        )

    comment_rows = conn.execute(
        """
        select c.pull_request_id as pr_id,
               c.created_at as occurred_at,
               c.comment_type as comment_type,
               c.review_id as review_id,
               u.login as login
        from comments c
        join users u on u.id = c.user_id
        where c.repo_id = ?
          and c.pull_request_id is not null
          and c.created_at is not null
          and c.created_at >= ?
          and c.created_at <= ?
          and u.login is not null
        """,
        (repo_id, start_s, cutoff_s),
    ).fetchall()
    for r in comment_rows:
        occurred_at = parse_dt_utc(r["occurred_at"])
        if occurred_at is None:
            continue
        comment_type = r["comment_type"]
        kind = "comment_created"
        if comment_type == "review" or r["review_id"] is not None:
            kind = "review_comment_created"
        events.append(
            ActivityEvent(
                login=str(r["login"]),
                occurred_at=occurred_at,
                kind=kind,
                pr_id=int(r["pr_id"]),
            )
        )

    events.sort(
        key=lambda e: (e.occurred_at, e.pr_id, e.login.lower(), e.kind)
    )
    return events


def _pr_head_sha_as_of(
    *, conn: sqlite3.Connection, pr_id: int, as_of: datetime
) -> str | None:
    as_of_s = dt_sql_utc(as_of, timespec="microseconds")
    row = conn.execute(
        """
        select phi.head_sha as head_sha
        from pull_request_head_intervals phi
        join events se on se.id = phi.start_event_id
        left join events ee on ee.id = phi.end_event_id
        where phi.pull_request_id = ?
          and se.occurred_at <= ?
          and (ee.id is null or ? < ee.occurred_at)
        order by se.occurred_at desc, se.id desc
        limit 1
        """,
        (pr_id, as_of_s, as_of_s),
    ).fetchone()
    return None if row is None else row["head_sha"]


def _pr_areas_for_event(
    *,
    conn: sqlite3.Connection,
    repo_id: int,
    pr_id: int,
    occurred_at: datetime,
    overrides: list[AreaOverride],
    cache: dict[tuple[int, str | None], list[str]],
) -> list[str]:
    head_sha = _pr_head_sha_as_of(conn=conn, pr_id=pr_id, as_of=occurred_at)
    cache_key = (pr_id, head_sha)
    if cache_key in cache:
        return cache[cache_key]
    if head_sha is None:
        cache[cache_key] = []
        return []

    rows = conn.execute(
        """
        select path from pull_request_files
        where repo_id = ? and pull_request_id = ? and head_sha = ?
        order by path asc
        """,
        (repo_id, pr_id, head_sha),
    ).fetchall()
    areas: list[str] = []
    for r in rows:
        areas.append(area_for_path(str(r["path"]), overrides))
    unique = sorted(set(areas), key=lambda s: s.lower())
    cache[cache_key] = unique
    return unique


def _current_pr_areas(
    snapshot_paths: Iterable[str], overrides: list[AreaOverride]
) -> list[str]:
    areas = [area_for_path(path, overrides) for path in snapshot_paths]
    return sorted(set(areas), key=lambda s: s.lower())


def _build_evidence(
    *,
    features: CandidateFeatures,
    config: ScoringConfig,
    overlap: bool,
) -> list[Evidence]:
    return [
        Evidence(
            kind="activity_totals",
            data={
                "activity_total": features.activity_total,
            },
        ),
        Evidence(
            kind="area_overlap",
            data={
                "area_overlap_activity": features.area_overlap_activity,
                "overlap": overlap,
            },
        ),
        Evidence(
            kind="decay_params",
            data={
                "half_life_days": config.decay.half_life_days,
                "lookback_days": config.decay.lookback_days,
                "event_weights": config.event_weights.model_dump(mode="json"),
            },
        ),
        Evidence(
            kind="filters_applied",
            data={
                "min_activity_total": config.filters.min_activity_total,
            },
        ),
    ]


def analyze_pr(
    *,
    repo: str,
    pr_number: int,
    cutoff: datetime,
    data_dir: str | Path = "data",
    config_path: str | Path,
) -> AnalysisResult:
    cutoff_utc = require_dt_utc(cutoff, name="cutoff")
    config = load_scoring_config(config_path)
    overrides = load_repo_area_overrides(repo_full_name=repo, data_dir=data_dir)

    with HistoryReader(repo_full_name=repo, data_dir=data_dir) as reader:
        snapshot = reader.pull_request_snapshot(number=pr_number, as_of=cutoff_utc)

    gates = parse_gate_fields(snapshot.body)
    current_paths = [f.path for f in snapshot.changed_files]
    areas = _current_pr_areas(current_paths, overrides)

    db = repo_db_path(repo_full_name=repo, data_dir=data_dir)
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "select id from repos where full_name = ?", (repo,)
        ).fetchone()
        if row is None:
            raise KeyError(f"repo not found in db: {repo}")
        repo_id = int(row["id"])

        candidates = _candidate_pool(
            conn=conn,
            repo_id=repo_id,
            cutoff=cutoff_utc,
            lookback_days=config.candidate_pool.lookback_days,
            exclude_bots=config.candidate_pool.exclude_bots,
            exclude_author=config.candidate_pool.exclude_author,
            author_login=snapshot.author_login,
        )

        events = _activity_events(
            conn=conn,
            repo_id=repo_id,
            cutoff=cutoff_utc,
            lookback_days=config.decay.lookback_days,
        )

        event_weights = config.event_weights.model_dump()
        by_login: dict[str, CandidateFeatures] = {}
        overlap_cache: dict[tuple[int, str | None], list[str]] = {}

        for event in events:
            if event.login not in candidates:
                continue
            weight = float(event_weights.get(event.kind, 0.0))
            if weight == 0.0:
                continue
            age_days = (cutoff_utc - event.occurred_at).total_seconds() / 86400.0
            if age_days < 0:
                continue
            if age_days > config.decay.lookback_days:
                continue
            decayed = weight * decay_weight(age_days, config.decay.half_life_days)
            feats = by_login.setdefault(event.login, CandidateFeatures())
            feats.activity_total += decayed

            if areas:
                event_areas = _pr_areas_for_event(
                    conn=conn,
                    repo_id=repo_id,
                    pr_id=event.pr_id,
                    occurred_at=event.occurred_at,
                    overrides=overrides,
                    cache=overlap_cache,
                )
                if set(event_areas).intersection(areas):
                    feats.area_overlap_activity += decayed
    finally:
        conn.close()

    analyses: list[CandidateAnalysis] = []
    for login in candidates:
        feats = by_login.get(login, CandidateFeatures())
        if feats.activity_total < config.filters.min_activity_total:
            continue
        score = linear_score(
            {"activity_total": feats.activity_total, "area_overlap_activity": feats.area_overlap_activity},
            config.weights.model_dump(),
        )
        analyses.append(
            CandidateAnalysis(
                login=login,
                score=score,
                features=feats,
                evidence=_build_evidence(
                    features=feats,
                    config=config,
                    overlap=feats.area_overlap_activity > 0,
                ),
            )
        )

    analyses.sort(key=lambda c: (-c.score, c.login.lower()))
    scores = [c.score for c in analyses]
    confidence = confidence_from_scores(scores, config.thresholds)
    risk = risk_from_inputs(gates=gates, areas=areas, has_candidates=bool(analyses))

    return AnalysisResult(
        repo=repo,
        pr_number=pr_number,
        cutoff=cutoff_utc,
        author_login=snapshot.author_login,
        areas=areas,
        gates=gates,
        candidates=analyses,
        confidence=confidence,
        risk=risk,
        config_version=config.version,
        feature_version=config.feature_version,
    )
