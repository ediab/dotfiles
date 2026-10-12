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

* Choose test timing to suit the task; strict test-first development is opt-in. For bug fixes, prefer a reproducing check before editing when practical. Derive expected results from requirements or independent examples, and verify the full requested behaviour even when tests pass.
* After modifying code, run the most relevant available tests, type checks, linters, or validation commands.
* Prefer targeted checks during iteration; run broader project checks when appropriate before finishing.
* In delegated work, helpers run assigned focused checks. The implementation/integration owner runs affected checks after each integration and the full supported validation on the final combined tree. Reuse results for unchanged source, dependencies and environment; rerun what later changes invalidate. The main agent verifies the evidence even when an orchestrator-only assignment puts execution with a child.
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
* Review the complete affected contract before returning one consolidated correction list: callers, evidence/data scope, boundary cases, and expected workload. Keep corrections with the task owner. A further substantial defect or invalidated assumption triggers a blocker report with impact and a revised bounded approach, rather than another open-ended correction round; seek user approval only where the workflow gates require it.
* Review in the current context by default. Dispatch an independent code-audit agent only when the user explicitly requests delegated review. Asking for a review, giving generic permission to delegate, or invoking an orchestration flow does not authorize delegation. A dedicated review workflow may define its own checks; invoking it authorizes only those checks.
* For hard-to-reverse changes (deletion, auth, money, live deploy), offer an independent code-audit agent; the user decides whether to take it. That agent reports only; the owner assigns corrections and rechecks affected behaviour.

## Delegation

* Choose the execution host's delegation layer before dispatch. Inside BB (`BB_THREAD_ID` is set), new authorized workers run as BB child threads; read `bb-cli` and use the current thread as parent. Standalone Pi delegates through pi-herdsman only when the user explicitly requests orchestration or invokes the `orchestrate` skill (see the orchestration rules in `AGENTS.md`); other standalone clients keep their native delegation tools. Explicit user requests for a different runner take precedence when supported. Existing workers stay on the layer that launched them; never replace a failed run through another layer without approval. This routing rule does not authorize delegation by itself.
* The main agent owns planning, scope and the final result. Name one implementation/integration owner and one canonical working tree at the start. Default to the main agent; when explicitly orchestrator-only, assign that ownership to one child from the start, not a final integration ticket.
* Task ownership is end-to-end: the owner investigates, implements, tests and corrects the change. Add a helper only for authorised independent work with a stable input contract, separable edits and its own checkable result. Shared-file or evolving-interface work stays with one writer or runs sequentially. A concurrency limit is a ceiling, not a staffing target.
* Use ticket dependencies to identify the critical path, then check edit/interface overlap before parallel dispatch. Ticket boundaries alone do not establish independence. Keep dependent work on the latest integrated baseline.
* Before dispatch, read the selected agent's tools and scope. Give each helper a self-contained brief: goal, exact baseline, owned paths/interfaces, exclusions, done-criteria and focused checks. Use a fresh context for independent work; retain context where correctness depends on prior discussion. Reference shared workflow rules rather than copying them into every brief.
* Integrate each accepted helper delta promptly into the canonical tree, relative to its recorded baseline. Reconcile overlapping regions while preserving both behaviours and regression tests; whole-file precedence is not a merge strategy. Run affected combined checks before dependent work starts. Completion requires a recorded integrated source identity and passing affected checks, not just a worker report.
* Handoffs report baseline and resulting source identities, changed files, exact focused results (including skips), material gaps, owned-resource cleanup and absolute workspace path. Hand off once that scope is ready; unrelated broad checks belong to the integration owner.
* Respect the client's agent limit; if none exists, use at most four active agents. Use background completion notifications; when only helpers are running, yield rather than polling. Foreground waiting is for a necessary dependency, not a final review.
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
* Report combined-application milestones: implemented → integrated → validated. Keep application to the target checkout and deployment explicit. Worker completion counts do not establish readiness; send milestone or concrete blocker updates, not duplicate worker notifications or unsupported 'nearly finished' claims.
* When finished, summarize what changed and any relevant validation performed.
