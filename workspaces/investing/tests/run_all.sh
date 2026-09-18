#!/usr/bin/env bash
# Run every investing-workspace check. Excel must be otherwise idle: the
# automation refuses to run while unrelated workbooks are open.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
PY=".venv/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "no .venv - run: python3 -m venv .venv && .venv/bin/python -m pip install -e ." >&2
  exit 2
fi
echo "== AppleScript identifier scoping lint"
"$PY" tests/test_applescript_scoping.py
echo
echo "== Unit 0 Excel feasibility gate"
"$PY" tests/test_unit0_excel_roundtrip.py
echo
echo "== Phase 2 checkpoint: audit-xls / model-update / investment-memo"
"$PY" tests/test_audit_update_memo.py
