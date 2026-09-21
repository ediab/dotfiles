#!/usr/bin/env bash
# pi-dotfiles — update pi + all installed packages, and re-sync bundled custom skills.
# For day-to-day updates on a machine already bootstrapped by bootstrap.sh.
# New machine? Use bootstrap.sh instead.
#   rebuild.sh              → full: pi update --all + settings.json + all bundled config
#   rebuild.sh --sync-only  → bundled config only (skills, extensions, agents, models,
#                             subagents, web-search, prompts); skips the package
#                             update and the settings.json copy — for skill/extension edits
set -euo pipefail

SYNC_ONLY=0
if [ "${1:-}" = "--sync-only" ]; then
  SYNC_ONLY=1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
PI_SKILLS_DIR="$HOME/.pi/agent/skills"
PI_EXTENSIONS_DIR="$HOME/.pi/agent/extensions"
# Skills deployed below = every dir in $SCRIPT_DIR/home/skills/ (whole-dir copies).
# Extensions are auto-discovered from home/extensions — every top-level .ts/.js file is a
# single-file extension, every subdirectory with an index.ts/index.js is a directory
# extension. Add/remove by file/dir; no script edit needed.
shopt -s nullglob
CUSTOM_EXTENSIONS=()
for src in "$SCRIPT_DIR/home/extensions/"*.ts "$SCRIPT_DIR/home/extensions/"*.js; do
  CUSTOM_EXTENSIONS+=("$(basename "${src%.*}")")
done
CUSTOM_EXTENSION_DIRS=()
for src in "$SCRIPT_DIR/home/extensions/"*/; do
  [ -f "$src/index.ts" ] || [ -f "$src/index.js" ] || continue
  CUSTOM_EXTENSION_DIRS+=("$(basename "$src")")
done
shopt -u nullglob

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
  # VPS package exclusions (Linux only — Mac keeps the full repo list): strip
  # excluded ids from the live settings.json so a repo list that includes them
  # never resurrects them here. All other live settings are left untouched.
  if [ "$(uname -s)" = "Linux" ] && [ -f "$SCRIPT_DIR/home/vps-package-exclude.txt" ]; then
    python3 - "$SCRIPT_DIR/home/vps-package-exclude.txt" <<'PY'
import json, os, sys
path = os.path.expanduser("~/.pi/agent/settings.json")
exc = {l.strip() for l in open(sys.argv[1]) if l.strip() and not l.startswith("#")}
d = json.load(open(path))
kept, dropped = [], []
for p in d.get("packages", []):
    (dropped if isinstance(p, str) and p in exc else kept).append(p)
d["packages"] = kept
json.dump(d, open(path, "w"), indent=2)
open(path, "a").write("\n")
for p in dropped:
    print(f"    ! {p} (vps-excluded)")
PY
    # Uninstall any excluded package still present on disk (keeps `pi list` clean).
    while IFS= read -r pkg; do
      case "$pkg" in ""|\#*) continue ;; esac
      case "$pkg" in
        npm:*)      dir="$HOME/.pi/agent/npm/node_modules/${pkg#npm:}" ;;
        git:*)      dir="$HOME/.pi/agent/git/${pkg#git:}" ;;
        https://*)  dir="$HOME/.pi/agent/git/${pkg#https://}" ;;
        *)          dir="" ;;
      esac
      if [ -n "$dir" ] && [ -e "$dir" ]; then
        echo "    - $pkg (vps-excluded, uninstalling)"
        pi uninstall "$pkg" || echo "    (uninstall failed — may not be removable)"
      fi
    done < "$SCRIPT_DIR/home/vps-package-exclude.txt"
  fi
fi

echo "==> 3/3  skills (every dir in $SCRIPT_DIR/home/skills/) + extensions (${#CUSTOM_EXTENSIONS[@]} total)"
mkdir -p "$PI_SKILLS_DIR"
shopt -s nullglob
for src in "$SCRIPT_DIR/home/skills"/*/; do
  skill="$(basename "$src")"
  rm -rf "$PI_SKILLS_DIR/$skill"
  cp -R "$SCRIPT_DIR/home/skills/$skill" "$PI_SKILLS_DIR/"
  echo "    $skill  re-synced"
done
shopt -u nullglob

mkdir -p "$PI_EXTENSIONS_DIR"
for ext in "${CUSTOM_EXTENSIONS[@]}"; do
  src="$SCRIPT_DIR/home/extensions/$ext.ts"
  [ -f "$src" ] || src="$SCRIPT_DIR/home/extensions/$ext.js"
  cp "$src" "$PI_EXTENSIONS_DIR/$(basename "$src")"
  echo "    $ext  re-synced"
done
if [ "${#CUSTOM_EXTENSION_DIRS[@]}" -gt 0 ]; then
  for ext in "${CUSTOM_EXTENSION_DIRS[@]}"; do
    src="$SCRIPT_DIR/home/extensions/$ext"
    mkdir -p "$PI_EXTENSIONS_DIR/$ext"
    cp -R "$src/". "$PI_EXTENSIONS_DIR/$ext/"
    echo "    $ext/  re-synced"
  done
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

# Prompt templates: every .md in home/prompts/ → ~/.pi/agent/prompts/. Add/remove by file; no script edit needed.
PI_PROMPTS_DIR="$HOME/.pi/agent/prompts"
mkdir -p "$PI_PROMPTS_DIR"
shopt -s nullglob
for src in "$SCRIPT_DIR/home/prompts/"*.md; do
  cp "$src" "$PI_PROMPTS_DIR/"
  echo "    $(basename "$src")  re-synced"
done
shopt -u nullglob

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

echo "==> done."
