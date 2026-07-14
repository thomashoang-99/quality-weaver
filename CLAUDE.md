# CLAUDE.md

Repository development commands and conventions for Claude Code sessions
working on QualityWeaver itself. This file does not describe plugin
runtime behavior — that lives in `skills/*/SKILL.md`.

## Commands

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
python -m ruff check .
python -m mypy src
```

Run all three before committing. See `CONTRIBUTING.md` for the full
command list and test-layout description.

## Conventions

- Python 3.11+, Pydantic 2, Typer, ruamel.yaml, openpyxl.
- TDD: add a failing test, then the minimal implementation, per task in
  `docs/superpowers/plans/2026-07-13-quality-weaver-v1.md`.
- Never modify `../qa-engine`; verify with
  `git -C ../qa-engine status --porcelain`.
- `Workspace` is the only writer of `.quality-weaver/state.json`.
- The Coverage Ledger is the only coverage source of truth; the Test Map
  is a projection from `render_testmap`, never a model's independent
  calculation.
- Canonical testcase Markdown is the source of truth once approved; treat
  the YAML working artifact as upstream input only.
