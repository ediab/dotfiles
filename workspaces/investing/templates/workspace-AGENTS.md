# Investing workspace

Ad hoc company modeling and pitch work. The user supplies a broker/company
Excel model, supporting documents and a question; the work product is an adapted
workbook copy, a change log with validation, and — when asked — an HTML
investment memo grounded in that workbook.

## Tooling lives outside this folder

Skills are registered here through `.agents/skills` → `@REPO_ROOT@/workspaces/investing/skills`.
Scripts, shared policies and the environment setup live in that repository
checkout, not here:

```sh
cd @REPO_ROOT@/workspaces/investing
.venv/bin/python scripts/inspect_workbook.py inspect <workbook> --out <record>.json
.venv/bin/python scripts/inspect_workbook.py guard --workbook <copy> --expect <sha256>
osascript scripts/excel_model.applescript edit workbook=<abs copy> changes=<changes.tsv> readback=<cells.tsv> out=<report>.tsv
```

Read these two before changing anything:

- `@REPO_ROOT@/workspaces/investing/references/workflow-policy.md` — the
  inspect → propose → approve → edit a copy → recalculate → validate → report
  contract, hash gating, and the A/B/C baseline separation.
- `@REPO_ROOT@/workspaces/investing/references/source-policy.md` — supplied data
  only; missing inputs are requested or flagged, never fetched or fabricated.

`@REPO_ROOT@/workspaces/investing/README.md` records what the Excel automation
actually does and where it stops.

## Assignment layout

One folder per assignment, created on request (never prepopulated):

```text
<assignment-name>/
├── inputs/    untouched supplied originals and evidence (read-only)
├── working/   drafts, inspection records, mapping, approved change list, B and C copies
└── outputs/   delivered workbook, memo, change log, validation summary
```

## Standing rules for this folder

- Never write to a supplied original; work on copies and hash-gate them.
- Never fetch financial data, prices, consensus or catalysts. Ask for what is
  missing, or mark it `MISSING`.
- One supplied broker model is not consensus.
- Keep supplied broker files out of git; this folder is not a repository.
- Excel automation touches only the workbook it was told to open; the running
  Excel session is otherwise left as found.
