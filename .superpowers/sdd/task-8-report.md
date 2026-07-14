# Task 8 Evidence Report

## Scope

Implemented six portable shared skills and dual Codex/Claude plugin manifests. The shared tree contains only `SKILL.md` files; generated `agents/openai.yaml` files were removed. No marketplace or Task 9 artifact was added.

## Contract RED and GREEN

Initial platform/skill run:

```text
python -m pytest tests/contract/test_skills.py tests/platform/test_manifests.py -q
7 failed, 3 passed, 1 skipped
```

Failures were caused by the absent six skills and two manifests. A dedicated missing-file contract then failed before each skill was initialized.

Final contract run:

```text
python -m pytest tests/contract/test_skills.py tests/platform/test_manifests.py -q
22 passed
```

Contracts verify portable two-field frontmatter, trigger-only third-person descriptions, declared paths, real leaf-command help and options, retry bounds, state/approval ownership, Test Map projection ownership, capability parity, and absence of platform metadata in the shared tree.

## Per-skill evidence

| Skill | RED | GREEN and quick validation | Fresh application evidence |
|---|---|---|---|
| `initialize` | Missing `skills/initialize/SKILL.md` failed its dedicated contract. | Targeted contract: 2 passed. `quick_validate.py`: `Skill is valid!` | Used `init`, then one `status` check; blocked invalid paths/existing workspace; zero retries; handed Markdown input selection to the human without approval. |
| `analyze-requirements` | Missing `skills/analyze-requirements/SKILL.md` failed its dedicated contract. | Targeted contract: 2 passed. `quick_validate.py`: `Skill is valid!` | First pass invented an undeclared `check-jsonschema` executable. The skill was tightened to use an available schema facility without introducing an executable. A fresh pass retained evidence, labeled ambiguity, used exact `status` checks, capped actionable schema revisions at two, and left approval to the human. |
| `plan-coverage` | Missing `skills/plan-coverage/SKILL.md` failed its dedicated contract. | Targeted contract: 2 passed. `quick_validate.py`: `Skill is valid!` | Routed only relevant catalog groups, emitted include/exclude/clarification decisions, used exact `coverage validate` and `testmap render` commands, stopped on blocking findings, and did not calculate Test Map values. |
| `design-testcases` | Missing `skills/design-testcases/SKILL.md` failed its dedicated contract. | Targeted contract: 2 passed. `quick_validate.py`: `Skill is valid!` | Recognized a newly discovered scenario as a blocking coverage finding, did not add it silently, deferred validation/rendering until coverage review, and preserved the testcase human gate. |
| `export-testcases` | Missing `skills/export-testcases/SKILL.md` failed its dedicated contract. | Targeted contract: 2 passed. `quick_validate.py`: `Skill is valid!` | Blocked a company-legacy Excel request missing workbook, project, and artifact values; reported exact validation/export commands; used zero retries; handed delivery acceptance to the human. |
| `status` | Missing `skills/status/SKILL.md` failed its dedicated contract. | Targeted contract: 2 passed. `quick_validate.py`: `Skill is valid!` | Used one authoritative `status` snapshot, reported stale coverage only if the CLI did, used zero retries, and did not execute the reported next action. |

Each directory was created individually with `skill-creator/scripts/init_skill.py`, edited, validated with `quick_validate.py`, and application-tested before the next skill was started.

## Manifest evidence

- Codex and Claude manifests share `quality-weaver`, version `0.1.0`, description, and the same six shared capabilities.
- Claude keeps the portable identity manifest and discovers the root `skills/` tree.
- Codex declares `./skills/`, `author.name`, and current required interface metadata.
- The first current-validator run rejected missing `interface.longDescription` and `interface.defaultPrompt`; both were added minimally.

```text
python C:\Users\Admin\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py .
Plugin validation passed
```

## Completion gates

```text
python -m pytest -q
187 passed, 1 skipped

python -m ruff check .
All checks passed!

python -m mypy src
Success: no issues found in 13 source files

git diff --check
clean

git -C D:\zero-to-hero-something\qa-engine status --porcelain
clean
```

The skipped test is the existing opt-in live legacy migration audit, which requires `QUALITY_WEAVER_LEGACY_ROOT`.

## Independent review remediation

The follow-up review was implemented in three TDD groups.

### Public validation and Gate 2 recovery

RED:

```text
python -m pytest tests/unit/test_cli.py tests/unit/test_workspace.py -q
10 failed, 35 passed
```

GREEN added:

- `quality-weaver requirements validate PATH`, using strict YAML loading and `RequirementDocument` validation with concise typed failures.
- `quality-weaver reopen STAGE PROJECT`, allowing only an approved gate to return to draft while downstream gates become stale through the existing locked atomic mutation path.

```text
45 passed
```

### Canonical Markdown

RED:

```text
python -m pytest tests/unit/test_testcases.py -q
6 failed, 11 passed
```

GREEN added a strict parser for the exact renderer grammar. Canonical escaping is reversible for CR/LF, backslashes, Markdown punctuation, and HTML. Coverage and tag arrays use inert escaped JSON encoding, preserving values that contain commas. Parsing rejects malformed, noncanonical, count-mismatched, or adversarial input with `TestCaseMarkdownError`.

The CLI now accepts canonical `.md` in testcase validation and export. Generic Markdown export is byte-equal after parse/re-render, and the Excel CLI path preserves all parsed testcase values.

```text
python -m pytest tests/unit/test_testcases.py -q
17 passed
```

### Portable skill and platform contracts

RED:

```text
python -m pytest tests/contract/test_skills.py tests/platform/test_manifests.py -q
15 failed, 14 passed
```

GREEN contracts now enforce:

- `<project-path>/.quality-weaver/...` for every project artifact.
- `<plugin-root>/schemas`, `<plugin-root>/viewpoints`, and `<plugin-root>/profiles` for plugin resources.
- Fully qualified commands, leaf help/options, positional semantics, and execution from an unrelated current directory with separate project and plugin roots.
- Exact public requirement validation and human-only reopen/approval commands.
- Deterministic Coverage Ledger finding codes without claiming the CLI performs semantic coverage evaluation.
- Canonical Markdown review at Gate 3 and Markdown input for downstream export.
- Real Claude manifest validation and discovery of all six shared skills when the Claude executable is installed.

Claude author metadata removed the validator warning. Current Codex validation remained clean.

```text
29 passed
```

### Modified-skill application evidence

- `analyze-requirements`: used absolute project/plugin paths from an unrelated CWD, ran the public requirement validator, and stopped unresolved ambiguity without consuming retries.
- `plan-coverage`: used absolute catalog/artifact paths, listed the actual deterministic CLI finding codes, and reserved semantic applicability/completeness for model proposal plus human Gate 2 review.
- `design-testcases`: stopped all testcase outputs on newly discovered coverage, directed the human through `reopen coverage`, ledger validation, Test Map rendering, Gate 2 approval, and restart; the normal path validated YAML, rendered canonical Markdown, validated Markdown again, then handed off Gate 3.
- `export-testcases`: the first pass mislabeled `--workbook` as a filename. The skill was corrected to `<workbook-kind>` (`ut` or `it` for `company-legacy`) and to leave filename generation to the profile. A fresh pass used `ut`, treated `--out` as a directory, and did not invent a filename policy.

All six modified skills passed `quick_validate.py`; fresh application evaluations were run for the four workflow skills above.

### Final review gates

```text
python -m pytest -q
213 passed, 1 skipped

python -m ruff check .
All checks passed!

python -m mypy src
Success: no issues found in 13 source files

plugin-creator/scripts/validate_plugin.py .
Plugin validation passed

claude plugin validate .
Validation passed

claude --plugin-dir . plugin details quality-weaver
Skills (6): analyze-requirements, design-testcases, export-testcases,
initialize, plan-coverage, status

git diff --check
clean

git -C D:\zero-to-hero-something\qa-engine status --porcelain
clean
```
