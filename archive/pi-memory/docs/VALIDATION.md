# Home Pi memory — validation

## Environment and scope

Validated locally on the Mac with Pi 1.1.0, BB CLI 0.45.0 and Node 26.10.0. The existing personal extension-directory symlink points to dotfiles, so the new extension directory is already discoverable by fresh sessions. No settings changes, real-project memory seeding, commits, pushes, VPS deployment or reload of other sessions were performed.

## Automated checks

- `node --test tests/test-memory.mjs`: 25 tests cover scoping, missing files, read errors, private persistence/permissions, revision conflicts, independent concurrent processes, busy locks, worktrees, named handoffs, traversal/symlink rejection, invalid checkout metadata, literal search limits, explicit selection, session restoration, run-boundary refresh and concise-file warnings. Added regression coverage verifies non-Git case aliases share private memory on this Mac and Git discovery forces `LC_ALL=C` without changing the parent environment.
- The same suite loads the real TypeScript extension with the installed jiti loader. Its installed-SDK integration test exercises real `ctx.executeTool()` read/invalid calls, verifies Pi's specific schema-validation error, checks that unchanged snapshots preserve the request prefix and memory/tool changes append system updates, confirms snapshot recording in session entries, and checks recall after real compaction. A local mock provider and custom fixture compaction avoid network inference; they are test fixtures, not runtime package features. These checks verify Pi's message layout, not actual provider cache hits or costs.
- `bash tests/test-link.sh`: passed against fake HOME, including concurrent linking and conflict preservation.
- `node --test tests/test-title-in-border.mjs`: existing 24 extension tests passed.
- `node --check` for the storage module and test file, and `git diff --check`: passed.

## Live recall

The following live checks preceded the review follow-up's switch from request-local snapshots to structured system-prompt sections. They have not been rerun for that change; current automated SDK checks cover the new injection path without network inference.

Two fresh standalone Pi processes ran in separate temporary Git projects. Each had a unique non-sensitive public marker in root `MEMORY.md` and a unique private marker in its checkout-specific private memory. Each correctly returned its own two markers with tools disabled. The fixture markers were not included in the prompts. Fixture workspaces and private stores were removed.

One hidden disposable BB Pi thread ran on the Mac in a temporary checkout. It correctly returned both public and private markers from automatic context, without file reads or tool calls. This verifies actual global extension loading and automatic recall through BB, beyond source inspection. The test thread was stopped and archived; its temporary checkout and private notes were removed. BB retains normal archived test history containing only non-sensitive fixtures.

Live requests used the existing OpenAI model configuration and incurred ordinary model usage. No automatic retrieval or maintenance code makes model requests.

## Loading measurement

A local extension-boundary benchmark used two 3,719-byte durable memory files, with 20 warm-up iterations followed by 200 status operations:

| Metric | Result |
| --- | ---: |
| Two-file snapshot refresh, median | 0.097 ms |
| Two-file snapshot refresh, p95 | 0.114 ms |
| Complete status operation, median | 0.126 ms |
| Complete status operation, p95 | 0.149 ms |
| Estimated memory snapshot tokens | 2,017 |

The snapshot estimate includes memory labels, paths and revisions, but not the always-present curation guidance or tool schema. Tokens are character-based estimates, not provider tokenization. Timings measure warm local filesystem reads/context construction, not startup Git discovery, cold disks, model latency or remote filesystems. Status exposes measurements for real projects.

## Remaining limits

- VPS/Linux behaviour was not tested; private stores intentionally do not sync between machines.
- BB recall was tested for one fresh thread. Parallel BB worker curation remains an ownership instruction, not an enforced worker permission boundary. Storage conflict tests cover independent cooperating writers.
- The package does not detect secrets automatically. Private memory enters provider context and automatic snapshots are now recorded in ordinary session history as system-message sections. Older versions may remain in history; snapshots refresh at the next agent-run boundary rather than immediately after tool saves or selection.
- Locks coordinate package-managed writes, not arbitrary simultaneous editor/shell writes. Crashed writers may leave locks that require manual verification and cleanup.
- Private identity follows the checkout's canonical path. Moving a checkout requires explicit private-memory migration, as do older non-Git private stores keyed by a differently capitalised path spelling. Existing stores are not moved or deleted automatically.
- Switching the active project does not erase existing conversation history; use a fresh session for a clean boundary.
