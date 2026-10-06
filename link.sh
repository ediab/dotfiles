#!/usr/bin/env bash
# Link repo content into place. No flags; rerun any time; concurrent runs are safe.
# Per link: absent -> create; right link -> keep; other symlink -> replace; real file or
# folder identical to the repo -> replace; anything else -> SKIP (exit 1).
set -u
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"; H="$HOME"; skipped=0; pend=()

# Each link is made under a temp name, then renamed over its destination in one step with
# os.replace (mv would move a link into a linked folder). One python call per run, not per link.
flush() {
  [ ${#pend[@]} -gt 0 ] || return 0
  python3 -c 'import os, sys
a, bad = sys.argv[1:], 0
for t, d in zip(a[::2], a[1::2]):
    try: os.replace(t, d)
    except OSError as e: print("FAIL", d, e); os.unlink(t); bad = 1
sys.exit(bad)' "${pend[@]}" || skipped=1
  pend=()
}
swap() { ln -s "$1" "$2.tmp.$$" && pend+=("$2.tmp.$$" "$2") || { echo "FAIL $2"; skipped=1; }; }

# Leftovers of a run killed mid-swap carry its PID: drop a temp link, or a moved-aside folder
# that still matches the repo. Live PIDs belong to a concurrent run; leave those alone.
sweep() { # sweep <source> <destination>
  local p pid
  for p in "$2".tmp.* "$2".old.*; do
    [ -e "$p" ] || [ -L "$p" ] || continue
    pid="${p##*.}"; case "$pid" in ''|*[!0-9]*) continue ;; esac
    kill -0 "$pid" 2>/dev/null && continue
    if [ -L "$p" ]; then rm -f "$p"
    elif diff -rq "$1" "$p" >/dev/null 2>&1; then echo "remove leftover $p"; rm -rf "$p"
    else echo "SKIP $p (leftover differs from repo)"; skipped=1; fi
  done
}

link() { # link <repo-relative source> <destination>
  local src="$REPO/$1" dst="$2"
  [ -e "$src" ] || return 0   # not in the repo (yet)
  sweep "$src" "$dst"
  if [ -L "$dst" ]; then
    [ "$(readlink "$dst")" = "$src" ] || { echo "relink $dst"; swap "$src" "$dst"; }
  elif [ ! -e "$dst" ]; then
    echo "link $dst"; mkdir -p "$(dirname "$dst")"; swap "$src" "$dst"
  elif cmp -s "$src" "$dst" 2>/dev/null || { [ -d "$src" ] && diff -rq "$src" "$dst" >/dev/null 2>&1; }; then
    echo "link $dst (was identical)"
    if [ -d "$dst" ]; then  # a folder can't be renamed over: move it aside, link, drop it (mv loses a race: the other run links it)
      local old="$dst.old.$$"
      if mv "$dst" "$old" 2>/dev/null; then
        swap "$src" "$dst"; flush
        rm -rf "$old"   # was verified identical to src; the repo holds the content, so drop it even if the link failed
      elif [ -L "$dst" ] || [ ! -e "$dst" ]; then
        link "$1" "$dst"   # a concurrent run moved it first
      else echo "FAIL $dst (could not move it aside)"; skipped=1; fi
    else swap "$src" "$dst"; fi
  elif [ -L "$dst" ] || [ ! -e "$dst" ]; then
    link "$1" "$dst"   # a concurrent run changed it while we compared
  else echo "SKIP $dst (differs from repo)"; skipped=1; fi
}

# Pi writes machine-local keys into pi/settings.json: lastChangelogVersion after each update,
# deviceId (a per-machine login ID) on first use. Keep both out of git so pulls are not
# blocked and machines do not share one ID. Git config is per clone, so set it on every run.
if git -C "$REPO" rev-parse --git-dir >/dev/null 2>&1; then
  git -C "$REPO" config filter.pi-settings.clean "jq 'del(.lastChangelogVersion, .deviceId)'"
fi

platform="$(uname)"
case "$platform" in
  Darwin) claude_settings=settings.json; codex_config=config.toml ;;
  Linux) claude_settings=settings.linux.json; codex_config=config.linux.toml ;;
  *) echo "Unsupported platform: $platform" >&2; exit 1 ;;
esac

for f in settings herdr web-search pi-btw mcp; do link "pi/$f.json" "$H/.pi/agent/$f.json"; done
link pi/pi-title.jsonc "$H/.pi/agent/pi-title.jsonc"   # .jsonc, so not in the loop above
for d in agents extensions themes; do link "pi/$d" "$H/.pi/agent/$d"; done
for d in "$REPO"/pi/skills/*/; do d="$(basename "$d")"; link "pi/skills/$d" "$H/.pi/agent/skills/$d"; done
link agents/AGENTS.md "$H/.pi/agent/AGENTS.md"
link agents/skills "$H/.agents/skills"   # Pi and Codex read this
if [ -d "$H/.claude" ]; then
  link agents/AGENTS.md "$H/.claude/CLAUDE.md"
  link "claude/$claude_settings" "$H/.claude/settings.json"
  link claude/statusline-command.sh "$H/.claude/statusline-command.sh"
  for d in "$REPO"/agents/skills/*/; do d="$(basename "$d")"; link "agents/skills/$d" "$H/.claude/skills/$d"; done
fi
if [ -d "$H/.codex" ]; then
  link agents/AGENTS.md "$H/.codex/AGENTS.md"
  link "codex/$codex_config" "$H/.codex/config.toml"
  link codex/hooks.json "$H/.codex/hooks.json"
fi
if [ "$platform" = Darwin ]; then
  for f in .zshrc .zprofile .zshenv; do link "config/$f" "$H/$f"; done
  for f in starship.toml topgrade.toml ghostty/config herdr/config.toml herdr-auto-title/config.env; do link "config/$f" "$H/.config/$f"; done
  for f in settings keybindings; do link "config/vscode/$f.json" "$H/Library/Application Support/Code/User/$f.json"; done
  link "config/vscode/argv.json" "$H/.vscode/argv.json"
fi
flush

# Remove links into the repo whose skill was deleted or renamed
for p in "$H"/.claude/skills/* "$H"/.pi/agent/skills/*; do
  [ -L "$p" ] && [ ! -e "$p" ] || continue
  case "$(readlink "$p")" in "$REPO"/*) echo "remove broken $p"; rm -f "$p";; esac
done

# Retired links: cleanup for config files left by removed packages
for p in "$H/.pi/agent/subagents.json" "$H/.pi/agent/open-tui.json" "$H/.pi/agent/workflows"; do
  [ -L "$p" ] && [ ! -e "$p" ] || continue
  case "$(readlink "$p")" in "$REPO"/*) echo "remove retired $p"; rm -f "$p";; esac
done
exit "$skipped"
