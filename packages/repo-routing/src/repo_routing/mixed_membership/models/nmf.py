from __future__ import annotations

from datetime import datetime
from typing import Any

from ...time import require_dt_utc
from ..artifacts import AreaMembershipModelArtifact, compute_model_hash
from ..config import AreaMembershipConfig
from ..areas.basis import UserAreaMatrix, rows_to_user_area_matrix


def _row_normalize(rows: list[list[float]]) -> list[list[float]]:
    out: list[list[float]] = []
    for row in rows:
        s = float(sum(row))
        if s <= 0:
            out.append([0.0 for _ in row])
        else:
            out.append([float(v) / s for v in row])
    return out


def _entropy(values: list[float]) -> float:
    import math

    v = [float(x) for x in values if float(x) > 0.0]
    if not v:
        return 0.0
    h = -sum(p * math.log(p) for p in v)
    denom = math.log(float(len(values))) if len(values) > 1 else 1.0
    return float(h / denom) if denom > 0 else 0.0


def _round_matrix(rows: list[list[float]], ndigits: int = 10) -> list[list[float]]:
    return [[round(float(v), ndigits) for v in row] for row in rows]


def fit_area_membership_nmf(
    *,
    repo: str,
    cutoff: datetime,
    rows: list[dict[str, Any]],
    config: AreaMembershipConfig | None = None,
) -> AreaMembershipModelArtifact:
    """Fit deterministic NMF mixed-membership model on user×area rows.

    This function is exploration-focused. It requires `numpy` + `scikit-learn`.
    """

    cfg = config or AreaMembershipConfig()
    cutoff_utc = require_dt_utc(cutoff, name="cutoff")

    matrix: UserAreaMatrix = rows_to_user_area_matrix(
        rows,
        min_user_total_weight=cfg.min_user_total_weight,
    )

    users = list(matrix.users)
    areas = list(matrix.areas)
    if not users or not areas:
        artifact = AreaMembershipModelArtifact(
            repo=repo,
            cutoff=cutoff_utc,
            config=cfg.model_dump(mode="json"),
            users=users,
            areas=areas,
            roles=[],
            user_role_mix={u: [] for u in users},
            role_area_mix={},
            diagnostics={"empty_matrix": True},
        )
        data = artifact.model_dump(mode="json")
        artifact.model_hash = compute_model_hash(data)
        return artifact

    try:
        import numpy as np  # type: ignore[import-not-found]
        from sklearn.decomposition import NMF  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover
        raise ImportError(
            "fit_area_membership_nmf requires numpy and scikit-learn."
        ) from exc

    X = np.array(matrix.values, dtype=float)
    n_users, n_areas = X.shape
    effective_k = max(1, min(int(cfg.n_components), int(n_users), int(n_areas)))

    model = NMF(
        n_components=effective_k,
        init=cfg.init,
        random_state=int(cfg.random_state),
        max_iter=int(cfg.max_iter),
        solver="cd",
        beta_loss="frobenius",
    )

    W = model.fit_transform(X)
    H = model.components_

    Wn = _round_matrix(_row_normalize(W.tolist()))
    Hn = _round_matrix(_row_normalize(H.tolist()))

    roles = [f"k{i}" for i in range(effective_k)]

    user_role_mix = {
        users[i]: [float(v) for v in Wn[i]]
        for i in range(len(users))
    }

    role_area_mix = {
        roles[i]: {
            area: float(Hn[i][j])
            for j, area in enumerate(areas)
            if float(Hn[i][j]) > 0.0
        }
        for i in range(len(roles))
    }
    role_area_mix = {
        r: {k: role_area_mix[r][k] for k in sorted(role_area_mix[r])}
        for r in sorted(role_area_mix)
    }

    diagnostics = {
        "n_users": n_users,
        "n_areas": n_areas,
        "n_components_effective": effective_k,
        "reconstruction_err": float(getattr(model, "reconstruction_err_", 0.0)),
        "n_iter": int(getattr(model, "n_iter_", 0)),
        "basis_version": cfg.basis_version,
    }

    artifact = AreaMembershipModelArtifact(
        repo=repo,
        cutoff=cutoff_utc,
        config=cfg.model_dump(mode="json"),
        users=users,
        areas=areas,
        roles=roles,
        user_role_mix=user_role_mix,
        role_area_mix=role_area_mix,
        diagnostics=diagnostics,
    )
    data = artifact.model_dump(mode="json")
    artifact.model_hash = compute_model_hash(data)
    return artifact


def build_candidate_role_mix_features(
    *,
    model: AreaMembershipModelArtifact,
    candidate_logins: list[str],
    prefix: str = "candidate.role_mix",
) -> dict[str, dict[str, Any]]:
    roles = list(model.roles)
    out: dict[str, dict[str, Any]] = {}

    for login in sorted(set(candidate_logins), key=str.lower):
        mix = model.user_role_mix.get(login.lower())
        if mix is None:
            mix = [0.0 for _ in roles]

        role_pairs = [(roles[i], float(mix[i])) for i in range(len(roles))]
        top_role = None
        if role_pairs:
            top_role = sorted(role_pairs, key=lambda kv: (-kv[1], kv[0]))[0][0]

        feats: dict[str, Any] = {
            f"{prefix}.{r}": float(v)
            for r, v in role_pairs
        }
        feats[f"{prefix}.entropy"] = _entropy([v for _r, v in role_pairs])
        feats[f"{prefix}.max_share"] = max([v for _r, v in role_pairs], default=0.0)
        feats[f"{prefix}.top_role"] = top_role

        out[login] = {k: feats[k] for k in sorted(feats)}

    return {k: out[k] for k in sorted(out, key=str.lower)}


def _candidate_area_projection(
    *,
    model: AreaMembershipModelArtifact,
    role_mix: list[float],
) -> dict[str, float]:
    proj: dict[str, float] = {}
    for i, role in enumerate(model.roles):
        rw = float(role_mix[i]) if i < len(role_mix) else 0.0
        if rw <= 0.0:
            continue
        area_map = model.role_area_mix.get(role, {})
        for area, aw in area_map.items():
            proj[area] = proj.get(area, 0.0) + rw * float(aw)

    s = float(sum(proj.values()))
    if s <= 0.0:
        return {}
    return {k: float(v) / s for k, v in proj.items()}


def pr_candidate_role_affinity(
    *,
    model: AreaMembershipModelArtifact,
    pr_area_distribution: dict[str, float],
    candidate_login: str,
) -> float:
    mix = model.user_role_mix.get(candidate_login.lower())
    if mix is None:
        return 0.0
    proj = _candidate_area_projection(model=model, role_mix=mix)
    if not proj or not pr_area_distribution:
        return 0.0
    keys = sorted(set(proj) & set(pr_area_distribution), key=str.lower)
    return float(sum(float(proj[k]) * float(pr_area_distribution[k]) for k in keys))


def build_pair_role_affinity_features(
    *,
    model: AreaMembershipModelArtifact,
    pr_area_distribution: dict[str, float],
    candidate_logins: list[str],
) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for login in sorted(set(candidate_logins), key=str.lower):
        out[login] = {
            "pair.affinity.pr_area_dot_candidate_role_mix": pr_candidate_role_affinity(
                model=model,
                pr_area_distribution=pr_area_distribution,
                candidate_login=login,
            )
        }
    return {k: out[k] for k in sorted(out, key=str.lower)}
