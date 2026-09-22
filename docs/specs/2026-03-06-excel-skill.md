# Brief: General Excel skill for Pi

- Date: 2026-03-06
- Status: agreed brainstorming brief; not an implementation plan

## Idea and purpose

Create a global Pi skill for high-quality creation and safe targeted editing of Excel `.xlsx` workbooks. It should produce editable workbooks with formulas, professional formatting, tables or charts when requested, and verified Excel calculation.

## Who uses it and what they do

A Pi user asks to create a workbook or update a bounded, known region of an existing workbook.

## Smallest useful version

Use a working-copy workflow for existing workbooks: inspect the relevant layout and conventions, make a targeted change, recalculate in native Microsoft Excel, validate formula errors and selected outputs, then report intended and unexpected changes.

Creation is also in scope: build polished `.xlsx` workbooks with formulas, tables, and charts when requested, then validate them in Excel. It can create from a written specification or adapt a supplied template; use a template when available to retain established layout and formula conventions.

## Important decisions

- Microsoft Excel is required for final recalculation and compatibility validation.
- Existing-workbook updates may make planned structural extensions (for example, forecast columns, schedule rows, and source ranges) after a preflight impact check and final validation. Arbitrary reshaping and deletions remain excluded.
- `agent-spreadsheet` is preferred for normal workbook inspection and editing; use its installed capabilities rather than assuming a fixed CLI surface.
- `openpyxl` is a narrow fallback for operations the primary tool cannot perform. Never save a `data_only=True` workbook.
- Incorporate the useful QA guidance from Anthropic's XLSX skill: formulas for derived values, explicit assumptions/sources in newly created models, consistent formula patterns, targeted output checks, and matching existing-workbook conventions.
- Do not import LibreOffice-specific formula restrictions because Excel is the calculation authority.
- The skill is standalone. It supplies general workbook mechanics, layout, formatting, and validation; any domain-specific financial assumptions or valuation methodology still come from the user's request.

## Explicit exclusions

V1 does not actively edit `.xlsm`, `.xls`, `.xlsb`, or externally linked workbooks. It excludes arbitrary reshaping or deletion of complex existing layouts, pivot tables, Power Query, and VBA manipulation.

## Concrete success examples

1. Create a readable financial model with formulas, input areas, a table/chart, and Excel-verified totals.
2. Extend an existing forecast row or add forecast columns by five periods, retaining formula patterns and nearby styles, with no unexplained new formula errors or unintended changes.

## Next step

Produce a standalone implementation plan that checks local Excel tooling before installing dependencies or creating the skill.
