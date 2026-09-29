#!/usr/bin/env bash
# pi-dotfiles — update pi + all installed packages, and re-sync bundled custom skills.
# For day-to-day updates on a machine already bootstrapped by bootstrap.sh.
# New machine? Use bootstrap.sh instead.
#   rebuild.sh              → full: pi update --all + settings.json + all bundled config
#   rebuild.sh --sync-only  → bundled config only (skills, instructions, extensions, agents,
#                             and config); skips package updates and the settings.json copy
set -euo pipefail

SYNC_ONLY=0
if [ "${1:-}" = "--sync-only" ]; then
  SYNC_ONLY=1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
PI_EXTENSIONS_DIR="$HOME/.pi/agent/extensions"
# Skill and generated-instruction deployment is owned by sync-agent-content.sh.
# Everything under home/extensions/ is copied recursively; no script edit needed.

if [ "$SYNC_ONLY" = "1" ]; then
  echo "==> sync-only: skipping 'pi update --all' and the settings.json copy"
else
  echo "==> 1/3  pi + packages"
  pi update --all

  echo "==> 2/3  settings.json (repo → live)"
  # Repo is source of truth for the pi agent settings.json. NOTE: pi itself rewrites
  # this file (changelog version, installed-packages list); if you edit the live file,
  # re-sync it back into the repo (`cp ~/.pi/agent/settings.json ~/Dev/pi-dotfiles/settings.json`)
  # before re-running rebuild.sh to avoid clobbering local changes.
  cp "$SCRIPT_DIR/home/settings.json" "$HOME/.pi/agent/settings.json" \
    && echo "    settings.json  re-synced" \
    || echo "    FAILED: home/settings.json"
fi

echo "==> 3/3  skills + generated instructions + extensions"
"$SCRIPT_DIR/lint-agent-content.sh"
"$SCRIPT_DIR/sync-agent-content.sh" --yes

if [ -d "$SCRIPT_DIR/home/extensions" ]; then
  mkdir -p "$PI_EXTENSIONS_DIR"
  cp -R "$SCRIPT_DIR/home/extensions/." "$PI_EXTENSIONS_DIR/"
  echo "    extensions  re-synced"
fi

# Custom agents (pi-subagents): every .md in home/agents/ → ~/.pi/agent/agents/. Add/remove by file; no script edit needed.
PI_AGENTS_DIR="$HOME/.pi/agent/agents"
mkdir -p "$PI_AGENTS_DIR"
shopt -s nullglob
for src in "$SCRIPT_DIR/home/agents/"*.md; do
  cp "$src" "$PI_AGENTS_DIR/"
  echo "    $(basename "$src")  re-synced"
done
shopt -u nullglob

# Subagent defaults (tintinweb pi-subagents global settings; pi never writes this file)
cp "$SCRIPT_DIR/home/subagents.json" "$HOME/.pi/agent/subagents.json" \
  && echo "    subagents.json  re-synced"

# Web search config (pi-web-access provider/workflow prefs). 0.29.0+ reads ~/.pi/agent/web-search.json;
# the old ~/.pi/web-search.json is ignored unless XDG_CONFIG_HOME is set.
cp "$SCRIPT_DIR/home/web-search.json" "$HOME/.pi/agent/web-search.json" \
  && echo "    web-search.json  re-synced"

# Open-TUI config (footer segments, telemetry toggles, thinking peek).
# Repo copy is the source of truth.
cp "$SCRIPT_DIR/home/open-tui.json" "$HOME/.pi/agent/open-tui.json" \
  && echo "    open-tui.json  re-synced"

# pi-btw side-thread config (model, thinking level). Repo copy is the source
# of truth. Unlike settings.json this flows repo → live (rebuild overwrites
# live), so tune it in the repo and re-run rebuild.sh.
cp "$SCRIPT_DIR/home/pi-btw.json" "$HOME/.pi/agent/pi-btw.json" \
  && echo "    pi-btw.json  re-synced"

# Ponytail default mode (off = opt-in per session via /ponytail).
# Repo copy is the source of truth — matches the live file written by
# Pi's /ponytail default command (~/.config/ponytail/config.json).
# diff first so rebuild --sync-only stays quiet when nothing changed.
if ! diff -q "$SCRIPT_DIR/home/ponytail.json" "$HOME/.config/ponytail/config.json" &>/dev/null; then
  mkdir -p "$HOME/.config/ponytail"
  cp "$SCRIPT_DIR/home/ponytail.json" "$HOME/.config/ponytail/config.json" \
    && echo "    ponytail.json  re-synced (defaultMode off)"
fi

# Subagent model router (Jev-judged tier chains + per-agent floors). Repo copy is
# the source of truth; the extension also ships built-in defaults, so this file
# only needs entries you want to override.
cp "$SCRIPT_DIR/home/pi-subagent-router.json" "$HOME/.pi/agent/pi-subagent-router.json" \
  && echo "    pi-subagent-router.json  re-synced"

# Secrets file for pi sessions (loaded by home/extensions/env-loader.ts). Seed
# once from the example; never overwrite an existing .env with real values in it.
if [ ! -f "$HOME/.pi/agent/.env" ]; then
  cp "$SCRIPT_DIR/home/.env.example" "$HOME/.pi/agent/.env" \
    && echo "    .env  seeded from example (fill in TYPESAFE_API_KEY)" \
    || echo "    FAILED: .env seed"
  chmod 600 "$HOME/.pi/agent/.env"
fi

echo "==> done."
