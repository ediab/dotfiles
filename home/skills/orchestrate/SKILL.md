---
name: orchestrate
description: Main-agent-owned fan-out for approved execution or research across 2-5 workstreams. Use when the main agent will decompose, delegate to worker/explorer/researcher/reviewer, verify, and synthesize inline. Not for planning-only requests (user-invoked /skill:to-spec).
---

# Orchestrate

Invoke as `/skill:orchestrate`. The main agent owns decomposition, delegation, verification, and synthesis. Keep this path flat: main → leaf specialists. Never spawn an orchestrator from this skill; orchestration stays with the main agent (there is no delegated-orchestrator profile).

## 1. Decide whether to delegate

Delegate only when at least two independently useful tasks exist, each briefable with clear outputs, and delegation saves time or context. Otherwise work inline. Handle trivial or indivisible tasks directly; leave planning-only requests to the user-invoked `/skill:to-spec`. Never convert a plan request into implementation. Unapproved product or architecture decisions return to the user before any writer dispatches.

## 2. Decompose and brief

Split into 2-5 workstreams; default to two specialists. At most 4 active leaf agents across the whole task; hold the rest until earlier ones finish, then launch them. The cap is enforced in subagents config (`maxConcurrent: 4`), not just here. Reviewers and follow-ups count toward the cap. Give each child one brief: approved objective, read-first paths and context, exact writable-file ownership (or read-only), dependencies, expected result shape, acceptance checks, prohibited actions, no further delegation. Read enough to brief concretely; never delegate "investigate and implement whatever you find."

## 3. Choose profiles by contract

Worker implements approved edits; explorer locates code (quick/medium/very-thorough breadth); researcher gathers external evidence via web tools; reviewer audits a diff without fixing. Research-only work is synthesized and source-checked by the owner, not auto-routed to the code reviewer.

## 4. Launch and collect

Launch independent `Agent` calls in one message for real concurrency; respect dependencies. Prefer foreground calls when results gate the next step. Set background/foreground intentionally; main-session detached calls follow the main tool's notification rules. Use `SubagentWorkflow` only after explicit user opt-in to orchestration (including invoking `/skill:orchestrate`); automatic skill discovery alone is not consent. Prefer plain `Agent` calls for a handful of named tasks; for a justified workflow prefer `pipeline()`, pass an explicit existing `agentType` (workflows default to general-purpose), never pass `model` or `effort` overrides alongside `agentType` unless the user explicitly names a model — no profile sets a model, subagents inherit the parent model, and workflow dispatch applies no `inherit_context` pins — and keep at most 4 active children across all stages via bounded batches of at most four item pipelines, with at most one child active per item. Do not run additional fan-out alongside a workflow if it would exceed that task-wide cap. Workflows must not dispatch orchestrators or specialists that spawn their own children — this is policy, not a package-enforced restriction. One writer per file at a time; shared files need serialization and explicit ownership transfer. Disjoint ownership on the current checkout by default; worktrees auto-commit and miss uncommitted changes, so avoid them without Git authorization.

## 5. Verify, review, recover

Inspect actual changes and validation evidence, not summaries. One targeted retry or follow-up per workstream max — if a dispatch fails, report the blocker rather than re-routing to another model; after code review allow one bounded correction pass plus one re-review. If checks still fail or a decision remains unresolved after those attempts, report incomplete rather than looping. Resolve conflicting outputs against actual files/sources and the approved scope; escalate unapproved decisions to the user. Review non-trivial implementations inline by default; delegate review only on explicit review-agent consent ("use a reviewer subagent"). Ordinary review requests, generic subagent permission, invoking this skill or any workflow, and a substantial changeset are not review-delegation consent. Exception: `/skill:code-review` explicitly structures its review as two parallel review subagents (Standards + Spec), so running that skill is consent for its own two review children only — they still count toward the 4-leaf cap, and any further fan-out on top must fit within it. An authorized reviewer gets intent, exact changed paths, and a scoped diff/base.

## 6. Respect precedence and boundaries

On `Agent` calls, profile frontmatter is authoritative for thinking and `inherit_context` — pass only what the profile leaves unset (check the profile file). No profile sets a model: subagents inherit the parent model, and never pass `model`/`effort` overrides unless the user explicitly names one. Worker pins `inherit_context: true`. Fresh reviewer calls use `inherit_context: false`. Select profiles by role — explorer for lookup, worker for implementation, reviewer for high reasoning — and never override a profile pin. Do not prescribe model IDs in this policy, manage Herdr, schedule work, or add persistent orchestration state. Existing harness transcripts/session storage remain unchanged. "Integration" means combining verified results, not authorization for Git operations; follow applicable user and repository Git rules separately.

## 7. Report

Return: what ran (profiles, tasks, status), what changed (verified paths), validation and results, unresolved risks, next step. Mark partial work explicitly; never claim success while children run or checks fail.
