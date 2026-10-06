---
name: personal-workflow
description: Personal coding workflow and gates — plan approval, review delegation, subagent dispatch and delegation rules, task tracking, git rules, coding and validation rules. Use on a plan-approval decision, a review-delegation request, a substantial change, a subagent dispatch, or a multi-step coding task. Not for a one-line edit.
---

# Personal workflow

The agent owns execution and verification; the user controls intent, material trade-offs, and risk. The workflow gates below distinguish direct implementation from work that needs an approved plan. Planning skills are user-invoked, not mandatory stages.

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
* Validate proportionately; stronger evidence for money, private data, authentication, and live-service behaviour.
* Report what was checked and what remains unverified, including validation that could not be run.
* Add tests only when failure signals real breakage; skip assertions on styling, colors, or internal structure.

## Workflow gates

* Small, clear, low-risk changes: implement directly. Material uncertainty or substantial/risky changes: inspect first, resolve high-level decisions with the user, present a short spec or plan for approval before implementing.
* Planning skills (`brainstorm`, `to-spec`, `to-tickets`) are user-invoked and own their behavior. Running one is never approval to implement. Offer `implement` as the next step.
* Non-trivial specs carry 2–3 agent-proposed, checkable success examples; the user confirms or edits them. They become acceptance criteria for implementation and review. Clear small fixes skip this; the request itself is the criterion.
* After approval, execute the whole approved sequence without "shall I continue?" prompts. Routine technical decisions within approved constraints belong to the agent. Workers escalate material deviations to their owner; the owner asks the user only about changed product intent, material trade-offs, or unapproved risk.

## Review

* Compare the result to the agreed goal and exclusions before claiming completion.
* Substantial changes (a new user-facing flow, behaviour spanning components, a nontrivial refactor, auth/privacy/financial-calculation/data-deletion/deployment changes — impact, not size) get an owner review before you call them done: re-read the exact changeset against the agreed intent and acceptance examples. An audit does not replace this review.
* Review in the current context by default. Dispatch an independent code-audit agent only when the user explicitly requests delegated review. Asking for a review, giving generic permission to delegate, or invoking an orchestration flow does not authorize delegation. A dedicated review workflow may define its own checks; invoking it authorizes only those checks.
* For hard-to-reverse changes (deletion, auth, money, live deploy), offer an independent code-audit agent; the user decides whether to take it. That agent reports only; the owner assigns corrections and rechecks affected behaviour.

## Delegation

* Choose the execution host's delegation layer before dispatch. Inside BB (`BB_THREAD_ID` is set), new authorized workers run as BB child threads; read `bb-cli` and use the current thread as parent. Standalone Pi delegates through pi-herdr only when the user explicitly requests orchestration or invokes the `orchestrate` skill (see the orchestration rules in `AGENTS.md`); other standalone clients keep their native delegation tools. Explicit user requests for a different runner take precedence when supported. Existing workers stay on the layer that launched them; never replace a failed run through another layer without approval. This routing rule does not authorize delegation by itself.
* The main agent owns the goal and result. Planning stays in the main context and is never delegated.
* Task ownership is end-to-end: the agent that investigates a change implements, tests, and corrects it. Delegate meaningfully independent work or a fresh second opinion on a finished artifact, not sequential explore → plan → code → fix stages of one task.
* When work is ticketed, use blocking edges to identify what can start. Each worker owns one ticket at a time; independent unblocked tickets may run in parallel. Prefer the ticket graph for parallel implementation; use ad-hoc delegation for independent tasks that do not fit it.
* Before delegating, read the selected agent's configured tools and scope. Brief every dispatch self-contained (goal, paths, scope, constraints, done-criteria). Use a fresh context for self-contained ticket work; carry context forward only when correctness depends on prior discussion.
* Prefer one well-briefed helper over several loosely directed ones. Respect the current client's configured agent limit; if none is available, use no more than four active agents. Prefer background execution with completion notifications, including independent final reviews. If only helpers are running, yield rather than polling. Foreground blocking is for a necessary dependency when the selected runner supports it, not final reviews.
* Use a fresh independent audit agent for each second opinion; do not reuse one that has already seen the work. Do not silently retry a failed delegation through a different agent.
* Verify material subagent findings against the underlying files or sources rather than acting on the summary.

## Git

* Do not push, rebase, reset, stash, or modify branches unless explicitly requested.
* Do not commit unless explicitly requested, except when the user invokes an implementation workflow whose documented contract explicitly includes a commit. Keep each ticket-sized change as a review boundary. Push, deploy, branch, or open PRs only when requested.
* Do not overwrite or revert unrelated working-tree changes.
* Assume other work may exist in the repository.

## Communication

* Be concise, practical, and plain-English. Include technical detail when needed to explain a decision, constraint, or result, or when requested.
* State important assumptions, material trade-offs, and unresolved risks.
* When finished, summarize what changed and any relevant validation performed.
