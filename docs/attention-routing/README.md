# Attention Routing Docs

Primary architecture and onboarding doc:

- [architecture.md](./architecture.md)

Current implementation anchors (kept in sync with code):

- Shared router spec parsing/validation: `packages/inference/src/repo_routing/router_specs.py`
- Builtin router loading + config schema validation: `packages/inference/src/repo_routing/registry.py`
- Boundary strategy/parser registries with runtime registration hooks:
  - `packages/inference/src/repo_routing/boundary/inference/registry.py`
  - `packages/inference/src/repo_routing/boundary/parsers/registry.py`

Feature implementation and status:

- [feature-implementation-checklist.md](./feature-implementation-checklist.md)

Boundary model contracts:

- [boundary-model.md](./boundary-model.md)
- [boundary-language-support.md](./boundary-language-support.md)

Feature taxonomy + policy registries:

- [feature-registry.md](./feature-registry.md)

Relational taxonomy + policy boundary:

- [relation-taxonomy.md](./relation-taxonomy.md)
- [policy-signal-boundary.md](./policy-signal-boundary.md)

Decisions:

- [decisions/DEC-0001-routing-policy-baseline.md](./decisions/DEC-0001-routing-policy-baseline.md)

Traceability:

- [traceability/README.md](./traceability/README.md)

Exploration:

- [mixed-membership.md](./mixed-membership.md)

Related task/planning docs in this folder are historical and exploratory; use `architecture.md` and the registry/checklist docs above as the current implementation reference.
