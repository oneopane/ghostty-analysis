from __future__ import annotations

import json
from pathlib import Path



def default_team_roster_path(*, repo: str, data_dir: str | Path) -> Path:
    owner, name = repo.split("/", 1)
    return Path(data_dir) / "github" / owner / name / "routing" / "team_roster.json"


def load_team_roster(*, repo: str, data_dir: str | Path) -> dict[str, list[str]]:
    """Load optional team roster mapping.

    Supported shapes:

    1) {"team-a": ["alice", "bob"], ...}
    2) {"teams": {"team-a": ["alice", "bob"], ...}}

    Team keys are normalized to lowercase and may be either:
    - "org/team"
    - "team:slug"
    - "slug"
    """

    p = default_team_roster_path(repo=repo, data_dir=data_dir)
    if not p.exists():
        return {}

    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}

    table = raw.get("teams") if isinstance(raw, dict) and isinstance(raw.get("teams"), dict) else raw
    if not isinstance(table, dict):
        return {}

    out: dict[str, list[str]] = {}
    for team, members in table.items():
        if not isinstance(team, str) or not isinstance(members, list):
            continue
        cleaned = sorted(
            {
                str(m).strip()
                for m in members
                if isinstance(m, str) and str(m).strip()
            },
            key=str.lower,
        )
        out[team.strip().lower()] = cleaned
    return out


def team_key_variants(team_name: str) -> list[str]:
    t = team_name.strip().lower()
    keys = {t}
    if t.startswith("team:"):
        keys.add(t.split(":", 1)[1])
    if "/" in t:
        keys.add(t)
        keys.add(t.split("/", 1)[1])
    else:
        keys.add(f"team:{t}")
    return sorted(keys)


def expand_team_members(*, team_names: set[str], roster: dict[str, list[str]]) -> set[str]:
    out: set[str] = set()
    for t in team_names:
        for k in team_key_variants(t):
            out.update(roster.get(k, []))
    return out
