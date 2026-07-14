---
name: initialize
description: Use when an existing project directory needs a new QualityWeaver workspace before requirement analysis begins.
---

# Initialize QualityWeaver

Initialize only through the CLI so workspace files and state begin consistently.

## Contract

**Input artifacts and read paths:** `<project-path>` must be an existing project directory.

**Allowed state:** No `<project-path>/.quality-weaver/` workspace exists.

**CLI validation command:** Run `quality-weaver init <project-path>`, then run `quality-weaver status <project-path>` and require a successful requirements-draft status.

**Output artifact:** `<project-path>/.quality-weaver/config.yaml`, with the remaining workspace structure managed by the CLI.

**Blocking findings:** Stop for a missing or non-directory project path, an existing workspace, a permission failure, or any nonzero CLI result.

**Retry limit:** Model artifact validation retries: 0. Initialization failures are not model artifact validation failures.

**Next human gate:** Ask the human to provide or confirm the Markdown requirement inputs for requirement analysis. No approval is due yet.

## Guardrails

- Do not create the project directory or workspace files by hand.
- Do not write `<project-path>/.quality-weaver/state.json`; only the CLI owns state.
- Do not approve a gate; only report the next human decision.
