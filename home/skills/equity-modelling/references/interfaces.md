# Interfaces

Schemas, entry points, the structured locator grammar and the transform registry for the v2
evidence layer (V2_PLAN.md §8). Written before any Stage 2 code, against VRT as the worked
example. A contract lives in exactly one file — this one owns schemas and entry points;
`evidence-rules.md` owns the conventions as rules; `model-rules.md` owns the workbook contract.

`scripts/evidence.py` owns the evidence layer. `engine.py`, `checks.py`, `cli.py`, `style.py` and
`overrides.py` are shipped, and `scripts/cli.py` is the build/check runtime for a prepared project
(SKILL.md "Prepared project and runtime"). This file documents only shipped public entry points.

---

## 1. `model_spec.json`

Unchanged in shape from the VRT pilot (`~/Desktop/equity-models/VRT_v1_baseline/model_spec.json`).
Stage 2 adds no new top-level keys; `fact_map.json` is a sibling file, not a subtree of this one.

```json
{
  "schema_version": 1,
  "company": "Vertiv Holdings Co",
  "ticker": "VRT",
  "currency": "USD",
  "display_units": "USD millions except per-share data and percentages",
  "model_date": "2026-09-21",
  "latest_actual_period": "2026Q2",
  "price": { "value": 249.39, "date": "2026-09-18", "type": "official close", "source": "…" },
  "source_boundary": {
    "root": "/Users/eliasdiab/Dev/financial_data_pull/data",
    "policy": "Only the frozen local VRT pack may populate the model. Web research is challenge-only.",
    "latest_sec_snapshot": "2026-09-21T170653+0000-3ce4e7",
    "latest_yahoo_snapshot": "2026-09-21T145121+0000-9e427b",
    "latest_av_estimate_snapshot": "2026-09-21T151923+0000-repair",
    "latest_transcript_snapshot": "2026-09-21T150106+0000-b57670"
  },
  "periods": {
    "historical_quarters": ["…"],
    "forecast_quarters": ["…"],
    "fiscal_calendar": "Calendar year ending December 31",
    "period_end_dates": { "2026Q3": "2026-08-02" }
  },
  "approved_blueprint": { "approved": true, "primary_drivers": ["…"], "…": "…" },
  "forecast_gate": { "approved": false, "note": "forecast inputs remain proposed" },
  "release_accessions": { "2026Q2": "0001628280-26-050323" },
  "workbook": { "filename": "VRT_2026-09-21_v1.xlsx", "sheets": ["…"] },
  "known_data_gaps": ["…"]
}
```

`source_boundary` is the immutable four-snapshot manifest (§6). Every locator resolved by
`evidence.py` must be reachable from one of these four snapshot ids; a locator pointing outside the
manifest is a build error, not a warning.

`periods.period_end_dates` optionally maps canonical `YYYYQn` ids to their ISO period-end dates for
a non-calendar (e.g. 52/53-week) fiscal year. When present it is authoritative for every
date-sensitive lookup — SEC column/date selection, Q4 annual selection, `sec_label` count/date
pairing, and `8k_exhibit`/`8k_exhibit_role` period scopes — so a requested period absent from the
mapping is an error, never a silent calendar guess. Specs without the key keep the calendar-quarter
fallback (Mar/Jun/Sep/Dec), preserving existing calendar-year projects.

---

## 2. `fact_map.json` — the company-specific mapping

One entry per canonical metric. `evidence.py` is generic; this file is where company knowledge
lives (§6 "facts are mapped, not inferred").

```json
{
  "schema_version": 1,
  "ticker": "VRT",
  "facts": [
    {
      "metric": "revenue",
      "dimension": null,
      "basis": "GAAP",
      "units": "USDm",
      "locator": "sec_snapshot:income#concept=Revenues",
      "period_kind": "fiscal_quarter",
      "transform": "direct",
      "missing_treatment": "unavailable"
    },
    {
      "metric": "regional_revenue_emea",
      "dimension": "vrt_EMEASegmentMember",
      "basis": "GAAP",
      "units": "USDm",
      "locator": "sec_snapshot:income#concept=Revenues&dimension_member=vrt_EMEASegmentMember",
      "period_kind": "fiscal_quarter",
      "transform": "segment_axis_filter",
      "missing_treatment": "unavailable"
    },
    {
      "metric": "adjusted_diluted_eps",
      "dimension": null,
      "basis": "adjusted",
      "units": "USD/share",
      "locator": "8k_exhibit:row_label=Adjusted diluted EPS|col_pattern={month} {day}, {year}",
      "period_kind": "fiscal_quarter",
      "transform": "direct",
      "missing_treatment": "unavailable"
    },
    {
      "metric": "gross_profit",
      "dimension": null,
      "basis": "GAAP",
      "units": "USDm",
      "locator": "derived:revenue-cost_of_sales",
      "period_kind": "fiscal_quarter",
      "transform": "direct",
      "missing_treatment": "unavailable"
    },
  ]
}
```

Field notes:

- `locator` uses the grammar in §3 below. The reader selects the SEC snapshot and release accession from `model_spec.json`; the map never hardcodes a quarter-specific table, row, or column. A raw-payload locator carries its immutable payload hash and may use `{date}` in its index selector.
- `transform` must be a registry id (§7). No inline lambdas. `sec_label` is intentionally a closed locator mode, not arbitrary label regex: it only recognizes the XBRL 'shares authorized, [counts] shares issued and outstanding at [dates], respectively' construction.
- `8k_exhibit_role` is a narrowly reviewed exception for duplicate regional-table labels. Its `period_hashes` object supplies the literal `period_hash` for each allowed period. It may not use table/row/column coordinates as a selector; those are recorded only as resolved lineage and it fails on more than one semantic candidate.
- `dimension` is the XBRL `dimension_member` token (never a display label — VRT's EMEA label
  changes punctuation between filings; the member id `vrt_EMEASegmentMember` does not — resolved
  fact from Stage 2 store investigation, 2026-09-22).
- `missing_treatment` is `unavailable` (write nothing, mark the availability matrix) or `required`
  (build fails if unresolved). Dated price belongs in `benchmarks.csv`, not this SEC-focused map.
- `missing_reason` is required for an entry whose `locator` is `unavailable` — an intentional,
  documented gap. Such an entry never reads the store, so a period the frozen pack cannot map is
  declared rather than guessed. On any other entry `missing_reason` is a fallback note for an
  unresolved (non-error) result. `scripts/cli.py` fails a build whose blank actual has no specific
  reason.
- A metric needing more than one locator across periods (e.g. a metric that moves XBRL concept
  after a restatement) gets multiple fact entries with disjoint `period` predicates, not a
  conditional inside one locator string.

---

## 3. Structured locator grammar

```
locator  := scheme ":" path ["#" fragment]
scheme   := "sec_snapshot" | "sec_label" | "8k_exhibit" | "8k_exhibit_role" | "raw_payload" | "derived" | "unavailable"
```

| Scheme | Path | Fragment | Resolves to | Lineage terminus |
|---|---|---|---|---|
| `sec_snapshot` | `<statement>` | `concept=<XBRL concept>[&dimension_member=<member>]` | the matching quarter or annual cell in the configured immutable SEC snapshot | the resolved parquet file — `data/tables/` is never rewritten |
| `sec_label` | `<statement>` | `concept=<XBRL concept>&mode=issued_and_outstanding_shares` | the share count paired to the requested period-end date in the standard label's explicit `respectively` list | the resolved SEC parquet row; labels without an exact count/date pairing are unavailable |
| `8k_exhibit_role` | — | `caption=<exact>|row_labels=<exact,...>|column_role=<exact>|period_scope=<template>|exhibit_sha256={period_hash}` | one reviewed cell identified by its release table caption, semantic current-period column role, permitted exact row role, and immutable hash | exhibit payload, row/table/column keys; a missing, mismatched, or non-unique candidate is unavailable |
| `8k_exhibit` | `row_label=<regex>\|col_pattern=<template>` | — | the matching data cell in `data/derived/<issuer>/8k_cells.csv`, limited to `model_spec.json.release_accessions[period]` | that row's own `exhibit_sha256` column — **not** a hash of `8k_cells.csv`, which is a rewritable view. `evidence.py` records `exhibit_sha256` in `actuals.csv`'s lineage column, resolved at read time |
| `raw_payload` | `<provider>/<sha256>/payload.<ext>` | `index=<key>[&field=<name>]` for indexed JSON (e.g. Yahoo's `{columns,index,data}` frame) | one value inside `data/raw/<issuer>/<provider>/<sha256>/` | the raw payload file — already the immutable terminus |
| `derived` | an arithmetic expression over other canonical metric ids, same period | — | a Python evaluation of already-resolved `(metric, period)` values | inherits the lineage of every metric it references; `evidence.py` must have resolved all operands first |
| `unavailable` | — (the bare token `unavailable`) | — | nothing — the period is an intentional, documented gap; requires a non-empty `missing_reason` (§2) | none: the frozen row carries no lineage, only its `missing_reason` |

`sec_snapshot` gets its `run_id` from `model_spec.json.source_boundary`, while `8k_exhibit` gets
its release accession from `model_spec.json.release_accessions`. Neither is hardcoded per mapped
fact, so rollover changes the source boundary without rewriting the map.

Every date the grammar depends on (SEC period columns, Q4 annual labels, `sec_label` date pairing,
`8k_exhibit`/`8k_exhibit_role` period scopes) comes from `model_spec.json.periods.period_end_dates`
when declared, else from the calendar-quarter fallback (§1). No locator hardcodes a period-end date.

**Why `8k_exhibit` uses semantic selectors:** release tables move between filings. `row_label` and
`col_pattern` identify the reported fact without encoding a period-specific table, row, or column;
the immutable lineage still terminates at the matching row's `exhibit_sha256`.

---

## 4. `evidence.py` — public entry points (Stage 2)

```python
def load_fact_map(path: Path) -> list[FactMapping]: ...

def resolve(mapping: FactMapping, period: str, spec: dict) -> ResolvedFact:
    """Resolve one (metric, period) via its locator against the snapshot manifest in `spec`.
    Returns value, units, lineage (scheme + immutable path + concept/row keys), and
    provenance_status. Raises on a locator outside the four-snapshot manifest."""

def build_actuals(fact_map: list[FactMapping], spec: dict, periods: list[str]) -> list[ResolvedFact]:
    """Iterate every (metric, period) the fact map declares over `periods`; apply the metric's
    transform; return rows ready to freeze as actuals.csv. A `derived` transform is evaluated only
    after its operand metrics are resolved for the same period. A required unresolved fact fails the build."""

def build_availability(actuals: list[ResolvedFact], metrics: list[str], periods: list[str]) -> str:
    """metric x period -> ✓ (resolved in actuals) | unavailable (never a silent zero). `metrics` is
    the flat list of canonical metric ids to show as rows — usually `sorted({m.metric for m in
    fact_map})`, not the fact_map itself, since one metric may have several fact_map entries
    (§2's disjoint period predicates). Returns the rendered Markdown table."""

def freeze(actuals: list[ResolvedFact], out_dir: Path) -> None:
    """Write evidence/actuals.csv. benchmarks.csv is a separate call (guidance/consensus/price are
    not facts from fact_map's SEC path); availability.md is written separately too, from
    build_availability()'s return value — freeze() itself only writes actuals.csv."""
```

`evidence.py` ships no per-ticker knowledge — every company noun above comes from the `fact_map`
and `spec` arguments (§5 non-goals: "no engine that owns company formulas").

---

## 5. `actuals.csv` — canonical frozen facts

```
metric,period,value,units,basis,dimension,transform,locator,lineage_scheme,lineage_path,lineage_key,provenance_status,notes
revenue,2026Q2,2144.4,USDm,GAAP,,direct,sec_snapshot:2026-09-21T170653+0000-3ce4e7/income_quarterly_0.parquet#concept=Revenues&period=2026-06-30 (Q2),sec_snapshot,data/tables/VRT/2026-09-21T170653+0000-3ce4e7/income_quarterly_0.parquet,concept=Revenues,verified,
regional_revenue_emea,2026Q2,412.1,USDm,GAAP,vrt_EMEASegmentMember,segment_axis_filter,sec_snapshot:...,sec_snapshot,data/tables/VRT/.../income_quarterly_0.parquet,concept=Revenues;dimension_member=vrt_EMEASegmentMember,verified,
adjusted_diluted_eps,2023Q3,0.52,USD/share,adjusted,,direct,8k_exhibit:row_label=Adjusted diluted EPS|col_pattern=September 30, 2023,8k_exhibit,data/raw/VRT/sec/<exhibit_sha256>/payload.htm,exhibit_sha256=<hash>,verified,
```

`(metric, period[, dimension])` is unique. `lineage_scheme`/`lineage_path`/`lineage_key` together
are what §15's exit criterion means by "lineage to a snapshot or raw payload" — never a `data/csv/`
or `data/derived/` view path alone (the `8k_exhibit` row above stores the exhibit's own hash as
`lineage_key`, satisfying this even though the locator's *addressing* convenience is a derived CSV).

Before a build, `scripts/cli.py` validates the freeze against the map: every
`(metric, historical period)` a fact-map entry covers needs an actuals row (`periods` limits the
coverage, an absent predicate covers every historical quarter), rows are unique per
`(metric, period, dimension)`, and every blank value needs a specific, non-empty `notes` reason — a
bare `unresolved`/`unavailable` status token is not sufficient. A covered period with no row, a
duplicate row, or a blank without a reason fails the build.

## `benchmarks.csv` — guidance, consensus, dated price

```
metric,period,value,units,basis,source,as_of_date,analyst_count,range_low,range_high,locator,lineage_scheme,lineage_path,lineage_key,notes
price_dated,2026-09-18,249.39,USD/share,market,Yahoo,2026-09-18,,,,raw_payload:yahoo/<sha256>/payload.json#index=2026-09-18T04:00:00.000Z&field=Close,raw_payload,data/raw/VRT/yahoo/<sha256>/payload.json,index=2026-09-18T04:00:00.000Z;field=Close,Resolves the store's date-less yahoo_prices.csv defect by reading the raw indexed payload directly (§6)
```

## `availability.md`

One table: rows = the 44 canonical metrics (VRT baseline count), columns = the 12 historical
quarters, cell = `✓` (resolved in `actuals.csv`) or blank with a one-line reason (`unavailable:
no segment disclosure before 2023Q4`, etc.). Never a zero standing in for a blank cell.

---

## 6. `drivers.csv` — replaces v1's `forecast_inputs.csv` shape

One row **per driver**, not per driver-quarter (§18 explicitly excludes importing v1's
per-driver-quarter approval rows). Stable metadata columns, then one column per approved
forecast-quarter label from `model_spec.json.periods.forecast_quarters`:

```
driver_id,driver_name,unit,basis,rationale,uncertainty,guidance_comparison,consensus_comparison,scenario_treatment,status,approved_by,approved_on,approval_id,2026Q3,2026Q4,2027Q1,2027Q2,2027Q3,2027Q4,2028Q1,2028Q2
regional_organic_growth_americas,Americas organic revenue growth,%,GAAP,"Calibrates FY2026 to disclosed midpoint...",medium,"Guidance implies high-30s to mid-40s H2","Consensus ~41% H2",linked to upside/downside scenario deltas,approved,elias@diab.io,2026-09-22,APR-2026-09-22-01,43,44,…
```

**Approval manifest** (separate small JSON alongside `drivers.csv`, e.g. `drivers.approval.json`):
one entry per `approval_id` recording a hash of the exact `(driver_id, period, value)` triples it
covers. Any new or changed quarter — including one added by rollover — produces triples absent from
every existing hash, which invalidates approval for that row until Gate 2 runs again (§9). `engine.py`
refuses to activate a `status=proposed` row or a row whose current values don't hash-match its
`approval_id`.

---

## 7. Transform registry (closed set — from §8, unchanged)

| id | Meaning |
|---|---|
| `direct` | Reported value, used as filed |
| `unit_scale` | Multiply by a declared power of ten |
| `sign_flip` | Reverse the filed sign convention |
| `ytd_deaccumulate` | Period value = YTD − prior YTD within the same fiscal year |
| `q4_from_fy_minus_9m` | Q4 = FY − first nine months; no Q4 filing exists |
| `sum_quarters` | Annual flow, only when all four fiscal quarters are present |
| `period_end_stock` | Annual balance = fiscal-year-end stock |
| `recompute_ratio` | Ratio recomputed from annual numerator ÷ denominator |
| `recompute_per_share` | Per-share recomputed from annual NI ÷ stated share convention |
| `segment_axis_filter` | Select one dimension member from a segmented table, by `dimension_member` token |

Every transform must be expressible as a visible Excel formula in the workbook (§6, §8). Arithmetic
combinations of already-canonical metrics (v1's `derived:revenue-cost_of_sales` pattern) use
`transform: "direct"` with a `derived:` locator — the arithmetic itself becomes the Excel formula
linking two `Data - Actuals` cells, so no new registry id is needed for it.

---

## 8. `model_<TICKER>.py` — company-module contract

```python
def workbook_rows(actuals, drivers, periods) -> WorkbookRows: ...
```

Accepts and returns key-based structures, never row numbers or resolved A1 addresses (§14, §16.3).
`WorkbookRows` is `{sheet_name: {metric_id: {canonical_period: scalar | "=defined_name_formula"}}}`.
The returned sheet names must exactly equal `model_spec.json`'s `workbook.sheets` after `SourceData`
and `Drivers`; the engine creates that declared order, binds every output as
`model.<sheet>.<metric_id>.<period>`, and rejects output periods outside the canonical grid.
Historical model cells must link their single `SourceData` hardcode by defined name rather than copy
it. All company strategy — drivers, segment bridges, scenarios and accounting checks — lives here;
`engine.py` only lays out declared sheets and resolves keys to cells.

## `scripts/cli.py`, `rollover.py`, `engine.py`, `checks.py`, `style.py`, `overrides.py` — entry points

```python
# cli.py — python3 scripts/cli.py <project_dir> build|check [--full]
#      or python3 scripts/cli.py <new_project> rollover --prior-project <old_project> --output-project <rolled_project>
def build(project_dir: Path) -> Path: ...      # writes model_spec.json workbook.filename once; refuses to overwrite
def check(project_dir: Path, mode: Literal["fast", "full"] = "fast") -> CheckReport: ...
# Prepared-project runtime only: no raw-source ingestion, rendering, or recalculation.

# rollover.py — copies a new prepared project, carries compatible inputs by driver_id, and resets approval.
def rollover(prior_project: Path, new_project: Path, output_project: Path, report_path: Path | None = None) -> dict: ...

# engine.py
def build_workbook(spec, actuals, drivers, company_module, approval_manifest=None) -> BuildContext: ...

# checks.py
def check_fast(project_dir: Path) -> CheckReport: ...   # shared formula/reference/defined-name/approval-isolation checks
def check_full(project_dir: Path) -> CheckReport: ...   # structural core plus cached formula-error and no-positional-cross-sheet checks; company source/accounting checks are additive

# style.py — cell-level house-style writers
# title, subtitle, header, label, note, band, put, comment, widths, base, backlink

# overrides.py — identity-based user-owned-value preservation
def extract(path: Path, sheet: str = "Assumptions", ...) -> OverrideSet: ...
def restore(template: Path, destination: Path, overrides: OverrideSet, ...) -> RestoreReport: ...
```

---

## 9. Worked example index (VRT)

| Interface | Worked example |
|---|---|
| `fact_map.json` entry, direct SEC fact | `revenue`, §2 |
| `fact_map.json` entry, segmented fact | `regional_revenue_emea` via `dimension_member=vrt_EMEASegmentMember`, §2 |
| `fact_map.json` entry, 8-K-only fact | `adjusted_diluted_eps`, §2 |
| `fact_map.json` entry, derived fact | `gross_profit`, §2 |
| `fact_map.json` entry, dated price | `price_dated` reading the raw Yahoo payload, §2 |
| `actuals.csv` row | `revenue` 2026Q2, §5 |
| `benchmarks.csv` row | `price_dated` 2026-09-18, §5 |
| `drivers.csv` row | `regional_organic_growth_americas`, §6 |
