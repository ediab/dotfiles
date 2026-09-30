#!/usr/bin/env bash
# Isolated SSH/rsync fixture: no live VPS or local agent configuration is touched.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/dotfiles-vps-test.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT HUP INT TERM
fail() { echo "FAIL: $*" >&2; exit 1; }
contains() { grep -Fq "$2" "$1" || fail "expected '$2' in $1"; }

REPO="$WORK/repo"
LOCAL_HOME="$WORK/local-home"
REMOTE_HOME="$WORK/remote-home"
FAKE_BIN="$WORK/bin"
REAL_RSYNC="$(command -v rsync)"
mkdir -p "$REPO" "$FAKE_BIN" "$LOCAL_HOME/.pi/agent" "$REMOTE_HOME/.pi/agent/skills/personal-workflow"
cp -R "$ROOT/home" "$REPO/home"
for script in deploy-vps.sh apply.sh sync-agent-content.sh lint-agent-content.sh; do cp "$ROOT/$script" "$REPO/"; done
cp -R "$REPO/home/shared-skills/personal-workflow/." "$REMOTE_HOME/.pi/agent/skills/personal-workflow/"
printf '%s\n' '{"theme":"fixture-source","deviceId":"source-id","packages":["npm:source"]}' > "$REPO/home/settings.json"
printf '%s\n' '{"theme":"local-only","packages":["npm:local"]}' > "$LOCAL_HOME/.pi/agent/settings.json"
printf '%s\n' '{"theme":"old","deviceId":"remote-id","packages":["npm:remote"]}' > "$REMOTE_HOME/.pi/agent/settings.json"
printf 'remote credentials stay local\n' > "$REMOTE_HOME/.pi/agent/auth.json"
printf 'local credentials must not transfer\n' > "$LOCAL_HOME/.pi/agent/auth.json"
printf 'remote preview state\n' > "$REMOTE_HOME/.pi/agent/code-previews.json"
printf 'pending package ledger\n' > "$REMOTE_HOME/.pi/agent/settings.json.pre-reconcile"
mkdir -p "$REMOTE_HOME/.pi/agent/extensions" "$REMOTE_HOME/.pi/agent/themes" "$REMOTE_HOME/.pi/agent/skills/foreign"
printf 'Herdr owns this\n' > "$REMOTE_HOME/.pi/agent/extensions/herdr-agent-state.ts"
printf '%s\n' '{"name":"foreign"}' > "$REMOTE_HOME/.pi/agent/themes/foreign.json"
printf 'foreign skill\n' > "$REMOTE_HOME/.pi/agent/skills/foreign/KEEP"

cat > "$FAKE_BIN/ssh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" >> "$SSH_LOG"
shift
export HOME="$FAKE_REMOTE_HOME"
exec bash -c "$*"
EOF
cat > "$FAKE_BIN/rsync" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
args=()
for arg in "$@"; do
  case "$arg" in *:\~/*) arg="$FAKE_REMOTE_HOME/${arg#*:\~/}" ;; esac
  args+=("$arg")
done
exec "$REAL_RSYNC" "${args[@]}"
EOF
for command in pi npm brew apt-get git curl sudo systemctl; do
  printf '#!/bin/sh\necho forbidden >> "$FORBIDDEN_LOG"\nexit 99\n' > "$FAKE_BIN/$command"
done
chmod +x "$FAKE_BIN/"*
export REAL_RSYNC FAKE_REMOTE_HOME="$REMOTE_HOME" SSH_LOG="$WORK/ssh.log" FORBIDDEN_LOG="$WORK/forbidden.log"
run_deploy() { HOME="$LOCAL_HOME" PATH="$FAKE_BIN:$PATH" bash "$REPO/deploy-vps.sh" "$@"; }

# Missing remote ownership stops before any native config or skill writes.
if run_deploy fake-vps > "$WORK/output" 2>&1; then fail 'missing manifest accepted'; fi
contains "$WORK/output" 'ownership manifest missing'
contains "$REMOTE_HOME/.pi/agent/settings.json" '"theme":"old"'
[ ! -e "$REMOTE_HOME/.agents/skills/bro" ] || fail 'preflight copied skills'

run_deploy --prepare-agent-content fake-vps > "$WORK/output" 2>&1
contains "$WORK/output" 'sync-agent-content.sh --adopt --yes'
HOME="$REMOTE_HOME" bash "$REMOTE_HOME/.cache/pi-dotfiles-agent-content/sync-agent-content.sh" --adopt --yes > "$WORK/adopt" 2>&1
run_deploy fake-vps > "$WORK/output" 2>&1 || { cat "$WORK/output"; fail 'configuration deployment'; }
python3 - "$REMOTE_HOME" "$REPO" <<'PY'
import json
from pathlib import Path
import sys
home, repo = map(Path, sys.argv[1:])
agent = home / '.pi/agent'
settings = json.loads((agent / 'settings.json').read_text())
assert settings == {'theme':'fixture-source', 'deviceId':'remote-id', 'packages':['npm:remote']}, settings
assert (agent / 'auth.json').read_text() == 'remote credentials stay local\n'
assert (agent / 'code-previews.json').read_text() == 'remote preview state\n'
assert (agent / 'settings.json.pre-reconcile').read_text() == 'pending package ledger\n'
assert (agent / 'extensions/herdr-agent-state.ts').read_text() == 'Herdr owns this\n'
assert (agent / 'themes/foreign.json').exists()
assert (agent / 'skills/foreign/KEEP').read_text() == 'foreign skill\n'
assert (home / '.agents/skills/personal-workflow/SKILL.md').exists()
assert not (agent / 'skills/personal-workflow').exists()
for name in ('terminal.json','terminal-tinted.json','LICENSE'):
    assert (agent / 'themes' / name).read_bytes() == (repo / 'home/themes' / name).read_bytes()
web = json.loads((agent / 'web-search.json').read_text())
assert web['tinyfishApiKey'] == '!cat "$HOME/.pi/agent/tinyfish-api-key"'
PY
[ ! -e "$WORK/forbidden.log" ] || fail 'software/Git/service command executed'

# Ownership collisions stop all config changes, and preflight never enables adoption.
cp "$REMOTE_HOME/.pi/agent/settings.json" "$WORK/settings-before"
grep -v '^\.agents/skills/bro$' "$REMOTE_HOME/.local/state/pi-dotfiles/managed-paths" > "$WORK/manifest"
mv "$WORK/manifest" "$REMOTE_HOME/.local/state/pi-dotfiles/managed-paths"
printf '%s\n' '{"theme":"blocked"}' > "$REPO/home/settings.json"
if run_deploy fake-vps > "$WORK/output" 2>&1; then fail 'unmanaged collision accepted'; fi
contains "$WORK/output" 'unmanaged collision for bro'
cmp "$WORK/settings-before" "$REMOTE_HOME/.pi/agent/settings.json" || fail 'collision changed settings'

# Invalid source JSON and invalid CLI input fail before even staging over SSH.
: > "$WORK/ssh.log"
printf '{broken\n' > "$REPO/home/web-search.json"
if run_deploy fake-vps > "$WORK/output" 2>&1; then fail 'invalid source JSON accepted'; fi
[ ! -s "$WORK/ssh.log" ] || fail 'invalid source contacted host'
if run_deploy --unknown > "$WORK/output" 2>&1; then fail 'unknown argument accepted'; fi
[ ! -e "$WORK/forbidden.log" ] || fail 'forbidden side effect'
echo 'configuration-only VPS deployment tests passed.'
