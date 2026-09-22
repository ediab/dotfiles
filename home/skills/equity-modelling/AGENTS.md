# Equity modelling — maintainer notes

This is a working, model-invoked skill. V1 (`company-model`) is archived reference only; VRT is the
V2 proof fixture. V2's generic core is shipped — evidence, engine, `scripts/cli.py` build/check, and
shared checks/style/overrides — and `SKILL.md` points at it. Later stages (second-company proof,
rollover, final acceptance) are incomplete, so v2 has not yet passed all acceptance patterns.

**`V2_PLAN.md` is the active design and migration plan. Read it before changing this skill**, and
start at its §18.

## Layout and ownership

A contract lives in exactly one file. Everything else links to it.

| File | Owns |
|---|---|
| `SKILL.md` | The executable workflow, principles, defaults, boundaries, prepared-project runtime contract, web-challenge policy |
| `references/model-rules.md` | Workbook contract: sheets, periods, presentation, hardcode policy, decision integrity, web-challenge record format |
| `references/update-model.md` | The earnings-update / rollover branch |
| `tests/` | Unit tests and the research-behaviour smoke test |
| `V2_PLAN.md` | v2 design, diagnosis, staged sequence; archive after Stage 6 |
| `V2_PROGRESS.md` | Append-only execution record; delete with the plan at Stage 6 |

`references/interfaces.md` owns the artifact schemas, entry points and locator grammar;
`references/evidence-rules.md` owns the evidence conventions.

## Rules

- Keep company-specific drivers in the invocation-time interview and the generated company project.
  Only reusable workflow and validation rules belong here.
- Do not add sector templates, dashboards, or automatic web-data ingestion.
- A data-driven engine **is** wanted (V2 §12.1); a formula DSL or a database is not.
- `company-model` is the donor skill and stays in place until V2 Stage 6. Do not rename or overwrite
  it; port from it rather than recreating equivalents.
- Keep `SKILL.md`'s runtime contract and the shipped files in `scripts/` consistent — change them
  together. `scripts/cli.py` is the prepared-project build/check/driver-rollover runtime; it does not
  ingest raw sources, render, or recalculate.

## Workflow

Edit this source folder, then deploy with `~/Dev/pi-dotfiles/rebuild.sh --sync-only`.

Run the tests before committing:

```sh
python3 -m unittest discover home/skills/equity-modelling/tests
```
