# Feature Brainstorming Substrate

## 1. Prediction Task (What are we modeling?)

- **Unit of prediction:**
  - One pull request evaluated at a specific cutoff timestamp (`repo`, `pr_number`, `cutoff`)

- **Decision/output:**
  - Ranked list of reviewer or maintainer candidates (users or teams)
  - Concrete output object: `RouteResult` with scored `RouteCandidate`s + evidence

- **Current operational truth:**
  - First eligible non-author, non-bot reviewer action after cutoff (current harness behavior label)
  - Also available as alternate framing: intent truth from active review requests near cutoff

- **Important framing notes:**
  - This is behavioral prediction, not normative “best reviewer”
  - Features that correlate with *who actually responds* are valid, even if imperfect
  - Candidate space includes explicit requests, owners, historically active participants, mention-derived users, etc.
  - Evaluation currently scores rank against observed responder, so “response propensity” is first-class


## 2. Snapshot of the World at Cutoff Time

This section defines everything that is knowable at prediction time.

### 2.1 Pull Request State (as-of)

Known at cutoff:
- PR title and body (interval-reconstructed where applicable)
- Author identity (`author_login`)
- Draft / ready state (via draft intervals if queried)
- Base SHA and head SHA (head via intervals)
- Changed files at head (`pull_request_files` keyed by head SHA)
- Active review requests (users and teams via intervals)
- Parsed gate fields from body (`issue`, `ai_disclosure`, `provenance`)
- PR creation time, number, repo identity

Conceptual dimensions this enables:
- Intent and scope
- Change size and complexity
- Explicit coordination signals
- Readiness/ambiguity from PR text and state
- “Who is being asked” vs “who typically responds”


### 2.2 Change Surface (Files and Churn)

Available data:
- File paths
- Change status (added / modified / deleted)
- Additions, deletions, total changes
- Deterministic per-file ordering in input bundle

Conceptual dimensions:
- Breadth vs depth of change
- Localized vs cross-cutting edits
- Hotspot vs cold files
- Ownership ambiguity
- Language/module mix proxies from path patterns


### 2.3 Codebase Structure (Pinned Context)

Pinned, as-of-safe artifacts:
- CODEOWNERS at base SHA (`codeowners/<base_sha>/CODEOWNERS`)
- Area / module mappings (`routing/area_overrides.json` + path-derived default area)

What this represents:
- Intended ownership and responsibility boundaries
- Social expectations for review
- Team/user responsibility priors independent of recent activity

Conceptual dimensions:
- Ownership coverage
- Number and overlap of owners
- Owner alignment with change surface
- Direct vs ambiguous ownership paths
- Team-level vs user-level routing pressure


### 2.4 People and Historical Behavior

Available historical signals (bounded by cutoff):
- Review history (`reviews`)
- Comment activity (`comments`)
- Review request history (`pull_request_review_request_intervals` + events)
- Author–reviewer interaction history
- Area- or file-level familiarity from past touched/reviewed paths
- Recency windows (e.g., last 7/30/90/180 days)
- User type for bot filtering (`users.type`)

Conceptual dimensions:
- Familiarity
- Availability
- Habitual behavior
- Load and responsiveness
- Social graph locality (author ↔ reviewer recurring edges)


### 2.5 Process and Coordination Signals

From events and intervals:
- Review request add/remove intervals and starts
- Draft state transitions
- PR head updates/synchronizations (via head intervals / event stream)
- Comment/review bursts around cutoff
- Label/assignee/milestone state as-of (if included)

Conceptual dimensions:
- Explicit vs implicit intent
- Escalation or re-request patterns
- PR readiness signals
- Coordination intensity and urgency
- “Stuckness” indicators before cutoff


## 3. Temporal Semantics and Safety Model

Core rule:
- All features must be computable strictly using data with timestamps ≤ cutoff

Mental leakage checks:
- Would this value change after cutoff?
- Does it depend on knowing who reviewed?
- Does it use post-cutoff merged/closed outcomes?
- Does it rely on current checkout instead of pinned artifacts?
- Would a human at cutoff plausibly know this?

If yes → feature is invalid.


## 4. Data Strengths, Biases, and Limitations

Strengths:
- Rich longitudinal behavior data (events + reviews/comments)
- File-level granularity with churn stats
- Deterministic reconstruction via interval tables
- Strong ownership metadata when CODEOWNERS exists
- Reproducible artifact pipeline (`snapshot.json`, `inputs.json`, `routes`, optional features/llm)

Known limitations:
- Ground truth is noisy/opportunistic (first responder ≠ best reviewer)
- Review behavior influenced by out-of-band channels (Slack, meetings, rotations)
- Automation and bots distort activity footprints
- Missing intent behind actions and unavailable context (PTO, org changes)
- Coverage variance across repos/time windows (sparse histories, missing snapshots)

Implication for features:
- Prefer aggregated and robust signals
- Use multiple temporal windows to reduce brittleness
- Treat rare event patterns as weak priors, not dominant drivers
- Separate “coordination signals” from “true expertise” signals in ablations


## 5. Feature Ideation Lenses (Primary Value Section)

Use these questions to generate feature candidates.

### 5.1 Familiarity
- Who has interacted with these files before?
- Who has reviewed similar PRs (area/path/churn profile)?
- Who frequently reviews PRs by this author?
- Is familiarity recent or stale?
- Is familiarity broad (many files) or deep (few hot files)?

### 5.2 Responsibility
- Who is listed as an owner for the touched areas?
- How concentrated or diffuse is ownership?
- Are owners overloaded or inactive?
- Are there conflicts between CODEOWNERS and observed historical responders?
- Do team-level owners need user-level expansion heuristics?

### 5.3 Availability
- Who has been active recently?
- Who tends to respond quickly?
- Who currently has open review requests (proxy load)?
- Is recent inactivity temporary or long-term?
- Are there cyclical patterns (day-of-week/hour-of-day in repo-local behavior)?

### 5.4 Scope Matching
- Is this PR within someone’s typical review size?
- Does it span multiple areas or teams?
- Is it unusually large or small?
- Does candidate historically handle cross-area PRs?
- Is there mismatch between PR complexity and candidate historical throughput?

### 5.5 Process Intent
- Are reviewers explicitly requested?
- Has anyone been re-requested?
- Is the PR transitioning out of draft?
- Are mention signals aligned with ownership/history or compensating for them?
- Do update bursts/head changes imply re-triage behavior?


## 6. Hard Constraints for Feature Design

- Offline-only computation
- SQLite history DB and pinned artifacts only
- No network or live repo access
- Deterministic outputs
- Compact evidence payloads (no large blobs)


## 7. How This Document Is Used

Intended workflow:
1. Pick a feature lens
2. Generate multiple candidate features
3. Check as-of safety and data source
4. Implement and log feature
5. Ablate and iterate

This document is a living brainstorming aid, not a static spec.
