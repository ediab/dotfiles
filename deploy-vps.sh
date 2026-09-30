#!/usr/bin/env bash
# Explicit agent-configuration deployment. No packages, credentials, or runtime mirroring.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PREPARE=0
if [ "${1:-}" = "--prepare-agent-content" ]; then
  PREPARE=1
  shift
fi
[ "$#" -le 1 ] || { echo 'Usage: deploy-vps.sh [--prepare-agent-content] [host]' >&2; exit 2; }
HOST="${1:-vps}"
case "$HOST" in ''|-*|*[!a-zA-Z0-9_.@-]*) echo 'Invalid SSH host/alias' >&2; exit 2 ;; esac
REMOTE_STAGE='.cache/pi-dotfiles-agent-content'

"$ROOT/lint-agent-content.sh"
STAGE="$(mktemp -d "${TMPDIR:-/tmp}/dotfiles-vps-stage.XXXXXX")"
trap 'rm -rf "$STAGE"' EXIT HUP INT TERM
mkdir -p "$STAGE/home"
cp "$ROOT/apply.sh" "$ROOT/sync-agent-content.sh" "$ROOT/lint-agent-content.sh" "$STAGE/"
cp "$ROOT/home/AGENTS.md" "$STAGE/home/"
for directory in shared-skills skills instructions agents extensions themes; do
  if [ -d "$ROOT/home/$directory" ]; then
    cp -R "$ROOT/home/$directory" "$STAGE/home/"
  fi
done
for file in settings.json web-search.json subagents.json open-tui.json pi-btw.json; do
  cp "$ROOT/home/$file" "$STAGE/home/"
done
# Keep the remote credential lookup remote; never read or transfer the credential.
python3 - "$STAGE/home" <<'PY'
import json
from pathlib import Path
import sys
root = Path(sys.argv[1])
def reject_constant(value):
    raise ValueError(f'Invalid JSON constant: {value}')
for name in ('settings.json', 'web-search.json', 'subagents.json', 'open-tui.json', 'pi-btw.json'):
    value = json.loads((root / name).read_text(), parse_constant=reject_constant)
    if not isinstance(value, dict):
        raise ValueError(f'{name} must be a JSON object')
    if name == 'web-search.json':
        value['tinyfishApiKey'] = '!cat "$HOME/.pi/agent/tinyfish-api-key"'
        (root / name).write_text(json.dumps(value, indent=2) + '\n')
PY

echo '==> stage configuration only; native config has not been changed'
ssh "$HOST" "mkdir -p \"\$HOME/$REMOTE_STAGE\""
# Deletion is restricted to this dedicated staging directory, never native skill/config roots.
rsync -az --delete "$STAGE/" "$HOST:~/$REMOTE_STAGE/"
if [ "$PREPARE" = 1 ]; then
  printf 'Dry run: ssh %s %s\n' "$HOST" "bash ~/.cache/pi-dotfiles-agent-content/sync-agent-content.sh --adopt"
  printf 'Only after approval: ssh %s %s\n' "$HOST" "bash ~/.cache/pi-dotfiles-agent-content/sync-agent-content.sh --adopt --yes"
  exit 0
fi
if ! ssh "$HOST" 'test -f "$HOME/.local/state/pi-dotfiles/managed-paths"'; then
  echo 'ERROR: ownership manifest missing; explicit one-time adoption is required' >&2
  echo 'Stage with --prepare-agent-content, then review and approve the remote helper adoption.' >&2
  exit 1
fi

# The same local apply path preflights ALL selected files and managed content before writes.
# Settings preserve this host's runtime IDs/proxy/session paths and package declarations.
ssh "$HOST" "bash \"\$HOME/$REMOTE_STAGE/apply.sh\" --group configs --group agents --group extensions --group themes --group agent-content"
ssh "$HOST" "bash \"\$HOME/$REMOTE_STAGE/apply.sh\" --group configs --group agents --group extensions --group themes --group agent-content --yes"
echo '==> done. VPS configuration applied; credentials and installed software were untouched.'
