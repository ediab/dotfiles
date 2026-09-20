#!/bin/bash
# Sync Firefox profile configs into this repo.
# Run this to refresh the backup after making Firefox changes.
#
#   sync.sh           full sync, including the latest bookmark backup
#   sync.sh --latest  bookmark backup only (bookmarkbackups/ is gitignored —
#                     the live profile is the real backup; this just refreshes
#                     the local copy for restore use)

PROFILE="$HOME/Library/Application Support/Firefox/Profiles/iaqaaxy6.default-release"
DEST="$(cd "$(dirname "$0")" && pwd)"

if [ ! -d "$PROFILE" ]; then
    echo "Profile not found: $PROFILE"
    exit 1
fi

sync_bookmarks() {
    mkdir -p "$DEST/bookmarkbackups"
    latest="$(ls -t "$PROFILE/bookmarkbackups/" | head -n 1)"
    [ -n "$latest" ] || { echo "No bookmark backups in profile." >&2; return 1; }
    cp "$PROFILE/bookmarkbackups/$latest" "$DEST/bookmarkbackups/"
    # Keep only the newest locally — older dated snapshots are gitignored anyway.
    ls -t "$DEST/bookmarkbackups/" | tail -n +2 | while IFS= read -r f; do
        rm -f "$DEST/bookmarkbackups/$f"
    done
    echo "Bookmarks: $latest"
}

if [ "${1:-}" = "--latest" ]; then
    sync_bookmarks
    exit 0
fi

# Core configs
cp "$PROFILE/prefs.js"              "$DEST/"
cp "$PROFILE/extension-preferences.json" "$DEST/"
cp "$PROFILE/extension-settings.json"    "$DEST/"
cp "$PROFILE/containers.json"       "$DEST/"
cp "$PROFILE/handlers.json"         "$DEST/"
cp "$PROFILE/search.json.mozlz4"    "$DEST/"

# Chrome CSS and theme
cp "$PROFILE/chrome/userChrome.css"   "$DEST/chrome/"
cp "$PROFILE/chrome/userContent.css"  "$DEST/chrome/"
rsync -a --delete "$PROFILE/chrome/theme/" "$DEST/chrome/theme/"

sync_bookmarks

echo "Firefox configs synced."
