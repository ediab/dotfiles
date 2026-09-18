# Financial modelling reference

Shared conventions for `3-statement-model`, `dcf-model`, `comps-analysis` and
`scenario-analysis`. It is reference material, consulted on demand — the workflow
rules live in [`workflow-policy.md`](workflow-policy.md), and the data rules in
[`source-policy.md`](source-policy.md).

Adapted from the licensed Anthropic financial-services material (see
[`../UPSTREAM.md`](../UPSTREAM.md)); the changes are listed there, and the two
places where a generic upstream rule would have been wrong are called out below.

## Two rules that override any generic formula in this file

1. **Match the workbook, don't impose a template.** Every formula here describes
   a *convention*, and conventions differ between companies and brokers (SBC
   inside or outside retained earnings, D&A in COGS or below the line, lease
   treatment, minority interests). Read the supplied model's own structure first
   and follow it. An "identity" the model was never built to satisfy is not a
   finding.
2. **Do not assert an accounting identity universally.** The upstream
   retained-earnings roll-forward — `prior RE + net income + SBC − dividends` —
   is **not** a universal check. Plenty of companies present stock-based
   compensation inside paid-in capital rather than RE. Test the RE roll-forward
   only with the model's own line items, and say which convention you used.

## Core linkages

```text
Balance sheet      Assets = Liabilities + Equity
Income statement   Net revenue − cost of revenue = gross profit
                     − operating expenses, D&A → EBIT → EBITDA = EBIT + D&A
                     − interest → pre-tax income − tax → net income
Cash flow          ΔCash = CFO + CFI + CFF
Cash tie-out       Ending cash (CF) = cash (BS)
Retained earnings  prior RE ± net income ± dividends ± other equity movements = ending RE
Debt schedule      opening debt + drawdowns − repayments = closing debt
PP&E               opening gross PP&E + capex − disposals = closing gross PP&E
                     accumulated depreciation + depreciation − disposals = closing accumulated depreciation
```

## Operating and margin formulas

```text
Gross margin %      = gross profit / net revenue        (use NET revenue, never gross)
EBITDA              = EBIT + D&A
EBITDA margin %     = EBITDA / net revenue
EBIT margin %       = EBIT / net revenue
Net income margin % = net income / net revenue
```

Forecast by percentage of net revenue is the default only when the model already
works that way:

```text
Cost of revenue(forecast) = net revenue × cost-of-revenue % assumption
S&M / G&A / R&D(forecast) = net revenue × respective % assumption
```

## Working capital: days and turns are the honest form

A percentage-of-revenue plug hides what is happening; days/turns are checkable
against supplied operating data, so prefer them when the model has them:

```text
DSO  = (accounts receivable / revenue) × 365     Inventory turns = COGS / inventory
DIO  = (inventory / COGS) × 365                  DPO = (accounts payable / COGS) × 365
Net working capital = AR + inventory − AP        ΔWC = NWC(current) − NWC(prior)
```

A ΔWC that is positive consumes cash; negative releases it. Sign errors here are
among the most common inherited defects, so verify the direction against the
balance-sheet movement rather than trusting the label.

## Credit and leverage metrics

```text
Total debt = current portion + long-term debt (± lease obligations, per the model)
Net debt   = total debt − cash and equivalents        (negative net debt = net cash)
Total debt / EBITDA            Interest coverage = EBITDA / interest expense
Net debt / EBITDA              Debt / total capital = total debt / (total debt + equity)
Current ratio = current assets / current liabilities
Quick ratio   = (current assets − inventory) / current liabilities
```

With a net cash position, the debt weight in WACC is negative — that is
arithmetic, not an error. Say so rather than clamping it to zero.

## Check formulas (build them, then trust only the ones that resolve)

```text
Balance sheet:  assets − liabilities − equity            = 0
Cash tie-out:   BS cash − CF ending cash                 = 0
CF sum:         CFO + CFI + CFF − Δcash                  = 0
D&A match:      IS D&A − CF D&A (− CF D&A add-back)      = 0
Capex match:    CF capex − PP&E schedule capex           = 0
Tax:            tax expense − taxable income × rate      = 0  (deferred items explained, not ignored)
RE roll:        prior RE ± net income ± dividends − BS RE = 0  (using the model's own convention)
```

A check cell that *contains* `#REF!` is a dead check: it cannot evaluate, so
nothing downstream was validated. That is a finding in its own right, and it is
the defect present in the supplied Evercore workbook this toolset was built
against.

## Discounted cash flow mechanics

```text
NOPAT            = EBIT × (1 − tax rate)
Unlevered FCF    = NOPAT + D&A − capex − ΔNWC        (D&A added back, capex and ΔWC as outflows)
Discount factor  = 1 / (1 + WACC) ^ period           period = 0.5, 1.5, 2.5 … under a mid-year convention
PV of FCF        = FCF × discount factor
Terminal (perpetuity)  TV = final-year FCF × (1 + g) / (WACC − g)     requires g < WACC
Terminal (exit multiple) TV = final-year EBITDA × exit multiple
PV of TV         = TV × discount factor of the terminal period
Enterprise value = Σ PV(FCF) + PV(TV)
Equity value     = enterprise value − net debt − minority interests − preferred (± other claims)
Implied price    = equity value / diluted shares
```

Conventions to state explicitly in every deliverable, because the number changes
with each: **mid-year or end-year discounting**; **net debt as of which date**;
**diluted share count and its source**; **whether FCF is levered or unlevered**
(an unlevered DCF must not deduct interest); **terminal value method**; and
**whether the terminal value was discounted at all**.

Sanity checks that catch most DCF errors: terminal value above roughly 80% of
enterprise value; terminal growth at or above WACC; discounting the terminal
value by the wrong period; margins in the terminal year that the business has
never earned; and a WACC that uses book values or a stale risk-free rate.

## Comparables mechanics

```text
Market capitalisation = price × diluted shares
Enterprise value      = market cap + net debt + minority interests + preferred
                        (a net cash position reduces EV)
EV/revenue, EV/EBITDA, P/E = the relevant EV or equity value ÷ the metric
FCF yield = FCF / market cap        PEG = P/E ÷ growth rate
Statistics: max, 75th percentile, median, 25th percentile, min — and the count
```

Rules that make a comps table honest rather than merely tidy:

- **Units and periods must match before anything is divided.** Mixing a
  calendarised LTM figure with a fiscal-year figure, or thousands with millions,
  produces a multiple that looks fine and is wrong. Declare units and period per
  company, and flag mismatches instead of silently averaging them.
- **A non-meaningful denominator is not a data point.** Negative EBITDA, a
  negative P/E, or revenue near zero makes the multiple meaningless: show `n/m`,
  exclude it from the statistics, and say what was excluded and why.
- **Size metrics do not get a median.** A median market cap across differently
  sized companies is not a statistic; margins and multiples are.
- Reference each raw figure once. If revenue sits in one cell, every ratio
  divides *that* cell.

## Rounding and tolerance

State a tolerance per check rather than eyeballing: currency in millions typically
tolerates ±1 (display rounding) or ±0.01 (statement precision); ratios and
margins tolerate ±0.0005; per-share values ±0.01; tie-outs zero ±1e-6 when the
model carries full precision. `inspect_workbook.py verify` takes the tolerance per
evidence item, which is what makes rounding an explicit choice rather than a
hidden fudge.
