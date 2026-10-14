#!/usr/bin/env bash
# vps-cleanup.sh — bounded weekly disk upkeep for the VPS.
#
#   vps-cleanup.sh            reclaim
#   vps-cleanup.sh --dry-run  print what would happen, change nothing
#
# Run by vps-cleanup.timer (Sunday 04:30, persistent) as `diab`. Deployed from the
# dotfiles repo's config/vps/ — edit there, not on the VPS.
#
# What it reclaims:
#   * Docker build cache, capped with --max-used-space (the older --keep-storage is now
#     an alias for reserved-space, which is a FLOOR, not a cap — using it silently failed
#     to bound anything). Never wiped: the app stacks rebuild locally on every push
#     (mp3podcasts, redact_pdf, cratch, onyx, greek_embassy_bot), so a cold
#     cache makes every deploy slow.
#   * Images are retained: unused images can be release candidates or rollback artifacts.
#   * Superseded GitHub runner versions and its downloaded update tarballs, the npm cache,
#     apt cache, and a journal cap.
#
# Never touched: ~/apps contents, Docker volumes, running containers, ~/.pi, node_modules,
# /swapfile. Idempotent — a second run reports nothing to do. Exits non-zero if any step
# failed, so the timer is not silently green.

set -uo pipefail

CACHE_CEILING="${CACHE_CEILING:-3GB}"
JOURNAL_CEILING="${JOURNAL_CEILING:-200M}"
LOG_DIR="$HOME/logs"
LOG="$LOG_DIR/vps-cleanup.log"
RUNNER_DIR="$HOME/actions-runner"
LOCK_FILE="$HOME/.cache/vps-deploy.lock"   # shared with ~/bin/vps-deploy.sh
FAILURES=0

DRY_RUN=0
LOCKED=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --locked)  LOCKED=1 ;;
    *) echo "usage: $0 [--dry-run]" >&2; exit 2 ;;
  esac
done

# mkdir BEFORE the tee, or the log pipe dies on a host without ~/logs.
mkdir -p "$LOG_DIR" "$(dirname "$LOCK_FILE")"

# The parent tees and the lock child inherits that stdout, so exactly one writer owns the
# log. The lock child itself must not tee again (that interleaves two writers).
if [ "$LOCKED" -eq 0 ]; then
  exec > >(tee -a "$LOG") 2>&1
fi

# Take the same lock as a push-to-deploy: image pruning must never race a build whose new
# image is tagged but not yet attached to a container.
if [ "$DRY_RUN" -eq 0 ] && [ "$LOCKED" -eq 0 ]; then
  # -E 75 tells a lock timeout apart from the locked run's own failure exit.
  rc=0; flock -w 540 -E 75 "$LOCK_FILE" "$0" --locked || rc=$?
  if [ "$rc" -eq 75 ]; then
    echo "could not take $LOCK_FILE within 540s (a deploy in progress?) — aborting" >&2
  fi
  exit "$rc"
fi

echo "=== vps-cleanup $(date -Is) dry_run=$DRY_RUN locked=$LOCKED ==="
df -h / | tail -1

# Run a step (or print it in dry-run); a failure is counted and reported instead of
# vanishing into the log.
attempt() {
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "  [dry-run] $*"
    return 0
  fi
  if "$@" ; then
    return 0
  fi
  echo "  FAILED: $*" >&2
  FAILURES=$((FAILURES + 1))
  return 0
}

# --- Docker: build cache, then images nothing uses -----------------------------------
if command -v docker >/dev/null 2>&1; then
  echo "--- docker build cache (cap $CACHE_CEILING) ---"
  if docker builder prune --help 2>&1 | grep -q -- "--max-used-space"; then
    attempt docker builder prune -f --max-used-space "$CACHE_CEILING"
  else
    echo "  bounded cache prune unavailable; leaving build cache in place"
    FAILURES=$((FAILURES + 1))
  fi

  # Release candidates and rollback images may have no container attached.
  # Their lifecycle belongs to the release/recovery owner, so routine upkeep
  # preserves every image reference.
  echo "--- docker images: retained for release and recovery ---"

else
  echo "--- docker not present, skipping ---"
fi

# --- GitHub runner: superseded versions and update tarballs ---------------------------
if [ -d "$RUNNER_DIR" ]; then
  echo "--- runner caches ---"
  # Keep the newest bin.<version>; the live service runs whatever runsvc.sh resolves to.
  while read -r old; do
    echo "  removing: $old"
    attempt rm -rf "$old"
  done < <(ls -d "$RUNNER_DIR"/bin.* 2>/dev/null | sort -V | head -n -1)
  if [ -d "$HOME/actions-runner-work/_update" ]; then
    echo "  removing: runner update tarballs"
    attempt rm -rf "$HOME/actions-runner-work/_update"
  fi
fi

# --- package and language caches -----------------------------------------------------
echo "--- caches ---"
if command -v npm >/dev/null 2>&1; then
  attempt npm cache clean --force
fi
if sudo -n true 2>/dev/null; then
  attempt sudo -n apt-get clean
  # --vacuum-size leaves the active journal file alone, so this is a soft cap.
  attempt sudo -n journalctl --vacuum-size="$JOURNAL_CEILING"
else
  echo "  skipping apt/journal: passwordless sudo unavailable"
  FAILURES=$((FAILURES + 1))
fi

echo "--- result ---"
df -h / | tail -1
docker system df 2>/dev/null | head -4

if [ "$FAILURES" -gt 0 ]; then
  echo "=== done with $FAILURES failed step(s) ==="
  exit 1
fi
echo "=== done ==="
