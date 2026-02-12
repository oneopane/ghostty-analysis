from __future__ import annotations

from datetime import datetime, timedelta, timezone

from evaluation_harness.truth_policy import TruthPolicySpec, builtin_truth_policy_specs
from evaluation_harness.truth_schema import (
    TruthResult,
    TruthResultDiagnostics,
    TruthResultProvenance,
    TruthResultStatus,
)


def test_truth_policy_spec_contract_has_required_fields() -> None:
    schema = TruthPolicySpec.model_json_schema()
    props = schema.get("properties", {})
    for key in (
        "id",
        "version",
        "target_kind",
        "window_seconds",
        "sources",
        "filters",
        "selector",
        "status_rules",
    ):
        assert key in props


def test_builtin_truth_policy_specs_validate_and_have_stable_hashes() -> None:
    specs = builtin_truth_policy_specs()
    assert {"first_response_v1", "first_approval_v1", "merger_v1", "hybrid_owner_v1"} <= set(specs)

    seen_hashes: set[str] = set()
    for pid, spec in specs.items():
        validated = TruthPolicySpec.model_validate(spec.model_dump(mode="json"))
        assert validated.id == pid
        digest = validated.stable_hash()
        assert len(digest) == 64
        assert digest not in seen_hashes
        seen_hashes.add(digest)


def test_truth_result_contract_round_trip() -> None:
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end = start + timedelta(hours=1)
    result = TruthResult(
        policy_id="first_response_v1",
        policy_version="v1",
        status=TruthResultStatus.observed,
        targets=["bob"],
        diagnostics=TruthResultDiagnostics(
            window_start=start,
            window_end=end,
            source_branch="reviews_or_review_comments",
            scanned_review_rows=1,
            scanned_review_comment_rows=1,
            eligible_candidates=1,
            data_gaps=[],
            notes=["contract test"],
        ),
        provenance=TruthResultProvenance(
            policy_hash="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
        ),
    )

    payload = result.model_dump(mode="json")
    decoded = TruthResult.model_validate(payload)
    assert decoded.targets == ["bob"]
    assert decoded.status == TruthResultStatus.observed
