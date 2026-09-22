# Model rules

Conventions every company project must satisfy. Consult on demand; the workflow itself is in
`SKILL.md`.

## Project contract

One directory per company, `<parent>/<TICKER>/`, self-contained so a later session can rebuild
it with no chat history:

| Path | Holds |
|---|---|
| `model-brief.md` | Scope, fiscal calendar, as-of date, approved forecast approach, approval record (who approved what, when), known limitations. |
| `sources.csv` | One row per designated Data cell: sheet, cell, section, metric_id, period, unit, value_kind, value, source, provider, snapshot id/hash, locator, transform, as-of date, missing reason. |
| `data-map.csv` | One row per populated, formula or designated-blank Data cell: sheet, cell, section, metric_id, label, period, unit, value_kind, source record, transform, downstream cells, missing reason. Generated from workbook/layout state, never maintained by hand. |
| `research.md` | Business explanation, chosen drivers, availability matrix, differences versus guidance and consensus, falsifying evidence. |
| `validation.md` | Output filename and SHA-256, snapshot/run ids, coverage counts, hardcode count, section 7's results, remaining limitations. |
| `build/layout.py` | Structure only: sheet names, period labels, stable metric IDs, ordered row specifications, Outlook field labels, allowed hardcode ranges, `actual_ref` / `benchmark_ref` / `assumption_ref`. No financial values, no source parsing. |
| `build/data.py` | Evidence layer: reads the retained store, returns the model inputs; writes `sources.csv`; self-checks against figures quoted independently in the evidence. |
| `build/build.py` | openpyxl authoring of the workbook, plus `data-map.csv`. |
| `build/forecast_inputs.csv` | Long-form driver × forecast period rows with provenance and approval state. |
| `build/reconcile.py` | Data cells ≡ retained evidence, reparsed independently of `data.py`; provenance set equality; hardcode audit. |
| `build/verify.py` | Workbook ≡ `build/data.py`, plus structure, links, blanks and forecast isolation. |
| `build/check.py` | The one command: `--fast` (manifest, reconcile, verify, hardcode scan) and `--routine` (fast + asp recalculation + controlled tests + renders). |
| `build/panel.py` | Optional statement-panel helper used while deriving calendar/period support facts. |
| `build/assumption_test.py`, `build/rollover_test.py`, `build/compare.py` | Controlled tests and reference-workbook comparison. |
| `<TICKER>_Model_<as-of-date>_V1_actuals_review.xlsx` | Pre-approval deliverable: history + benchmarks + inactive proposals. |
| `<TICKER>_Model_<as-of-date>_V1.xlsx` | Post-approval deliverable. |
| `comparison.md` / `comparison.csv` | Only when a reference workbook is being compared. |

`layout.py` is the only shared module: stable metric IDs and workbook structure live there, and
downstream builders call its helpers instead of repeating literal Data addresses.

The project reads the external store through `FINANCIAL_DATA_PULL_ROOT` (default
`~/Dev/financial_data_pull`) and never through the network. Do not copy a `data/` directory into
the project.

## Period grid

- **12 actual quarters and 8 forecast quarters**, ending at the agreed as-of quarter, derived
  from the company's own fiscal calendar. Non-calendar fiscal years get the fiscal labels.
- On `Operating Model`, `Assumptions`, `Segments` and `Consensus`, the grid runs
  `C..N` (actuals), `O..V` (forecast), `W..Z` (annual). Keep the columns aligned across those
  sheets. `Balance Sheet` and `Cash Flow` keep the same actual columns, with annual columns for
  the completed fiscal years only.
- **Record fiscal week counts where they exist.** A 52/53-week or 4-4-4 calendar changes the
  comparability of a quarter; state the weeks in each period, or state that the filings disclose
  calendar quarters and no week count.
- **Annual columns appear only when all four model quarters are present** — never a partial-year
  total. An annual flow cell stays blank unless its four quarters are populated.
- Annual flow totals sum their four quarters. **Annual balance-sheet values are fiscal-year-end
  balances**, never sums. **Annual EPS is recalculated** as annual net income ÷ annual shares —
  quarterly EPS never sums to it.
- Historical annual share counts use the **published full-year denominator**. Forecast annual
  share counts average the four model quarters unless a published denominator exists; state
  which method was used.
- A published annual figure that differs from the quarter sum by rounding stays visible as a
  benchmark/cross-check on `Data - Benchmarks`; the model's annual cell is the quarter sum and
  the difference is explained.

## Evidence

- Prefer the simplest retained source that carries the figure: the per-cell release dump and the
  statement CSVs over re-parsing HTML.
- **A loader agreeing with itself is not source validation.** `verify.py` (workbook ≡ loader) and
  `reconcile.py` (Data cells ≡ filings) are separate checks for that reason: reconciliation must
  reparse the retained evidence independently and must not import expected values from `data.py`.
- Quarterly cash flow is usually **YTD after Q1**: Q2 = six months − Q1, Q3 = nine months −
  six months, Q4 = full year − nine months. De-accumulate before use. Cash *balances* are stocks
  — never difference them.
- **There is generally no Q4 filing.** Derive Q4 as fiscal year − nine-month YTD, and cross-check
  it against an earnings release where one exists.
- **Comparative columns in later filings are legitimate evidence.** A metric for an early quarter
  may live in a later release's comparative columns (adjusted measures, segment tables, prior-year
  bridge columns). Search the whole retained set, metric by metric, before declaring anything
  unavailable.
- Adjusted, company-defined measures are frequently absent from XBRL: they come from Item 2.02
  release tables. Parse the release cell dump, keep GAAP and adjusted distinct, and never
  synthesise an adjusted bridge the disclosures do not support.
- Filter dimension axes deliberately. Segment tables need the operating-segment axis (plus the
  consolidation axis for profit); external revenue by region needs the segment axis **alone**.
  Exclude restatement, intersegment and product-axis rows.
- Segment labels drift across filings (punctuation, abbreviations). Match on a stable token, not
  the full string.
- Historic periods may carry two different diluted denominators (GAAP vs pro-forma adjusted). Keep
  them on their own rows.
- **Missing is not zero.** A missing critical input propagates as blank through its dependents; a
  guarded formula (`IF(...="","",...)`) keeps Excel from coercing it to zero. A zero is written
  only when the source reports zero or a complete bridge proves it.

## The two data layers

**`Data - Actuals`** — one wide table. Columns `A:I` are metadata (`section`, stable `metric_id`,
presentation label, unit, value type, source family, locator pattern, transformation rule,
snapshot/as-of). `J..U` are the 12 actual quarters. `V`/`W` are the model's FY actual annuals.
`X..AI` are the source-support columns: prior-year comparatives and the 6M/9M/FY YTD facts that
drive visible Q4 and de-accumulation formulas. Row 1 is the title, row 2 the snapshot, row 4 the
metadata headings, row 5 the period headings; data starts at row 7. Freeze panes at `J7` and
filter `A5:AI5`. Metadata and support columns stay visible (support may be grouped).

Sections and ID families: `income.*` (reported), `adjusted.*` and `op_adjustment.*`
(company-defined and the adjustment bridge), `balance.*`, `cashflow.*`, `segment.*`,
`growth_bridge.*`, and `support.*` where a value exists only to drive a visible derivation.

**`Data - Benchmarks`** — the same `A:I` metadata; columns `J..Q` are Q3 2026-equivalent forecast
periods, `R`/`S` the forecast fiscal years, `T` the current/point-in-time column (price, price
date, shares outstanding, published annual cross-checks). Sections: `guidance.*`,
`consensus.*`, `market.*`, `published_annual.*`. A guidance midpoint is a formula on this sheet,
never a second hardcode. Consensus keeps source, as-of date, analyst count and range distinct
from the mean. An item with no retained provider stays blank/pink with a reason.

A directly reported fact is written **once** as a blue numeric hardcode on a Data sheet. Anything
requiring arithmetic — Q4 = FY − 9M, YTD de-accumulation, annual sums, margins, growth rates,
bridge percentages, segment/consolidated reconciliations — is a visible black formula on the Data
sheet whose operands are cells on that sheet. Never compute a derived value in Python and write it
as a hardcode.

Every Data cell carries unit, source, locator, transform and as-of/snapshot metadata beside it,
and a note with its exact source record. The machine-readable register is `sources.csv`; the cell
map is `data-map.csv`. `(sheet, cell)` and `(sheet, metric_id, period)` are unique.

## Downstream sheets

Sheet roles, in tab order: `Outlook`, `Data - Actuals`, `Data - Benchmarks`, `Operating Model`,
`Assumptions`, `Segments`, `Balance Sheet`, `Cash Flow`, `Guidance`, `Consensus`, `Valuation`,
`Checks`, `Sources`.

Every historical value on `Operating Model`, `Segments`, `Balance Sheet` and `Cash Flow` is
either a green direct link to one `Data - Actuals` cell or a black formula over links/formulas.
`Guidance` and `Consensus` link only to `Data - Benchmarks` for benchmark inputs and to model
outputs for comparisons. `Valuation` links to price/shares on `Data - Benchmarks` and to EPS on
`Operating Model`. `Outlook` links to the model, benchmark and valuation outputs.

**Hardcode policy.** A direct numeric cell value is allowed only in sourced/benchmark Data cells
identified by `data-map.csv` and in the `proposed_value`, `approved` and yellow-override rows on
`Assumptions`. Dates and model status used elsewhere link to Data/Assumptions. Labels, text and
formulas are not hardcodes; the scanner examines constant numeric cells, not ordinary formula
literals. There is no sheet-level exception for `Checks`, `Outlook`, headers or charts.

Colour key: blue = numeric hardcode · green = link to another tab · black = formula ·
yellow = optional override · gray = intentionally not modelled · pink = unavailable from the
retained sources. Pink cells are a finding, not a decoration — every one carries a visible reason
and appears in `sources.csv` with a non-empty `missing_reason`.

## Forecast

- One primary operating-profit route. Company-specific revenue drivers where the disclosures
  support them; otherwise an explained consolidated revenue-growth fallback with the reason
  recorded. Segment or regional forecasts only where the company discloses a driver that supports
  them; otherwise leave them blank and say so.
- Keep the GAAP and adjusted tax treatments and diluted share counts on separate rows, and
  reconcile adjusted operating profit to GAAP operating profit through disclosed adjustments.
- Put each measure where its label says it belongs. A row labelled "published" carries only
  company-reported figures; consensus goes on the benchmark tab or in explicitly labelled
  benchmark rows, never inside a published row.
- A bridge may disclose only some of its components. Leave an undisclosed component unavailable
  rather than zero, and confirm that the disclosed components account for the total.
- Guidance and consensus are **benchmarks, not assumptions**. Label each by source, publication
  date, fiscal period and accounting basis. Leave a metric unavailable when no retained provider
  supplies it rather than manufacturing a benchmark. Guidance ranges stay ranges.
- Forecast drivers live in exactly one place: the `Assumptions` sheet's four-row blocks across
  `C..J` — `Proposed (inactive)`, `Approved default`, `YOUR override`, `Active input` — with
  `driver_id`, and one visible `Forecast status` cell reading `NOT APPROVED` or `APPROVED`.
  The active input is
  `=IF(forecast_status<>"APPROVED","",IF(override<>"",override,approved_default))`.
  `proposed_value` never feeds a forecast. `forecast_inputs.csv` is long-form: one row per
  required `(driver_id, period)` pair with `status` (`proposed` / `approved` / `rejected`) and
  blank approval metadata until approval. The forecast is globally approved only when every
  required row is approved with a numeric value and non-blank batch metadata; partial approval
  activates nothing.
- Every forecast formula first checks its required active inputs and returns blank while any is
  unavailable. The `YOUR override` row's period header carries period labels and nothing else:
  the override helper rejects any other label there rather than risk reading a period from the
  wrong column.

## Valuation

- Trading multiples use a **verified dated price**. State the date and how it was established
  from the price file (a bar-position inference is specific to one export's metadata — do not
  generalise it; prefer an export that carries dates).
- **Label every multiple with its earnings period and its metric definition**.
- Show a non-positive-earnings multiple as not meaningful. V1 includes **current-price lenses
  only**: no target price, no assumed fair multiple, no implied upside, no sensitivity table, no
  DCF.

## Outlook

Replace a KPI `Summary` with `Outlook`. Sections: header (company/ticker, model date,
price/date, coverage, forecast status), investment view, earnings snapshot, house versus
guidance/consensus, key drivers, current-price valuation, and at most two charts. The
investment-view labels — `Thesis`, `Key debate`, `Catalysts`, `Risks`, `Falsifying evidence` —
are the only workbook cells whose *content* survives an update; each must occur exactly once, and
blank text is a valid value. Keep the reading guide, the colour key and the provenance caveats on
`Sources`.

## Validation

1. `reconcile.py` — reparse retained evidence independently and compare with every sourced Data
   cell; recompute every derived Data cell from the independent parse; require set equality
   between Data cells and provenance records; count unexplained numeric hardcodes and require
   zero.
2. `verify.py` — compare the workbook against `build/data.py` values and assert structure, links,
   deliberate blanks, forecast isolation and benchmark isolation.
3. `check.py --fast` — source manifest/frozen-snapshot hash, reconciliation, verification and the
   hardcode scan. `check.py --routine` adds prompt-free `asp workbook recalculate` (require
   `0 unsupported` and `state: clean`), the evaluated-formula and controlled-dependency tests, and
   ASP renders. The native Microsoft Excel gate is a separate final milestone (Phase F after
   forecast approval), not part of routine work.
4. Financial and structural checks — statement identities, segment sums, annual totals, earnings
   bridges, balance-sheet balance, cash roll-forward, GAAP/adjusted denominator separation.
   Derive every total at runtime; never hardcode an expected check count.
5. A controlled assumption change — move one approved revenue-growth driver and confirm the
   effect reaches profit, tax, EPS and the multiples after a real recalculation, while actuals,
   guidance and consensus stay put.
6. Quarter-rollover exercise on a copy: extract numeric overrides and the five Outlook text
   fields, rebuild with a rolled grid, restore by identity, and compare payloads. Simulated data
   is labelled test-only and never delivered as actuals.

## Escalation

Stop and ask when: an input needed for the forecast is unavailable from retained evidence;
a live pull would be needed and is not yet approved; an assumption has no retained basis; or a
metric's definition differs between sources in a way that changes the answer. A visible,
disclosed limitation is an acceptable outcome; an invented number is not.
