# Authorized delegation

This reference supplies execution mechanics for `personal-workflow`; it grants no permission to launch workers. The main agent owns scope, synthesis and final verification.

## Choose the runner and model

* Inside BB (`BB_THREAD_ID` is set), use BB child threads with the current thread as parent; read `bb-cli` before dispatch. Standalone Pi uses pi-herdsman only for explicitly requested orchestration; other standalone clients use their native tools. An explicit user choice of another runner takes precedence when supported.
* Existing workers stay with the runner that launched them. Never silently replace a failed run through another runner or agent. A delegated worker must not start another orchestrator.
* Inspect the selected profile's tools, scope and model/thinking overrides. In BB, select and verify the worker model at creation. Fresh unpinned Herdsman workers inherit the controller's model and thinking; continued sessions use their saved selection unless overridden. Verify the resolved choice rather than describing an inherited worker as cheaper. Keep choices task-specific, not permanently pinned in shared profiles.

## One owner, one integrated result

* Name one implementation/integration owner and one canonical working tree at the start. Default to the main agent; if explicitly orchestrator-only, assign that ownership to one child immediately, not to a final integration ticket.
* Ownership is end-to-end: investigate, implement, test and correct. Add a helper only for independent work with a stable input contract, separable edits and a checkable result. Shared-file or evolving-interface work stays with one writer or runs sequentially. Concurrent writers require isolated worktrees; isolation alone does not make their changes independent.
* Use dependencies to find the critical path, then check edit/interface overlap. A concurrency limit is a ceiling, not a staffing target. Respect the client's limit; if none exists, use at most four active agents.
* Brief each helper with the goal, exact baseline, owned paths/interfaces, exclusions, acceptance criteria and focused checks. Reference shared rules rather than copying them. Use fresh context for independent work; preserve context needed for corrections.
* Integrate each accepted delta promptly against its recorded baseline. Reconcile overlapping regions while preserving both behaviours and regression tests; whole-file precedence is not a merge strategy. Run affected combined checks before dependent work starts, and give those workers the integrated baseline.

## Verify and hand off

* Helpers run assigned focused checks. The integration owner runs affected checks after integration and full supported validation on the final combined tree. Reuse evidence for unchanged source, dependencies and environment. The main agent verifies the evidence even when a child owns implementation.
* Verify material worker findings against underlying files or primary sources. Completion requires an integrated source identity and passing affected checks, not just a success report.
* Independent reviews follow `personal-workflow` authorization. Start a fresh reviewer for a second opinion; a focused correction recheck can retain that reviewer's context. Reviewers report only; the implementation owner makes corrections.
* Handoffs include baseline/result identities, changed files, exact check results including skips, material gaps, owned-resource cleanup and the absolute workspace path. Unrelated broad checks belong to the integration owner.
* Use completion notifications; yield when only helpers are running rather than polling. Foreground waiting is for a necessary dependency. Escalate material deviations to the owner, who asks the user only at personal-workflow's stop-and-ask points.
* Report implemented → integrated → validated, with application to the target checkout and deployment explicit. Worker counts and duplicate notifications are not product progress.
