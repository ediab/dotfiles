#!/usr/bin/env bash
# Merge selected druk settings and copy pi-opener configuration, without installing
# extensions. extensions.txt is an inventory, not an installation request.
# deploy-druk.sh: local only; DEPLOY_DRUK_HOST=<host>: local + explicit remote copy.
# Keep bash-3.2-safe.

set -euo pipefail
[ "$#" -eq 0 ] || { echo "Usage: DEPLOY_DRUK_HOST=<host> $0" >&2; exit 1; }
SRC="$(cd "$(dirname "$0")" && pwd)"
HOST="${DEPLOY_DRUK_HOST:-}"
for f in settings.partial.json pi-opener.config.yaml; do
    [ -f "$SRC/$f" ] || { echo "Not found: $SRC/$f" >&2; exit 1; }
done

# The same merge runs locally and remotely. Validate both objects before any writes:
# only a missing live file is an empty configuration, never malformed/unreadable JSON.
configure() {
  "$@" <<'PY'
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile

def reject_constant(value):
    raise ValueError("Invalid JSON constant: " + value)

partial_path, opener_source = map(Path, sys.argv[1:])
partial = json.loads(partial_path.read_text(), parse_constant=reject_constant)
path = Path("~/.config/druk/config.json").expanduser().resolve()
try:
    live = json.loads(path.read_text(), parse_constant=reject_constant)
except FileNotFoundError:
    live = {}
if not isinstance(partial, dict) or not isinstance(live, dict):
    raise ValueError("druk partial and live settings must both be JSON objects")
opener = opener_source.read_bytes()
merged = {**live, **partial}

def replace(path, content):
    if path.exists() and path.read_bytes() == content:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(content)
        if path.exists():
            os.chmod(temporary, stat.S_IMODE(path.stat().st_mode))
            backup_fd, backup = tempfile.mkstemp(prefix=path.name + ".backup.", dir=path.parent)
            os.close(backup_fd)
            shutil.copy2(path, backup)
            print("  backed up %s -> %s" % (path, backup))
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print("  wrote %s" % path)

# Compare serialized values so false and 0 (or true and 1) stay distinct JSON types.
# Preserve existing formatting when the selected settings already match.
content = json.dumps(merged, indent=2, allow_nan=False) + "\n"
if not path.exists() or content != json.dumps(live, indent=2, allow_nan=False) + "\n":
    replace(path, content.encode())
replace(Path("~/.config/pi-opener/config.yaml").expanduser().resolve(), opener)
print("  merged %d selected settings -> %s" % (len(partial), path))
PY
}

echo "==> local druk settings and pi-opener configuration"
configure python3 - "$SRC/settings.partial.json" "$SRC/pi-opener.config.yaml"
if [ -n "$HOST" ]; then
    STAGE="$(ssh "$HOST" 'mktemp -d "$HOME/.dotfiles-druk.XXXXXX"')"
    [ -n "$STAGE" ] || { echo "Could not create remote staging directory" >&2; exit 1; }
    printf -v STAGE_ARG '%q' "$STAGE"
    trap 'ssh "$HOST" "rm -rf -- $STAGE_ARG" >/dev/null 2>&1 || true' EXIT
    scp -q "$SRC/settings.partial.json" "$HOST:$STAGE/settings.partial.json"
    scp -q "$SRC/pi-opener.config.yaml" "$HOST:$STAGE/pi-opener.config.yaml"
    printf -v PARTIAL_ARG '%q' "$STAGE/settings.partial.json"
    printf -v OPENER_ARG '%q' "$STAGE/pi-opener.config.yaml"
    echo "==> remote druk settings and pi-opener configuration ($HOST)"
    configure ssh "$HOST" python3 - "$PARTIAL_ARG" "$OPENER_ARG"
fi

echo "Done. druk picks up settings on next launch. No extensions were installed."
