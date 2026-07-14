---
name: design-testcases
description: Use when approved coverage needs an exact-consumption outline and traceable detailed manual test cases.
---

# Design Test Cases

Design only from approved included coverage. Return newly discovered coverage to coverage review instead of adding it silently.

## Contract

**Input artifacts and read paths:** Read `.quality-weaver/normalized/requirements.yaml`, `.quality-weaver/coverage/ledger.yaml`, `.quality-weaver/coverage/test-map.md`, `schemas/test-outline.schema.json`, and `schemas/testcase.schema.json`.

**Allowed state:** Require coverage approved and testcases draft in `quality-weaver status <project-path>`.

**CLI validation command:** Run `quality-weaver outline validate .quality-weaver/coverage/ledger.yaml .quality-weaver/tests/outlines/test-outline.yaml`, then run `quality-weaver testcases validate .quality-weaver/coverage/ledger.yaml .quality-weaver/tests/outlines/test-outline.yaml .quality-weaver/tests/detailed/testcases.yaml`. After both pass, run `quality-weaver testcases render .quality-weaver/tests/detailed/testcases.yaml --out .quality-weaver/tests/detailed/testcases.md`.

**Output artifact:** Produce `.quality-weaver/tests/outlines/test-outline.yaml`, `.quality-weaver/tests/detailed/testcases.yaml`, and its deterministic `.quality-weaver/tests/detailed/testcases.md` rendering.

**Blocking findings:** Stop for uncovered or multiply consumed included coverage, excluded or unknown coverage references, outline mismatches, invalid traceability, unobservable expectations, unresolved blocking clarifications, newly discovered coverage, or any state/input failure.

**Retry limit:** Model artifact validation retries: 2 per current outline or testcase artifact, only for actionable validation findings. Do not retry state, permission, stale approval, or unresolved clarification failures.

**Next human gate:** Present validated traceability and rendered cases. The human may run `quality-weaver approve testcases <project-path>` only after review.

## Workflow

1. Create a concise outline that consumes each included ledger item exactly once.
2. Validate the outline; revise only actionable model-artifact findings within the limit.
3. Create detailed cases from the valid outline with numbered single-action steps and observable results.
4. Validate details, render Markdown through the CLI, and report traceability.

Do not add coverage absent from the approved ledger. Do not embed or restate schemas. Do not calculate Test Map values. Do not write `.quality-weaver/state.json`; only the CLI owns state. Do not approve a gate or run the approval command.
