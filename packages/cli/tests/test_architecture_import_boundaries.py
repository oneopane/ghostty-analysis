from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def _iter_python_files(base: Path) -> list[Path]:
    return sorted(p for p in base.rglob("*.py") if p.is_file())


def _collect_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
    return imports


def test_experimentation_uses_evaluation_api_surface_only() -> None:
    exp_src = ROOT / "packages/experimentation/src/experimentation"
    violations: list[str] = []
    for path in _iter_python_files(exp_src):
        for mod in _collect_imports(path):
            if mod == "evaluation_harness.runner":
                violations.append(f"{path}: forbidden import {mod}")
    assert not violations, "\n".join(violations)


def test_cli_avoids_deep_eval_and_inference_internal_imports() -> None:
    cli_src = ROOT / "packages/cli/src/repo_cli"
    allow_eval = {
        "evaluation_harness.cli.app",
    }
    allow_inference = {
        "repo_routing.cli.app",
    }
    violations: list[str] = []

    for path in _iter_python_files(cli_src):
        for mod in _collect_imports(path):
            if mod.startswith("evaluation_harness.") and mod not in allow_eval:
                violations.append(f"{path}: forbidden import {mod}")
            if mod.startswith("repo_routing.") and mod not in allow_inference:
                violations.append(f"{path}: forbidden import {mod}")

    assert not violations, "\n".join(violations)
