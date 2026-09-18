# Sector drivers

Reference for `scenario-analysis`, `model-update` and `investment-memo` when the
company is an industrial, a semiconductor name, or a software/cloud business —
the user's coverage. Consult the branch that matches the supplied model; **do not
assume every company reports every metric below.** If a driver is not in the
supplied model or supplied documents, it is missing evidence, not a gap to fill
from memory.

The point of this file is to know *which line in the supplied model* a driver
should move, so a change list targets the right cell and the propagation can be
verified.

## Industrials — orders, backlog, capacity

| Driver | Where it usually lives | What moves with it |
| --- | --- | --- |
| Orders / bookings | orders row, often quarterly, sometimes TTM | forward revenue, and backlog with a lag |
| Backlog | backlog row, sometimes split by segment | revenue conversion, capacity utilisation |
| Book-to-bill | orders ÷ revenue for the period | the direction of the backlog, and the revenue ramp |
| Capacity / utilisation | capex rows, capacity or unit rows, utilisation % | capex, depreciation, incremental margin on the next volume tranche |
| Price / cost | price and material-cost rows, or margin % by segment | gross margin, incremental margin |
| Aftermarket / service | service revenue split | margin mix, recurring revenue share |

Tests specific to this shape:

- Backlog is a stock and orders a flow: a plausible model has revenue converting
  from backlog with a lag, not equal to orders in the same period.
- Capacity additions set the ceiling on the volume ramp; a revenue forecast that
  outruns supplied capacity guidance is a question for the user.
- Incremental margin on the next tranche of volume is usually higher than the
  average margin — check the model says so, and that the number is supplied.

## Semiconductors — product and mix cycles

| Driver | Where it usually lives | What moves with it |
| --- | --- | --- |
| Product revenue vs services/other | segment revenue rows with their own growth rows | total revenue and mix |
| Product gross margin | product cost row or margin % row | gross margin, and the incremental margin |
| Mix shift (new node / new product) | mix % rows, ASP rows | margin and revenue per unit |
| ASP / units | ASP and unit rows where the model carries them | revenue build |
| Cycle position (inventory, lead times) | inventory turns, DSO | working capital, cash conversion, and the revenue ramp |
| Capex intensity | capex % of revenue | depreciation lag, cash flow |

Tests specific to this shape:

- A sequential growth pattern that swings from deeply negative to strongly
  positive (as in the supplied Vertiv model: −19%, then +20%, +13%, +16%) is the
  load-bearing assumption — name it in the memo's disconfirmers.
- Product and services margins usually differ materially; a blended margin rise
  that comes mostly from mix should be described as mix, not as productivity.
- Inventory turns and DSO moving the wrong way while revenue accelerates is a
  working-capital warning, not a rounding detail.

## Cloud / software — segments, cohort and capex

| Driver | Where it usually lives | What moves with it |
| --- | --- | --- |
| Segment revenue with its own growth | segment rows | total revenue, mix |
| Recurring vs transactional split | subscription/usage rows | revenue quality, margin |
| Net revenue retention / churn | cohort or retention rows, if supplied | the growth rate's durability |
| Gross margin by segment | cost-of-revenue rows | blended gross margin |
| S&M / R&D as % of revenue | opex % rows | operating leverage |
| Capex / capitalised software | capex rows, capitalised software | D&A later, and FCF now |
| Deferred revenue | balance-sheet and CF rows | cash conversion vs revenue recognition |

Tests specific to this shape:

- "Rule of 40" (growth % + FCF margin %) and FCF conversion are useful only if
  the model carries the inputs; never import a growth or margin figure from
  outside the assignment.
- Capitalised software and SBC both move cash and equity in ways that are easy to
  double-count; check the model's own treatment before adding either to a roll-
  forward.
- Deferred revenue growth means cash arrives before revenue: if the model's cash
  conversion looks implausibly good, this line is usually why.

## Cross-sector rules

- The driver rows differ by sector; the **verification discipline does not**.
  Trace each changed driver through the model, recompute at least one dependent
  output by hand, and confirm nothing outside the expected propagation moved.
- Segment detail is where a scenario becomes interesting, and also where a model
  is most often internally inconsistent. Check that segment revenue sums to total
  revenue and that segment margins reproduce the blended margin within tolerance.
- Working capital connects the income statement to the cash flow statement in
  every sector: DSO, DPO, inventory turns, accrued expenses. Industrial and
  semi cycles show up there first.
- A driver that exists in the model but that no supplied document supports is an
  assumption: record it as one, with its source field naming the user or the file
  it came from.
