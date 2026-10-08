# Home Pi memory — implementation plan

Status: approved and implemented. The design in DESIGN.md is confirmed; checks and live recall results are in [VALIDATION.md](VALIDATION.md).

## Verified on this Mac

- Pi CLI version: 1.1.0. BB CLI version: 0.45.0.
- Installed Pi `dist/core/extensions/types.d.ts` declares `before_agent_start` and request-local `context` transformations. `docs/extensions.md` and `docs/message-types.md` describe custom context messages and external storage.
- BB's installed `server/dist/builtin-plugins/provider-pi/dist/host.js` launches Pi with `--mode rpc`, an explicit bridge extension, session options and workspace cwd. The inspected launch argument construction does not disable ordinary extension discovery. This is source evidence, not a successful live recall test.
- Dotfiles already links `pi/extensions/` into the personal Pi extension directory. A directory with `index.ts` is discovered as an extension, so no copied extension in each project is needed.

## 1. Local extension package and storage

Create `pi/extensions/memory/` with a small `index.ts` adapter, a standard-library-only storage module, package metadata and concise usage documentation. Use existing extension-directory linking; no npm publication or new runtime dependency.

- Find the initial project root from cwd with Git; outside a repository, start without an active project until explicit selection.
- Key private storage by a hash of the canonical checkout root, under the actual Pi agent directory's `memory/` directory. Keep separate Git worktrees isolated. Store the root identity in private metadata for diagnostics.
- Use root `MEMORY.md` for shareable memory and private `MEMORY.md` plus named handoff files for private state. Create files lazily and private directories/files with restrictive permissions.
- Validate selected roots, handoff names and write targets. Handle missing files normally and surface other errors.
- Package-managed saves use expected content revisions, an exclusive cross-process lock and atomic replacement. Reject conflicting/stale saves and busy locks without overwriting. This protects cooperating package writers, not arbitrary simultaneous editor or shell writes.

## 2. Retrieval and agent operations

- Read/cache active durable memory at run start and refresh tool results after package-managed saves or explicit selection/lookup. The automatic prompt snapshot changes at the next agent-run boundary.
- Supply curation guidance and a clearly labelled reference snapshot in `systemPromptOptions.sections.home_memory` from `before_agent_start`. Pi persists the section and appends changes rather than collapsing prompt/tool updates into a rewritten leading system message. Keep current memory available after compaction; unchanged snapshots produce no extra section patch.
- The original request-local `context` design was replaced with the user's approval during review follow-up. Automatically loaded memory now enters session history as system-message content, including private memory; older versions can remain in history. Memory remains reference data, not authoritative instructions.
- Offer small model-callable operations for explicit project selection, memory lookup/keyword search, conflict-aware saves, named handoff save/resume and status. Operations work through Codemode and without terminal UI.
- Preserve explicit project selection across session resume using non-context session metadata. Reconstruct from the active branch and reset correctly on session changes.
- Load other project memories only on explicit lookup or selection; load handoffs only on explicit resume.
- Report active paths, revisions, load duration and approximate memory tokens in status. Label token counts as estimates. Use concise-file guidance and warnings, not silent truncation.
- Supply Pi-only curation guidance from the extension: sources outrank memory; save durable discoveries; uncertain sharing goes private or requires approval; workers report proposed updates; use the conflict-aware save operation. Keep shared Claude/Codex global policy unchanged.

## 3. Checks and documentation

Create `tests/test-memory.mjs` using Node's test runner and temporary roots/private stores. Cover scope isolation, missing/read-failure cases, worktrees, fresh-session persistence, named handoffs, invalid targets, stale saves and concurrent package writers.

Use a minimal extension harness and installed Pi runtime to verify registration, stable prefixes, append-only memory/tool updates, nested-tool schema validation, run-boundary refresh, session selection and post-compaction retrieval without model inference where possible. Measure load overhead with small fixture memories; report measurements rather than claim negligible latency in advance.

After local checks pass, enable the globally discovered extension through the existing dotfiles link and document reload/restart requirements. Do not disrupt other active sessions.

Verify fresh-session recall in standalone Pi and a disposable Pi-through-BB task with non-sensitive fixture memory. A live BB test starts a task and may incur model usage: obtain explicit permission if implementation approval does not authorize that test. If automatic BB recall is unavailable, document explicit Markdown lookup and its limitation.

Update package usage docs, DESIGN.md verification notes and the dotfiles README. Run the relevant linker test with a fake HOME. Preserve unrelated changes; do not commit, push or deploy to the VPS.

## Boundaries

- Private means untracked and machine-local, not excluded from the selected model provider or ordinary Pi/BB session history.
- Memory is potentially stale knowledge, not authoritative instructions or a secret vault.
- No automatic cross-project inference, global personal-memory layer, memory sync, background summarisation, embeddings or component index.
- Shared MEMORY.md is a normal Git file; the package does not commit it or resolve Git merge conflicts.
- Private identity follows the canonical checkout path. Moving a checkout does not automatically migrate its private memory in the first version.
