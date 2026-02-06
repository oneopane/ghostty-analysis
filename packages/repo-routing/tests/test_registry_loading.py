from __future__ import annotations

from pathlib import Path

from repo_routing.registry import RouterSpec, load_router, router_id_for_spec


def test_load_router_builtin_mentions() -> None:
    router = load_router(RouterSpec(type="builtin", name="mentions"))
    assert hasattr(router, "route")


def test_load_router_import_path_factory(tmp_path: Path, monkeypatch) -> None:
    mod = tmp_path / "fake_router_mod.py"
    mod.write_text(
        """
from datetime import datetime
from repo_routing.router.base import RouteResult

def make_router(config_path=None):
    class _R:
        def route(self, *, repo, pr_number, as_of, data_dir='data', top_k=5):
            return RouteResult(repo=repo, pr_number=pr_number, as_of=as_of, top_k=top_k)
    return _R()
""",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    spec = RouterSpec(
        type="import_path",
        name="fake",
        import_path="fake_router_mod:make_router",
    )
    router = load_router(spec)
    assert hasattr(router, "route")

    rid = router_id_for_spec(spec)
    assert rid.startswith("fake-router-mod-make-router-")
