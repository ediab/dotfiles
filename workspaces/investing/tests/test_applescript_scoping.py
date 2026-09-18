#!/usr/bin/env python3
"""Lint the AppleScript helper for name collisions with Excel's scripting dictionary.

Inside a `tell application "Microsoft Excel"` block, an unqualified name that also
exists in Excel's dictionary resolves to Excel's property instead of to this
script's variable or handler parameter. That silently corrupts values (`kind` and
`content` both came back as `missing value` during Unit 0) or raises at compile
time (`ask`, `key`, `text`, `data`, `number`).

For every identifier the script assigns or takes as a handler parameter, this test
sets it outside the tell block and reads it back inside the block. Identifiers on
ALLOWED are intentional Excel properties, not variables.

Usage:   .venv/bin/python tests/test_applescript_scoping.py
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APPLESCRIPT = ROOT / "scripts" / "excel_model.applescript"

# Names used deliberately as Excel properties, never as script variables.
ALLOWED = {
    "calculation",  # set calculation to calculation manual
    "ask",          # set ask to update links to ...
}


def identifiers(source: str) -> list[str]:
    names = set(re.findall(r"\bset\s+([A-Za-z][A-Za-z0-9_]*)\s+to\b", source))
    names |= set(re.findall(r"repeat with ([A-Za-z][A-Za-z0-9_]*)\s+in\b", source))
    for match in re.finditer(r"\bon\s+([A-Za-z][A-Za-z0-9_]*)\(([^)]*)\)", source):
        for param in match.group(2).split(","):
            param = param.strip()
            if param:
                names.add(param)
    return sorted(names - ALLOWED)


def build_probe(names: list[str]) -> str:
    handlers = []
    for i, name in enumerate(names):
        handlers.append(
            f'on p{i}()\n'
            f'\ttry\n\t\tset {name} to "SENTINEL"\n'
            f'\ton error e number n\n\t\treturn "SET-ERROR:" & n\n\tend try\n'
            f'\ttell application "Microsoft Excel"\n\t\ttry\n\t\t\treturn ({name} as text)\n'
            f'\t\ton error e number n\n\t\t\treturn "READ-ERROR:" & n\n\t\tend try\n\tend tell\n'
            f'end p{i}\n'
        )
    body = ["on run", '\tset rpt to ""']
    for i, name in enumerate(names):
        body.append(f'\tset rpt to rpt & "{name}=" & (my p{i}() as text) & linefeed')
    body += ["\treturn rpt", "end run"]
    return "\n".join(handlers) + "\n" + "\n".join(body)


def main() -> int:
    source = APPLESCRIPT.read_text()
    names = identifiers(source)
    if not names:
        print("no identifiers found - did the script move?")
        return 1

    with tempfile.NamedTemporaryFile("w", suffix=".applescript", delete=False) as handle:
        handle.write(build_probe(names))
        probe_path = Path(handle.name)

    proc = subprocess.run(["osascript", str(probe_path)], capture_output=True, text=True, timeout=300)
    probe_path.unlink()
    if proc.returncode != 0:
        print("probe failed to run:")
        print(proc.stderr.strip())
        return 1

    collisions = []
    for line in proc.stdout.splitlines():
        if "=" not in line:
            continue
        name, _, value = line.partition("=")
        if value.strip() != "SENTINEL":
            collisions.append(f"{name} -> {value.strip()}")

    print(f"checked {len(names)} identifiers in {APPLESCRIPT.name}")
    if collisions:
        print("identifiers that resolve to Excel instead of to this script:")
        for c in collisions:
            print(f"  - {c}")
        print("rename them or add them to ALLOWED with a justification")
        return 1
    print("no identifier shadows a name in Excel's scripting dictionary")
    return 0


if __name__ == "__main__":
    sys.exit(main())
