#!/usr/bin/env bash
# deploy-vps.sh — push local pi config to VPS, sync packages/skills/extensions.
set -euo pipefail

VPS_HOST="${1:-vps}"
PI_DIR="$HOME/.pi/agent"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> 1/4  settings.json + auth.json"
# Snapshot the old settings on the VPS first — step 4 needs it to find surplus packages
# (pi list only reflects the NEW settings by the time it runs).
ssh "$VPS_HOST" 'cp ~/.pi/agent/settings.json ~/.pi/agent/settings.json.pre-deploy 2>/dev/null || true'
rsync -az "$PI_DIR/settings.json" "$VPS_HOST:~/.pi/agent/settings.json"
rsync -az "$PI_DIR/auth.json" "$VPS_HOST:~/.pi/agent/auth.json"
ssh "$VPS_HOST" 'chmod 600 ~/.pi/agent/auth.json'
# VPS package exclusions (versioned in home/vps-package-exclude.txt): strip excluded
# ids from the VPS live settings.json right after the push, so step 4's reconcile
# uninstalls them as surplus (the pre-deploy snapshot still lists them) and never
# installs them. All other VPS live settings are left untouched.
if [ -f "$REPO_DIR/home/vps-package-exclude.txt" ]; then
  rsync -az "$REPO_DIR/home/vps-package-exclude.txt" "$VPS_HOST:/tmp/vps-package-exclude.txt"
  ssh "$VPS_HOST" bash -s <<'REMOTE'
    set -euo pipefail
    python3 <<'PY'
import json, os
path = os.path.expanduser("~/.pi/agent/settings.json")
exc = {l.strip() for l in open("/tmp/vps-package-exclude.txt") if l.strip() and not l.startswith("#")}
d = json.load(open(path))
kept, dropped = [], []
for p in d.get("packages", []):
    (dropped if isinstance(p, str) and p in exc else kept).append(p)
d["packages"] = kept
json.dump(d, open(path, "w"), indent=2)
open(path, "a").write("\n")
for p in dropped:
    print(f"  ! {p} (vps-excluded)")
PY
    rm -f /tmp/vps-package-exclude.txt
REMOTE
fi
# Ponytail default mode (off = on-demand via /ponytail full). Deploys the repo copy
# so fresh machines get the same default; mirrors it as the live file (the same
# file Pi's /ponytail default command writes).
ssh "$VPS_HOST" 'mkdir -p ~/.config/ponytail'
rsync -az "$REPO_DIR/home/ponytail.json" "$VPS_HOST:~/.config/ponytail/config.json"

echo "==> 2/4  skills + prompts + agents + AGENTS.md + configs"
rsync -az --delete "$REPO_DIR/home/skills/" "$VPS_HOST:~/.pi/agent/skills/"
rsync -az --delete --exclude=.gitkeep "$REPO_DIR/home/prompts/" "$VPS_HOST:~/.pi/agent/prompts/"
rsync -az --delete "$REPO_DIR/home/agents/" "$VPS_HOST:~/.pi/agent/agents/"
rsync -az "$REPO_DIR/home/models.json" "$VPS_HOST:~/.pi/agent/models.json"
rsync -az "$REPO_DIR/home/subagents.json" "$VPS_HOST:~/.pi/agent/subagents.json"
rsync -az "$REPO_DIR/home/AGENTS.md" "$VPS_HOST:~/.pi/agent/AGENTS.md"
ssh "$VPS_HOST" 'rm -f ~/.pi/agent/subagents-lite.json'  # legacy lite config, superseded by tintinweb pi-subagents
# leftovers from packages that are no longer installed anywhere
# NOTE: ~/.pi/agent/intercom was removed from this list when pi-intercom was installed —
# it is the live config/state dir for npm:pi-intercom, not a leftover.
ssh "$VPS_HOST" 'rm -rf ~/.pi/agent/pi-pretty; rm -f ~/.pi/agent/lsp.json ~/.pi/agent/claude-bridge.json ~/.pi/agent/pi-plan-build.json'  # pi-plan-build removed 2026-09-14, replaced by plan skill

# Versioned package configs: the repo is the source of truth, so the VPS gets the same
# files bootstrap.sh / rebuild.sh deploy locally.
rsync -az "$REPO_DIR/home/zentui.json" "$VPS_HOST:~/.pi/agent/zentui.json"
ssh "$VPS_HOST" 'mkdir -p ~/.pi/agent/pi-blackhole'
rsync -az "$REPO_DIR/home/pi-blackhole.json" "$VPS_HOST:~/.pi/agent/pi-blackhole/pi-blackhole-config.json"

# code-previews.json is per-machine (local paths and state) — mirrored, not versioned.
if [ -f "$PI_DIR/code-previews.json" ]; then
  rsync -az "$PI_DIR/code-previews.json" "$VPS_HOST:~/.pi/agent/code-previews.json"
fi

# web-search.json: same routing/preferences as local, but the TinyFish key comes from a 0600
# file on the VPS instead of the macOS Keychain (Linux has no `security`). The key file
# itself is managed directly on the VPS and never lands in the repo — deploy
# deliberately does not touch it, so a VPS-side key is never clobbered.
python3 - "$REPO_DIR/home/web-search.json" <<'PY' | ssh "$VPS_HOST" 'cat > ~/.pi/agent/web-search.json'
import json, sys
cfg = json.load(open(sys.argv[1]))
cfg["tinyfishApiKey"] = '!cat "$HOME/.pi/agent/tinyfish-api-key"'
print(json.dumps(cfg, indent=2) + "\n")
PY
# mcp.json is deliberately NOT synced: MCP servers are per-machine (youtube-music runs a local
# macOS node build), so the VPS keeps its own entry list.

echo "==> 3/4  extensions"
# herdr-agent-state.ts is installed and versioned by Herdr on each machine (see
# 'herdr integration status'), not shipped by this repo — exclude it so --delete leaves the
# VPS's own copy alone. Do not drop this exclude: --delete would remove it from the VPS.
rsync -az --delete --exclude=herdr-agent-state.ts "$REPO_DIR/home/extensions/" "$VPS_HOST:~/.pi/agent/extensions/"

echo "==> 4/4  reconcile packages"
# Read the canonical package list from the freshly deployed settings.json on the VPS,
# then install missing and remove surplus.
ssh "$VPS_HOST" bash -s <<'REMOTE'
  set -euo pipefail
  PI_DIR="$HOME/.pi/agent"

  # extract package identifiers (strings only, skip objects like {source:..., skills:...})
  strings_only() {
    python3 -c "
import json, sys
d = json.load(open(sys.argv[1]))
for p in d.get('packages', []):
    if isinstance(p, str):
        print(p)
" "$1" 2>/dev/null || true
  }

  wanted=$(strings_only "$PI_DIR/settings.json")
  had=$(strings_only "$PI_DIR/settings.json.pre-deploy")  # pre-deploy snapshot (step 1)

  # install packages that are missing on disk (pi list shows settings entries even
  # when the package dir is absent, so check the install dir itself)
  while IFS= read -r pkg; do
    if [ -z "$pkg" ]; then continue; fi
    case "$pkg" in
      npm:*)      dir="$PI_DIR/npm/node_modules/${pkg#npm:}" ;;
      git:*)      dir="$PI_DIR/git/${pkg#git:}" ;;
      https://*)  dir="$PI_DIR/git/${pkg#https://}" ;;
      *)          dir="" ;;
    esac
    if [ -n "$dir" ] && [ ! -e "$dir" ]; then
      echo "  + $pkg (missing on disk)"
      pi install "$pkg"
    fi
  done <<< "$wanted"

  # remove surplus (packages that were installed before the deploy but are no longer wanted)
  while IFS= read -r pkg; do
    if [ -z "$pkg" ]; then continue; fi
    if ! echo "$wanted" | grep -qxF "$pkg"; then
      echo "  - $pkg"
      pi uninstall "$pkg" || echo "  (uninstall failed — may not be removable)"
    fi
  done <<< "$had"

  rm -f "$PI_DIR/settings.json.pre-deploy"
REMOTE

echo "==> done. vps synced from local."
