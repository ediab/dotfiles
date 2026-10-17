#!/usr/bin/env python3
"""Drop Codex app-managed state from the tracked Mac config.

The Codex desktop app rewrites its version, browser-service path, and [desktop]
preferences on update. They are machine-local choices, not agent configuration,
so keep them in the live file but out of Git like Pi's machine-local keys.
"""
import sys

DROP_KEYS = ("BROWSER_USE_CODEX_APP_VERSION =", "NODE_REPL_TRUSTED_SERVICES =")


def clean(text: str) -> str:
    kept = []
    in_desktop = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            in_desktop = stripped == "[desktop]"
        if in_desktop or stripped.startswith(DROP_KEYS):
            continue
        kept.append(line)
    while kept and not kept[-1].strip():
        kept.pop()
    return "\n".join(kept) + "\n"


if __name__ == "__main__":
    sys.stdout.write(clean(sys.stdin.read()))
