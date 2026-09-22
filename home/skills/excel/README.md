# excel

A Pi skill for working with Excel workbooks (`.xlsx`): creating new ones, editing existing ones safely, and answering questions about them.

## What it does

- **New workbooks** — builds them with openpyxl: editable inputs, real formulas for every derived value, tables, charts, validation, and formatting as requested.
- **Editing existing workbooks** — uses `agent-spreadsheet` (`asp`) to inspect, analyze impact, and apply bounded edits on a copy. The original file is never modified.
- **Answers without changes** — read-only questions never create a modified file.
- **Real Excel validation** — every deliverable is opened in Microsoft Excel by a built-in gate script: all formulas are recalculated, cached values are saved, results are scanned for errors (like `#REF!` or `#DIV/0!`), and key areas are rendered to PNG for visual review. The agent looks at those images and fixes anything that looks wrong before delivering.

## What it won't do

- Write `.xlsm`, `.xls`, or `.xlsb` files.
- Edit workbooks with VBA, external links, Power Query, or pivot-table internals — it detects these and stops with an explanation instead of silently flattening the file.
- Invent business assumptions. Structure, formulas, and formatting are the agent's job; the numbers behind them are yours.

## Requirements

- Microsoft Excel (macOS). The first run may ask for automation permission — approve it once.
- `asp` (agent-spreadsheet) and `uv`, installed automatically or on demand.

## Files

- `SKILL.md` — the workflow the agent follows (not written for humans).
- `references/quality-and-formatting.md` — formatting rules used for polished or financial workbooks.
- `scripts/excel_gate.py` — the native Excel validation gate.
- `tests/` — unit tests.

Adapted from pinned OpenAI spreadsheet-skill sources (licenses bundled in this folder); no Anthropic material is included. See `../ATTRIBUTION.md`.
