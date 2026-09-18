---
name: 3-statement-model
description: Complete, extend or repair a linked three-statement model in a supplied Excel workbook — income statement, balance sheet and cash flow — so a changed operating driver flows through all three with the balance sheet and cash tie-outs holding. Use when asked to build or finish a 3-statement model, link the statements, fix a model that will not balance, add working-capital or debt schedules, or check statement tie-outs.
---

# Three-statement model

The supplied workbook decides the layout, the line items and the conventions.
This skill completes or extends what is there; it does not impose a preferred
template, and it does not rebuild a model wholesale.

Shared rules: [`workflow-policy.md`](../../references/workflow-policy.md),
[`source-policy.md`](../../references/source-policy.md) and the linkage formulas
in [`financial-modeling.md`](../../references/financial-modeling.md). Sector
driver detail: [`sector-drivers.md`](../../references/sector-drivers.md).

## Environment

```sh
TOOLSET="$(dirname "$(readlink -f ~/Investing/.agents/skills)")"   # investing toolset root
```

## 1. Read the model before touching it

Inspect, then establish the baseline (state A→B) per the workflow policy. Then
answer these questions **from the file**, writing the answers into the assignment
mapping:

- Which sheet is the income statement, which the balance sheet, which the cash
  flow, and which rows are inputs versus formulas?
- Which period is the last actual and which the first forecast?
- Where do the statements link (net income → CFO, ending cash → BS cash, D&A →
  CF add-back, capex → PP&E schedule, debt movements → CFF)?
- What are the model's own check cells, and do they evaluate? A check containing
  `#REF!` is dead: report it, because nothing downstream was validated.
- What are the model's conventions (SBC inside or outside RE, leases, minority
  interests, dividend treatment)? Follow them.

## 2. Propose the bounded change list

Repairs and additions are changes like any other: cells, old and new content,
reason, source, expected downstream effects. Ask once for the whole list.

Typical work, in the order that keeps the model coherent:

1. **Complete missing links** — a statement line with no source (e.g. ending cash
   not linked to the BS, or tax not driven by pre-tax income).
2. **Add the schedule that makes a line honest** — working capital by days, PP&E
   by capex and depreciation, debt by drawdowns and repayments, retained earnings
   by the model's own equity movements.
3. **Keep check cells working** — a tie-out row that cannot evaluate is worse
   than no check, because it looks like one.

Do not "fix" a line by replacing a formula with a constant, and do not delete a
link because the source is missing: mark the gap and ask.

## 3. The three statements must close

```text
BS:        assets − liabilities − equity = 0  (every period)
Cash:      BS cash − CF ending cash       = 0  (every period)
CF sum:    CFO + CFI + CFF − Δcash        = 0
RE:        prior RE ± NI ± dividends − BS RE = 0   (the model's own convention)
D&A:       IS D&A = CF add-back            capex: CF capex = PP&E schedule capex
```

When the balance sheet does not close, **quantify the gap per period first**, then
trace it to the period it first appears. A one-period break is usually a single
mislink; a growing gap is a flow statement (RE, WC, or debt) that is not feeding
the stock.

## 4. Prove a driver flows through all three

The test of a linked model is not that it recalculates, it is that a change
propagates correctly:

```sh
"$TOOLSET/.venv/bin/python" "$TOOLSET/scripts/inspect_workbook.py" guard --workbook <C copy> --expect <sha256>
osascript "$TOOLSET/scripts/excel_model.applescript" edit workbook=<abs C copy> changes=<changes.tsv> readback=<cells.tsv> out=<report>.tsv
"$TOOLSET/.venv/bin/python" "$TOOLSET/scripts/inspect_workbook.py" diff <B copy> <C copy> --out <working>/diff-BC.json
```

With one operating driver changed (revenue growth, a margin, a working-capital
day count), confirm:

- the IS line moved, and its margin moved with it;
- the cash flow moved through the matching channel (working capital through CFO,
  capex through CFI, debt or dividends through CFF);
- the balance sheet moved on both sides — the asset *and* the funding line;
- the check cells still read zero within the declared tolerance;
- nothing outside the expected propagation changed.

Hand-check at least one number in the chain (revenue × margin, or ΔWC from a day
count) so the workbook is not the only witness to its own arithmetic.

## 5. Report

- The change list with old → new, reason and source.
- The gap analysis before and after (per period), if the model did not balance.
- Which check cells now evaluate and which remain dead, with locations.
- The propagation check from step 4, and the hand-checked arithmetic.
- Inherited problems left in place: mixed units, scale mismatches, hardcoded
  overrides inside calculation blocks, hidden rows holding stale values.
- Rounding tolerance used, and where conventions differ from the textbook
  presentation (SBC, leases, minority interests) so the reader knows the model's
  own basis.

Technical success (it recalculates, nothing new broke) is reported separately
from financial success (the statements tie and the driver propagated as intended).
