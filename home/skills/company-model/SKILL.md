---
name: company-model
description: Build or update a company-specific, source-driven earnings model workbook — 12 actual and 8 forecast quarters on the company's own fiscal calendar, two in-workbook data layers with per-cell provenance, GAAP and adjusted EPS kept distinct, historical balance sheet and cash flow, management guidance and consensus kept separate, and trading multiples on a verified dated price — with an approval gate on the forecast assumptions and a quarter-rollover update path that preserves designated overrides and Outlook text. Use when asked to model a company, to recreate or update an earnings model after results, or to compare a model against a reference workbook, guidance or consensus.
---

# Company model

Builds one company's earnings model from retained official evidence: statements, earnings
releases, guidance, consensus and a dated price. The forecast is consolidated revenue ×
adjusted margin with a GAAP bridge — not an integrated three-statement model, and not a DCF.

Read `references/model-rules.md` before step 3; it holds the project contract, the Data-sheet
layout, the hardcode policy and the conventions every build must satisfy. Updates and quarter
rollovers follow `references/update-model.md`.

Every historical input enters the workbook **once**, on `Data - Actuals` or `Data - Benchmarks`.
Every other sheet links to those cells or calculates from them; a source number is never typed
twice. Every sourced Data cell is independently reconciled against the retained evidence, and
forecast outputs stay blank until the user approves the assumptions. Guidance and consensus are
benchmarks, never assumptions.

Two hard gates stop the run:

- **Acquisition permission** before any live `pull-financial-data` request (step 1). A pull can
  spend SEC requests, ~100 MB of originals per ticker and limited Alpha Vantage quota.
- **Assumption approval** before the forecast is activated (step 5). Approval of *building* a
  model never approves the financial assumptions. Before approval, deliver an
  **actuals-review workbook** — sourced history, benchmarks, proposed-but-inactive assumptions,
  blank active inputs, blank forecast outputs. Ask, in one batch, and wait.

## Steps

1. **Confirm scope.** Company, fiscal calendar, intended as-of date, output parent directory and
   the source policy (may the store be refreshed from the network, or is the retained snapshot
   frozen?). If the user is not explicit, ask before acquiring anything.
   *Done when:* ticker, as-of date, frozen-or-live source policy, and the chosen parent
   directory are written down and the parent directory has been checked for collisions.

2. **Inspect what evidence is already held.** Follow `pull-financial-data`: from the tool's
   checkout run `.venv/bin/financial-data-pull --index <TICKER>`, then
   `.venv/bin/financial-data-pull <TICKER> --cache-only`. Report to the user which datasets and
   filing dates are held before spending anything, and record the snapshot run-ids.
   *Done when:* the user has seen the holdings summary and has approved either the retained
   snapshot or an explicit acquisition scope, with a ceiling.

3. **Build the evidence layer.** Create `<parent>/<TICKER>/` (the project contract is in
   `references/model-rules.md`) and write `build/layout.py`, `build/data.py` and `sources.csv`
   so that **every** historical input is derived from the retained evidence — the cell dump, the
   statement CSVs, the release files — never from a reference workbook and never from the
   acquisition tool's convenience loader. `layout.py` holds structure only: sheet names, period
   labels, stable metric IDs, the ordered row catalog, the Outlook field labels and the allowed
   hardcode ranges, plus `actual_ref` / `benchmark_ref` / `assumption_ref` helpers. Downstream
   builders call those helpers rather than repeating Data addresses. Produce an availability
   matrix for the 12 actual quarters, metric by metric, before promising complete history.
   *Done when:* every historical input has a locator (accession / table / row / column, or CSV
   table + column) in `sources.csv`, every unavailable input is marked unavailable rather than
   zero, and the availability matrix is in `research.md`. Where a metric is materially
   incomplete, escalate to the user instead of shortening the window silently.

4. **Research the business.** Write `research.md`: how the company earns money, which revenue
   drivers the disclosures actually support, the margin structure, one-off items and their
   recurrence, the fiscal calendar (including 52/53-week years and their week counts), and the
   falsifying evidence that would break the forecast thesis.
   *Done when:* `research.md` names the chosen revenue driver route (company-specific or
   explained consolidated fallback), cites evidence for it, and lists the assumptions it forces.

5. **Propose the forecast assumptions — STOP for approval.** Draft the long-form
   `build/forecast_inputs.csv` (schema in `references/model-rules.md`): exactly one row per
   required `(driver_id, forecast period)` pair, each with `status`, a `proposed_value`, its
   basis, the evidence source and locator, and its comparison with guidance and consensus.
   Present the proposal as a compact table: driver, period, value, basis (guidance / consensus /
   retained control / reasoned fade), evidence, and the difference from guidance and consensus.
   Name the quarters with no retained evidence at all.
   Before approval the actuals-review workbook is the deliverable: proposed values visible and
   inactive, `approved_value` blank, `status=proposed`, active inputs and every forecast output
   blank. Guidance and consensus stay untouched throughout.
   *Done when:* the user has approved every material assumption, including — explicitly — any
   reuse of retained or predecessor controls, which are model configuration and never presented
   as sourced facts. Record the approval and its date in `model-brief.md`, then set
   `approved_value`, `status=approved` and the batch metadata (`approved_by`, `approved_on`,
   `approval_id`) for all required rows. Partial approval never activates a forecast.

6. **Build the workbook.** Author `<TICKER>/build/build.py` with openpyxl, following the
   workbook contract in `references/model-rules.md`. Real formulas for every derived value; the
   two Data sheets are the only places a sourced number is written, and they are written from
   `build/data.py`'s reparse of the retained evidence. Use the excel skill's authoring rules.
   Write `data-map.csv` and `sources.csv` from workbook/layout state after each build.
   *Done when:* the workbook is written to a fresh path, all 13 tabs are present in order,
   every derived cell is a formula, the colour key is applied, the forecast spine runs
   revenue → adjusted OP → GAAP OP → tax → net income → EPS with GAAP and adjusted kept
   distinct, and no numeric constant exists outside the two Data sheets and the Assumptions
   input rows.

7. **Validate.** Write `<TICKER>/build/reconcile.py` (every sourced/derived Data cell ≡ retained
   evidence, reparsed independently of `data.py`), `<TICKER>/build/verify.py` (workbook ≡
   `data.py` plus structure, links, blanks and forecast isolation) and `<TICKER>/build/check.py`
   (one command: `--fast` for source manifest, reconciliation, verification and the hardcode
   scan; `--routine` adds prompt-free `asp workbook recalculate`, requiring `0 unsupported` and
   `state: clean`, the controlled tests and ASP renders). Then inspect every render.
   *Done when:* reconciliation reports zero unexplained populated cells and set equality between
   Data cells and provenance records; verification passes; `check.py --fast` passes in seconds;
   the calculation-checks tab reads all-OK with its total derived at runtime; the renders show
   no clipping, blank formula results or broken layout; and the controlled tests pass
   (single-entry actual, pre-approval blankness, approved-assumption flow, annual conventions,
   rollover, reference immutability).

8. **Deliver.** Hand over the workbook path, `model-brief.md`, `research.md` and
   `validation.md`, and state explicitly what is unverified, unavailable or assumed. The brief
   must discuss the differences versus management guidance and versus consensus, and what
   evidence would invalidate the forecast.
   *Done when:* the user has the workbook, the brief and the limitation list, with each
   unavailable input visible in the workbook rather than silently filled.

9. **Later updates and quarter rollovers.** Follow `references/update-model.md` and preserve
   designated overrides — numeric assumption overrides and the five labelled Outlook text
   fields — with `scripts/overrides.py`.

## Reporting honestly

Implementation of this skill is not evidence that any company model works. Keep the two
separate: "skill built" and "company X validated" are different claims, and a company is only
validated when steps 3–8 completed for it with the workbook's own checks passing. Never fill a
gap with an invented value, a reference workbook's number, or a stale assumption presented as
current evidence — surface it.
