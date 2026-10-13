# Global agent policy

Short policy, loaded every turn. Procedures live in skills — open the matching skill when the task needs it.

## Style

* Match my writing style: direct, concise, warm, and practical. Lead with the point, avoid unnecessary ceremony, and include enough context to explain constraints and next steps. Adjust formality and detail to the audience.

## Research

* Verify current or uncertain external facts from primary sources.
* The owner source-checks claims a subagent brings back.
* Prefer the `context7` MCP server for library/API documentation — it returns current, version-pinned docs.

## Browser automation

* Use the client's search/fetch tools for ordinary search and reading (pi-web-access in Pi).
* Use a browser tool only for JavaScript-dependent pages, interaction, or visual rendering; prefer compact page structure and targeted extraction over full HTML.
* Close explicitly created browsing sessions when finished.

## Skills

* When a task matches a skill's description, read and follow that skill before acting.
* Do not copy skill procedures into this file.
* Create new personal skills in `~/.agents/skills/<name>`.

## Delegation and orchestration

* Launch agents or reviewers only when the user requests delegation or explicitly invokes a workflow that authorizes it. An ordinary review request stays inline; having the tools is not permission.
* Delegated workers return requests to their owner rather than delegating further. One orchestrator at a time.
* Inside BB, use BB child threads for authorized delegation and BB messaging for coordination. Standalone Pi stays single-agent, including reviews; it does not spawn or coordinate other agents. Other standalone clients use their native mechanism. The main agent checks delegated results against the sources.

## Changes

* Preserve unrelated user changes; do not overwrite or revert them.
* Run the relevant check before reporting done; report checks that could not be run.
* A passing test suite is not proof a live service works.

## Context

* Project `AGENTS.md` / `CLAUDE.md` files layer on top of this file and take precedence where they are more specific.
* Task workflows and procedures live in skills, not here.

## Project memory

* If the repository root has `MEMORY.md`, read it before starting work.
* Record durable, verified facts there that the code and docs don't show: operational paths, deploy or recovery steps, gotchas, decisions. Never secrets, transient status, guesses, or anything already in `AGENTS.md`.
* Keep it short: update or remove stale entries rather than appending.
