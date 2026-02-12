from repo_routing.router.baselines.mentions import extract_targets
from repo_routing.router.base import TargetType


def test_extract_targets_order_and_dedupe() -> None:
    targets = extract_targets("cc @alice @org/core @alice @bob")
    assert [(t.type, t.name) for t in targets] == [
        (TargetType.user, "alice"),
        (TargetType.team, "org/core"),
        (TargetType.user, "bob"),
    ]
