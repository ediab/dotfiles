# Equity modelling — maintainer notes

This is a working, model-invoked skill. V1 (`company-model`) is archived reference only; VRT and
AVGO have V2 proof projects. V2's generic core is shipped — evidence, engine, `scripts/cli.py`
build/check, and shared checks/style/overrides — but release gates remain open.

**`DECISIONS.md` is the agreed nine-sheet target, not yet implemented.** For redesign planning,
read `docs/specs/2026-09-23-nine-sheet-equity-model-redesign.md` (user-selected trial rollout;
awaiting implementation approval). `SKILL.md` and its references describe what runs today. `docs/archive/V2_PLAN.md`
and `docs/archive/V2_PROGRESS.md` retain unresolved V2 defects for migration, not target design.

## Layout and ownership

A contract lives in exactly one file. Everything else links to it.

| File | Owns |
|---|---|
| `SKILL.md` | The executable workflow, principles, defaults, boundaries, prepared-project runtime contract, web-challenge policy |
| `references/model-rules.md` | Workbook contract: sheets, periods, presentation, hardcode policy, decision integrity, web-challenge record format |
| `references/update-model.md` | The earnings-update / rollover branch |
| `tests/` | Unit tests and the research-behaviour smoke test |
| `DECISIONS.md` | Approved target design and sheet roles; not the current runtime contract |
| `docs/specs/2026-09-23-nine-sheet-equity-model-redesign.md` | User-selected trial rollout; awaiting implementation approval |
| `docs/archive/V2_PLAN.md` | Historical V2 design and unresolved migration issues |
| `docs/archive/V2_PROGRESS.md` | Append-only historical V2 execution record |

`references/interfaces.md` owns the artifact schemas, entry points and locator grammar;
`references/evidence-rules.md` owns the evidence conventions.

## Rules

- Keep company-specific drivers in the invocation-time interview and the generated company project.
  Only reusable workflow and validation rules belong here.
- Do not add sector templates, dashboards, or automatic web-data ingestion.
- A data-driven engine **is** wanted (V2 §12.1); a formula DSL or a database is not.
- `company-model` was the donor skill and is **archived** (2026-09-22) at
  `~/Downloads/archive/company-model-2026-09-22/` — repo copy under `pi-dotfiles-home-skills/`, VPS
  copy at `~/archive/company-model-2026-09-22`. Treat it as reference-only: port from the archive
  rather than recreating equivalents, and do not reinstall it under `home/skills/`.
- Keep `SKILL.md`'s runtime contract and the shipped files in `scripts/` consistent — change them
  together. `scripts/cli.py` is the prepared-project build/check/driver-rollover runtime; it does not
  ingest raw sources, render, or recalculate.

## Workflow

Edit this source folder, then deploy with `~/Dev/pi-dotfiles/rebuild.sh --sync-only`.

Run the tests before committing:

```sh
python3 -m unittest discover home/skills/equity-modelling/tests
```
