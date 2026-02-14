from __future__ import annotations

import json
from pathlib import Path


def _read_json(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else None


def materialize_per_pr_jsonl(*, run_dir: Path) -> None:
    out = run_dir / "per_pr.jsonl"
    if out.exists():
        return

    idx = run_dir / "artifact_index.jsonl"
    if not idx.exists():
        return

    rows = [
        json.loads(line)
        for line in idx.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    grouped: dict[str, dict[str, object]] = {}
    for row in rows:
        if row.get("artifact_type") != "route_result":
            continue
        rel = row.get("relative_path")
        if not isinstance(rel, str):
            continue
        payload = _read_json(run_dir / rel)
        if payload is None:
            continue
        rec = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
        result = rec.get("result") if isinstance(rec, dict) and isinstance(rec.get("result"), dict) else {}
        pr = str((result or {}).get("pr_number") or "")
        if not pr:
            continue
        grouped.setdefault(pr, {"pr_number": int(pr), "routers": {}})
        router_id = rec.get("router_id") if isinstance(rec, dict) else None
        if isinstance(router_id, str):
            grouped[pr]["routers"][router_id] = {"route_result": result}

    if not grouped:
        return

    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(grouped[k], sort_keys=True, ensure_ascii=True) for k in sorted(grouped)]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def materialize_report_json(*, run_dir: Path) -> dict[str, object]:
    report_path = run_dir / "report.json"
    existing = _read_json(report_path)
    if existing is not None:
        return existing

    idx = run_dir / "artifact_index.jsonl"
    if not idx.exists():
        return {"repo": None, "run_id": run_dir.name, "routers": [], "routing_agreement": {}}

    route_counts: dict[str, int] = {}
    for line in idx.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("artifact_type") != "route_result":
            continue
        rel = row.get("relative_path")
        if not isinstance(rel, str):
            continue
        payload = _read_json(run_dir / rel)
        if payload is None:
            continue
        rec = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
        router_id = rec.get("router_id") if isinstance(rec, dict) else None
        if isinstance(router_id, str):
            route_counts[router_id] = route_counts.get(router_id, 0) + 1

    return {
        "repo": None,
        "run_id": run_dir.name,
        "routers": sorted(route_counts),
        "routing_agreement": {
            rid: {"n": n}
            for rid, n in sorted(route_counts.items(), key=lambda kv: kv[0])
        },
        "derived_from": "artifact_index",
    }
