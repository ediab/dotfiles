---
name: ask-matt
description: Ask which skill or flow fits your situation. A router over the main installed skills and optional workflows.
disable-model-invocation: true
---

# Ask Matt

Use this router only when you explicitly ask which skill or workflow fits. Refer to skills by name; the current agent client determines how to invoke them.

A **flow** is a path through skills. Most work follows the main idea-to-delivery flow; bugs and large efforts are on-ramps. Other skills stand alone or supply shared vocabulary.

## Main flow: idea → delivery

1. **Sharpen the idea.** Use `grill-with-docs` when working in a repository so decisions can be recorded in the project glossary (`GLOSSARY.md` for new projects) and ADRs. Without a working repository, use `grill-me`. Both use the `grilling` interview method; `grill-with-docs` also leaves a project record.
2. **If a runnable answer is needed**, such as testing a state model, business rule, or UI, hand off the focused question, use `prototype` to answer it with throwaway code, then hand the result back to the original work. A prototype is a detour for a question that is hard to settle on paper.
3. **For work spanning sessions**, create a spec with `to-spec`, then split it into blocker-aware tickets with `to-tickets`. Implement one ticket at a time, in a clean context, respecting its blockers. For a small change, use `implement` directly in the current context.

4. **If you want to improve future runs**, explicitly invoke `retro` after a build, especially one that went sideways. It reviews the session for improvements to the agent's environment, not more code changes. Run it before clearing the session, or supply that session's log later. It is an optional follow-up, not an automatic phase.

The implementation procedure owns its testing and verification steps. Use `tdd` on its own when you want to build one concrete behavior test-first. After implementation, use the repository's code-review workflow when one is available; otherwise review the change inline against its intent and project standards.

Keep idea-shaping and ticket planning in one context when their decisions need to carry forward. If the context is approaching its useful limit, pause at a phase boundary and choose an appropriate reset, handoff, or summary rather than continuing with degraded context. See [PHASE-BOUNDARIES.md](PHASE-BOUNDARIES.md).

## On-ramps

- **Incoming bugs or requests you did not create** → use a triage workflow if one is installed. It turns raw reports into agent-ready work; tickets already produced by `to-tickets` do not need triage.
- **Something is broken** → use `diagnosing-bugs`, especially for intermittent failures, regressions, or bugs that resist a first pass. It establishes a tight feedback loop before theorizing, then adds a regression test. After the fix, offer `retro` to examine what would have prevented the bug; run it only when explicitly requested.
- **A huge, foggy effort**—such as a greenfield project or a feature too large to plan in one session → use `wayfinder`. It resolves decision tickets into a shared map; it produces decisions, not implementation. Once the map clears, return to `to-spec`, then `to-tickets` and implementation. If the effort proves small, implement directly instead.

## Codebase health

For upkeep rather than feature work, use a codebase-improvement survey if one is installed. It can surface architecture opportunities; take a selected opportunity through the main idea-to-delivery flow.

## Vocabulary underneath

These skills supply language and concepts to other work. Use them directly when terminology or a design concept is the problem, or let other procedures consult them:

- `domain-modeling` sharpens domain language, resolves overloaded terms, and records important decisions in the project glossary or ADRs.
- `codebase-design`, when installed, provides vocabulary for module shape: interfaces, depth, seams, adapters, and locality.
- `writing-for-agents` guides documents agents consume, including skills and project instructions.

## Phase boundaries

A phase is a meaningful chunk of work, such as exploration, implementation, or QA. Make context-management decisions at the boundary, not in the middle of a phase. The available choices are:

- **Continue** when the next phase needs the current reasoning or comfortably fits in the current context.
- **Reset** when the current context is disposable and none of its decisions need to carry forward.
- **Hand off** when work must move to another client, directory, collaborator, or side task.
- **Delegate** when a task is independently useful, tightly scoped, and can run without your steering.
- **Summarize or compact** when the context still matters but needs more room.

The cheaper, more precise choice should win. In particular, do not discard context that contains decisions or rationale the next phase needs. Use the ordered decision tree in [PHASE-BOUNDARIES.md](PHASE-BOUNDARIES.md).

## Standalone

- `grill-me` is the stateless interview for plans, designs, or writing without a repository. In a working repository, prefer `grill-with-docs` so decisions leave a record.
- `grilling` is the interview method itself. Use it directly when you want the interview without another workflow around it.
- `resolving-merge-conflicts`, if installed, resolves an in-progress conflict hunk by hunk according to each side's intent; use it only when already in a merge or rebase conflict.
- `prototype` answers one design question with throwaway code. Keep the prototype as a source of decisions and point the eventual implementation to it.
- For research, use an available research skill or delegate a tightly scoped reading task, then verify important claims against primary sources.
- `wayfinder` is for work whose decisions cannot yet fit in one session; use its map to reach a buildable plan, not as an implementation ticket.
- Use an available questionnaire workflow when the missing information belongs to someone else; use `grill-with-docs` or `to-spec` to turn the response into a plan.
- Use a setup workflow when a task requires a human-only action such as provisioning credentials or navigating an unfamiliar dashboard. If the agent can perform the action safely, it should do so instead.
- `blast-radius` investigates what a change could break beyond its diff and tests its safety assumptions. It is not a substitute for standards/spec review or diagnosis of an existing symptom.
- `create-verification-skill` creates and proves a project-local recipe for driving the running app. Invoke it to refresh an existing verification skill as well; maintenance is a separate branch, not a new command.
- `why` traces the historical reasons for a design through Git, discussions, and docs, separating documented intent from inference. It does not infer intent merely from current code.
- `unslop` edits supplied writing for clarity and specificity while preserving facts and uncertainty. It is not an always-on style policy.
- `bro` re-explains the previous answer more simply. Use it when the message did not land.

## Precondition

No setup skill is required. These are local-file workflows: specs use the project's established docs location, tickets use `.scratch/<feature>/issues/`, and decision maps use the location established by `wayfinder`.
