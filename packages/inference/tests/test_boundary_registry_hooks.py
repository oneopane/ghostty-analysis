from __future__ import annotations

from dataclasses import dataclass

from repo_routing.boundary.inference.registry import (
    available_boundary_strategies,
    get_boundary_strategy,
    register_boundary_strategy,
)
from repo_routing.boundary.models import (
    BoundaryDef,
    BoundaryModel,
    BoundaryUnit,
    Granularity,
    Membership,
    MembershipMode,
)
from repo_routing.boundary.parsers.models import (
    ParsedFileSignals,
    ParsedFunction,
    ParsedImport,
    ParserRunResult,
)
from repo_routing.boundary.parsers.registry import (
    available_parser_backends,
    get_parser_backend,
    register_parser_backend,
)


@dataclass
class _FakeStrategy:
    strategy_id: str = "fake.strategy.v1"
    strategy_version: str = "v1"

    def infer(self, context):  # type: ignore[no-untyped-def]
        model = BoundaryModel(
            strategy_id=self.strategy_id,
            strategy_version=self.strategy_version,
            repo=context.repo_full_name,
            cutoff_utc=context.cutoff_utc,
            membership_mode=MembershipMode.MIXED,
            units=[
                BoundaryUnit(
                    unit_id="u1",
                    granularity=Granularity.FILE,
                    path="src/a.py",
                )
            ],
            boundaries=[
                BoundaryDef(
                    boundary_id="b1",
                    name="b1",
                    granularity=Granularity.FILE,
                )
            ],
            memberships=[Membership(unit_id="u1", boundary_id="b1", weight=1.0)],
            metadata={"source": "test"},
        )
        return model, []


@dataclass
class _FakeParser:
    backend_id: str = "fake.parser.v1"
    backend_version: str = "v1"

    def parse_snapshot(self, *, root, paths):  # type: ignore[no-untyped-def]
        return ParserRunResult(
            backend_id=self.backend_id,
            backend_version=self.backend_version,
            files=[
                ParsedFileSignals(
                    path="src/a.py",
                    language="python",
                    imports=[ParsedImport(module="typing")],
                    functions=[ParsedFunction(name="f")],
                )
            ],
            diagnostics=[],
        )


def test_boundary_strategy_registry_supports_runtime_registration() -> None:
    register_boundary_strategy(
        strategy_id="fake.strategy.v1",
        factory=_FakeStrategy,
        aliases=("fake",),
    )
    loaded = get_boundary_strategy("fake")
    assert loaded.strategy_id == "fake.strategy.v1"
    assert "fake.strategy.v1" in available_boundary_strategies()


def test_parser_registry_supports_runtime_registration() -> None:
    register_parser_backend(
        backend_id="fake.parser.v1",
        factory=_FakeParser,
        aliases=("fake-parser",),
    )
    loaded = get_parser_backend("fake-parser")
    assert loaded.backend_id == "fake.parser.v1"
    assert "fake.parser.v1" in available_parser_backends()
