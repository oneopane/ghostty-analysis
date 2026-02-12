from __future__ import annotations

from pathlib import Path
from typing import Protocol

from .models import ParserRunResult


class BoundaryParserBackend(Protocol):
    backend_id: str
    backend_version: str

    def parse_snapshot(self, *, root: Path, paths: list[str]) -> ParserRunResult: ...
