---
name: export-testcases
description: Use when approved detailed test cases need canonical Markdown or profile-driven Excel delivery.
---

# Export Test Cases

Export only explicitly selected approved cases through an explicit profile and destination.

## Contract

**Input artifacts and read paths:** Read `.quality-weaver/coverage/ledger.yaml`, `.quality-weaver/tests/outlines/test-outline.yaml`, `.quality-weaver/tests/detailed/testcases.yaml`, `.quality-weaver/config.yaml`, and `<profiles-root>/<profile>/profile.yaml`.

**Allowed state:** Require testcases approved in `quality-weaver status <project-path>` and no blocking clarification.

**CLI validation command:** Run `quality-weaver testcases validate .quality-weaver/coverage/ledger.yaml .quality-weaver/tests/outlines/test-outline.yaml .quality-weaver/tests/detailed/testcases.yaml`. For Markdown run `quality-weaver export <project-path> .quality-weaver/tests/detailed/testcases.yaml --profiles-root <profiles-root> --profile <profile> --format markdown --out <out-path>`. For Excel add `--format excel --out <output-directory> --workbook <workbook> --project-name <project-name> --artifact-name <artifact-name>` instead of the Markdown format and output arguments.

**Output artifact:** Produce the CLI-reported Markdown file or profile-driven Excel workbook under the explicit output destination.

**Blocking findings:** Stop for unapproved or stale testcases, invalid traceability, unresolved clarification, invalid profile, missing Excel metadata or template, protected-input collision, permission failure, or any export error.

**Retry limit:** Model artifact validation retries: 0. Export and profile findings are deterministic or require human input.

**Next human gate:** Present the exported path, format, profile, and case count for human delivery acceptance. All QualityWeaver approval gates are already complete.

## Workflow

1. Confirm approved state and revalidate the selected canonical testcase document.
2. Load the requested profile from the explicit profile root.
3. Require the Excel-only workbook and naming values when Excel is selected.
4. Run one export command and report its result without rewriting the output.

Do not bypass profile policy or export unapproved cases. Do not write `.quality-weaver/state.json`; only the CLI owns state. Do not approve a gate or run an approval command.
