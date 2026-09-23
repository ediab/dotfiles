---
name: equity-modelling
description: Build or update a driver-based public-equity earnings model in Excel — operating drivers, segment revenue, margins, EBIT, EPS, cash flow, scenarios, consensus variance and multiples-based valuation, with source provenance and two approval gates. Use when asked to model a company, forecast earnings or EPS, build or refresh an equity/earnings model, compare estimates against guidance or consensus, or roll a model forward after results.
---

# Equity modelling

Build or update one editable, formula-driven public-equity earnings model.

Read `references/model-rules.md` before building. Read `references/interfaces.md` for the artifact
schemas and locator grammar, and `references/evidence-rules.md` for the evidence conventions, before
building the evidence layer. For an earnings update, also read `references/update-model.md` before
changing anything. Use the `excel` skill for workbook construction, recalculation, and rendering
(step 7).

The model answers: **what do I believe that differs from consensus, what evidence supports it, and
how much does it matter?** It is not a universal planning model, a mandatory three-statement model,
a DCF engine, or a report-writing system.

## Principles

1. **Model the business, not a template.** Discover the company's segments and economic drivers
   during the run.
2. **Forecast edge first.** The model must explain why its estimates differ from guidance or
   consensus.
3. **Excel stays legible.** Forecast outputs are visible formulas driven by editable inputs.
4. **Python supplies reproducibility.** Python handles evidence, construction, updates, and checks.
5. **Web research challenges; it does not supply.** A web-found number cannot enter the model until
   the user supplies it.
6. **Machine checks can be exhaustive; the human workflow stays short.**
7. **Gaps stay visible.** Missing evidence is never silently converted to zero or false precision.

## Boundaries

- The evidence boundary is explicit and recorded. Web research may challenge it, but a web-found
  number stays outside the workbook until the user supplies it.
- Discover five to ten company-specific primary drivers during the run. Do not substitute a sector
  template. Supporting inputs (tax, shares, interest, capex, cash conversion) are additional visible
  inputs, not hidden formulas.
- Forecast eight quarters. Derive annual periods on the same model sheets.
- Build a full earnings model plus thesis-relevant cash-flow and balance-sheet items. Expand to
  three statements only when liquidity, leverage, working capital, or balance-sheet risk requires it.
- Keep guidance and consensus as benchmarks. Keep business-event scenarios separate from mechanical
  sensitivities.
- Write every delivery to a new dated path. A prior workbook is immutable.

## Defaults

| Decision | Default |
|---|---|
| Interview starting point | Business economics |
| Primary drivers | Five to ten |
| Revenue method | Units × price/mix when operational evidence supports it; otherwise explicit segment growth |
| Margin method | Driver bridge: volume, price/mix, mix, productivity, inflation, FX, other material effects |
| Special effects | Organic growth, acquisitions/disposals and FX shown separately when supported |
| Missing driver | Visible analyst assumption with rationale, uncertainty and scenario sensitivity |
| Forecast horizon | Eight quarters with derived annual periods |
| Statement depth | Full earnings model plus thesis-relevant cash flow and balance-sheet items |
| Consensus | Benchmark only, never a forecast input |
| Scenarios | Coherent business-event cases plus mechanical sensitivities |
| Valuation | Relevant trading multiples plus reverse expectations; DCF only when useful |
| Companion output | One-page investment view |
| Assumption approval | One concise package |
| Human gates | Blueprint approval, then forecast-assumption approval |
| Versioning | Immutable dated files |
| Restatements | Latest reported basis with a change log; prior versions preserved |

## Prepared project and runtime

The build/check runtime is `scripts/cli.py`, and it operates on a *prepared project* directory that
already holds frozen artifacts. It never fetches, parses, or ingests raw sources.

```text
<TICKER>/
├── model_spec.json              # company, periods, workbook sheets/filename, price, source manifest
├── fact_map.json                # immutable source-locator manifest required by the generic build
├── evidence/actuals.csv         # frozen canonical facts — one row per (metric, period), with lineage
├── evidence/benchmarks.csv      # optional guidance/consensus comparisons; dated price may be in model_spec.json
├── drivers.csv                  # one row per driver; one column per forecast quarter; status proposed|approved
├── drivers.approval.json        # required only when a driver is approved; hashes its (driver, period, value) triples
├── model_<TICKER>.py            # exactly one module exposing company_module.workbook_rows(...)
└── <TICKER>_Model_<date>.xlsx   # workbook named by model_spec.json workbook.filename
```

The artifact schemas are in `references/interfaces.md`. `build` reads `model_spec.json`,
`evidence/actuals.csv`, `drivers.csv`, `drivers.approval.json` (when present), and the company
module. `rollover` reads a prior and a new prepared project but never mutates either. Run from this
skill directory:

```sh
python3 scripts/cli.py <project_dir> build          # writes the workbook once; refuses to overwrite an existing delivery
python3 scripts/cli.py <project_dir> check          # shared structural checks
python3 scripts/cli.py <project_dir> check --full   # structural checks plus cached formula-error and cross-sheet checks
python3 scripts/cli.py <new_project> rollover --prior-project <old_project> --output-project <rolled_project> [--report <report.json>]
```

`check` is structural only; company accounting identities live in the company module. `rollover`
copies compatible driver values into a new project by stable `driver_id`, resets every row to
`proposed`, and omits approval so outputs remain blank pending a new Gate 2. The CLI does not ingest
raw sources, render, or recalculate. Recalculation, rendering, and
the native Excel gate are external validation steps run through the `excel` skill (step 7).

## Workflow

### 1. Inventory the source pack

Classify the run as a new model or an update. Record the company, ticker, fiscal calendar, model
as-of date, intended output directory, supplied files, periods, units, accounting basis, segment
disclosures, guidance, consensus, price evidence, conflicts, and missing items. Select one
exclusive evidence mode before inventory. For pull-data-only runs, inspect `pull-financial-data`'s
zero-network held index/cache-only report and pin only held snapshots and immutable originals;
a first live acquisition or refresh requires explicit user consent. For supplied-files-only runs,
inventory and hash only the designated documents, without consulting the pull store or network.
Treat missing coverage as a gap; never cite rewritable exports (including `8k_cells.csv`) as originals.
The current build accepts pull-data-only packs; supplied-files-only preparation is not yet implemented.

For an update, preflight the existing workbook and follow `references/update-model.md`.

**Done when:** the evidence boundary, fiscal periods, usable sources, gaps, conflicts, and a fresh
output path are explicit.

### 2. Interview the business

Read the evidence actually held first — earnings-release exhibits, held transcripts, statement
tables — then draft the five to ten primary drivers with your reasoning and confirm them in **one**
batch of questions. Ask open questions only where evidence is genuinely absent: variant perception,
which risks matter, decision-relevant valuation metrics.

Establish business economics; reporting and economic segments; volume, price, mix, capacity,
utilization, backlog or other operating drivers; cost and margin structure; cash conversion and
capital intensity; thesis, risks and falsifiers.

Use units × price/mix only where operating evidence supports it; otherwise use explicit segment
growth. Treat any unsupported driver as a visible analyst assumption with rationale, uncertainty,
and scenario treatment.

**Done when:** the driver set, segment structure, profit bridge, statement depth, scenario events,
and valuation lenses are specific enough to build.

### 3. Propose the blueprint — Gate 1

Present one concise blueprint: sheets, period grid, segments, driver equations, profit bridge, cash
and balance-sheet scope, guidance/consensus comparisons, scenarios, sensitivities, valuation, and
evidence gaps. Include 2–3 checkable success examples for this company. Stop for batch approval
before constructing the model.

**Done when:** the user approves or edits the blueprint and success examples.

### 4. Build the historical and evidence layer

Parse the supplied evidence into canonical historical values and a source register; each source
value enters the workbook once. Record source file, hash, locator, period, units, basis, and
transformation. Produce an availability matrix before promising complete history. Use the latest
reported historical basis and log restatements. Keep missing values blank with a reason.

Freeze the canonical evidence to disk before Gate 2 so the forecast layer can be built from those
artifacts afterwards.

**Done when:** displayed actuals reconcile to the source pack, each canonical value has provenance,
and every missing or conflicting item remains visible.

### 5. Propose forecast assumptions — Gate 2

Present one compact package covering all primary drivers across eight forecast quarters: values,
progression, rationale, evidence or analyst basis, uncertainty, guidance comparison, consensus
comparison, and scenario treatment. Keep the proposals inactive and forecast outputs blank. Stop for
batch approval.

After approval, record who approved the package, the date, and an approval id. Approval covers an
immutable manifest of the approved periods and values — a later added or changed quarter invalidates
it. User edits become explicit approved inputs; they do not alter guidance or consensus.

**Done when:** every material driver is approved or rejected, and no forecast activates on partial
approval.

### 6. Build the forecast, scenarios, and decision view

Build the workbook once, after Gate 2, from the frozen evidence plus the approved inputs. Forecast
segments, earnings, relevant cash and balance-sheet items, scenario cases, sensitivities, and
valuation. Show why the house view differs from guidance and consensus. Create the one-page
investment view.

Use coherent business-event cases that change groups of assumptions. Put one-variable mechanical
sensitivities in a separate block. Leave unavailable outputs blank instead of inventing precision.

**Done when:** every forecast output traces to an approved driver or visible formula, annuals derive
from quarters, and the decision view states thesis, variant view, catalysts, risks, falsifiers, and
valuation basis.

### 7. Validate and deliver

Run the prepared project's checks with `python3 scripts/cli.py <project_dir> check` (add `--full`
for the recalculated-formula and cross-sheet checks), then the `excel` skill's prompt-free ASP
recalculation. Recalculation, rendering, and the native Excel gate are external validation steps
outside the CLI. Skip the native Excel gate in the standard run — it is slow, needs Excel closed,
and is known to be flaky. Run it only when the workbook uses non-vanilla formulas (dynamic arrays,
LAMBDA, newer functions) or the user asks. Inspect the routine renders; render the full workbook
only when release risk warrants it.

Validation must cover source reconciliation, provenance coverage, unexpected hardcodes, formula
errors, core identities, GAAP/adjusted separation, annual conventions, missing-value propagation,
and one controlled driver change whose expected revenue, earnings, cash, and valuation effects move
while unrelated actuals and benchmarks do not.

Deliver the fresh dated workbook and state the approved assumptions, estimate differences, evidence
gaps, unresolved conflicts, and checks that could not run.

**Done when:** reconciliation and identities pass, no unexplained constants or new formula errors
remain, behavioural checks pass, critical renders are readable, and the prior workbook or source
pack remains unchanged.

## Web challenge policy

1. Search only to test, contextualize, or contradict supplied information.
2. Prefer filings and company IR; use secondary reporting only to locate primary evidence.
3. Fetch and inspect the underlying source rather than relying on a search snippet.
4. Record the challenged model value, exact quote, primary-source URL, publication date, accounting
   basis, and materiality — the record format is in `references/model-rules.md`.
5. Alert the user; do not alter the workbook.
6. A web-found number becomes eligible model evidence only after the user supplies it into the
   source pack.

Run the smoke test in `tests/web-challenge-smoke.md` when changing research behaviour.
