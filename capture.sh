#!/usr/bin/env bash
# Capture live Pi settings and managed config changes into this checkout.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIVE_DIR="$HOME/.pi/agent"

# launchd WatchPaths events can arrive in a burst while Pi is writing these files.
sleep 5
export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:$PATH"

cd "$REPO"
for file in settings.json open-tui.json; do
  if [ -f "$LIVE_DIR/$file" ]; then
    cp -p "$LIVE_DIR/$file" "$REPO/home/$file"
  fi
done

# Keep the last good list if VS Code is unavailable or its CLI fails.
extensions_tmp="$(mktemp "${TMPDIR:-/tmp}/dotfiles-vscode-extensions.XXXXXX")"
if code --list-extensions > "$extensions_tmp" 2>/dev/null; then
  cat "$extensions_tmp" > "$REPO/config/vscode/extensions.txt"
else
  echo "warning: could not refresh config/vscode/extensions.txt" >&2
fi
rm -f "$extensions_tmp"

git add -u -- home/settings.json home/open-tui.json config/
if git diff --cached --quiet -- home/settings.json home/open-tui.json config/; then
  exit 0
fi

git commit -m "auto: capture dotfiles $(date '+%Y-%m-%d %H:%M')" -- \
  home/settings.json home/open-tui.json config/
if ! git push 2>&1; then
  echo "warning: push failed; local capture commit retained" >&2
fi
