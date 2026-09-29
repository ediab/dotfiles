#!/bin/bash
# Deploy the VPS Herdr config from this repo to `ssh vps` and reload it there.
#
# Unlike the Mac, the VPS config is not symlinked: nothing on the VPS reads this
# repo, so run this after editing herdr/config.vps.toml.
#
#   HERDR_VPS_HOST=<ssh-alias>   override the target host (default: vps)

set -euo pipefail

HOST="${HERDR_VPS_HOST:-vps}"
SRC="$(cd "$(dirname "$0")" && pwd)/config.vps.toml"

if [ ! -f "$SRC" ]; then
    echo "Not found: $SRC" >&2
    exit 1
fi

scp -q "$SRC" "$HOST:~/.config/herdr/config.toml"
echo "Copied config.vps.toml to $HOST:~/.config/herdr/config.toml"

# Apply it to the running server. The JSON response carries any diagnostics.
# After a VPS reboot there is usually no server (nothing autostarts it there), and a fresh
# server reads config.toml at startup anyway — so a missing server is reported as deferred
# rather than failing. Failing here would hold the sync agent's change-stamp back and alert
# every hour. Any other reload error still fails loudly.
reload_status=0
response="$(ssh "$HOST" 'herdr server reload-config' 2>&1)" || reload_status=$?
printf '%s\n\n' "$response"
if [ "$reload_status" -eq 0 ]; then
    echo "Reload requested on $HOST."
elif printf '%s' "$response" | grep -q '"server_not_running"'; then
    echo "No herdr server running on $HOST — config deployed; it applies when one starts."
else
    echo "Reload FAILED on $HOST (exit $reload_status)." >&2
    exit "$reload_status"
fi
