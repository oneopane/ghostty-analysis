from __future__ import annotations

from pathlib import PurePosixPath
from statistics import median
from typing import Any

from ...inputs.models import PRInputBundle
from .sql import connect_repo_db, cutoff_sql, load_repo_pr_ids


def _dir_depth3(path: str) -> str:
    parts = [p for p in PurePosixPath(path).parts[:-1] if p not in {"", "."}]
    if not parts:
        return "__root__"
    return "/".join(parts[:3])


def _dot_sparse(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    keys = sorted(set(a) & set(b), key=str.lower)
    return float(sum(float(a[k]) * float(b[k]) for k in keys))


def _response_rate_bucket(events_30d: float, events_180d: float) -> str:
    if events_180d <= 0:
        return "none"
    if events_30d >= 10:
        return "high"
    if events_30d >= 3:
        return "medium"
    return "low"


def _author_candidate_social_counts(
    *,
    input: PRInputBundle,
    candidate_login: str,
    data_dir: str,
    lookback_days: int = 180,
) -> tuple[int, int, int, float | None]:
    if not input.author_login:
        return 0, 0, 0, None
    conn = connect_repo_db(repo=input.repo, data_dir=data_dir)
    try:
        ids = load_repo_pr_ids(conn=conn, repo=input.repo, pr_number=input.pr_number)
        # Candidate reviews/comments on PRs authored by current author in lookback.
        row = conn.execute(
            """
            with author_user as (
              select id as author_id from users where lower(login)=lower(?) limit 1
            ),
            cand_user as (
              select id as cand_id from users where lower(login)=lower(?) limit 1
            ),
            author_prs as (
              select pr.id as pr_id
              from pull_requests pr
              join author_user au on au.author_id = pr.user_id
              where pr.repo_id = ?
                and pr.created_at is not null
                and pr.created_at >= datetime(?, ?)
                and pr.created_at <= ?
            )
            select
              (
                select count(*)
                from reviews r
                join cand_user cu on cu.cand_id = r.user_id
                where r.repo_id = ?
                  and r.pull_request_id in (select pr_id from author_prs)
                  and r.submitted_at is not null
                  and r.submitted_at <= ?
              ) as reviews_n,
              (
                select count(*)
                from comments c
                join cand_user cu on cu.cand_id = c.user_id
                where c.repo_id = ?
                  and c.pull_request_id in (select pr_id from author_prs)
                  and c.created_at is not null
                  and c.created_at <= ?
              ) as comments_n
            """,
            (
                input.author_login,
                candidate_login,
                ids.repo_id,
                cutoff_sql(input.cutoff),
                f"-{int(lookback_days)} days",
                cutoff_sql(input.cutoff),
                ids.repo_id,
                cutoff_sql(input.cutoff),
                ids.repo_id,
                cutoff_sql(input.cutoff),
            ),
        ).fetchone()
        if row is None:
            return 0, 0, 0, None
        reviews_n = int(row["reviews_n"] or 0)
        comments_n = int(row["comments_n"] or 0)

        latency_rows = conn.execute(
            """
            with author_user as (
              select id as author_id from users where lower(login)=lower(?) limit 1
            ),
            cand_user as (
              select id as cand_id from users where lower(login)=lower(?) limit 1
            ),
            author_prs as (
              select pr.id as pr_id, pr.created_at as created_at
              from pull_requests pr
              join author_user au on au.author_id = pr.user_id
              where pr.repo_id = ?
                and pr.created_at is not null
                and pr.created_at >= datetime(?, ?)
                and pr.created_at <= ?
            ),
            cand_first as (
              select ap.pr_id as pr_id, min(ts) as first_ts, ap.created_at as created_at
              from author_prs ap
              join (
                select r.pull_request_id as pr_id, r.submitted_at as ts, r.user_id as uid
                from reviews r where r.repo_id = ? and r.submitted_at is not null and r.submitted_at <= ?
                union all
                select c.pull_request_id as pr_id, c.created_at as ts, c.user_id as uid
                from comments c where c.repo_id = ? and c.created_at is not null and c.created_at <= ?
              ) ce on ce.pr_id = ap.pr_id
              join cand_user cu on cu.cand_id = ce.uid
              group by ap.pr_id, ap.created_at
            )
            select created_at, first_ts from cand_first
            order by pr_id asc
            """,
            (
                input.author_login,
                candidate_login,
                ids.repo_id,
                cutoff_sql(input.cutoff),
                f"-{int(lookback_days)} days",
                cutoff_sql(input.cutoff),
                ids.repo_id,
                cutoff_sql(input.cutoff),
                ids.repo_id,
                cutoff_sql(input.cutoff),
            ),
        ).fetchall()
        latencies: list[float] = []
        from ...time import parse_dt_utc

        for r in latency_rows:
            c = parse_dt_utc(r["created_at"])
            f = parse_dt_utc(r["first_ts"])
            if c is None or f is None:
                continue
            latencies.append(max(0.0, (f - c).total_seconds()))

        latency_median = median(latencies) if latencies else None
        return reviews_n + comments_n, reviews_n, comments_n, latency_median
    except Exception:
        return 0, 0, 0, None
    finally:
        conn.close()


def build_interaction_features(
    *,
    input: PRInputBundle,
    pr_features: dict[str, Any],
    candidate_features: dict[str, dict[str, Any]],
    data_dir: str | None = None,
) -> dict[str, dict[str, Any]]:
    """Build deterministic PR x candidate pair features."""

    mention_text = "\n".join([input.title or "", input.body or ""]).lower()
    requested_users = {
        rr.reviewer.lower()
        for rr in input.review_requests
        if rr.reviewer_type.lower() == "user"
    }
    owner_set = {str(x).lower() for x in (pr_features.get("pr.ownership.owner_set") or [])}
    pr_boundaries = {str(x) for x in (pr_features.get("pr.boundary.set") or [])}

    pr_dir_counts: dict[str, int] = {}
    for f in input.changed_files:
        d = _dir_depth3(f.path)
        pr_dir_counts[d] = pr_dir_counts.get(d, 0) + 1
    total_dirs = float(sum(pr_dir_counts.values()))
    pr_dir_scores = {k: (v / total_dirs if total_dirs > 0 else 0.0) for k, v in pr_dir_counts.items()}

    pr_boundary_scores: dict[str, float] = {}
    for _path, weights in sorted(input.file_boundary_weights.items()):
        for boundary_id, weight in sorted(weights.items()):
            pr_boundary_scores[str(boundary_id)] = pr_boundary_scores.get(str(boundary_id), 0.0) + float(weight)
    boundary_total = float(sum(pr_boundary_scores.values()))
    if boundary_total > 0:
        pr_boundary_scores = {
            k: (v / boundary_total) for k, v in sorted(pr_boundary_scores.items(), key=lambda kv: kv[0].lower())
        }

    out: dict[str, dict[str, Any]] = {}

    for login in sorted(candidate_features.keys(), key=lambda s: s.lower()):
        cand = candidate_features[login]
        login_l = login.lower()

        cand_boundary = {
            str(k): float(v)
            for k, v in (cand.get("candidate.footprint.boundary_scores.topN") or {}).items()
        }
        cand_dir = {
            str(k): float(v)
            for k, v in (cand.get("candidate.footprint.dir_depth3_scores.topN") or {}).items()
        }
        cand_boundaries = set(cand_boundary.keys())
        cand_dirs = set(cand_dir.keys())

        boundary_overlap = pr_boundaries & cand_boundaries
        dir_overlap = set(pr_dir_scores.keys()) & cand_dirs

        reviews_180 = float(cand.get("candidate.activity.review_count_180d", 0) or 0)
        comments_180 = float(cand.get("candidate.activity.comment_count_180d", 0) or 0)
        events_30d = float(cand.get("candidate.activity.event_counts_30d", cand.get("cand.activity.events_30d", 0)) or 0)
        events_180d = float(cand.get("candidate.activity.event_counts_180d", cand.get("cand.activity.events_180d", 0)) or 0)

        participating = bool(reviews_180 > 0 or comments_180 > 0)

        social_total = 0
        social_reviews = 0
        social_comments = 0
        social_latency = None
        if data_dir:
            social_total, social_reviews, social_comments, social_latency = _author_candidate_social_counts(
                input=input,
                candidate_login=login,
                data_dir=str(data_dir),
            )

        out[login] = {
            "pair.affinity.boundary_overlap_count": len(boundary_overlap),
            "pair.affinity.boundary_overlap_share": (
                float(len(boundary_overlap)) / float(len(pr_boundaries)) if pr_boundaries else 0.0
            ),
            "pair.affinity.dir_overlap_count": len(dir_overlap),
            "pair.affinity.dir_overlap_share": (
                float(len(dir_overlap)) / float(len(pr_dir_scores)) if pr_dir_scores else 0.0
            ),
            "pair.affinity.owner_match": login_l in owner_set,
            "pair.affinity.requested_match": login_l in requested_users,
            "pair.affinity.mentioned_match": f"@{login_l}" in mention_text,
            "pair.affinity.pr_touch_dot_candidate_boundary_atlas": _dot_sparse(pr_boundary_scores, cand_boundary),
            "pair.affinity.pr_touch_dot_candidate_dir_atlas": _dot_sparse(pr_dir_scores, cand_dir),
            "pair.social.prior_interactions_author_candidate_180d": social_total,
            "pair.social.prior_reviews_on_author_prs_180d": social_reviews,
            "pair.social.prior_comments_on_author_prs_180d": social_comments,
            "pair.social.author_to_candidate_latency_median": social_latency,
            "pair.availability.recency_seconds": cand.get("candidate.activity.last_seen_seconds"),
            "pair.availability.historical_response_rate_bucket": _response_rate_bucket(events_30d, events_180d),
            "pair.availability.is_already_participating": participating,
            # Legacy
            "x.mentioned_in_pr": f"@{login_l}" in mention_text,
            "x.multi_boundary_and_recent_activity": bool(
                bool(pr_features.get("pr.boundary.is_multi_boundary", False)) and events_30d > 0.0
            ),
            "x.churn_times_recent_activity": float(pr_features.get("pr.surface.total_churn", 0.0) or 0.0)
            * events_30d,
        }

    return {k: out[k] for k in sorted(out, key=str.lower)}
