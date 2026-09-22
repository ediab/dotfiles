# Workbook quality and formatting rules

Deferred reference — load only for presentation-heavy or financial workbooks. Existing workbook conventions always override everything here.

Adapted from the pinned OpenAI spreadsheet skills (see `../LICENSE.openai-skills.txt` and `../LICENSE.openai-role-specific-plugins.txt`, provenance in `../ATTRIBUTION.md`); independently expressed, no Anthropic material.

## Layout and hierarchy

- One idea per section; consistent title → subtitle → table → notes flow, top to bottom.
- Deliberate whitespace: blank rows/columns between logical blocks rather than dense packing.
- Column widths fitted to content; wrap long text instead of overflowing into neighbors.
- Headers distinct from data (bold + fill at most); avoid competing emphasis — if everything is highlighted, nothing is.
- Freeze header rows/columns on long tables.

## Number and date formats

- Semantic formats: currency with the right symbol and decimals, percentages as `0.0%`, dates as real date formats (never text), thousands separators for counts over 999.
- Consistent decimals within a column; inconsistent precision reads as an error.
- Negative numbers: parentheses or minus, one convention per workbook.

## Color and borders

- Restrained palette: 1–2 accent colors, neutral fills for headers, white background.
- Borders only where they separate meaning (table edges, total lines); not grids everywhere.
- Financial-model color conventions (apply when the workbook is financial): inputs in one distinct color/style (commonly blue text on light fill), formulas in black, links to other sheets in green, external links in red — follow the workbook's own scheme if one exists.
- Mark assumption blocks clearly: a bordered, labeled input area separate from calculations.

## Tables, charts, formulas

- Excel Tables (`openpyxl.worksheet.table.Table`) for data ranges that grow; charts reference table ranges where possible.
- Charts: title, labeled axes, legend only when multiple series, one chart per message. Native Excel charts via `openpyxl.chart`, never images.
- Formulas: real formulas for all derived values; no hard-coded computed constants. Prefer range references over chains of single-cell hops; use named ranges for repeated key inputs.
- Guard divisions: `IFERROR` only where a controlled fallback is intended — do not blanket-wrap everything and hide real breakage.
- Sources: add a cell comment or a Sources section for non-obvious data — source name, URL, retrieved date.

## Check sheets (complex models)

- A dedicated Checks sheet with balance/tie-out identities (`assets == liabilities + equity`, forecast totals vs. summary, etc.).
- Each check is a real formula evaluating to TRUE/0; a roll-up cell aggregates them; the gate `--target` should capture the roll-up.

## Formula hazards

- Watch for: wrong-range references after row insertion (mitigated by Excel Tables/structured refs), mixed absolute/relative references dragged incorrectly, volatile functions (OFFSET, INDIRECT, TODAY) used where stable alternatives exist, hard-coded numbers buried inside formulas.
- After edits, `asp analyze scan-volatiles` and `asp verify proof --targets` on check cells catch most of these.
