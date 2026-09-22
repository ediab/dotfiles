# V2 progress log

Append only, newest last.

## 2026-09-22 — Stage 1 + Stage 2, Task 2 and Task 3 in flight

Done:
- Task 2 (Stage 1 benchmark): timed `build.py` / `check.py` in a scratch copy of
  `~/Desktop/equity-models/VRT/` (never `--force`d the live copy). Both complete in under 1s per
  run; recorded in `V2_PLAN.md` §2 under "Stage 1 benchmark". Finding: process wall-clock was never
  the bottleneck — the 91-minute session's cost was invocation count (81 calls) and per-call context
  re-reads, confirming §3's diagnosis rather than adding a new one.
- Resolved all four "known unknowns" (§18) via store investigation (`data/tables/VRT/`,
  `data/raw/VRT/`, `8k_cells.csv`, XBRL parquet schemas):
  - Dated price: read the raw Yahoo payload (`data/raw/VRT/yahoo/<sha256>/payload.json`, an
    `{columns,index,data}` frame with full ISO dates) directly — the `data/csv/` export is the
    defective (date-less) view, the raw payload was never broken.
  - 10-K/10-Q text: confirmed absent from the store in practice (only 8-K exhibits + statement
    tables); SKILL.md's existing claim stands.
  - `historical_inputs.csv` → `actuals.csv` schema mapping: written into `references/interfaces.md` §5.
  - Segment label stability: labels are NOT stable (VRT's EMEA label punctuation changes between
    filings) but the XBRL `dimension_member` token (`vrt_EMEASegmentMember` etc.) is. Match on the
    token, never the label — encoded in `evidence.py` and `interfaces.md` §3.
- Wrote `references/interfaces.md` per §8: model_spec.json schema (unchanged from pilot),
  fact_map.json schema, structured locator grammar (`sec_snapshot` / `8k_exhibit` / `raw_payload` /
  `derived`), transform registry (carried from §8 verbatim), `actuals.csv`/`benchmarks.csv`/
  `drivers.csv` schemas, `evidence.py` entry points (implemented), and Stage-3 entry-point stubs for
  `engine.py`/`checks.py`/`style.py`/`overrides.py`/`cli.py`/`model_<TICKER>.py` (specified now per
  §8's intent, not implemented — that's Stage 3).
- Wrote `scripts/evidence.py`: generic reader, no VRT-specific knowledge in the module itself.
  Implements all four locator schemes and the `q4_from_fy_minus_9m` / `segment_axis_filter` /
  `unit_scale` transforms for `sec_snapshot` facts, semantic (row_label/column_label regex, never
  period-hardcoded table/row/col) matching for `8k_exhibit` facts, and arithmetic evaluation for
  `derived` facts. Spot-verified against known-correct v1 values for `revenue`, `regional_revenue_emea`
  (segment axis purity rule), and `adjusted_diluted_eps` (8-K semantic match) before handing off the
  full 44-metric mapping.

In flight:
- Dispatched a subagent to build the complete VRT `fact_map.json` (all 44 metrics from
  `historical_inputs.csv`), extend `model_spec.json`'s `release_accessions` to all 12 historical
  quarters (only 2024Q1–2026Q2 were populated; 2023Q3/2023Q4 need the comparative-column accessions
  `0001628280-24-043343` / `0001628280-25-005006` — the store holds no "own" 2023 filing), freeze
  `evidence/actuals.csv` + `benchmarks.csv` + `availability.md`, and run the required row-level
  comparison against all 507 rows of `historical_inputs.csv`. Not yet returned.

Blocked: nothing yet — waiting on the subagent's comparison result before Stage 2's exit criterion
can be claimed either way.

Next: review the subagent's `fact_map.json` and comparison output myself (do not take its
"passed"/"failed" claim at face value — re-run or spot-check independently), fix or flag any
`evidence.py` bug it reports, and write the honest MATCH/DIVERGENT/UNRESOLVED tally into this file
and the final report to the user. Do not claim Stage 2 passed until that comparison has actually run
and been checked.

## 2026-09-22 — Stage 2, Task 3 complete (exit criterion partially met)

Done:
- Reviewed and independently re-ran the subagent's work. `comparison_result.json` reproduced exactly
  (420 MATCH / 24 DIVERGENT / 62 UNRESOLVED of 506 rows) via a clean second run of `compare_v1.py`,
  not just re-reading its saved output. Spot-checked several DIVERGENT/UNRESOLVED reasons against the
  store directly (e.g. confirmed only one Yahoo raw payload under `data/raw/VRT/yahoo/` has ISO-date
  index format matching a dated price, and its resolved value $249.3899993896 matches
  `model_spec.json`'s independently-recorded official close of $249.39).
- Three real bugs found and fixed in `scripts/evidence.py` during the build (reviewed, sound):
  1. `_find_period_column` didn't match bare-date balance-sheet columns (`"2026-06-30"` vs
     income/cashflow's `"2026-06-30 (Q2)"`) — `cash`/`current_debt`/`long_term_debt` never resolved.
     Fixed with a bare-date fallback, non-YTD only.
  2. `q4_from_fy_minus_9m` applied unconditionally regardless of which period was being resolved,
     corrupting non-Q4 periods for any metric assigned that transform. Gated on `period.endswith("Q4")`.
  3. `interfaces.md` §2 promised disjoint per-period predicates for a metric needing more than one
     locator, but `FactMapping`/`build_actuals` had no field for it. Added `periods: list[str] | None`
     to `FactMapping`; `build_actuals` now keys results in a dict (`by_key`) instead of an
     append-only list, so a later disjoint entry for the same metric can't silently duplicate rows.
- 39 of 44 v1 metrics carried into `fact_map.json` (42 entries — 3 metrics need >1 locator via the
  `periods` predicate). 5 metrics deliberately left unmapped rather than forced: `short_term_investments`
  (undisclosed; v1 hardcoded 0.0 — mapping a locator that always returns 0 would itself be a hardcode),
  `end_shares` (only exists as text embedded inside an XBRL label, no discrete concept — would need a
  new locator scheme, out of scope), `organic_growth_{americas,apac,emea}` (the 8-K row_label for each
  region is byte-identical across 3 different tables — revenue $, AOP $, organic growth % — so semantic
  row_label matching cannot disambiguate without a row/col hardcode, which the plan forbids).
- Working artifacts at `~/Desktop/equity-models/VRT_v2_stage2/` (sibling to, not inside, the live
  `~/Desktop/equity-models/VRT/` pilot copy — kept separate since Stage 3's atomic switch hasn't
  happened yet): `fact_map.json`, extended `model_spec.json` (12-quarter `release_accessions`, the
  original only covered 10), `evidence/{actuals.csv,benchmarks.csv,availability.md}`, `compare_v1.py`,
  `comparison_result.json`. Not copied into git — these are Stage 2 working evidence for a specific
  snapshot pull, not skill source; Stage 3 decides where the per-company project template lives
  permanently.

**Stage 2 exit criterion (§15) — partially met, explicitly not rounded up.** Every one of the 506
rows either resolves to a matching value (420, tight tolerance: 0.01 absolute or 0.1% relative) or
carries a specific, investigated, non-generic reason (24 divergent, 62 unresolved) — so no row was
silently dropped, no zero stands in for missing data, and no locator was forced with a hardcode to
manufacture a match. But 62 rows (12%) are UNRESOLVED rather than resolved-with-lineage, so full
coverage is not met. The stop condition that was honored: "Stage 2 divergences that are not
explainable by a declared transform — that is a mis-mapped metric, not a tolerance problem" (§18) —
every divergence found *was* explainable (rounding propagation, restatement vintage, FY-9M vs
discrete-quarter basis), so nothing here indicates a mis-mapped metric requiring a stop.

Blocked: nothing — this is a scope boundary (5 metrics need a locator-grammar extension or accepted
gap), not an error requiring a decision before Stage 3 can start.

Next (Stage 3, not started): decide whether the 5 unmapped metrics are (a) accepted as a permanent
known gap with a divergence reason carried into the shipped model, (b) closed by extending the
locator grammar (a new scheme for text-embedded XBRL label values, e.g. `end_shares`), or (c) closed
by a deliberate, reviewed row/col exception for the handful of genuinely ambiguous 8-K tables — then
extract `scripts/{engine,checks,style,overrides,cli}.py` from the pilots and do the atomic `SKILL.md`
switch per §15 Stage 3's exit criterion.

## 2026-09-22 — post-Stage-2 review fixes

Done:
- A fresh deepseek-flash review independently verified ten actionable issues in the Stage 2 evidence layer and VRT donor pilot. Fixed them before beginning Stage 3: aligned `references/interfaces.md` with the shipped semantic locator grammar; made literal-hash `raw_payload` resolution work and made required unresolved facts fail closed (with `tests/test_evidence.py`); restored the FY2025 published adjusted-net-income benchmark and Checks row; stopped assigning Yahoo estimate rows to unlabeled periods; corrected the VRT approval command; made benchmark isolation an allowlist; made `rollover_test.py` import the in-repo `overrides.py`; and corrected the v2 acceptance-status claim.
- Validation passed:
  - `python3 -m unittest discover home/skills/equity-modelling/tests -v` — 2 tests passed.
  - `cd home/skills/company-model/models/VRT/build && python3 data.py && python3 approve_forecast_test.py` — passed.
  - `VRT_OUTPUT=/tmp/VRT_review_fix.xlsx python3 build.py && python3 check.py --fast /tmp/VRT_review_fix.xlsx` — passed (1,014 data cells; 1,537 structural/pipeline checks; formula-value checks skipped because fast mode does not recalculate).

Decision:
- `short_term_investments` stays visibly unavailable when undisclosed; v1's fabricated zero will not be preserved.
- Extend the locator grammar for `end_shares`, whose source is a number embedded in an XBRL label. For the three organic-growth metrics, permit a narrow reviewed `8k_exhibit` exception carrying the release-table identity and column role, because the retained cells provide no semantic discriminator; validate every exception against the immutable exhibit hash and v1 comparison output. Do not accept a permanent silent-gap policy.

## 2026-09-22 — Stage 3, shared-helper extraction started

Done:
- Copied the proven, company-independent `style.py` and identity-based `overrides.py` helpers from `company-model` into `equity-modelling/scripts/`, together with the 22-case override test suite. The old helper defaults remain during the extraction; the `Drivers` / `InvestmentView` rename is part of the later atomic runtime switch.
- `python3 -m unittest discover home/skills/equity-modelling/tests -v` passes 24 tests.

In flight:
- Extract the engine, fast/full checks and CLI, then adapt the VRT rebuild to use those modules. The live `SKILL.md` still correctly describes v1 and has not switched.

Next:
- Complete the extracted core and the VRT adapter, then make the sheet rename and `SKILL.md` switch in one change. The unresolved rows remain explicit Stage 2 coverage debt and must stay visible in the VRT rebuild until the new locator paths have been implemented and re-compared.

## 2026-09-22 — Stage 3 slice review and fixes

Done:
- A fresh `glm-5.3-flash` reviewer at maximum reasoning reviewed the extracted helpers and VRT imports. Owner verification accepted two required `grid.py` bugs and several low-risk hardening/documentation findings.
- `PeriodGrid` now rejects duplicate fiscal-quarter identities, serves complete mixed actual/estimate years consistently as an estimated annual period, and uses Excel-case-insensitive defined-name collision detection. Defined names now reject an absent workbook sheet.
- `overrides.restore()` now rejects duplicate template period labels, matching extraction; CLI column arguments accept multi-letter Excel columns. Added `references/evidence-rules.md` and reconciled `interfaces.md` with the style and override APIs actually shipped.
- VRT now imports extracted v2 `style.py` and `overrides.py` in this repository. Its company calculations remain local until the full adapter is ready.

Validation:
- `python3 -m unittest discover equity-modelling/tests -v` — 28 tests passed.
- `python3 -m py_compile equity-modelling/scripts/{evidence,grid,style,overrides}.py` — passed.
- Fresh `/tmp/VRT_stage3_review_fixes.xlsx` build, `check.py --fast`, and `rollover_test.py` — passed (1,014 Data cells; 1,537 fast structural/pipeline checks; no unexplained hardcodes; identity rollover preserved overrides and narrative).
- `git diff --check` — passed.

In flight:
- The review correctly did not treat later-plan incompleteness as a defect. Stage 3 still lacks the generic engine, checks and CLI, the VRT adapter, the atomic sheet/runtime switch, and its parity gates.

Next:
- Extract the smallest reusable engine boundary from the VRT build without introducing a formula DSL, then make VRT use that boundary before changing the live skill contract.

## 2026-09-22 — Stage 3 engine spine

Done:
- Added `scripts/engine.py`: it owns canonical-period conversion, evidence/driver sheet placement, key-bound Excel defined names, and fail-closed batch activation. Company modules receive only metric-keyed actuals and active drivers through `segment_build`, `profit_bridge`, and `scenario_wiring`; they do not receive cell addresses. Their returned metric/period maps are rendered to `RegionalModel`, `Earnings`, and `Scenarios` and each output cell is rebound under a stable defined name.
- The approval manifest hashes sorted `(driver_id, period, value)` triples. Proposed inputs produce blank active values; any partial, unmanifested, blank, or changed approved batch fails rather than quietly activating a forecast.
- Added `tests/test_engine.py` (four cases) covering blank proposed inputs, exact hash activation/invalidation, partial-approval failure, and rejection of positional cross-sheet formulas from company modules. The v2 suite now has 32 passing tests.

Validation:
- `python3 -m unittest discover equity-modelling/tests -v` — 32 tests passed.
- `python3 -m py_compile equity-modelling/scripts/{engine,evidence,grid,style,overrides}.py` and `git diff --check` — passed.

In flight:
- This is intentionally not the runtime switch: the VRT company module and generic checks/CLI are not yet extracted, and VRT has not yet rebuilt through `engine.py`. Do not point `SKILL.md` at it until that atomic migration and parity proof are complete.

## 2026-09-22 — VRT full routine validation fix

Done:
- Full ASP recalculation exposed that `=Data - Benchmarks!<blank>` evaluates to zero. The Consensus Yahoo cross-check column now uses an explicit blank guard, so unavailable provider values remain blank after recalculation rather than becoming fabricated zeroes.

Validation:
- Fresh `VRT_Model_2026-09-22_stage3_review_recalculated.xlsx` routine check passed: 3,053 formulas evaluated, zero unsupported/errors, 3,163 structural/pipeline checks, all 150 Checks rows OK, source reconciliation, hardcode scan, controlled entry, approved-assumption behaviour, rollover, and 20 rendered ranges passed.
- All 20 ASP render PNGs in `/tmp/VRT_stage3_routine_renders` were inspected; no clipping or broken populated results were observed. Blank forecast/chart areas are expected because the forecast remains unapproved.
- The native Microsoft Excel gate was attempted both with an existing Excel process and again after Excel was closed. Both attempts failed opening its own temporary `gate.xlsx` with macOS `OSERROR -50` / “Parameter error”; this is an automation/environment blocker rather than a workbook-package failure (`unzip -t` passes). ASP evidence is not a substitute for the requested native proof.

## 2026-09-22 — Stage 2 `end_shares` locator extension

Done:
- Implemented the staged `sec_label` locator mode for the one supported standard-label construction: comma-separated issued-and-outstanding counts explicitly paired to period-end dates with `respectively`. It rejects ambiguous labels rather than applying free-text parsing.
- Added VRT's `end_shares` map using `us-gaap_CommonStockValue`, with a `-6` scale to millions. Eleven quarters resolve with immutable SEC-table lineage; 2023Q3 remains unavailable because retained labels do not cover that date. The VRT source spec now accurately keeps `forecast_gate.approved=false`.

Validation:
- `tests/test_evidence.py` covers successful exact date pairing and ambiguous-label rejection; the full v2 suite has 34 tests passing.
- Regenerated VRT Stage-2 actuals/availability and reran the v1 comparison: **431 MATCH, 24 DIVERGENT, 51 UNRESOLVED** of 506 rows (previously 420/24/62). No `end_shares` row is now unresolved except the genuinely absent 2023Q3 value.

## 2026-09-22 — Stage 2 organic-growth reviewed exception

Done:
- Implemented `8k_exhibit_role`, the authorized narrow exception for the duplicated regional labels. It selects only an exact `Regional Segment Results` caption, the current-quarter `Organic Δ%(2)` column role under its period header, an exact allowed region label, and a period-pinned immutable exhibit hash. It rejects mismatched hashes and non-unique candidates; table/row/column indices are output lineage only, never selectors.
- Added three VRT mappings with ten period-specific exhibit hashes each. All 30 organic-growth facts from 2024Q1–2026Q2 now resolve and match v1. The intentional absence before 2024Q1 is not backfilled.

Validation:
- Added synthetic resolver tests for exact semantic resolution and duplicate-candidate failure. The full v2 suite still has 36 tests passing; syntax and `git diff --check` pass.
- Regenerated Stage-2 evidence and reran the v1 comparison: **461 MATCH, 24 DIVERGENT, 21 UNRESOLVED** of 506 rows. The remaining unresolved items are documented non-silent gaps: 11 short-term-investment periods, five historical corporate-cost periods with unresolved table-role ambiguity, three Q4 diluted-share periods, and two 2023Q4 adjusted measures.

Next:
- Keep the remaining 21 evidence gaps visible. Do not reactivate the false approval that was removed from `model_spec.json`.

## 2026-09-22 — Gate 2 decision

Decision:
- The user selected **Keep blank** for the VRT eight-quarter forecast package. This is not an approval or rejection of the proposed values: it preserves them as proposed and keeps every forecast output inactive/blank.

Recorded:
- `VRT_v2_stage2/model_spec.json` now records the decision and explicitly states that no approval manifest exists.

Next:
- Continue the Stage 3 VRT adapter/runtime-switch work against this unapproved state. Its checks must preserve blank forecast propagation; it must not synthesize an active approval.

## 2026-09-22 — Stage 3 artifact CLI and forecast-isolation hardening

Done:
- Added the artifact-driven `scripts/cli.py`: it builds exactly once from `model_spec.json`, frozen `evidence/actuals.csv`, `drivers.csv`, an optional approval manifest, and one declared `model_<TICKER>.py` company module. It refuses to overwrite a delivery.
- Added `scripts/checks.py` for the shared structural contract: required core sheets, `#REF!` formula/defined-name detection, and proposed-driver isolation. Company accounting/recalculation checks remain company-owned rather than being duplicated generically.
- Fixed a core approval leak: a company module could previously emit a forecast formula even when every driver was proposed. `engine.py` now blanks all forecast module outputs unless the complete driver batch activates through its approval manifest; actual-period values and named references remain available.

Validation:
- Added an end-to-end CLI fixture and extended the engine approval test to cover blocked and hash-approved module outputs.
- `python3 -m unittest discover equity-modelling/tests -v` — 37 passed.
- `python3 -m py_compile equity-modelling/scripts/{engine,evidence,grid,style,overrides,checks,cli}.py`, JSON parsing of the VRT spec, and `git diff --check` — passed.

In flight:
- The generic CLI/check core is tested only through a fixture. The VRT company adapter, its renamed sheet implementation, and the atomic `SKILL.md` runtime switch remain unstarted; no parity claim is made from this core-only slice.

Next:
- Adapt VRT to the declared artifact project shape and build its first generic-core workbook while retaining its explicit NOT APPROVED state.

## 2026-09-22 — Stage 3 first VRT generic-core build

Done:
- Pivoted the prior 80 proposed driver-quarter records into the v2 one-row-per-driver `drivers.csv` shape (10 drivers × 8 forecast periods) without approving any value.
- Added VRT's `model_VRT.py` company module. It exposes actual regional and earnings rows by metric key and uses only stable defined-name formulas for revenue growth / adjusted operating-profit wiring when a future approved fixture exercises it.
- Built the first generic-core review workbook: `VRT_v2_stage2/VRT_Model_2026-09-22_stage3_core_review.xlsx` (SHA-256 `9c14c6981610d95284d01de5600479dbb3cc1e31fbcaf4022ebc1a6202aaf40c`). It has `SourceData`, `Drivers`, `RegionalModel`, `Earnings`, and `Scenarios`; its 500 frozen actual facts and 10 proposed driver rows are present.
- Removed the inherited, misleading `Back to Outlook` text from generic-core sheets while preserving the legacy VRT builder's default presentation.

Validation:
- Generic VRT build and structural check completed 1,438 checks. It contains zero populated active-driver cells and zero populated forecast model cells, as required by the Gate-2 decision.
- ASP/Formualizer recalculation of the unapproved review workbook was clean (0 formula cells, 0 errors, 0 unsupported). Its five sheets were rendered and visually inspected: actual values and explicit pink unavailable values are legible; blank pink forecast areas are intentional.
- An isolated, non-delivery approved-manifest fixture exercised VRT's emitted named formulas: ASP evaluated all 32 formula cells with 0 errors and 0 unsupported formulas. The fixture was deleted afterwards.
- Full v2 unit suite: 37 tests passed; core compilation and `git diff --check` passed.

In flight:
- This is a narrow generic-core proof, not parity: it deliberately does not yet recreate the VRT investment view, cash/debt, sensitivity, consensus, checks, or the full regional forecast/earnings bridge. The legacy VRT workbook remains the capability baseline. Therefore Stage 3's capability-parity and atomic `SKILL.md` switch exits are still unmet.

Next:
- Expand the VRT company module and workbook composition to cover the remaining approved v2 sheet contract, then perform a row/formula parity comparison before switching the runtime contract.

## 2026-09-22 — Stage 3 regional-driver design and propagation proof

Decision:
- The user explicitly approved adding the three regional organic-growth driver rows (Americas, APAC, EMEA) to the existing VRT blueprint. This is a Gate-1 design decision only; it does not reverse the earlier Gate-2 decision to keep all forecast values blank.

Done:
- Aligned `drivers.csv` to the already-approved regional-first blueprint. It now contains the three regional organic-growth rows plus acquisition-revenue, FX-revenue, three regional-margin, and corporate-cost rows. The resulting 19 driver rows remain `proposed`; the nine new regional/bridge drivers have deliberately blank values and documented evidence/rationale rather than invented forecasts.
- Expanded the VRT module's prospective formulas: regional organic growth drives regional revenue; regional margins drive regional adjusted operating profit; acquisition and FX remain separate bridges into consolidated revenue; corporate costs bridge regional profit to consolidated adjusted operating profit; adjusted net income, EPS and FCF follow from that result.
- Added the frozen dated price once to `SourceData` as a named benchmark reference. The scenario sheet derives an implied price at the frozen trailing adjusted P/E; it is a valuation output only and never feeds the operating forecast.

Validation:
- Unapproved VRT generic-core build/check now completes 1,731 structural checks and preserves 0 active-driver and 0 forecast values.
- In an isolated non-delivery manifest fixture, ASP/Formualizer evaluated all 120 VRT formulas with 0 errors and 0 unsupported formulas.
- Controlled-driver proof: increasing the approved-fixture Americas organic-growth input from 10% to 20% changed Q3 2026E revenue (2,943.38 → 3,114.62), adjusted operating profit (658.02 → 705.97), adjusted EPS (1.2784 → 1.3742), adjusted FCF (478.30 → 514.13), and implied price (60.27 → 64.78). Actuals, guidance, and the frozen price were not changed. Both fixtures were deleted afterwards.
- The 37-test v2 suite, core compilation and `git diff --check` were clean before the current external VRT module/driver extension; that extension was separately compiled and exercised by the clean 120-formula fixture.

In flight:
- The VRT core still lacks the remaining v2 presentation/check sheets and has no v1 parity evidence. The new forecast formulas are deliberately absent in the user-delivery workbook until a full future Gate-2 approval manifest exists.

Next:
- Add the remaining named-sheet composition and accounting/benchmark checks, then compare v1 and v2 canonical rows before considering the runtime switch.

## 2026-09-22 — Stage 3 declared-sheet adapter slice

Done:
- Replaced the three fixed company callbacks with one declared-sheet `workbook_rows(actuals, drivers, periods)` contract. The engine now creates exactly the ordered `workbook.sheets` from `model_spec.json`; a company module must return exactly every non-`SourceData`/`Drivers` sheet. This removes the generic spine's hidden five-sheet assumption.
- VRT now builds the approved v2 sheet names: `InvestmentView`, `SourceData`, `Drivers`, `RegionalModel`, `Earnings`, `CashDebt`, `Scenarios`, `Sensitivity`, `Consensus`, and `Checks`.
- Historical values on company sheets are now defined-name links back to their only `SourceData` hardcode. The generic `Checks` implementation validates the sheet order declared by the project, not a stale fixed set. `interfaces.md` publishes the new single callback contract.
- Added a visible regional-revenue-bridge check and structured rows for the view, cash/debt, sensitivity, consensus-data-not-held, and checks surfaces. These are intentionally limited early v2 implementations, not a claim that each legacy sheet's content is yet at parity.

Validation:
- Fresh VRT build and full structural check: 1,991 checks.
- Fresh unapproved workbook recalculation: 469 formulas evaluated, 0 unsupported, 0 errors, clean state. The delivery remains blank in all forecast cells because no approval manifest exists.
- An approved, non-delivery full-sheet fixture recalculated 653 formulas with 0 unsupported and 0 errors.
- All 39 v2 unit tests, core/VRT compilation, and `git diff --check` passed.

In flight:
- The runtime switch remains blocked: parity is not yet established, `Consensus` accurately records that its frozen evidence does not hold the legacy consensus series, `Checks` does not yet surface all accounting statuses, and several presentation sheets are structural rather than full replacements.

Next:
- Define and run a metric/period parity report against v1, expand failed/missing rows explicitly, and only then decide which remaining capability gaps can be closed from frozen evidence.

## 2026-09-22 — fresh VRT actual/parity evidence

Validation:
- Re-ran the frozen Stage-2 `compare_v1.py` against all 506 v1 historical rows: 461 MATCH, 24 DIVERGENT, and 21 UNRESOLVED. The 45 open rows remain documented by metric/period/reason in `comparison_result.json`; this explicitly fails the full-coverage and actual-parity exits.
- Independently read the fresh v2 review workbook after recalculation and compared every one of its 500 frozen `SourceData` fact cells against `evidence/actuals.csv`: 500 checked, 0 mismatches. This establishes that the workbook faithfully represents the current evidence freeze; it does not make the unresolved evidence rows or v1 capability debt disappear.

Next:
- Use the 45-row comparison ledger as the v1 actual-parity baseline; keep each unsupported source gap visible while adding the remaining company checks and presentation capabilities.

## 2026-09-22 — Stage 2 short-term-investment correction

Done:
- Audited V1's live `sources.csv` after the comparison review. This corrected an over-broad V2 gap: five periods (`2025Q2`–`2026Q2`) have explicitly disclosed short-term-investment balances in the frozen SEC balance snapshots. Added their exact SEC concept mapping, restricted to those five periods; no value is inferred for earlier undisclosed periods.
- Removed the comparison script's metric-wide short-term-investment exclusion. The six genuinely undisclosed V1 zero stand-ins remain explicit unavailable facts with a period-specific reason, while the five disclosed balances now participate in parity comparison.

Validation:
- Regenerated the frozen evidence (505 rows) and reran all 506 V1 historical rows: **466 MATCH, 24 DIVERGENT, 16 UNRESOLVED**. The five newly mapped balances match exactly: 98.2, 544.6, 99.5, 349.9, and 300.0 USDm.
- Fresh VRT review build and structural check: 2,003 checks. Formualizer recalculation evaluated 469 formulas with 0 unsupported formulas and 0 errors. Direct workbook inspection verified all five new facts on `SourceData`.
- All 39 v2 tests, core/VRT compilation, JSON parsing, and `git diff --check` passed.

In flight:
- Stage 2 remains blocked by the 16 visible rows: six genuinely undisclosed early short-term-investment values, five corporate-cost table-role ambiguities, three Q4 diluted-share row/column ambiguities, and two Q4 2023 adjusted measures. They must not be filled from the old workbook merely to satisfy parity.

Next:
- Review the five corporate-cost source cells from V1 against the retained release-table structure and extend the constrained role locator only if the column identity can be made unambiguous.

## 2026-09-22 — Core V2 release decision

Decision:
- The user explicitly chose a **useful, decent V2 core earnings model** as the priority. V1 is a diagnostic/reference source, not a release-parity target. A V1 value can identify a missing V2 mapping, but it must never be copied into V2 without frozen lineage.
- The first useful V2 release prioritizes source-backed historicals, blank-until-approved forecast activation, regional-to-consolidated revenue/earnings/FCF/valuation propagation, checks, rollover, and a usable workbook. Presentation-complete parity with V1 is not a prerequisite for this core release.

Validation:
- After the decision, the full v2 suite passed **40 tests**. Regenerating the 505-row V2 evidence freeze preserved **466 MATCH, 24 DIVERGENT, 16 UNRESOLVED** against V1; that ledger is now diagnostic only.
- Fresh ten-sheet VRT core build passed 2,003 structural checks. Formualizer recalculation evaluated 469 formulas with zero errors and zero unsupported formulas. The current review workbook is `VRT_Model_2026-09-22_stage3_core_review.xlsx` (SHA-256 `2b812bb886e683334fe168fef9b164b47872bd3d3ab8088f67e46998f89fb1b7`).

In flight:
- The V1-derived 16-row ledger still needs source review where the omitted fact matters to the V2 core. Six unsupported V1 zeroes remain unavailable by design. The active SKILL.md runtime switch, core-model acceptance, second-company proof, and rollover/release gates remain incomplete.

Next:
- Use only source-backed evidence gaps that materially affect the core V2 model to prioritize the next extraction fix; do not spend implementation time chasing cosmetic V1 parity.

## 2026-09-22 — Prepared-artifact core release proof

Done:
- Completed the atomic prepared-artifact runtime/documentation switch. The generic `build`, `check --full`, and project-level `rollover` flows are documented consistently across `SKILL.md`, `AGENTS.md`, `interfaces.md`, and `model-rules.md`; raw ingestion, rendering, and native recalculation remain explicitly outside that bounded runtime.
- Hardened evidence freezing and forecast activation. Populated facts require immutable lineage; every covered blank fact requires a specific reason; activation requires an explicit boolean forecast gate, a complete approved manifest, a single approval ID, and a matching digest. Proposed drivers remain blank.
- Added model-spec fiscal period-end support, allowing non-calendar fiscal years. The frozen-cache AVGO proof now provides the required second-company validation: a 52/53-week fiscal map, 200 explicit source rows (195 populated; five documented blanks), inactive delivery forecasts, controlled approved-fixture propagation, source re-resolution, Formualizer recalculation, and rendered review.
- Shipped generic project-level driver rollover. It creates a separate output project, transfers only stable-ID/definition-compatible driver values, invalidates approval state, and then builds/checks the output; focused tests and a VRT smoke passed without mutating inputs.
- Closed VRT's remaining evidence-freeze completeness gap: formerly period-excluded facts are now 23 explicit `unavailable` mappings with reasons rather than omitted rows. `python3 freeze_evidence.py` is the documented VRT reproduction command. The refreshed VRT freeze is 528 rows: 491 immutable-lineage populated facts plus 37 visible unavailable facts; all 528 reproduce exactly into `SourceData`.

Validation:
- Full generic test discovery: **79 tests passed**; core scripts compile; `git diff --check` passed.
- Final VRT proof: `VRT_Model_2026-09-22_v2_evidence_complete.xlsx`, SHA-256 `546a03949c9e000f9ae14d6d7ca9e8aa7b2fb54ab833e6bb6382c00ec92b779c`. `check --full` passed **2,484 checks**; ASP/Formualizer evaluated **480/480** formula cells with zero errors or unsupported formulas; direct comparison found **0/528** `SourceData` mismatches. All ten current-revision native-raster renders were inspected; populated historical values are legible and unavailable/forecast cells remain blank.
- AVGO final proof: `AVGO_Model_2026-09-21_v2.xlsx`, SHA-256 `7b4ded2e0d937d938167d6076404138a6d6ef732d9deb08b75352fa4072cd77f`. `check --full` passed **1,439 checks** and Formualizer evaluated 325 formulas with zero errors or unsupported formulas.

Open gates:
- Stage 5 still needs a real post-earnings source-pack rollover, not merely generic fixture/smoke coverage.
- Native Microsoft Excel automation remains blocked: a final isolated VRT gate copy exceeded its 180-second automation limit. Formualizer and native-raster rendering are strong non-native evidence, not a substitute for that gate.
- VRT forecast activation remains intentionally inactive until a future explicit approval manifest covers the complete regional-first dependency set.

## 2026-09-22 — Final reviewer remediation reopened release gates

The required independent review of commit `29e0375` found release-blocking defects. The SEC resolver now records concrete resolved parquet paths (not the former `<resolved-table>` placeholder); refreshed VRT and AVGO freezes contain zero placeholder paths and both deliveries still pass `check --full`. Remaining release blockers are: the generic `8k_exhibit` resolver can select the first of multiple matching cells; `check --full` does not perform the raw-store/source-replay checks still promised by older plan sections; the update guide and approval-manifest production path do not yet match the shipped prepared-project runtime; and rollover does not yet preserve narrative or produce an estimate-change bridge. Stage 6 must remain open until each is remediated and independently rechecked.
