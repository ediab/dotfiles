# Investing workspace (pi-dotfiles)

Local Excel + memo toolset for **ad hoc company modeling assignments**: take a
supplied broker/company workbook, inspect it, propose bounded changes, obtain
approval, edit a *copy*, recalculate in native Excel, and write an investment
memo whose figures tie back to the saved workbook.

Everything runs against **supplied data only**. No financial data, consensus, or
prices are ever fetched. Missing inputs are requested or flagged, never
fabricated.

Plan and acceptance criteria: `docs/specs/2026-09-18-ad-hoc-modeling-and-pitch.md`.

## Layout

```text
workspaces/investing/
├── pyproject.toml          openpyxl pinned; no requests, no network client
├── scripts/
│   ├── excel_model.applescript   controlled Excel automation (writes/recalculation)
│   └── inspect_workbook.py       read-only OOXML inspection + workbook diff
├── references/             shared policy text cited by every skill
├── skills/                 the seven skill definitions
├── templates/              workspace AGENTS.md, HTML memo shell
├── tests/                  synthetic fixtures, feasibility tests, lint
└── licenses/               upstream license/notice copies
```

The skill definitions in `skills/` are registered **only** in the private
assignment workspace `~/Investing` (see `setup.sh`). They are deliberately
*not* in `home/skills/`, so `rebuild.sh` never copies them into the global
`~/.pi/agent/skills/` directory, and they are not part of VPS sync.

## Environment

```sh
cd workspaces/investing
python3 -m venv .venv
.venv/bin/python -m pip install -e .      # installs openpyxl==3.1.5
```

Tested interpreter: **CPython 3.10.13** (macOS, pyenv); `requires-python = ">=3.10"`.
Run scripts through the venv interpreter so the resolved environment, not a
machine-specific absolute path, decides the dependency set:

```sh
.venv/bin/python scripts/inspect_workbook.py inspect path/to/model.xlsx
```

`scripts/excel_model.applescript` is invoked with the system `osascript`; it has
no Python dependency.

## Unit 0 — Excel feasibility gate (verified facts)

These are the measured results of the feasibility gate, on disposable synthetic
workbooks under `tests/tmp/` (`tests/make_fixtures.py`). Ad-hoc claims invented
from memory were not accepted; every item below was executed.

Run the gate with:

```sh
.venv/bin/python tests/test_unit0_excel_roundtrip.py   # 44 checks
.venv/bin/python tests/test_applescript_scoping.py     # AppleScript name lint
```

### Environment

* Microsoft Excel 16.113 (`/Applications/Microsoft Excel.app`).
* macOS Automation permission for AppleEvents to Excel is **already granted** to
  the terminal process; no permission dialog appeared during the tests.
  If a future machine shows no dialog and calls fail, check
  System Settings → Privacy & Security → Automation.
* `osascript` reports AppleScript timeouts (`-1712`) when Excel is blocked; the
  helper wraps Excel calls in `with timeout of 600 seconds` where relevant.

### Capabilities that work (verified)

| Capability | Verified behaviour |
| --- | --- |
| Open a workbook without touching links | `open workbook workbook file name <path> update links do not update links read only false ignore read only recommended true add to mru false` |
| External links are *not* refreshed | Fixture with an `externalLink` part kept its cached `5100` after `calculate full`; the live value from the referenced workbook would have been `6525` |
| Read a cell | `formula of range`, `value of range`; error cells return `missing value` (flagged `iserror=true`) |
| Write a cell | `set formula of range` / `set value of range` through `edit`'s change list |
| Recalculate | `calculate full` (all open workbooks), `calculate` (dirty cells), `calculate full rebuild` |
| Save | `save workbook` — safe save, preserves the file's existing format |
| Close | `close workbook saving false`; settings restored even when a run fails |
| Settings snapshot/restore | `calculation`, `display alerts`, `ask to update links`, `automation security`; the restore is read back and reported (`match=true`) |
| Format/feature preservation | defined names, data validation, conditional formatting, chart, hidden sheet, comment, number formats, freeze panes, column widths, tab colour |

### Limits found — do not ignore

1. **`calculate <workbook>` is not supported.** The dictionary's `calculate`
   command takes a reference; passing a workbook raises `-50 Parameter error`.
   `calculate full` therefore recalculates *every* open workbook, which is why
   `recalc`/`edit` refuse to run while any unrelated workbook is open
   (`STATUS BLOCKED`). Work with Excel otherwise idle, or pass
   `allowOtherWorkbooks=yes` only with the user's explicit permission.
2. **AppleScript name collisions.** Inside `tell application "Microsoft Excel"`,
   an unqualified name that also exists in Excel's dictionary resolves to
   Excel's property. `kind` and `content` returned `missing value`; `ask`,
   `key`, `text`, `data`, `number` cannot be used as variables at all.
   `tests/test_applescript_scoping.py` checks every identifier mechanically.
   Allowed intentional collisions: `calculation`, `ask`.
3. **A split-application name still resolves to Excel.** Bare `tab` inside a
   `tell` block is Excel's own property, so the script carries the tab character
   in a script property (`TABCHAR`).
4. **`do shell script` rewrites line endings** unless invoked
   `without altering line endings`; the helper relies on `paragraphs` for
   splitting change/readback files.
5. **`text of range` (displayed text) comes back empty** under this automation
   path. Read raw values with `value` (large/small numbers render in scientific
   notation, e.g. `2.55E+4`, but stay exact) and take display formats from
   openpyxl instead.
6. **Reopening an already-open file misbehaves.** If the same path is open in
   Excel, `open workbook` returns without binding a workbook object. The helper
   detects this and fails loudly instead of silently doing nothing.
7. **Excel rewrites workbooks on save.** Observed serialization changes:
   external-link formulas are rewritten to absolute paths, and colour alpha
   bytes are normalised (`0000B050` → `FF00B050`). These are metadata changes,
   not financial edits, but they must be reported rather than hidden.
8. **Data-table (`autoNoTable`) recalculation is not addressable from
   AppleScript.** `Application.Calculation` exposes only automatic / manual /
   semiautomatic; the "automatic except data tables" distinction is per
   workbook. Unchanged sensitivity tables must not be presented as fresh.
9. **No per-workbook `calculate` means no isolation from other workbooks** —
   see (1). The block-when-busy guard is the safety mechanism.
10. **Protected sheets, missing add-ins, circular references and unsupported
    objects are unverified.** They need an explicit capability assessment on the
    actual file, and a narrowed scope if they cannot be handled safely.

### Failure handling

* A run that fails restores Excel's settings and closes only the workbook it
  opened; Excel is never killed.
* `close workbook=<abs path>` closes exactly the named workbooks (never saving)
  and reports `SKIPPED` for anything else that is open.
* An input whose hash no longer matches the inspected/approved copy is refused
  before any edit (see `inspect_workbook.py diff` and the skill policies).
