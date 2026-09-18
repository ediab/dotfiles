# Workbook workflow policy

Shared by every investing skill. This is the approval and evidence contract for
changing a supplied workbook: **inspect → propose → approve → edit a copy →
recalculate → validate → report**. No assignment skips a stage.

Environment capabilities, measured limits and the exact commands live in
[`../README.md`](../README.md) — read it before automating Excel. Cell
locations, sheet names and drivers are **never** hardcoded here; they come from
the assignment's inspection record.

## 1. Inspect the supplied original (read-only)

```sh
.venv/bin/python scripts/inspect_workbook.py inspect <original> --out <record>.json
```

Record the SHA-256 of the file that was inspected. `inspect_workbook.py` reads
OOXML and never writes to a workbook. Counts it reports (formulas, stored
errors, external links) are **observations**, not proof of financial
correctness.

## 2. Work on copies, and hash-gate them

The supplied original is never opened for writing, never saved, and never
recalculated in place. Every Excel run happens on a copy under the assignment's
`working/` directory.

Before any edit, prove the copy is still the artifact that was inspected and
approved:

```sh
.venv/bin/python scripts/inspect_workbook.py guard --workbook <copy> --expect <sha256>
```

A mismatch means the input changed: stop, re-inspect, and put a fresh change
list to the user. Editing a copy that failed the guard is a defect, not a
convenience.

## 3. Propose a bounded change list, then obtain approval

A change list is one row per cell, with the *old* and *new* content, the reason,
and the supplied source or explicit user assumption behind it. Present it in
chat. Then ask for approval once for the whole list.

- Approval is for **that list**. Growing it during the run means stopping and
  asking again.
- A change list that silently widens from "plug Q3 actuals" to "repair all
  inherited errors" is out of scope. Inherited problems are reported, not fixed
  by default.
- After approval, run the whole approved sequence without asking again. Ask
  again only for changed scope, material ambiguity, or a new financial
  assumption.

Record the approval in `working/approval.md`: what was approved, when, the
message reference if available, and the hash of the input it applies to. This is
an **audit trail, not enforcement** — no file an agent writes can prove the user
consented, so never describe it as authorization.

## 4. Edit with native Excel, then recalculate

```sh
cp <approval-hash-copy> <working>/<name>-C.xlsx        # fresh copy of the original for each attempt
osascript scripts/excel_model.applescript edit workbook=<abs C copy> changes=<changes.tsv> readback=<cells.tsv> out=<report>.tsv
```

`excel_model.applescript` writes nothing outside the workbook it was told to
open, refuses to run while unrelated workbooks are open (Excel's
`calculate full` recalculates every open workbook), disables macros and link
updates for the run, and restores Excel's settings on success *and* failure.
Prefer it over any Python library for **writes to inherited workbooks**;
openpyxl is for inspection and reading only.

Preserve inherited formulas, names and links unless replacing them is part of
the approved list. Replacing a broken formula with a constant, or deleting a
link, is a financial change and needs explicit approval.

## 5. Baseline separation A / B / C

Every real trial establishes three states:

| State | What it is | Why |
| --- | --- | --- |
| **A** | the original, with its cached values intact | the only record of what the broker shipped |
| **B** | an unedited copy recalculated in the tested environment, links not updated | separates *environment* drift from *edit* effects |
| **C** | the approved edited copy, recalculated under the same settings | the deliverable |

- Preserve A's cached evidence (hash + extracted values) **before** opening any
  copy in Excel.
- Build C from a fresh copy of A, never from B.
- Report **A→B** (missing add-ins, unresolved external references, recalculated
  caches, `fullCalcOnLoad`) separately from **B→C** (edit-related effects).
- If B's key outputs are unusable, the baseline is unsound: report it and stop
  rather than treating a broken baseline as noise.
- Sensitivity tables and `autoNoTable` workbooks are called out explicitly;
  an unchanged data-table cache is not a fresh sensitivity.

## 6. Validate, then report

`inspect_workbook.py diff` compares A/B/C at cell, formula, name, sheet and
error level. Report all four separately:

1. **Technical validation** — opened, recalculated, saved, formulas and
   features preserved (`README.md` lists what was verified).
2. **Financial validation** — the intended linkages and arithmetic, using the
   assignment's mapped cells and declared rounding tolerance.
3. **Unresolved inherited issues** — counted and located, with materiality where
   it can be established. "No new errors" is not "the model is correct".
4. **Changes** — direct edits versus expected propagation, from the change log.

Do not assert a universal accounting identity. Balance-sheet and cash tie-outs
are checked only where the workbook actually contains the corresponding lines
and where the convention matches the model's own.

## 7. Report deliverables

Per assignment, in the assignment's `outputs/`:

- the working `.xlsx` (state C) with its hash,
- a concise change log (old → new, reason, source) and validation summary,
- the inspection diff records,
- the memo/pitch when requested, with its evidence record.

Say plainly what was checked, what remains unverified, and which inputs are
still missing. A successful recalculation and zero new error cells prove
technical handling — not financial correctness.

## 8. Failure handling

- A failed run restores Excel's settings and closes only the workbook it opened.
- Excel is never killed to escape an error, and unrelated workbooks are never
  closed, saved or recalculated.
- If the required handling cannot be demonstrated safely (protected sheets,
  missing add-ins, circular references, unsupported objects, permission
  denial), narrow the scope and say so. Do not remove protection, flatten
  objects, or improvise repairs.
