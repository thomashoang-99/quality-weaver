---
name: plan-coverage
description: Use when approved normalized requirements need viewpoint applicability decisions and a reviewable coverage plan.
---

# Plan Coverage

Author Coverage Ledger decisions from requirement evidence and the repository catalog. Delegate validation and the Test Map projection to the CLI.

## Contract

**Input artifacts and read paths:** Read `<project-path>/.quality-weaver/normalized/requirements.yaml`, `<project-path>/.quality-weaver/config.yaml`, `<plugin-root>/schemas/coverage-ledger.schema.json`, `<plugin-root>/viewpoints/catalog.yaml`, and only the routed `<plugin-root>/viewpoints/**/*.yaml` files.

**Allowed state:** Require requirements approved and coverage draft in `quality-weaver status <project-path>`.

**CLI validation command:** Run `quality-weaver coverage validate <project-path>/.quality-weaver/coverage/ledger.yaml --catalog <plugin-root>/viewpoints --requirement-id <requirement-id> --target <requirement-id>=<target-id>` with every requirement and target lookup repeated as needed. After validation, run `quality-weaver testmap render <project-path>/.quality-weaver/coverage/ledger.yaml --out <project-path>/.quality-weaver/coverage/test-map.md --catalog <plugin-root>/viewpoints --requirement-id <requirement-id> --target <requirement-id>=<target-id>` with the same lookup set.

**Output artifact:** Produce `<project-path>/.quality-weaver/coverage/ledger.yaml` as the source of truth and `<project-path>/.quality-weaver/coverage/test-map.md` as its CLI-rendered review projection.

**Blocking findings:** Treat these deterministic CLI codes as blocking: `COVERAGE_CATALOG_VERSION_MISMATCH`, `COVERAGE_DUPLICATE_KEY`, `COVERAGE_DUPLICATE_ID`, `COVERAGE_UNKNOWN_REQUIREMENT`, `COVERAGE_UNKNOWN_TARGET`, `COVERAGE_UNKNOWN_VIEWPOINT`, `COVERAGE_EVIDENCE_REQUIRED`, `COVERAGE_QUESTION_REQUIRED`, and `COVERAGE_UNRESOLVED`. Also stop for state, input, catalog, or permission failure.

**Retry limit:** Model artifact validation retries: 2, only for actionable Coverage Ledger validation findings. Do not retry state, permission, catalog, or unresolved clarification failures.

**Next human gate:** Present the CLI-rendered Test Map and ledger findings. The human may run `quality-weaver approve coverage <project-path>` only after review.

## Workflow

1. Route normalized entities through `<plugin-root>/viewpoints/catalog.yaml`; load detailed rows only from routed groups.
2. Record include, exclude, or needs-clarification decisions with evidence in the ledger.
3. Run the exact coverage validator and revise at most twice for actionable model-artifact findings.
4. Render the Test Map only after valid coverage and hand both artifacts to the human. Present semantic applicability, unsupported proposals, and high-risk concerns as the Model proposal and human Gate 2 review; do not claim the deterministic CLI evaluates them independently.

The Test Map is only the CLI-rendered projection. Do not calculate Test Map values or edit the projection as coverage input. Do not embed schemas or viewpoint rows. Do not write `<project-path>/.quality-weaver/state.json`; only the CLI owns state. Do not approve a gate or run the approval command.
