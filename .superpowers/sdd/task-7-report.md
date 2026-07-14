# Task 7 Report

## Outcome

Implemented strict generic and legacy-company export profiles, canonical Markdown export,
profile-driven Excel export, and an explicit export CLI. The legacy profile contains byte-for-byte
copies of both workbook templates and runtime code has no dependency on the sibling `qa-engine`
repository.

## Profile and export contract

- `Profile.load(name, profiles_root)` loads only a named child of an explicitly supplied profile
  root. Unknown names, schema errors, identity mismatches, escaping/missing templates, unknown
  formats, duplicate mappings, and invalid workbook declarations fail with typed profile codes.
- `generic` permits Markdown only. `company-legacy` permits canonical Markdown and Excel and owns
  the organizational cell metadata, workbook templates, required sheets, header/column mappings,
  first data rows, and filename patterns.
- `export_markdown` and `export_excel` require an explicit `Workspace`, approved
  `TestCaseDocument`, profile, output path, and protected inputs. Both reject resolved input/output
  collisions and publish atomically only after all checks pass.
- Excel export verifies required sheets and declared header mappings before writing, sorts cases by
  stable ID, writes one case per workbook row, verifies the written ID/count projection, treats user
  text as literal cells rather than formulas, and derives the output filename from profile policy.
- CLI export requires explicit project, cases, profiles root, profile, format, and output. Excel also
  requires explicit workbook kind, project name, and artifact name; it performs no artifact or
  sibling-repository discovery.

## TDD evidence

Initial RED:

```text
ModuleNotFoundError: No module named 'quality_weaver.profiles'
ModuleNotFoundError: No module named 'quality_weaver.exporters'
```

Additional RED/GREEN cycles demonstrated and fixed missing template-header verification,
profile-root traversal, and Excel formula interpretation of user-authored values.

Focused GREEN:

```text
20 passed in 9.30s
```

## Files

- Added `src/quality_weaver/profiles.py` and `src/quality_weaver/exporters.py`.
- Added `profiles/generic/profile.yaml`.
- Added `profiles/company-legacy/profile.yaml` and self-contained copies of
  `UT_TestCase.xlsx` and `IT_TestCase.xlsx`.
- Added `tests/unit/test_profiles.py` and `tests/unit/test_exporters.py`.
- Updated `src/quality_weaver/cli.py` with the explicit export command.
- Added `types-openpyxl` to development dependencies so strict mypy checks cover workbook code.

## Verification

- `python -m pytest tests/unit/test_profiles.py tests/unit/test_exporters.py -q`: 20 passed.
- `python -m pytest -q`: 132 passed, 1 expected optional live legacy-audit skip.
- `python -m ruff check .`: all checks passed.
- `python -m mypy src`: success, no issues in 13 source files.
- `git diff --check`: clean; Git emitted only Windows line-ending conversion warnings.
- `qa-engine` status before and after: `## manual...origin/manual`, with no modified or untracked
  files.
- Copied template SHA-256 values match the read-only legacy sources:
  `UT_TestCase.xlsx` = `d3a83fa689e1b92a258c6dc719ff8b4d2d9016ebddb55c6fcc99956f0ae2bf2c`;
  `IT_TestCase.xlsx` = `ed39f971bbc2035b4d1cfd046fa99179615981a4afb545e6661434a720167118`.

## Concerns

- For Excel, CLI `--out` denotes the explicit output directory because the selected profile owns
  the deterministic filename. For Markdown, `--out` is the explicit output file.
- The pre-existing unstaged edit to `docs/superpowers/plans/2026-07-13-quality-weaver-v1.md`
  was neither modified nor staged by Task 7.

## Independent review fixes

All six Important findings from the independent Task 7 review were reproduced and fixed:

- Both exporters now protect `profile.yaml` and every workbook template at the exporter boundary,
  including templates for workbook kinds not selected by the current Excel export.
- Filename policies are parsed with `string.Formatter`; only plain `project` and `artifact` fields
  are accepted, with no attribute/index access, conversion, format specification, unknown field,
  or malformed brace syntax. Export revalidates a bypassed profile and returns typed
  `EXPORT_FILENAME_INVALID` findings.
- Excel presentation preserves every testcase field without adding legacy columns: tags are
  labelled in traceability/Description, while labelled Preconditions and Test Data share the
  preconditions cell. Empty lists render deterministically as `None.`.
- Mapped data cells are cleared through the used worksheet range before writing. Vertical stale
  data merges are removed while horizontal template formatting remains intact. The temporary
  workbook is reloaded and its complete ID region must exactly equal the sorted source case IDs
  before atomic replacement.
- `profile.yaml` is resolved and containment-checked so a symlink cannot escape its resolved
  profile root.
- Directory creation, temporary-file setup, workbook save, reload, verification, and atomic
  replacement failures are converted to typed export findings. Invalid ZIPs and missing sheets
  are rejected before publication, and failed temporary outputs are removed.

### Review RED/GREEN evidence

The initial adversarial batch produced 11 expected failures with 23 existing tests passing.
Focused REDs separately reproduced post-save corruption, invalid ZIP reload, and missing-sheet
reload behavior. The final focused run was:

```text
36 passed in 25.95s
```

### Review verification

- `python -m pytest -q`: 148 passed, 1 expected optional live legacy-audit skip.
- `python -m ruff check .`: all checks passed.
- `python -m mypy src`: success, no issues in 13 source files.
- `git diff --check`: clean; Git emitted only Windows line-ending conversion warnings.
- `qa-engine` remained clean at `## manual...origin/manual`.
