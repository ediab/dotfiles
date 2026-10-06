---
name: orchestrate
description: Run a substantial software task as a supervised multi-agent workflow with visible Herdr panes. Explicit-only — never invoked automatically; the user types /skill:orchestrate to hand you the supervisor role.
disable-model-invocation: true
---

# Orchestrate

Before taking the supervisor role, check `BB_THREAD_ID` and whether this session
is already working under another orchestrator. If either applies, stop this
skill, stay a normal worker, and return the request to the owning orchestrator.
Explicit invocation does not override this guard.

Next, require a nonempty `HERDR_PANE_ID` and a running Herdr server
(`herdr status`). If either is missing, stop and ask the user to start Pi inside
Herdr and invoke this skill there. The installed pi-herdr needs a parent pane
to split; a running server alone is not enough.

Otherwise, you are the top-level orchestrator/supervisor. Your job is to plan, delegate
through pi-herdr, integrate, review with fresh agents, and verify — not to do the
routine implementation yourself.

**Do not load the `herdr` skill.** That skill is for manually controlling Herdr
panes from inside a Herdr pane (it requires `HERDR_ENV=1`). Orchestration here
uses the pi-herdr extension tools (`herdr_spawn_agent`, `herdr_get_agent_result`,
`herdr_list_agents`, `herdr_message_agent`, `herdr_resume_agent`,
`herdr_run_workflow`, …). Use these extension tools for delegation; the pane
prerequisite above still applies.

Run only when explicitly invoked. Do not spawn agents for ordinary requests; if
the user wants normal work, finish this skill and behave normally.

## 1. Understand the task

Read the relevant, existing files only: `AGENTS.md`, `SPEC.md`, `CONCEPTS.md`,
`README.md`, ticket files, and existing plans in `docs/plans/`. Identify:

- the requested outcome
- constraints and acceptance criteria
- the dependency graph
- which tasks can run independently

If the task is trivial or sequential, do it directly instead of spawning agents.
This skill is for work with genuinely parallel or separable parts.

## 2. Build a dependency-aware plan

Shape the work roughly as:

```
frontier (unblocked tickets, within the configured concurrency limit)
      ↓  delivery → ticket review → merge → integrated checks → unblock
integration branch → full validation → fresh final review → spec check
```

- Tickets with blocking edges form a task graph, not a step list. The
  **frontier** is every ticket whose blockers are merged and pass integrated
  checks. After each verified integration, recompute the frontier and start
  newly unblocked tickets (up to the cap), without waiting for the whole wave.
- Never parallelize tasks that edit the same code heavily or depend on one another.
- Prefer a small useful fleet. Respect the configured concurrency limit; when
  none is available, cap active agents at four, including reviewers and testers.
- For each worker, write down: the bounded task, the exact files/spec/ticket to
  read, the acceptance criteria, and how the work integrates afterward.

## 3. Delegate through pi-herdr

Spawn visible Herdr agents with `herdr_spawn_agent` (types: `implementer`,
`reviewer`, `tester`, `explorer` — definitions in `~/.pi/agent/agents/`). Each
worker brief must be self-contained:

- exactly one bounded task, with the relevant files/spec/ticket paths
- acceptance criteria and tests to run
- an instruction not to broaden scope and not to spawn more agents
- for implementation, testing, and search workers, a final verdict: `DONE`
  (acceptance criteria met), `BLOCKED` (decision or prerequisite needed), or
  `FAILED` (execution failed), plus changed files, exact validation commands/results,
  remaining concerns, and preserved partial work; reviewers use section 5's verdicts
- for worktree implementers, explicit commit authorization and a request to
  return their branch and committed delivery SHA

Worktree isolation rules:

- Before Git changes, record the current branch, HEAD, and working-tree status.
  Confirm the approved task base; do not assume the default branch. Obtain
  explicit authorization for branch creation/checkouts, commits, and integration
  merges unless already granted. Invoking this skill alone is not Git approval.
- Preserve existing staged, unstaged, and untracked work. If it affects the task
  base or prevents safe isolation, resolve that with the user; do not stash,
  reset, or include unrelated changes in worker deliveries.
- Multi-worker implementation runs land on one **integration branch** created
  from the approved base. Use a separate clean integration worktree if the main
  checkout has unrelated changes. Nothing reaches the default branch during the run.
- For independent concurrent writers, use
  `herdr worktree create --cwd <repo> --base <integration-branch>` and spawn
  each implementer with the returned checkout path as `cwd`. Record the ticket,
  spawn handle, worktree path, branch, and review base SHA in the run checklist.
- Worktree implementers commit only their assigned changes. Before delivery,
  they merge the current integration tip into their branch, resolve conflicts,
  rerun focused tests, and report the resulting SHA. If integration advances
  before landing, return the task to its implementer for synchronization and
  renewed validation/review.
- Small or sequential tasks may share a checkout; sequence their edits.
  Never spawn parallel in-repo writers without worktrees.
- After verified integration and final review, confirm the delivery SHA is an ancestor of the
  integration tip, the worker worktree is clean, and no agent/process still uses
  it. Only then remove the worktree without force and delete the merged branch
  with `git branch -d`. Preserve failed, blocked, or unmerged work for recovery.

Spawn in the background and handle completion notifications as they arrive.
Use `herdr_get_agent_result` to read exact finals; an idle/closed pane is not
proof of `DONE`. Use `herdr_list_agents` for inspection or recovery, not a polling
loop. When only helpers are running, yield; use `wait: true` only for a necessary
dependency. Do not duplicate a worker's task.

Use `herdr_message_agent` for blocked freeform answers and `herdr_send_keys` for
option-list answers. Relay material product/scope decisions to the user.
Use `herdr_run_workflow` for repetitive fan-out, dynamically discovered task
lists, or real pipelines; ordinary supervised spawns suit a small ticket graph.

## 4. Parent stays in control

The parent owns: the plan, dependency ordering, integration decisions, conflict
resolution, whether another worker is needed, and the user-facing summary.
Stop and redirect live spawned Pi workers with `herdr_interrupt_agent`, followed
by `herdr_message_agent`. For a gone worker, inspect its retained result and
partial repository state, then use `herdr_resume_agent` with the spawn handle
and a bounded recovery instruction. Do not discard partial work or silently
retry through a different runner. `BLOCKED` and `FAILED` tickets do not unblock
dependents.
Do not send routine questions to the user; continue autonomously through
ordinary engineering decisions.

## 5. Review with a fresh agent

Implementation and review must be done by different agents (the implementer
never grades its own work). Review each ticket delivery before integration,
then use a fresh reviewer for the combined final changeset. Each brief supplies
exact base/head SHAs, the checkout path, spec/ticket, and acceptance criteria:

- compare the implementation with the relevant spec/ticket
- inspect the actual diff (not summaries) and look for regressions
- check for unnecessary scope expansion and missing tests
- reply with `PASS` or `CHANGES REQUIRED` and concrete findings; report blocked
  or failed review explicitly — a reviewer never fixes its own findings

If changes are required, check the implementer's state. For a closed pane,
use `herdr_resume_agent` with the spawn handle as `target` and the findings as
`message`; autonomous implementers normally close after finishing. Use
`herdr_message_agent` only while its pane is still live. Alternatively, spawn
a bounded repair agent. Then review again with a fresh reviewer.
Do not declare success from the implementer's word alone.

## 6. Test and integrate

For each worktree implementation `DONE` delivery, verify its committed changes and validation evidence,
obtain ticket review `PASS`, then serialize its authorized merge (`--no-ff`)
into the integration branch. Run focused integrated checks before marking the
ticket merged and unblocking dependents. A failed check leaves the ticket
unresolved: return findings to its implementer, preserve the work, and repeat
the validation/review gate before releasing dependents.

Shared-checkout tasks use the same validation/review gate on their exact diff;
commit only when authorized. Read-only worker results need verification, not a merge.

After all tickets integrate, run lint/typecheck/build and relevant integration
tests where applicable, inspect the combined diff yourself, and obtain fresh
final review. Compare against the original task/spec and acceptance criteria.
Report the integration branch, delivered SHAs, checks, and any unresolved work.
Merge to the default branch, push, or open a PR only when the user asks.

## 7. Stop conditions

Stop and ask the user only when a decision materially changes product behavior,
architecture, scope, irreversible data, credentials/secrets, triggers expensive
external actions, or requires Git authorization not already granted. Everything
else within the approved plan is yours to decide and proceed.
