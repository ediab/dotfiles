#!/usr/bin/env bash
# Weekly note-sx refresh entry point. The root helper owns selection, locking,
# snapshots, digest pinning, activation, and recovery.
set -euo pipefail

LOG_DIR="$HOME/logs"
LOG="$LOG_DIR/vps-update-images.log"
mkdir -p "$LOG_DIR"
exec > >(tee -a "$LOG") 2>&1

case "$#:${1:-}" in
  0:) ;;
  1:--locked)
    echo "legacy flock handoff declined; retry through the root helper after the caller drains" >&2
    exit 75
    ;;
  1:--dry-run)
    echo "=== vps-update-images $(date -Is) dry_run=1 ==="
    echo "  [dry-run] sudo -n /usr/local/sbin/note-sx-deploy"
    exit 0
    ;;
  *) echo "usage: $0 [--dry-run]" >&2; exit 2 ;;
esac

echo "=== vps-update-images $(date -Is) ==="
exec /usr/bin/sudo -n /usr/local/sbin/note-sx-deploy
