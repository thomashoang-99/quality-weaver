---
name: status
description: Use when an initialized QualityWeaver project needs its gate states, stale conditions, or next legal action reported.
---

# Report QualityWeaver Status

Treat CLI output as the authoritative workflow snapshot. Report it without inferring or advancing state.

## Contract

**Input artifacts and read paths:** Accept `<project-path>` and confirm `.quality-weaver/config.yaml` exists; query state only through the CLI.

**Allowed state:** Any initialized QualityWeaver state, including draft, approved, or stale gates.

**CLI validation command:** Run exactly `quality-weaver status <project-path>` once and use that single snapshot.

**Output artifact:** Return the requirements, coverage, and testcases statuses plus the CLI-reported `Next:` action as a read-only status report.

**Blocking findings:** Stop for a missing workspace, unreadable or invalid CLI-managed state, permission failure, or nonzero status result.

**Retry limit:** Model artifact validation retries: 0. Status is a deterministic read and state failures require correction.

**Next human gate:** Identify the human gate named by `Next:` or state that no approval remains. Do not execute the next action.

## Workflow

1. Run the status command once.
2. Preserve all three gate values and the exact next-action meaning.
3. Explain stale or blocked state only from CLI output and direct the human to the reported gate.

Do not read `.quality-weaver/state.json` directly. Do not write `.quality-weaver/state.json`; only the CLI owns state. Do not approve a gate, regenerate an artifact, or execute the reported next action.
