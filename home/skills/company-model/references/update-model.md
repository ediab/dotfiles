# Update a model after new results

Runs when new actuals arrive (typically a new quarter), when an assumption is re-approved, or
when the evidence set is refreshed. The generated formulas and layout may be rebuilt; the user's
designated override cells and the five Outlook text fields are preserved by identity. Arbitrary
formula or layout edits inside the workbook are **not** preserved — say so before an update, and
prefer changes in the generator.

## Sequence

1. **Preflight the original.** Read it without modifying it: sheet inventory, period header row,
   driver blocks, Outlook labels, and whether it carries VBA, external links, pivots, slicers or
   connections (refuse and explain if it does). Record the original's sha256.
2. **Extract the payload.** `python3 scripts/overrides.py check <original.xlsx>` to inspect, then
   `extract <original.xlsx> --out overrides.json`. The payload is versioned:
   `schema_version`, `assumption_overrides` (driver id → fiscal period → numeric value) and
   `outlook_text` (field id → text). Extraction validates every override cell: formulas, text,
   booleans, duplicate identities and malformed driver blocks are rejected rather than guessed. A
   blank numeric cell means "use the default"; **zero is a valid override**. Outlook fields are
   located by exact label in the configured sheet and column; each label must occur exactly once,
   and a missing or duplicated label is a hard error. Blank Outlook text is an intentional value
   and restores as blank — it is not "missing from the payload".
3. **Record identities.** `(driver, fiscal period)` is the numeric identity; `(field id)` is the
   Outlook identity. The cell coordinate is only where the value sits today. Each driver's
   definition signature (its active-input formula with block rows and its own column normalised
   away) is recorded beside it.
4. **Refresh only authorised evidence** and roll the fiscal window forward. Rebuild the company
   project's `build/data.py` inputs from the retained or newly approved evidence; never hand-copy
   values out of the previous workbook.
5. **Rebuild the workbook** with `build/build.py` into a fresh path. The rebuild carries the new
   period grid, the current defaults and the current approval state.
6. **Restore the payload** into the rebuilt workbook:
   `python3 scripts/overrides.py restore <rebuild.xlsx> <updated.xlsx> --overrides overrides.json --report report.json`.
   The template is never written; the output is a separate, non-colliding workbook. Placement
   comes from the rebuild's own headers, driver rows and Outlook labels, so moved rows and
   shifted columns are handled by identity. Restore only after the rebuild and before
   recalculation.
7. **Report, do not silently remap.** The restore report lists:
   - **restored** — matched driver/field and period;
   - **retired period** — the quarter left the forecast grid (it became actual). The value is
     dropped, not carried forward;
   - **removed driver** — the driver no longer exists under that name; the value is withheld,
     because a rename is not proof of the same meaning;
   - **changed definition** — the active-input formula changed; the value is withheld for review.
     Re-run with `--allow-definition-change` only once the user has confirmed the driver still
     means the same thing; the item is **still reported** as an allowed definition change, so the
     category is never silently cleared.
8. **Flag carried assumptions for review** and obtain approval for material new ones. Overrides
   restored from a previous forecast were approved for an older evidence set: re-confirm them, and
   treat every *new* forecast quarter as requiring its own assumption approval (per `SKILL.md`
   step 5) before it is delivered.
9. **Validate and deliver** the new workbook through the normal validation steps, then report the
   original's unchanged hash alongside the new file's path so both facts are auditable.

## What the helper guarantees, and what it does not

Guaranteed: identities survive reordered or inserted rows and columns, quarter rollover, zero and
cleared overrides, a driver removed or renamed, and blank or multiline/Unicode Outlook text. No
override migrates silently to another quarter, no Outlook value migrates to another label, and
the file the payload came from is byte-for-byte unchanged.

Not guaranteed: correctness of a restored value under a changed driver definition (that is why
it is withheld), any formula or layout edit made directly in the workbook, or preservation of
overrides in a workbook whose driver blocks no longer follow the four-row contract. Tests for all
of the guaranteed behaviours live in `tests/test_overrides.py`.
