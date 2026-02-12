import os
import subprocess


def select_auth_token() -> str:
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            check=False,
            capture_output=True,
            text=True,
        )
        token = (result.stdout or "").strip()
        if result.returncode == 0 and token:
            return token
    except FileNotFoundError:
        pass

    token = os.getenv("GITHUB_TOKEN")
    if token:
        return token

    raise RuntimeError(
        "No GitHub token found. Run `gh auth login` or set GITHUB_TOKEN."
    )
