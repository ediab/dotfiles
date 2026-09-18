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

## Skills

Seven skills live in `skills/`, registered only in `~/Investing`:

| Skill | Basis | Core content |
| --- | --- | --- |
| `audit-xls` | Anthropic `financial-analysis/skills/audit-xls` | formula-level checks, model-integrity checks, located findings with severity |
| `model-update` | Anthropic `equity-research/skills/model-update` | supplied actuals/guidance → mapped change list → approved copy → propagation verification |
| `investment-memo` | original | evidence record → reconciled HTML memo/pitch, missing inputs flagged |
| `scenario-analysis` | original | base/bull/bear as driver sets, propagation and grid verification, delivery case restored |
| `comps-analysis` | Anthropic `financial-analysis/skills/comps-analysis` | supplied peer data, declared units/periods, `n/m` handling, ratios-only statistics |
| `3-statement-model` | Anthropic `financial-analysis/skills/3-statement-model` | linked IS/BS/CF, schedule-driven tie-outs, driver propagation |
| `dcf-model` | Anthropic `financial-analysis/skills/dcf-model`, retrieval core stripped | unlevered FCF, WACC, discounting conventions, terminal value, EV→equity bridge |

Shared references (ordinary Markdown, not skills): `workflow-policy.md`,
`source-policy.md`, `financial-modeling.md`, `sector-drivers.md`.

## Inspector

`scripts/inspect_workbook.py` is read-only; it never writes to a workbook.

| Mode | Purpose |
| --- | --- |
| `inspect` | sheets, formulas, stored errors, external links, names, hidden content, calculation mode, provider-function traces, unsupported parts; bounded JSON record + summary |
| `checks` | mechanical candidates on a recalculated copy: error cells with formulas, formulas breaking their contiguous neighbours' pattern, numeric literals inside formulas, subtraction tie-outs with their cached values |
| `diff` | two workbooks compared at sheet, name, formula-text, constant, cached-value and error level (A→B = environment drift, B→C = edit effects) |
| `guard` | input-hash gate: refuses an artifact that is not the inspected one |
| `verify` | reconciles an evidence record (memo, change log) against the workbook's cached values |

Counts and findings are observations for analyst judgement. `checks` exits 1 when
it reports an error cell, but a clean run is not a clean model.

## Workspace registration

`setup.sh` registers the skills only in `~/Investing` (override with
`INVESTING_WORKSPACE`) and mirrors the toolset's layout beside them:

```text
~/Investing/.agents/skills      -> workspaces/investing/skills      (Pi discovers this)
~/Investing/.agents/references  -> workspaces/investing/references
~/Investing/.agents/scripts     -> workspaces/investing/scripts
~/Investing/.agents/templates   -> workspaces/investing/templates
~/Investing/.agents/README.md   -> workspaces/investing/README.md
```

The extra links exist because a relative pointer such as
`../../references/workflow-policy.md` inside a skill must resolve from *both*
the checkout and the workspace: a relative symlink inside the repo would break
once reached through `.agents/skills`, so these use absolute targets. Verified
live: skills are discovered from `/Users/eliasdiab/Investing` and from an
assignment subfolder, the two policy pointers resolve from the reported skill
location, and `TOOLSET="$(dirname "$(readlink -f ~/Investing/.agents/skills)")"`
runs the inspector from any directory.

`setup.sh` is idempotent, reports conflicts instead of overwriting, and never
touches global skill settings, `~/.pi/agent/settings.json`, `rebuild.sh`,
`bootstrap.sh` or VPS sync.

## Unit 0 — Excel feasibility gate (verified facts)

These are the measured results of the feasibility gate, on disposable synthetic
workbooks under `tests/tmp/` (`tests/make_fixtures.py`). Ad-hoc claims invented
from memory were not accepted; every item below was executed.

Run the gate with:

```sh
tests/run_all.sh                                    # everything below, in order
.venv/bin/python tests/test_applescript_scoping.py  # AppleScript name lint
.venv/bin/python tests/test_unit0_excel_roundtrip.py  # 45 checks
.venv/bin/python tests/test_audit_update_memo.py    # 42 checks: Phase 2 checkpoint
.venv/bin/python tests/test_remaining_skills.py    # Phase 3: 3-statement, DCF, comps, scenarios
```

`test_audit_update_memo.py` is the audit/update/memo integration checkpoint on
synthetic fixtures: it locates the seeded defects and separates them from
harmless input constants, applies an approved input change to a hash-gated copy
and checks the propagated values against arithmetic computed in the test, and
reconciles memo-style figures to the delivered workbook through the evidence
record (including catching a figure that disagrees).

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
   external-link formulas are rewritten to absolute paths, colour alpha bytes are
   normalised (`0000B050` → `FF00B050`), `calcId` moves, and `fullCalcOnLoad`
   is dropped once the workbook has been fully calculated. These are metadata
   changes, not financial edits, but they must be reported rather than hidden.
   *Fixed side effect:* Excel writes the **application-level** calculation mode
   into the saved file, so a run under manual calculation used to flip an
   automatic workbook to manual. `excel_model.applescript` now reads the mode
   the file itself declares (`workbookCalcModeValue`) and restores it before
   saving; an `autoNoTable` workbook is saved as `automatic` and reported as a
   `WARNING`, because AppleScript cannot express the data-table exception.
8. **Data-table (`autoNoTable`) recalculation is not addressable from
   AppleScript.** `Application.Calculation` exposes only automatic / manual /
   semiautomatic; the "automatic except data tables" distinction is per
   workbook. Unchanged sensitivity tables must not be presented as fresh.
9. **No per-workbook `calculate` means no isolation from other workbooks** —
   see (1). The block-when-busy guard is the safety mechanism.
10. **Protected sheets, missing add-ins, circular references and unsupported
    objects are unverified.** They need an explicit capability assessment on the
    actual file, and a narrowed scope if they cannot be handled safely.

11. **A modal dialog in Excel queues AppleEvents.** A leftover "Open" file-picker
    (window subrole `AXDialog`) made every automation call hang until the
    AppleScript default timeout fired, reported as `-1712 AppleEvent timed out`.
    The script now takes `timeout=<seconds>` (default 600) and names the likely
    cause on a timeout. Recover by activating Excel and pressing Escape; a file
    picker holds no workbook content.
12. **Quarantined files open fine through AppleScript.** Both supplied Vertiv
    workbooks carry `com.apple.quarantine`, and the copy opened read/write and
    saved without a Protected View prompt — but only when this terminal already
    holds Automation permission. A first run on a fresh machine may still need
    interactive approval.
13. **Excel tolerates drawing XML that strict parsers reject.** One supplied
    workbook declares `xmlns:id="{guid}"` — not a legal namespace name — so
    openpyxl/Expat failed to read the whole workbook. The inspector now skips
    unparsable drawing parts, reports them as `parse_warnings`, and still reads
    formulas, names, values and errors.
14. **Defined names are reported as a summary, not a list.** One supplied
    workbook carries **11,051** inherited names (687 broken `#REF!`, 495
    pointing at other workbooks, 10,774 hidden) while **no** Model-sheet formula
    references any of them. The record keeps totals plus a bounded sample, so a
    big number is visible without drowning the report.

15. **Excel's `open workbook` can wedge mid-session.** After a long run of
    automation it stops returning a workbook object and raises its own file
    picker instead; that picker is not one of Excel's scriptable windows, so it
    cannot be closed from AppleScript, and every later AppleEvent queues behind
    it. Recovery is a human keystroke: press Escape in Excel (or quit Excel).
    The tool now detects the stuck dialog, reports `BLOCKED` with that
    instruction when the target workbook declares external links, and otherwise
    falls back to the standard `open` command — which is **only** allowed for
    workbooks with no `xl/externalLinks/` part, because the standard open cannot
    pass `update links do not update links`. Link fidelity is never traded for
    convenience. It also refuses to attempt the preferred open while a stuck
    dialog is present, so it does not deepen the wedge.

### Failure handling

* A run that fails restores Excel's settings and closes only the workbook it
  opened; Excel is never killed.
* `close workbook=<abs path>` closes exactly the named workbooks (never saving),
  reports `SKIPPED` for anything else that is open, and restores Excel's settings
  from a snapshot instead of hardcoding them.
* An input whose hash no longer matches the inspected/approved copy is refused
  before any edit (see `inspect_workbook.py diff` and the skill policies).
