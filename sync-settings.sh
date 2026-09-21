#!/usr/bin/env bash
# Auto-sync: live ~/.pi/agent/*.json → pi-dotfiles repo.
# Triggered by launchd WatchPaths when pi mutates a watched file.
set -euo pipefail

# Repo root = this script's location (works from any clone path, not just ~/dev/pi-dotfiles).
REPO="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
LIVE_DIR="$HOME/.pi/agent"

# ponytail: debounce via sleep — launchd may fire multiple times in a burst
sleep 5

cd "$REPO"
STAGED=0
for f in settings.json open-tui.json; do
  if ! diff -q "$LIVE_DIR/$f" "$REPO/home/$f" &>/dev/null; then
    cp "$LIVE_DIR/$f" "$REPO/home/$f"
    git add "home/$f"
    STAGED=1
  fi
done

[ "$STAGED" = "1" ] || exit 0
git diff --cached --quiet || git commit -q -m "auto: sync pi config from live"
