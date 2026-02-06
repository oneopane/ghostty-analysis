from __future__ import annotations

from datetime import datetime

from ...inputs.models import PRInputBundle
from .schemas import FeatureExtractionContext


def is_draft_at_cutoff(ctx: FeatureExtractionContext) -> bool:
    """Feature #26: PR draft status at cutoff.

    SQL derivation:
    - Query `pull_request_draft_intervals` active at cutoff.
    - Join start/end events for interval predicate.
    """
    raise NotImplementedError


def pr_age_seconds_at_cutoff(input: PRInputBundle) -> float:
    """Feature #27: PR age at cutoff.

    Derivation:
    - `input.cutoff - input.snapshot.created_at` in seconds (>=0), if created_at present.
    """
    raise NotImplementedError


def time_since_last_head_update_seconds(ctx: FeatureExtractionContext) -> float | None:
    """Feature #28: recency of last head update before cutoff.

    SQL derivation:
    - `pull_request_head_intervals` joined with start events.
    - Find max start_event.occurred_at <= cutoff; subtract from cutoff.
    """
    raise NotImplementedError


def head_updates_pre_cutoff_count(ctx: FeatureExtractionContext) -> int:
    """Feature #29: number of head updates before cutoff.

    SQL derivation:
    - Count head interval starts with start_event.occurred_at <= cutoff.
    """
    raise NotImplementedError


def last_author_activity_pre_cutoff_seconds(ctx: FeatureExtractionContext) -> float | None:
    """Feature #30: recency of author activity before cutoff.

    SQL derivation:
    - For PR/repo + author_id, compute latest timestamp from events/comments/reviews <= cutoff.
    - Return cutoff minus latest activity in seconds.
    """
    raise NotImplementedError


def author_comment_count_pre_cutoff(ctx: FeatureExtractionContext) -> int:
    """Feature #31: author comments count before cutoff.

    SQL derivation:
    - `comments` where user_id == author_id and created_at <= cutoff for PR.
    """
    raise NotImplementedError


def non_author_comment_count_pre_cutoff(ctx: FeatureExtractionContext) -> int:
    """Feature #32: non-author comments before cutoff.

    SQL derivation:
    - `comments` where user_id != author_id and created_at <= cutoff for PR.
    """
    raise NotImplementedError


def review_count_pre_cutoff(ctx: FeatureExtractionContext) -> int:
    """Feature #33: submitted reviews before cutoff.

    SQL derivation:
    - `reviews` with submitted_at <= cutoff for PR.
    """
    raise NotImplementedError


def any_active_review_requests_at_cutoff(ctx: FeatureExtractionContext) -> bool:
    """Feature #34: whether any review request is active at cutoff.

    SQL derivation:
    - active rows in `pull_request_review_request_intervals` at cutoff.
    """
    raise NotImplementedError


def requested_users_count_at_cutoff(ctx: FeatureExtractionContext) -> int:
    """Feature #35: number of requested user reviewers at cutoff.

    SQL derivation:
    - active review request intervals with reviewer_type='User'.
    """
    raise NotImplementedError


def requested_teams_count_at_cutoff(ctx: FeatureExtractionContext) -> int:
    """Feature #36: number of requested teams at cutoff.

    SQL derivation:
    - active review request intervals with reviewer_type='Team'.
    """
    raise NotImplementedError


def reviewer_request_breadth(ctx: FeatureExtractionContext) -> int:
    """Feature #37: reviewer request breadth indicator.

    Derivation options:
    - count distinct reviewer types present (user/team), or
    - count distinct teams if team requests exist.
    """
    raise NotImplementedError


def requested_overlap_with_codeowners(
    ctx: FeatureExtractionContext,
    *,
    codeowner_logins: set[str],
    requested_user_logins: set[str],
) -> bool:
    """Feature #38: request includes a CODEOWNER.

    Derivation:
    - compute overlap(requested users, matched owners from pinned CODEOWNERS).
    """
    raise NotImplementedError


def mentions_overlap_with_requests(
    *,
    mentioned_logins: set[str],
    requested_user_logins: set[str],
) -> bool:
    """Feature #39: mention/request overlap.

    Derivation:
    - set intersection between title/body mentions and requested reviewers.
    """
    raise NotImplementedError


def title_has_wip_signal(input: PRInputBundle) -> bool:
    """Feature #40: WIP / DO NOT REVIEW heuristic.

    Derivation:
    - case-insensitive string matching on title text.
    """
    raise NotImplementedError


def build_pr_timeline_features(
    input: PRInputBundle,
    *,
    data_dir: str,
    codeowner_logins: set[str] | None = None,
) -> dict[str, int | float | bool]:
    """Assemble timeline/as-of features (#26-#40).

    High-level implementation plan:
    - Use cutoff-bounded SQL helpers for interval/event-backed features.
    - Use bundle text fields for pure string heuristics.
    - Return deterministic flat keys (`pr.timeline.*`).
    """
    raise NotImplementedError


def _seconds_between(later: datetime, earlier: datetime | None) -> float | None:
    """Helper skeleton for recency features.

    Implement as a deterministic arithmetic helper used by #28/#30.
    """
    raise NotImplementedError
