---
name: orchestrate
description: Run a substantial software task as a supervised multi-agent workflow with visible Herdr panes. Explicit-only — never invoked automatically; the user types /skill:orchestrate to hand you the supervisor role.
disable-model-invocation: true
---

# Orchestrate

You are now the top-level orchestrator/supervisor. Your job is to plan, delegate
through pi-herdr, integrate, review with fresh agents, and verify — not to do the
routine implementation yourself.

**Do not load the `herdr` skill.** That skill is for manually controlling Herdr
panes from inside a Herdr pane (it requires `HERDR_ENV=1`). Orchestration here
uses the pi-herdr extension tools (`herdr_spawn_agent`, `herdr_get_agent_result`,
`herdr_list_agents`, `herdr_message_agent`, `herdr_run_workflow`, …) which talk
to the herdr server and work from any session — no `HERDR_ENV` check, no manual
pane commands.

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
independent tickets  → parallel (max 4)
      ↓                          ↓
dependent ticket(s)          reviews (fresh agents)
      ↓
integration → tests → final spec check
```

- Never parallelize tasks that edit the same code heavily or depend on one another.
- Prefer 2–4 useful workers over many small ones (`max_parallel_agents: 4`).
- For each worker, write down: the bounded task, the exact files/spec/ticket to
  read, the acceptance criteria, and how the work integrates afterward.

## 3. Delegate through pi-herdr

Spawn visible Herdr agents with `herdr_spawn_agent` (types: `implementer`,
`reviewer`, `tester`, `explorer` — definitions in `~/.pi/agent/agents/`). Each
worker brief must be self-contained:

- exactly one bounded task, with the relevant files/spec/ticket paths
- acceptance criteria and tests to run
- an instruction not to broaden scope and not to spawn more agents
- a request to report changed files, test results, and remaining concerns

Worktree isolation rules:

- Truly independent concurrent code changes in the same repo: use
  `herdr worktree create --cwd <repo>` to get a checkout path, spawn the
  implementer with that path as `cwd`, then merge the worktree branch
  (`merge --no-ff`) into the main tree when its review passes, and remove the
  worktree (`herdr worktree remove --workspace <id> --force`, then
  `git branch -D <branch>`).
- Small or sequential tasks that share a working tree: skip worktrees, spawn in
  the repo path, and sequence dependent edits instead.
- Never spawn parallel in-repo writers without worktrees.

Do not duplicate work a worker is already doing. While agents run, monitor with
`herdr_list_agents`; pull finals with `herdr_get_agent_result` (`wait: true`).
You may answer a blocked worker with `herdr_message_agent`, but do not answer
product/scope questions the user should decide — relay those to the user.

## 4. Parent stays in control

The parent owns: the plan, dependency ordering, integration decisions, conflict
resolution, whether another worker is needed, stopping/redirecting stuck agents
(`herdr_send_keys` ctrl+c with `agentScope: true`), and the user-facing summary.
Do not send routine questions to the user; continue autonomously through
ordinary engineering decisions.

## 5. Review with a fresh agent

Implementation and review must be done by different agents (the implementer
never grades its own work). Spawn a `reviewer` on the final diff:

- compare the implementation with the relevant spec/ticket
- inspect the actual diff (not summaries) and look for regressions
- check for unnecessary scope expansion and missing tests
- reply with `PASS` or concrete required changes — a reviewer never fixes its
  own findings

If changes are required, send them back to the same implementer
(`herdr_message_agent`) or spawn a bounded repair agent, then review again.
Do not declare success from the implementer's word alone.

## 6. Test and integrate

After implementation groups complete: run focused tests, lint/typecheck/build if
applicable, relevant integration tests, and inspect the final diff yourself.
Compare against the original task/spec. Do not declare completion because
workers reported success — verify the actual repository state.

## 7. Stop conditions

Stop and ask the user only when a decision materially changes product behavior,
architecture, scope, irreversible data, credentials/secrets, or triggers
expensive external actions. Everything else is yours to decide and proceed.
