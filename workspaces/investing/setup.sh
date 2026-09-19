#!/usr/bin/env bash
# Register the investing skills in the private assignment workspace.
#
# Creates/repairs:
#   $WORKSPACE/.agents/skills  ->  <repo>/workspaces/investing/skills   (symlink)
#   $WORKSPACE/AGENTS.md       <-  templates/workspace-AGENTS.md        (only if absent)
#
# Deliberately does NOT touch global skill settings, ~/.pi/agent/settings.json,
# rebuild.sh, bootstrap.sh or VPS sync: these skills exist only in the investing
# workspace. Safe to re-run; conflicts are reported, never overwritten.
#
# Usage: workspaces/investing/setup.sh [--check]

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
WORKSPACE="${INVESTING_WORKSPACE:-$HOME/Desktop/Fundaments}"
SKILLS_DIR="$HERE/skills"
LINK="$WORKSPACE/.agents/skills"
TEMPLATE_AGENTS="$HERE/templates/workspace-AGENTS.md"
TARGET_AGENTS="$WORKSPACE/AGENTS.md"

CHECK_ONLY=0
if [[ "${1:-}" == "--check" ]]; then
  CHECK_ONLY=1
elif [[ $# -gt 0 ]]; then
  echo "usage: $0 [--check]" >&2
  exit 2
fi

problems=0
report_problem() { echo "CONFLICT  $*" >&2; problems=$((problems + 1)); }

# ----------------------------------------------------------------- workspace links
# skills/ is what Pi discovers. references/, scripts/, templates/ and README.md are
# mirrored alongside it so that the relative pointers inside SKILL.md
# (../../references/workflow-policy.md and friends) resolve from either path: the
# repository checkout or the workspace symlink. Relative symlinks inside the repo
# would not survive that indirection, so these use absolute targets.
link_path() {  # link_path <workspace-relative path> <target>
  local link="$WORKSPACE/.agents/$1" target="$2"
  if [[ -L "$link" ]]; then
    if [[ "$(readlink "$link")" == "$target" ]]; then
      echo "ok        $link -> $target"
    else
      report_problem "$link points at $(readlink "$link"), expected $target (leaving it alone)"
    fi
  elif [[ -e "$link" ]]; then
    report_problem "$link exists and is not a symlink (leaving it alone)"
  elif [[ $CHECK_ONLY -eq 1 ]]; then
    report_problem "$link is missing (run without --check to create it)"
  else
    mkdir -p "$(dirname "$link")"
    ln -s "$target" "$link"
    echo "created   $link -> $target"
  fi
}

link_path skills "$SKILLS_DIR"
link_path references "$HERE/references"
link_path scripts "$HERE/scripts"
link_path templates "$HERE/templates"
link_path README.md "$HERE/README.md"

# ------------------------------------------------------------- workspace AGENTS.md
if [[ -f "$TARGET_AGENTS" ]]; then
  echo "ok        $TARGET_AGENTS exists (not overwritten)"
elif [[ $CHECK_ONLY -eq 1 ]]; then
  report_problem "$TARGET_AGENTS is missing (run without --check to create it)"
else
  mkdir -p "$WORKSPACE"
  sed -e "s|@REPO_ROOT@|$REPO_ROOT|g" -e "s|@WORKSPACE@|$WORKSPACE|g" \
      "$TEMPLATE_AGENTS" > "$TARGET_AGENTS"
  echo "created   $TARGET_AGENTS"
fi

# ------------------------------------------------------------------ skill sanity
shopt -s nullglob
skills=("$SKILLS_DIR"/*/SKILL.md)
if [[ ${#skills[@]} -eq 0 ]]; then
  report_problem "no skills found under $SKILLS_DIR"
fi
for skill in "${skills[@]}"; do
  name="$(basename "$(dirname "$skill")")"
  if ! grep -q '^name: ' "$skill" || ! grep -q '^description: ' "$skill"; then
    report_problem "$name/SKILL.md is missing name/description frontmatter"
  fi
  # Relative pointers must resolve from the real skill directory.
  if ! (cd "$(dirname "$skill")" && [[ -f ../../references/workflow-policy.md && -f ../../references/source-policy.md ]]); then
    report_problem "$name/SKILL.md's ../../references pointers do not resolve"
  fi
done
echo "checked   ${#skills[@]} skill file(s) under $SKILLS_DIR"

# ------------------------------------------------------------------------ finish
echo
if [[ $problems -gt 0 ]]; then
  echo "setup finished with $problems conflict(s) - resolve them before using the skills" >&2
  exit 1
fi

cat <<EOF
Fundaments workspace ready.

  skills    $LINK
  workspace $WORKSPACE

Next:
  1. Start Pi at $WORKSPACE (the simplest workflow) and confirm the seven
     investing skills appear in /skills.
  2. Per assignment, create a folder with inputs/ (untouched supplied files),
     working/ (drafts, inspection records, approved change list) and outputs/
     (delivered workbook, memo, summaries).
  3. Read $WORKSPACE/AGENTS.md - it points at the shared workflow and source
     policies in $HERE/references/.
  4. Derive the toolset root in commands, so they work from any directory:
       TOOLSET=\$(dirname "\$(readlink -f $WORKSPACE/.agents/skills)")
       "\$TOOLSET/.venv/bin/python" "\$TOOLSET/scripts/inspect_workbook.py" inspect <workbook>
EOF
