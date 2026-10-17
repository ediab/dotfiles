# BB preferences

## Questions

For necessary clarification questions in BB, prefer BB's `AskUserQuestion` tool when available; otherwise ask in chat. Leave Pi's `ask_user_question` tool for standalone terminal sessions.

## Delegation and tool routing

- Read the `pstack-bb` skill before any pstack delegation. Use BB child threads and BB messaging instead of native subagent tools. If the adapter is missing, report it before dispatching pstack workers.
- Every pstack worker is a `pi` child thread. Do not dispatch pstack work to Claude Code, Codex, or another provider, and do not fall back to an Anthropic model.

## Memory

Repository knowledge follows the global `MEMORY.md` policy, including inside BB. Do not create duplicate BB project memories for repository facts. Reserve BB memory for cross-project preferences and BB-wide operational facts, using global scope.
