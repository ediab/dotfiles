---
name: scenario-analysis
description: Build and run base, bull and bear cases in a supplied Excel model — define which drivers each case changes, apply the approved case to a copy, recalculate, verify that only the intended drivers moved, check a small sensitivity grid, and restore and save the delivery case. Use when asked for scenarios, base/bull/bear cases, upside/downside cases, a sensitivity table, or to test how a model responds to different assumptions.
---

# Scenario analysis on a supplied model

Scenarios are **approved driver changes**, not new forecasts and not a rebuilt
model. Everything comes from the supplied workbook or from user-supplied
assumptions.

Shared rules: [`workflow-policy.md`](../../references/workflow-policy.md),
[`source-policy.md`](../../references/source-policy.md) and the linkage
mechanics in [`financial-modeling.md`](../../references/financial-modeling.md).
Where to aim each driver, by sector: [`sector-drivers.md`](../../references/sector-drivers.md).

## Environment

```sh
TOOLSET="$(dirname "$(readlink -f ~/Investing/.agents/skills)")"   # investing toolset root
```

## 1. Name the drivers and the cases

Inspect first, then map. A case is a table of *driver cells and their values*
for each scenario — nothing else changes:

| Driver | Cell(s) | Bear | Base | Bull |
| --- | --- | --- | --- | --- |
| [from the inspection record's driver rows] | [sheet!range] | [value] | [supplied base] | [value] |

Rules that keep cases honest:

- **Base is the supplied model, unchanged.** Do not "improve" the base case.
- Bear and bull values are user-supplied assumptions or explicitly illustrative.
  A case whose numbers nobody supplied is labelled **illustrative** and cannot
  support a decision-ready conclusion.
- Probabilities only if supplied; otherwise the cases are unweighted and the
  deliverable says so.
- 3–6 drivers is usually the useful range. Every additional driver multiplies
  verification work without adding an answer.

## 2. Approve, then apply to a copy

Follow the workflow policy exactly: fresh copy of the original (state A), hash
guard must pass, one approval for the whole case set, edits via
`excel_model.applescript` (never a Python writer):

```sh
"$TOOLSET/.venv/bin/python" "$TOOLSET/scripts/inspect_workbook.py" guard --workbook <C copy> --expect <sha256>
osascript "$TOOLSET/scripts/excel_model.applescript" edit workbook=<abs C copy> changes=<case-changes.tsv> readback=<cells.tsv> out=<report>.tsv
```

Use one copy per case (`-base`, `-bull`, `-bear`) so each case's evidence stands
alone, and diff each against the baseline rather than against each other.

## 3. Verify that only the intended drivers moved

```sh
"$TOOLSET/.venv/bin/python" "$TOOLSET/scripts/inspect_workbook.py" diff <B copy> <bull copy> --out <working>/diff-B-bull.json
```

For each case, confirm in this order:

1. **Intended drivers** carry exactly the approved values — and no other input
   cell changed.
2. **Outputs recomputed**: the affected statements/valuation moved, and at least
   one dependent output is checked by hand arithmetic (a driver × a supplied
   price, a margin applied to revenue), not read back from the same formula.
3. **Nothing else moved**: any change outside the expected propagation set is a
   finding, not noise.
4. **Tie-outs still hold** within the declared tolerance, and no new error cells
   appeared.
5. **Ordering sanity**, where the model supports it: bull > base > bear for
   revenue, EBITDA, EPS and FCF. A case that inverts an ordering means a driver
   sign or a scenario reference is wrong.

## 4. Sensitivity grid

When the user wants a grid (WACC × terminal growth, price × volume, growth ×
margin), build it only from **supplied** axes, and make every cell a real
recalculation of the model, not an approximation:

- Recalculating a grid cell by cell means repeated `calculate full` runs, and
  each run restores Excel's settings. Do them in one Excel session per axis value
  rather than one per cell, and keep the number of cells small enough that you
  can independently check at least the corners.
- Independently verify the four corners by hand before presenting the grid.
- If the workbook uses data tables (`autoNoTable`), say so: Excel's data-table
  exception is not addressable from AppleScript, so a stored table cache is not
  a fresh sensitivity and must not be presented as one.

## 5. Restore and save the delivery case

The delivered workbook carries the **base case** unless the user asks for a
different one. After running cases:

- write the base values back into the delivery copy (a fresh copy of A, not a
  leftover case copy),
- recalculate, save, and confirm by reading the driver cells back: the delivery
  file must show the base values for every driver the scenarios touched,
- state in the summary which case the delivered file holds.

## 6. Report

- The case table: driver, cell, bear/base/bull values, and each case's source.
- Per case: outputs before → after, with the hand-checked arithmetic.
- The propagation check: what changed, what was expected to change, what did not.
- Sensitivity corners with their independent verification.
- The delivered case, its hash, and an explicit note that no other case is saved
  in it.

Report model response, not conviction: a scenario table proves the model does
what its formulas say, not that any case will happen.
