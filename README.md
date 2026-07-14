# QualityWeaver

QualityWeaver turns a Markdown requirement into approved, viewpoint-driven
test coverage, traceable manual test cases, canonical Markdown, and
profile-driven Excel exports — through a shared Python CLI and matching
Codex/Claude Code skills.

A Python CLI owns schemas, workspace state, validation, projections, and
exporters. Codex and Claude Code coordinate through the same `skills/`
content and call the same CLI commands. Viewpoints are reusable knowledge,
the Coverage Ledger is the project source of truth, and the Test Map is a
deterministic projection of it — never a model's independent judgment.

## Install

Requires Python 3.11+.

```bash
python -m pip install -e ".[dev]"
```

This installs the `quality-weaver` console command and the `dev` extras
(pytest, ruff, mypy, build) used below.

## Plugin setup

QualityWeaver ships as one skill tree with two platform manifests.

**Codex** (local marketplace / plugin directory):

- Point Codex at this repository root; `.codex-plugin/plugin.json` declares
  `skills: "./skills/"` and lists the six capabilities below.

**Claude Code** (`--plugin-dir` development setup):

```bash
claude --plugin-dir /path/to/quality-weaver
```

`.claude-plugin/plugin.json` shares the same `name` and `version` as the
Codex manifest; both platforms read the same `skills/*/SKILL.md` files, so
there is nothing platform-specific to keep in sync beyond the manifests
themselves.

## The six skills

| Skill | Use when |
| --- | --- |
| `initialize` | An existing project directory needs a new workspace before requirement analysis. |
| `analyze-requirements` | Markdown requirements need normalized facts, evidence, risks, and questions. |
| `plan-coverage` | Approved requirements need viewpoint applicability decisions and a reviewable coverage plan. |
| `design-testcases` | Approved coverage needs an exact-consumption outline and traceable detailed test cases. |
| `export-testcases` | Approved test cases need canonical Markdown or profile-driven Excel delivery. |
| `status` | A project needs its gate states, stale conditions, or next legal action reported. |

Every skill calls the public CLI for validation and never recomputes a
Coverage Ledger or Test Map decision on its own.

## The three approval gates

A workspace tracks three independent gates, each `draft` -> `approved`,
gated on the previous one:

```text
requirements: draft -> approved
coverage:     draft -> approved   (requires requirements approved)
testcases:    draft -> approved   (requires coverage approved)
```

```bash
quality-weaver init <path>
quality-weaver status <path>
quality-weaver approve requirements <path>
quality-weaver approve coverage <path>
quality-weaver approve testcases <path> --artifact <path>/.quality-weaver/tests/detailed/testcases.md
```

Export requires all three gates approved.

## Workspace artifacts

`quality-weaver init` creates `.quality-weaver/` with:

```text
.quality-weaver/
  config.yaml               # schema_version, profile
  state.json                # gate statuses; CLI-owned, never hand-edited
  normalized/requirements.yaml
  questions/
  coverage/ledger.yaml       # source of truth
  coverage/test-map.md       # CLI-rendered projection of the ledger
  tests/outlines/test-outline.yaml
  tests/detailed/testcases.yaml   # model working artifact
  tests/detailed/testcases.md     # canonical Markdown, source of truth
  exports/
  runs/
```

The Coverage Ledger and the canonical testcase Markdown are the only
sources of truth for their stages; every other artifact (Test Map,
rendered Markdown from YAML) is a deterministic projection the CLI
produces from them.

## Generic export

```bash
quality-weaver export <project-path> <project-path>/.quality-weaver/tests/detailed/testcases.md \
  --profiles-root profiles --profile generic --format markdown --out <out-file>
```

## Legacy-company Excel profile

```bash
quality-weaver export <project-path> <project-path>/.quality-weaver/tests/detailed/testcases.md \
  --profiles-root profiles --profile company-legacy --format excel \
  --out <output-directory> --workbook ut --project-name <project> --artifact-name <artifact>
```

`--workbook` selects `ut` or `it`; the profile's filename policy generates
the output filename, so `--project-name`/`--artifact-name` only supply the
values it substitutes.

## Recovering from stale state

Approving requirements or coverage does not retroactively invalidate
downstream work in v1 — invalidation is manual only
(`quality-weaver regenerate <stage> <path>` after marking a stage stale via
`invalidate_after`, or `quality-weaver reopen <stage> <path>` to return an
approved gate to draft for revision). If `quality-weaver status <path>`
reports a stale gate, run `regenerate` for that stage, redo the artifact,
and re-validate before approving again.

## Worked example

`examples/login/requirements/login.md` and `tests/golden/login/` contain a
complete, reproducible run of the workflow (normalized requirement,
approved ledger, rendered Test Map, outline, and canonical testcase
Markdown). See `tests/golden/test_login_vertical_slice.py` for the exact
sequence of CLI-equivalent calls that produces them.

## Development

See `CONTRIBUTING.md` for local commands, and `AGENTS.md` / `CLAUDE.md` for
repository conventions used by agentic contributors.
