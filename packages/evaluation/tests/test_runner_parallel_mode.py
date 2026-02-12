from __future__ import annotations

import json

from evaluation_harness.config import EvalDefaults, EvalRunConfig
from evaluation_harness.runner import run_streaming_eval
from repo_routing.registry import RouterSpec

from .fixtures.build_min_db import build_min_db


def _strip_volatile(payload: object) -> object:
    if isinstance(payload, dict):
        out: dict[str, object] = {}
        for k, v in payload.items():
            if k in {"run_id", "generated_at"}:
                continue
            out[k] = _strip_volatile(v)
        return out
    if isinstance(payload, list):
        return [_strip_volatile(x) for x in payload]
    return payload


def test_parallel_mode_matches_sequential_outputs(tmp_path) -> None:  # type: ignore[no-untyped-def]
    db = build_min_db(tmp_path=tmp_path)
    specs = [
        RouterSpec(type="builtin", name="mentions"),
        RouterSpec(type="builtin", name="popularity"),
    ]
    cfg_seq = EvalRunConfig(
        repo=db.repo,
        data_dir=str(db.data_dir),
        run_id="run-sequential",
        defaults=EvalDefaults(execution_mode="sequential"),
    )
    cfg_par = EvalRunConfig(
        repo=db.repo,
        data_dir=str(db.data_dir),
        run_id="run-parallel",
        defaults=EvalDefaults(execution_mode="parallel", max_workers=2),
    )

    seq = run_streaming_eval(cfg=cfg_seq, pr_numbers=[db.pr_number], router_specs=specs)
    par = run_streaming_eval(cfg=cfg_par, pr_numbers=[db.pr_number], router_specs=specs)

    seq_report = json.loads((seq.run_dir / "report.json").read_text(encoding="utf-8"))
    par_report = json.loads((par.run_dir / "report.json").read_text(encoding="utf-8"))
    assert _strip_volatile(seq_report) == _strip_volatile(par_report)

    seq_per_pr = [
        json.loads(line)
        for line in (seq.run_dir / "per_pr.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    par_per_pr = [
        json.loads(line)
        for line in (par.run_dir / "per_pr.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert _strip_volatile(seq_per_pr) == _strip_volatile(par_per_pr)
