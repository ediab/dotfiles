---
name: audit-xls
description: Audit a supplied Excel model for formula errors, inconsistent formulas, broken or stale links, hardcode overrides and failed statement tie-outs, and report located findings with severity. Use when asked to audit or check a workbook, sanity-check a model, find formula errors, check whether a model balances or ties out, or assess whether a supplied model is safe to rely on.
---

# Audit a supplied workbook

Report findings. **Fix nothing without a separate approved change list** — the
audit itself is read-only, end to end.

Shared rules: [`workflow-policy.md`](../../references/workflow-policy.md)
and [`source-policy.md`](../../references/source-policy.md).
Tool limits and verified capabilities: [`../../README.md`](../../README.md).

## Environment

Derive the toolset root (scripts, policies, venv) once, so every command below
works from any directory:

```sh
TOOLSET="$(dirname "$(readlink -f ~/Investing/.agents/skills)")"   # investing toolset root
```

## 1. Inspect read-only

```sh
"$TOOLSET/.venv/bin/python" "$TOOLSET/scripts/inspect_workbook.py" \
    inspect <workbook> --out <assignment>/working/inspect.json
```

The inspection record is the source of sheet names, formula counts, stored
errors, external links, names, hidden content and calculation mode — including
`autoNoTable`. Record the file's SHA-256. Treat every count as an observation:
a formula count is not a correctness measure, and a cached value proves nothing
about whether the function that produced it still works.

## 2. Establish the baseline before judging any number

Stored results may be stale, so an audit that reads only the cached file
misreads the model's actual state. Follow state A/B in the workflow policy:
hash and extract A, then recalculate an unedited copy (B) with links not updated
and compare A→B.

Report what the environment did to the numbers — missing add-ins, unresolved
external references, cells that only had cache before, `fullCalcOnLoad`. An
A→B difference is environment drift, not a finding about the model's logic; it
is reported separately and first, because it changes what the other checks mean.

## 3. Formula-level checks (every audit)

Run all of these against the inspection record and the recalculated copy:

| Check | What to report |
| --- | --- |
| Error values | `#REF!`, `#VALUE!`, `#N/A`, `#DIV/0!`, `#NAME?`, `#NULL!` — sheet, cell, formula |
| Hardcodes inside formulas | a literal that should be a referenced assumption (`=A1*1.05`) |
| Inconsistent neighbours | a cell breaking the pattern of its row or column (the same operation applied to every peer, except one) |
| Range edges | `SUM`/`AVERAGE` ranges that miss the first or last member of a block |
| Pasted-over formulas | a block that reads as a calculation but holds constants |
| Broken cross-sheet references | references to cells, sheets or names that no longer exist |
| Circular references | the loop's cells, and whether an iteration toggle exists |
| Unit and scale mismatch | thousands mixed with millions, percents stored as whole numbers, a units row that contradicts the values |
| Hidden rows, columns and sheets | what they hold — overrides and stale calculations hide there |

Then classify: a hardcoded *assumption* in an input row is normal modelling. A
hardcoded *result* inside a calculation block is a finding. Say which is which
per cell; do not report inputs as defects.

## 4. Model-integrity checks (when the workbook contains statements)

Only where the workbook actually has the corresponding lines, and using the
assignment's mapped cells:

- **Balance sheet**: total assets vs total liabilities and equity, every period.
  Quantify the gap per period and trace it to where it starts.
- **Retained earnings**: prior RE + net income − dividends vs current RE. Use
  the model's own line items; do not impose a textbook roll-forward — a
  company's SBC or dividend treatment may legitimately sit elsewhere.
- **Cash flow**: CF ending cash vs balance-sheet cash; CFO + CFI + CFF vs the
  change in cash; D&A and capex against the statement and the PP&E schedule;
  working-capital signs against balance-sheet movements.
- **Income statement**: revenue build against segment or product detail; tax
  against pre-tax income and the stated rate; share count against the dilution
  schedule.
- **Valuation, where present**: enterprise-to-equity bridge, net debt sign and
  period, share count and timing conventions, cash flows discounted in the
  period they belong to, terminal value discounted at all, unlevered cash flow
  actually unlevered, WACC inputs sourced rather than typed.
- **Reasonableness**: growth, margins, terminal-value share of value,
  compounding that reaches implausible levels, and behaviour at 0% or negative
  growth. Flag these as questions, not errors.

Do not assert an identity the model is not built to satisfy, and do not call a
tie-out failure a "critical error" before locating the line that breaks it.

## 5. Report

Findings table, most severe first — one row per finding, with location:

| # | Sheet | Cell / range | Severity | Category | Issue | Evidence |
| --- | --- | --- | --- | --- | --- | --- |

- **Critical** — a wrong output: statements that do not tie, a broken formula
  feeding results, valuation arithmetic that contradicts the model's own inputs.
- **Warning** — risky: overrides, inconsistent formulas, stale links, edge cases
  that break, unverified dependencies.
- **Info** — style, convention, layout.

Prepend a summary: workbook type, overall state (clean / minor / major issues),
counts by severity, and — separately — the baseline drift observed in step 2.

Then, and explicitly:

- what could **not** be audited (macros, provider functions with no cache,
  protected sheets, add-in-dependent formulas),
- inherited problems that are **out of scope** for the current assignment,
- whether the model is fit to carry the assignment's decisions, and what it
  would take to make it so.

Never claim the model is correct because recalculation produced no new error
cells.
