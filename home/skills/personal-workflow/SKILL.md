---
name: personal-workflow
description: Personal coding workflow and gates — plan approval, review delegation, the substantial-change reviewer pass, subagent dispatch and delegation rules, task tracking, git rules, coding and validation rules. Use on a plan-approval decision, a review-delegation request, a substantial change, a subagent dispatch, or a multi-step coding task. Not for a one-line edit.
---

# Personal workflow

The gates and rules for how the main agent works. Fan-out mechanics live in the `orchestrate` skill; a profile's frontmatter is the source of truth for its tools and scope — read it before dispatching.

## Working Principles

* Make the smallest correct change that fully solves the task.
* Do not broaden scope or refactor unrelated code unless necessary.
* Inspect relevant code before modifying it. Follow existing project patterns and conventions.
* Do not guess APIs, types, file locations, or library behaviour when they can be verified from the repository or installed dependencies.
* Prefer simple implementations over additional abstractions unless complexity is justified by the task.
* If the task is sufficiently specified, proceed. Ask only when unresolved ambiguity would materially change the implementation.

## Task tracking

* Track multi-step work with the task tools from `@tintinweb/pi-tasks` (`TaskCreate`, `TaskUpdate`, `TaskList`, `TaskGet`, `TaskExecute`, `TaskStop`, `TaskOutput`) — not the retired `todo` tool.
* Keep the task list current: mark a task `in_progress` before starting it and `completed` immediately when done; never batch completions.
* Expect `<system-reminder>` nudges when the list goes stale — treat one as an instruction to sync the list before continuing.
* Project `.pi/tasks/tasks.json` is shared state between sessions and belongs in `.gitignore` unless the project explicitly versions it.

## Repository Navigation

* Search for relevant files and symbols before reading large parts of the repository.
* Read enough surrounding code to understand interfaces, callers, tests, and local conventions before editing.
* Prefer existing utilities and abstractions over introducing duplicates.
* Treat repository documentation, configuration, tests, and source code as the source of truth.

## Changes

* Preserve existing behaviour unless the requested change requires otherwise.
* Avoid speculative backwards compatibility, fallback paths, or defensive abstractions that are not required.
* Do not remove apparently intentional functionality without confirming that it is part of the requested change.
* Keep changes localized and easy to review.
* Name literals whose meaning is not obvious at the call site.
* For bug fixes, check all callers of the changed function, fix the shared root cause, and verify sibling paths.
* Prefer deletion and reuse, but do not trade correctness or readability for a smaller diff.
* Comment only on non-obvious intent or constraints.

## Validation

* After modifying code, run the most relevant available tests, type checks, linters, or validation commands.
* Prefer targeted checks during iteration; run broader project checks when appropriate before finishing.
* Fix errors introduced by your changes. Do not hide failures by weakening tests, types, or validation.
* Report validation that could not be run.
* Add tests only when failure signals real breakage; skip assertions on styling, colors, or internal structure.

## Review delegation

* Review in the current session by default. Except for the substantial-implementation pass below, spawn a subagent to perform a review only when the user explicitly requests review delegation (for example, "use a reviewer subagent"). This applies regardless of the chosen agent type or tool.
* "Review this", `/review`, generic permission to use subagents, and invoking an orchestration skill or workflow do not by themselves authorize a review subagent. Keep review stages inline unless review delegation was explicitly requested.
* Exception: substantial implementations get an automatic fresh-reviewer pass under Personal workflow below. Standalone review requests still need an explicit request.

## Personal workflow

* Plain English for the user. Technical detail belongs in agent instructions or on request.
* Brainstorming only on explicit invocation (`/skill:brainstorm`): one question at a time with a recommendation; stay with the user's idea; propose smaller versions and let the user decide. End at an agreed short brief; offer chat-only or saving under `docs/specs/`; never auto-start implementation.
* Small, clear, low-risk changes: implement directly. Material uncertainty or substantial/risky changes: inspect first, resolve high-level decisions with the user, present a short plan for approval before implementing.
* Non-trivial plans carry 2–3 agent-proposed, checkable success examples; the user confirms or edits them. They become acceptance criteria for implementation and review. Clear small fixes skip this; the request itself is the criterion.
* After approval, execute the whole approved sequence without "shall I continue?" prompts. Routine technical decisions within approved constraints belong to the agent. Workers escalate material deviations to their owner; the owner asks the user only about changed product intent, material trade-offs, or unapproved risk.
* Substantial changes (a new user-facing flow, behaviour spanning components, a nontrivial refactor, auth/privacy/financial-calculation/data-deletion/deployment changes — impact, not size) get an automatic independent review: the owner dispatches a fresh `reviewer` with the agreed intent, acceptance examples, exact changeset, and validation performed. The reviewer reports only; the owner assigns corrections to the implementer and rechecks affected behaviour. Tiny mechanical edits stay inline.
* Validate proportionately; stronger evidence for money, private data, authentication, and live-service behaviour. Compare the result to the agreed goal and exclusions before claiming completion; state what was checked and what remains unverified. A passing test suite does not prove a live service works.
* Deliver locally by default. Push, deploy, branch, or open PRs only when requested.
* Delegation: the main agent owns the goal and result. Prefer one well-briefed helper over several loosely directed ones; parallelize genuinely independent work. At most 4 active leaf agents (enforced in subagents config). Set `run_in_background` explicitly: background with useful work meanwhile, foreground when the next step depends on the result. Brief every dispatch self-contained (goal, paths, scope, constraints, done-criteria). Use a fresh reviewer per independence check, never a resumed one. `fallbackSubagent` stays `none`.
* Task ownership is end-to-end, never an assembly line: the agent that investigates a change implements, tests, and corrects it. Do not delegate sequential stages of one task (explore → plan → code → fix chains) — every summary handed between agents is context the next agent will never have. Spawn subagents only for meaningfully independent parallel work or a fresh second opinion on a finished artifact, and when a subagent's findings matter, verify them against the underlying files or sources rather than acting on the summary. Delegating to a profile that inherits the full conversation (`worker` pins `inherit_context: true`) forks context instead of summarising it, but that mitigates rather than removes the loss — it is not a licence to split coherent tasks. Planning is never delegated: `/skill:plan` runs in the main session; the `planner` profile is retired.
* Ponytail stays installed with default lite; it runs on every coding task and names the lazier alternative in one line. Switch levels with `/ponytail full` or `/ponytail ultra`, turn it off with `stop ponytail`. An enabled Ponytail never authorizes unrequested Git operations or overriding approved requirements.

## Git

* Do not commit, push, rebase, reset, stash, or modify branches unless explicitly requested.
* Do not overwrite or revert unrelated working-tree changes.
* Assume other work may exist in the repository.
* **Standing exception:** `~/dev/configs` and `~/dev/pi-dotfiles` are repos where committing after an edit is expected. Pushing still requires an explicit request.

## Communication

* Be concise and technical.
* State important assumptions, material trade-offs, and unresolved risks.
* When finished, summarize what changed and any relevant validation performed.
