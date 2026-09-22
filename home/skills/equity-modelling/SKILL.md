---
name: equity-modelling
description: Pilot-only workflow for building or updating a source-driven public-equity earnings model from a user-supplied source pack.
---

# Equity modelling

Build or update one editable, formula-driven public-equity earnings model. The VRT pilot passed
its exit criteria in `SPEC.md`; `company-model` remains available until retired.

Read `references/model-rules.md` before building. For an earnings update, also read
`references/update-model.md` before changing anything. Use the `excel` skill for workbook
construction, recalculation, and rendering.

## Boundaries

- The user's supplied files are the model evidence. Web research may challenge them, but a
  web-found number stays outside the workbook until the user supplies it.
- Discover five to ten company-specific primary drivers during the run. Do not substitute a
  sector template.
- Forecast eight quarters. Derive annual periods on the same model sheets.
- Build a full earnings model plus thesis-relevant cash-flow and balance-sheet items. Expand to
  three statements only when liquidity, leverage, working capital, or balance-sheet risk requires
  it.
- Keep guidance and consensus as benchmarks. Keep business-event scenarios separate from
  mechanical sensitivities.
- Write every delivery to a new dated path. A prior workbook is immutable.

## Workflow

### 1. Inventory the source pack

Classify the run as a new model or an update. Record the company, ticker, fiscal calendar, model
as-of date, intended output directory, supplied files, periods, units, accounting basis, segment
disclosures, guidance, consensus, price evidence, conflicts, and missing items. Hash each supplied
file. Do not fetch replacement model data.

For an update, preflight the existing workbook and follow `references/update-model.md`.

**Done when:** the evidence boundary, fiscal periods, usable sources, gaps, conflicts, and a fresh
output path are explicit.

### 2. Interview the business

Ask at most four questions at a time. Start with business economics, then establish reporting and
economic segments; volume, price, mix, capacity, utilization, backlog, or other operating drivers;
cost and margin structure; cash conversion and capital intensity; thesis, variant perception,
risks, and falsifiers; and decision-relevant valuation metrics.

Select five to ten primary drivers. Use units × price/mix only where operating evidence supports
it; otherwise use explicit segment growth. Treat any unsupported driver as a visible analyst
assumption with rationale, uncertainty, and scenario treatment.

**Done when:** the driver set, segment structure, profit bridge, statement depth, scenario events,
and valuation lenses are specific enough to build.

### 3. Propose the blueprint — Gate 1

Present one concise blueprint: sheets, period grid, segments, driver equations, profit bridge,
cash and balance-sheet scope, guidance/consensus comparisons, scenarios, sensitivities, valuation,
and evidence gaps. Include 2–3 checkable success examples for this company. Stop for batch
approval before constructing the model.

**Done when:** the user approves or edits the blueprint and success examples.

### 4. Build the historical and evidence layer

Create the minimal company project from `references/model-rules.md`. Parse the supplied files into
canonical historical cells and `sources.csv`; each source value enters the workbook once. Record
source file, hash, locator, period, units, basis, and transformation. Use the latest reported
historical basis and log restatements. Keep missing values blank with a reason.

`check.py` must independently reparse the supplied evidence; it must not import expected values
from `build.py` or a shared parsed-values module.

**Done when:** displayed actuals reconcile to the source pack, each canonical value has provenance,
and every missing or conflicting item remains visible.

### 5. Propose forecast assumptions — Gate 2

Present one compact package covering all primary drivers across eight forecast quarters: values,
progression, rationale, evidence or analyst basis, uncertainty, guidance comparison, consensus
comparison, and scenario treatment. Keep the proposals inactive and forecast outputs blank. Stop
for batch approval.

After approval, record who approved the package, the date, and an approval id in
`forecast_inputs.csv`. User edits become explicit approved inputs; they do not alter guidance or
consensus.

**Done when:** every material driver is approved or rejected, and no forecast activates on partial
approval.

### 6. Build the forecast, scenarios, and decision view

Write company-specific formulas in the generated project's `build.py`. Forecast segments,
earnings, relevant cash and balance-sheet items, scenario cases, sensitivities, and valuation.
Show why the house view differs from guidance and consensus. Create the one-page `Outlook` view.

Use coherent business-event cases that change groups of assumptions. Put one-variable mechanical
sensitivities in a separate block. Leave unavailable outputs blank instead of inventing precision.

**Done when:** every forecast output traces to an approved driver or visible formula, annuals derive
from quarters, and the decision view states thesis, variant view, catalysts, risks, falsifiers, and
valuation basis.

### 7. Validate and deliver

Run the generated project's `check.py`, then the `excel` skill's prompt-free ASP recalculation.
Skip the native Excel gate in the standard run — it is slow and needs Excel closed. Run it only
when the workbook uses non-vanilla formulas (dynamic arrays, LAMBDA, newer functions) or the user
asks. Inspect the routine renders for `Outlook`, `Drivers`, `Scenarios`, `Valuation`,
and `Sources & Checks`; render the full workbook when the release risk warrants it.

Validation must cover source reconciliation, provenance coverage, unexpected hardcodes, formula
errors, core identities, GAAP/adjusted separation, annual conventions, missing-value propagation,
and one controlled driver change whose expected revenue, earnings, cash, and valuation effects
move while unrelated actuals and benchmarks do not. Run the web-challenge smoke test in
`tests/web-challenge-smoke.md` during the pilot.

Deliver the fresh dated workbook and state the approved assumptions, estimate differences,
evidence gaps, unresolved conflicts, and checks that could not run.

**Done when:** reconciliation and identities pass, no unexplained constants or new formula errors
remain, behavioural checks pass, critical renders are readable, and the prior workbook or source
pack remains unchanged.
