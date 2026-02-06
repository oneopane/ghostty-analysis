from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from ..paths import repo_db_path
from ..time import dt_sql_utc, parse_dt_utc, require_dt_utc
from .models import PullRequestFile, PullRequestSnapshot, ReviewRequest


@dataclass(frozen=True)
class RepoIds:
    repo_id: int


class HistoryReader:
    """Read-only accessor for a single repo history.sqlite."""

    def __init__(
        self,
        *,
        repo_full_name: str,
        data_dir: str | Path = "data",
        strict_as_of: bool = True,
    ) -> None:
        self.repo_full_name = repo_full_name
        self.data_dir = Path(data_dir)
        self.db_path = repo_db_path(
            repo_full_name=repo_full_name, data_dir=self.data_dir
        )
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._repo_ids: RepoIds | None = None
        self.strict_as_of = strict_as_of

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "HistoryReader":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        self.close()

    def repo_ids(self) -> RepoIds:
        if self._repo_ids is not None:
            return self._repo_ids
        row = self._conn.execute(
            "select id from repos where full_name = ?", (self.repo_full_name,)
        ).fetchone()
        if row is None:
            raise KeyError(f"repo not found in db: {self.repo_full_name}")
        self._repo_ids = RepoIds(repo_id=int(row["id"]))
        return self._repo_ids

    def pull_request_snapshot(
        self, *, number: int, as_of: datetime
    ) -> PullRequestSnapshot:
        as_of_utc = require_dt_utc(as_of, name="as_of")
        repo_id = self.repo_ids().repo_id
        pr_row = self._conn.execute(
            """
            select
              pr.id as pull_request_id,
              pr.issue_id as issue_id,
              pr.number as number,
              pr.user_id as author_id,
              u.login as author_login,
              pr.created_at as created_at,
              pr.title as pr_title,
              pr.body as pr_body,
              pr.base_sha as base_sha,
              pr.base_ref as base_ref
            from pull_requests pr
            left join users u on u.id = pr.user_id
            where pr.repo_id = ? and pr.number = ?
            """,
            (repo_id, number),
        ).fetchone()
        if pr_row is None:
            raise KeyError(f"pr not found: {self.repo_full_name}#{number}")

        pr_id = int(pr_row["pull_request_id"])
        issue_id = pr_row["issue_id"]

        if issue_id is not None:
            title, body = self._issue_content_as_of(
                issue_id=int(issue_id), as_of=as_of_utc
            )
        else:
            title, body = pr_row["pr_title"], pr_row["pr_body"]
        head_sha = self._pr_head_sha_as_of(pull_request_id=pr_id, as_of=as_of_utc)
        files = self._pull_request_files(pull_request_id=pr_id, head_sha=head_sha)
        review_requests = self._review_requests_as_of(
            pull_request_id=pr_id, as_of=as_of_utc
        )

        return PullRequestSnapshot(
            repo=self.repo_full_name,
            number=int(pr_row["number"]),
            pull_request_id=pr_id,
            issue_id=int(issue_id) if issue_id is not None else None,
            author_login=pr_row["author_login"],
            created_at=parse_dt_utc(pr_row["created_at"]),
            title=title,
            body=body,
            base_sha=pr_row["base_sha"],
            head_sha=head_sha,
            changed_files=files,
            review_requests=review_requests,
        )

    def iter_participants(self, *, start: datetime, end: datetime) -> Iterable[str]:
        """Yield user logins who commented or reviewed in [start, end]."""
        repo_id = self.repo_ids().repo_id
        start_s = dt_sql_utc(start, timespec="microseconds")
        end_s = dt_sql_utc(end, timespec="microseconds")

        for row in self._conn.execute(
            """
            select u.login as login
            from comments c
            join users u on u.id = c.user_id
            where c.repo_id = ?
              and c.pull_request_id is not null
              and c.created_at is not null
              and c.created_at >= ?
              and c.created_at <= ?
              and u.login is not null
              and (u.type is null or u.type != 'Bot')
            """,
            (repo_id, start_s, end_s),
        ):
            yield str(row["login"])

        for row in self._conn.execute(
            """
            select u.login as login
            from reviews r
            join users u on u.id = r.user_id
            where r.repo_id = ?
              and r.submitted_at is not null
              and r.submitted_at >= ?
              and r.submitted_at <= ?
              and u.login is not null
              and (u.type is null or u.type != 'Bot')
            """,
            (repo_id, start_s, end_s),
        ):
            yield str(row["login"])

    def _issue_content_as_of(
        self, *, issue_id: int, as_of: datetime
    ) -> tuple[str | None, str | None]:
        as_of_s = dt_sql_utc(as_of, timespec="microseconds")
        row = self._conn.execute(
            """
            select ici.title as title, ici.body as body
            from issue_content_intervals ici
            join events se on se.id = ici.start_event_id
            left join events ee on ee.id = ici.end_event_id
            where ici.issue_id = ?
              and se.occurred_at <= ?
              and (ee.id is null or ? < ee.occurred_at)
            order by se.occurred_at desc, se.id desc
            limit 1
            """,
            (issue_id, as_of_s, as_of_s),
        ).fetchone()
        if row is None:
            if self.strict_as_of:
                raise RuntimeError(
                    "missing issue_content_intervals; run interval rebuild during ingestion"
                )
            base = self._conn.execute(
                "select title, body from issues where id = ?",
                (issue_id,),
            ).fetchone()
            if base is None:
                return None, None
            return base["title"], base["body"]
        return row["title"], row["body"]

    def _pr_head_sha_as_of(
        self, *, pull_request_id: int, as_of: datetime
    ) -> str | None:
        as_of_s = dt_sql_utc(as_of, timespec="microseconds")
        row = self._conn.execute(
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
            (pull_request_id, as_of_s, as_of_s),
        ).fetchone()
        if row is None:
            if self.strict_as_of:
                raise RuntimeError(
                    "missing pull_request_head_intervals; run interval rebuild during ingestion"
                )
            base = self._conn.execute(
                "select head_sha from pull_requests where id = ?",
                (pull_request_id,),
            ).fetchone()
            return None if base is None else base["head_sha"]
        return row["head_sha"]

    def _pull_request_files(
        self, *, pull_request_id: int, head_sha: str | None
    ) -> list[PullRequestFile]:
        if head_sha is None:
            return []
        repo_id = self.repo_ids().repo_id
        rows = self._conn.execute(
            """
            select path, status, additions, deletions, changes
            from pull_request_files
            where repo_id = ? and pull_request_id = ? and head_sha = ?
            order by path asc
            """,
            (repo_id, pull_request_id, head_sha),
        ).fetchall()
        return [
            PullRequestFile(
                path=row["path"],
                status=row["status"],
                additions=row["additions"],
                deletions=row["deletions"],
                changes=row["changes"],
            )
            for row in rows
        ]

    def _review_requests_as_of(
        self, *, pull_request_id: int, as_of: datetime
    ) -> list[ReviewRequest]:
        as_of_s = dt_sql_utc(as_of, timespec="microseconds")
        rows = self._conn.execute(
            """
            select rri.reviewer_type as reviewer_type, rri.reviewer_id as reviewer_id
            from pull_request_review_request_intervals rri
            join events se on se.id = rri.start_event_id
            left join events ee on ee.id = rri.end_event_id
            where rri.pull_request_id = ?
              and se.occurred_at <= ?
              and (ee.id is null or ? < ee.occurred_at)
            order by rri.reviewer_type asc, rri.reviewer_id asc
            """,
            (pull_request_id, as_of_s, as_of_s),
        ).fetchall()

        out: list[ReviewRequest] = []
        for row in rows:
            reviewer_type = row["reviewer_type"]
            reviewer_id = int(row["reviewer_id"])
            if reviewer_type == "Team":
                team = self._conn.execute(
                    "select slug from teams where id = ?",
                    (reviewer_id,),
                ).fetchone()
                if team is None or team["slug"] is None:
                    continue
                out.append(
                    ReviewRequest(reviewer_type="team", reviewer=str(team["slug"]))
                )
            else:
                user = self._conn.execute(
                    "select login, type from users where id = ?",
                    (reviewer_id,),
                ).fetchone()
                if user is None or user["login"] is None:
                    continue
                if user["type"] == "Bot":
                    continue
                out.append(
                    ReviewRequest(reviewer_type="user", reviewer=str(user["login"]))
                )

        return out
