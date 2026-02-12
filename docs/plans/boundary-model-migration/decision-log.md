# Decision Log: Boundary Model Migration

Status legend: `Proposed` / `Accepted` / `Deferred` / `Superseded`

## D-001 — Replace area with boundary abstraction
- **Status:** Accepted
- **Date:** 2026-02-11
- **Decision:** Remove area-first conceptual model and adopt boundary-first model as the routing substrate.
- **Rationale:** Area labels are path-only and insufficient for structural inference, overlap, and mixed membership.
- **Alternatives considered:** keep area + add optional boundary adapter (rejected: unnecessary compatibility complexity).

## D-002 — Architecture option C (hybrid multi-view) as primary path
- **Status:** Accepted
- **Date:** 2026-02-11
- **Decision:** Implement hybrid inference combining path/co-change signals in v1, then parser signals as additive channels.
- **Rationale:** Best balance between immediate value (existing data) and long-term structural power.
- **Alternatives considered:**
  - A-only deterministic co-change/path (rejected as end-state; kept as fallback layer)
  - B-only parser-first (rejected for initial rollout risk and data dependency)

## D-003 — v1 hard partition required at file level
- **Status:** Accepted
- **Date:** 2026-02-11
- **Decision:** Boundary model v1 always emits a deterministic hard file partition.
- **Rationale:** guarantees complete coverage and stable downstream behavior.
- **Note:** mixed memberships are also emitted in v1 where available.

## D-004 — Granularity support contract
- **Status:** Accepted
- **Date:** 2026-02-11
- **Decision:** model supports repo/dir/file/symbol/function in schema from day one.
- **Rationale:** avoid rework in schema evolution and plugin contracts.
- **Execution detail:** symbol/function inference may be empty for unsupported languages, but schema remains stable.

## D-005 — Parser support as first-class plugin interface
- **Status:** Accepted
- **Date:** 2026-02-11
- **Decision:** define parser backend contract and registry independent of inference strategy implementation.
- **Rationale:** modular language coverage and clear ownership boundaries.

## D-006 — Minimal parser language set
- **Status:** Accepted
- **Date:** 2026-02-11
- **Decision:** initial parser backends: Python, Zig, TypeScript/JavaScript.
- **Rationale:** aligns with likely target repos and immediate practical utility.

## D-007 — Artifact storage path
- **Status:** Accepted
- **Date:** 2026-02-11
- **Decision:** persist boundary artifacts under:
  - `data/github/<owner>/<repo>/artifacts/routing/boundary_model/...`
- **Rationale:** consistent with existing artifact hierarchy and clear separation from eval run outputs.

## D-008 — Determinism and cutoff safety as hard gates
- **Status:** Accepted
- **Date:** 2026-02-11
- **Decision:** strategy promotion requires deterministic reproducibility and leak-safe cutoff behavior.
- **Rationale:** mandatory for evaluation comparability and policy safety.

## D-009 — Promotion metric
- **Status:** Accepted
- **Date:** 2026-02-11
- **Decision:** primary promotion metric = routing quality uplift (MRR/Hit@k) vs baseline, with required secondary gates (stability + interpretability + determinism).
- **Rationale:** routing performance is primary business outcome; safety and operability are non-negotiable constraints.

## D-010 — No backward compatibility layer for `areas.v1`
- **Status:** Accepted
- **Date:** 2026-02-11
- **Decision:** direct migration and renaming in active modules; no long-lived adapters.
- **Rationale:** codebase size is manageable; cleaner final architecture.

## D-011 — Source snapshot contract for parser channels
- **Status:** Proposed
- **Decision:** parser channels read only from pinned snapshot rooted at declared ref (`base_sha` or chosen as-of ref policy), never from live checkout by default.
- **Open points:** exact ref policy for comparison tasks (base-only vs base+head dual).

## D-012 — Boundary confidence policy
- **Status:** Proposed
- **Decision:** all boundary artifacts include confidence and coverage diagnostics by signal channel.
- **Open points:** define exact confidence computation and thresholds per strategy.

## Deferred Questions

1. Should symbol/function memberships be emitted when parse confidence < threshold, or withheld?
2. Should ownership signals (CODEOWNERS) remain a direct channel in boundary inference or only an external feature?
3. Do we require per-language parser reproducibility pinning at grammar revision level in manifest, or backend semantic version only?

## Superseded / Removed Concepts

- Path-only `area_for_path` as default conceptual boundary.
- `routing/area_overrides.json` as central routing structure signal.
- Area-only mixed-membership basis as the sole decomposition substrate.
