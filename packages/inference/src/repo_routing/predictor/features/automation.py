from __future__ import annotations

import re
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any

from ...inputs.models import PRInputBundle
from .sql import connect_repo_db, cutoff_sql, load_repo_pr_ids

_BOT_RE = re.compile(r"(?i)(\[bot\]|dependabot|renovate|copilot|claude|github-actions)")
_CATEGORY_RES: dict[str, re.Pattern[str]] = {
    "lint": re.compile(r"(?i)\b(lint|ruff|flake8|eslint|prettier)\b"),
    "test": re.compile(r"(?i)\b(test|pytest|junit|coverage|ci failed)\b"),
    "security": re.compile(r"(?i)\b(security|vuln|cve|sast|secret scan)\b"),
    "cla": re.compile(r"(?i)\bcla\b|contributor license"),
    "dep_update": re.compile(r"(?i)\b(dependabot|renovate|dependency update|bump .* from .* to)\b"),
}


def build_automation_features(
    *,
    input: PRInputBundle,
    data_dir: str | Path,
) -> dict[str, Any]:
    conn = connect_repo_db(repo=input.repo, data_dir=data_dir)
    try:
        ids = load_repo_pr_ids(conn=conn, repo=input.repo, pr_number=input.pr_number)
        cutoff_s = cutoff_sql(input.cutoff)

        try:
            rows = conn.execute(
                """
                select lower(coalesce(u.login, '')) as login, coalesce(c.body, '') as body
                from comments c
                left join users u on u.id = c.user_id
                where c.repo_id = ?
                  and c.pull_request_id = ?
                  and c.created_at <= ?
                order by c.created_at asc, c.id asc
                """,
                (ids.repo_id, ids.pull_request_id, cutoff_s),
            ).fetchall()
        except sqlite3.OperationalError:
            rows = []
    finally:
        conn.close()

    bot_comments = 0
    bot_logins: set[str] = set()
    category_counts: Counter[str] = Counter()

    for r in rows:
        login = str(r["login"] or "")
        body = str(r["body"] or "")
        is_bot = bool(_BOT_RE.search(login))
        if is_bot:
            bot_comments += 1
            if login:
                bot_logins.add(login)

        text = f"{login}\n{body}"
        for k, pat in _CATEGORY_RES.items():
            if pat.search(text):
                category_counts[k] += 1

    out: dict[str, Any] = {
        "automation.bot_comment_count": bot_comments,
        "automation.bot_authors.distinct_count": len(bot_logins),
        "automation.bot_categories.lint": int(category_counts.get("lint", 0)),
        "automation.bot_categories.test": int(category_counts.get("test", 0)),
        "automation.bot_categories.security": int(category_counts.get("security", 0)),
        "automation.bot_categories.cla": int(category_counts.get("cla", 0)),
        "automation.bot_categories.dep_update": int(category_counts.get("dep_update", 0)),
        "automation.has_dep_update_signal": int(category_counts.get("dep_update", 0)) > 0,
        "automation.has_security_scan_signal": int(category_counts.get("security", 0)) > 0,
    }
    return {k: out[k] for k in sorted(out)}
