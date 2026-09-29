#!/usr/bin/env bash
# Deploy shared/Pi-only skills and generated global instructions.
set -eo pipefail
umask 077

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOME_DIR="${HOME:?HOME must be set}"
STATE_DIR="$HOME_DIR/.local/state/pi-dotfiles"
MANIFEST="$STATE_DIR/managed-paths"
BACKUP_DIR="$STATE_DIR/backups"
ADOPT=0
APPLY=0
FORCE=0
SKILL_BLOCKED=0
INSTRUCTION_BLOCKED=0
APPLY_ABORT=0
MANIFEST_PRESENT=0
MANAGED_PATHS=()
DESIRED_PATHS=()

usage() {
  cat <<'EOF'
Usage: sync-agent-content.sh [--dry-run] [--adopt] [--force] [--yes]

Default is a dry run. --adopt enables only the audited path/action allowlist.
--force backs up and replaces generated instructions changed since the last run.
--yes applies the printed plan. --adopt and --force never imply --yes.
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run) APPLY=0 ;;
    --yes) APPLY=1 ;;
    --adopt) ADOPT=1 ;;
    --force) FORCE=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

if [ -f "$MANIFEST" ]; then
  MANIFEST_PRESENT=1
  while IFS= read -r rel || [ -n "$rel" ]; do
    [ -z "$rel" ] && continue
    case "$rel" in
      .agents/skills/*|.claude/skills/*|.pi/agent/skills/*) ;;
      *) echo "Invalid managed path in $MANIFEST: $rel" >&2; exit 1 ;;
    esac
    case "${rel##*/}" in
      ATTRIBUTION.md) [ "$rel" = ".pi/agent/skills/ATTRIBUTION.md" ] || { echo "Invalid managed path in $MANIFEST: $rel" >&2; exit 1; } ;;
      ''|*[!a-z0-9-]*|-*|*-|*--*) echo "Invalid managed path in $MANIFEST: $rel" >&2; exit 1 ;;
    esac
    MANAGED_PATHS+=("$rel")
  done < "$MANIFEST"
elif [ -e "$MANIFEST" ] || [ -L "$MANIFEST" ]; then
  echo "ERROR: $MANIFEST is not a regular file; refusing to use ownership state." >&2
  exit 1
fi
OLD_MANAGED_PATHS=("${MANAGED_PATHS[@]}")

# Explicit one-time migration allowlist. Each entry is a HOME-relative path
# and an action; destinations are never adopted from a source-name match alone.
adoption_action() {
  case "$1" in
    .pi/agent/skills/ask-matt|.pi/agent/skills/brainstorm|.pi/agent/skills/code-review|.pi/agent/skills/convert-documents-to-markdown|.pi/agent/skills/equity-modelling|.pi/agent/skills/excel|.pi/agent/skills/frontend-design|.pi/agent/skills/local-env|.pi/agent/skills/orchestrate|.pi/agent/skills/personal-workflow|.pi/agent/skills/pull-financial-data|.pi/agent/skills/to-spec|.pi/agent/skills/to-tickets|.pi/agent/skills/web-design-guidelines|.pi/agent/skills/ATTRIBUTION.md)
      printf 'copy\n' ;;
    .pi/agent/skills/bro|.pi/agent/skills/diagnosing-bugs|.pi/agent/skills/domain-modeling|.pi/agent/skills/grill-me|.pi/agent/skills/grill-with-docs|.pi/agent/skills/grilling|.pi/agent/skills/handoff|.pi/agent/skills/herdr|.pi/agent/skills/implement|.pi/agent/skills/prototype|.pi/agent/skills/tdd|.pi/agent/skills/wayfinder|.pi/agent/skills/writing-for-agents)
      printf 'remove-shared-pi-copy\n' ;;
    .claude/skills/grilling|.claude/skills/grill-me|.claude/skills/handoff)
      printf 'replace-claude-copy-with-link\n' ;;
    .pi/agent/skills/show-me)
      printf 'remove-after-upstream-install\n' ;;
    *) printf '\n' ;;
  esac
}

path_exists() { [ -e "$1" ] || [ -L "$1" ]; }

is_managed() {
  local needle="$1" path
  for path in "${MANAGED_PATHS[@]}"; do
    [ "$path" = "$needle" ] && return 0
  done
  return 1
}

is_desired() {
  local needle="$1" path
  for path in "${DESIRED_PATHS[@]}"; do
    [ "$path" = "$needle" ] && return 0
  done
  return 1
}

append_unique() {
  local array_name="$1" value="$2" path
  shift 2
  # Bash 3.2 has no nameref; keep the two call sites explicit.
  if [ "$array_name" = "desired" ]; then
    for path in "${DESIRED_PATHS[@]}"; do [ "$path" = "$value" ] && return; done
    DESIRED_PATHS+=("$value")
  else
    for path in "${MANAGED_PATHS[@]}"; do [ "$path" = "$value" ] && return; done
    MANAGED_PATHS+=("$value")
  fi
}

write_manifest() {
  [ "$APPLY" -eq 1 ] || return 0
  mkdir -p "$STATE_DIR"
  local tmp="$STATE_DIR/managed-paths.tmp.$$"
  if [ "${#MANAGED_PATHS[@]}" -gt 0 ]; then
    printf '%s\n' "${MANAGED_PATHS[@]}" | LC_ALL=C sort -u > "$tmp"
  else
    : > "$tmp"
  fi
  mv "$tmp" "$MANIFEST"
  MANIFEST_PRESENT=1
}

record_path() {
  append_unique managed "$1"
  write_manifest
}

unrecord_path() {
  local remove="$1" kept=() path
  for path in "${MANAGED_PATHS[@]}"; do
    [ "$path" = "$remove" ] || kept+=("$path")
  done
  MANAGED_PATHS=("${kept[@]}")
  write_manifest
}

same_directory() {
  [ -d "$2" ] && [ ! -L "$2" ] && diff -qr "$1" "$2" >/dev/null 2>&1
}

same_file() {
  [ -f "$2" ] && [ ! -L "$2" ] && cmp -s "$1" "$2"
}

show_diff() {
  local source="$1" destination="$2"
  if [ -d "$destination" ] && [ ! -L "$destination" ]; then
    diff -ru "$source" "$destination" || true
  elif [ -L "$destination" ]; then
    printf '  existing symlink: %s\n' "$(readlink "$destination" 2>/dev/null || echo '(unreadable)')"
  else
    printf '  existing path is not a directory copy\n'
  fi
}

backup_existing() {
  local rel="$1" source="$HOME_DIR/$1" stamp label candidate suffix=0
  [ -e "$source" ] || [ -L "$source" ] || { echo "ERROR: cannot back up missing path $source" >&2; return 1; }
  mkdir -p "$BACKUP_DIR" || return 1
  stamp="$(date +%Y%m%dT%H%M%S)"
  label="$(printf '%s' "$rel" | tr '/ ' '--')"
  candidate="$BACKUP_DIR/${label}-${stamp}-$$"
  while path_exists "$candidate"; do
    suffix=$((suffix + 1))
    candidate="$BACKUP_DIR/${label}-${stamp}-$$-$suffix"
  done
  if ! cp -RP "$source" "$candidate"; then
    echo "ERROR: backup failed for $source; destination left untouched." >&2
    return 1
  fi
  printf '  backed up %s -> %s\n' "$source" "$candidate"
}

blocked_collision() {
  local rel="$1" path="$HOME_DIR/$1" action="$2" approved
  approved="$(adoption_action "$rel")"
  if [ -n "$approved" ] && [ "$ADOPT" -eq 0 ]; then
    printf 'BLOCKED: unmanaged collision for %s at %s; rerun with --adopt to approve %s.\n' "${rel##*/}" "$path" "$approved"
  else
    printf 'BLOCKED: unmanaged collision for %s at %s; --adopt has no approved %s action for this path.\n' "${rel##*/}" "$path" "$action"
  fi
  SKILL_BLOCKED=1
}

plan_directory_copy() {
  local source="$1" rel="$2" path="$HOME_DIR/$2" action="${3:-copy}"
  if path_exists "$path"; then
    if is_managed "$rel"; then
      printf 'UPDATE managed directory: %s\n' "$path"
    elif [ "$ADOPT" -eq 1 ] && [ "$(adoption_action "$rel")" = "$action" ]; then
      if same_directory "$source" "$path"; then
        printf 'ADOPT identical directory without replacing: %s\n' "$path"
      else
        printf 'BACK UP, then replace allowlisted directory: %s\n' "$path"
        show_diff "$source" "$path"
      fi
    else
      blocked_collision "$rel" "$action"
    fi
  else
    printf 'COPY directory: %s -> %s\n' "$source" "$path"
  fi
}

plan_file_copy() {
  local source="$1" rel="$2" path="$HOME_DIR/$2" action="${3:-copy}"
  if path_exists "$path"; then
    if is_managed "$rel"; then
      printf 'UPDATE managed file: %s\n' "$path"
    elif [ "$ADOPT" -eq 1 ] && [ "$(adoption_action "$rel")" = "$action" ]; then
      if same_file "$source" "$path"; then
        printf 'ADOPT identical file without replacing: %s\n' "$path"
      else
        printf 'BACK UP, then replace allowlisted file: %s\n' "$path"
        diff -u "$source" "$path" || true
      fi
    else
      blocked_collision "$rel" "$action"
    fi
  else
    printf 'COPY file: %s -> %s\n' "$source" "$path"
  fi
}

plan_claude_link() {
  local name="$1" rel=".claude/skills/$1" path="$HOME_DIR/.claude/skills/$1" source="$ROOT/home/shared-skills/$1"
  if path_exists "$path"; then
    if [ -L "$path" ] && [ "$(readlink "$path" 2>/dev/null || true)" = "$HOME_DIR/.agents/skills/$name" ]; then
      if is_managed "$rel"; then
        printf 'KEEP managed Claude link: %s\n' "$path"
      elif [ "$ADOPT" -eq 1 ] && [ "$(adoption_action "$rel")" = "replace-claude-copy-with-link" ]; then
        printf 'ADOPT existing Claude link: %s\n' "$path"
      else
        blocked_collision "$rel" "replace-claude-copy-with-link"
      fi
    elif is_managed "$rel"; then
      printf 'REPLACE managed Claude path with link: %s\n' "$path"
    elif [ "$ADOPT" -eq 1 ] && [ "$(adoption_action "$rel")" = "replace-claude-copy-with-link" ]; then
      printf 'BACK UP if different, then replace Claude copy with link: %s\n' "$path"
      show_diff "$source" "$path"
    else
      blocked_collision "$rel" "replace-claude-copy-with-link"
    fi
  else
    printf 'LINK Claude skill: %s -> %s\n' "$path" "$HOME_DIR/.agents/skills/$name"
  fi
}

make_instruction() {
  local client="$1" out="$2" shared="$ROOT/home/AGENTS.md" repo_overlay="$ROOT/home/instructions/$1.md" local_overlay="$HOME_DIR/.config/pi-dotfiles/local/$1.md"
  {
    printf '<!-- Generated by dotfiles. Edit home/AGENTS.md, home/instructions/%s.md, or ~/.config/pi-dotfiles/local/%s.md, then run rebuild.sh. -->\n\n' "$client" "$client"
    cat "$shared"
    printf '\n'
    if [ -f "$repo_overlay" ]; then cat "$repo_overlay"; printf '\n'; fi
    if [ -f "$local_overlay" ]; then cat "$local_overlay"; printf '\n'; fi
  } > "$out"
}

sha256_file() {
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | awk '{print $1}'
  elif command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    echo "ERROR: shasum or sha256sum is required for instruction drift checks." >&2
    return 1
  fi
}

instruction_target() {
  case "$1" in
    pi) printf '.pi/agent/AGENTS.md\n' ;;
    codex) printf '.codex/AGENTS.md\n' ;;
    claude) printf '.claude/CLAUDE.md\n' ;;
  esac
}

plan_instruction() {
  local client="$1" rel target expected hash_file stored current
  rel="$(instruction_target "$client")"
  target="$HOME_DIR/$rel"
  expected="$TMP_WORK/$client.md"
  hash_file="$STATE_DIR/instructions/$client.sha256"
  make_instruction "$client" "$expected"
  if path_exists "$target" && { [ -d "$target" ] && [ ! -L "$target" ]; }; then
    printf 'BLOCKED: instruction target is a directory: %s\n' "$target"
    INSTRUCTION_BLOCKED=1
    return
  fi
  if [ -f "$hash_file" ]; then
    IFS= read -r stored < "$hash_file" || stored=""
    if path_exists "$target"; then
      current="$(sha256_file "$target")"
      if [ "$current" != "$stored" ]; then
        if [ "$FORCE" -eq 1 ]; then
          printf 'BACK UP modified generated instructions, then replace: %s (--force)\n' "$target"
        else
          printf 'BLOCKED: generated instructions changed since last run: %s; backup and stop for this target (use --force to replace).\n' "$target"
          INSTRUCTION_BLOCKED=1
        fi
      else
        printf 'GENERATE instructions: %s\n' "$target"
      fi
    else
      printf 'GENERATE missing instructions: %s\n' "$target"
    fi
  elif ! path_exists "$target" || [ ! -s "$target" ] || cmp -s "$ROOT/home/AGENTS.md" "$target"; then
    printf 'GENERATE first-run instructions: %s\n' "$target"
  elif [ "$ADOPT" -eq 1 ]; then
    printf 'BACK UP existing instructions, then adopt: %s\n' "$target"
  else
    printf 'BLOCKED: first-run instructions contain local content: %s; copy it to the repo/local overlay or use --adopt.\n' "$target"
    INSTRUCTION_BLOCKED=1
  fi
}

apply_directory_copy() {
  local source="$1" rel="$2" path="$HOME_DIR/$2" action="${3:-copy}" parent temp same=0 approved
  if path_exists "$path"; then
    if same_directory "$source" "$path"; then same=1; fi
    if is_managed "$rel"; then
      [ "$same" -eq 1 ] && { record_path "$rel"; return 0; }
    elif [ "$ADOPT" -eq 1 ] && [ "$(adoption_action "$rel")" = "$action" ]; then
      if [ "$same" -eq 1 ]; then record_path "$rel"; return 0; fi
      show_diff "$source" "$path"
      backup_existing "$rel" || { APPLY_ABORT=1; return 1; }
    else
      APPLY_ABORT=1
      echo "ERROR: refusing unmanaged directory $path" >&2
      return 1
    fi
  fi
  parent="$(dirname "$path")"
  mkdir -p "$parent" || { APPLY_ABORT=1; return 1; }
  temp="$(mktemp -d "$parent/.dotfiles-sync.XXXXXX")" || { APPLY_ABORT=1; return 1; }
  mkdir "$temp/new" || { rm -rf "$temp"; APPLY_ABORT=1; return 1; }
  if ! cp -R "$source/." "$temp/new/"; then
    rm -rf "$temp"
    APPLY_ABORT=1
    echo "ERROR: failed staging $source; destination left untouched." >&2
    return 1
  fi
  if path_exists "$path"; then
    if ! mv "$path" "$temp/old"; then
      rm -rf "$temp"
      APPLY_ABORT=1
      echo "ERROR: could not move existing destination $path; left it untouched." >&2
      return 1
    fi
  fi
  if ! mv "$temp/new" "$path"; then
    [ ! -e "$temp/old" ] || mv "$temp/old" "$path" || true
    rm -rf "$temp"
    APPLY_ABORT=1
    echo "ERROR: could not install $path; attempted to restore the previous destination." >&2
    return 1
  fi
  rm -rf "$temp"
  record_path "$rel" || { APPLY_ABORT=1; return 1; }
  printf '  deployed %s\n' "$path"
}

apply_file_copy() {
  local source="$1" rel="$2" path="$HOME_DIR/$2" action="${3:-copy}" parent temp same=0
  if path_exists "$path"; then
    if same_file "$source" "$path"; then same=1; fi
    if is_managed "$rel"; then
      [ "$same" -eq 1 ] && { record_path "$rel"; return 0; }
    elif [ "$ADOPT" -eq 1 ] && [ "$(adoption_action "$rel")" = "$action" ]; then
      if [ "$same" -eq 1 ]; then record_path "$rel"; return 0; fi
      diff -u "$source" "$path" || true
      backup_existing "$rel" || { APPLY_ABORT=1; return 1; }
    else
      APPLY_ABORT=1
      echo "ERROR: refusing unmanaged file $path" >&2
      return 1
    fi
  fi
  parent="$(dirname "$path")"
  mkdir -p "$parent" || { APPLY_ABORT=1; return 1; }
  temp="$parent/.dotfiles-file.$$"
  if ! cp "$source" "$temp"; then APPLY_ABORT=1; return 1; fi
  if path_exists "$path" && ! mv "$path" "$temp.old"; then
    rm -f "$temp"
    APPLY_ABORT=1
    echo "ERROR: could not move existing file $path." >&2
    return 1
  fi
  if ! mv "$temp" "$path"; then
    [ ! -e "$temp.old" ] || mv "$temp.old" "$path" || true
    APPLY_ABORT=1
    echo "ERROR: could not install $path." >&2
    return 1
  fi
  rm -f "$temp.old"
  record_path "$rel" || { APPLY_ABORT=1; return 1; }
  printf '  deployed %s\n' "$path"
}

apply_claude_link() {
  local name="$1" rel=".claude/skills/$1" path="$HOME_DIR/.claude/skills/$1" target="$HOME_DIR/.agents/skills/$1" source="$ROOT/home/shared-skills/$1" parent temp same=0
  if [ -L "$path" ] && [ "$(readlink "$path" 2>/dev/null || true)" = "$target" ]; then
    if is_managed "$rel" || { [ "$ADOPT" -eq 1 ] && [ "$(adoption_action "$rel")" = "replace-claude-copy-with-link" ]; }; then
      record_path "$rel"
      return 0
    fi
  fi
  if path_exists "$path"; then
    if same_directory "$source" "$path"; then same=1; fi
    if ! is_managed "$rel"; then
      if [ "$ADOPT" -ne 1 ] || [ "$(adoption_action "$rel")" != "replace-claude-copy-with-link" ]; then
        APPLY_ABORT=1
        echo "ERROR: refusing unmanaged Claude skill path $path" >&2
        return 1
      fi
      [ "$same" -eq 1 ] || { show_diff "$source" "$path"; backup_existing "$rel" || { APPLY_ABORT=1; return 1; }; }
    fi
  fi
  parent="$(dirname "$path")"
  mkdir -p "$parent" || { APPLY_ABORT=1; return 1; }
  temp="$(mktemp -d "$parent/.dotfiles-sync.XXXXXX")" || { APPLY_ABORT=1; return 1; }
  if ! ln -s "$target" "$temp/link"; then rm -rf "$temp"; APPLY_ABORT=1; return 1; fi
  if path_exists "$path" && ! mv "$path" "$temp/old"; then
    rm -rf "$temp"
    APPLY_ABORT=1
    echo "ERROR: could not move existing Claude path $path." >&2
    return 1
  fi
  if ! mv "$temp/link" "$path"; then
    [ ! -e "$temp/old" ] || mv "$temp/old" "$path" || true
    rm -rf "$temp"
    APPLY_ABORT=1
    echo "ERROR: could not install Claude link $path." >&2
    return 1
  fi
  rm -rf "$temp"
  record_path "$rel" || { APPLY_ABORT=1; return 1; }
  printf '  linked %s -> %s\n' "$path" "$target"
}

apply_remove() {
  local rel="$1" expected_action="$2" compare="$3" path="$HOME_DIR/$1" action
  path_exists "$path" || { unrecord_path "$rel"; return 0; }
  if ! is_managed "$rel"; then
    action="$(adoption_action "$rel")"
    if [ "$ADOPT" -ne 1 ] || [ "$action" != "$expected_action" ]; then
      APPLY_ABORT=1
      echo "ERROR: refusing to remove unmanaged path $path" >&2
      return 1
    fi
  fi
  if [ -n "$compare" ] && ! same_directory "$compare" "$path"; then
    show_diff "$compare" "$path"
    backup_existing "$rel" || { APPLY_ABORT=1; return 1; }
  fi
  if ! rm -rf "$path"; then
    APPLY_ABORT=1
    echo "ERROR: could not remove $path" >&2
    return 1
  fi
  unrecord_path "$rel"
  printf '  removed approved/managed path %s\n' "$path"
}

apply_instruction() {
  local client="$1" rel target expected hash_file stored current parent temp hash backup_needed=0
  rel="$(instruction_target "$client")"
  target="$HOME_DIR/$rel"
  expected="$TMP_WORK/$client.md"
  hash_file="$STATE_DIR/instructions/$client.sha256"
  make_instruction "$client" "$expected"
  if path_exists "$target" && { [ -d "$target" ] && [ ! -L "$target" ]; }; then
    echo "ERROR: instruction target is a directory: $target" >&2
    INSTRUCTION_BLOCKED=1
    return 1
  fi
  if [ -f "$hash_file" ]; then
    IFS= read -r stored < "$hash_file" || stored=""
    if path_exists "$target"; then
      current="$(sha256_file "$target")"
      if [ "$current" != "$stored" ]; then
        if [ "$FORCE" -eq 1 ]; then backup_needed=1
        else
          backup_existing "$rel" || return 1
          echo "STOP: generated instructions changed; left $target untouched." >&2
          INSTRUCTION_BLOCKED=1
          return 1
        fi
      fi
    fi
  elif path_exists "$target" && [ -s "$target" ] && ! cmp -s "$ROOT/home/AGENTS.md" "$target"; then
    if [ "$ADOPT" -eq 1 ]; then backup_needed=1
    else
      backup_existing "$rel" || return 1
      echo "STOP: first-run instructions contain local content; left $target untouched." >&2
      INSTRUCTION_BLOCKED=1
      return 1
    fi
  fi
  [ "$backup_needed" -eq 0 ] || backup_existing "$rel" || return 1
  parent="$(dirname "$target")"
  mkdir -p "$parent" "$STATE_DIR/instructions" || return 1
  temp="$parent/.dotfiles-instructions.$$"
  cp "$expected" "$temp" || return 1
  if ! mv "$temp" "$target"; then rm -f "$temp"; return 1; fi
  hash="$(sha256_file "$target")"
  printf '%s\n' "$hash" > "$hash_file.tmp.$$"
  mv "$hash_file.tmp.$$" "$hash_file"
  printf '  generated %s\n' "$target"
}

# Prepare source names and reject malformed skill directories before planning.
SHARED_NAMES=()
PI_NAMES=()
DESIRED_PATHS=()
MANAGED_PATHS=("${MANAGED_PATHS[@]}")
shopt -s nullglob
for source in "$ROOT/home/shared-skills"/*/; do
  [ -d "$source" ] || continue
  name="$(basename "$source")"
  case "$name" in ''|*[!a-z0-9-]*|-*|*-|*--*) echo "Invalid shared skill name: $name" >&2; exit 1 ;; esac
  [ -f "$source/SKILL.md" ] || { echo "Missing SKILL.md: $source" >&2; exit 1; }
  SHARED_NAMES+=("$name")
done
for source in "$ROOT/home/skills"/*/; do
  [ -d "$source" ] || continue
  name="$(basename "$source")"
  case "$name" in ''|*[!a-z0-9-]*|-*|*-|*--*) echo "Invalid Pi-only skill name: $name" >&2; exit 1 ;; esac
  [ -f "$source/SKILL.md" ] || { echo "Missing SKILL.md: $source" >&2; exit 1; }
  PI_NAMES+=("$name")
done
shopt -u nullglob

for name in "${SHARED_NAMES[@]}"; do
  append_unique desired ".agents/skills/$name"
  if [ -d "$HOME_DIR/.claude" ]; then append_unique desired ".claude/skills/$name"; fi
done
for name in "${PI_NAMES[@]}"; do append_unique desired ".pi/agent/skills/$name"; done
if [ -f "$ROOT/home/skills/ATTRIBUTION.md" ]; then append_unique desired ".pi/agent/skills/ATTRIBUTION.md"; fi

TMP_WORK="$(mktemp -d "${TMPDIR:-/tmp}/dotfiles-agent-content.XXXXXX")"
trap 'rm -rf "$TMP_WORK"' EXIT HUP INT TERM

printf '==> %s plan\n' "$([ "$APPLY" -eq 1 ] && echo APPLY || echo DRY RUN)"
if [ "$MANIFEST_PRESENT" -eq 0 ]; then
  echo 'No ownership manifest: prune nothing; existing destinations are unmanaged unless explicitly allowlisted with --adopt.'
fi
if [ "$APPLY" -eq 1 ] && [ "$ADOPT" -eq 1 ]; then echo 'Adoption is limited to the audited path/action allowlist below.'; fi

for name in "${SHARED_NAMES[@]}"; do
  plan_directory_copy "$ROOT/home/shared-skills/$name" ".agents/skills/$name"
  if [ -d "$HOME_DIR/.claude" ]; then plan_claude_link "$name"; fi
  legacy_rel=".pi/agent/skills/$name"
  legacy_path="$HOME_DIR/$legacy_rel"
  if path_exists "$legacy_path"; then
    if is_managed "$legacy_rel"; then
      printf 'REMOVE managed old Pi copy after shared deployment: %s\n' "$legacy_path"
    elif [ "$ADOPT" -eq 1 ] && [ "$(adoption_action "$legacy_rel")" = "remove-shared-pi-copy" ]; then
      printf 'BACK UP if different, then remove allowlisted old Pi copy after shared deployment: %s\n' "$legacy_path"
      show_diff "$ROOT/home/shared-skills/$name" "$legacy_path"
    else
      printf 'BLOCKED: unmanaged old Pi copy for %s at %s; it will be left untouched.\n' "$name" "$legacy_path"
      SKILL_BLOCKED=1
    fi
  fi
done

for name in "${PI_NAMES[@]}"; do
  plan_directory_copy "$ROOT/home/skills/$name" ".pi/agent/skills/$name"
done
if [ -f "$ROOT/home/skills/ATTRIBUTION.md" ]; then
  plan_file_copy "$ROOT/home/skills/ATTRIBUTION.md" ".pi/agent/skills/ATTRIBUTION.md"
fi

# show-me is now externally owned. Remove its old Pi copy only after the
# external owner has installed the canonical shared copy and adoption is explicit.
SHOW_ME_OLD="$HOME_DIR/.pi/agent/skills/show-me"
SHOW_ME_SHARED="$HOME_DIR/.agents/skills/show-me"
if path_exists "$SHOW_ME_OLD"; then
  if [ -f "$SHOW_ME_SHARED/SKILL.md" ]; then
    if [ "$ADOPT" -eq 1 ] && [ "$(adoption_action ".pi/agent/skills/show-me")" = "remove-after-upstream-install" ]; then
      printf 'REMOVE old Pi show-me only after upstream copy exists: %s\n' "$SHOW_ME_OLD"
      show_diff "$SHOW_ME_SHARED" "$SHOW_ME_OLD"
    else
      printf 'PRESERVE unmanaged old Pi show-me: %s (use --adopt after installing upstream under ~/.agents/skills/show-me).\n' "$SHOW_ME_OLD"
    fi
  else
    printf 'PRESERVE old Pi show-me: upstream ~/.agents/skills/show-me is absent; install it before removal.\n'
  fi
fi

for rel in "${OLD_MANAGED_PATHS[@]}"; do
  if ! is_desired "$rel"; then
    if path_exists "$HOME_DIR/$rel"; then printf 'PRUNE managed path: %s\n' "$HOME_DIR/$rel"; else printf 'FORGET missing managed path: %s\n' "$HOME_DIR/$rel"; fi
  fi
done

INSTRUCTION_CLIENTS=(pi)
[ ! -d "$HOME_DIR/.codex" ] || INSTRUCTION_CLIENTS+=(codex)
[ ! -d "$HOME_DIR/.claude" ] || INSTRUCTION_CLIENTS+=(claude)
for client in "${INSTRUCTION_CLIENTS[@]}"; do plan_instruction "$client"; done

if [ "$APPLY" -eq 0 ]; then
  echo 'Dry run only; pass --yes to apply this plan.'
  [ "$SKILL_BLOCKED" -eq 0 ] && [ "$INSTRUCTION_BLOCKED" -eq 0 ] || exit 1
  exit 0
fi
if [ "$SKILL_BLOCKED" -ne 0 ]; then
  echo 'No changes applied: resolve unmanaged skill collisions or use the approved --adopt migration.' >&2
  exit 1
fi

# A dry-run and the exact plan above always precede writes. Deploy shared copies
# and Claude links first; only then can their old Pi copies be removed.
for name in "${SHARED_NAMES[@]}"; do
  if ! apply_directory_copy "$ROOT/home/shared-skills/$name" ".agents/skills/$name"; then break; fi
  if [ -d "$HOME_DIR/.claude" ] && ! apply_claude_link "$name"; then break; fi
  legacy_rel=".pi/agent/skills/$name"
  legacy_path="$HOME_DIR/$legacy_rel"
  if path_exists "$legacy_path"; then
    if [ -d "$HOME_DIR/.claude" ] && ! [ -L "$HOME_DIR/.claude/skills/$name" ]; then
      echo "ERROR: keeping old Pi copy because Claude link was not installed for $name." >&2
      APPLY_ABORT=1
      break
    fi
    apply_remove "$legacy_rel" "remove-shared-pi-copy" "$ROOT/home/shared-skills/$name" || break
  fi
done

if [ "$APPLY_ABORT" -eq 0 ]; then
  for name in "${PI_NAMES[@]}"; do
    apply_directory_copy "$ROOT/home/skills/$name" ".pi/agent/skills/$name" || break
  done
fi
if [ "$APPLY_ABORT" -eq 0 ] && [ -f "$ROOT/home/skills/ATTRIBUTION.md" ]; then
  apply_file_copy "$ROOT/home/skills/ATTRIBUTION.md" ".pi/agent/skills/ATTRIBUTION.md" || true
fi
if [ "$APPLY_ABORT" -eq 0 ] && path_exists "$SHOW_ME_OLD" && [ -f "$SHOW_ME_SHARED/SKILL.md" ] && [ "$ADOPT" -eq 1 ]; then
  apply_remove ".pi/agent/skills/show-me" "remove-after-upstream-install" "$SHOW_ME_SHARED" || true
fi

if [ "$APPLY_ABORT" -eq 0 ]; then
  for rel in "${OLD_MANAGED_PATHS[@]}"; do
    if ! is_desired "$rel"; then
      if path_exists "$HOME_DIR/$rel"; then
        rm -rf "$HOME_DIR/$rel" || { APPLY_ABORT=1; break; }
        printf '  pruned managed path %s\n' "$HOME_DIR/$rel"
      fi
      unrecord_path "$rel"
    fi
  done
fi

if [ "$APPLY_ABORT" -eq 0 ]; then
  for client in "${INSTRUCTION_CLIENTS[@]}"; do
    apply_instruction "$client" || true
  done
fi

if [ "$APPLY_ABORT" -ne 0 ]; then
  echo 'Stopped after an apply error. Any completed operations are recorded in the local manifest.' >&2
  exit 1
fi
if [ "$INSTRUCTION_BLOCKED" -ne 0 ]; then
  echo 'Skills synchronized; one or more instruction targets were backed up and left unchanged.' >&2
  exit 1
fi

echo 'Agent content synchronization complete.'
