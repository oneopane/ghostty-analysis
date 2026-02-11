from __future__ import annotations

from datetime import datetime
from pathlib import Path

import typer
from rich import print
from repo_routing.time import parse_dt_utc

from repo_routing.registry import RouterSpec, router_id_for_spec

from ..cutoff import cutoff_for_pr
from ..paths import (
    eval_per_pr_jsonl_path,
    eval_report_json_path,
    eval_report_md_path,
    repo_db_path,
    repo_eval_dir,
    repo_eval_run_dir,
)
from ..config import EvalRunConfig
from ..sampling import sample_pr_numbers_created_in_window
from ..run_id import compute_run_id
from ..runner import run_streaming_eval


app = typer.Typer(add_completion=False, pretty_exceptions_show_locals=False)

_VALID_ROUTERS = {
    "mentions",
    "popularity",
    "codeowners",
    "union",
    "hybrid_ranker",
    "llm_rerank",
    "stewards",
}


def _parse_dt(value: str) -> datetime:
    try:
        dt = parse_dt_utc(value)
    except ValueError as exc:
        raise typer.BadParameter(f"invalid ISO timestamp: {value}") from exc
    if dt is None:
        raise typer.BadParameter("missing datetime value")
    return dt


def _normalize_builtin_routers(values: list[str], *, option_name: str) -> list[str]:
    normalized = [v.strip().lower() for v in values if v.strip()]
    if not normalized:
        return []

    unknown = sorted({b for b in normalized if b not in _VALID_ROUTERS})
    if unknown:
        valid = ", ".join(sorted(_VALID_ROUTERS))
        raise typer.BadParameter(
            f"unknown {option_name}(s): {', '.join(unknown)}. valid: {valid}"
        )
    return normalized


def _apply_router_configs(
    *,
    specs: list[RouterSpec],
    router_configs: list[str],
) -> list[RouterSpec]:
    if not router_configs:
        return specs

    keyed = [c for c in router_configs if "=" in c]
    positional = [c for c in router_configs if "=" not in c]

    out = [s.model_copy() for s in specs]

    if keyed:
        mapping: dict[str, str] = {}
        for item in keyed:
            key, value = item.split("=", 1)
            if not key.strip() or not value.strip():
                raise typer.BadParameter(f"invalid --router-config pair: {item}")
            mapping[key.strip()] = value.strip()

        for i, spec in enumerate(out):
            rid = router_id_for_spec(spec)
            if rid in mapping:
                out[i] = spec.model_copy(update={"config_path": mapping[rid]})
            elif spec.name in mapping:
                out[i] = spec.model_copy(update={"config_path": mapping[spec.name]})

    if positional:
        if len(positional) > len(out):
            raise typer.BadParameter("too many --router-config values for routers")
        for i, cfg in enumerate(positional):
            out[i] = out[i].model_copy(update={"config_path": cfg})

    return out


def _build_router_specs(
    *,
    routers: list[str],
    baselines: list[str],
    router_imports: list[str],
    router_configs: list[str],
) -> list[RouterSpec]:
    builtin = _normalize_builtin_routers(routers, option_name="router")
    baseline_alias = _normalize_builtin_routers(baselines, option_name="baseline")

    specs: list[RouterSpec] = [
        RouterSpec(type="builtin", name=name)
        for name in [*baseline_alias, *builtin]
    ]
    specs.extend(
        [
            RouterSpec(type="import_path", name=import_path, import_path=import_path)
            for import_path in router_imports
        ]
    )

    if not specs:
        specs = [RouterSpec(type="builtin", name="mentions")]

    specs = _apply_router_configs(specs=specs, router_configs=router_configs)

    for spec in specs:
        if spec.type == "builtin" and spec.name == "stewards":
            if spec.config_path is None:
                raise typer.BadParameter(
                    "--config is required when baseline includes stewards"
                )
            p = Path(spec.config_path)
            if not p.exists():
                raise typer.BadParameter(f"router config path does not exist: {p}")

    return specs


@app.command()
def info(
    repo: str = typer.Option(..., help="Repository in owner/name format"),
    data_dir: str = typer.Option("data", help="Base directory for per-repo data"),
):
    """Show resolved paths for a repository."""
    print(f"[bold]repo[/bold] {repo}")
    print(f"[bold]db[/bold] {repo_db_path(repo_full_name=repo, data_dir=data_dir)}")


@app.command("sample")
def sample(
    repo: str = typer.Option(..., help="Repository in owner/name format"),
    data_dir: str = typer.Option("data", help="Base directory for per-repo data"),
    start_at: str | None = typer.Option(
        None, "--from", "--start-at", help="ISO created_at window start"
    ),
    end_at: str | None = typer.Option(None, help="ISO created_at window end"),
    limit: int | None = typer.Option(None, help="Max PRs"),
):
    prs = sample_pr_numbers_created_in_window(
        repo=repo,
        data_dir=data_dir,
        start_at=_parse_dt(start_at) if start_at else None,
        end_at=_parse_dt(end_at) if end_at else None,
        limit=limit,
    )
    print(f"[bold]n[/bold] {len(prs)}")
    for n in prs:
        print(n)


@app.command("cutoff")
def cutoff(
    repo: str = typer.Option(..., help="Repository in owner/name format"),
    pr_number: int = typer.Option(..., help="Pull request number"),
    data_dir: str = typer.Option("data", help="Base directory for per-repo data"),
):
    c = cutoff_for_pr(repo=repo, pr_number=pr_number, data_dir=data_dir)
    print(c.isoformat())


@app.command("paths")
def paths(
    repo: str = typer.Option(..., help="Repository in owner/name format"),
    run_id: str = typer.Option(..., help="Evaluation run id"),
    data_dir: str = typer.Option("data", help="Base directory for per-repo data"),
):
    print(
        f"[bold]eval_run[/bold] {repo_eval_run_dir(repo_full_name=repo, data_dir=data_dir, run_id=run_id)}"
    )


@app.command("list")
def list_runs(
    repo: str = typer.Option(..., help="Repository in owner/name format"),
    data_dir: str = typer.Option("data", help="Base directory for per-repo data"),
):
    base = repo_eval_dir(repo_full_name=repo, data_dir=data_dir)
    if not base.exists():
        print(f"[bold]eval_dir[/bold] {base}")
        print("(missing)")
        raise typer.Exit(code=1)

    runs = [p.name for p in base.iterdir() if p.is_dir()]
    runs.sort(key=lambda s: s.lower())
    print(f"[bold]n[/bold] {len(runs)}")
    for r in runs:
        print(r)


@app.command("show")
def show(
    repo: str = typer.Option(..., help="Repository in owner/name format"),
    run_id: str = typer.Option(..., help="Evaluation run id"),
    data_dir: str = typer.Option("data", help="Base directory for per-repo data"),
):
    p = eval_report_md_path(repo_full_name=repo, data_dir=data_dir, run_id=run_id)
    if p.exists():
        print(p.read_text(encoding="utf-8").rstrip("\n"))
        return

    pj = eval_report_json_path(repo_full_name=repo, data_dir=data_dir, run_id=run_id)
    if pj.exists():
        print(pj.read_text(encoding="utf-8").rstrip("\n"))
        return

    raise typer.BadParameter(f"missing report: {p} / {pj}")


@app.command("explain")
def explain(
    repo: str = typer.Option(..., help="Repository in owner/name format"),
    run_id: str = typer.Option(..., help="Evaluation run id"),
    pr_number: int = typer.Option(..., "--pr", help="Pull request number"),
    baseline: str | None = typer.Option(None, help="Router id (deprecated name)"),
    router: str | None = typer.Option(None, help="Router id (default: first present)"),
    policy: str | None = typer.Option(None, "--policy", help="Truth policy id"),
    data_dir: str = typer.Option("data", help="Base directory for per-repo data"),
):
    import json

    p = eval_per_pr_jsonl_path(repo_full_name=repo, data_dir=data_dir, run_id=run_id)
    if not p.exists():
        raise typer.BadParameter(f"missing per_pr.jsonl: {p}")

    row: dict | None = None
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        if int(obj.get("pr_number", -1)) == pr_number:
            row = obj
            break
    if row is None:
        raise typer.BadParameter(f"pr not found in per_pr.jsonl: {pr_number}")

    routers = row.get("routers") or row.get("baselines") or {}
    if not isinstance(routers, dict) or not routers:
        raise typer.BadParameter("missing routers for pr")

    chosen = router or baseline
    if chosen is None:
        chosen = sorted(routers.keys(), key=lambda s: str(s).lower())[0]
    if chosen not in routers:
        raise typer.BadParameter(f"router not found: {chosen}")

    print(f"[bold]repo[/bold] {repo}")
    print(f"[bold]run_id[/bold] {run_id}")
    print(f"[bold]pr[/bold] {pr_number}")
    print(f"[bold]cutoff[/bold] {row.get('cutoff')}")
    print(f"[bold]router[/bold] {chosen}")

    selected_policy = policy
    truth_block = row.get("truth")
    truth_policies = {}
    if isinstance(truth_block, dict):
        raw = truth_block.get("policies")
        if isinstance(raw, dict):
            truth_policies = raw
            if selected_policy is None:
                raw_primary = truth_block.get("primary_policy")
                if isinstance(raw_primary, str) and raw_primary.strip():
                    selected_policy = raw_primary.strip()
    if selected_policy is None and truth_policies:
        selected_policy = sorted(truth_policies.keys(), key=lambda s: str(s).lower())[0]
    if selected_policy is not None and truth_policies and selected_policy not in truth_policies:
        raise typer.BadParameter(f"truth policy not found: {selected_policy}")
    if selected_policy is not None:
        print(f"[bold]truth_policy[/bold] {selected_policy}")
    print("")

    print("[bold]truth_behavior[/bold]")
    if selected_policy is not None and truth_policies:
        targets = (truth_policies.get(selected_policy) or {}).get("targets") or []
    else:
        targets = row.get("truth_behavior") or []
    for t in targets:
        print(f"- {t}")
    if selected_policy is not None and truth_policies:
        policy_entry = truth_policies.get(selected_policy) or {}
        print(
            f"- status: {policy_entry.get('status')}"
        )
    print("")

    b = routers[chosen]
    rr = b.get("route_result") or {}
    print("[bold]candidates[/bold]")
    for c in rr.get("candidates") or []:
        target = (c.get("target") or {}).get("name")
        score = c.get("score")
        print(f"- {target} (score={score})")
        for ev in c.get("evidence") or []:
            kind = ev.get("kind")
            data = ev.get("data")
            print(f"  {kind}: {data}")
    print("")

    print("[bold]routing_agreement[/bold]")
    routing_agreement = b.get("routing_agreement") or {}
    by_policy = b.get("routing_agreement_by_policy")
    if (
        selected_policy is not None
        and isinstance(by_policy, dict)
        and isinstance(by_policy.get(selected_policy), dict)
    ):
        routing_agreement = by_policy.get(selected_policy) or {}
    print(
        json.dumps(
            routing_agreement,
            sort_keys=True,
            indent=2,
            ensure_ascii=True,
        )
    )
    print("")

    print("[bold]gates[/bold]")
    print(
        json.dumps(row.get("gates") or {}, sort_keys=True, indent=2, ensure_ascii=True)
    )
    print("")

    print("[bold]queue[/bold]")
    print(json.dumps(b.get("queue") or {}, sort_keys=True, indent=2, ensure_ascii=True))


@app.command("run")
def run(
    repo: str = typer.Option(..., help="Repository in owner/name format"),
    data_dir: str = typer.Option("data", help="Base directory for per-repo data"),
    run_id: str | None = typer.Option(None, help="Run id (default: computed)"),
    pr_number: list[int] = typer.Option([], "--pr", help="PR number (repeatable)"),
    start_at: str | None = typer.Option(
        None, "--from", "--start-at", help="ISO created_at window start"
    ),
    end_at: str | None = typer.Option(None, help="ISO created_at window end"),
    limit: int | None = typer.Option(None, help="Max PRs"),
    baseline: list[str] = typer.Option(
        [], "--baseline", help="Deprecated alias for --router"
    ),
    router: list[str] = typer.Option(
        [], "--router", help="Builtin router name(s) (repeatable)"
    ),
    router_import: list[str] = typer.Option(
        [], "--router-import", help="Import-path router(s): pkg.mod:ClassOrFactory"
    ),
    router_config: list[str] = typer.Option(
        [],
        "--router-config",
        help="Router config path(s): router_id=path, name=path, or positional",
    ),
    config: str | None = typer.Option(
        None,
        "--config",
        help="Deprecated single router config path (maps to first router)",
    ),
):
    configs = list(router_config)
    if config is not None:
        configs.insert(0, config)

    specs = _build_router_specs(
        routers=list(router),
        baselines=list(baseline),
        router_imports=list(router_import),
        router_configs=configs,
    )

    prs = pr_number
    if not prs:
        prs = sample_pr_numbers_created_in_window(
            repo=repo,
            data_dir=data_dir,
            start_at=_parse_dt(start_at) if start_at else None,
            end_at=_parse_dt(end_at) if end_at else None,
            limit=limit,
        )
    if not prs:
        raise typer.BadParameter("no PRs selected")

    cfg = EvalRunConfig(repo=repo, data_dir=data_dir, run_id=run_id or "run")
    if run_id is None:
        cfg.run_id = compute_run_id(cfg=cfg)

    res = run_streaming_eval(
        cfg=cfg,
        pr_numbers=list(prs),
        router_specs=specs,
    )
    typer.echo(f"run_dir {res.run_dir}")
