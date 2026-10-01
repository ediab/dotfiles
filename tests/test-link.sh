#!/usr/bin/env bash
# link.sh against a fake HOME and a throwaway copy of the repo layout. Never touches the real HOME.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(cd "$(mktemp -d "${TMPDIR:-/tmp}/dotfiles-link-test.XXXXXX")" && pwd -P)"
trap 'rm -rf "$WORK"' EXIT HUP INT TERM
fail() { echo "FAIL: $*" >&2; exit 1; }
REPO="$WORK/repo"
DARWIN=0; [ "$(uname)" = Darwin ] && DARWIN=1

mkrepo() {
  rm -rf "$REPO"; mkdir -p "$REPO"
  cp "$ROOT/link.sh" "$REPO/"
  mkdir -p "$REPO"/agents/skills/{alpha,beta} "$REPO"/pi/{agents,extensions,themes,skills/code-review} \
    "$REPO"/claude "$REPO"/codex "$REPO"/config/{ghostty,herdr,rpiv-advisor,vscode}
  echo policy > "$REPO/agents/AGENTS.md"
  echo alpha > "$REPO/agents/skills/alpha/SKILL.md"; echo beta > "$REPO/agents/skills/beta/SKILL.md"
  echo review > "$REPO/pi/skills/code-review/SKILL.md"
  echo agent > "$REPO/pi/agents/worker.md"; echo ext > "$REPO/pi/extensions/env-loader.ts"; echo theme > "$REPO/pi/themes/t.json"
  for f in settings web-search subagents open-tui pi-btw; do echo "{\"$f\":1}" > "$REPO/pi/$f.json"; done  # no mcp.json on purpose
  echo '{}' > "$REPO/claude/settings.json"; echo '#!/bin/sh' > "$REPO/claude/statusline-command.sh"
  echo model > "$REPO/codex/config.toml"; echo '{}' > "$REPO/codex/hooks.json"
  for f in .zshrc .zprofile .zshenv .tmux.conf starship.toml ghostty/config herdr/config.toml rpiv-advisor/advisor.json vscode/settings.json vscode/keybindings.json; do
    echo "$f" > "$REPO/config/$f"
  done
}
mkhome() { H="$WORK/home"; rm -rf "$H"; mkdir -p "$H/.claude" "$H/.codex"; }
run() { HOME="$H" bash "$REPO/link.sh" "$@"; }
points() { [ -L "$1" ] && [ "$(readlink "$1")" = "$REPO/$2" ] || fail "$1 does not point at $2 (is: $(readlink "$1" 2>/dev/null || echo none))"; }
expect_status() { # expect_status <code> <message>; uses $out and $rc from the last run
  [ "$rc" = "$1" ] || fail "$2: exit $rc, wanted $1; output: $out"
}
go() { rc=0; out="$(run 2>&1)" || rc=$?; }
all_links() {
  points "$H/.pi/agent/settings.json" pi/settings.json
  for f in web-search subagents open-tui pi-btw; do points "$H/.pi/agent/$f.json" pi/$f.json; done
  for d in agents extensions themes; do points "$H/.pi/agent/$d" pi/$d; done
  points "$H/.pi/agent/skills/code-review" pi/skills/code-review
  points "$H/.pi/agent/AGENTS.md" agents/AGENTS.md
  points "$H/.agents/skills" agents/skills
  points "$H/.claude/CLAUDE.md" agents/AGENTS.md; points "$H/.codex/AGENTS.md" agents/AGENTS.md
  points "$H/.claude/settings.json" claude/settings.json
  points "$H/.claude/statusline-command.sh" claude/statusline-command.sh
  points "$H/.codex/config.toml" codex/config.toml; points "$H/.codex/hooks.json" codex/hooks.json
  for s in alpha beta; do points "$H/.claude/skills/$s" agents/skills/$s; done
  if [ "$DARWIN" = 1 ]; then
    for f in .zshrc .zprofile .zshenv .tmux.conf; do points "$H/$f" config/$f; done
    points "$H/.config/starship.toml" config/starship.toml
    points "$H/.config/ghostty/config" config/ghostty/config
    points "$H/.config/rpiv-advisor/advisor.json" config/rpiv-advisor/advisor.json
    points "$H/Library/Application Support/Code/User/keybindings.json" config/vscode/keybindings.json
  fi
}

echo "1. nothing there: create parents and link; missing repo source is not an error"
mkrepo; mkhome; go; expect_status 0 fresh; all_links
[ ! -e "$H/.pi/agent/mcp.json" ] || fail 'mcp.json should not exist'
[ "$DARWIN" = 1 ] || [ ! -e "$H/.zshrc" ] || fail 'config links must be macOS-only'

echo "2. already correct: leave alone, print nothing, write nothing"
before="$(cd "$H" && find . -type l -exec stat -f '%i %m %N' {} + 2>/dev/null || find . -type l -printf '%i %T@ %p\n')"
sleep 1; go; expect_status 0 rerun; [ -z "$out" ] || fail "rerun printed: $out"
after="$(cd "$H" && find . -type l -exec stat -f '%i %m %N' {} + 2>/dev/null || find . -type l -printf '%i %T@ %p\n')"
[ "$before" = "$after" ] || fail 'rerun rewrote links'

echo "3. other symlink: replaced"
ln -sfn /nonexistent/elsewhere "$H/.pi/agent/settings.json"; ln -sfn "$WORK" "$H/.pi/agent/themes"
go; expect_status 0 relink; all_links

echo "4. identical real file/folder: replaced by the link"
rm "$H/.pi/agent/settings.json" "$H/.pi/agent/themes" "$H/.agents/skills"
cp "$REPO/pi/settings.json" "$H/.pi/agent/settings.json"; cp -R "$REPO/pi/themes" "$H/.pi/agent/themes"; cp -R "$REPO/agents/skills" "$H/.agents/skills"
go; expect_status 0 identical; all_links
ls "$H/.pi/agent" | grep -q '\.old\.' && fail 'aside copy left behind' || true

echo "5. anything else: SKIP, untouched, exit 1, other links still made"
rm "$H/.pi/agent/settings.json" "$H/.pi/agent/themes" "$H/.codex/config.toml" "$H/.claude/skills/beta"
echo mine > "$H/.pi/agent/settings.json"
mkdir "$H/.pi/agent/themes"; echo mine > "$H/.pi/agent/themes/custom.json"
echo mine > "$H/.codex/config.toml"
mkdir "$H/.claude/skills/beta"; echo mine > "$H/.claude/skills/beta/SKILL.md"
go; expect_status 1 differs
for p in .pi/agent/settings.json .codex/config.toml; do
  echo "$out" | grep -Fq "SKIP $H/$p (differs from repo)" || fail "no SKIP line for $p: $out"
  [ ! -L "$H/$p" ] && [ "$(cat "$H/$p")" = mine ] || fail "$p was touched"
done
echo "$out" | grep -Fq "SKIP $H/.pi/agent/themes" || fail 'no SKIP for themes folder'
echo "$out" | grep -Fq "SKIP $H/.claude/skills/beta" || fail 'no SKIP for beta folder'
[ ! -L "$H/.pi/agent/themes" ] && [ -f "$H/.pi/agent/themes/custom.json" ] || fail 'themes folder was touched'
points "$H/.pi/agent/web-search.json" pi/web-search.json; points "$H/.claude/skills/alpha" agents/skills/alpha

echo "6. client skips: no ~/.claude or ~/.codex"
mkhome; rmdir "$H/.claude" "$H/.codex"; go; expect_status 0 noclients
[ ! -e "$H/.claude" ] && [ ! -e "$H/.codex" ] || fail 'created client folders'
points "$H/.pi/agent/AGENTS.md" agents/AGENTS.md; points "$H/.agents/skills" agents/skills

echo "7. broken-link cleanup"
mkhome; go; expect_status 0 setup
ln -s "$REPO/agents/skills/gone" "$H/.claude/skills/gone"; ln -s "$REPO/pi/skills/gone" "$H/.pi/agent/skills/gone"
ln -s /nowhere/else "$H/.claude/skills/foreign-broken"; mkdir "$H/.claude/skills/synced"; echo x > "$H/.claude/skills/synced/f"
go; expect_status 0 cleanup
[ ! -e "$H/.claude/skills/gone" ] && [ ! -L "$H/.claude/skills/gone" ] || fail 'broken Claude link kept'
[ ! -L "$H/.pi/agent/skills/gone" ] || fail 'broken Pi link kept'
[ -L "$H/.claude/skills/foreign-broken" ] && [ -f "$H/.claude/skills/synced/f" ] || fail 'removed something not ours'
points "$H/.claude/skills/alpha" agents/skills/alpha

echo "8. skill added under ~/.agents/skills lands in the repo and gets a Claude link on the next run"
mkdir "$H/.agents/skills/gamma"; echo gamma > "$H/.agents/skills/gamma/SKILL.md"
[ -f "$REPO/agents/skills/gamma/SKILL.md" ] || fail 'new skill not in repo'
[ ! -e "$H/.claude/skills/gamma" ] || fail 'Claude link appeared before a run'
go; expect_status 0 gamma; points "$H/.claude/skills/gamma" agents/skills/gamma
cat "$H/.claude/skills/gamma/SKILL.md" | grep -q gamma || fail 'Claude link does not resolve'

echo "9. a deleted skill loses its Claude link"
rm -rf "$REPO/agents/skills/gamma"; go; expect_status 0 delete
[ ! -L "$H/.claude/skills/gamma" ] || fail 'link to deleted skill kept'

echo "9b. a run killed between moving a folder aside and linking: next run recovers"
mkhome; go; expect_status 0 setup9b
rm "$H/.claude/skills/alpha"; cp -R "$REPO/agents/skills/alpha" "$H/.claude/skills/alpha.old.123"   # state after the aside, before the link
go; expect_status 0 recover; points "$H/.claude/skills/alpha" agents/skills/alpha

echo "10. two simultaneous runs (ROUNDS, default 5; mixed starting states)"
for i in $(seq 1 "${ROUNDS:-5}"); do
  mkhome; mkdir -p "$H/.pi/agent" "$H/.claude/skills"
  cp -R "$REPO/pi/themes" "$H/.pi/agent/themes"           # identical folder
  ln -s /nowhere "$H/.pi/agent/settings.json"              # other symlink
  cp "$REPO/pi/subagents.json" "$H/.pi/agent/subagents.json" # identical file
  ( run > "$WORK/a.out" 2>&1; echo $? > "$WORK/a.rc" ) &
  ( run > "$WORK/b.out" 2>&1; echo $? > "$WORK/b.rc" ) &
  wait
  [ "$(cat "$WORK/a.rc")" = 0 ] && [ "$(cat "$WORK/b.rc")" = 0 ] || fail "round $i: exit $(cat "$WORK/a.rc")/$(cat "$WORK/b.rc"): $(cat "$WORK/a.out" "$WORK/b.out")"
  if grep -Eiq 'skip|fail|error|no such|cannot' "$WORK/a.out" "$WORK/b.out"; then fail "round $i: $(cat "$WORK/a.out" "$WORK/b.out")"; fi
  all_links
  find "$H" -name '*.tmp.*' -o -name '*.old.*' | grep -q . && fail "round $i: leftovers"
done

echo "PASS"
