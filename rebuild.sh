#!/usr/bin/env bash
# pi-dotfiles — update pi + all installed packages, and re-sync bundled custom skills.
# For day-to-day updates on a machine already bootstrapped by bootstrap.sh.
# New machine? Use bootstrap.sh instead.
#   rebuild.sh              → full: pi update --all + settings.json + all bundled config
#   rebuild.sh --sync-only  → bundled config only (skills, extensions, agents, models,
#                             subagents, web-search); skips the package
#                             update and the settings.json copy — for skill/extension edits
set -euo pipefail

SYNC_ONLY=0
if [ "${1:-}" = "--sync-only" ]; then
  SYNC_ONLY=1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
PI_SKILLS_DIR="$HOME/.pi/agent/skills"
PI_EXTENSIONS_DIR="$HOME/.pi/agent/extensions"
# Skills deployed below = every dir in $SCRIPT_DIR/home/skills/ (whole-dir copies) plus any
# top-level files such as ATTRIBUTION.md.
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

echo "==> 3/3  skills (every dir + top-level file in $SCRIPT_DIR/home/skills/) + extensions"
mkdir -p "$PI_SKILLS_DIR"
shopt -s nullglob
for src in "$SCRIPT_DIR/home/skills"/*/; do
  skill="$(basename "$src")"
  rm -rf "$PI_SKILLS_DIR/$skill"
  cp -R "$SCRIPT_DIR/home/skills/$skill" "$PI_SKILLS_DIR/"
  echo "    $skill  re-synced"
done
# Top-level files in home/skills/ (e.g. ATTRIBUTION.md) deploy beside the skill dirs.
for src in "$SCRIPT_DIR/home/skills/"*; do
  if [ -f "$src" ]; then
    cp "$src" "$PI_SKILLS_DIR/"
    echo "    $(basename "$src")  re-synced"
  fi
done
shopt -u nullglob

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

# Custom models (providers + model defs)
cp "$SCRIPT_DIR/home/models.json" "$HOME/.pi/agent/models.json" \
  && echo "    models.json  re-synced"

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

# Ponytail default mode (lite = active on coding tasks, names the lazier alternative).
# Repo copy is the source of truth — matches the live file written by
# Pi's /ponytail default command (~/.config/ponytail/config.json).
# diff first so rebuild --sync-only stays quiet when nothing changed.
if ! diff -q "$SCRIPT_DIR/home/ponytail.json" "$HOME/.config/ponytail/config.json" &>/dev/null; then
  mkdir -p "$HOME/.config/ponytail"
  cp "$SCRIPT_DIR/home/ponytail.json" "$HOME/.config/ponytail/config.json" \
    && echo "    ponytail.json  re-synced (defaultMode lite)"
fi

# i-have-adhd output style (opt-in via /i-have-adhd). Repo copy is the source of truth.
cp "$SCRIPT_DIR/home/i-have-adhd.json" "$HOME/.pi/agent/i-have-adhd.json" \
  && echo "    i-have-adhd.json  re-synced"

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
