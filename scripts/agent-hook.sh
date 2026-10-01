#!/usr/bin/env bash
# Optional session integrations: keep working on hosts without desktop tooling.
set -eu
case "${1:-}" in
  gh-axi|lavish-axi|chrome-devtools-axi)
    command -v "$1" >/dev/null 2>&1 || exit 0
    exec "$@"
    ;;
  claude|codex)
    client="$1"; shift
    if [ "$client" = claude ]; then
      hook="$HOME/.claude/hooks/herdr-agent-state.sh"
    else
      hook="$HOME/.codex/herdr-agent-state.sh"
    fi
    [ -f "$hook" ] || exit 0
    exec bash "$hook" "$@"
    ;;
  *) echo "Unknown session integration: ${1:-}" >&2; exit 2 ;;
esac
