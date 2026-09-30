# Search notes

The user searches saved note titles and receives only matching results.

## Sub-features

- matching-title: find a stored title by a query.
- empty-result: return no titles for a query with no match.

## How to get to it (user POV)

Use the CLI's `search` command with the disposable data directory from the map README.

## Driving it with the CLI

Preconditions: the example command contract in the README; a fresh owned store seeded with exactly `Quarterly plan` and `Grocery list` through two CLI `add` calls.

- Match: `python3 notes.py --data-dir "$VERIFY_DATA" search "Quarterly"`. Expect exit 0 and exactly `Quarterly plan` on stdout.
- No match: `python3 notes.py --data-dir "$VERIFY_DATA" search "missing"`. Expect exit 0 and empty stdout.
- Evidence: capture seeding, both queries, outputs, and exit codes under `VERIFY_EVIDENCE/search.txt`. Assert the positive match as well as the absence case.

## Gotchas

No-match proof alone would accept a search that always returns nothing. Drive both queries with the same seeded state. Record missing prerequisites and failed actions as unverified rather than inferring a pass. Cleanup removes owned data, never the proof.
