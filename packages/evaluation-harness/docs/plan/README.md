# Evaluation Harness Implementation Plan

This plan tracks the work to build a leakage-safe, offline evaluation harness for routing and policy signals.

Conventions:
- Each task is atomic and tracked in its own file.
- Mark tasks complete by checking the box in this index (and optionally in the task file).

## Phase 0 - Prerequisites (Blocking)

- [ ] [001 - Add PR changed files signal to history DB](001-add-pr-changed-files-signal.md)
- [ ] [002 - Ensure reviewer/commenter truth signals exist for the eval window](002-ensure-truth-signals.md)

## Phase 1 - Routing/Eval Interfaces (repo-routing)

- [ ] [003 - Define strict as-of HistoryReader contract](003-historyreader-contract.md)
- [ ] [004 - Define Router interface + RouteResult schema](004-router-interface.md)
- [ ] [005 - Implement offline baselines behind Router API](005-baselines.md)
- [ ] [006 - Implement routing artifact builders (optional v0)](006-artifact-builders.md)
- [ ] [007 - Extend repo-routing CLI commands](007-repo-routing-cli.md)

## Phase 2 - Evaluation Harness Core (evaluation-harness)

- [ ] [008 - Define eval config + report schemas](008-eval-config-and-models.md)
- [ ] [009 - Implement cutoff policy](009-cutoff-policy.md)
- [ ] [010 - Implement deterministic sampling](010-sampling.md)
- [ ] [011 - Implement truth extraction](011-truth-extraction.md)
- [ ] [012 - Implement routing agreement metrics](012-metrics-routing-agreement.md)
- [ ] [013 - Implement gate correlation metrics](013-metrics-gates.md)
- [ ] [014 - Implement queue metrics (TTFR/TTFC)](014-metrics-queue.md)
- [ ] [015 - Implement report aggregation + formatting](015-reporting.md)
- [ ] [016 - Implement run output layout + manifests](016-run-output-and-manifest.md)
- [ ] [017 - Implement streaming evaluator (leakage-safe)](017-streaming-evaluator.md)

## Phase 3 - CLI (repo eval)

- [ ] [018 - Add repo eval commands (run/show/explain/list)](018-eval-cli.md)
- [ ] [019 - Validate unified CLI wiring](019-repo-cli-wiring.md)

## Phase 4 - Tests, Fixtures, Guardrails

- [ ] [020 - Add synthetic DB fixture builder](020-test-fixture-db-builder.md)
- [ ] [021 - Add cutoff tests](021-tests-cutoff.md)
- [ ] [022 - Add routing agreement unit tests](022-tests-routing-agreement.md)
- [ ] [023 - Add end-to-end eval run test](023-tests-end-to-end.md)
- [ ] [024 - Add leakage + bot filtering guardrail tests](024-tests-guardrails.md)
- [ ] [025 - Ensure unique test module names across packages](025-tests-unique-names.md)

## Phase 5 - Docs

- [ ] [026 - Add evaluation runbook + metric definitions](026-docs-runbook-metrics.md)
- [ ] [027 - Document baseline limitations (CODEOWNERS leakage warnings)](027-docs-baselines.md)
