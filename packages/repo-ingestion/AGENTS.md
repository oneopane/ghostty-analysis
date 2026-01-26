# Agent Notes

This repository uses:

- Python environment + dependencies: `uv`
- Version control: Jujutsu (`jj`) with a Git-compatible repo

## Python workflow (uv)

- Create/update the local venv: `uv venv`
- Install project deps (including test deps): `uv pip install -e .`
- Run tests: `uv run pytest`

Notes:

- Prefer `uv run <cmd>` over invoking `python` directly.
- Keep dependency changes in `pyproject.toml` and use `uv` to resolve/install.

## VCS workflow (jj)

- Prefer `jj` commands for day-to-day work (`jj status`, `jj diff`, `jj log`, `jj commit`).
- Avoid creating commits with `git commit` unless explicitly required.
