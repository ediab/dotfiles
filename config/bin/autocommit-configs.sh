#!/bin/bash
set -euo pipefail

REPO="$HOME/dev/configs"
cd "$REPO"

# launchd runs with a minimal PATH (/usr/bin:/bin:/usr/sbin:/sbin);
# add Homebrew so code/git are found.
export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:$PATH"

# Refresh VS Code extensions list (best-effort: never block the commit)
code --list-extensions 2>/dev/null > vscode/extensions.txt || true

# Only act if there are changes
if [ -z "$(git status --porcelain)" ]; then
  exit 0
fi

git add -A
git commit -m "auto: $(date '+%Y-%m-%d %H:%M')" || exit 0  # exit 0 on empty commit (shouldn't happen, but safe)
git push 2>&1 || true  # push failures (no network, etc.) are non-fatal
