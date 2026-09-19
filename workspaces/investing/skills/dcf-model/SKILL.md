---
name: dcf-model
description: Build, complete or audit a discounted cash flow in a supplied Excel model — unlevered free cash flow, WACC, discounting convention, terminal value, enterprise-to-equity bridge and per-share value — using only supplied inputs, and verify the arithmetic against independently computed expectations. Use when asked for a DCF, intrinsic value, implied share price, WACC, terminal value, or to check whether an existing DCF's maths is right.
---

# Discounted cash flow

Every input is supplied: cash-flow drivers from the model, and WACC components
(risk-free rate, beta, equity risk premium, cost of debt, capital structure),
terminal assumptions (growth rate or exit multiple), net debt, and diluted share
count. **This skill retrieves nothing.** No SEC filings, no market data, no
consensus, no prices. A missing input is requested or the affected output is
withheld.

Shared rules: [`workflow-policy.md`](../../references/workflow-policy.md),
[`source-policy.md`](../../references/source-policy.md), and the DCF mechanics in
[`financial-modeling.md`](../../references/financial-modeling.md).

Upstream provenance: this is the adapted `dcf-model` skill from the licensed
Anthropic material, **with its SEC/analyst retrieval core removed** — no fetching
module, no `requests` dependency, no live data path. See
[`../../UPSTREAM.md`](../../UPSTREAM.md).

## Environment

```sh
TOOLSET="$(dirname "$(readlink -f ~/Desktop/Fundamentals/.agents/skills)")"   # investing toolset root
```

## 1. Confirm the inputs exist before building anything

| Input | Supplied source | If missing |
| --- | --- | --- |
| Unlevered FCF drivers (revenue growth, margins, tax, D&A, capex, ΔWC) | the model | ask; do not borrow a generic percentage |
| Risk-free rate, with its date | user | ask — it is a market input, not an assumption to invent |
| Beta and equity risk premium | user | ask |
| Cost of debt and tax rate | user / model | ask |
| Capital structure weights | user (market value equity, net debt) | ask |
| Terminal growth rate or exit multiple | user | ask |
| Net debt as of a stated date, and share count basis | model / user | ask |
| Discounting convention (mid-year or end-year) | user; if unstated, choose and **declare** | state the choice in every output |

A DCF with a requested input missing is not "illustrative" — it is incomplete.
Label it that way and stop before producing a per-share number.

## 2. Build or extend in the workbook, with formulas

Follow the workflow policy: inspect, propose the bounded change list, approve,
fresh copy of A, hash guard, then `excel_model.applescript` for the edits. If the
model has no DCF at all, adding one is a structural change and needs its own
approved list; do not silently append sheets to an inherited model.

```text
NOPAT         = EBIT × (1 − tax rate)
Unlevered FCF = NOPAT + D&A − capex − ΔNWC          (no interest deducted: it is unlevered)
Discount      = 1 / (1 + WACC) ^ period             period = 0.5, 1.5, … under mid-year
PV of TV      = terminal value × discount factor of the terminal period
EV            = Σ PV(FCF) + PV(TV)
Equity        = EV − net debt − minority interests − preferred
Per share     = equity / diluted shares
WACC          = cost of equity × equity weight + after-tax cost of debt × debt weight
Cost of equity = risk-free + beta × equity risk premium
```

Conventions that must appear in the output, because they change the answer:
mid-year or end-year discounting; the date of net debt; diluted shares and their
source; whether the terminal value was discounted; terminal method; and whether
cash flows are truly unlevered.

## 3. Independently verify the arithmetic — the workbook is not the witness

Recompute, outside the workbook, for a small known-input case: NOPAT, unlevered
FCF per year, each discount factor, PV of each year, terminal value, PV of the
terminal value, enterprise value, the equity bridge and per-share value. Compare
against the workbook's cached values with an explicit tolerance and record the
comparison as an evidence file:

```sh
"$TOOLSET/.venv/bin/python" "$TOOLSET/scripts/inspect_workbook.py" verify --workbook <dcf workbook> --evidence <evidence.json>
```

Then check the failure modes that a recalculation cannot reveal:

- terminal value above roughly 80% of enterprise value;
- terminal growth at or above WACC (infinite value);
- interest deducted inside "unlevered" FCF;
- the terminal value not discounted, or discounted by the wrong period;
- WACC built on book values, or a stale risk-free rate;
- net debt added when it should be subtracted (and vice versa for net cash);
- a per-share value divided by basic shares while the model dilutes elsewhere;
- sensitivity tables whose cells are typed numbers rather than recalculations.

## 4. Sensitivity

Grids are allowed only from supplied axes and with every cell a real
recalculation. Verify the corners by hand, keep the grid small, and never present
a stored data-table cache as a fresh sensitivity — a workbook in `autoNoTable`
mode keeps its old table values, and AppleScript cannot re-set that exception.

## 5. Report

- The build or the audit findings, per convention: discounting, net debt date,
  share count, terminal method.
- The independent recomputation table: each component, workbook value,
  independently computed value, tolerance, pass/fail.
- WACC build-up with each input's source.
- Sensitivities, with corners verified and the axes' sources.
- What is missing and what it blocks; a per-share value is withheld when a
  required input is absent.
- Unresolved inherited issues (dead check cells, mixed units, hardcoded
  overrides) and whether they touch the DCF.

A DCF that recalculates cleanly is not a correct DCF: report the arithmetic
verification and the convention choices separately from the valuation conclusion,
and never present a per-share output as decision-ready while an input behind it
is missing.
