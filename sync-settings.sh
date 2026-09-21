#!/usr/bin/env bash
# Auto-sync: live ~/.pi/agent/settings.json → pi-dotfiles repo.
# Triggered by launchd WatchPaths when pi mutates settings.json.
set -euo pipefail

LIVE="$HOME/.pi/agent/settings.json"
# Repo root = this script's location (works from any clone path, not just ~/dev/pi-dotfiles).
REPO="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
DEST="$REPO/home/settings.json"

# ponytail: debounce via sleep — launchd may fire multiple times in a burst
sleep 5

# Only act if the file actually changed
if diff -q "$LIVE" "$DEST" &>/dev/null; then
  exit 0
fi

cp "$LIVE" "$DEST"
cd "$REPO"
git add home/settings.json
git diff --cached --quiet || git commit -q -m "auto: sync settings.json from pi"
