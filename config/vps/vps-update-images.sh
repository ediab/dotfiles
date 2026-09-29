#!/usr/bin/env bash
# vps-update-images.sh — weekly refresh of the VPS's third-party container images.
#
#   vps-update-images.sh            refresh
#   vps-update-images.sh --dry-run  print what would run, change nothing
#
# Run by vps-update-images.timer (Sunday 05:30, persistent) as `diab`. Deployed from the
# configs repo — edit there, not on the VPS.
#
# Scope: only projects whose runtime is a published image.
#   note-sx      ghcr.io/note-sx/server:latest   (its push-to-deploy step is the same pull)
#   karakeep-app ghcr.io/karakeep-app/karakeep:release
# Everything else on the box is a local build deployed from git by the push-to-deploy
# workflow (mp3podcasts, redact_pdf, cratch/ai-cookbook, onyx, greek_embassy_bot) and is
# deliberately not touched here. ~/apps/termix (guacd) has no compose file checked out, so
# it cannot be managed this way at all.
#
# Safety, in order:
#   1. the whole run takes the SAME flock as ~/bin/vps-deploy.sh, so an image refresh can
#      never interleave with a push-to-deploy of the same project;
#   2. the project is STOPPED first and its data snapshotted (3 generations kept), then the
#      snapshot is verified with `tar -tzf` — restoring an image does not undo a database
#      migration, and a torn tar of a live SQLite file is not a way back at all. If the
#      snapshot is missing or unreadable the project is restarted and left untouched;
#   3. the current image IDs are recorded; if the project is not healthy afterwards, those
#      IDs are re-tagged and the project recreated from them.

set -uo pipefail

APPS_DIR="$HOME/apps"
LOG_DIR="$HOME/logs"
LOG="$LOG_DIR/vps-update-images.log"
SNAP_ROOT="$HOME/backups"
LOCK_FILE="$HOME/.cache/vps-deploy.lock"   # shared with ~/bin/vps-deploy.sh
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-150}"
PROJECTS=(note-sx karakeep-app)
SNAPSHOT_TARGET=""

DRY_RUN=0
LOCKED=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --locked)  LOCKED=1 ;;
    *) echo "usage: $0 [--dry-run]" >&2; exit 2 ;;
  esac
done

mkdir -p "$LOG_DIR" "$SNAP_ROOT" "$(dirname "$LOCK_FILE")"
# Only the outermost process tees: the flock re-exec inherits this stdout, so teeing in
# both would interleave two writers into one log file.
if [ "$LOCKED" -eq 0 ]; then
  exec > >(tee -a "$LOG") 2>&1
fi
echo "=== vps-update-images $(date -Is) dry_run=$DRY_RUN locked=$LOCKED ==="

run() {
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "  [dry-run] $*"
  else
    "$@"
  fi
}

compose_file_for() {
  local dir="$1" candidate
  for candidate in docker-compose.yml docker-compose.yaml compose.yaml compose.yml; do
    if [ -f "$dir/$candidate" ]; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

# Keep the 3 newest snapshots for an app, drop the rest (the new one is newest by mtime).
rotate_snapshots() {
  local app_dir="$1"
  ls -1t "$app_dir"/*.tgz 2>/dev/null | tail -n +4 | while read -r old; do
    echo "  rotating out $(basename "$old")"
    run rm -f "$old"
  done
}

# Snapshot an app's data with its containers stopped. Karakeep keeps everything in a Docker
# volume (root-only, hence sudo); note-sx keeps db/ and userfiles/ inside its checkout.
# Sets SNAPSHOT_TARGET on success; a failed or partial tar is deleted, never left behind as
# something the next run could mistake for a usable backup.
snapshot_data() {
  local project="$1" stamp target rc=0
  stamp="$(date +%Y%m%d-%H%M%S)"
  mkdir -p "$SNAP_ROOT/$project"

  case "$project" in
    karakeep-app)
      target="$SNAP_ROOT/$project/data-$stamp.tgz"
      echo "  snapshot: karakeep-app_data -> $(basename "$target")"
      if [ "$DRY_RUN" -eq 1 ]; then
        echo "  [dry-run] sudo -n tar -czf $target -C /var/lib/docker/volumes/karakeep-app_data/_data ."
      else
        sudo -n tar -czf "$target" -C /var/lib/docker/volumes/karakeep-app_data/_data . || rc=1
      fi
      ;;
    note-sx)
      target="$SNAP_ROOT/$project/state-$stamp.tgz"
      echo "  snapshot: db/ + userfiles/ -> $(basename "$target")"
      if [ "$DRY_RUN" -eq 1 ]; then
        echo "  [dry-run] tar -czf $target -C $APPS_DIR/$project db userfiles"
      else
        tar -czf "$target" -C "$APPS_DIR/$project" db userfiles || rc=1
      fi
      ;;
    *)
      echo "  no snapshot rule for '$project' — refusing to refresh it" >&2
      return 1
      ;;
  esac

  if [ "$rc" -ne 0 ]; then
    echo "  warning: snapshot failed" >&2
    [ "$DRY_RUN" -eq 0 ] && rm -f "$target"
    return 1
  fi

  SNAPSHOT_TARGET="$target"
  rotate_snapshots "$SNAP_ROOT/$project"
  return 0
}

record_image_ids() {
  local dir="$1" out="$2" ref id
  : > "$out"
  while read -r ref; do
    [ -n "$ref" ] || continue
    id="$(docker image inspect --format '{{.Id}}' "$ref" 2>/dev/null || true)"
    [ -n "$id" ] && printf '%s %s\n' "$id" "$ref" >> "$out"
  done < <(docker compose --project-directory "$dir" config --images 2>/dev/null | sort -u)
}

# Every container of the project present and running, and healthy where a healthcheck
# exists. `ps -aq` so a container that failed to come up is counted, not skipped.
project_is_healthy() {
  local dir="$1" ids state cid
  ids="$(docker compose --project-directory "$dir" ps -aq 2>/dev/null)"
  [ -n "$ids" ] || return 1
  for cid in $ids; do
    state="$(docker inspect --format '{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{end}}' "$cid" 2>/dev/null)"
    case "$state" in
      "running "|"running healthy") ;;
      *) echo "    not healthy: $cid ($state)"; return 1 ;;
    esac
  done
  return 0
}

wait_for_health() {
  local dir="$1" waited=0
  while [ "$waited" -lt "$HEALTH_TIMEOUT" ]; do
    project_is_healthy "$dir" && return 0
    sleep 5
    waited=$((waited + 5))
  done
  return 1
}

refresh_project() {
  local project="$1" dir ids_file pull_status=0
  dir="$APPS_DIR/$project"
  ids_file="$(mktemp)"

  echo "--- $project ($dir) ---"
  if ! compose_file_for "$dir" >/dev/null; then
    echo "  no compose file — skipping"
    rm -f "$ids_file"
    return 0
  fi

  record_image_ids "$dir" "$ids_file"
  echo "  recorded image IDs:"; sed 's/^/    /' "$ids_file"

  # Quiesce before snapshotting. Containers come back below (or immediately, if the
  # snapshot turns out unusable).
  echo "  stopping containers for a consistent snapshot"
  run docker compose --project-directory "$dir" stop

  SNAPSHOT_TARGET=""
  snapshot_data "$project" || true

  if [ "$DRY_RUN" -eq 0 ]; then
    if [ -z "$SNAPSHOT_TARGET" ] || [ ! -s "$SNAPSHOT_TARGET" ] || ! tar -tzf "$SNAPSHOT_TARGET" >/dev/null 2>&1; then
      echo "  snapshot missing or unreadable — restarting and refusing to pull" >&2
      docker compose --project-directory "$dir" up -d
      rm -f "$ids_file"
      return 1
    fi
    echo "  snapshot verified: $(basename "$SNAPSHOT_TARGET") ($(du -h "$SNAPSHOT_TARGET" | cut -f1))"
  fi

  if [ "$DRY_RUN" -eq 1 ]; then
    echo "  [dry-run] docker compose --project-directory $dir pull"
  else
    # A pull can fail for one pinned image while the rest succeed (e.g. a registry that
    # now demands billing). Report it instead of silently leaving that image stale, but
    # keep going: `up -d` still uses the images already on disk.
    docker compose --project-directory "$dir" pull || pull_status=$?
    [ "$pull_status" -ne 0 ] && echo "  warning: pull exited $pull_status — continuing with local images" >&2
  fi
  run docker compose --project-directory "$dir" up -d

  if [ "$DRY_RUN" -eq 1 ]; then
    rm -f "$ids_file"
    return 0
  fi

  if wait_for_health "$dir"; then
    echo "  ok: healthy"
    rm -f "$ids_file"
    return 0
  fi

  echo "  FAILED health check — rolling back to the recorded images"
  while read -r id ref; do
    [ -n "${id:-}" ] || continue
    echo "    restoring $ref -> $id"
    docker tag "$id" "$ref"
  done < "$ids_file"
  docker compose --project-directory "$dir" up -d --force-recreate
  rm -f "$ids_file"
  if wait_for_health "$dir"; then
    echo "  rolled back and healthy again"
  else
    echo "  STILL unhealthy after rollback — needs a human" >&2
  fi
  return 1
}

refresh_all() {
  local failures=0
  for project in "${PROJECTS[@]}"; do
    refresh_project "$project" || failures=$((failures + 1))
  done
  if [ "$failures" -gt 0 ]; then
    echo "=== finished with $failures failing project(s) ==="
    return 1
  fi
  echo "=== all projects refreshed ==="
  return 0
}

if [ "$DRY_RUN" -eq 1 ] || [ "$LOCKED" -eq 1 ]; then
  refresh_all
else
  # Re-exec under the deploy lock; same wait budget as the push-to-deploy path.
  if ! flock -w 540 "$LOCK_FILE" "$0" --locked; then
    echo "could not take $LOCK_FILE within 540s (a deploy in progress?) — aborting" >&2
    exit 1
  fi
fi
