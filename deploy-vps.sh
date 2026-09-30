#!/usr/bin/env bash
# deploy-vps.sh — push local pi config to VPS, sync packages/agent content/extensions.
#
# Stable interface for the merged repo's config/bin/sync-vps.sh orchestrator:
#   deploy-vps.sh [host]   (default host: vps)
#   deploy-vps.sh --prepare-agent-content [host]   (stage only; no live deployment)
# Reads this repo's home/ plus the live ~/.pi/agent/ files noted below
# (settings.json, auth.json, code-previews.json) — nothing outside this repo.
set -euo pipefail

PREPARE_AGENT_CONTENT=0
if [ "${1:-}" = "--prepare-agent-content" ]; then
  PREPARE_AGENT_CONTENT=1
  VPS_HOST="${2:-vps}"
elif [ "$#" -le 1 ]; then
  VPS_HOST="${1:-vps}"
else
  echo "Usage: deploy-vps.sh [host] | --prepare-agent-content [host]" >&2
  exit 2
fi
PI_DIR="$HOME/.pi/agent"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REMOTE_STAGE=".cache/pi-dotfiles-agent-content"
LOCAL_STAGE=""

stage_agent_content() {
  "$REPO_DIR/lint-agent-content.sh"
  LOCAL_STAGE="$(mktemp -d "${TMPDIR:-/tmp}/dotfiles-vps-stage.XXXXXX")"
  trap 'if [ -n "$LOCAL_STAGE" ]; then rm -rf "$LOCAL_STAGE"; fi' EXIT HUP INT TERM
  mkdir -p "$LOCAL_STAGE/home"
  cp -p "$REPO_DIR/sync-agent-content.sh" "$REPO_DIR/reconcile-pi-packages.py" "$LOCAL_STAGE/"
  cp -R "$REPO_DIR/home/skills" "$LOCAL_STAGE/home/skills"
  cp -R "$REPO_DIR/home/shared-skills" "$LOCAL_STAGE/home/shared-skills"
  cp -R "$REPO_DIR/home/instructions" "$LOCAL_STAGE/home/instructions"
  cp "$REPO_DIR/home/AGENTS.md" "$LOCAL_STAGE/home/AGENTS.md"
  ssh "$VPS_HOST" "mkdir -p \"\$HOME/$REMOTE_STAGE\""
  rsync -az --delete "$LOCAL_STAGE/" "$VPS_HOST:~/$REMOTE_STAGE/"
}

print_adoption_commands() {
  printf 'Dry run: ssh %s %s\n' "$VPS_HOST" "bash ~/.cache/pi-dotfiles-agent-content/sync-agent-content.sh --adopt"
  printf 'After reviewing that plan: ssh %s %s\n' "$VPS_HOST" "bash ~/.cache/pi-dotfiles-agent-content/sync-agent-content.sh --adopt --yes"
}

echo "==> preflight agent content; no live config changes yet"
stage_agent_content
if [ "$PREPARE_AGENT_CONTENT" -eq 1 ]; then
  print_adoption_commands
  exit 0
fi
if ! ssh "$VPS_HOST" 'test -f "$HOME/.local/state/pi-dotfiles/managed-paths"'; then
  echo "    ownership manifest missing; explicit one-time adoption is required"
  ssh "$VPS_HOST" "bash \"\$HOME/$REMOTE_STAGE/sync-agent-content.sh\" --adopt" || true
  print_adoption_commands
  exit 1
fi
# Once adoption has established ownership, every unattended run still proves
# that the exact steady-state plan is safe before any live config is changed.
ssh "$VPS_HOST" "bash \"\$HOME/$REMOTE_STAGE/sync-agent-content.sh\""

echo "==> 1/4  settings.json + auth.json"
# Stage settings before replacing live state. Prepare merges earlier pending
# cleanup with current declarations, so a failed deploy cannot erase removal history.
rsync -az "$PI_DIR/settings.json" "$VPS_HOST:~/$REMOTE_STAGE/settings.json"
ssh "$VPS_HOST" "python3 \"\$HOME/$REMOTE_STAGE/reconcile-pi-packages.py\" prepare \"\$HOME/$REMOTE_STAGE/settings.json\""
rsync -az "$PI_DIR/auth.json" "$VPS_HOST:~/.pi/agent/auth.json"
ssh "$VPS_HOST" 'chmod 600 ~/.pi/agent/auth.json'

echo "==> 2/4  agent content + agents + configs"
# The manifest and successful dry-run above make --yes a steady-state apply;
# unattended deploys never enable ownership adoption or forced drift replacement.
ssh "$VPS_HOST" "bash \"\$HOME/$REMOTE_STAGE/sync-agent-content.sh\" --yes"
rsync -az --delete "$REPO_DIR/home/agents/" "$VPS_HOST:~/.pi/agent/agents/"
rsync -az "$REPO_DIR/home/subagents.json" "$VPS_HOST:~/.pi/agent/subagents.json"

# Versioned package configs: the repo is the source of truth, so the VPS gets the same
# files bootstrap.sh / rebuild.sh deploy locally.
rsync -az "$REPO_DIR/home/open-tui.json" "$VPS_HOST:~/.pi/agent/open-tui.json"
rsync -az "$REPO_DIR/home/pi-btw.json" "$VPS_HOST:~/.pi/agent/pi-btw.json"

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
# The same identity-aware reconciler handles strings, object sources and pins.
# Errors propagate; pending state is removed only after successful cleanup/install.
ssh "$VPS_HOST" "python3 \"\$HOME/$REMOTE_STAGE/reconcile-pi-packages.py\" reconcile"

echo "==> done. vps synced from local."
