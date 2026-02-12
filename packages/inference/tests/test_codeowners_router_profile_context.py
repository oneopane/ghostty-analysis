from __future__ import annotations

import json
from datetime import datetime, timezone

from repo_routing.history.models import PullRequestFile, PullRequestSnapshot
from repo_routing.inputs.models import PRInputBundle
from repo_routing.router.baselines.codeowners import CodeownersRouter


def test_codeowners_router_can_use_repo_profile_context(tmp_path) -> None:  # type: ignore[no-untyped-def]
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(
        json.dumps(
            {
                "kind": "repo_profile",
                "version": "v1",
                "identity": {
                    "owner": "acme",
                    "repo": "widgets",
                    "pr_number": 1,
                    "cutoff": "2024-01-01T00:00:00Z",
                    "base_sha": "deadbeef",
                    "schema_version": "v1",
                    "builder_version": "repo_profile_builder.v1",
                },
                "artifact_manifest": {"files": []},
                "ownership_graph": {
                    "nodes": [
                        {
                            "node_id": "person:bob",
                            "kind": "person",
                            "name": "bob",
                            "provenance": [{"path": ".github/CODEOWNERS"}],
                            "confidence": 1.0,
                        }
                    ],
                    "edges": [
                        {
                            "relation": "OWNS",
                            "source_node_id": "person:bob",
                            "path_glob": "src/*",
                            "boundary": "src",
                            "target_node_id": None,
                            "provenance": [{"path": ".github/CODEOWNERS", "line": 1}],
                            "confidence": 1.0,
                        }
                    ],
                },
                "boundary_model": {"boundaries": []},
                "policy_signals": {"signals": []},
                "vocabulary": {
                    "labels": [],
                    "template_fields": [],
                    "keywords": [],
                },
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    changed_files = [PullRequestFile(path="src/main.py")]
    snapshot = PullRequestSnapshot(
        repo="acme/widgets",
        number=1,
        pull_request_id=100,
        base_sha=None,
        changed_files=changed_files,
    )
    bundle = PRInputBundle(
        repo="acme/widgets",
        pr_number=1,
        cutoff=datetime(2024, 1, 1, tzinfo=timezone.utc),
        snapshot=snapshot,
        changed_files=changed_files,
        repo_profile_path=str(profile_path),
        repo_profile_qa={"coverage": {"codeowners_present": True}},
    )

    router = CodeownersRouter(
        enabled=True,
        codeowners_at_base_sha=lambda repo, base_sha, data_dir: None,
    )
    result = router.route(
        repo="acme/widgets",
        pr_number=1,
        as_of=datetime(2024, 1, 1, tzinfo=timezone.utc),
        input_bundle=bundle,
    )

    assert result.candidates
    assert result.candidates[0].target.name == "bob"
    assert "source=repo_profile" in result.notes
