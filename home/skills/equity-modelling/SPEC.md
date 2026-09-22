# Equity Modelling V1 Specification

## Status

Agreed design; implementation has not started. The skill remains manually invoked until a real-company pilot passes.

## Purpose

Build or update a trustworthy, editable public-equity earnings model that emphasizes forecast edge: company-specific operating drivers, quarterly earnings, consensus variance, scenarios, cash conversion, valuation, and a one-page investment view.

The skill is not a universal planning model, mandatory three-statement model, DCF engine, or report-writing system.

## Product principles

1. **Model the business, not a template.** Discover the company's segments and economic drivers during the run.
2. **Forecast edge first.** The model should explain why its estimates differ from guidance or consensus.
3. **Excel remains legible.** Forecast outputs are visible formulas driven by editable inputs.
4. **Python supplies reproducibility.** Python handles evidence, workbook construction, updates, and independent checks.
5. **Web research challenges; it does not supply.** A web-found number cannot enter the model until the user supplies it.
6. **Machine checks can be exhaustive; the human workflow stays short.**
7. **Gaps stay visible.** Missing evidence is never silently converted to zero or false precision.

## Invocation branches

### New model

Inspect the user-supplied source pack, conduct a company-specific interview, agree the model blueprint, propose the forecast assumptions, build the workbook after approval, and validate it.

### Earnings update

Inspect the existing model and new source pack, preserve designated overrides and Outlook commentary, load reported actuals and guidance, roll the forecast horizon forward, show estimate changes, and write a new immutable dated workbook.

A standalone model audit remains outside this skill unless later usage proves it belongs here.

## Agreed defaults

| Decision | Default |
|---|---|
| Historical input | Flexible user-supplied source pack |
| Interview starting point | Business economics |
| Primary drivers | Five to ten |
| Revenue method | Units × price/mix when operational evidence supports it; otherwise explicit segment growth |
| Margin method | Driver bridge: volume, price/mix, mix, productivity, inflation, FX, and other material effects |
| Special effects | Organic growth, acquisitions/disposals, and FX shown separately when supported |
| Missing driver | Visible analyst assumption with rationale, uncertainty, and scenario sensitivity |
| Forecast horizon | Eight quarters with derived annual periods |
| Statement depth | Full earnings model plus thesis-relevant cash flow and balance-sheet items |
| Full three statements | Optional when liquidity, leverage, working capital, or balance-sheet risk matters |
| Consensus | Benchmark only, never a forecast input |
| Scenarios | Coherent business-event cases plus mechanical sensitivities |
| Valuation | Relevant trading multiples plus reverse-expectations analysis; DCF only when useful |
| Companion output | One-page investment view |
| Assumption approval | One concise package |
| Human gates | Blueprint approval, then forecast-assumption approval |
| Versioning | Immutable dated files |
| Restatements | Latest reported basis with a change log; prior model versions preserved |
| Migration | Keep `company-model` through the pilot |

## Workflow

### 1. Inventory the source pack

Identify the company, fiscal calendar, as-of date, files supplied, periods covered, units, accounting basis, segment disclosures, guidance, consensus, price evidence, and missing items. Do not fetch replacement model data from the web.

**Done when:** the usable evidence, gaps, conflicts, and model-input boundary are explicit.

### 2. Conduct the company interview

Ask brief questions in groups of no more than four. Establish:

- how the company makes money;
- its reporting and economic segments;
- volume, price, mix, capacity, utilization, backlog, or other operating drivers;
- cost and margin structure;
- cash-conversion and capital-intensity drivers;
- thesis, variant perception, risks, and likely falsifiers;
- decision-relevant valuation metrics.

Do not embed sector-specific drivers in the reusable skill.

**Done when:** five to ten primary drivers and the appropriate financial depth are identified.

### 3. Propose the model blueprint — Gate 1

Show the proposed sheets, segments, driver equations, profit bridge, cash and balance-sheet scope, comparison metrics, scenario design, valuation method, and known evidence gaps. Wait for approval before constructing the full model.

**Done when:** the user approves one concise blueprint.

### 4. Build the historical and evidence layer

Enter each historical source value once. Downstream sheets link to that canonical cell or calculate from it. Record source, period, units, basis, and locator. Use the latest company-reported basis and record historical changes.

**Done when:** displayed actuals reconcile to the supplied source pack and every gap is labelled.

### 5. Propose forecast assumptions — Gate 2

Present one compact package covering the five to ten drivers across eight quarters: values, progression, rationale, evidence or analyst basis, uncertainty, guidance comparison, consensus comparison, and scenario treatment. Wait for batch approval.

**Done when:** the user approves or edits the package; approval does not alter guidance or consensus.

### 6. Build the forecast and scenarios

Create company-specific segment, earnings, cash, selected balance-sheet, scenario, and valuation formulas. Business-event scenarios must change coherent groups of assumptions; mechanical sensitivities remain a separate layer.

**Done when:** every forecast output traces to an approved driver or visible formula.

### 7. Validate and deliver

Run independent source reconciliation, hardcode scanning, formula-error scanning, core identity checks, behavioural tests, recalculation, and focused visual review. Deliver an immutable dated workbook and the one-page investment view.

**Done when:** no unexplained constants or new formula errors remain, key identities hold, behavioural tests pass, and critical rendered sheets are readable.

## Workbook contract

### Decision layer

1. `Outlook` — thesis, variant estimates, scenario outcomes, valuation, risks, and proof points.
2. `Drivers` — editable company-specific assumptions and explanations.
3. `Scenarios` — Base/Bull/Bear or named business events plus mechanical sensitivities.
4. `Valuation` — multiples, reverse expectations, implied value, and price/date basis.

### Model layer

5. `Segments` — operational and financial segment forecasts.
6. `Operating Model` — quarterly and annual P&L, GAAP/adjusted separation where relevant.
7. `Cash & Capital` — CFO, capex, FCF, debt/cash, shares, and capital returns as relevant.
8. `Balance Sheet` — only decision-relevant items by default; expand when required.

### Evidence layer

9. `Data - Actuals`
10. `Guidance & Consensus`
11. `Sources & Checks`

The blueprint may combine or omit sheets when the company does not require them. Sheet names are a default, not a fixed 11-tab law.

## Presentation contract

- Use a compact institutional style.
- Show actual and estimate periods with a clear divider and explicit `A`/`E` labels.
- Keep quarterly and derived annual columns on the same model sheets.
- Put a YoY row beneath each material quarterly level.
- Add two-year stacks only when distorted bases, timing, acquisitions, or volatility make them informative.
- Use QoQ only for businesses where sequential movement is economically meaningful.
- Prefer compact blocks: level → YoY → relevant unit or margin.
- Keep editable inputs beside the driver rows they control; link them into one approval summary.
- Use one obvious input colour and a visible legend.
- Keep verbatim management guidance separate from analyst assumptions.
- Use contribution bridges for material earnings changes.
- Routine renders cover `Outlook`, `Drivers`, `Scenarios`, `Valuation`, and `Sources & Checks`; full-workbook rendering is a release option.

## Minimal project machinery

A generated company project should initially need no more than:

```text
<TICKER>/
├── model_spec.json
├── sources.csv
├── forecast_inputs.csv
├── build.py
├── check.py
└── <TICKER>_Model_<YYYY-MM-DD>.xlsx
```

- `model_spec.json` records the approved interview outcome: periods, segments, selected drivers, relevant statement lines, scenarios, and valuation metrics.
- `forecast_inputs.csv` stores five to ten driver rows with eight forecast-quarter columns rather than one approval row per driver-period pair.
- `sources.csv` holds the historical provenance register and change log fields.
- `build.py` writes the formula-driven workbook.
- `check.py` independently reparses supplied evidence and validates the workbook.

Use Python's standard library for JSON, CSV, hashing, and file operations; `openpyxl` for workbook construction; and the Excel skill's ASP recalculation for validation, with asp-rendered PNGs for visual review. The native Microsoft Excel gate is optional in the standard run — reserve it for non-vanilla formulas (dynamic arrays, LAMBDA, newer functions) or explicit user request. Reuse small proven helpers from `company-model` where they fit. Do not create a formula DSL, database, generic model engine, or duplicated calculation graph.

## Trust contract

### Source integrity

- Every historical value is entered once.
- Every canonical value records source, locator, period, units, and accounting basis.
- Missing values remain blank and explained.
- Restated history uses the latest reported basis and records the old value and reason.

### Formula integrity

- Numerical hardcodes are allowed only in designated source and forecast-input cells.
- Forecast outputs remain Excel formulas.
- Annual periods derive from quarters.
- Segment totals reconcile to consolidated totals when comparable.
- Earnings bridges, EPS, cash roll-forwards, and balance sheets reconcile where modelled.

### Independent validation

`check.py` must not merely read values produced by `build.py`. It independently reparses the supplied evidence and compares the workbook's canonical actuals and selected outputs.

### Behavioural validation

At least one controlled test changes a single driver and verifies that expected revenue, earnings, cash, and valuation outputs move while unrelated outputs remain unchanged.

### Decision integrity

- Guidance and consensus remain benchmarks.
- Analyst assumptions are visibly labelled.
- Scenarios distinguish business events from mechanical sensitivities.
- Current-price evidence carries an as-of date.
- Prior approved forecasts remain available for forecast-versus-actual review.

## Web challenge policy

1. Search only to test, contextualize, or contradict supplied information.
2. Prefer filings and company IR; use secondary reporting only to locate primary evidence or provide context.
3. Fetch and inspect the underlying source rather than relying on a search snippet.
4. Record the conflicting model value, exact quote, URL, date, basis, and materiality.
5. Alert the user; do not alter the workbook.
6. A web-found number becomes eligible model evidence only after the user supplies it into the source pack.

The implemented skill should include a small known-true, known-false, and ambiguous web-search smoke test.

## Explicit V1 exclusions

- Mandatory integrated three-statement modelling.
- Mandatory DCF.
- Sector-template or driver libraries.
- Automatic web-data ingestion.
- HTML dashboards or report systems.
- Generic formula or modelling DSLs.
- Databases or background services.
- Fixed exhaustive tab and line-item counts.
- Per-quarter approval records.
- Large visible control packs, manifests, or status taxonomies.

## Pilot acceptance examples

1. **Operationally disclosed company:** the interview selects unit and price/mix drivers, the segment forecasts drive consolidated earnings, YoY and annual views reconcile, and consensus remains a comparison rather than an input.
2. **Sparse disclosure company:** unavailable operational history stays visible, reasoned assumptions are clearly labelled and scenario-sensitive, and the model does not invent sourced facts.
3. **Earnings update:** a newly reported quarter replaces the forecast on the latest reported basis, designated overrides and Outlook text survive, estimate changes are explained, and a new dated workbook is produced without altering the prior version.

## Pilot exit criteria

Enable model invocation and consider retiring or redirecting `company-model` only after one real-company pilot satisfies all three applicable acceptance patterns, the user approves the workbook's usefulness, and validation demonstrates that no web-only or unexplained numbers entered the model.
