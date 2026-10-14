---
name: personal-workflow
description: Default coding workflow — target, inspect, change, verify, report — with approval stops and Git rules. Use for multi-step coding, a plan-approval decision, or before authorized delegation. Not for a one-line edit.
---

# Personal workflow

One agent does the work end to end. Specs, tickets, reviewers and extra agents are opt-in.

## Loop

1. **Target.** Before editing, state in one line what will change, where, and how it will be checked ("Add Min price to the existing top-right filter; verify it filters the list"). Then continue; this is not an approval request. For UI, name the actual control or page the user means.
2. **Inspect.** Read the relevant code, callers, tests and project instructions. Verify uncertain APIs against installed code or primary docs.
3. **Change.** Make the smallest complete change, following existing patterns. Reuse existing utilities; add no speculative fallbacks, compatibility paths or abstractions. Fix shared root causes and check sibling callers. Leave unrelated code and work alone.
4. **Verify.** Run the affected checks, then exercise the requested behaviour itself (for UI, in the running app). Re-read the diff against the request. Never weaken tests, types or validation to pass.
5. **Report.** What changed, what passed, what was not verified.

Done = step-4 evidence for the exact target from step 1.

## Stop and ask only when

* a material product or architecture choice cannot be resolved from the request or existing conventions;
* the work requires unapproved changes to authentication, credentials, privacy or financial calculations, destructive data operations, deployments or external systems, or paid or long-running external jobs;
* the scope grows beyond the request.

Routine read-only inspection and isolated local checks may proceed within scope. Ordinary technical choices belong to the agent. A clear request authorizes its stated scope and risks, however many files or steps; finish approved work without further permission prompts. Planning skills (`brainstorm`, `to-spec`, `to-tickets`) run only when invoked, and planning is not approval to implement.

## When stuck

After two unsuccessful fixes or a disproved assumption, gather new evidence and revise the approach before trying again. Briefly explain the change of approach and continue within approved scope; ask only at the boundaries above. If the revised approach also fails, or no evidence-based next step is available, report the blocker with evidence rather than repeat guesses.

## Testing

Use focused checks while iterating, then broader checks where project requirements, affected scope or risk warrant them: shared contracts, callers, dependencies, configuration, authorization or data. Risk, not diff size, sets the breadth. Reuse passing results only while source, dependencies and environment remain unchanged; rerun what later changes invalidate.

For bugs, reproduce with a failing check first when practical. Test behaviour and real failure cases, not styling or internals. Expected values come from requirements, not from the code's output. Use TDD only when requested directly or through an explicitly invoked workflow that includes it.

## Git

Commit only when explicitly requested or included in an explicitly invoked implementation workflow. Push, deploy, open PRs, rebase, reset, stash or create, switch or merge branches only when explicitly requested. Preserve unrelated staged, unstaged and untracked work. Keep runtime state and caches out of Git unless the project versions them.

## Extra agents

Authorization and routing follow the delegation rules in `AGENTS.md`. When authorized:

* Default to one helper, at most two. Add one only for independent work with a checkable result.
* Inside BB, create a child thread with `--parent-self` (read `bb-cli` first) and a self-contained brief: goal, baseline, owned paths, exclusions, checks, and "report only, no further delegation" where it applies.
* The main agent stays the owner: it integrates, verifies findings against the source, and runs the final checks. Report-only reviewers may share the checkout; concurrent writers need separate worktrees.
* Yield to completion notifications instead of polling.

Higher risk calls for stronger verification, not more implementers. For hard-to-reverse changes, offer an independent review; the user decides.
