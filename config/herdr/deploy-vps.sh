#!/bin/bash
# Deploy the VPS Herdr config from this repo to `ssh vps` and reload it there.
#
# Unlike the Mac, the VPS Herdr config is not symlinked to the VPS dotfiles checkout,
# so run this after editing herdr/config.vps.toml.
#
#   HERDR_VPS_HOST=<ssh-alias>   override the target host (default: vps)

set -euo pipefail

HOST="${HERDR_VPS_HOST:-vps}"
SRC="$(cd "$(dirname "$0")" && pwd)/config.vps.toml"

if [ ! -f "$SRC" ]; then
    echo "Not found: $SRC" >&2
    exit 1
fi

# Stage beside the live file, keep the previous one as .backup, then swap in one rename,
# so a dropped transfer never leaves a truncated config behind.
scp -q "$SRC" "$HOST:~/.config/herdr/config.toml.new"
ssh "$HOST" 'cd ~/.config/herdr && { [ ! -f config.toml ] || cp -p config.toml config.toml.backup; } && mv -f config.toml.new config.toml'
echo "Copied config.vps.toml to $HOST:~/.config/herdr/config.toml (previous kept as config.toml.backup)"

# Apply it to the running server. The JSON response carries any diagnostics.
# herdr-server.service normally keeps a server running, but an explicit `herdr server stop`
# leaves it down, and a fresh server reads config.toml at startup anyway — so a missing
# server is a warning rather than a failure. Failing here would hold the sync agent's change-stamp back and alert
# every hour. Any other reload error still fails loudly.
reload_status=0
response="$(ssh "$HOST" 'herdr server reload-config' 2>&1)" || reload_status=$?
printf '%s\n\n' "$response"
if [ "$reload_status" -eq 0 ]; then
    echo "Reload requested on $HOST."
elif printf '%s' "$response" | grep -q '"server_not_running"'; then
    echo "WARNING: no herdr server running on $HOST — config deployed; it applies when one starts." >&2
    echo "  herdr-server.service should keep one up; check: ssh $HOST systemctl --user status herdr-server" >&2
else
    echo "Reload FAILED on $HOST (exit $reload_status)." >&2
    exit "$reload_status"
fi
