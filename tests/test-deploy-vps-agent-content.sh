#!/usr/bin/env bash
set -eo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/dotfiles-vps-test.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT HUP INT TERM

fail() { echo "FAIL: $*" >&2; exit 1; }
contains() { grep -Fq "$2" "$1" || fail "expected '$2' in $1"; }
not_contains() { grep -Fq "$2" "$1" && fail "did not expect '$2' in $1" || true; }

REAL_RSYNC="$(command -v rsync)"
LOCAL_HOME="$WORK/local-home"
REMOTE_HOME="$WORK/remote-home"
FAKE_BIN="$WORK/bin"
mkdir -p "$LOCAL_HOME/.pi/agent" "$REMOTE_HOME/.pi/agent/skills/personal-workflow" "$FAKE_BIN"
printf '%s\n' '{"packages":[]}' > "$LOCAL_HOME/.pi/agent/settings.json"
printf '%s\n' '{"localAuth":true}' > "$LOCAL_HOME/.pi/agent/auth.json"
printf '%s\n' '{"packages":[],"old":true}' > "$REMOTE_HOME/.pi/agent/settings.json"
printf '%s\n' '{"remoteAuth":true}' > "$REMOTE_HOME/.pi/agent/auth.json"
cp -R "$ROOT/home/skills/personal-workflow/." "$REMOTE_HOME/.pi/agent/skills/personal-workflow/"
mkdir -p "$REMOTE_HOME/.pi/agent/skills/vps-foreign"
printf 'keep foreign\n' > "$REMOTE_HOME/.pi/agent/skills/vps-foreign/KEEP"

cat > "$FAKE_BIN/ssh" <<'EOF'
#!/usr/bin/env bash
set -eo pipefail
shift # host
export HOME="$FAKE_REMOTE_HOME"
if [ "${1:-}" = "bash" ] && [ "${2:-}" = "-s" ]; then
  exec bash -s
fi
exec bash -c "$*"
EOF

cat > "$FAKE_BIN/rsync" <<'EOF'
#!/usr/bin/env bash
set -eo pipefail
args=()
for arg in "$@"; do
  case "$arg" in
    *:\~/*)
      suffix="${arg#*:\~/}"
      arg="$FAKE_REMOTE_HOME/$suffix"
      mkdir -p "$(dirname "$arg")"
      ;;
  esac
  args+=("$arg")
done
exec "$REAL_RSYNC" "${args[@]}"
EOF
cp "$ROOT/tests/fake-pi.py" "$FAKE_BIN/pi"
chmod +x "$FAKE_BIN/ssh" "$FAKE_BIN/rsync" "$FAKE_BIN/pi"

run_deploy() {
  HOME="$LOCAL_HOME" PATH="$FAKE_BIN:$PATH" FAKE_REMOTE_HOME="$REMOTE_HOME" \
    REAL_RSYNC="$REAL_RSYNC" FAKE_PI_HELPER="$ROOT/reconcile-pi-packages.py" \
    FAKE_PI_LOG="$WORK/pi.log" FAKE_PI_FAIL_REMOVE="${FAKE_PI_FAIL_REMOVE:-}" \
    PYTHONDONTWRITEBYTECODE=1 bash "$ROOT/deploy-vps.sh" fake-vps
}

# Existing old-style skills without a manifest require explicit adoption and
# stop before settings, auth, packages, or other live config is changed.
if run_deploy > "$WORK/output" 2>&1; then
  fail "deploy succeeded without a VPS ownership manifest"
fi
contains "$WORK/output" 'ownership manifest missing; explicit one-time adoption is required'
contains "$WORK/output" 'sync-agent-content.sh --adopt --yes'
contains "$REMOTE_HOME/.pi/agent/settings.json" '"old":true'
contains "$REMOTE_HOME/.pi/agent/auth.json" '"remoteAuth":true'
[ ! -e "$REMOTE_HOME/.agents/skills/bro" ] || fail "missing-manifest preflight deployed shared skills"
contains "$REMOTE_HOME/.pi/agent/skills/vps-foreign/KEEP" 'keep foreign'

# The explicit approved migration creates this machine's manifest.
HOME="$REMOTE_HOME" bash "$REMOTE_HOME/.cache/pi-dotfiles-agent-content/sync-agent-content.sh" \
  --adopt --yes > "$WORK/adopt-output" 2>&1 || { cat "$WORK/adopt-output"; fail "approved VPS adoption"; }
[ -f "$REMOTE_HOME/.local/state/pi-dotfiles/managed-paths" ] || fail "adoption did not create manifest"

# After adoption, routine deploys preflight and then apply managed updates automatically.
printf '\nstale remote copy\n' >> "$REMOTE_HOME/.agents/skills/tdd/SKILL.md"
printf '%s\n' '{"packages":[],"new":true}' > "$LOCAL_HOME/.pi/agent/settings.json"
printf '%s\n' '{"newAuth":true}' > "$LOCAL_HOME/.pi/agent/auth.json"
run_deploy > "$WORK/output" 2>&1 || { cat "$WORK/output"; fail "post-adoption automatic deploy"; }
contains "$REMOTE_HOME/.pi/agent/settings.json" '"new": true'
contains "$REMOTE_HOME/.pi/agent/auth.json" '"newAuth":true'
not_contains "$REMOTE_HOME/.agents/skills/tdd/SKILL.md" 'stale remote copy'
contains "$REMOTE_HOME/.pi/agent/skills/vps-foreign/KEEP" 'keep foreign'

# Non-empty reconciliation: an object removal failure must fail the whole deploy.
# A subsequent deploy keeps cleanup history and installs a filtered exact pin.
mkdir -p "$REMOTE_HOME/.pi/agent/npm/node_modules/retired" \
  "$REMOTE_HOME/.pi/agent/npm/node_modules/foreign"
printf '%s\n' '{"version":"1.0.0"}' > "$REMOTE_HOME/.pi/agent/npm/node_modules/retired/package.json"
printf '%s\n' '{"version":"1.0.0"}' > "$REMOTE_HOME/.pi/agent/npm/node_modules/foreign/package.json"
printf '%s\n' '{"packages":[{"source":"npm:retired","extensions":[]}]}' > "$REMOTE_HOME/.pi/agent/settings.json"
printf '%s\n' '{"packages":[{"source":"npm:rotation@1.5.3","extensions":["+dist/index.js"]}],"new":true}' > "$LOCAL_HOME/.pi/agent/settings.json"
if FAKE_PI_FAIL_REMOVE=npm:retired run_deploy > "$WORK/package-failure.out" 2>&1; then
  fail "deploy swallowed package removal failure"
fi
contains "$WORK/package-failure.out" 'Package reconciliation failed'
not_contains "$WORK/package-failure.out" 'done. vps synced'
[ -f "$REMOTE_HOME/.pi/agent/settings.json.pre-reconcile" ] || fail "failed cleanup lost its ledger"
run_deploy > "$WORK/package-retry.out" 2>&1 || { cat "$WORK/package-retry.out"; fail "package retry deploy"; }
[ ! -e "$REMOTE_HOME/.pi/agent/settings.json.pre-reconcile" ] || fail "successful cleanup kept pending state"
[ ! -e "$REMOTE_HOME/.pi/agent/npm/node_modules/retired" ] || fail "retry did not remove retired object package"
[ -f "$REMOTE_HOME/.pi/agent/npm/node_modules/foreign/package.json" ] || fail "cleanup touched undeclared package"
python3 - "$REMOTE_HOME" "$WORK/pi.log" <<'PY'
import json, pathlib, sys
home = pathlib.Path(sys.argv[1])
settings = json.loads((home / '.pi/agent/settings.json').read_text())
assert settings['packages'] == [{'source': 'npm:rotation@1.5.3', 'extensions': ['+dist/index.js']}]
assert json.loads((home / '.pi/agent/npm/node_modules/rotation/package.json').read_text())['version'] == '1.5.3'
calls = [json.loads(line)['argv'][:2] for line in pathlib.Path(sys.argv[2]).read_text().splitlines()]
assert calls == [['remove', 'npm:retired'], ['remove', 'npm:retired'], ['install', 'npm:rotation@1.5.3']], calls
PY

# A later unmanaged collision fails preflight before settings/auth are changed.
grep -v '^\.agents/skills/bro$' "$REMOTE_HOME/.local/state/pi-dotfiles/managed-paths" \
  > "$WORK/managed-paths"
mv "$WORK/managed-paths" "$REMOTE_HOME/.local/state/pi-dotfiles/managed-paths"
printf '%s\n' '{"packages":[],"blocked":true}' > "$LOCAL_HOME/.pi/agent/settings.json"
printf '%s\n' '{"blockedAuth":true}' > "$LOCAL_HOME/.pi/agent/auth.json"
if run_deploy > "$WORK/output" 2>&1; then
  fail "deploy succeeded with an unmanaged collision"
fi
contains "$WORK/output" 'unmanaged collision for bro'
contains "$WORK/output" 'no approved copy action'
contains "$REMOTE_HOME/.pi/agent/settings.json" '"new": true'
not_contains "$REMOTE_HOME/.pi/agent/settings.json" '"blocked": true'
contains "$REMOTE_HOME/.pi/agent/auth.json" '"newAuth":true'
not_contains "$REMOTE_HOME/.pi/agent/auth.json" '"blockedAuth":true'

echo 'deploy-vps agent-content tests passed.'
