from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from repo_routing.boundary.models import MembershipMode
from repo_routing.boundary.parsers.models import (
    ParsedFileSignals,
    ParsedImport,
    ParserRunResult,
)
from repo_routing.boundary.pipeline import build_boundary_model
from repo_routing.boundary.signals.parser import parser_boundary_votes


def test_parser_votes_convert_imports_to_boundary_scores() -> None:
    run = ParserRunResult(
        backend_id="python.ast.v1",
        backend_version="v1",
        files=[
            ParsedFileSignals(
                path="src/a.py",
                imports=[ParsedImport(module="pkg.core"), ParsedImport(module="pkg.util")],
            )
        ],
    )

    votes = parser_boundary_votes(run)
    assert votes["src/a.py"]["dir:pkg"] == 1.0


def _seed_db(base_dir: Path) -> str:
    repo = "acme/widgets"
    owner, name = repo.split("/", 1)
    db_path = base_dir / "github" / owner / name / "history.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("create table repos (id integer primary key, full_name text not null)")
        conn.execute(
            """
            create table pull_requests (
                id integer primary key,
                repo_id integer,
                number integer,
                created_at text
            )
            """
        )
        conn.execute(
            """
            create table pull_request_files (
                repo_id integer,
                pull_request_id integer,
                head_sha text,
                path text,
                status text,
                additions integer,
                deletions integer,
                changes integer
            )
            """
        )

        conn.execute("insert into repos (id, full_name) values (1, ?)", (repo,))
        conn.execute(
            "insert into pull_requests (id, repo_id, number, created_at) values (101, 1, 1, '2024-01-10 00:00:00')"
        )
        conn.execute(
            """
            insert into pull_request_files
            (repo_id, pull_request_id, head_sha, path, status, additions, deletions, changes)
            values (1, 101, 'h1', 'src/a.py', 'modified', 1, 1, 2)
            """
        )

        conn.commit()
    finally:
        conn.close()

    return repo


def test_hybrid_strategy_applies_parser_signal_channel(tmp_path: Path) -> None:
    repo = _seed_db(tmp_path / "data")

    snapshot_root = tmp_path / "snapshot"
    (snapshot_root / "src").mkdir(parents=True, exist_ok=True)
    (snapshot_root / "src" / "a.py").write_text(
        "import tests.helper\n\n\ndef f():\n    return 1\n",
        encoding="utf-8",
    )

    model, signal_rows = build_boundary_model(
        repo_full_name=repo,
        cutoff_utc=datetime(2024, 1, 11, tzinfo=timezone.utc),
        data_dir=tmp_path / "data",
        membership_mode=MembershipMode.MIXED,
        strategy_config={
            "parser_enabled": True,
            "parser_backend_id": "python.ast.v1",
            "parser_snapshot_root": str(snapshot_root),
            "parser_weight": 1.0,
            "path_weight": 1.0,
            "cochange_weight": 0.0,
        },
    )

    boundary_ids = {b.boundary_id for b in model.boundaries}
    assert "dir:tests" in boundary_ids

    file_memberships = [m for m in model.memberships if m.unit_id == "file:src/a.py"]
    assert any(m.boundary_id == "dir:tests" for m in file_memberships)
    assert any(r["boundary_id"] == "dir:tests" for r in signal_rows)
