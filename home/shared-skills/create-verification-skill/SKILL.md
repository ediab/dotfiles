---
name: create-verification-skill
description: Create and prove a project-local app verification skill, or refresh an existing one.
disable-model-invocation: true
license: MIT
---

# Create a verification skill

Generate instructions another agent can follow cold to exercise the real product and capture proof. The artifact belongs in the target project, not this global skill library.

For an explicit request to maintain or refresh an existing verification skill, read [the maintenance procedure](references/maintenance.md) and follow that branch instead. Do not regenerate a target during maintenance.

## 1. Inspect the repo

Find facts in code and existing docs before asking the user:

- **User entry points:** web, CLI/TUI, desktop, API, mobile, or library interfaces. Name the primary one and any others.
- **Run:** documented startup/build commands, readiness checks, version identity, ports, auth, seed data, and environment prerequisites.
- **Drive:** existing tests and harnesses first, then available browser automation, PTY tools, HTTP requests, or public library calls. Discover actual selectors, commands, and routes.
- **Observe:** screenshots, terminal transcripts, responses, logs, exit codes, persisted state, and external effects.
- **Isolate:** disposable data dirs, profiles, ports, and credentials. Establish ownership of every instance and scratch resource the run will create.

Use a disposable local instance by default. Shared/live state, paid operations, outbound messages, or other external mutations require explicit permission. A dry-run name is not proof of safety: inspect and observe what it actually skips. Stop if safe isolation or access cannot be established. Do not double-drive the user's session.

If the checkout does not build or start, report the precise blocker. Generation does not authorize dependency installation or product repairs. Temporary scaffolding must be explicitly scoped, documented, and removed in cleanup; do not silently hide a broken startup behind it.

## 2. Write the project skill

Default to `.agents/skills/verify-<app>/SKILL.md`; follow an existing project convention only when documented and supported by the active client. Inspect any existing target before editing and preserve unrelated work. Include YAML `name: verify-<app>` and a description naming the app, user interfaces, and verification trigger.

Ground these sections in the repo, with no unresolved placeholders:

- **Launch:** exact commands, prerequisites, isolated state, readiness and build identity, and the lifecycle model. For a short-lived CLI, build once if needed and start fresh per drive; do not invent a persistent server.
- **Doctor:** a read-only check for the right process/build/port/data dir and valid access. Run before the first drive and after surprises; healthy processes with wedged state need a known-state reset or relaunch.
- **Drive:** repo-native commands, routes, or stable selectors. Prefer accessible names and stable attributes over coordinates. No required `control-*` CLI.
- **Evidence:** exact artifact locations and capture commands. Capture action and result; assert the observable user outcome, not just successful execution or a final screenshot. Verify relevant side effects with an independent read. Exercise real entry points, not internal setters or test-only shortcuts; mocks belong only at existing external boundaries. Redact secrets and private data.
- **Cleanup:** teardown on success and failed iterations. Remove only owned instances and scratch state. Track what was started; never kill by process name or remove unrelated/shared data. Evidence lives outside disposable state and survives cleanup.
- **Helpers:** ship only useful helpers, mark executable scripts executable, and document their invocation and dependencies.

## 3. Seed the feature map

Create `features/README.md` and a file per identified user-facing feature, starting with the most important few. State the map's coverage and known omissions; do not silently imply a complete inventory.

Use [the example map](references/feature-map-example/README.md) for shape, not as a source of app commands. Each feature has a plain user-facing description and four H2s: `Sub-features`, `How to get to it (user POV)`, `Driving it with <harness>`, and `Gotchas`. Include prerequisites, entry points, exact actions, and observable results. The README indexes the files and defines common state and proof conventions.

A feature with multiple entry points is not fully verified by driving one convenient route. Unreachable paths need the attempted route and concrete missing prerequisite, not a claim that a different path covers them.

## 4. Prove the generated instructions

Follow the generated skill itself: launch, doctor, drive one mapped feature, capture evidence, and clean up. Re-run after correcting instruction/helper failures; clean failed-attempt residue too. After teardown, check the evidence still exists and shows both the action and the asserted result.

One successful feature proves this recipe is runnable, not that every mapped feature works. Report precisely which features and entry points were executed, which are only mapped, and which were unreachable.

**Completion:** an executed, reproducible recipe with retained proof and verified cleanup. If execution is blocked, hand back a clearly labeled draft with the blocker, not a finished verification skill.

## Report

Name the generated directory, launch/drive commands, proof artifacts, executed and unexecuted coverage, blockers, and cleanup result. Maintenance is available by explicitly invoking this skill to refresh that target; offer it without scheduling it. Commit, apply, deployment, and product fixes remain separately authorized actions.
