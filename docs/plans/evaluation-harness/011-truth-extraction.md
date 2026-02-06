# 011 - Implement truth extraction

- [ ] Done

## Goal
Compute ground truth sets for evaluation, separately for intent vs behavior.

## Work
- Intent truth: requested reviewers/teams within a window after open (default 1h).
- Behavior truth: first non-author, non-bot review submitter.
- Participants: commenters/reviewers excluding author and bots.
- Outcome: merged vs closed/unmerged.

## Files
Create:
- `packages/evaluation-harness/src/evaluation_harness/truth/__init__.py`
- `packages/evaluation-harness/src/evaluation_harness/truth/requested_reviewers.py`
- `packages/evaluation-harness/src/evaluation_harness/truth/reviewers.py`
- `packages/evaluation-harness/src/evaluation_harness/truth/participants.py`
- `packages/evaluation-harness/src/evaluation_harness/truth/outcome.py`

## Acceptance Criteria
- Truth extraction is offline and uses only the DB.
- Bot filtering is explicit and reported.
