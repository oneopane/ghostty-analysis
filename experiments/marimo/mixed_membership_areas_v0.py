import marimo

__generated_with = "0.19.7"
app = marimo.App(width="full")


@app.cell
def _():
    from datetime import datetime, timezone

    import marimo as mo

    from repo_routing.mixed_membership import (
        AreaMembershipConfig,
        build_area_membership_dataset,
        fit_area_membership_model,
    )

    return AreaMembershipConfig, build_area_membership_dataset, datetime, fit_area_membership_model, mo, timezone


@app.cell
def _(mo):
    repo = mo.ui.text(label="repo", value="acme/widgets")
    data_dir = mo.ui.text(label="data dir", value="data")
    cutoff = mo.ui.text(label="cutoff (ISO)", value="2024-01-03T00:00:00+00:00")
    lookback_days = mo.ui.number(label="lookback_days", value=180, start=1, stop=3650)
    n_components = mo.ui.number(label="n_components", value=6, start=1, stop=64)
    return cutoff, data_dir, lookback_days, n_components, repo


@app.cell
def _(cutoff, datetime, timezone):
    try:
        cutoff_dt = datetime.fromisoformat(cutoff.value.replace("Z", "+00:00"))
        if cutoff_dt.tzinfo is None:
            cutoff_dt = cutoff_dt.replace(tzinfo=timezone.utc)
    except Exception:
        cutoff_dt = None
    cutoff_dt
    return (cutoff_dt,)


@app.cell
def _(AreaMembershipConfig, lookback_days, n_components):
    cfg = AreaMembershipConfig(
        lookback_days=int(lookback_days.value),
        n_components=int(n_components.value),
    )
    cfg
    return (cfg,)


@app.cell
def _(build_area_membership_dataset, cfg, cutoff_dt, data_dir, mo, repo):
    if cutoff_dt is None:
        mo.md("Invalid cutoff datetime")
        dataset = None
    else:
        try:
            dataset = build_area_membership_dataset(
                repo=repo.value,
                cutoff=cutoff_dt,
                data_dir=data_dir.value,
                config=cfg,
                as_polars=True,
            )
        except Exception as exc:
            dataset = None
            mo.md(f"Could not build dataset: `{exc}`")

    if dataset is not None:
        dataset.head(20)
    return (dataset,)


@app.cell
def _(cfg, cutoff_dt, data_dir, fit_area_membership_model, mo, repo):
    if cutoff_dt is None:
        model = None
    else:
        try:
            model = fit_area_membership_model(
                repo=repo.value,
                cutoff=cutoff_dt,
                data_dir=data_dir.value,
                config=cfg,
            )
        except Exception as exc:
            model = None
            mo.md(f"Could not fit model: `{exc}`")

    if model is not None:
        mo.md(
            f"""
            **Model hash:** `{model.model_hash[:16]}`  
            **Users:** {len(model.users)}  
            **Areas:** {len(model.areas)}  
            **Roles:** {len(model.roles)}
            """
        )
    return (model,)


@app.cell
def _(model):
    if model is None:
        return

    # Show top areas for each role.
    top = {}
    for role, area_map in model.role_area_mix.items():
        top[role] = sorted(area_map.items(), key=lambda kv: (-kv[1], kv[0]))[:8]
    top


if __name__ == "__main__":
    app.run()
