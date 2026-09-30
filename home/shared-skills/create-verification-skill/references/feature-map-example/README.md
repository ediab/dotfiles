# Notes CLI verification map example

Illustrative map for a small notes CLI, not a harness to install. The example assumes an existing `notes.py` with `--data-dir`, `add`, `list`, and `search` commands. Replace these commands and results with those discovered in the target repo; generated instructions must not retain example assumptions.

## Baseline

Run from the app root. Use an owned scratch directory with separate data and evidence locations:

```bash
VERIFY_ROOT=$(mktemp -d)
VERIFY_DATA="$VERIFY_ROOT/data"
VERIFY_EVIDENCE="$VERIFY_ROOT/evidence"
mkdir -p "$VERIFY_DATA" "$VERIFY_EVIDENCE"
python3 notes.py --help
python3 notes.py --data-dir "$VERIFY_DATA" list
```

Doctor confirms the expected CLI help/version and reads the empty disposable store. Each feature starts with a fresh empty data directory unless it names another prerequisite. The example CLI prints one note title per line.

## Proof and cleanup

Capture literal actions, stdout, stderr, and exit codes; assert expected values rather than just successful invocation. Verify persistence by a separate CLI read. Keep a feature ID and entry point with each artifact. Do not include private notes or credentials.

Clean only the data directory created by this run, with its ownership established. Retain `VERIFY_EVIDENCE` and confirm its artifacts remain afterward. An unexpected state needs doctor and a safe reset before retrying.

## Feature contract and index

Each feature starts with a title and user-facing description, then the four H2s shown in the examples. Name exact prerequisites, entry points, actions, expected results, and gotchas. Unreachable routes require the command attempted and unmet prerequisite; another entry point does not count as its proof.

- [Create a note](create-note.md)
- [Search notes](search.md)
