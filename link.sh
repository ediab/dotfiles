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

link() { # link <repo-relative source> <destination>
  local src="$REPO/$1" dst="$2"
  [ -e "$src" ] || return 0   # not in the repo (yet)
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
      fi
    else swap "$src" "$dst"; fi
  elif [ -L "$dst" ] || [ ! -e "$dst" ]; then
    link "$1" "$dst"   # a concurrent run changed it while we compared
  else echo "SKIP $dst (differs from repo)"; skipped=1; fi
}

for f in settings web-search open-tui pi-btw mcp; do link "pi/$f.json" "$H/.pi/agent/$f.json"; done
link pi/pi-title.jsonc "$H/.pi/agent/pi-title.jsonc"   # .jsonc, so not in the loop above
for d in agents extensions themes; do link "pi/$d" "$H/.pi/agent/$d"; done
link pi/skills/code-review "$H/.pi/agent/skills/code-review"
link agents/AGENTS.md "$H/.pi/agent/AGENTS.md"
link agents/skills "$H/.agents/skills"   # Pi and Codex read this
if [ -d "$H/.claude" ]; then
  link agents/AGENTS.md "$H/.claude/CLAUDE.md"
  for f in settings.json statusline-command.sh; do link "claude/$f" "$H/.claude/$f"; done
  for d in "$REPO"/agents/skills/*/; do d="$(basename "$d")"; link "agents/skills/$d" "$H/.claude/skills/$d"; done
fi
if [ -d "$H/.codex" ]; then
  link agents/AGENTS.md "$H/.codex/AGENTS.md"
  for f in config.toml hooks.json; do link "codex/$f" "$H/.codex/$f"; done
fi
if [ "$(uname)" = Darwin ]; then
  for f in .zshrc .zprofile .zshenv .tmux.conf; do link "config/$f" "$H/$f"; done
  for f in starship.toml topgrade.toml ghostty/config herdr/config.toml herdr-auto-title/config.env rpiv-advisor/advisor.json; do link "config/$f" "$H/.config/$f"; done
  for f in settings keybindings; do link "config/vscode/$f.json" "$H/Library/Application Support/Code/User/$f.json"; done
fi
flush

# Remove links into the repo whose skill was deleted or renamed
for p in "$H"/.claude/skills/* "$H"/.pi/agent/skills/*; do
  [ -L "$p" ] && [ ! -e "$p" ] || continue
  case "$(readlink "$p")" in "$REPO"/*) echo "remove broken $p"; rm -f "$p";; esac
done

# Retired links: pi-subagents keeps runtime config in extensions/subagent/config.json
for p in "$H/.pi/agent/subagents.json"; do
  [ -L "$p" ] && [ ! -e "$p" ] || continue
  case "$(readlink "$p")" in "$REPO"/*) echo "remove retired $p"; rm -f "$p";; esac
done
exit "$skipped"
