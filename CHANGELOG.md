# Changelog

All notable changes to this project are documented here.

## 0.1.0

Initial release: a three-gate, viewpoint-driven manual test design
workflow shared between Codex and Claude Code.

- Python CLI (`quality-weaver`) owning schemas, workspace state,
  validation, projections, and exporters.
- Three sequential human approval gates — `requirements`, `coverage`,
  `testcases` — each `draft -> approved`, gated on the previous one, with
  manual `invalidate_after`/`regenerate`/`reopen` state transitions.
- Portable viewpoint catalog (`viewpoints/`) migrated from the legacy
  `qa-engine` rule tables, routed by entity type and risk, with full
  migration provenance.
- Coverage Ledger as the single source of truth for coverage decisions,
  with deterministic validation (`validate_ledger`) and a Test Map
  projection (`render_testmap`) that never recomputes ledger decisions
  independently.
- Traceable outline and detailed test-case validation
  (`validate_outline`, `validate_testcases`) and canonical, round-trip-safe
  Markdown rendering for detailed test cases.
- Profile-driven export: a `generic` Markdown-only profile and a
  `company-legacy` profile producing UT/IT Excel workbooks from the
  original templates, without importing code from `qa-engine` at runtime.
- Shared Agent Skills (`initialize`, `analyze-requirements`,
  `plan-coverage`, `design-testcases`, `export-testcases`, `status`) and
  matching Codex (`.codex-plugin/`) and Claude Code (`.claude-plugin/`)
  plugin manifests.
- A reproducible login vertical-slice example (`examples/login/`,
  `tests/golden/login/`) and a model evaluation contract
  (`evals/cases/login.yaml`) separating deterministic structural scoring
  from reported-only semantic scoring.
