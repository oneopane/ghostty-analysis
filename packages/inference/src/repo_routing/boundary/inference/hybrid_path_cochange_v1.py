from __future__ import annotations

import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any

from ...paths import repo_db_path
from ...time import dt_sql_utc, require_dt_utc
from ..models import (
    BoundaryDef,
    BoundaryModel,
    BoundaryUnit,
    Granularity,
    Membership,
    MembershipMode,
)
from ..parsers.registry import get_parser_backend
from ..signals.cochange import cochange_scores
from ..signals.parser import parser_boundary_votes
from ..signals.path import normalize_path, path_boundary
from ..source_snapshot import resolve_snapshot_root
from .base import BoundaryInferenceContext


class HybridPathCochangeV1:
    strategy_id = "hybrid_path_cochange.v1"
    strategy_version = "v1"

    def infer(
        self, context: BoundaryInferenceContext
    ) -> tuple[BoundaryModel, list[dict[str, Any]]]:
        cutoff = require_dt_utc(context.cutoff_utc, name="cutoff_utc")
        db_path = repo_db_path(repo_full_name=context.repo_full_name, data_dir=context.data_dir)

        file_sets = _read_file_sets_as_of(db_path=db_path, repo=context.repo_full_name, cutoff_sql=dt_sql_utc(cutoff))
        files = sorted({f for fs in file_sets for f in fs})

        if not files:
            model = BoundaryModel(
                strategy_id=self.strategy_id,
                strategy_version=self.strategy_version,
                repo=context.repo_full_name,
                cutoff_utc=cutoff,
                membership_mode=context.membership_mode,
                units=[],
                boundaries=[],
                memberships=[],
                metadata={"diagnostics": {"empty": True, "file_count": 0}},
            )
            return model, []

        path_map: dict[str, tuple[str, str]] = {f: path_boundary(f) for f in files}
        base_boundary_ids = sorted({bid for bid, _ in path_map.values()})
        boundary_name_by_id = {bid: name for bid, name in path_map.values()}

        cochange = cochange_scores(file_sets)

        path_weight = float(context.config.get("path_weight", 1.0))
        cochange_weight = float(context.config.get("cochange_weight", 0.35))
        min_mixed_weight = float(context.config.get("min_mixed_weight", 1e-8))

        parser_enabled = bool(context.config.get("parser_enabled", False))
        parser_weight = float(context.config.get("parser_weight", 0.2))
        parser_backend_id = str(context.config.get("parser_backend_id", "python.ast.v1"))
        parser_backend_version: str | None = None
        parser_votes: dict[str, dict[str, float]] = {}
        parser_diagnostics: list[str] = []
        if parser_enabled:
            parser_strict = bool(context.config.get("parser_strict", False))
            snapshot_root = resolve_snapshot_root(
                configured_root=context.config.get("parser_snapshot_root")
            )
            if snapshot_root is None:
                parser_diagnostics.append("parser_snapshot_missing")
                if parser_strict:
                    raise RuntimeError("parser snapshot root missing in strict parser mode")
            else:
                try:
                    backend = get_parser_backend(parser_backend_id)
                    parsed = backend.parse_snapshot(root=snapshot_root, paths=files)
                except Exception as exc:
                    parser_diagnostics.append(f"parser_backend_error:{type(exc).__name__}")
                    if parser_strict:
                        raise
                else:
                    parser_backend_version = parsed.backend_version
                    parser_votes = parser_boundary_votes(parsed)
                    parser_diagnostics.extend(parsed.diagnostics)

        parser_boundary_ids = sorted(
            {
                boundary_id
                for votes in parser_votes.values()
                for boundary_id in votes.keys()
            }
        )
        for boundary_id in parser_boundary_ids:
            boundary_name_by_id.setdefault(boundary_id, boundary_id.removeprefix("dir:"))
        boundary_ids = sorted(set(base_boundary_ids) | set(parser_boundary_ids))

        score_rows: list[dict[str, Any]] = []
        mixed_memberships: list[Membership] = []
        hard_memberships: list[Membership] = []
        confidence: dict[str, float] = {}

        for file_path in files:
            by_boundary: dict[str, float] = defaultdict(float)

            own_boundary_id, _ = path_map[file_path]
            by_boundary[own_boundary_id] += path_weight

            neighbors = cochange.get(file_path, {})
            for neighbor_path, score in neighbors.items():
                neighbor_boundary_id, _ = path_map.get(neighbor_path, path_boundary(neighbor_path))
                by_boundary[neighbor_boundary_id] += cochange_weight * float(score)

            for boundary_id, vote in parser_votes.get(file_path, {}).items():
                by_boundary[boundary_id] += parser_weight * float(vote)

            ranked = sorted(
                by_boundary.items(),
                key=lambda it: (-round(it[1], 12), it[0]),
            )

            total = sum(v for _, v in ranked)
            if total <= 0:
                ranked = [(own_boundary_id, 1.0)]
                total = 1.0

            normalized = [(bid, (val / total)) for bid, val in ranked]
            confidence[file_path] = normalized[0][1]
            hard_memberships.append(
                Membership(unit_id=f"file:{file_path}", boundary_id=normalized[0][0], weight=1.0)
            )

            for bid, frac in normalized:
                if frac < min_mixed_weight:
                    continue
                mixed_memberships.append(
                    Membership(
                        unit_id=f"file:{file_path}",
                        boundary_id=bid,
                        weight=float(round(frac, 8)),
                    )
                )
                score_rows.append(
                    {
                        "unit_id": f"file:{file_path}",
                        "signal": "hybrid_score",
                        "boundary_id": bid,
                        "value": float(round(frac, 8)),
                    }
                )

        units = [
            BoundaryUnit(unit_id=f"file:{p}", granularity=Granularity.FILE, path=p)
            for p in files
        ]
        boundaries = [
            BoundaryDef(
                boundary_id=bid,
                name=boundary_name_by_id.get(bid, bid.removeprefix("dir:")),
                granularity=Granularity.DIR,
            )
            for bid in boundary_ids
        ]

        memberships = (
            hard_memberships
            if context.membership_mode == MembershipMode.HARD
            else mixed_memberships
        )
        model = BoundaryModel(
            strategy_id=self.strategy_id,
            strategy_version=self.strategy_version,
            repo=context.repo_full_name,
            cutoff_utc=cutoff,
            membership_mode=context.membership_mode,
            units=units,
            boundaries=boundaries,
            memberships=memberships,
            metadata={
                "diagnostics": {
                    "empty": False,
                    "file_count": len(files),
                    "boundary_count": len(boundary_ids),
                    "mean_top_membership": round(
                        sum(confidence.values()) / max(len(confidence), 1),
                        8,
                    ),
                },
                "weights": {
                    "path_weight": path_weight,
                    "cochange_weight": cochange_weight,
                    "parser_weight": parser_weight,
                },
                "cochange_edges": int(sum(len(v) for v in cochange.values())),
                "parser_enabled": parser_enabled,
                "parser_backend_id": parser_backend_id if parser_enabled else None,
                "parser_backend_version": parser_backend_version,
                "parser_signal_files": len(parser_votes),
                "parser_diagnostics": sorted(set(parser_diagnostics)),
                "hard_membership_preview": {
                    m.unit_id: m.boundary_id
                    for m in sorted(hard_memberships, key=lambda m: m.unit_id)
                },
            },
        )

        score_rows = sorted(
            score_rows,
            key=lambda r: (
                str(r.get("unit_id", "")),
                str(r.get("signal", "")),
                str(r.get("boundary_id", "")),
                float(r.get("value", 0.0)),
            ),
        )
        return model, score_rows


def _read_file_sets_as_of(*, db_path: Path, repo: str, cutoff_sql: str) -> list[list[str]]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        repo_row = conn.execute(
            "select id from repos where full_name = ?",
            (repo,),
        ).fetchone()
        if repo_row is None:
            raise KeyError(f"repo not found in db: {repo}")
        repo_id = int(repo_row["id"])

        rows = conn.execute(
            """
            select pr.id as pull_request_id, prf.path as path
            from pull_request_files prf
            join pull_requests pr on pr.id = prf.pull_request_id
            where prf.repo_id = ?
              and pr.repo_id = ?
              and pr.created_at is not null
              and pr.created_at <= ?
              and prf.path is not null
            order by pr.id asc, prf.path asc
            """,
            (repo_id, repo_id, cutoff_sql),
        ).fetchall()

        by_pr: dict[int, list[str]] = defaultdict(list)
        for row in rows:
            path = normalize_path(str(row["path"]))
            if not path:
                continue
            by_pr[int(row["pull_request_id"])].append(path)

        return [sorted(set(paths)) for _, paths in sorted(by_pr.items())]
    finally:
        conn.close()
