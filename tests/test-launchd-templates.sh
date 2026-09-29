#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/dotfiles-launchd-test.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT HUP INT TERM

fail() { echo "FAIL: $*" >&2; exit 1; }

FAKE_ROOT="$WORK/fake repo"
FAKE_HOME="$WORK/fake home"
mkdir -p "$FAKE_ROOT" "$FAKE_HOME"
for name in com.diab.dotfiles.capture com.diab.sync-vps; do
  ! grep -Eq '/Users/eliasdiab|~/(dev|Dev)' "$ROOT/launchd/$name.plist" \
    || fail "personal checkout path in $name"
  sed -e "s|__DOTFILES_ROOT__|$FAKE_ROOT|g" \
      -e "s|__HOME__|$FAKE_HOME|g" \
      "$ROOT/launchd/$name.plist" > "$WORK/$name.plist"
  ! grep -Eq '__DOTFILES_ROOT__|__HOME__' "$WORK/$name.plist" || fail "placeholder remains in $name"
  plutil -lint "$WORK/$name.plist" || fail "$name did not pass plutil"
done

python3 - "$WORK/com.diab.dotfiles.capture.plist" "$WORK/com.diab.sync-vps.plist" \
  "$FAKE_ROOT" "$FAKE_HOME" <<'PY'
import plistlib, sys

capture_path, sync_path, root, home = sys.argv[1:]
with open(capture_path, "rb") as f:
    capture = plistlib.load(f)
with open(sync_path, "rb") as f:
    sync_vps = plistlib.load(f)

def check(condition, message):
    if not condition:
        raise SystemExit(message)

check(capture["Label"] == "com.diab.dotfiles.capture", "capture label mismatch")
check(capture["EnvironmentVariables"] == {"HOME": home}, "capture HOME mismatch")
check(capture["ProgramArguments"] == [root + "/capture.sh"], "capture path mismatch")
check(capture["ProgramArguments"][0].startswith(root + "/"), "capture path is outside fake root")
check(capture["StartInterval"] == 900, "capture interval mismatch")
check(capture["WatchPaths"] == [
    home + "/.pi/agent/settings.json",
    home + "/.pi/agent/open-tui.json",
], "capture WatchPaths mismatch")
check(capture["StandardOutPath"] == "/tmp/com.diab.dotfiles.capture.out", "capture stdout mismatch")
check(capture["StandardErrorPath"] == "/tmp/com.diab.dotfiles.capture.err", "capture stderr mismatch")

check(sync_vps["Label"] == "com.diab.sync-vps", "sync-vps label mismatch")
check(sync_vps["EnvironmentVariables"] == {"HOME": home}, "sync-vps HOME mismatch")
check(sync_vps["ProgramArguments"] == [root + "/config/bin/sync-vps.sh"], "sync-vps path mismatch")
check(sync_vps["ProgramArguments"][0].startswith(root + "/"), "sync-vps path is outside fake root")
check(sync_vps["StartInterval"] == 900, "sync-vps interval mismatch")
check(sync_vps["RunAtLoad"] is True, "sync-vps RunAtLoad missing")
check(sync_vps["StandardOutPath"] == "/tmp/com.diab.sync-vps.out", "sync-vps stdout mismatch")
check(sync_vps["StandardErrorPath"] == "/tmp/com.diab.sync-vps.err", "sync-vps stderr mismatch")
PY

# Exercise the installer in an isolated HOME with a fake launchctl; no live job is touched.
FAKE_BIN="$WORK/fake-bin"
INSTALL_HOME="$WORK/installer-home"
LAUNCHCTL_LOG="$WORK/launchctl.log"
mkdir -p "$FAKE_BIN" "$INSTALL_HOME"
cat > "$FAKE_BIN/launchctl" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$LAUNCHCTL_LOG"
case "$1" in
  bootout) exit 1 ;;
  bootstrap) exit 0 ;;
  *) exit 2 ;;
esac
EOF
chmod +x "$FAKE_BIN/launchctl"

HOME="$INSTALL_HOME" PATH="$FAKE_BIN:$PATH" LAUNCHCTL_LOG="$LAUNCHCTL_LOG" \
  bash "$ROOT/install-launchd.sh" capture > "$WORK/install-capture.out" 2>&1 \
  || { printf '%s\n' 'capture installer failed:'; printf '%s\n' "$(<"$WORK/install-capture.out")"; fail "capture installer"; }
HOME="$INSTALL_HOME" PATH="$FAKE_BIN:$PATH" LAUNCHCTL_LOG="$LAUNCHCTL_LOG" \
  bash "$ROOT/install-launchd.sh" sync-vps > "$WORK/install-sync-vps.out" 2>&1 \
  || { printf '%s\n' 'sync-vps installer failed:'; printf '%s\n' "$(<"$WORK/install-sync-vps.out")"; fail "sync-vps installer"; }

LAUNCH_AGENTS="$INSTALL_HOME/Library/LaunchAgents"
plutil -lint "$LAUNCH_AGENTS/com.diab.dotfiles.capture.plist" >/dev/null || fail "installed capture plist invalid"
plutil -lint "$LAUNCH_AGENTS/com.diab.sync-vps.plist" >/dev/null || fail "installed sync-vps plist invalid"
printf 'bootout gui/%s/com.diab.dotfiles.capture\nbootstrap gui/%s %s\nbootout gui/%s/com.diab.sync-vps\nbootstrap gui/%s %s\n' \
  "$UID" "$UID" "$LAUNCH_AGENTS/com.diab.dotfiles.capture.plist" \
  "$UID" "$UID" "$LAUNCH_AGENTS/com.diab.sync-vps.plist" > "$WORK/expected-launchctl.log"
cmp "$WORK/expected-launchctl.log" "$LAUNCHCTL_LOG" || fail "installer launchctl order/labels mismatch"

# The installer requires a component; callers cannot accidentally load both jobs.
if HOME="$INSTALL_HOME" PATH="$FAKE_BIN:$PATH" LAUNCHCTL_LOG="$LAUNCHCTL_LOG" \
  bash "$ROOT/install-launchd.sh" > "$WORK/usage.out" 2>&1; then
  fail "installer accepted a missing component"
fi

echo 'launchd template and installer tests passed.'
