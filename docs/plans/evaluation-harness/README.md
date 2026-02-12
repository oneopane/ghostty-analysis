# Evaluation Implementation Plan

This plan tracks the work to build a leakage-safe, offline evaluation for routing and policy signals.

## Pinned Defaults (v0)

These are the design defaults we agreed to use unless a run overrides them via config/CLI:

- Goal: report both routing accuracy and queue metrics (no single scalar).
- Scope: start with `ghostty`, keep everything repo-agnostic.
- Evaluation mode: strict streaming evaluation ordered by per-PR cutoff time.
- Cutoff anchor (default): `created_at`.
  - Supported alternates: `ready_for_review` (when available), `created_at + delta`.
- Truth signals:
  - Behavior truth (primary): first non-author, non-bot review submission.
  - Intent truth (secondary): requested reviewers/teams within 60 minutes of cutoff.
- Filtering:
  - Exclude bots and PR author from candidates and truths.
- Candidate pool default:
  - Users/teams observed as reviewers or commenters in the last 180 days (as-of cutoff).
  - Optionally include CODEOWNERS-derived candidates when CODEOWNERS is read as-of base SHA.
- Routing output default:
  - Evaluate `top_k=5` (hit@1/3/5, MRR) and also store full scored lists in per-PR artifacts.
- Run outputs:
  - `manifest.json`, `report.md`, `report.json`, `per_pr.jsonl` under `data/github/<owner>/<repo>/eval/<run_id>/`.

Conventions:
- Each task is atomic and tracked in its own file.
- Mark tasks complete by checking the box in this index (and optionally in the task file).

## Phase 0 - Prerequisites (Blocking)

- [x] [001 - Add PR changed files signal to history DB](001-add-pr-changed-files-signal.md)
- [x] [002 - Ensure reviewer/commenter truth signals exist for the eval window](002-ensure-truth-signals.md)

## Phase 1 - Routing/Eval Interfaces (inference)

- [x] [003 - Define strict as-of HistoryReader contract](003-historyreader-contract.md)
- [x] [004 - Define Router interface + RouteResult schema](004-router-interface.md)
- [x] [005 - Implement offline baselines behind Router API](005-baselines.md)
- [x] [006 - Implement routing artifact builders (optional v0)](006-artifact-builders.md)
- [x] [007 - Extend inference CLI commands](007-repo-routing-cli.md)

## Phase 2 - Evaluation Core (evaluation)

- [x] [008 - Define eval config + report schemas](008-eval-config-and-models.md)
- [x] [009 - Implement cutoff policy](009-cutoff-policy.md)
- [x] [010 - Implement deterministic sampling](010-sampling.md)
- [x] [011 - Implement truth extraction](011-truth-extraction.md)
- [x] [012 - Implement routing agreement metrics](012-metrics-routing-agreement.md)
- [x] [013 - Implement gate correlation metrics](013-metrics-gates.md)
- [x] [014 - Implement queue metrics (TTFR/TTFC)](014-metrics-queue.md)
- [x] [015 - Implement report aggregation + formatting](015-reporting.md)
- [x] [016 - Implement run output layout + manifests](016-run-output-and-manifest.md)
- [x] [017 - Implement streaming evaluator (leakage-safe)](017-streaming-evaluator.md)

## Phase 3 - CLI (repo evaluation)

- [x] [018 - Add repo evaluation commands (run/show/explain/list)](018-eval-cli.md)
- [x] [019 - Validate unified CLI wiring](019-repo-cli-wiring.md)

## Phase 4 - Tests, Fixtures, Guardrails

- [x] [020 - Add synthetic DB fixture builder](020-test-fixture-db-builder.md)
- [x] [021 - Add cutoff tests](021-tests-cutoff.md)
- [x] [022 - Add routing agreement unit tests](022-tests-routing-agreement.md)
- [x] [023 - Add end-to-end eval run test](023-tests-end-to-end.md)
- [x] [024 - Add leakage + bot filtering guardrail tests](024-tests-guardrails.md)
- [x] [025 - Ensure unique test module names across packages](025-tests-unique-names.md)

## Phase 5 - Docs

- [x] [026 - Add evaluation runbook + metric definitions](026-docs-runbook-metrics.md)
- [x] [027 - Document baseline limitations (CODEOWNERS leakage warnings)](027-docs-baselines.md)
