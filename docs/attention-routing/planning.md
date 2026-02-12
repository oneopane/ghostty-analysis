# Attention Routing: Planning

## 1. Executive Summary
- **North-star outcomes**
  - Lower **time-to-first-response (TTFR)** and faster initial triage loop.
  - Higher **correct ownership** (right team/user engaged earlier).
  - Lower **attention cost** (fewer unnecessary pings per PR).
- **Phase focus**
  - Build **routing/control** (D0–D3) first.
  - Defer planning/copilot behaviors (D4 split suggestions) to later.

## 2. System Scope & Non-goals
- **In scope (attention-routing)**
  - Decide if a PR is routable now.
  - Infer likely ownership/boundaries.
  - Rank reviewer/team candidates.
  - Trigger control actions (nudge/escalate/how many to ping).
- **Out of scope (near-term)**
  - Optimizing long-term code quality or merge strategy directly.
  - Solving org staffing/rotation policy design.
  - Auto-splitting code changes (D4 planning assistance).
- **Unit of decision**
  - Primary: **PR at cutoff** (`repo`, `pr_number`, `cutoff`).
  - Near-future extension: **PR segment / split-PR suggestion**.
  - Targets: **team** and **user** levels (team→user expansion versioned).

## 3. Decision Pipeline (D0–D4)
- **D0: Triage viability**
  - Is this PR in-scope, ready, and sized for normal routing?
- **D1: Ownership/boundary inference**
  - Which boundaries/modules and how confident is ownership coverage?
- **D2: Candidate ranking (team/user)**
  - Who should be pinged first under candidate constraints?
- **D3: Control policy (nudge/escalate/ping size)**
  - When to escalate; how many candidates to request; who to re-route.
- **D4: Planning assistance**
  - Split suggestions / decomposition hints.
  - **Explicitly out of near-term scope**.

## 4. Prediction Task Portfolio (Core Section)
- Portfolio covers 10 tasks mapped to D0–D3:
  - **D0**: T01 out-of-scope, T02 readiness, T03 oversized PR.
  - **D1**: T04 ownership coverage confidence, T05 boundary/module multi-label.
  - **D2**: T06 first-responder routing, T07 owner-constrained routing.
  - **D2/D3**: T08 candidate availability/non-response.
  - **D3**: T09 stall-risk escalation, T10 reviewer set sizing.
- Principle: stage-gated decisions; later stages consume earlier outputs with confidence.
- **Hard rule**: every task ships with at least one **non-ML baseline** (required for promotion).

## 5. Shared Data Contracts & Leakage Policy
- **As-of cutoff semantics**
  - Every input must be computable from records with timestamp/event ordering `<= cutoff`.
  - No post-cutoff labels/features in model inputs.
- **Interval tables + pinned artifacts**
  - Use interval tables for state at cutoff (`issue_content_intervals`, `pull_request_draft_intervals`, `pull_request_head_intervals`, `pull_request_review_request_intervals`, etc.).
  - Use pinned repo artifacts at cutoff SHAs:
    - `codeowners/<base_sha>/CODEOWNERS`
    - `artifacts/routing/boundary_model/<strategy_id>/<cutoff_key>/...`
    - snapshot artifacts (`snapshot.json`, `inputs.json`) tied to run manifest.
- **Candidate generation versioning + evaluation coupling**
  - Candidate set is a versioned contract (e.g., `candidate_gen_version=v1`).
  - Include sources: requested users/teams, CODEOWNERS owners, historically active participants, mention-derived candidates.
  - Offline eval must record and score against the exact candidate-gen version.
- **Leakage checklist (“human-knowable at cutoff” tests)**
  - Could a human observer at cutoff know this value?
  - Does value change if post-cutoff events are removed?
  - Does feature encode observed responder/outcome indirectly?
  - Is file/context loaded from pinned SHA artifacts (not current checkout)?
  - Is any merged/closed/final-state field excluded from inputs?

## 6. Evaluation Framework
- **Dataset construction**
  - Build examples per PR cutoff policy (`created_at` default; optional `ready_for_review`).
  - Use time-based splits (train/valid/test) plus held-out repo splits where feasible.
  - Keep deterministic manifests and schema versions.
- **Slice analysis (required)**
  - By repo, boundary/module, PR size, ownership coverage bucket, and requested vs unrequested candidates.
- **Calibration requirements**
  - Required for probability-trigger tasks: **T04, T08, T09, T10**.
  - Why: thresholds drive control actions (escalate/ping counts), so probability reliability matters.
- **Counterfactual flags + restrictions (intervention tasks)**
  - Mark tasks requiring action-policy inference (T08/T09/T10) with `counterfactual_risk=true`.
  - Restrict primary offline claims to observationally supported subsets (e.g., requested candidates).
  - Require policy simulation disclaimers; no causal claims without dedicated design.
- **Global outcome metrics (program-level)**
  - **TTFR**
  - **Owner-correctness**
  - **Pings/PR**
  - **Reroute rate**

## 7. Prioritization & Roadmap
- **Rubric (1–5 each)**
  - `Priority = (Labelability + HarnessFit + Actionability + Leverage) - (Risk + EngCost)`
- **Ranked top 5 (in order)**
  1. **T06** First-responder routing
  2. **T08** Candidate availability/non-response
  3. **T07** Owner-constrained routing
  4. **T09** Stall-risk escalation trigger
  5. **T04** Ownership coverage confidence
- **Milestones (owners TBD)**
  - M1: Data contracts + label builders locked (T06/T07/T08/T09/T04).
  - M2: Baselines + offline harness reports for top 5.
  - M3: Shadow-mode routing/control dashboard.
  - M4: Assistive rollout with thresholds and guardrails.
- **Kill criteria (explicit)**
  - If a task cannot beat trivial baseline on primary metric across key slices.
  - If calibration error remains above agreed threshold for control tasks.
  - If projected pings/PR increases without TTFR or owner-correctness gain.

## 8. Rollout Strategy
- **Phase 1: Shadow**
  - Generate decisions and evidence only; no user-facing actions.
- **Phase 2: Assistive**
  - Show ranked recommendations + escalation suggestions to humans.
- **Phase 3: Constrained automation**
  - Auto-apply low-risk actions under strict thresholds and fallback rules.
- **Monitoring / guardrails**
  - Spam rate (excess pings)
  - Fairness/load balance across teams/users
  - Reroute rate
  - Regression alarms on TTFR, owner-correctness, and calibration drift

## 9. Open Risks & Questions
- **Known risks**
  - Ground-truth mismatch (observed responder vs best owner)
  - Counterfactual bias for intervention tasks
  - Label inconsistency across repos/processes
  - Candidate-generation drift across versions
  - Team→user expansion noise
- **High-value open questions (max 5)**
  1. TODO: What is the default response SLA window per repo tier (e.g., 24h vs 48h)?
  2. TODO: How should team requests be expanded to users when multiple rosters exist?
  3. TODO: Which owner-correctness definition is canonical (strict CODEOWNERS vs boundary policy)?
  4. TODO: What minimum calibration quality gates are required before assistive launch?
  5. TODO: How should reroute actions be attributed when multiple nudges occur?
