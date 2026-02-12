from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template, request

SQLITE_EXTENSIONS = {".sqlite", ".sqlite3", ".db"}
FORBIDDEN_SQL = re.compile(
    r"\b(insert|update|delete|drop|alter|create|replace|pragma|attach|detach|vacuum|reindex|analyze|truncate)\b",
    re.IGNORECASE,
)


def create_app(data_root: str = "data/github") -> Flask:
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )
    app.config["DATA_ROOT"] = Path(data_root).resolve()

    @app.get("/")
    def index() -> str:
        return render_template("index.html")

    @app.get("/api/databases")
    def list_databases():
        try:
            root = _data_root(app)
            if not root.exists():
                return jsonify({"items": [], "warning": f"Data directory not found: {root}"})
            items = _discover_databases(root)
            return jsonify({"items": items, "root": str(root)})
        except Exception as exc:  # pragma: no cover - defensive API guard
            return _json_error(f"Failed to scan data directory: {exc}", 500)

    @app.get("/api/tables")
    def list_tables():
        db_key = request.args.get("db", "")
        with _open_db(app, db_key) as conn:
            tables = conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """
            ).fetchall()

            payload: list[dict[str, Any]] = []
            for row in tables:
                table_name = row[0]
                count_value: int | None = None
                count_error: str | None = None
                try:
                    quoted = _quote_identifier(table_name)
                    count_value = int(
                        conn.execute(f"SELECT COUNT(*) AS n FROM {quoted}").fetchone()[0]
                    )
                except Exception as exc:  # noqa: BLE001
                    count_error = str(exc)
                payload.append(
                    {
                        "table": table_name,
                        "row_count": count_value,
                        "row_count_error": count_error,
                    }
                )
            return jsonify({"items": payload})

    @app.get("/api/schema")
    def table_schema():
        db_key = request.args.get("db", "")
        table = request.args.get("table", "")

        with _open_db(app, db_key) as conn:
            _ensure_table_exists(conn, table)
            quoted = _quote_identifier(table)
            rows = conn.execute(f"PRAGMA table_info({quoted})").fetchall()
            columns = [
                {
                    "cid": int(r[0]),
                    "name": r[1],
                    "type": r[2],
                    "notnull": bool(r[3]),
                    "default": r[4],
                    "pk": bool(r[5]),
                }
                for r in rows
            ]
            return jsonify({"table": table, "columns": columns})

    @app.get("/api/rows")
    def table_rows():
        db_key = request.args.get("db", "")
        table = request.args.get("table", "")
        page = max(1, int(request.args.get("page", "1")))
        page_size = min(500, max(1, int(request.args.get("page_size", "100"))))
        sort_col = request.args.get("sort_col")
        sort_dir = request.args.get("sort_dir", "asc").lower()
        global_filter = request.args.get("filter", "").strip()

        with _open_db(app, db_key) as conn:
            _ensure_table_exists(conn, table)
            columns = _table_columns(conn, table)
            quoted_table = _quote_identifier(table)

            where_clauses: list[str] = []
            params: list[Any] = []
            if global_filter:
                like = f"%{global_filter}%"
                col_terms = []
                for col in columns:
                    col_terms.append(f"CAST({_quote_identifier(col)} AS TEXT) LIKE ?")
                    params.append(like)
                if col_terms:
                    where_clauses.append("(" + " OR ".join(col_terms) + ")")

            where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

            order_sql = ""
            if sort_col:
                if sort_col not in columns:
                    raise ValueError(f"Unknown sort column: {sort_col}")
                dir_sql = "DESC" if sort_dir == "desc" else "ASC"
                order_sql = f"ORDER BY {_quote_identifier(sort_col)} {dir_sql}"

            total = int(
                conn.execute(
                    f"SELECT COUNT(*) FROM {quoted_table} {where_sql}", params
                ).fetchone()[0]
            )

            offset = (page - 1) * page_size
            rows = conn.execute(
                f"SELECT * FROM {quoted_table} {where_sql} {order_sql} LIMIT ? OFFSET ?",
                [*params, page_size, offset],
            ).fetchall()
            data_rows = [dict(r) for r in rows]

            return jsonify(
                {
                    "table": table,
                    "page": page,
                    "page_size": page_size,
                    "total_rows": total,
                    "total_pages": max(1, (total + page_size - 1) // page_size),
                    "columns": columns,
                    "rows": data_rows,
                }
            )

    @app.post("/api/query")
    def run_query():
        payload = request.get_json(silent=True) or {}
        db_key = str(payload.get("db", ""))
        sql = str(payload.get("sql", "")).strip()
        row_limit = min(1000, max(1, int(payload.get("row_limit", 200))))

        if not sql:
            raise ValueError("SQL is required")
        _validate_select_sql(sql)

        with _open_db(app, db_key) as conn:
            cur = conn.execute(sql)
            if cur.description is None:
                raise ValueError("Only SELECT queries are allowed")

            columns = [c[0] for c in cur.description]
            fetched = cur.fetchmany(row_limit + 1)
            truncated = len(fetched) > row_limit
            rows = fetched[:row_limit]

            return jsonify(
                {
                    "columns": columns,
                    "rows": [dict(r) for r in rows],
                    "returned_rows": len(rows),
                    "truncated": truncated,
                    "row_limit": row_limit,
                }
            )

    @app.errorhandler(ValueError)
    def handle_value_error(err: ValueError):
        return _json_error(str(err), 400)

    @app.errorhandler(sqlite3.Error)
    def handle_sqlite_error(err: sqlite3.Error):
        return _json_error(f"SQLite error: {err}", 400)

    return app


def _data_root(app: Flask) -> Path:
    return Path(app.config["DATA_ROOT"]).resolve()


def _discover_databases(data_root: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in sorted(data_root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in SQLITE_EXTENSIONS and not _looks_like_sqlite(path):
            continue

        rel = path.relative_to(data_root)
        parts = rel.parts
        owner = parts[0] if len(parts) > 0 else ""
        repo = parts[1] if len(parts) > 1 else ""
        stat = path.stat()
        items.append(
            {
                "id": rel.as_posix(),
                "owner": owner,
                "repo": repo,
                "file": path.name,
                "relative_path": rel.as_posix(),
                "size_bytes": stat.st_size,
                "updated_at": int(stat.st_mtime),
            }
        )
    return items


def _looks_like_sqlite(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return handle.read(16) == b"SQLite format 3\x00"
    except OSError:
        return False


def _resolve_db_path(app: Flask, db_key: str) -> Path:
    if not db_key:
        raise ValueError("Database id is required")

    root = _data_root(app)
    candidate = (root / db_key).resolve()
    if root not in candidate.parents and candidate != root:
        raise ValueError("Invalid database path")
    if not candidate.exists() or not candidate.is_file():
        raise ValueError(f"Database file not found: {db_key}")
    return candidate


def _open_db(app: Flask, db_key: str):
    db_path = _resolve_db_path(app, db_key)
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        raise ValueError(f"Could not open database: {exc}") from exc
    conn.row_factory = sqlite3.Row
    return conn


def _quote_identifier(identifier: str) -> str:
    if not identifier:
        raise ValueError("Identifier is required")
    return '"' + identifier.replace('"', '""') + '"'


def _ensure_table_exists(conn: sqlite3.Connection, table: str) -> None:
    if not table:
        raise ValueError("Table is required")
    found = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ? LIMIT 1",
        (table,),
    ).fetchone()
    if not found:
        raise ValueError(f"Table not found: {table}")


def _table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    pragma_rows = conn.execute(f"PRAGMA table_info({_quote_identifier(table)})").fetchall()
    columns = [str(row[1]) for row in pragma_rows]
    if not columns:
        raise ValueError(f"No columns found for table: {table}")
    return columns


def _validate_select_sql(sql: str) -> None:
    compact = sql.strip().rstrip(";").strip()
    if not compact:
        raise ValueError("SQL is required")

    normalized = compact.lower()
    if not (normalized.startswith("select") or normalized.startswith("with")):
        raise ValueError("Only SELECT queries are allowed")
    if FORBIDDEN_SQL.search(normalized):
        raise ValueError("Only read-only SELECT queries are allowed")

    statements = [s.strip() for s in sql.split(";") if s.strip()]
    if len(statements) != 1:
        raise ValueError("Only one SELECT statement is allowed")
