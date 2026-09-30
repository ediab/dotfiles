#!/usr/bin/env bash
# Exercise standalone theme deployment without touching the real home or packages.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/dotfiles-themes-test.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT HUP INT TERM

mkdir -p "$WORK/repo" "$WORK/home/.pi/agent/themes" "$WORK/bin"
cp "$ROOT/apply.sh" "$WORK/repo/"
cp -R "$ROOT/home" "$WORK/repo/home"
# Isolate skill/instruction deployment, which is not under test here.
for helper in lint-agent-content.sh sync-agent-content.sh; do
  printf '#!/usr/bin/env bash\nexit 0\n' > "$WORK/repo/$helper"
  chmod +x "$WORK/repo/$helper"
done
printf '#!/usr/bin/env bash\necho "unexpected package command" >&2\nexit 1\n' > "$WORK/bin/pi"
chmod +x "$WORK/bin/pi"
printf '%s\n' '{"packages":[],"theme":"terminal"}' > "$WORK/home/.pi/agent/settings.json"
cp "$WORK/home/.pi/agent/settings.json" "$WORK/settings-before.json"
printf 'keep unrelated theme\n' > "$WORK/home/.pi/agent/themes/unrelated.json"

HOME="$WORK/home" PATH="$WORK/bin:$PATH" bash "$WORK/repo/apply.sh" --group themes --yes > "$WORK/output" 2>&1 \
  || { cat "$WORK/output"; exit 1; }
for theme in terminal terminal-tinted; do
  cmp "$ROOT/home/themes/$theme.json" "$WORK/home/.pi/agent/themes/$theme.json"
done
cmp "$ROOT/home/themes/LICENSE" "$WORK/home/.pi/agent/themes/LICENSE"
cmp "$WORK/settings-before.json" "$WORK/home/.pi/agent/settings.json"
grep -Fq 'keep unrelated theme' "$WORK/home/.pi/agent/themes/unrelated.json"

echo 'Standalone theme apply tests passed.'
