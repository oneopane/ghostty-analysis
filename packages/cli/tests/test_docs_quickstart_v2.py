from pathlib import Path


def test_quickstart_mentions_artifacts_and_backfill() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    quickstart = repo_root / "docs" / "quickstart.md"
    assert quickstart.exists()
    text = quickstart.read_text(encoding="utf-8")
    assert "repo artifacts list" in text
    assert "repo backfill semantic" in text
