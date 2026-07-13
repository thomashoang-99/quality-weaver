# QualityWeaver v1 Design

**Date:** 2026-07-13
**Status:** Ready for user review

## 1. Product definition

QualityWeaver is a platform-independent, AI-assisted manual test design system. Version 1 transforms Markdown requirements into reviewed, traceable manual test cases and exports them as canonical Markdown or profile-driven Excel workbooks.

QualityWeaver supports both Codex and Claude Code. Agent platforms coordinate the workflow, while a shared deterministic core owns state transitions, validation, projections, and export behavior.

### Goals

- Accept Markdown requirements as the only v1 source format.
- Make reusable test viewpoints the central test-design knowledge base.
- Record project-specific coverage decisions in a machine-validatable Coverage Ledger.
- Generate a human-readable Test Map from approved coverage instead of asking a model to recreate test strategy.
- Use three human approval gates: requirement analysis, coverage design, and detailed test cases.
- Produce canonical Markdown test cases and optional Excel exports selected by profile.
- Allow a workflow started in Codex to continue in Claude Code, and vice versa, without relying on chat history.
- Reduce model-dependent variance through small context packets, stable schemas, deterministic validators, and traceable decisions.

### Non-goals for v1

- Reading DOCX, PDF, images, Jira, or external requirement systems.
- Generating Playwright, Appium, Selenium, or other automation code.
- Executing tests, healing automation, or reporting execution results.
- Autonomous approval, merge, delivery, or removal of the three human gates.
- Preserving the current `qa-engine` Test Map implementation or its eleven-skill command structure.

## 2. Source repository policy

The existing sibling repository `qa-engine/` is a read-only legacy reference. QualityWeaver development must not modify, rename, reformat, or commit changes to that repository.

Migration is selective:

- Preserve and normalize useful viewpoint knowledge.
- Port Markdown parsing and Excel export behavior behind tests.
- Convert the current company workbook and naming behavior into a `company-legacy` profile.
- Do not copy old skills verbatim.
- Do not port Claude-only paths, `CLAUDE.md` injection, `${CLAUDE_PLUGIN_ROOT}`, AJIS source names, company naming conventions, or PM/PQCL fields into the core.
- Record provenance for migrated knowledge so future maintainers can trace the legacy source.

## 3. Core architecture

QualityWeaver separates reusable knowledge, project decisions, overview projections, and deliverables.

```text
Viewpoint Catalog
        ↓
Requirement-specific applicability decisions
        ↓
Coverage Ledger (source of truth)
        ↓
Generated Test Map (review projection)
        ↓
Outline and detailed test cases
```

### 3.1 Viewpoint Catalog

The Viewpoint Catalog defines what may need testing. Every detailed viewpoint has a stable ID, name, group, scope, applicable entity types, positive signals, exclusions, clarification prompts, default priority, and test-design guidance.

Viewpoints have one of three scopes:

- `local`: evaluated against one normalized requirement unit or entity.
- `cross-requirement`: evaluated after related requirements and flows are available.
- `system-wide`: enabled by project configuration or a profile.

The catalog includes a lightweight routing index. Agents load detailed viewpoint files only for groups selected by routing, instead of loading the full catalog for every requirement.

### 3.2 Coverage Ledger

The Coverage Ledger is the project-specific source of truth for what will and will not be tested. Each decision records:

- Stable coverage ID.
- Requirement source ID.
- Target entity or flow ID.
- Viewpoint ID.
- Condition or scenario discriminator.
- Decision: `include`, `exclude`, or `needs-clarification`.
- Priority.
- Evidence from the normalized requirement.
- Rationale or a controlled exclusion reason.
- Related clarification question when required.

The logical uniqueness key is:

```text
requirement + target + viewpoint + condition
```

The core rejects duplicate keys. Included coverage must map to an outline item exactly once unless a profile explicitly permits one test case to group multiple coverage items.

### 3.3 Generated Test Map

The Test Map is never independently authored by a model. It is a deterministic Markdown projection of the Coverage Ledger for human review.

It summarizes, per requirement unit or flow:

- Applicable, included, excluded, and unresolved counts.
- Priority distribution.
- Coverage by viewpoint group.
- High-risk items.
- Review status and detected anomalies.

The projection links back to Coverage Ledger IDs. Editing the Test Map does not change coverage; users edit the ledger through the supported workflow and regenerate the map.

## 4. Requirement processing

Each Markdown input is normalized into stable, typed entities before viewpoint evaluation. The normalized model covers:

- Requirement units and source locations.
- Business rules and acceptance statements.
- UI controls when present.
- APIs and data fields when present.
- Actors, preconditions, outcomes, and flows.
- Risks, ambiguities, contradictions, and missing information.

The canonical model is not screen-only. A requirement unit may describe a screen, popup, API, business rule, batch operation, feature, or flow.

Every normalized fact retains source evidence. Inferred content must be marked as an assumption or clarification candidate and cannot silently become a confirmed requirement.

## 5. Coverage workflow

Coverage planning uses two routing stages and one independent evaluation stage.

### Stage 1: Viewpoint group routing

The core and agent classify the normalized entity inventory into relevant viewpoint groups. Entire irrelevant groups receive a controlled exclusion reason, such as `NO_INPUT_ENTITY` or `NO_BATCH_BEHAVIOR`.

### Stage 2: Detailed applicability

Only detailed viewpoints in routed groups are evaluated. Each result becomes a Coverage Ledger decision with evidence. Missing information produces `needs-clarification`; it does not default silently to inclusion or exclusion.

### Stage 3: Coverage evaluation

An evaluator checks the proposed ledger against normalized requirements and catalog rules. Deterministic checks run before model judgment. The evaluator reports gaps, unsupported inclusions, duplicates, conflicting decisions, and high-risk requirements without suitable negative or abnormal coverage.

The generator may revise the ledger at most two times per run. Remaining ambiguity or disagreement is escalated to the human coverage gate. The loop never approves its own output.

## 6. Human gates and state machine

The workflow has exactly three required approval gates.

### Gate 1: Requirement analysis

The user reviews normalized requirements, source evidence, risks, and clarification questions. Coverage planning cannot start until the relevant requirement scope is approved.

### Gate 2: Coverage design

The user reviews the generated Test Map and drills down into Coverage Ledger decisions as needed. Outline generation cannot start until the relevant coverage scope is approved.

### Gate 3: Detailed test cases

The user reviews detailed cases and traceability. Export cannot start until cases are approved and no blocking clarification remains.

The CLI owns legal state transitions. Agents may request transitions but cannot edit state directly. Stale upstream artifacts invalidate downstream approvals and require regeneration or an explicit reviewed migration.

## 7. Test-case generation

Approved coverage produces a concise outline. Every outline item references one or more approved Coverage Ledger IDs, and every included coverage item must be consumed.

Detailed test cases are generated only from approved outlines. Each detailed case retains:

- Test case ID and title.
- Coverage and requirement traceability.
- Preconditions.
- Test data when required.
- Numbered steps with one action per step.
- Observable expected results.
- Priority and tags.
- Assumptions or linked clarification IDs.

The model cannot add unapproved coverage during detail generation. Newly discovered coverage returns to Gate 2 instead of being inserted silently.

## 8. Output model and profiles

Canonical Markdown is the source of truth for test cases. Excel is an output adapter selected by profile.

The built-in `generic` profile defines portable defaults. The optional `company-legacy` profile contains migrated workbook templates, delivery columns, filename rules, and organizational metadata from `qa-engine` when those behaviors are still required.

Profiles may configure presentation and policy within documented extension points, but cannot replace core schemas, bypass approval gates, or disable traceability validation.

## 9. Repository layout

```text
quality-weaver/
├── .codex-plugin/plugin.json
├── .claude-plugin/plugin.json
├── skills/
├── src/quality_weaver/
│   ├── cli/
│   ├── domain/
│   ├── workflow/
│   ├── coverage/
│   ├── validators/
│   ├── projections/
│   └── exporters/
├── viewpoints/
│   ├── catalog.yaml
│   ├── local/
│   ├── cross-requirement/
│   └── system-wide/
├── profiles/
│   ├── generic/
│   └── company-legacy/
├── schemas/
├── tests/
│   ├── unit/
│   ├── contract/
│   ├── golden/
│   └── platform/
├── examples/
├── docs/
├── pyproject.toml
└── README.md
```

The implementation targets Python 3.11 or newer. The core libraries are Pydantic for typed validation and JSON Schema generation, Typer for the CLI, ruamel.yaml for round-trip-safe reviewable YAML, openpyxl for Excel profiles, and pytest for verification.

## 10. Codex and Claude Code portability

The plugin root contains both platform manifests and one shared `skills/` tree. Shared skills use only portable Agent Skills metadata and instructions.

Skills coordinate the model-facing parts of a workflow but delegate deterministic behavior to the same `quality-weaver` CLI. They do not own schemas, state transitions, validation algorithms, or workbook formatting.

Platform-specific wrappers are introduced only when a required capability cannot be represented portably. Such wrappers must remain thin and pass the same platform contract tests.

No workflow depends on prior chat history. A task can move between Codex and Claude Code using versioned workspace artifacts and CLI-managed state.

## 11. User-project workspace

QualityWeaver stores generated state under `.quality-weaver/` in the user's project:

```text
.quality-weaver/
├── config.yaml
├── state.json
├── normalized/
├── questions/
├── coverage/
│   ├── ledger.yaml
│   └── test-map.md
├── tests/
│   ├── outlines/
│   └── detailed/
├── exports/
└── runs/<run-id>/
    ├── input-manifest.json
    ├── validation.json
    └── summary.md
```

`state.json` is CLI-managed and not a manual review surface. Markdown and YAML review artifacts remain human-readable. Each run records input hashes, catalog/profile versions, validation evidence, artifact lineage, and available model/platform metadata.

## 12. Error handling and recovery

Errors are categorized as:

- `input`: malformed or missing requirement content.
- `schema`: artifact does not match its canonical model.
- `state`: illegal transition, stale dependency, or missing approval.
- `coverage`: duplicate, conflicting, unsupported, or unmapped coverage.
- `clarification`: human judgment or missing product information is required.
- `profile`: invalid profile or incompatible export configuration.
- `export`: workbook/template or filesystem delivery failure.
- `platform`: plugin loading or CLI discovery failure.

Commands fail without partially advancing state. Recoverable generation failures preserve diagnostics and the last valid artifact. Automated retries are limited to two and apply only to model-generated artifacts that fail actionable validation. State, profile, permission, and unresolved clarification errors do not retry automatically.

## 13. Verification strategy

### Unit tests

Cover schemas, state transitions, logical coverage keys, routing metadata, stale detection, Test Map aggregation, Markdown parsing, and export helpers.

### Contract tests

Verify that every skill consumes and produces the documented artifacts, and that both platform manifests expose the same shared workflow capabilities.

### Golden tests

Run representative Markdown requirements through fixed checkpoints and compare normalized facts, selected viewpoint IDs, coverage decisions, Test Map summaries, and testcase traceability. Golden fixtures include UI-heavy, API-only, flow-based, mobile, ambiguous, and duplicate-prone requirements.

### Model-variance evaluations

Evaluate at least one stronger and one lower-capability supported model against the same fixtures. Structural validity, logical uniqueness, traceability, and gate enforcement must remain deterministic. Semantic coverage quality may differ and is measured separately.

### Legacy regression tests

Port existing Markdown parser and Excel exporter tests before changing their behavior. A small set of approved legacy examples verifies the `company-legacy` profile without making legacy conventions core requirements.

## 14. v1 success criteria

QualityWeaver v1 is successful when:

- The same workspace can progress through all three gates using Codex or Claude Code interchangeably.
- Every included testcase traces to approved coverage and requirement evidence.
- Every included coverage item is consumed, with no accidental duplicate logical key.
- The Test Map is reproducibly generated from the ledger and contains no independent model decisions.
- Invalid state transitions and stale downstream artifacts are blocked.
- Unresolved blocking clarifications prevent export.
- Generic Markdown export and the selected Excel profile pass automated verification.
- Golden fixtures show stable structure and traceability across the selected strong and lower-capability models.
- `qa-engine` remains unchanged.
