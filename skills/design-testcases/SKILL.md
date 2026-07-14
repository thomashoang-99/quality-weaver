---
name: design-testcases
description: Use when approved coverage needs an exact-consumption outline and traceable detailed manual test cases.
---

# Design Test Cases

Design only from approved included coverage. Return newly discovered coverage to coverage review instead of adding it silently.

## Contract

**Input artifacts and read paths:** Read `<project-path>/.quality-weaver/normalized/requirements.yaml`, `<project-path>/.quality-weaver/coverage/ledger.yaml`, `<project-path>/.quality-weaver/coverage/test-map.md`, `<plugin-root>/schemas/test-outline.schema.json`, and `<plugin-root>/schemas/testcase.schema.json`.

**Allowed state:** Require coverage approved and testcases draft in `quality-weaver status <project-path>`.

**CLI validation command:** Run `quality-weaver outline validate <project-path>/.quality-weaver/coverage/ledger.yaml <project-path>/.quality-weaver/tests/outlines/test-outline.yaml`, then run `quality-weaver testcases validate <project-path>/.quality-weaver/coverage/ledger.yaml <project-path>/.quality-weaver/tests/outlines/test-outline.yaml <project-path>/.quality-weaver/tests/detailed/testcases.yaml`. After both pass, run `quality-weaver testcases render <project-path>/.quality-weaver/tests/detailed/testcases.yaml --out <project-path>/.quality-weaver/tests/detailed/testcases.md`, then validate the canonical artifact with `quality-weaver testcases validate <project-path>/.quality-weaver/coverage/ledger.yaml <project-path>/.quality-weaver/tests/outlines/test-outline.yaml <project-path>/.quality-weaver/tests/detailed/testcases.md`.

**Output artifact:** Produce `<project-path>/.quality-weaver/tests/outlines/test-outline.yaml`, use `<project-path>/.quality-weaver/tests/detailed/testcases.yaml` only as the model working artifact, and produce `<project-path>/.quality-weaver/tests/detailed/testcases.md` as canonical Markdown. The canonical Markdown is the source of truth.

**Blocking findings:** Stop for uncovered or multiply consumed included coverage, excluded or unknown coverage references, outline mismatches, invalid traceability, unobservable expectations, unresolved blocking clarifications, newly discovered coverage, or any state/input failure.

**Retry limit:** Model artifact validation retries: 2 per current outline or testcase artifact, only for actionable validation findings. Do not retry state, permission, stale approval, or unresolved clarification failures.

**Next human gate:** On normal success, present validated canonical Markdown and traceability for Gate 3; the human may run `quality-weaver approve testcases <project-path>` only after review. If new coverage is discovered, stop testcase outputs and return to Gate 2: tell the human to run `quality-weaver reopen coverage <project-path>`, revise and validate the ledger, render the Test Map, approve coverage, then restart testcase design.

## Workflow

1. Create a concise outline that consumes each included ledger item exactly once.
2. Validate the outline; revise only actionable model-artifact findings within the limit.
3. Create detailed cases from the valid outline with numbered single-action steps and observable results.
4. Validate the YAML working artifact, render canonical Markdown through the CLI, validate the Markdown again, and report traceability.

Do not add coverage absent from the approved ledger. Do not continue outline, testcase, or Markdown outputs after discovering new coverage. Do not run reopen or approval commands; they are human actions. Do not embed or restate schemas. Do not calculate Test Map values. Do not write `<project-path>/.quality-weaver/state.json`; only the CLI owns state. Do not approve a gate or run the approval command.
