# Contributing

## Setup

```bash
python -m pip install -e ".[dev]"
```

## Commands

```bash
python -m pytest -q                                            # full suite
python -m pytest --cov=quality_weaver --cov-report=term-missing -q  # with coverage
python -m ruff check .
python -m mypy src
python -m build                                                 # wheel + sdist
```

Core package line coverage must stay at or above 90% (`--cov-fail-under=90`
in CI).

## Test layout

- `tests/unit/`: deterministic unit tests, one module per `src/quality_weaver/*.py`.
- `tests/contract/`: schema, manifest, skill, and workspace contracts.
- `tests/golden/`: end-to-end fixed artifact fixtures, byte-compared against
  committed expected output.
- `tests/platform/`: Codex and Claude plugin discovery smoke tests.

## Workflow

1. Write a failing test first (TDD; see task steps in
   `docs/superpowers/plans/2026-07-13-quality-weaver-v1.md` for the pattern
   used throughout this codebase).
2. Implement the minimal change to pass it.
3. Run ruff, mypy, and the full test suite before committing.
4. Keep commits scoped to one task/behavior; follow the existing
   Conventional-Commits-style messages (`feat(...)`, `fix(...)`,
   `build:`, `docs:`, `ci:`).

## Constraints that apply to every change

- Never modify the sibling `qa-engine/` repository. `git -C ../qa-engine
  status --porcelain` must report no output after any change here.
- The Coverage Ledger is the only source of truth for coverage; the Test
  Map is a projection produced only by `render_testmap`. Do not let a
  model (or a skill) write Test Map values directly.
- Canonical testcase Markdown (`tests/detailed/testcases.md`) is the
  source of truth once approved; the YAML working artifact is upstream
  input only.
- `state.json` is written only by `Workspace`; nothing else — CLI, skill,
  or human — writes it by hand.
- Skills declare input/read paths, allowed state, the exact CLI validation
  command, output artifact, blocking findings, retry limit, and next human
  gate. They must not embed schemas, duplicate viewpoint knowledge, or
  independently calculate Test Map values.
