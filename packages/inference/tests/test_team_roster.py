from __future__ import annotations

import json

from repo_routing.predictor.features.team_roster import (
    expand_team_members,
    load_team_roster,
)


def test_load_team_roster_supports_nested_shape(tmp_path) -> None:  # type: ignore[no-untyped-def]
    p = tmp_path / "github" / "acme" / "widgets" / "routing" / "team_roster.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps({"teams": {"acme/reviewers": ["bob", "carol", "bob"]}}),
        encoding="utf-8",
    )

    roster = load_team_roster(repo="acme/widgets", data_dir=tmp_path)
    assert roster["acme/reviewers"] == ["bob", "carol"]


def test_expand_team_members_handles_key_variants() -> None:
    roster = {
        "acme/reviewers": ["bob"],
        "team:core": ["carol"],
        "infra": ["dave"],
    }
    out = expand_team_members(
        team_names={"acme/reviewers", "core", "team:infra"},
        roster=roster,
    )
    assert out == {"bob", "carol", "dave"}
