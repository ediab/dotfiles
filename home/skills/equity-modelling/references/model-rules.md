# Model rules

Reusable contract for an `equity-modelling` company project. The workflow and approval gates live
in `SKILL.md`; company-specific drivers and formulas live in the generated project.

## Minimal project

```text
<TICKER>/
├── model_spec.json
├── sources.csv
├── forecast_inputs.csv
├── build.py
├── check.py
└── <TICKER>_Model_<YYYY-MM-DD>.xlsx
```

Add a file only when the pilot needs it. Keep the project rebuildable without chat history.

`model_spec.json` records the approved blueprint: company and ticker, as-of date, fiscal calendar,
actual and forecast periods, segments, five to ten driver ids, selected statement lines, scenario
events, sensitivities, valuation metrics, sheet list, approval record, and known gaps.

`sources.csv` is the source register and change log. Use one row per canonical model input with at
least: `record_id`, `metric_id`, `period`, `value`, `unit`, `basis`, `source_file`, `source_sha256`,
`locator`, `transform`, `as_of_date`, `prior_value`, `change_reason`, and `missing_reason`.
`(metric_id, period)` is unique. A missing input has a reason, not a zero.

`forecast_inputs.csv` uses one row per driver, not one row per driver-quarter. Its stable metadata
columns are: `driver_id`, `driver_name`, `unit`, `basis`, `rationale`, `uncertainty`,
`guidance_comparison`, `consensus_comparison`, `scenario_treatment`, `status`, `approved_by`,
`approved_on`, and `approval_id`; the remaining eight columns are the approved forecast-quarter
labels from `model_spec.json`. `status=proposed` never activates a forecast. Activate only when all
required rows are approved with numeric values and complete batch metadata.

`build.py` reparses the supplied source files, writes the workbook formulas, and never uses the web.
`check.py` independently reparses the supplied files and validates the workbook. The two scripts
may share small structural constants, but not parsed source values or expected financial outputs.

## Workbook

Default sheets, combined or omitted only when the approved blueprint warrants it:

1. `Outlook`
2. `Drivers`
3. `Scenarios`
4. `Valuation`
5. `Segments`
6. `Operating Model`
7. `Cash & Capital`
8. `Balance Sheet`
9. `Data - Actuals`
10. `Guidance & Consensus`
11. `Sources & Checks`

### Periods and presentation

- Show actual and estimate quarters with explicit `A`/`E` labels and a clear divider.
- Forecast eight quarters. Put derived annual periods on the same model sheets.
- Show a YoY row beneath each material quarterly level. Add a two-year stack only when a distorted
  base, timing, acquisition, or volatility makes it informative. Use QoQ only where sequential
  movement is economically meaningful.
- Sum annual flow values only when all four fiscal quarters are present. Use fiscal-year-end stocks
  for annual balance-sheet values. Recalculate annual EPS from annual net income and the stated
  annual share-count convention; never sum quarterly EPS.
- Use the company's fiscal calendar, including 52/53-week effects where disclosed.
- Keep the style compact: restrained palette, semantic number formats, frozen headings, fitted
  columns, and one obvious input colour with a legend. Follow the `excel` skill's financial-model
  colour conventions.

### Evidence and hardcodes

- Write each supplied historical value once on `Data - Actuals`; all other actuals link to that
  cell or calculate from canonical cells.
- Write guidance, consensus, and dated price evidence once on `Guidance & Consensus`; keep source,
  as-of date, period, units, range, analyst count, and accounting basis distinct where available.
- Numerical hardcodes are allowed only in designated source cells and editable forecast-input
  cells. Everything derived is an Excel formula. A hardcode scan must compare numeric constants
  with the designated ranges and report zero unexplained cells.
- Store exact source provenance in `sources.csv` and expose source, locator, period, unit, basis,
  and missing reason on `Sources & Checks` or in cell notes.
- Use the latest company-reported historical basis. Preserve old values and the reason for a
  restatement in `sources.csv`; preserve prior workbook versions unchanged.
- Missing is blank, not zero. Guard dependent formulas so Excel does not coerce missing values to
  zero. Write zero only when the supplied evidence reports or proves zero.

### Forecast and decision integrity

- Keep analyst assumptions visibly labelled and editable on `Drivers`. Each active driver uses an
  approved default unless a clearly designated local override is present.
- Proposals never feed formulas. Partial approval activates nothing.
- Keep GAAP and adjusted profit, tax, share counts, and EPS distinct wherever the company reports
  both. Reconcile them only through disclosed or explicitly assumed bridge items.
- Guidance and consensus are comparisons, never forecast inputs.
- Business-event scenarios change coherent groups of drivers. Mechanical sensitivities change one
  variable and remain separate.
- Trading multiples state the dated price, earnings period, and metric definition. Show a
  non-positive-earnings multiple as not meaningful. Use reverse expectations when decision-useful;
  add a DCF only when the approved blueprint calls for it.
- `Outlook` contains the investment view, earnings snapshot, house versus guidance/consensus,
  scenario outcomes, valuation, key drivers, catalysts, risks, and falsifying evidence. Preserve
  designated user-authored Outlook text during updates.

## Checks

`check.py` exits non-zero on failure and covers:

1. supplied-file hashes and immutable-input checks;
2. independent source reparse versus every canonical actual, benchmark, and dated price;
3. complete provenance and unique `(metric_id, period)` identities;
4. zero unexplained numeric hardcodes;
5. formula presence, formula-error scan after recalculation, and missing-value propagation;
6. segment/consolidated ties, earnings bridge, EPS, annual conventions, cash roll-forward, and
   balance-sheet identity where modelled;
7. guidance/consensus isolation from forecast formulas;
8. one controlled driver change on a copy: expected revenue, earnings, cash, and valuation outputs
   move; actuals, guidance, consensus, and unrelated outputs stay fixed.

Use `asp workbook recalculate` and require `0 unsupported` and `state: clean`. Skip the Excel
skill's native gate in the standard run; use it only for non-vanilla formulas or on request. Then
inspect the asp-rendered PNGs — a passing script is not evidence that an unrendered workbook is
readable.

## Web challenge record

A web challenge may test or contradict a supplied value. Record the challenged model value, exact
quote, primary-source URL, publication date, accounting basis, and materiality. Tell the user; do
not change the workbook. The number becomes eligible only after the user adds it to the supplied
source pack.
