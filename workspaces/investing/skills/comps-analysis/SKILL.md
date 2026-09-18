---
name: comps-analysis
description: Build a comparable-company analysis from user-supplied peer and market data — enterprise values, multiples, margins, growth and summary statistics in Excel, with units and fiscal periods declared and non-meaningful denominators flagged rather than averaged. Use when asked for comps, comparable companies, peer multiples, a trading-comparables table, or a relative-value screen, when the peer data is supplied.
---

# Comparable company analysis

Peer data, prices, share counts and financials are **supplied**. This skill never
retrieves a price, a multiple or a peer set, and never treats one supplied broker
file as consensus.

Shared rules: [`workflow-policy.md`](../../references/workflow-policy.md),
[`source-policy.md`](../../references/source-policy.md), and the mechanics in
[`financial-modeling.md`](../../references/financial-modeling.md) (comparables
section). Data requirements are the opening question, not an afterthought.

## Environment

```sh
TOOLSET="$(dirname "$(readlink -f ~/Investing/.agents/skills)")"   # investing toolset root
```

## 1. Establish what was supplied — and what each figure is

Before computing anything, write down per peer, per figure:

| Requirement | Why it matters |
| --- | --- |
| Share price **and its date** | a comps table is a point-in-time statement; a price without a date is not usable |
| Diluted share count | market cap = price × diluted shares, not basic |
| Net debt (or net cash) **and its date** | EV = market cap + net debt + minorities + preferred |
| Revenue, EBITDA, EPS with **the fiscal period they cover** | LTM, FY, or a forecast year — mixing them is the most common comps error |
| The **units** of every figure | thousands vs millions vs actuals |
| Whether each figure is **reported or adjusted** | an adjusted EBITDA against a reported multiple is apples-to-oranges |

Missing requirements are requested or listed as `MISSING`, and any multiple
depending on them is withheld rather than approximated.

## 2. Build the table with formulas, in a copy

Edits go through native Excel on a working copy, per the workflow policy
(`excel_model.applescript`), or — when the comps sheet is new rather than
inherited — as a new workbook whose cells carry formulas, not typed results.

```text
Market cap      = price × diluted shares
Enterprise value = market cap + net debt + minority interests + preferred
EV/Revenue      = EV / revenue            EV/EBITDA = EV / EBITDA
P/E             = market cap / net income FCF yield = FCF / market cap
```

Every ratio references the raw figure once, in the same sheet: no raw figure is
entered twice, and no multiple is typed as a number.

## 3. Statistics, and what does not get one

Add max, 75th percentile, median, 25th percentile and min **for ratios only** —
margins, growth rates, multiples, yields — plus the count behind each. Size
metrics (revenue, EBITDA, market cap, EV) do not get a median: averaging
differently sized companies is not a statistic.

## 4. Required flags before any conclusion

State these explicitly in the deliverable; each one changes how the table may be
read:

- **Period mismatches** — companies on different fiscal calendars, LTM vs FY vs
  forecast. Show the period per company and flag any comparison across periods.
- **Unit/scale mismatches** — thousands vs millions, or a currency mix without
  the FX rate supplied.
- **Non-meaningful denominators** — negative EBITDA or earnings, near-zero
  revenue. Show `n/m`, exclude from the statistics, and list what was excluded.
- **Adjusted vs reported** — name which the figure is, per company.
- **Outliers** — a multiple that is an order of magnitude away from its peers is
  a question about that company, not a data point to bridge the distribution with.
- **Single-source caveat** — where one supplied broker drives the whole peer set,
  say so; that is one view, not consensus.

## 5. Verify before reporting

```sh
"$TOOLSET/.venv/bin/python" "$TOOLSET/scripts/inspect_workbook.py" checks <comps workbook> --out <working>/comps-checks.json
"$TOOLSET/.venv/bin/python" "$TOOLSET/scripts/inspect_workbook.py" verify --workbook <comps workbook> --evidence <evidence.json>
```

Independently recompute at least: enterprise value for two companies, one
multiple per company, and the median of one multiple. Compare against the
workbook and state the tolerance. Then check the table for the failure modes a
recalculation cannot see: a typed-over formula, a hardcoded multiple, a ratio
pointing at the wrong column, and a statistic that silently included an `n/m`.

## 6. Report

- The peer table with declared units and periods, plus the statistics block.
- The flags from step 4, listed, not buried.
- The verification: which values were recomputed independently, and with what
  tolerance.
- What is missing, and which conclusion it blocks.
- A relative-value *observation* only where the supplied data supports it: a
  single broker's estimates are not consensus, and a comps table without
  supplied prices for the target itself cannot place the target in the table.
