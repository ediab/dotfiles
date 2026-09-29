#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/dotfiles-capture-test.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT HUP INT TERM

fail() { echo "FAIL: $*" >&2; exit 1; }
contains() { grep -Fq "$2" "$1" || fail "expected '$2' in $1"; }

REAL_GIT="$(command -v git)"
export REAL_GIT

git() {
  if [ "${1:-}" = "push" ]; then
    printf 'push\n' >> "$CAPTURE_PUSH_LOG"
    if [ "${CAPTURE_PUSH_FAIL:-0}" = "1" ]; then
      echo 'simulated push failure' >&2
      return 1
    fi
    return 0
  fi
  "$REAL_GIT" "$@"
}
code() {
  printf '%s\n' "$*" >> "$CAPTURE_CODE_LOG"
  printf '%s\n' "${CAPTURE_CODE_OUTPUT:-extension.test}"
  [ "${CAPTURE_CODE_FAIL:-0}" != "1" ]
}
sleep() {
  [ "$1" = 5 ] || { echo "unexpected debounce: $*" >&2; return 1; }
  printf '%s\n' "$1" >> "$CAPTURE_SLEEP_LOG"
}
export -f git code sleep

REPO="$WORK/repo"
TEST_HOME="$WORK/home"
PUSH_LOG="$WORK/pushes.log"
CODE_LOG="$WORK/code.log"
SLEEP_LOG="$WORK/sleeps.log"
mkdir -p "$REPO/home" "$REPO/config/vscode" "$TEST_HOME/.pi/agent"
cp "$ROOT/capture.sh" "$REPO/capture.sh"
chmod +x "$REPO/capture.sh"
printf '{"settings":"base"}\n' > "$REPO/home/settings.json"
printf '{"open":"base"}\n' > "$REPO/home/open-tui.json"
printf 'extension.test\n' > "$REPO/config/vscode/extensions.txt"
printf 'tracked base\n' > "$REPO/config/tracked.txt"
printf 'unrelated base\n' > "$REPO/unrelated.txt"
cp "$REPO/home/settings.json" "$TEST_HOME/.pi/agent/settings.json"
cp "$REPO/home/open-tui.json" "$TEST_HOME/.pi/agent/open-tui.json"
"$REAL_GIT" -C "$REPO" init -q
"$REAL_GIT" -C "$REPO" config user.name 'Capture Test'
"$REAL_GIT" -C "$REPO" config user.email 'capture@example.invalid'
"$REAL_GIT" -C "$REPO" add home/settings.json home/open-tui.json config/tracked.txt \
  config/vscode/extensions.txt unrelated.txt
"$REAL_GIT" -C "$REPO" commit -qm 'initial'

run_capture() {
  HOME="$TEST_HOME" CAPTURE_PUSH_LOG="$PUSH_LOG" CAPTURE_CODE_LOG="$CODE_LOG" \
    CAPTURE_SLEEP_LOG="$SLEEP_LOG" CAPTURE_CODE_FAIL="${CAPTURE_CODE_FAIL:-0}" \
    CAPTURE_CODE_OUTPUT="${CAPTURE_CODE_OUTPUT:-extension.test}" \
    CAPTURE_PUSH_FAIL="${CAPTURE_PUSH_FAIL:-0}" \
    bash "$REPO/capture.sh"
}
assert_commit_paths() {
  "$REAL_GIT" -C "$REPO" diff-tree --no-commit-id --name-only -r HEAD > "$WORK/actual-paths"
  printf '%s\n' "$@" > "$WORK/expected-paths"
  cmp "$WORK/expected-paths" "$WORK/actual-paths" || fail "capture commit contained unexpected paths"
}
assert_unrelated_staged() {
  "$REAL_GIT" -C "$REPO" diff --cached --name-only > "$WORK/staged-paths"
  printf 'unrelated.txt\n' > "$WORK/expected-staged"
  cmp "$WORK/expected-staged" "$WORK/staged-paths" || fail "unrelated staged file was not preserved"
}

# Unchanged live/repo state produces no commit or push and does not refresh
# repository mtimes that the VPS orchestrator uses as its change signal.
touch -t 202001010000 "$REPO/home/settings.json" "$REPO/home/open-tui.json"
touch -t 202101010000 "$TEST_HOME/.pi/agent/settings.json" "$TEST_HOME/.pi/agent/open-tui.json"
base_head="$("$REAL_GIT" -C "$REPO" rev-parse HEAD)"
run_capture > "$WORK/no-change.out" 2>&1 || { cat "$WORK/no-change.out"; fail "no-change capture"; }
[ "$("$REAL_GIT" -C "$REPO" rev-parse HEAD)" = "$base_head" ] || fail "no-change capture made a commit"
[ ! -s "$PUSH_LOG" ] || fail "no-change capture pushed"
[ "$REPO/home/settings.json" -ot "$TEST_HOME/.pi/agent/settings.json" ] || fail "no-change capture refreshed settings mtime"
[ "$REPO/home/open-tui.json" -ot "$TEST_HOME/.pi/agent/open-tui.json" ] || fail "no-change capture refreshed open-tui mtime"

# One Pi setting is copied and committed; unrelated staged work remains staged.
printf '{"settings":"captured"}\n' > "$TEST_HOME/.pi/agent/settings.json"
printf 'unrelated staged edit\n' > "$REPO/unrelated.txt"
"$REAL_GIT" -C "$REPO" add unrelated.txt
run_capture > "$WORK/pi-capture.out" 2>&1 || { cat "$WORK/pi-capture.out"; fail "Pi settings capture"; }
cmp "$TEST_HOME/.pi/agent/settings.json" "$REPO/home/settings.json" || fail "Pi settings were not copied"
assert_commit_paths home/settings.json
assert_unrelated_staged
[ "$("$REAL_GIT" -C "$REPO" show -s --format=%s HEAD | cut -c1-5)" = 'auto:' ] || fail "capture commit lacks auto: prefix"
[ "$(wc -l < "$PUSH_LOG" | tr -d ' ')" = 1 ] || fail "successful capture did not push exactly once"

# A tracked config edit and Pi file are captured even when code fails; untracked
# config files and the prior unrelated staged file stay outside the commit.
printf 'tracked config edit\n' >> "$REPO/config/tracked.txt"
printf 'untracked config file\n' > "$REPO/config/untracked.txt"
printf '{"open":"captured"}\n' > "$TEST_HOME/.pi/agent/open-tui.json"
if CAPTURE_CODE_FAIL=1 CAPTURE_CODE_OUTPUT='partial failed output' run_capture > "$WORK/code-failure.out" 2>&1; then
  :
else
  cat "$WORK/code-failure.out"
  fail "code failure blocked capture"
fi
contains "$WORK/code-failure.out" 'could not refresh config/vscode/extensions.txt'
printf 'extension.test\n' > "$WORK/expected-extensions"
cmp "$WORK/expected-extensions" "$REPO/config/vscode/extensions.txt" || fail "failed code refresh replaced the existing list"
cmp "$TEST_HOME/.pi/agent/open-tui.json" "$REPO/home/open-tui.json" || fail "open-tui settings were not copied"
assert_commit_paths config/tracked.txt home/open-tui.json
assert_unrelated_staged
if "$REAL_GIT" -C "$REPO" ls-files --error-unmatch config/untracked.txt >/dev/null 2>&1; then
  fail "untracked config file was added"
fi
[ -f "$REPO/config/untracked.txt" ] || fail "untracked config file was removed"
[ "$(wc -l < "$PUSH_LOG" | tr -d ' ')" = 2 ] || fail "tracked config capture did not push"

# A failed push is non-fatal and leaves the local commit intact, without a later
# no-op capture amending it or retrying a push.
printf '{"settings":"local commit survives failed push"}\n' > "$TEST_HOME/.pi/agent/settings.json"
if CAPTURE_PUSH_FAIL=1 run_capture > "$WORK/push-failure.out" 2>&1; then
  :
else
  cat "$WORK/push-failure.out"
  fail "failed push made capture fail"
fi
contains "$WORK/push-failure.out" 'push failed; local capture commit retained'
assert_commit_paths home/settings.json
surviving_head="$("$REAL_GIT" -C "$REPO" rev-parse HEAD)"
[ "$(wc -l < "$PUSH_LOG" | tr -d ' ')" = 3 ] || fail "failed push was not attempted"
run_capture > "$WORK/final-no-change.out" 2>&1 || { cat "$WORK/final-no-change.out"; fail "post-push no-change capture"; }
[ "$("$REAL_GIT" -C "$REPO" rev-parse HEAD)" = "$surviving_head" ] || fail "no-op capture amended the local commit"
[ "$(wc -l < "$PUSH_LOG" | tr -d ' ')" = 3 ] || fail "no-op capture retried push"
assert_unrelated_staged
[ "$(wc -l < "$SLEEP_LOG" | tr -d ' ')" = 5 ] || fail "capture did not debounce each WatchPaths event by five seconds"
[ "$(wc -l < "$CODE_LOG" | tr -d ' ')" = 5 ] || fail "capture did not refresh extensions on each run"

echo 'capture tests passed.'
