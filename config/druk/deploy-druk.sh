#!/usr/bin/env bash
# deploy-druk.sh — sync druk editor config from this repo to a machine.
#
# Sources (all in this dir):
#   settings.partial.json   user-chosen settings, merged over the live config
#   extensions.txt          market extension ids, installed when missing
#   pi-opener.config.yaml   pi-opener config -> ~/.config/pi-opener/config.yaml
#
# druk's live config (~/.config/druk/config.json) is a full-file JSON that druk
# itself rewrites (theme picks, window state), so the repo holds only a partial:
# the merge adds our keys and leaves everything else (theme, keybindings, …)
# untouched. Unknown/invalid keys fall back to druk defaults, never break startup.
#
#   deploy-druk.sh            local machine only
#   DEPLOY_DRUK_HOST=vps deploy-druk.sh   local + VPS (same files both sides)
#
# NOTE: keep bash-3.2-safe (sync-vps.sh runs under launchd's /bin/bash).

set -euo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)"
HOST="${DEPLOY_DRUK_HOST:-}"

echo "==> druk settings (merge partial over live config)"
merge() {
  python3 - "$SRC/settings.partial.json" <<'PY'
import json, os, sys
partial = json.load(open(sys.argv[1]))
path = os.path.expanduser("~/.config/druk/config.json")
try:
    live = json.load(open(path))
except (OSError, ValueError):
    live = {}
live.update(partial)
os.makedirs(os.path.dirname(path), exist_ok=True)
json.dump(live, open(path, "w"), indent=2)
open(path, "a").write("\n")
print("  merged %d keys -> %s" % (len(partial), path))
PY
}
merge
if [ -n "$HOST" ]; then
  scp -q "$SRC/settings.partial.json" "$HOST:/tmp/druk-settings.partial.json"
  ssh "$HOST" python3 - /tmp/druk-settings.partial.json <<'PY'
import json, os, sys
partial = json.load(open(sys.argv[1]))
path = os.path.expanduser("~/.config/druk/config.json")
try:
    live = json.load(open(path))
except (OSError, ValueError):
    live = {}
live.update(partial)
os.makedirs(os.path.dirname(path), exist_ok=True)
json.dump(live, open(path, "w"), indent=2)
open(path, "a").write("\n")
print("  merged %d keys -> %s" % (len(partial), path))
PY
  ssh "$HOST" 'rm -f /tmp/druk-settings.partial.json'
fi

echo "==> druk extensions (install missing ids from the market)"
install_missing() {
  while IFS= read -r id; do
    case "$id" in ""|\#*) continue ;; esac
    if [ -d "$HOME/.config/druk/extensions/$id" ]; then
      echo "  = $id (already installed)"
    else
      echo "  + $id (fetching manifest from market)"
      mkdir -p "$HOME/.config/druk/extensions/$id"
      if curl -fsSL "https://raw.githubusercontent.com/letstri/druk/main/extensions/$id/extension.json" \
          -o "$HOME/.config/druk/extensions/$id/extension.json"; then
        echo "    installed $id"
      else
        echo "    FAILED to fetch $id" >&2
        rmdir "$HOME/.config/druk/extensions/$id" 2>/dev/null || true
      fi
    fi
  done < "$SRC/extensions.txt"
}
install_missing
if [ -n "$HOST" ]; then
  scp -q "$SRC/extensions.txt" "$HOST:/tmp/druk-extensions.txt"
  ssh "$HOST" bash -s <<'REMOTE'
    set -euo pipefail
    while IFS= read -r id; do
      case "$id" in ""|\#*) continue ;; esac
      if [ -d "$HOME/.config/druk/extensions/$id" ]; then
        echo "  = $id (already installed)"
      else
        echo "  + $id (fetching manifest from market)"
        mkdir -p "$HOME/.config/druk/extensions/$id"
        if curl -fsSL "https://raw.githubusercontent.com/letstri/druk/main/extensions/$id/extension.json" \
            -o "$HOME/.config/druk/extensions/$id/extension.json"; then
          echo "    installed $id"
        else
          echo "    FAILED to fetch $id" >&2
          rmdir "$HOME/.config/druk/extensions/$id" 2>/dev/null || true
        fi
      fi
    done < /tmp/druk-extensions.txt
    rm -f /tmp/druk-extensions.txt
REMOTE
fi

echo "==> pi-opener config"
mkdir -p "$HOME/.config/pi-opener"
cp "$SRC/pi-opener.config.yaml" "$HOME/.config/pi-opener/config.yaml"
echo "  copied -> $HOME/.config/pi-opener/config.yaml"
if [ -n "$HOST" ]; then
  ssh "$HOST" 'mkdir -p ~/.config/pi-opener'
  scp -q "$SRC/pi-opener.config.yaml" "$HOST:~/.config/pi-opener/config.yaml"
  echo "  copied -> $HOST:~/.config/pi-opener/config.yaml"
fi

echo ""
echo "Done. druk picks up settings/extensions on next launch (press r in the extensions panel to refresh)."
