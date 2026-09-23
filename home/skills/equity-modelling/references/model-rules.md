# Model rules

Workbook contract for an `equity-modelling` project: the prepared-project shape, the workbook
sheets, periods, presentation, hardcode policy, decision integrity, and the web-challenge record.
The executable workflow and both approval gates live in `SKILL.md`. This file owns no schema and no
command: artifact schemas, entry points and the locator grammar are in `interfaces.md`; the evidence
conventions as rules are in `evidence-rules.md`; earnings updates and rollover are in
`update-model.md`.

## Prepared project

The runtime consumes a prepared project directory that already holds frozen artifacts:

```text
<TICKER>/
├── model_spec.json
├── fact_map.json
├── evidence/actuals.csv
├── evidence/benchmarks.csv        # optional
├── drivers.csv
├── drivers.approval.json          # present only when a driver is approved
├── model_<TICKER>.py
└── <TICKER>_Model_<date>.xlsx
```

`actuals.csv` is the frozen canonical facts with immutable lineage; `benchmarks.csv` holds guidance,
consensus and dated price. Schemas are in `interfaces.md`; the project runtime is in `SKILL.md`
("Prepared project and runtime"). Build only from a frozen source boundary.

`scripts/cli.py` builds and checks prepared artifacts and can roll compatible driver values into a
new prepared-project copy. It does not ingest raw sources, calculate, recalculate or render.
Rollover always resets inputs to `proposed` and invalidates approval. Recalculation, rendering and
the native Excel gate are external validation steps (`SKILL.md` step 7).

## Workbook

`model_spec.json` declares the workbook filename and its exact sheet order; the engine creates
exactly those sheets. The legacy renderer requires engine-owned `SourceData` and `Drivers`, with
remaining sheets supplied by the company module. The thin nine-sheet renderer also supports the
agreed order `Outlook`, `Operating Model`, `Bridge Model`, `Financial Statements`, `Valuation`,
`Inputs`, `Consensus`, `SourceData`, `Checks`: it owns `SourceData` and `Inputs`, while the company
module supplies the other seven sheets. This renderer path requires eight forecast quarters and
supports prepared-project build/check; a thin synthetic proof is not a release-ready company model.

In the nine-sheet path, company rows remain keyed by internal metric IDs and fiscal periods.
Optional row metadata may set a readable label, semantic number format, section and display order;
company formulas still use defined names, not positional cross-sheet addresses. Supported semantic
formats are money, percent, percentage-point change, EPS, multiple, price, shares, count and text.
Forecast proposals may be visible on `Inputs`, but unapproved forecast formulas stay blank.
`Consensus` may state that a comparable benchmark is unavailable; it must not invent one.

Every SourceData actual is written once, and historical model sheets link the sourced fact by defined
name. Company rows supply their own causal calculations and independently grounded Checks; the
shared renderer does not provide a generic financial formula engine.

In the legacy renderer, every remaining declared sheet is a company-module sheet (`interfaces.md`
§8), not a fixed tab. A company that needs an investment view, regional model, earnings bridge,
cash and debt, scenarios, sensitivities, consensus comparison or checks block declares a sheet for
it.

The build writes the workbook once and refuses to overwrite an existing delivery. A prior workbook
is immutable; deliver each run to a new dated filename.

### Periods and presentation

- Show actual and forecast quarters with explicit `A`/`E` labels and a clear divider. Canonical
  quarter keys identify the company's fiscal year and fiscal quarter (for example, `2025Q1` is that
  company's Q1, not necessarily calendar Q1); use these keys for comparisons rather than deriving
  periods from calendar dates.
- Forecast eight quarters. Add annual columns only for fiscal years represented by all four quarter
  keys, after the quarterly columns; company modules supply the annual formulas through the same
  keyed period interface. The grid places periods but does not calculate financial results.
- Sum quarterly flows into an annual only when all four fiscal quarters are present; use
  fiscal-year-end stocks for annual balance-sheet values; recompute ratios and per-share values from
  annual components, never by summing quarterly EPS. Keep published annual figures visible as a
  cross-check. Show annual YoY where comparable; do not show annual QoQ.
- For meaningful quarterly levels, company modules place level → YoY → QoQ rows together; an
  optional compounded two-year stack is current level / same fiscal quarter two years earlier − 1.
  Growth requires present, positive current and comparison levels; absent, zero, negative, or
  otherwise unsuitable bases stay blank. Margins and other rates use percentage-point differences
  rather than percentage growth. These financial formulas belong to the company module, not the
  shared period grid or a generic finance engine.
- Keep the style compact: restrained palette, semantic number formats, frozen headings, fitted
  columns, one input colour with a legend. Follow the `excel` skill's financial-model conventions.

### Hardcodes and missing values

- A numerical hardcode is allowed only in a `SourceData` cell or an editable driver cell. Everything
  derived is a visible Excel formula. Project-specific validation must scan numeric constants against
  those designated ranges and report zero unexplained cells.
- Missing is blank, not zero. Guard dependent formulas so a blank is not coerced to zero. Write zero
  only when the evidence reports or proves zero.
- Each historical model cell links its single `SourceData` value by defined name rather than copying
  it. Cross-sheet references use defined names, never positional A1 addresses.

### Forecast and decision integrity

- Proposals never feed formulas; partial approval activates nothing. Activation requires one complete
  approved driver batch whose values hash-match its approval manifest (`interfaces.md` §6).
- Keep GAAP and adjusted profit, tax, share counts and EPS distinct wherever the company reports
  both, and reconcile them only through disclosed or explicitly assumed bridge items.
- Guidance and consensus are comparisons, never forecast inputs.
- Business-event scenarios change coherent groups of drivers; mechanical sensitivities change one
  variable and stay in a separate block.
- Trading multiples state the dated price, earnings period and metric definition; show a
  non-positive-earnings multiple as not meaningful. Use reverse expectations when decision-useful;
  add a DCF only when the approved blueprint calls for it.
- The investment view sheet states the thesis, variant view, catalysts, risks, falsifiers and
  valuation basis. Earnings updates and rollover follow `update-model.md`.

## Checks

`check` is structural; `check --full` adds cached-formula-error and no-positional-cross-sheet scans
when evaluated results are available (`interfaces.md` §8). Both exit non-zero on failure. The shared
core covers declared-sheet and defined-name structure, formula `#REF!` checks, and proposed-driver
isolation; it warns when formula cells lack cached calculation results.

Company accounting identities — segment/consolidated ties, the earnings bridge, EPS, annual
conventions, cash roll-forward, balance-sheet identity, missing-value propagation and hardcode
inventory — are project-additive validation. Run them alongside `check --full`; they are not yet a
shared CLI hook.

Recalculate with zero unsupported formulas and a clean state, then inspect the rendered PNGs — a
passing script is not evidence that an unrendered workbook is readable (`SKILL.md` step 7).

## Web challenge record

A web challenge may test or contradict a supplied value. Record the challenged model value, exact
quote, primary-source URL, publication date, accounting basis and materiality. Tell the user; do not
change the workbook. The number becomes eligible only after the user adds it to the supplied source
pack.
