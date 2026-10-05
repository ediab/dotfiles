---
name: bb-pi-control
description: "Control Pi work in BB: inspect, steer, queue, stop, recover, rerun or compact a thread/run, and route explicitly requested delegation to BB child threads. Use for managing Pi work or assigning helpers in BB, not ordinary coding or setup audits."
---

# BB–Pi control

Resolve the target, select its control layer, perform only the requested action,
and verify the result. This skill grants no new authority to spawn workers,
approve interactions, change settings, or discard work.

## Resolve the target

Read `bb-cli` for BB operations. Start with `bb status --json` and inspect the
selected thread with `bb thread show <id> --json`. Resolve an ambiguous target
from a list/search before acting; ask when several candidates remain.

Record the provider, project, environment, and machine. A Pi thread uses the
BB provider `pi`; the AI model/provider inside Pi is a separate selection.
Use the target environment or machine for provider/model queries. For remote
workspaces, use `project-files` or BB host-aware file commands rather than
reading a same-named path on the local disk.

If an action needs a user decision, follow BB's question-tool preference in
its user instructions. Never answer an approval or question on the user's
behalf.

## Choose the control layer

- **BB thread:** use `bb thread ...`; its ID is `thr_...`. Read the relevant
  `bb-cli` reference for thread operation or failure recovery.
- **Pi child run (Herdr pane):** read the run's pi-herdr surface: `herdr_list_agents` for status, `herdr_get_agent_result` for output, `herdr_message_agent` to steer, `herdr_interrupt_agent` to cancel the current turn. Inspecting an existing run does not authorize launching another one.
- **Persistent server or shell:** use `bb terminal ...` scoped to the correct
  thread/environment/machine, not a detached shell process the user cannot see.

A BB thread and a Pi child run are different objects. Do not pass one layer's
ID to the other, treat their concurrency limits as interchangeable, or silently
switch execution layers after a failure. Concurrent writers need separate
workspaces; a worktree separates edits but is not a security sandbox.

## Act on the requested branch

| Request | Action and boundary |
| --- | --- |
| Inspect progress or a blocker | Read status, bounded recent log/output, queued messages, and open interactions as needed. Classify running, queued, awaiting-user, stopped, or failed from evidence. |
| Redirect work now | Send one steer to the identified target. For a BB thread, `bb thread tell` supports `--mode steer`; use a message file/stdin for multiline text. |
| Add a next task | Use `--mode queue` so current work can finish. A queued delivery is not a failed send; report its waiting reason rather than sending again. |
| Stop | Use the target's stop control. Confirm it settled; `stopping` is not proof of termination. Archiving is not an immediate stop. |
| Recover a failed BB turn | Inspect the error, existing queued retries, and workspace changes first. Retry only when requested. Recovery must account for side effects already performed. |
| Edit and rerun a user message | Read `pi-provider`, inspect the eligible message/sequence, and use live `bb thread edit-message --help`. Explain that this changes conversation history and reruns work, but does not revert files. |
| Compact context | Read `pi-provider`. Request compaction of an idle or errored target; verify provider confirmation in the timeline. Compaction is not clearing history or reverting code. |

Use live `--help` for flags rather than assuming every Pi terminal slash command
has a BB equivalent. Confirm provider support before using structured Plan/Goal
actions. Requesting an inspection never authorizes retry, clear, queue bypass,
model changes, or destructive cleanup. If the user stopped work, leave it stopped
unless they request continuation.

For new authorized delegation, read `personal-workflow` for host-specific routing
and `bb-cli`'s thread-creation reference. In BB, create BB child threads parented
to the current thread (`--parent-self`), rather than spawning Herdr agents in the Pi session. Resolve
the project, environment/machine, provider and model before launch; include a
self-contained brief because a new thread does not inherit this conversation.
Use separate workspaces for concurrent writers. For report-only reviewers, the
same environment is acceptable. Keep one clear owner and let background children
report completion. A routing preference never authorizes extra workers, reviews,
or nested fanout; apply the user's delegation rules first. Existing Herdr panes
still use the pi-herdr controls above, and a failed BB launch is not permission to switch layers.

## Complete

Report the target, action, observed result, and any remaining wait or blocker.
Distinguish a request accepted/queued from an operation completed. Use
`@thread:thr_...` for a BB thread link. Yield to native completion notifications;
use a bounded wait only when the request actually requires a completion result.
For a dev server the user should open remotely, read `share-server-links` and
return the Connect URL after checking readiness.
