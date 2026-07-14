---
name: plan-coverage
description: Use when approved normalized requirements need viewpoint applicability decisions and a reviewable coverage plan.
---

# Plan Coverage

Author Coverage Ledger decisions from requirement evidence and the repository catalog. Delegate validation and the Test Map projection to the CLI.

## Contract

**Input artifacts and read paths:** Read `.quality-weaver/normalized/requirements.yaml`, `.quality-weaver/config.yaml`, `schemas/coverage-ledger.schema.json`, `viewpoints/catalog.yaml`, and only the routed `viewpoints/**/*.yaml` files.

**Allowed state:** Require requirements approved and coverage draft in `quality-weaver status <project-path>`.

**CLI validation command:** Run `quality-weaver coverage validate .quality-weaver/coverage/ledger.yaml --catalog viewpoints --requirement-id <requirement-id> --target <requirement-id>=<target-id>` with every requirement and target lookup repeated as needed. After validation, run `quality-weaver testmap render .quality-weaver/coverage/ledger.yaml --out .quality-weaver/coverage/test-map.md --catalog viewpoints --requirement-id <requirement-id> --target <requirement-id>=<target-id>` with the same lookup set.

**Output artifact:** Produce `.quality-weaver/coverage/ledger.yaml` as the source of truth and `.quality-weaver/coverage/test-map.md` as its CLI-rendered review projection.

**Blocking findings:** Stop for invalid or duplicate coverage, unknown requirement, target, or viewpoint IDs, conflicting decisions, unsupported inclusions, unresolved clarification, missing high-risk coverage, or any state/input failure.

**Retry limit:** Model artifact validation retries: 2, only for actionable Coverage Ledger validation findings. Do not retry state, permission, catalog, or unresolved clarification failures.

**Next human gate:** Present the CLI-rendered Test Map and ledger findings. The human may run `quality-weaver approve coverage <project-path>` only after review.

## Workflow

1. Route normalized entities through `viewpoints/catalog.yaml`; load detailed rows only from routed groups.
2. Record include, exclude, or needs-clarification decisions with evidence in the ledger.
3. Run the exact coverage validator and revise at most twice for actionable model-artifact findings.
4. Render the Test Map only after valid coverage and hand both artifacts to the human.

The Test Map is only the CLI-rendered projection. Do not calculate Test Map values or edit the projection as coverage input. Do not embed schemas or viewpoint rows. Do not write `.quality-weaver/state.json`; only the CLI owns state. Do not approve a gate or run the approval command.
