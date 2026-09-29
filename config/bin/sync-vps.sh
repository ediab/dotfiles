#!/usr/bin/env bash
# sync-vps.sh — keep `ssh vps` in step with this Mac.
#
# Runs the four VPS deploys, in order:
#   1. agent content        (skills, extensions, settings, AGENTS.md, package reconcile)
#   2. VPS dotfiles         (.zshrc, .zshenv, .p10k.zsh, .tmux.conf)
#   3. Herdr VPS config     (config.vps.toml + server reload-config)
#   4. druk editor config   (settings partial, market extensions, pi-opener)
#
# Installed as the launchd agent com.diab.sync-vps (every 15 minutes). When no source
# file changed since the last successful run it exits without touching the network.
#
#   sync-vps.sh            deploy only when a source file changed
#   sync-vps.sh --force    deploy unconditionally
#
# Every step runs even if an earlier one fails. The stamp is advanced only when all
# steps succeeded, so a failure is retried on the next tick.
#
# NOTE: launchd runs this with /bin/bash (3.2) and a minimal PATH — keep it 3.2-safe.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CONFIG_ROOT="$DOTFILES_ROOT/config"
STAMP="$HOME/.cache/sync-vps.stamp"
NOTIFY_STAMP="$HOME/.cache/sync-vps.notified"
NOTIFY_INTERVAL=3600   # seconds between failure notifications
LOG="/tmp/com.diab.sync-vps.out"

# launchd starts agents with a minimal PATH; Homebrew is needed for terminal-notifier.
export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:$PATH"

# Watched inputs are exactly the sources the deploys read. Repository metadata
# is excluded because it is not a deployed input.
INPUTS=(
  "$DOTFILES_ROOT/home"
  "$DOTFILES_ROOT/deploy-vps.sh"
  "$CONFIG_ROOT/vps"
  "$CONFIG_ROOT/herdr/config.vps.toml"
  "$CONFIG_ROOT/druk"
)

failed=""

# The agent-content deploy reads home/ and live ~/.pi/agent files, so watch only
# those repository inputs and guard the entry point separately.
AGENT_CONTENT_DEPLOY="$DOTFILES_ROOT/deploy-vps.sh"
[ -x "$AGENT_CONTENT_DEPLOY" ] || { echo "missing: $AGENT_CONTENT_DEPLOY (dotfiles checkout?)" >&2; failed="agent-content(checkout)"; }

# One host, three spellings: agent-content takes it as $1; the other deploys use env vars.
VPS_HOST="${VPS_HOST:-vps}"
export VPS_HOST
export HERDR_VPS_HOST="${HERDR_VPS_HOST:-$VPS_HOST}"

mkdir -p "$HOME/.cache"

changed() {
  [ -e "$STAMP" ] || return 0
  [ -n "$(find "${INPUTS[@]}" -newer "$STAMP" -print -quit 2>/dev/null)" ]
}

notify() {
  local message="$1" now last
  now="$(date +%s)"
  last="$(cat "$NOTIFY_STAMP" 2>/dev/null || echo 0)"
  case "$last" in ''|*[!0-9]*) last=0 ;; esac
  if [ $((now - last)) -lt "$NOTIFY_INTERVAL" ]; then
    echo "    (notification suppressed: one was sent under $((NOTIFY_INTERVAL / 60)) min ago)"
    return 0
  fi
  echo "$now" > "$NOTIFY_STAMP"
  if command -v terminal-notifier >/dev/null 2>&1; then
    terminal-notifier -title "VPS sync failed" -message "$message" -group com.diab.sync-vps >/dev/null 2>&1 || true
  else
    osascript -e "display notification \"$message\" with title \"VPS sync failed\"" >/dev/null 2>&1 || true
  fi
}

run_step() {
  local name="$1" status=0
  shift
  echo "==> $name"
  "$@" || status=$?
  if [ "$status" -eq 0 ]; then
    echo "    ok"
  else
    echo "    FAILED (exit $status)"
    failed="${failed:+$failed, }$name"
  fi
}

if [ "${1:-}" != "--force" ] && ! changed; then
  echo "no changes under the deployed paths since the last successful sync — nothing to do"
  exit 0
fi

if [ -z "$failed" ]; then
  run_step agent-content "$AGENT_CONTENT_DEPLOY" "$VPS_HOST"
else
  echo "==> agent-content SKIPPED (entrypoint missing)"
fi
run_step vps-dotfiles "$CONFIG_ROOT/vps/deploy-vps.sh"
run_step herdr "$CONFIG_ROOT/herdr/deploy-vps.sh"
run_step druk "env" "DEPLOY_DRUK_HOST=$VPS_HOST" "$CONFIG_ROOT/druk/deploy-druk.sh"

if [ -z "$failed" ]; then
  touch "$STAMP"
  echo "==> deployed: dotfiles agent content, VPS dotfiles, Herdr, druk (stamp $STAMP)"
  exit 0
fi

echo "==> FAILED: $failed — see $LOG" >&2
notify "failed: $failed (see $LOG)"
exit 1
