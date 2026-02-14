from __future__ import annotations

import subprocess
import sys


def main() -> int:
    cmd = [
        "uv",
        "run",
        "--with",
        "mkdocs",
        "--with",
        "mkdocs-material",
        "mkdocs",
        "build",
    ]
    try:
        return subprocess.call(cmd)
    except FileNotFoundError:
        print("error: uv is not installed or not on PATH", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
