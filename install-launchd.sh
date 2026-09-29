#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "Usage: install-launchd.sh capture|sync-vps" >&2
  exit 2
fi

DOTFILES_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
case "$1" in
  capture)
    label='com.diab.dotfiles.capture'
    template="$DOTFILES_ROOT/launchd/$label.plist"
    ;;
  sync-vps)
    label='com.diab.sync-vps'
    template="$DOTFILES_ROOT/launchd/$label.plist"
    ;;
  *)
    echo "Usage: install-launchd.sh capture|sync-vps" >&2
    exit 2
    ;;
esac

command -v launchctl >/dev/null 2>&1 || { echo 'launchctl is required' >&2; exit 1; }
command -v plutil >/dev/null 2>&1 || { echo 'plutil is required' >&2; exit 1; }
[ -f "$template" ] || { echo "missing template: $template" >&2; exit 1; }

: "${HOME:?HOME must be set}"
launch_agents="$HOME/Library/LaunchAgents"
plist="$launch_agents/$label.plist"
rendered="$(mktemp "${TMPDIR:-/tmp}/dotfiles-launchd.XXXXXX")"
trap 'rm -f "$rendered"' EXIT HUP INT TERM
sed -e "s|__DOTFILES_ROOT__|$DOTFILES_ROOT|g" \
    -e "s|__HOME__|$HOME|g" "$template" > "$rendered"
if grep -Eq '__DOTFILES_ROOT__|__HOME__' "$rendered"; then
  echo "unsubstituted placeholder in $template" >&2
  exit 1
fi
plutil -lint "$rendered"

mkdir -p "$launch_agents"
launchctl bootout "gui/$UID/$label" 2>/dev/null || true
cp "$rendered" "$plist"
launchctl bootstrap "gui/$UID" "$plist"
echo "installed $label"
