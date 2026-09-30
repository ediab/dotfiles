#!/bin/bash
# Copy VPS shell configuration and ~/apps/AGENTS.md to an explicitly chosen host.
# VPS copies are not symlinked to this repo. This does not install upkeep scripts,
# services, timers, packages, or apt policy; existing operational assets stay put.
# VPS_HOST=<ssh-alias> overrides the target host (default: vps).

set -euo pipefail
[ "$#" -eq 0 ] || { echo "Usage: VPS_HOST=<host> $0" >&2; exit 1; }

HOST="${VPS_HOST:-vps}"
SRC="$(cd "$(dirname "$0")" && pwd)"
FILES=(.zshrc .zshenv .p10k.zsh .tmux.conf apps-AGENTS.md)
for f in "${FILES[@]}"; do
    [ -f "$SRC/$f" ] || { echo "Not found: $SRC/$f" >&2; exit 1; }
done

# Stage uploads away from live files. A failed transfer leaves configuration intact.
STAGE="$(ssh "$HOST" 'mktemp -d "$HOME/.dotfiles-vps.XXXXXX"')"
[ -n "$STAGE" ] || { echo "Could not create remote staging directory" >&2; exit 1; }
printf -v STAGE_ARG '%q' "$STAGE"
trap 'ssh "$HOST" "rm -rf -- $STAGE_ARG" >/dev/null 2>&1 || true' EXIT
for f in "${FILES[@]}"; do
    scp -q "$SRC/$f" "$HOST:$STAGE/$f"
done

ssh "$HOST" bash -s -- "$STAGE_ARG" <<'REMOTE'
set -euo pipefail
stage="$1"
mkdir -p "$HOME/apps"
for f in .zshrc .zshenv .p10k.zsh .tmux.conf apps-AGENTS.md; do
    target="$HOME/$f"
    [ "$f" != apps-AGENTS.md ] || target="$HOME/apps/AGENTS.md"
    if [ -e "$target" ] && [ ! -f "$target" ]; then
        echo "Not a regular configuration file: $target" >&2
        exit 1
    fi
    # Pin .zshrc's existing private mode, independent of the checkout's permissions.
    [ "$f" != .zshrc ] || chmod 600 "$stage/$f"
    if [ -f "$target" ]; then
        if cmp -s "$stage/$f" "$target"; then
            [ "$f" != .zshrc ] || chmod 600 "$target"
            continue
        fi
        backup="$(mktemp "$target.backup.XXXXXX")"
        cp -p "$target" "$backup"
        echo "Backed up $target -> $backup"
    fi
    mv -f "$stage/$f" "$target"
    echo "Copied $f -> $target"
done
# tmux caches configuration. Reload an existing server when available; do not start one.
tmux source-file "$HOME/.tmux.conf" 2>/dev/null || true
REMOTE

echo "Deployed configuration. zsh changes apply to new shells on $HOST."
