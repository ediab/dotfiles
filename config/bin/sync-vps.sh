#!/usr/bin/env bash
# sync-vps.sh — keep `ssh vps` in step with this Mac.
#
# Runs the four VPS deploys, in order:
#   1. pi-dotfiles harness  (skills, extensions, settings, AGENTS.md, package reconcile)
#   2. configs VPS dotfiles (.zshrc, .zshenv, .p10k.zsh, .tmux.conf)
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

REPO="$HOME/dev/configs"
PI_DOTFILES="$HOME/dev/pi-dotfiles"
STAMP="$HOME/.cache/sync-vps.stamp"
NOTIFY_STAMP="$HOME/.cache/sync-vps.notified"
NOTIFY_INTERVAL=3600   # seconds between failure notifications
LOG="/tmp/com.diab.sync-vps.out"

# launchd starts agents with a minimal PATH; Homebrew is needed for terminal-notifier.
export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:$PATH"

# Watched inputs = exactly the sources the deploys read. `.git` is deliberately
# excluded: the autocommit agent churns it every 15 minutes and nothing deploys from it.
INPUTS=(
  "$PI_DOTFILES/home"
  "$PI_DOTFILES/deploy-vps.sh"
  "$REPO/vps"
  "$REPO/herdr/config.vps.toml"
  "$REPO/druk"
)

failed=""

# pi-dotfiles is a dependency with a stable interface: deploy-vps.sh [host],
# reading only its own home/ plus the live ~/.pi/agent/ config files (its README
# documents the contract) — never paths inside this repo. So the only inputs
# watched here for that step are its script and its home/ (plus a checkout guard).
PI_DOTFILES_DEP="$PI_DOTFILES/deploy-vps.sh"
[ -x "$PI_DOTFILES_DEP" ] || { echo "missing: $PI_DOTFILES_DEP (pi-dotfiles checkout?)" >&2; failed="pi-dotfiles(checkout)"; }

# One host, three spellings: pi-dotfiles takes it as $1, the configs scripts as env vars.
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
  run_step pi-dotfiles "$PI_DOTFILES_DEP" "$VPS_HOST"
else
  echo "==> pi-dotfiles SKIPPED (checkout missing)"
fi
run_step vps-dotfiles "$REPO/vps/deploy-vps.sh"
run_step herdr "$REPO/herdr/deploy-vps.sh"
run_step druk "env" "DEPLOY_DRUK_HOST=$VPS_HOST" "$REPO/druk/deploy-druk.sh"

if [ -z "$failed" ]; then
  touch "$STAMP"
  echo "==> deployed: pi-dotfiles, vps-dotfiles, herdr, druk (stamp $STAMP)"
  exit 0
fi

echo "==> FAILED: $failed — see $LOG" >&2
notify "failed: $failed (see $LOG)"
exit 1
