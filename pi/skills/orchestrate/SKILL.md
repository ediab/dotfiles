---
name: orchestrate
description: Run a substantial software task as a supervised multi-agent workflow with visible Herdr panes. Explicit-only — never invoked automatically; the user types /skill:orchestrate to hand you the supervisor role.
disable-model-invocation: true
---

# Orchestrate

Run only when explicitly invoked. Read `personal-workflow` before dispatch.
If `BB_THREAD_ID` is set, this session is a managed Agent, or it is already
working under another orchestrator, stay a normal worker and return the request
to its owner. Explicit invocation does not override this guard.

Require a nonempty `HERDR_PANE_ID` and a running Herdr server
(`herdr status server`). Otherwise ask the user to start Pi inside Herdr.
This skill uses a Lead's owned pi-herdsman Agents, not Manager/Chief mode.

Use the pinned package's installed docs under
`~/.pi/agent/npm/node_modules/pi-herdsman/docs/`: `reference/agent.md` for
tool contracts, `reference/agent-definition-schema.md` for profiles, and
`guides/project-orchestration.md` only if branch-isolated project work is
requested. Do not use the manual `herdr` skill to bypass ownership controls.

## 1. Understand and plan

Read relevant project instructions, specs, tickets, existing plans, and code.
Identify the outcome, constraints, acceptance criteria, dependency graph, and
genuinely independent work. Trivial or inseparable tasks need no fleet.

The frontier consists of tickets whose blockers are delivered, reviewed, and
pass integrated checks. Recompute it after each verified integration instead
of waiting for a whole wave. Cap active workers at four, including reviewers
and testers. This is owner-enforced policy; pi-herdsman has no matching hard
concurrency/depth config. All custom worker definitions are leaves.

Write each brief self-contained: one bounded objective, input paths, approved
scope, acceptance criteria, checks, expected handoff, and escalation boundary.
Keep one adequate scope artifact rather than duplicating instructions; temporary
coordination material stays untracked. Pass relevant files and exact reusable
result refs through `files`.

## 2. Choose a safe execution boundary

`agent_delegate` starts in the calling Lead's cwd; it accepts no `cwd`,
`isolated`, or worktree option. Never pretend a path in the task changes that
runtime boundary. Sequence writers in this checkout and parallelize independent
read-only work. Do not overlap readers with a changing diff they must review.

For concurrent branch-isolated implementation, stop this Lead workflow and
explain the separate native Manager workflow (`/manager`, `staff_delegate`).
It needs approved branches/worktrees and a deliberately configured managed-Lead
policy compatible with the user's no-nested-orchestration rule; do not activate
it or relax that rule implicitly.

Before authorized Git operations, record branch, HEAD, and working-tree status.
Preserve unrelated staged, unstaged, and untracked work. Invocation alone grants
no branch, commit, merge, push, or deployment permission.

## 3. Delegate and receive results

Use `agent_delegate` with `definition` (`implementer`, `reviewer`,
`tester`, `scout`, `researcher`, or `generalist`), `task`,
optional unique `label`, and optional `files`.

Use bundled `scout` and `generalist` policies; both disable normal skill and
extension discovery, and `generalist` permits delegation to `scout` and
`researcher`. Within this workflow, brief workers to stay in scope and return
results directly without delegating. Require `DONE`, `BLOCKED`, or
`FAILED`, plus changed/inspected files, exact validation commands/results,
remaining concerns, and preserved partial work. Reviewers use section 5's
verdicts. Authorize commits explicitly when required and request delivery SHAs.

Acceptance is not completion. Results arrive automatically at the exact owner;
yield when only Agents are working, do not poll. An idle/closed pane proves
neither success nor delivery. Verify material findings against source files.
Forward an exact delivered `result:<agent>#<index>` via `files` when another
assignment depends on it; do not substitute a summary of its evidence.

## 4. Keep ownership and recovery explicit

Use `agent_list` for a fresh roster or recovery decision, not a polling loop.
A live record's exact `agent` and `available_tools` guide permitted actions;
each operation revalidates identity and lifecycle.

- `agent_steer` with `agent` and `message` cooperatively redirects live work.
- `agent_interrupt` with replacement `message` cancels the current operation
  and continues the same assignment; do not pair it with duplicate steering.
- `agent_reply` answers an eligible correlated `ask_owner` question.
- `agent_transcript` reads bounded persisted evidence; `agent_inspect` reads
  bounded live terminal/process evidence when needed.
- `agent_continue` starts one new assignment from the exact saved session path
  or full UUID and a new `task`; it is not a live agent-label control.
  Retired sessions require a fresh Agent with the previous result as evidence.
- `agent_close` abandons eligible owned work; preserve partial repository and
  session evidence and do not close merely because progress looks slow.

Relay material scope/product decisions to the user; resolve ordinary engineering
choices within approved constraints. Unknown identity fails closed. Blocked or
failed work does not unblock dependents. Never silently switch runners.

## 5. Review with a fresh Agent

An implementer never grades its own work. Delegate a fresh `reviewer` for each
delivery before marking it accepted, then another fresh reviewer for the combined
final changeset. Supply exact base/head refs (or the bounded uncommitted diff),
checkout, spec/ticket, and acceptance criteria. Require inspection of the real
diff, regressions, scope, and tests, with `PASS` or `CHANGES REQUIRED`;
blocked/failed review must be explicit. Reviewers report only, never fix.

Return required corrections to the implementer through an eligible live steer,
or continue its saved session after completion. A retired session needs a fresh
bounded repair Agent. Re-review corrections with a fresh reviewer.

## 6. Validate and integrate

For every `DONE` delivery, verify the actual diff or committed SHA and test
evidence, obtain review `PASS`, and run focused integrated checks before
acceptance or unblocking dependents. Commit only when authorized.
Preserve failed or unmerged work; never reset or discard it to clear the queue.

After all work is accepted, run applicable lint/typecheck/build and integration
checks, inspect the combined diff yourself, obtain fresh final review, and compare
against the original goal. Report delivered SHAs, checks, and unresolved work.
Push, merge to the default branch, open a PR, or deploy only when requested.

Stop for material changes to intent, architecture, scope, irreversible data,
credentials, expensive external actions, or unapproved Git/operational risk.
Otherwise execute the approved sequence without routine continuation prompts.
