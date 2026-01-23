import subprocess

import pytest

from gh_history_ingestion.github.auth import select_auth_token


def test_auth_prefers_gh_token(monkeypatch):
    class Result:
        returncode = 0
        stdout = "ghp_123\n"

    monkeypatch.setenv("GITHUB_TOKEN", "env_token")
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: Result())
    assert select_auth_token() == "ghp_123"


def test_auth_falls_back_to_env_when_gh_unavailable(monkeypatch):
    def raise_error(*args, **kwargs):
        raise FileNotFoundError()

    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "env_token")
    monkeypatch.setattr(subprocess, "run", raise_error)
    assert select_auth_token() == "env_token"


def test_auth_raises_without_token(monkeypatch):
    def raise_error(*args, **kwargs):
        raise FileNotFoundError()

    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setattr(subprocess, "run", raise_error)
    with pytest.raises(RuntimeError):
        select_auth_token()
