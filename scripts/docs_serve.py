from __future__ import annotations

import argparse
import os
import subprocess
import sys


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Serve local MkDocs site")
    p.add_argument(
        "--host", default="127.0.0.1", help="Host interface (default: 127.0.0.1)"
    )
    p.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("DOCS_PORT", "8000")),
        help="Port (default: 8000 or $DOCS_PORT)",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    cmd = [
        "uv",
        "run",
        "--with",
        "mkdocs",
        "--with",
        "mkdocs-material",
        "mkdocs",
        "serve",
        "-a",
        f"{args.host}:{args.port}",
    ]
    try:
        return subprocess.call(cmd)
    except FileNotFoundError:
        print("error: uv is not installed or not on PATH", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
