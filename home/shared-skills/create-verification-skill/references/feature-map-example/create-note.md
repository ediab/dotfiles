# Create a note

The user adds a title and can read it back in a later invocation.

## Sub-features

- create-title: add one note with a nonempty title.
- persistence: read the saved title in a separate CLI invocation.

## How to get to it (user POV)

Use the CLI's `add` command from the app root, with the disposable data directory from the map README.

## Driving it with the CLI

Preconditions: a fresh empty `VERIFY_DATA`, owned by this run, and the example command contract described in the README.

- Add: `python3 notes.py --data-dir "$VERIFY_DATA" add "Quarterly plan"`. Expect exit 0 and the title `Quarterly plan`.
- Read: `python3 notes.py --data-dir "$VERIFY_DATA" list`. Expect exit 0 and exactly `Quarterly plan` on stdout. This independent invocation checks persistence.
- Evidence: save both literal commands, outputs, and exit codes under `VERIFY_EVIDENCE/create-title.txt`. Assert the exact title rather than merely checking nonempty output.

## Gotchas

A populated store invalidates the single-title assertion. Reset only this run's owned data. Capture evidence before cleanup and retain it afterward. If add succeeds but the next read is empty, report failed persistence, not successful creation.
