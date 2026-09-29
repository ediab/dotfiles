#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/dotfiles-sync-vps-test.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT HUP INT TERM

fail() { echo "FAIL: $*" >&2; exit 1; }
contains() { grep -Fq "$2" "$1" || fail "expected '$2' in $1"; }

REPO="$WORK/repo"
TEST_HOME="$WORK/home"
FAKE_BIN="$WORK/bin"
STEP_LOG="$WORK/steps.log"
mkdir -p "$REPO/config/bin" "$REPO/config/vps" "$REPO/config/herdr" \
  "$REPO/config/druk" "$REPO/config/firefox" "$REPO/home" \
  "$TEST_HOME/.cache" "$FAKE_BIN"
cp "$ROOT/config/bin/sync-vps.sh" "$REPO/config/bin/sync-vps.sh"
chmod +x "$REPO/config/bin/sync-vps.sh"
: > "$REPO/home/settings.json"
: > "$REPO/config/vps/.input"
: > "$REPO/config/herdr/config.vps.toml"
: > "$REPO/config/druk/.input"
: > "$REPO/config/firefox/.excluded"

cat > "$FAKE_BIN/record-step" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$1" >> "$FAKE_STEP_LOG"
[ "${FAKE_FAIL_STEP:-}" != "$1" ]
EOF
cat > "$FAKE_BIN/terminal-notifier" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
chmod +x "$FAKE_BIN/record-step" "$FAKE_BIN/terminal-notifier"

make_deploy() {
  path="$1" name="$2"
  mkdir -p "$(dirname "$path")"
  cat > "$path" <<EOF
#!/usr/bin/env bash
exec "$FAKE_BIN/record-step" "$name"
EOF
  chmod +x "$path"
}
make_deploy "$REPO/deploy-vps.sh" agent-content
make_deploy "$REPO/config/vps/deploy-vps.sh" vps-dotfiles
make_deploy "$REPO/config/herdr/deploy-vps.sh" herdr
make_deploy "$REPO/config/druk/deploy-druk.sh" druk

run_sync() {
  HOME="$TEST_HOME" PATH="$FAKE_BIN:$PATH" FAKE_BIN="$FAKE_BIN" \
    FAKE_STEP_LOG="$STEP_LOG" FAKE_FAIL_STEP="${FAKE_FAIL_STEP:-}" \
    bash "$REPO/config/bin/sync-vps.sh" "$@"
}

STAMP="$TEST_HOME/.cache/sync-vps.stamp"
: > "$STAMP"
sleep 1
printf 'excluded input changed\n' >> "$REPO/config/firefox/.excluded"
: > "$STEP_LOG"
run_sync > "$WORK/no-change.out" 2>&1 || fail "unchanged deployed inputs should succeed"
[ ! -s "$STEP_LOG" ] || fail "unchanged deployed inputs ran deploy steps"
contains "$WORK/no-change.out" 'nothing to do'

expected="$WORK/expected.log"
printf 'agent-content\nvps-dotfiles\nherdr\ndruk\n' > "$expected"
: > "$STEP_LOG"
run_sync --force > "$WORK/success.out" 2>&1 || { cat "$WORK/success.out"; fail "forced sync"; }
cmp "$expected" "$STEP_LOG" || fail "forced sync steps were missing or out of order"
contains "$WORK/success.out" 'deployed: dotfiles agent content, VPS dotfiles, Herdr, druk'
success_stamp="$(date -r "$STAMP" +%s)"

sleep 1
: > "$STEP_LOG"
if FAKE_FAIL_STEP=vps-dotfiles run_sync --force > "$WORK/failure.out" 2>&1; then
  fail "a failed deploy step should fail the orchestrator"
fi
cmp "$expected" "$STEP_LOG" || fail "a failed step prevented a later step from running"
contains "$WORK/failure.out" '==> vps-dotfiles'
contains "$WORK/failure.out" 'FAILED (exit 1)'
[ "$(date -r "$STAMP" +%s)" = "$success_stamp" ] || fail "failed sync advanced the success stamp"

mv "$REPO/deploy-vps.sh" "$WORK/deploy-vps.missing"
sleep 1
: > "$STEP_LOG"
if run_sync --force > "$WORK/missing.out" 2>&1; then
  fail "missing top-level deploy entry point should fail"
fi
printf 'vps-dotfiles\nherdr\ndruk\n' > "$WORK/remaining-steps.log"
cmp "$WORK/remaining-steps.log" "$STEP_LOG" || fail "missing entry point skipped a later step"
contains "$WORK/missing.out" 'missing: '
contains "$WORK/missing.out" '(dotfiles checkout?)'
contains "$WORK/missing.out" 'agent-content SKIPPED (entrypoint missing)'
[ "$(date -r "$STAMP" +%s)" = "$success_stamp" ] || fail "missing deploy entry point advanced the success stamp"

mv "$WORK/deploy-vps.missing" "$REPO/deploy-vps.sh"
sleep 1
: > "$STEP_LOG"
run_sync --force > "$WORK/recovered.out" 2>&1 || { cat "$WORK/recovered.out"; fail "recovered forced sync"; }
cmp "$expected" "$STEP_LOG" || fail "recovered sync steps were missing or out of order"
[ "$(date -r "$STAMP" +%s)" -gt "$success_stamp" ] || fail "successful sync did not advance the stamp"

echo 'sync-vps tests passed.'
