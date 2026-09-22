---
name: excel
description: Create, edit, inspect, recalculate, or validate Excel .xlsx workbooks — polished new workbooks with openpyxl, bounded safe edits of existing workbooks with asp (agent-spreadsheet), and native Microsoft Excel validation/recalculation with a built-in gate script. Use when an .xlsx file is the requested input or output. Do not use for CSV/TSV cleanup, Google Sheets, databases, or code deliverables that merely contain tabular data.
---

# Excel workbooks

Three layers:

1. **Authoring/editing** — `openpyxl` for new workbooks; `asp` (`agent-spreadsheet`) for inspecting, preflighting, and normally editing existing workbooks.
2. **Quality rules** — deferred reference: `references/quality-and-formatting.md`. Load it for presentation-heavy or financial workbooks; skip it for read-only or simple tasks.
3. **Native validation** — `scripts/excel_gate.py` opens a working copy in Microsoft Excel, rebuilds all formulas, saves cached values, scans errors (per-cell vs. baseline), checks the package inventory, and renders PNGs. Run it only via `uv run --script` (it self-installs its pinned Python deps; plain `python3` will fail).

Scope limits: `.xlsx` only. Never write `.xlsm`, `.xls`, `.xlsb`. Never edit workbooks containing VBA, external links, Power Query/connections, pivot-table internals, or slicers — detect and refuse before any write (the gate's package inventory and `asp read workbook` reveal these). The user supplies all domain assumptions; you supply structure, formulas, and formatting.

## Versions tested

- `asp` 0.16.0 (`npm i -g agent-spreadsheet@0.16.0`) — consult `asp operations`, `asp schema <cmd>`, and `asp example <cmd>` when a payload is uncertain; do not trust memorized flags.
- Gate script: `uv run --script` pins xlwings 0.32.2 / openpyxl 3.1.5 in its PEP 723 header. Requires Microsoft Excel installed; the gate waits up to 120 s for the macOS Apple Events consent dialog. macOS attributes the consent to the nearest app-bundle ancestor of the run (typically the terminal app — Ghostty is Developer ID-signed, so its grant survives app upgrades); a re-prompt is expected only when that hosting app's identity changes. Ask the user to click Allow instead of retrying in a loop. A refused grant is reported as an Apple Events denial, not a missing permission.
- Charts cannot be exported as standalone PNGs by automation on macOS (xlwings `Chart.to_png` unimplemented); the gate never accepts `--chart`. Review charts via `--render`/`--render-sheet` PNGs that cover the chart area.

## Workflow

### 1. Classify

Read-only question, new workbook, or edit of an existing one? Confirm the deliverable is `.xlsx` and pick a non-destructive output path.

- Read-only: use `asp read`/`asp analyze` (or openpyxl read-only). No changed copy unless the user asks.
- New workbook: `openpyxl`, save once to the final path, then gate.
- Edit: **originals are immutable by default.** Copy to `<stem>_updated.xlsx` (or the user's requested path) before any mutation; the source must remain byte-for-byte unchanged. Never write `.xlsm`/`.xls`/`.xlsb` outputs.

Done when: classification and output path are settled.

### 2. Preflight (edits and questions)

`asp read workbook <file>` for metadata (macros, tables, defined names); `asp read sheets`, `asp read overview --sheet <name>`, `asp analyze formula-map`, `asp analyze formula-trace`, `asp read names` as needed. Understand nearby formulas/styles, named ranges, tables, and any check/summary outputs the edit could affect. Detect disallowed features (VBA, external links, connections, pivots, slicers) and refuse with an explanation if found.

Done when: you can describe the affected area and every dependency that touches it.

### 3. Plan bounded changes

Define the intended ranges and the mechanically dependent ranges (formulas referencing edited cells, totals, check cells, table/chart ranges, print areas). For structural edits (insert/delete rows/columns/bands), run `asp analyze ref-impact --ops @ops.json` first. Every write targets a separate output path or uses `--dry-run` first.

Done when: intended + dependent ranges are listed and a dry-run or output-copy path exists.

### 4. Build / edit

- New workbook: openpyxl. Real formulas for every derived value — never paste computed constants where a formula belongs. Match requested tables/charts/validation/conditional formats. Save once.
- Existing workbook: `asp write cells --output <path>` (or `--in-place` only on the working copy), `asp write append`, `asp write clone-template-row`/`clone-row-band`, `asp write formulas`, `asp write batch`. Single-quote formulas containing `$`/parens, or use `--edits-file`. Extend formulas, styles, validation, conditional formatting, table ranges, totals, names, and check formulas only where dependency evidence from step 3 requires it. Existing conventions (number formats, colors, header styles) win over defaults.

Done when: the working copy holds the change with no computed-constant regressions.

### 5. Verify logic

- `asp verify diff <original> <modified>` — confirm the change is exactly the intended + dependent cells; investigate anything else.
- `asp verify proof <baseline> <current> --targets 'Summary!B10,Data!C2'` — target deltas, new/preexisting error provenance (targets are comma-separated in one `--targets` flag).
- Spot-check representative formulas and invariants against expected values.

Broad cached-value differences caused purely by Excel recalculation are acceptable when formulas/styles/structure stayed in scope.

Done when: diff is bounded and proof shows no new errors.

### 6. Excel gate + visual review

Prompt-free alternative: `asp workbook recalculate <file>` evaluates formulas with asp's internal engine and writes cached values — no Excel, no Apple Events, no consent prompt. Use it for routine validation when no human is present; spot-check for `0 unsupported` in its output (unsupported formulas are surfaced, not silently wrong). The native gate below remains the Excel-native proof and the only path for renders backed by Excel's own recalculation.

Run the gate on the working copy:

```sh
uv run --script <skill>/scripts/excel_gate.py OUTPUT.xlsx \
  --baseline ORIGINAL.xlsx \
  --target 'Summary!B10' --target 'Data!C2' \
  --render-sheet 'Summary' --render 'Data!A1:H40' \
  --output-dir /tmp/excel-review
```

Rendering requirements: for a **new** workbook, pass one `--render-sheet` per created sheet (plus `--render` ranges covering every chart). For an **edit**, pass explicit `--render` ranges covering each changed area and any chart on affected sheets — `--render-sheet` derives its bounds from the pre-recalculation file and can clip content that recalculation extends.

The gate exits non-zero and prints a JSON report on: automation failure/timeout, new formula errors, lost package features, missing requested targets/renders. On failure the draft is left untouched. Timeout or error mentioning a stuck Excel instance → tell the user to close that Excel instance; never kill Excel processes. An error mentioning Apple Events → have the user click Allow on the consent dialog (or enable the host app under System Settings → Privacy & Security → Automation); `tccutil reset AppleEvents` clears a cached denial.

Then **actually inspect every PNG** (read the files): clipping, overlapping content, unreadable column widths, inconsistent styles, blank formula results, broken charts. Repair and re-run only the failed stage.

Formula-free workbooks still get the gate (open/save + renders) — skip only the formula-error expectation.

Done when: gate passes and PNGs are reviewed and clean.

### 7. Deliver

Report: output path; intended changes; dependent changes; unexpected diffs (target: zero); formula-error delta (new workbooks: zero; edits: zero new, inherited listed); selected recalculated outputs from `--target`; what the PNGs showed. State anything unverified.

## Read-only questions

`asp read values --sheet S --range A1:D20`, `asp read cells`, `asp read table`, `asp analyze find-value/find-formula`, `asp analyze formula-trace`. Answer without creating files.
