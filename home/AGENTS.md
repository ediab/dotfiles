# Global agent policy

Short policy, loaded every turn. Procedures live in skills — open the matching skill when the task needs it.

## Research

* Verify current or uncertain external facts from primary sources.
* The owner source-checks claims a subagent brings back.
* Prefer the `context7` MCP server for library/API documentation — it returns current, version-pinned docs.

## Skills

* When a task matches a skill's description, read and follow that skill before acting.
* Do not copy skill procedures into this file.

## Subagents

* Spawn subagents only for independent investigation, specialist work, or parallel work.
* The main agent owns synthesis and verification of subagent results.

## Changes

* Preserve unrelated user changes; do not overwrite or revert them.
* Run the relevant check before reporting done; report checks that could not be run.
* A passing test suite is not proof a live service works.

## Context

* Project `AGENTS.md` / `CLAUDE.md` files layer on top of this file and take precedence where they are more specific.
* Task workflows and procedures live in skills, not here.
