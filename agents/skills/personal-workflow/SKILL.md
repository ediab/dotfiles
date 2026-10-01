---
name: personal-workflow
description: Personal coding workflow and gates — plan approval, review delegation, subagent dispatch and delegation rules, task tracking, git rules, coding and validation rules. Use on a plan-approval decision, a review-delegation request, a substantial change, a subagent dispatch, or a multi-step coding task. Not for a one-line edit.
---

# Personal workflow

The gates and rules for completing coding work. The default path is to turn approved intent into a spec, split it into blocker-aware tickets, implement one ticket at a time, then review the result. The ticket graph is the primary way to manage parallel work; use ad-hoc delegation only for independent tasks that do not fit it. Before delegating, read the selected agent's configured tools and scope.

## Working Principles

* Make the smallest correct change that fully solves the task.
* Do not broaden scope or refactor unrelated code unless necessary.
* Inspect relevant code before modifying it. Follow existing project patterns and conventions.
* Do not guess APIs, types, file locations, or library behaviour when they can be verified from the repository or installed dependencies.
* Prefer simple implementations over additional abstractions unless complexity is justified by the task.
* If the task is sufficiently specified, proceed. Ask only when unresolved ambiguity would materially change the implementation.

## Task tracking

* Track multi-step work with a short checklist in the conversation. State the current step and update progress when a step finishes.
* Keep project runtime state and caches out of Git unless the project explicitly versions them.

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

* Review in the current context by default. Dispatch an independent code-audit agent only when the user explicitly requests delegated review.
* Asking for a review, giving generic permission to delegate, or invoking an orchestration flow does not authorize delegation. A dedicated review workflow may define its own checks; invoking it authorizes only those checks.

## Personal workflow

* Plain English for the user. Technical detail belongs in agent instructions or on request.
* Planning skills (`brainstorm`, `to-spec`, `to-tickets`) are user-invoked and own their behavior. Running one is never approval to implement; planning stays in the main context. Offer `implement` as the next step.
* Small, clear, low-risk changes: implement directly. Material uncertainty or substantial/risky changes: inspect first, resolve high-level decisions with the user, present a short spec or plan for approval before implementing.
* Non-trivial specs carry 2–3 agent-proposed, checkable success examples; the user confirms or edits them. They become acceptance criteria for implementation and review. Clear small fixes skip this; the request itself is the criterion.
* After approval, execute the whole approved sequence without "shall I continue?" prompts. Routine technical decisions within approved constraints belong to the agent. Workers escalate material deviations to their owner; the owner asks the user only about changed product intent, material trade-offs, or unapproved risk.
* Substantial changes (a new user-facing flow, behaviour spanning components, a nontrivial refactor, auth/privacy/financial-calculation/data-deletion/deployment changes — impact, not size) get an owner review before you call them done, not a delegated agent: re-read the exact changeset against the agreed intent and acceptance examples, and state what was checked and what remains unverified. For hard-to-reverse changes (deletion, auth, money, live deploy), offer an independent code-audit agent; the user decides whether to take it. That agent reports only; the owner assigns corrections and rechecks affected behaviour.
* Validate proportionately; stronger evidence for money, private data, authentication, and live-service behaviour. Compare the result to the agreed goal and exclusions before claiming completion; state what was checked and what remains unverified. A passing test suite does not prove a live service works.
* Delegation: the main agent owns the goal and result. Prefer one well-briefed helper over several loosely directed ones; parallelize genuinely independent work. Respect the current client's configured agent limit; if none is available, use no more than four active agents. Use background execution only when there is useful work to do while it runs; otherwise keep the task in the foreground. Brief every dispatch self-contained (goal, paths, scope, constraints, done-criteria). Use a fresh independent audit agent for each second opinion; do not reuse one that has already seen the work. Do not silently retry a failed delegation through a different agent.
* Task ownership is end-to-end, never an assembly line: the agent that investigates a change implements, tests, and corrects it. Do not delegate sequential stages of one task (explore → plan → code → fix chains) — every summary handed between agents is context the next agent will never have. Spawn subagents only for meaningfully independent parallel work or a fresh second opinion on a finished artifact, and when a subagent's findings matter, verify them against the underlying files or sources rather than acting on the summary. Give every agent a self-contained task. Use a fresh context for self-contained ticket work; carry context forward only when correctness depends on prior discussion. Planning stays in the main context and is never delegated.

## Git

* Do not push, rebase, reset, stash, or modify branches unless explicitly requested.
* Do not commit unless explicitly requested, except when the user invokes an implementation workflow whose documented contract explicitly includes a commit. Keep each ticket-sized change as a review boundary. Push, deploy, branch, or open PRs only when requested.
* Do not overwrite or revert unrelated working-tree changes.
* Assume other work may exist in the repository.

## Communication

* Be concise and technical.
* State important assumptions, material trade-offs, and unresolved risks.
* When finished, summarize what changed and any relevant validation performed.
