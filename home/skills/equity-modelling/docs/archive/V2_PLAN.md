# equity-modelling v2 — historical implementation plan

**Historical record, not the target workbook design.** The agreed future nine-sheet design is in
[`DECISIONS.md`](../../DECISIONS.md) and is not yet implemented. Retain this plan for V2's
implementation history and unresolved release defects; the executable current contract is
[`SKILL.md`](../../SKILL.md).

**V2 status:** VRT and AVGO proof workbooks exist, but this is **not release-ready**: the required final review found active evidence-resolver and prepared-project contract defects. V1 is diagnostic only, not a release-parity target. Generic rollover exists but lacks the real next-quarter source-pack exercise, narrative preservation, and an estimate-change bridge. Native Microsoft Excel automation also remains environment-blocked. `V2_PROGRESS.md` is the append-only execution record; this file records V2's historical design and stage gates.
`PROPOSAL-V2.md` has been absorbed (baseline, diagnosis, staged order, import lists) and deleted.

Incorporates the review in `/tmp/findings_v2.md` (nine required revisions, all accepted except
where §11 records a disagreement) and corrects the errors in this plan's own first draft (§4).

**Historical navigation:** §18 records the old V2 implementation start, not the next redesign step.

---

## 1. Goal

The model shape in `Building a model 101.md`:

> drivers → segment revenue → margins → EBIT → EPS → FCF → bull/base/bear → valuation and
> consensus variance

Forecast earnings correctly and explain where the house view differs from consensus. Not intrinsic
value to three decimals. `equity-modelling` is the surviving skill; `company-model` is the donor.

---

## 2. Measured baseline

Do not optimise before reading this. Figures verified against the repo on 2026-09-22.

| | company-model | equity-modelling |
|---|---|---|
| Authored Python per company | **7,359 lines** / 14 files | **1,329 lines** / 2 files (`build.py` 770 + `check.py` 559) |
| Workbook sheets | 13, fixed order, fixed column letters | 10, blueprint-driven |
| Populated cells | 16,341 | 6,206 |
| Formulas | 3,050 | 1,637 |
| Full-source reparses per fast check | ~5 processes + 78 parquet hashes | 1, in-process |
| `asp workbook recalculate` per routine run | 5 | 0 in-script |
| Renders | 20 PNGs / 15.4 MB | 13 PNGs / 2.0 MB |
| Workbook builds per model | 2+ (review, then active) | 1 |
| Forecast cash flow | none | yes, simplified |
| Scenarios / sensitivities | none | 3 cases + 2×5×5 |
| **Measured session** | 91 min, 342 tool calls, 519K output tokens, **`build.py` ×37, `check.py` ×44** | 90 min, 218 tool calls, 141K output tokens, `build.py` ×6, `check.py` ×12 |

VRT work folder total: 59 sessions, **22.3 hours**, 427M tokens.

Data registers are rows, not bytes: `forecast_inputs.csv` **158 rows**, `historical_inputs.csv`
**507 rows**, `sources.csv` **58 rows**.

### Stage 1 benchmark — process wall-clock (2026-09-22)

Measured against a scratch copy of the live VRT project (`~/Desktop/equity-models/VRT/`, never
run with `--force` in place), current v1 code, 3 runs each after a cold first run, `/usr/bin/time -p`:

| Command | Run | Wall-clock |
|---|---|---|
| `build.py` (no existing xlsx) | 1 (cold) | 0.65s |
| `build.py --force` | 2 | 0.62s |
| `build.py --force` | 3 | 0.58s |
| `check.py` (full, 637 checks) | 1 | 0.78s |
| `check.py` (full, 637 checks) | 2 | 0.68s |
| `check.py --historicals-only` (633 checks) | 1 | 0.49s |

v1 has no `--fast` flag; `--historicals-only` is the closest analog and is timed above. Both
scripts read only `historical_inputs.csv` / `forecast_inputs.csv` plus a handful of already-extracted
store views (`derived/VRT/8k_cells.csv`, `csv/VRT/income_quarterly_0.csv`) — neither does a full
filings-store reparse per invocation.

**Finding: process cost is not the bottleneck.** Each `build.py` / `check.py` invocation completes
in under a second. The measured session cost (91 min, 342 tool calls, 519K output tokens, `build.py`
×37, `check.py` ×44 — §2 above) comes from **invocation count and per-call context**, not per-process
wall-clock: every one of those 81 calls sat inside an agent turn that re-read large context (39k-row
scans, provenance registers, 13–20 PNGs — §3.3), and the agent chose to re-invoke rather than reuse
a frozen result because no frozen intermediate existed to check against (§3.1). Stage 2's evidence
layer targets *invocation count and context re-reads*, not per-process speed, which is already fine.

---

## 3. Diagnosis — where the time actually goes

Ranked. **Excel validation is not the main cost.**

1. **No frozen intermediate.** Everything is re-derived on every iteration. `build.py` re-parses the
   whole evidence store; each build rewrites every cell. Each fast check re-parses the same sources
   several times across processes. A one-line driver change pays for a full evidence re-derivation
   and a full re-proof. **This is the dominant cost — `build.py` ran 37 times and `check.py` 44
   times in a single session.**
2. **Per-company code re-authoring**, made worse by the rule that `check.py` must independently
   re-implement the parse graph — so company-specific parsing is written and debugged twice.
3. **Context bloat.** 91.2M cache-read tokens in 91 minutes ≈ 267K re-read per model call. 39k-row
   `8k_cells` scans, provenance registers and 13–20 PNGs sit in context. Four compactions in one
   session.
4. **Excel, minor, but with one real defect.** The native gate is broken in practice — the pilot
   records a timeout with Excel instances open and a retry failing with OS error −50. Both skills
   already skip it. The renders' true cost is tokens when the agent eyeballs them.
5. **Gates are cheap** (user think time). But company-model's pre-approval/active two-workbook
   design forces a second full build.

**"Lots of checks" is not the problem.** The checks that catch errors are ~10 assertions. The rest
is ceremony: 5× reparse, `verify.py` twice, 5 recalculations, 20 renders.

---

## 4. Corrections to this plan's first draft

Recorded so the errors are not reintroduced.

- **"~2,000 authored Python lines"** — wrong. It is **1,329**. The figure was inferred from byte
  sizes rather than counted.
- **File sizes presented as register size** (`58K`, `41K`) next to company-model's row counts,
  inviting a false comparison. Row counts are in §2.
- **"Add the forecast to the same in-memory model after Gate 2"** — not executable. A human
  approval turn does not preserve a Python process.
- **Pinning the single snapshot `170653+0000-3ce4e7`** — that snapshot is **SEC-only** (33 statement
  parquets + `sec_8k` + manifest). It contains no price, no consensus and no transcripts. The
  pilot's `model_spec.json` already does this correctly with a four-snapshot manifest; the draft
  would have regressed it.
- **"The agent reads the 10-K"** — 10-K and 10-Q documents are **not archived** by
  `pull-financial-data`; only their extracted statement tables are.
- **`forecast_inputs.csv` "~10 rows"** — VRT needs **9 primary drivers but 17 base forecast
  metrics** (136 base rows). Tax, shares, interest, capex and cash conversion are real inputs.
- **A generic 400-line `facts.py`** — overclaimed. Mapping a canonical metric to the right XBRL
  concept, dimension, share class and basis is irreducibly company-specific.
- **Provenance replay presented as independent verification** — it is not. See §6.
- **Nine speculative modules specified up front** — premature. See §5.
- **`PROPOSAL-V2.md` was never read** before a competing plan was written into the same folder. Its
  diagnosis (§3 above) was better evidenced than the draft's.

---

## 5. Target architecture

One frozen intermediate, a minimal extracted core, per-company work reduced to data.

**Build only what the working pilots have already proven.** Do not author nine modules up front;
let the VRT and AVGO builds reveal which components are genuinely invariant.

### Per company

```text
<TICKER>/
├── model_spec.json       approved blueprint, snapshot manifest, periods, drivers, valuation lens
├── fact_map.json         canonical metric → concept/dimension/locator/basis/transform  (company-specific)
├── evidence/
│   ├── actuals.csv       FROZEN canonical actuals + lineage      (built once, refreshed explicitly)
│   ├── benchmarks.csv    guidance, consensus, dated price        (built once, refreshed on update)
│   └── availability.md   metric × quarter availability matrix
├── drivers.csv           primary drivers + supporting inputs × forecast quarters + approval manifest
├── model_<TICKER>.py     company formulas: segment build, profit bridge, scenario wiring
└── <TICKER>_Model_<date>.xlsx
```

### Shipped in the skill, tested once

```text
equity-modelling/scripts/
├── evidence.py    generic reader over the pull-financial-data store, driven by fact_map.json
├── engine.py      workbook construction from model_spec + actuals.csv + drivers.csv
├── checks.py      provenance replay, semantic controls, hardcode, identity, behavioural
├── style.py       compact institutional styling, named styles, once
├── overrides.py   identity-based override and narrative preservation from a prior project
└── cli.py         build | rollover --prior-project … | check --fast | check --full |
                   render --sheets … | show <metric>
```

- `check --fast` — formulas, identities, hardcodes, missing-propagation, approval isolation. Reads
  `evidence/actuals.csv` plus the workbook. Seconds. **This is the iteration loop.**
- `check --full` — raw-source reconciliation, behavioural test, ASP recalculation, selected renders.
  Runs when the evidence layer is created or refreshed, **not** on every assumption change.
- Routine renders: `InvestmentView`, drivers, core operating model, scenarios, checks. Full-workbook
  render is release-only.

**Non-goals:** no formula DSL, no database, no engine that owns company formulas.
`model_<TICKER>.py`, `fact_map.json` and `model_spec.json` hold everything company-specific.

`spine.py`, `scenarios.py` and `valuation.py` from the draft are **not** promoted to library modules
yet. They start as company code and are promoted only where the AVGO build proves them invariant.

---

## 6. The evidence and verification contract

### Facts are mapped, not inferred

`pull-financial-data` explicitly leaves release-cell-to-model-metric mapping to the consumer. So
`evidence.py` is a generic *reader*; `fact_map.json` is the company-specific *mapping*, declaring:

- canonical metric and dimension identity;
- accounting basis and units;
- a structured source locator;
- period interpretation;
- a transform id from a small **closed registry**; and
- missing-data treatment.

Directly reported facts stay distinguished from derived facts. YTD de-accumulation, `Q4 = FY − 9M`,
annual ratios and EPS recomputation must remain **visible Excel formulas**, never Python-produced
hardcodes.

Immutable lineage terminates at snapshot parquet files or raw payloads. Rewritable `data/csv/` and
`data/derived/` views may serve as convenient locators but are never the ultimate evidence object.

### Two complementary controls, because replay alone is not enough

Provenance replay — reopen the cited source, reapply the declared transform, compare — proves the
workbook agrees with **the builder's own provenance claim**. It does not detect a wrong metric,
dimension, share class, basis or transform *declaration*. So:

1. **Exhaustive mechanical replay** over structured locators and the closed transform registry.
2. **Frozen-artifact reconciliation:** `check --full` re-reads the raw store with its own reader,
   driven by the same `fact_map.json`, and compares it with `actuals.csv`. This catches stale or
   corrupt frozen evidence and reader divergence; it is **not** independent of the mapping and must
   never be described as such.
3. **Semantic controls:** alternative-source comparisons, accounting identities, availability
   checks and reviewed spot-checks of high-materiality source selections. Gate review owns the
   correctness of metric, dimension, share-class and basis selection; no second company parser is
   claimed.

### Source boundary

Use an **immutable dataset→snapshot manifest**, as the pilot already does:

```json
"latest_sec_snapshot":        "2026-09-21T170653+0000-3ce4e7",
"latest_yahoo_snapshot":      "2026-09-21T145121+0000-9e427b",
"latest_av_estimate_snapshot":"2026-09-21T151923+0000-repair",
"latest_transcript_snapshot": "2026-09-21T150106+0000-b57670"
```

- **10-K/10-Q documents are not in the store.** Either request them from the user, explicitly fetch
  and freeze them, or limit the default filing review to evidence actually present. Do not claim to
  have read a 10-K that was never retrieved.
- **Known store defect:** `data/csv/VRT/yahoo_prices.csv` has header
  `Open,High,Low,Close,Volume,Dividends,Stock Splits` — **no date column**. A dated price must trace
  to a raw payload or another dated source. Never infer the date from row position.

---

## 7. Financial semantics

**GAAP and adjusted stay on separate paths** wherever disclosures require: interest and other
income, tax expense and tax rate, net income, diluted shares, and EPS. Reconcile only through
disclosed or explicitly assumed bridge items.

**Annual aggregation needs a per-metric convention**, not just flow-vs-stock:

| Class | Rule |
|---|---|
| Summed flow | sum the four fiscal quarters, only when all four are present |
| Fiscal-period-end balance | take the year-end stock |
| Period average / published denominator | use the stated convention, not a quarter average |
| Recomputed ratio or margin | recompute from annual numerator and denominator |
| Recomputed per-share value | recompute from annual NI and the stated share convention |

**Consensus bridge** must specify accounting basis, source and as-of metadata, the ordering of
revenue and margin effects, below-the-line decomposition, and an explicit **residual row so the
bridge always sums**.

**Scope the generic spine to non-financial operating companies.** Banks, insurers and REITs must
fail closed or use a separate profile rather than being forced into an EBIT/EPS/FCF template.

---

## 8. Interfaces to define before implementation

Without these, an agent reads thousands of lines of library source and the token saving evaporates.
Write `references/interfaces.md` containing:

- the `model_spec.json` schema;
- the `fact_map.json` schema;
- the `drivers.csv` schema, including the approval manifest;
- the `model_<TICKER>.py` company-module contract;
- the `actuals.csv` / `benchmarks.csv` canonical facts and lineage schemas;
- the public entry points of each `scripts/` module (§5);
- the structured locator grammar and the transform registry (below); and
- one worked example of each, taken from VRT.

Gate 1 keeps its **2–3 checkable success examples** — approval is of a blueprint with concrete
expectations, not of an undefined JSON artifact.

### Transform registry — closed set, seeded here

No transform outside this list may appear in a `fact_map.json`. Adding one is a deliberate change to
the registry and its tests, never an inline lambda.

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
| `segment_axis_filter` | Select one dimension member from a segmented table |

Every transform must be expressible as a **visible Excel formula** in the workbook (§6). A transform
that can only be done in Python is a signal the metric is mis-mapped.

---

## 9. Driver and approval semantics

- **Keep the 5–10 primary-driver discipline, but do not cap total forecast inputs.** VRT has 9
  primary drivers and 17 base forecast metrics. Supporting assumptions (tax, shares, interest,
  capex, cash conversion, operating adjustments) stay visible inputs — never hidden in formulas or
  hardcodes.
- **Approval covers a hash or immutable manifest** of the approved periods and values. Row-level
  metadata must not silently authorise a newly added quarter during rollover. Any new or changed
  quarter invalidates approval until Gate 2 completes again.
- `status=proposed` never activates a forecast. Partial approval activates nothing.

---

## 10. Import list from company-model

Bring across — **rules and proven code, not re-imagined equivalents**:

1. Availability matrix (12 quarters × metric) before forecasting; unavailable marked, never zero.
2. YTD de-accumulation; `Q4 = FY − 9M`; no Q4 filing exists; cross-check against the release.
3. Annual conventions per §7, with published annual figures kept visible as a cross-check.
4. Missing ≠ zero, with guarded formulas `IF(x="","",…)`.
5. Dimension-axis filtering for segment tables; match segment labels on a stable token.
6. GAAP/adjusted separation; adjusted measures from the 8-K cell dump, not XBRL; never synthesise an
   unsupported adjustment bridge.
7. Benchmark register keeping source, publication date, period, units, basis, analyst count and
   range distinct from the mean.
8. Verified dated price, subject to the §6 store defect.
9. Restatement change log (`prior_value`, `change_reason`).
10. Quarter-rollover exercise as a **release-only** test.

Extract the **working implementations** from the pilots where they exist — key-based references,
evidence transforms, style helpers, cell-level hardcode checks, driver blocks, override
preservation — rather than deleting them and recreating equivalents.

**Do not import:** 13 fixed tabs · fixed column letters · `data-map.csv` · the 10,533-cell `Sources`
worksheet duplicating `sources.csv` · per-driver-quarter approval rows · the reconcile/verify/check
split · 20 routine renders · the two-workbook pre-approval build · 5× source reparse · `verify.py`
run twice · `panel.py` / `compare.py` · the 681-character frontmatter description · the undocumented
five-reviewer subagent phase.

---

## 11. Where this plan disagrees with the review

1. **`overrides.py` "cannot be ported literally" is too strong.** Sheet names are already default
   *parameters* — `sheet: str = "Assumptions"`, `outlook_sheet: str = "Outlook"`, and the payload
   reads `payload.get("outlook_sheet", …)`. Passing `Drivers` / `InvestmentView` works today. The
   real work is updating defaults, the module docstring and the 420-line test suite — a
   reconciliation, not a rewrite. Treat it as a configuration change with test updates.
2. **"Four independent DeepSeek Flash reviews converged" is weak evidence of priority.** Four
   samples from one small model correlate heavily. It does not weaken the findings, because the
   load-bearing ones (§6 evidence contract, §5 Gate-2 persistence, §6 source boundary) were
   independently verified against the repo — but it does mean the review's *ordering* carries no
   authority. Items 5 and 9 of the review are hygiene; items 1, 2 and 7 are structural.
3. **The generic spine is defensible for its stated scope.** The review is right that `spine.py`
   should not be promoted before the second-company build. But revenue → EBIT → interest → tax →
   net income → EPS → FCF is accounting, not company strategy, for non-financial operating
   companies. Expect promotion to succeed there; expect segment and driver logic to stay company
   code permanently.

---

## 12. Contract changes to the skill

1. **Reverse one SPEC exclusion.** SPEC currently forbids "a formula DSL, database, generic model
   engine, or duplicated calculation graph". The intent was to prevent over-engineering; the result
   was 7,359 lines re-authored per company. Replace with: *no formula DSL, no database — a
   data-driven engine is required.* A metric-mapping table and a driver-row schema are
   configuration, not a DSL.
2. **Add data acquisition.** `pull-financial-data` is absent from this skill's contract today
   ("the user's supplied files are the model evidence… do not fetch replacement model data"), which
   outsources the slowest step to the user. New contract: snapshot by default, user files override
   when indicated; `--index` → `--cache-only` → **ask before any live pull** → `--ceiling` →
   `--export-csv` / `--export-views`. A user-supplied override must be normalized into the same
   canonical evidence and lineage schemas through a declared locator adapter; arbitrary PDF/XLSX
   parsing is not a hidden responsibility of the generic reader.
3. **Add `references/evidence-rules.md`** carrying §10's ten conventions. Rules, not code.
4. **Add `references/interfaces.md`** per §8.

---

## 13. Workflow changes to `SKILL.md`

Seven steps and both gates stay. What changes inside them:

- **Step 2 (interview)** — read the evidence actually held (8-K exhibits, held transcripts,
  statement tables; 10-K only if supplied or explicitly fetched), draft the 5–10 primary drivers
  with reasoning, then confirm in **one** `AskUserQuestion` batch. Open questions only where
  evidence is genuinely absent: variant perception, which risks matter.
- **Step 3 (Gate 1)** — approve `model_spec.json` **plus 2–3 checkable success examples**.
- **Steps 4–6** — freeze the evidence layer to `evidence/*.csv` **before** Gate 2 and rebuild from
  those artifacts after approval. **Build the workbook once, after Gate 2.** Present the reconciled
  actuals/evidence artifact for review before it, not a second workbook.
- **Step 7 (validate)** — `check --fast` in the iteration loop; `check --full` on evidence
  create/refresh and at release. Default renders: `InvestmentView`, drivers, operating model,
  scenarios, checks. Native Excel gate stays opt-in and is known-flaky.

### Docs hygiene

**Done in Stage 0.** `SPEC.md` and `HANDOFF.md` are deleted; their unique content moved per the §18
ownership table. `SKILL.md` carries a description with real trigger vocabulary, and `AGENTS.md` is
maintainer notes plus the ownership map. The skill stays model-invoked.

Still outstanding: sheet renames (`Outlook`→`InvestmentView`, `Assumptions`→`Drivers`,
`Sources & Checks`→`Checks`) must land consistently across `SKILL.md`, `references/`, helper
defaults and tests. Do this in Stage 3, with the atomic runtime switch — not before, or the live
contract will name sheets the v1 builder does not produce.

---

## 14. Model-content upgrades

Neither existing model has these; both are asked for in `Building a model 101.md`:

- **Consensus bridge** on `InvestmentView`, with the residual row required by §7.
- **Incremental margin row** under each segment (ΔOP / ΔRevenue) — the analysis the note's worked
  example is built on.
- **Organic / acquisition / FX revenue bridge** where disclosure supports it.
- **Evidence table beside each assumption**: assumption | supporting evidence | what would falsify.
- **Business-event scenarios** ("shipments slip one quarter"), kept distinct from ±x% sensitivities.
- **Key-based references throughout.** Engine and company-formula APIs accept metric keys, never
  row numbers. Cross-sheet Excel formulas emit workbook defined names or structured table
  references, not resolved A1 addresses. The v1 workbook links positionally
  (`Earnings!B6 = ='SourceData'!$C$35`) into a 528-row sheet; any reorder corrupts it silently.

---

## 15. Staged sequence

| Stage | Work | Exit |
|---|---|---|
| **0** | Correct stale status/baseline docs; delete `PROPOSAL-V2.md`; name the source of truth for each contract. Do **not** change the active `SKILL.md` execution contract to reference v2 scripts yet | Docs describe the current executable v1 accurately |
| **1** | Benchmark a current VRT `build.py` and `check.py --fast`; record iterations and seconds each | Numbers on record |
| **2** | Write `references/interfaces.md`; build the evidence layer: dataset manifest, `fact_map.json` schema, transform registry, `actuals.csv` / `benchmarks.csv` / `availability.md`, approval manifest | Every populated V2 actual or benchmark has frozen snapshot/raw-payload lineage and every unavailable fact has a visible reason; evidence checks pass. The v1 input comparison is a diagnostic ledger, not a release gate: it may identify a V2 mapping gap or an unsupported v1 placeholder, but never authorizes copying an unsupported value. |
| **3** | Extract proven plumbing from the pilots into `scripts/` — grid, references, style, checks, CLI, overrides — then atomically update `SKILL.md` and its runtime references to v2 | VRT rebuilds through the extracted core; the active skill points only to files that exist; the core model has source-backed actuals, controlled forecast activation, regional-to-consolidated earnings/FCF/valuation propagation, checks, and rollover proof. |
| **4** | **Second-company proof: build AVGO** (already in the store). If it requires a core change, return to Stage 3, rebuild VRT and retry AVGO | Final AVGO pass requires zero further infrastructure changes |
| **5** | Rollover proof: update VRT for a new quarter; preserve only valid overrides and narrative; invalidate changed approvals; produce the estimate-change bridge | Rollover clean |
| **6** | **Deprecate** `company-model` (redirect, invocation off). Delete only after real usage confirms nothing unique remains | — |

Sparse-disclosure acceptance needs either a real second company exhibiting it or a deliberate
fixture. VRT alone cannot demonstrate every disclosure pattern.

---

## 16. Acceptance

1. `python3 -m unittest discover home/skills/equity-modelling/tests` — grid and annual conventions,
   YTD de-accumulation, `Q4 = FY − 9M`, key-based refs, driver activation, approval-manifest
   invalidation, hardcode scan, blank propagation, plus the reconciled override tests. No Excel
   required.
2. **Source-backed VRT core**, defined so it can fail: every populated V2 actual and benchmark has
   frozen lineage; unavailable facts stay visibly unavailable with a reason; V2 never copies a V1
   value merely because it existed there. The V1 comparison remains a diagnostic ledger for finding
   missing mappings and regressions, not a release-parity requirement. Core accounting identities
   for the V2 model must hold.
3. **No positional cross-sheet references survive**; engine APIs resolve by key and emitted
   cross-sheet formulas use Excel defined names or structured table references, never raw A1 links.
4. Controlled-driver test: move Americas organic growth; revenue, EBIT, EPS, FCF and implied value
   move; actuals, guidance and consensus do not.
5. `asp workbook recalculate` reports `0 unsupported` / `state: clean`; all `Checks` rows OK with a
   runtime-derived total.
6. Default renders inspected for clipping and blank formula results.
7. **AVGO's final pass requires zero further infrastructure changes** after any Stage 3↔4
   generalisation loop, and VRT still passes after every core change.
8. **Benchmark against Stage 1**, measuring wall-clock, authored lines and bytes, rebuild
   iterations, and subprocess count. Do not optimise for an artificial "one process" claim —
   recalculation still needs an external engine. The target is that assumption-only iterations stop
   touching raw filings.

### Acceptance patterns (carried from the retired `SPEC.md`)

All three must pass before Stage 6.

1. **Operationally disclosed company** — the interview selects unit and price/mix drivers, segment
   forecasts drive consolidated earnings, YoY and annual views reconcile, and consensus remains a
   comparison rather than an input. *Covered by VRT (Stage 3) and AVGO (Stage 4).*
2. **Sparse-disclosure company** — unavailable operational history stays visible, reasoned
   assumptions are clearly labelled and scenario-sensitive, and the model invents no sourced facts.
   *Needs a real company exhibiting it or a deliberate fixture; VRT alone cannot demonstrate it.*
3. **Earnings update** — a newly reported quarter replaces the forecast on the latest reported
   basis, designated overrides and investment-view text survive, estimate changes are explained, and
   a new dated workbook is produced without altering the prior version. *Covered by Stage 5.*

---

## 17. Out of scope

Mandatory three-statement integration · a DCF engine · sector driver templates · automatic web
ingestion · HTML dashboards · financial-sector business models in the generic spine. Web research
may challenge a number but never supplies one.

---

## 18. Implementation start

### Document ownership — settles Stage 0's "name the source of truth"

| File | Owns | Action |
|---|---|---|
| `V2_PLAN.md` | The v2 design, diagnosis and staged sequence | Live until Stage 6, then archive |
| `SKILL.md` | The **executable** workflow an agent follows at runtime | Keep describing v1 until Stage 3's atomic switch |
| `references/interfaces.md` | **New.** All schemas, entry points, locator grammar, transform registry | Create in Stage 2 |
| `references/evidence-rules.md` | **New.** §10's ten conventions, as rules | Create in Stage 2 |
| `references/model-rules.md` | Workbook contract only: sheets, periods, presentation, hardcode policy, decision integrity | **Shrink.** Move evidence rules out to `evidence-rules.md`, schemas out to `interfaces.md`. No rule lives in two files |
| `references/update-model.md` | The rollover branch | Rewrite in Stage 5 against the shipped `overrides.py` |
| `AGENTS.md` | Maintainer notes and the ownership map | Done in Stage 0 |
| ~~`SPEC.md`~~ | — | **Deleted in Stage 0.** Principles, defaults table and web-challenge policy → `SKILL.md`; acceptance patterns → §16; exclusions → §17; workflow copy was duplicated drift |
| ~~`HANDOFF.md`~~ | — | **Deleted in Stage 0.** Every claim was false; its locked decisions all live in `SKILL.md` |

Rule: a contract appears in exactly one file. Everything else links to it.

### First three tasks, in order

**Task 1 — Stage 0, docs only. ✅ DONE.** `SPEC.md` and `HANDOFF.md` deleted after folding their
unique content out; `SKILL.md` frontmatter rewritten with trigger vocabulary and the pilot framing
removed; `AGENTS.md` rewritten as maintainer notes plus the ownership map. The v1 execution contract
is unchanged — no reference to scripts that do not exist. Verified: `grep -rn "not been
implemented\|design skeleton\|Pilot-only\|implementation has not started"` returns nothing.

**Task 2 — Stage 1, benchmark before optimising.** Time a current VRT `build.py` and
`check.py --fast` from `~/Desktop/equity-models/VRT/`. Record seconds per run, wall-clock, and the
iteration counts already known (`build.py` ×37, `check.py` ×44). Write the numbers into this file's
§2. No behaviour change. This is the only baseline the §16.8 benchmark can be measured against —
taking it after refactoring is worthless.

**Task 3 — Stage 2, interfaces first, then evidence.** Write `references/interfaces.md` from §8 and
the transform registry before any code. Then implement `scripts/evidence.py` plus VRT's
`fact_map.json` and freeze `evidence/actuals.csv`, `benchmarks.csv`, `availability.md`. Exit on the
Stage 2 criterion in §15 — a row-level comparison against v1's 507 historical inputs, not a
visual scan.

### Known unknowns to resolve during Stage 2, not before

- **Dated price.** The Yahoo CSV view has no date column (§6). Decide: fix the export upstream, read
  the raw payload, or require a user-supplied dated price. Blocks `Valuation`.
- **10-K/10-Q text.** Not in the store. Decide whether Step 2's business read is limited to 8-K
  exhibits plus the two held transcripts, or whether documents get fetched and frozen.
- **`historical_inputs.csv` → `actuals.csv` schema mapping.** v1's 507 rows use their own column
  names; the canonical schema is new. Write the mapping down before comparing.
- **Segment label stability.** §10.5 requires matching on a stable token. Confirm VRT's segment
  labels are stable across all 12 quarters before relying on it.

### Immutable parity baseline

v1's VRT project is the measuring stick for Stages 2–4 and is **not** under version control, so it
is protected outside the working tree:

```text
~/Desktop/equity-models/VRT_v1_baseline/        chflags uchg, directory + contents
~/Desktop/equity-models/VRT_v1_baseline.tar.gz  chflags uchg, sha256 beside it
```

Workbook sha256 `bbb6389b…98487cd`. Recover with:

```sh
chflags -R nouchg VRT_v1_baseline && rm -rf VRT_v1_baseline && tar -xzf VRT_v1_baseline.tar.gz
```

`chmod -R a-w` is **not** sufficient — it blocks content writes but still permits `rm`. Verified.

Never run `build.py --force` in `~/Desktop/equity-models/VRT/`. Its overwrite guard
(`build.py:751`) is the only thing protecting the live copy, and `--force` defeats it. Benchmark
and rebuild from a scratch copy.

### Resuming across sessions

Stage 2 is larger than one comfortable context. Maintain `V2_PROGRESS.md` in this folder — append
only, newest last:

```markdown
## <date> — Stage N, <task>
Done: …            (what is finished and verified, with the command that proves it)
In flight: …       (what is half-done, and where the edge is)
Blocked: …         (what stopped, and what decision is needed)
Next: …            (the single next action)
```

Write an entry before context runs low, not after. A session that ends without one has to be
re-derived from scratch. Delete the file at Stage 6 with `V2_PLAN.md`.

### Stop conditions

Halt and report rather than working around:

- Stage 2 divergences that are not explainable by a declared transform — that is a mis-mapped
  metric, not a tolerance problem.
- Any need to write a Python-computed value into a cell where a formula belongs.
- Stage 4 requiring a third or later core change — the invariant boundary was wrong, and §11.3
  should be revisited rather than patched around.
