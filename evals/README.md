# Model Evaluation Contract

This directory defines what "good enough" means when a model (Codex, Claude,
or any other agent) proposes QualityWeaver artifacts. It is a contract, not
a runner: `evals/cases/*.yaml` describe fixed inputs and scoring dimensions
that any harness can implement against.

## Structure

- `cases/login.yaml`: the current eval case. Reuses the login vertical slice
  fixtures under `tests/golden/login/` as the fixed normalized-requirement
  and viewpoint packet, and scores a model-proposed Coverage Ledger against
  `schemas/coverage-ledger.schema.json`.

## Scoring dimensions

Every case separates scoring into two kinds:

- **Structural** (`schema_valid`, `unique_logical_keys`,
  `traceability_complete`, `gate_checks`): deterministic, code-checked
  properties. These reuse the same public functions the CLI uses
  (`quality_weaver.coverage.validate_ledger`, the `CoverageLedger` model
  validators) so a model cannot pass by producing output the CLI itself
  would reject.
- **Semantic** (`viewpoint_relevance`, `condition_specificity`, ...):
  judgment calls about whether the *chosen* viewpoints and conditions are
  sensible for the requirement. These are reported for trend analysis only.

## Acceptance rule

A run is accepted only when every structural score reaches its threshold
(100% for the current case). Semantic scores are never used to bypass the
three human approval gates (`requirements`, `coverage`, `testcases`)
enforced by `Workspace` and the CLI — they inform prompt and viewpoint
catalog iteration, not workflow gating.

## Run metadata

Every recorded run must include `provider`, `model`, `platform`,
`catalog_version`, `profile`, and `artifact_sha256` so results are
reproducible and comparable across Codex, Claude Code, and future
providers.
