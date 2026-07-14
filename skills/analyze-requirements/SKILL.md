---
name: analyze-requirements
description: Use when Markdown requirements need normalized facts, evidence, risks, and clarification questions before coverage planning.
---

# Analyze Requirements

Normalize only supported Markdown evidence. Mark inference as an assumption or clarification candidate.

## Contract

**Input artifacts and read paths:** Read `<project-path>/.quality-weaver/config.yaml`, `<project-path>/<requirements-glob>`, and `<plugin-root>/schemas/requirement.schema.json`.

**Allowed state:** Require the requirements gate to be draft, as reported by `quality-weaver status <project-path>`.

**CLI validation command:** Run `quality-weaver status <project-path>` before writing, run `quality-weaver requirements validate <project-path>/.quality-weaver/normalized/requirements.yaml`, then run `quality-weaver status <project-path>` again; require requirements to remain draft.

**Output artifact:** Write `<project-path>/.quality-weaver/normalized/requirements.yaml` with source evidence and explicit assumptions or clarification candidates.

**Blocking findings:** Stop for unreadable or empty Markdown, schema-invalid output, contradictory evidence, or unresolved ambiguity that prevents faithful normalization.

**Retry limit:** Model artifact validation retries: 2, only when schema findings are actionable. Stop immediately for input, state, permission, or unresolved clarification findings.

**Next human gate:** Present the normalized facts, evidence, risks, and questions. The human may run `quality-weaver approve requirements <project-path>` only after review.

## Workflow

1. Read the configured Markdown inputs and the canonical requirement schema from the declared absolute path families.
2. Normalize typed entities and retain source locations; label every inference.
3. Run the public requirement validator and apply at most two actionable revisions.
4. Report blocking findings and wait for the requirement-analysis gate.

Do not embed or restate the schema. Do not write `<project-path>/.quality-weaver/state.json`; only the CLI owns state. Do not approve a gate or run the approval command.
