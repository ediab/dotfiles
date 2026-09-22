#!/usr/bin/env bash
# pi-dotfiles — install the pi coding-agent harness + Elias's packages + skills.
# Does NOT install MCPs, auth keys, or provider/model settings.
set -euo pipefail

# Skills bundled in this repo under home/skills (whole directories, including subdocs, plus any
# top-level files such as ATTRIBUTION.md).
# Add/remove a skill by adding/removing its directory under home/skills/; no script edit needed.

# Custom extensions bundled in this repo under home/extensions.
# Everything under that directory is copied to pi's extensions directory; no script edit needed.

# Resolve the repo root (works for clone+run and curl|bash via $0).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
PI_SKILLS_DIR="$HOME/.pi/agent/skills"   # note: 'agent' singular — the path pi scans

echo "==> 1/4  pi harness"
if command -v pi >/dev/null 2>&1; then
  echo "    pi already installed ($(pi --version 2>/dev/null || echo unknown)); skipping"
else
  echo "    installing via npm..."
  if ! npm install -g --ignore-scripts @earendil-works/pi-coding-agent; then
    echo "    npm failed; falling back to curl installer..."
    curl -fsSL https://pi.dev/install.sh | sh
  fi
  command -v pi >/dev/null 2>&1 || { echo "    ERROR: pi still not on PATH"; exit 1; }
fi

echo "==> 2/4  packages (canonical list = home/settings.json, auto-synced from live by sync-settings.sh)"

# Deploy canonical pi agent settings.json from this repo as the base; pi install
# below appends each installed package into it. Live edits to settings.json are
# re-synced back into the repo automatically by sync-settings.sh (launchd).
cp "$SCRIPT_DIR/home/settings.json" "$HOME/.pi/agent/settings.json" \
  && echo "    settings.json  deployed" \
  || echo "    FAILED: home/settings.json"

# Packages to install = string entries in settings.json's packages array (the same
# list deploy-vps.sh reconciles against). No separate PACKAGES array to drift.
PKGS="$(python3 - "$SCRIPT_DIR/home/settings.json" <<'PY'
import json, sys
print("\n".join(p for p in json.load(open(sys.argv[1]))["packages"] if isinstance(p, str)))
PY
)"
if [ -z "$PKGS" ]; then
  echo "    WARNING: no package list found in home/settings.json (clone the repo for the full set)"
fi
for pkg in $PKGS; do
  pi install "$pkg" || echo "  FAILED: $pkg  (rerun: pi install $pkg)"
done

# apt/brew packages used by the harness/workflows (gh: GitHub CLI for repo tasks).
APT_PACKAGES=(gh)
for pkg in "${APT_PACKAGES[@]}"; do
  if ! command -v "$pkg" >/dev/null 2>&1; then
    if command -v apt-get >/dev/null 2>&1; then
      sudo apt-get install -y "$pkg" || echo "  FAILED: $pkg (rerun: sudo apt-get install -y $pkg)"
    elif command -v brew >/dev/null 2>&1; then
      brew install "$pkg" || echo "  FAILED: $pkg (rerun: brew install $pkg)"
    else
      echo "  SKIPPED: $pkg (no apt-get/brew on this host)"
    fi
  else
    echo "    apt: $pkg already installed"
  fi
done

echo "==> 3/4  skills (every dir + top-level file in $SCRIPT_DIR/home/skills/) + extensions + AGENTS.md seed + ponytail default"
mkdir -p "$PI_SKILLS_DIR"
shopt -s nullglob
for src in "$SCRIPT_DIR/home/skills"/*/; do
  skill="$(basename "$src")"
  rm -rf "$PI_SKILLS_DIR/$skill"
  cp -R "$SCRIPT_DIR/home/skills/$skill" "$PI_SKILLS_DIR/"
  echo "    $skill  installed"
done
# Top-level files in home/skills/ (e.g. ATTRIBUTION.md) deploy beside the skill dirs.
for src in "$SCRIPT_DIR/home/skills/"*; do
  if [ -f "$src" ]; then
    cp "$src" "$PI_SKILLS_DIR/"
    echo "    $(basename "$src")  installed"
  fi
done
shopt -u nullglob

PI_EXTENSIONS_DIR="$HOME/.pi/agent/extensions"
if [ -d "$SCRIPT_DIR/home/extensions" ]; then
  mkdir -p "$PI_EXTENSIONS_DIR"
  cp -R "$SCRIPT_DIR/home/extensions/." "$PI_EXTENSIONS_DIR/"
  echo "    extensions  installed"
fi

# Custom agents (pi-subagents): every .md in home/agents/ → ~/.pi/agent/agents/. Add/remove by file; no script edit needed.
PI_AGENTS_DIR="$HOME/.pi/agent/agents"
mkdir -p "$PI_AGENTS_DIR"
shopt -s nullglob
for src in "$SCRIPT_DIR/home/agents/"*.md; do
  cp "$src" "$PI_AGENTS_DIR/"
  echo "    $(basename "$src")  installed"
done
shopt -u nullglob

# Custom models (providers + model defs)
cp "$SCRIPT_DIR/home/models.json" "$HOME/.pi/agent/models.json" \
  && echo "    models.json  installed"

# Subagent defaults (tintinweb pi-subagents global settings; pi never writes this file)
cp "$SCRIPT_DIR/home/subagents.json" "$HOME/.pi/agent/subagents.json" \
  && echo "    subagents.json  installed"

# Open-TUI config (footer segments, telemetry toggles, thinking peek).
# Repo copy is the source of truth.
cp "$SCRIPT_DIR/home/open-tui.json" "$HOME/.pi/agent/open-tui.json" \
  && echo "    open-tui.json  installed"

# pi-btw side-thread config (model, thinking level). Repo copy is the source
# of truth. pi-btw only creates the live file after a Settings change, so a
# fresh copy must exist for the versioned defaults to take effect.
cp "$SCRIPT_DIR/home/pi-btw.json" "$HOME/.pi/agent/pi-btw.json" \
  && echo "    pi-btw.json  installed"

# Ponytail default mode (lite = active on coding tasks, names the lazier alternative).
# Repo copy is the source of truth; Pi's /ponytail default command also writes
# ~/.config/ponytail/config.json on this machine.
mkdir -p "$HOME/.config/ponytail"
cp "$SCRIPT_DIR/home/ponytail.json" "$HOME/.config/ponytail/config.json" \
  && echo "    ponytail.json  installed (defaultMode lite)"

# Seed ~/.pi/agent/AGENTS.md from the sanitized repo copy. Only when absent — never clobber
# local-only sections like VPS access details.
if [ ! -f "$HOME/.pi/agent/AGENTS.md" ] && [ -f "$SCRIPT_DIR/home/AGENTS.md" ]; then
  cp "$SCRIPT_DIR/home/AGENTS.md" "$HOME/.pi/agent/AGENTS.md"
  echo "    AGENTS.md  seeded (add any local-only sections, e.g. VPS access, manually)"
else
  echo "    AGENTS.md  already present — left untouched (local edits preserved)"
fi

# i-have-adhd output style (opt-in via /i-have-adhd). Repo copy is the source of truth.
cp "$SCRIPT_DIR/home/i-have-adhd.json" "$HOME/.pi/agent/i-have-adhd.json" \
  && echo "    i-have-adhd.json  installed (alwaysOn off)"

echo "==> 4/4  launchd auto-sync agent (settings.json live -> repo)"
# com.pi-dotfiles.sync-settings.plist is a template: bootstrap.sh substitutes the repo
# path and $HOME (launchd doesn't expand ~). Skipped under curl|bash (no plist).
if command -v launchctl >/dev/null 2>&1 && [ -f "$SCRIPT_DIR/com.pi-dotfiles.sync-settings.plist" ]; then
  LAUNCH_AGENT_DIR="$HOME/Library/LaunchAgents"
  LAUNCH_AGENT="$LAUNCH_AGENT_DIR/com.pi-dotfiles.sync-settings.plist"
  mkdir -p "$LAUNCH_AGENT_DIR"
  sed -e "s|__PI_DOTFILES_REPO__|$SCRIPT_DIR|g" \
      -e "s|__PI_HOME__|$HOME|g" \
      "$SCRIPT_DIR/com.pi-dotfiles.sync-settings.plist" > "$LAUNCH_AGENT"
  if grep -q '__PI_' "$LAUNCH_AGENT"; then
    echo "    WARNING: plist still has unsubstituted placeholders — auto-sync will fail"
  fi
  launchctl unload "$LAUNCH_AGENT" 2>/dev/null || true
  if launchctl load "$LAUNCH_AGENT"; then
    echo "    launchd agent installed: watches $HOME/.pi/agent/settings.json"
  else
    echo "    WARNING: launchctl load failed — auto-sync disabled (see /tmp/com.pi-dotfiles.sync-settings.err)"
  fi
else
  echo "    launchctl or template plist not available — auto-sync not installed"
fi

echo "==> verify"
command -v pi >/dev/null 2>&1 && echo "    pi: $(pi --version)" || echo "    pi: MISSING"
echo "    packages:"
pi list 2>/dev/null || echo "    pi list failed"
shopt -s nullglob
for src in "$SCRIPT_DIR/home/skills"/*/; do
  skill="$(basename "$src")"
  [ -f "$PI_SKILLS_DIR/$skill/SKILL.md" ] && echo "    ok: $skill" || echo "    MISSING: $skill"
done
for src in "$SCRIPT_DIR/home/skills/"*; do
  file="$(basename "$src")"
  if [ -f "$src" ]; then
    [ -f "$PI_SKILLS_DIR/$file" ] && echo "    ok: $file" || echo "    MISSING: $file"
  fi
done
shopt -u nullglob
shopt -s nullglob
for src in "$SCRIPT_DIR/home/extensions"/*; do
  extension="$(basename "$src")"
  [ -e "$PI_EXTENSIONS_DIR/$extension" ] && echo "    ok: $extension" || echo "    MISSING: $extension"
done
shopt -u nullglob
[ -f "$HOME/.pi/agent/AGENTS.md" ] && echo "    ok: AGENTS.md" || echo "    MISSING: AGENTS.md"

echo "==> done."
echo "    MCPs and auth keys were NOT installed — configure those separately."
