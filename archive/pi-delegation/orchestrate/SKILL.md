---
name: orchestrate
description: Run a substantial software task as a supervised multi-agent workflow with visible Herdr panes. Explicit-only — never invoked automatically; the user types /skill:orchestrate to hand you the supervisor role.
disable-model-invocation: true
---

# Orchestrate

Run only when explicitly invoked. Read `personal-workflow` and its
`DELEGATION.md` reference before dispatch. This skill authorizes implementation
coordination, not automatic independent reviews.
If this session is a delegated worker (a managed Agent, a BB child thread, or
working under another orchestrator), stay a normal worker and return the request
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
Keep one implementation/integration owner throughout; when supervising only,
assign that role to one child from the start. Keep coupled work with that owner,
continuing its context for dependent steps and corrections. Add helpers only
where their independent contribution outweighs briefing and integration costs.

The frontier consists of work whose blockers are delivered, owner-reviewed, and
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

`delegate_agent` starts in the calling Lead's cwd; it accepts no `cwd`,
`isolated`, or worktree option. Never pretend a path in the task changes that
runtime boundary. Sequence writers in this checkout and parallelize independent
read-only work. Do not overlap readers with a changing diff they must review.

For concurrent branch-isolated implementation, stop this Lead workflow and
explain the separate native Manager workflow (`/manager`, `delegate_project`).
It needs approved branches/worktrees and a deliberately configured managed-Lead
policy compatible with the user's no-nested-orchestration rule; do not activate
it or relax that rule implicitly.

Before authorized Git operations, record branch, HEAD, and working-tree status.
Preserve unrelated staged, unstaged, and untracked work. Invocation alone grants
no branch, commit, merge, push, or deployment permission.

## 3. Delegate and receive results

Use `delegate_agent` with `definition` (`implementer`, `reviewer`,
`tester`, `scout`, `researcher`, or `generalist`), `task`,
optional unique `label`, and optional `files`.

Use bundled `scout` and `generalist` policies; both disable normal skill and
extension discovery, and `generalist` permits delegation to `scout` and
`researcher`. Within this workflow, brief workers to stay in scope and return
results directly without delegating. Require `DONE`, `BLOCKED`, or
`FAILED`, plus changed/inspected files, exact validation commands/results,
remaining concerns, and preserved partial work. Authorized reviewers use
section 5's verdicts. Authorize commits explicitly when required and request
delivery SHAs.

Acceptance is not completion. Results arrive automatically at the exact owner;
yield when only Agents are working, do not poll. An idle/closed pane proves
neither success nor delivery. Verify material findings against source files.
Forward an exact delivered `result:<agent>#<index>` via `files` when another
assignment depends on it; do not substitute a summary of its evidence.

## 4. Keep ownership and recovery explicit

Use `list_agents` for a fresh roster or recovery decision, not a polling loop.
A live record's exact `agent` and `available_tools` guide permitted actions;
each operation revalidates identity and lifecycle.

- `steer_agent` with `agent` and `message` cooperatively redirects live work.
- `interrupt_agent` with replacement `message` cancels the current operation
  and continues the same assignment; do not pair it with duplicate steering.
- `reply_agent` answers an eligible correlated `ask_owner` question.
- `read_agent_transcript` reads bounded persisted evidence; `inspect_agent`
  reads bounded live terminal/process evidence when needed.
- `continue_agent` starts one new assignment from the exact saved session path
  or full UUID and a new `task`; it is not a live agent-label control.
  Retired sessions require a fresh Agent with the previous result as evidence.
- `close_agent` abandons eligible owned work; preserve partial repository and
  session evidence and do not close merely because progress looks slow.

Relay material scope/product decisions to the user; resolve ordinary engineering
choices within approved constraints. Unknown identity fails closed. Blocked or
failed work does not unblock dependents. Never silently switch runners.

## 5. Review proportionately

Review deliveries in the owner's context by default, against the actual diff,
acceptance criteria, callers, boundaries and tests. Return one consolidated
correction list. Independent review follows `personal-workflow` authorization;
it is not required per delivery, correction or final changeset.

When authorized, give a fresh `reviewer` one coherent changeset with exact
base/head refs (or a bounded uncommitted diff), checkout and acceptance criteria.
Require `PASS`, `CHANGES REQUIRED`, or an explicit blocked/failed result.
Reviewers report only, never fix. A correction recheck may retain the reviewer's
context and should cover fixes and affected assumptions, not unchanged code.

Return corrections to the implementation owner through an eligible live steer,
or continue its saved session after completion. A retired session needs a fresh
bounded repair Agent. Apply personal-workflow's recovery rule to failed fixes:
gather new evidence, revise the approach, and continue within approved scope.
Ask the user only at its stop-and-ask points.

## 6. Validate and integrate

For every `DONE` delivery, verify the actual diff or committed SHA and test
evidence, resolve required findings, and integrate its baseline-relative delta
promptly. Run focused integrated checks before acceptance or unblocking
dependents. Commit only when authorized.
Preserve failed or unmerged work; never reset or discard it to clear the queue.

The integration owner runs full supported validation on the final combined tree;
reuse passing evidence for unchanged source, dependencies and environment.
Inspect the combined diff and acceptance evidence against the original goal,
including the requested running UI behaviour when applicable. Report integrated
source identity, checks and unresolved work; isolated worker completion is not
application readiness.
Push, merge to the default branch, open a PR, or deploy only when requested.

Apply personal-workflow's stop-and-ask points and Git permissions throughout;
otherwise execute the approved sequence without routine continuation prompts.
