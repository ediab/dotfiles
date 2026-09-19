---
name: model-update
description: Update a supplied Excel model with user-supplied actuals, guidance or revised assumptions — map the supplied figures to cells, propose a bounded change list, edit a copy after approval, recalculate, and report dependent effects. Use when asked to plug earnings, refresh estimates, update a model with new data, revise forecasts, or change assumptions in a supplied workbook.
---

# Update a supplied model

Trigger, in every case, is **supplied information**: reported actuals, company
guidance, an updated broker file, or an explicit user assumption. This skill
never sources a number itself.

Shared rules: [`workflow-policy.md`](../../references/workflow-policy.md) and
[`source-policy.md`](../../references/source-policy.md). Verified capabilities
and limits: [`../../README.md`](../../README.md).

## Environment

Derive the toolset root (scripts, policies, venv) once, so every command below
works from any directory:

```sh
TOOLSET="$(dirname "$(readlink -f ~/Desktop/Fundaments/.agents/skills)")"   # investing toolset root
```

## 1. Map the supplied information to cells

First inspect, then map. Use the assignment's inspection record and a written
mapping file (`working/mapping.md`) that ties each supplied figure to a sheet and
cell:

| Supplied item | Value | Source (file, page/sheet) | Target sheet | Target cell |
| --- | --- | --- | --- | --- |

Build the mapping by reading the model, not by assuming a layout, and keep it in
the assignment folder: the same map is reused for the memo's evidence record.

If a figure the model needs is not supplied, list it under **missing inputs** and
say what it blocks. Do not substitute a remembered number, a provider value, or
a placeholder that looks like data.

## 2. Establish the baseline (state A→B)

Per the workflow policy: hash A, extract A's cached values, then recalculate an
unedited copy. Report A→B drift before proposing anything — if the baseline
itself is unsound, say so and stop rather than editing on top of it.

## 3. Propose the bounded change list

One row per cell. The old and new content, the reason, and the supplied source
or the user assumption behind it:

| Sheet | Cell | Old | New | Reason | Source |
| --- | --- | --- | --- | --- | --- |

Keep the list to what was asked for. In particular:

- **Period roll or actuals plug**: fill the reported periods, leave the forecast
  periods alone unless the supplied guidance covers them.
- **Guidance change**: change only the drivers that guidance covers, and record
  the implied output changes as expected propagation, not as edits.
- **Repairing an inherited error** is a different job. Report it; do not fold it
  into this list.

Present the list and ask for approval **once**. After approval, run the whole
sequence without asking again.

## 4. Apply, recalculate, validate

```sh
"$TOOLSET/.venv/bin/python" "$TOOLSET/scripts/inspect_workbook.py" \
    guard --workbook <C copy> --expect <approved sha256>
osascript "$TOOLSET/scripts/excel_model.applescript" edit \
    workbook=<abs C copy> changes=<changes.tsv> readback=<cells.tsv> out=<report>.tsv
"$TOOLSET/.venv/bin/python" "$TOOLSET/scripts/inspect_workbook.py" \
    diff <B copy> <C copy> --out <working>/diff-BC.json
```

- C is a **fresh copy of A** — never a copy of B.
- The guard must pass; a changed hash means re-inspect and re-approve.
- The original is never written to. Its hash is checked again after the run.
- `excel_model.applescript` refuses to run while unrelated workbooks are open.

Validate in the order that separates causes:

1. **Direct edits** — the cells in the list carry exactly the approved values.
2. **Propagation** — dependent outputs moved, and where the change is
   arithmetically checkable (a driver times a supplied price, a margin applied
   to revenue), the recalculated value matches the arithmetic independently.
3. **Tie-outs still hold** — the model's own balance/cash checks, within the
   declared rounding tolerance.
4. **Nothing else moved** — cells outside the expected propagation are
   unchanged. An unexplained change is a finding, not a rounding artefact.

## 5. Forward estimates

Adjust forward periods only from supplied guidance or approved assumptions, and
state the reason per assumption. Show each revision as old → new with the delta:

| Line item | Old FY est. | New FY est. | Delta | Why (source) |
| --- | --- | --- | --- | --- |

Reconcile reported figures before projecting from them: reported is not the same
as adjusted, and one-off items must be identified as such. If the model's
forecast depends on consensus or a market price the assignment does not supply,
write **MISSING: source not supplied** instead of a number, and say which
outputs are blocked by it — one supplied broker file is not consensus.

## 6. Valuation impact

Recalculate valuation **only** through the model's own machinery and only with
supplied inputs (multiples, discount rate, share count, price). Report prior vs
updated for whichever methods the model actually implements, and mark any
method that cannot be recomputed for want of a supplied input. Do not present a
price target as decision-ready when the share count, price or multiple behind it
is missing.

## 7. Report

- Change log: every approved cell, old → new, reason, source.
- Dependent outputs: before → after, with independent arithmetic checks where
  the maths is checkable by hand.
- Baseline drift (A→B) and edit effects (B→C), reported separately.
- Unresolved inherited issues, counted and located — not quietly repaired.
- Original hash unchanged; the C workbook hash; the delivered file name.
- Technical validation (opened, recalculated, saved, formulas and features
  preserved) separated from financial validation (linkages, arithmetic,
  tie-outs).

A clean recalculation is not a clean model. Say what was checked and what
remains unverified.
