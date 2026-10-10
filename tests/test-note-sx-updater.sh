#!/usr/bin/env bash
# Exercise the timer wrapper without sudo, Docker, or a service.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/note-sx-updater-test.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT HUP INT TERM
mkdir -p "$WORK/bin" "$WORK/home"
export CALLS="$WORK/sudo-calls.log"
cat > "$WORK/bin/sudo" <<'SH'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$CALLS"
exit "${SUDO_EXIT:-0}"
SH
chmod +x "$WORK/bin/sudo"
python3 - "$ROOT/config/vps/vps-update-images.sh" "$WORK/updater.sh" "$WORK/bin/sudo" <<'PY'
from pathlib import Path
import sys
source = Path(sys.argv[1]).read_text()
Path(sys.argv[2]).write_text(source.replace("/usr/bin/sudo", sys.argv[3]))
PY
chmod +x "$WORK/updater.sh"

HOME="$WORK/home" CALLS="$CALLS" bash "$WORK/updater.sh" --dry-run > "$WORK/dry.out"
[ ! -s "$CALLS" ] || { echo 'dry run called sudo' >&2; exit 1; }
grep -Fq 'dry_run=1' "$WORK/dry.out"
grep -Fq 'note-sx-deploy' "$WORK/dry.out"
HOME="$WORK/home" CALLS="$CALLS" bash "$WORK/updater.sh" > "$WORK/run.out"
[ "$(cat "$CALLS")" = '-n /usr/local/sbin/note-sx-deploy' ] || { echo 'unexpected root-helper argv' >&2; exit 1; }
: > "$CALLS"
if HOME="$WORK/home" CALLS="$CALLS" bash "$WORK/updater.sh" --locked > "$WORK/locked.out" 2>&1; then
  echo 'legacy flock re-exec was incorrectly accepted' >&2; exit 1
else
  [ "$?" -eq 75 ] || { echo 'legacy flock handoff returned the wrong status' >&2; exit 1; }
fi
[ ! -s "$CALLS" ] || { echo 'queued legacy caller invoked the root helper' >&2; exit 1; }
if HOME="$WORK/home" CALLS="$CALLS" bash "$WORK/updater.sh" --test-root > "$WORK/bad.out" 2>&1; then
  echo 'unexpected argument accepted' >&2
  exit 1
fi
[ ! -s "$CALLS" ] || { echo 'invalid argument invoked sudo' >&2; exit 1; }
: > "$CALLS"
if HOME="$WORK/home" CALLS="$CALLS" SUDO_EXIT=2 bash "$WORK/updater.sh" > "$WORK/held.out" 2>&1; then
  echo 'held status was lost by updater wrapper' >&2; exit 1
else
  [ "$?" -eq 2 ] || { echo 'held status was not propagated' >&2; exit 1; }
fi
echo 'note-sx updater wrapper: ok'
