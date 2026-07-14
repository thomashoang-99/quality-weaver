---
name: export-testcases
description: Use when approved detailed test cases need canonical Markdown or profile-driven Excel delivery.
---

# Export Test Cases

Export only explicitly selected approved cases through an explicit profile and destination.

## Contract

**Input artifacts and read paths:** Read `<project-path>/.quality-weaver/coverage/ledger.yaml`, `<project-path>/.quality-weaver/tests/outlines/test-outline.yaml`, the approved canonical Markdown at `<project-path>/.quality-weaver/tests/detailed/testcases.md`, `<project-path>/.quality-weaver/config.yaml`, and `<plugin-root>/profiles/<profile>/profile.yaml`.

**Allowed state:** Require testcases approved in `quality-weaver status <project-path>`, require the canonical Markdown document status to be approved, and require no blocking clarification.

**CLI validation command:** Run `quality-weaver testcases validate <project-path>/.quality-weaver/coverage/ledger.yaml <project-path>/.quality-weaver/tests/outlines/test-outline.yaml <project-path>/.quality-weaver/tests/detailed/testcases.md`. For Markdown run `quality-weaver export <project-path> <project-path>/.quality-weaver/tests/detailed/testcases.md --profiles-root <plugin-root>/profiles --profile <profile> --format markdown --out <out-path>`. For Excel run `quality-weaver export <project-path> <project-path>/.quality-weaver/tests/detailed/testcases.md --profiles-root <plugin-root>/profiles --profile <profile> --format excel --out <output-directory> --workbook <workbook-kind> --project-name <project-name> --artifact-name <artifact-name>`.

**Output artifact:** Produce the CLI-reported Markdown file or profile-driven Excel workbook under the explicit output destination.

**Blocking findings:** Stop for unapproved or stale testcases, invalid traceability, unresolved clarification, invalid profile, missing Excel metadata or template, protected-input collision, permission failure, or any export error.

**Retry limit:** Model artifact validation retries: 0. Export and profile findings are deterministic or require human input.

**Next human gate:** Present the exported path, format, profile, and case count for human delivery acceptance. All QualityWeaver approval gates are already complete.

## Workflow

1. Confirm approved state and revalidate the selected canonical Markdown testcase document.
2. Load the requested profile from the explicit profile root.
3. Require the Excel-only profile workbook kind (`ut` or `it` when using `company-legacy`) and naming values when Excel is selected. Let the profile generate the workbook filename; do not accept a filename policy from the user.
4. Run one export command and report its result without rewriting the output.

Treat canonical Markdown as the source of truth; use YAML only as an upstream working artifact. Do not bypass profile policy or export unapproved cases. Do not write `<project-path>/.quality-weaver/state.json`; only the CLI owns state. Do not approve a gate or run an approval command.
