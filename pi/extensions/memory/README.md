# Home Pi memory

A local, dependency-free Pi extension package. Dotfiles links this directory under `~/.pi/agent/extensions/`, so new Pi sessions discover it automatically. Existing sessions need `/reload` or a restart; do not reload someone else's session. No `pi install` or per-project configuration is needed.

## Storage and recall

- `<checkout>/MEMORY.md`: shareable, durable project knowledge. Review it before committing; this package never commits.
- `<Pi agent directory>/memory/<SHA-256 of canonical checkout path>/MEMORY.md`: private project knowledge.
- The same private directory holds `handoffs/<task>.md` and `checkout.json` identifying its checkout.

Files are created only when saved. Private directories use mode 0700 and files mode 0600. Private means **outside Git**, not outside the selected model provider or normal Pi/BB session history. Never save credentials or sensitive datasets.

The repository containing cwd is the initial project. Nested cwd works; Git worktrees have separate private stores and their own branch's project memory. Non-Git directories are supported through explicit selection. Outside a repository there is no automatic project selection. A checkout move changes its private identity; migrate private notes explicitly if needed. Non-Git paths use their on-disk spelling on case-insensitive filesystems. If an older version saved private notes under a differently capitalised path hash, migrate that store explicitly; this version does not move or delete existing stores.

At each agent run, the extension refreshes the active durable files and supplies the snapshot with curation guidance in Pi's structured `home_memory` system-prompt section. Pi records the section in session history and appends a patch only when it changes, preserving append-only prompt/tool updates rather than rewriting the request's beginning. Provider cache behaviour still depends on the provider. The current snapshot remains available after compaction. Tool results and status reflect saves, reads, selection and handoff resume immediately; the automatic prompt snapshot updates at the next agent-run boundary. External edits also appear at that boundary or through explicit read/status. There are no watchers, repository-wide scans or extra model calls.

Memory is labelled reference data, not instructions, even though it is carried in a system-prompt section. Automatically loaded private content is recorded in normal session history, and older versions may remain there after edits or project switches. Code and canonical docs are authoritative. Keep durable memories around 150 lines or 1,200 estimated tokens, and handoffs around 40 lines or 400 estimated tokens; status warns when they exceed those targets without truncating them. Detailed material belongs in canonical project documentation referenced from memory.

## Agent tool

The `memory` tool is callable directly or through Codemode. It returns JSON text; Codemode can use `JSON.parse(await tools.memory(...))`.

```js
// Current scope, revisions, handoff names, load time and approximate tokens.
await tools.memory({ action: 'status' });

// Read before curating; missing files return revision: 'missing'.
const [note] = JSON.parse(await tools.memory({ action: 'read', layer: 'private' }));
await tools.memory({
  action: 'save', layer: 'private', expectedRevision: note.revision,
  content: '# Project memory\n\n- Verified lesson, with source path and date.\n',
});

// Another project's explicit lookup does not change the active scope.
await tools.memory({ action: 'read', path: '/path/to/another/project' });
await tools.memory({ action: 'search', query: 'connector timeout' });

// Explicit scope selection persists on the active session branch.
await tools.memory({ action: 'select', path: '/path/to/project' });

// Save an explicitly paused task, then select it when resuming.
const [task] = JSON.parse(await tools.memory({ action: 'read', layer: 'handoff', name: 'connector-migration' }));
await tools.memory({
  action: 'save', layer: 'handoff', name: 'connector-migration', expectedRevision: task.revision,
  content: '# Connector migration\n\nObjective: ...\nDone: ...\nNext: ...\nTests: ...\n',
});
await tools.memory({ action: 'resume', name: 'connector-migration' });
```

Search is a case-insensitive literal search across the requested project's two durable files and named handoffs. It returns at most 100 matching lines with paths and line numbers, and reports the full match count. It does not search other repositories or follow links.

Switching projects clears the active handoff, not existing conversation history. Start a fresh session when you need a clean knowledge boundary. Selected handoffs stay available until another project is selected (select the same project to clear a handoff).

## Curation and competing writers

Save hard-won, verified lessons and decisions, with dates and source paths. Update existing knowledge instead of appending transcripts or facts copied from obvious source files. If suitability for sharing is uncertain, save privately or ask. Worker agents report proposed changes to their owner rather than writing memory.

Every package save requires a content revision and uses an exclusive per-file lock plus atomic replacement. If another writer won, read again and merge. Use this tool rather than bypassing it with `write`, `edit` or shell commands.

`*.lock` contains the writer PID. A crashed writer can leave a lock or `*.tmp` file: confirm the writer has exited before removing its leftovers manually. Never automatically remove a lock based only on its age. Locks coordinate package writers; arbitrary editor/shell writes are not fully protected. The package rechecks before replacement but cannot make non-cooperating editors transactional. This is not a security sandbox.

## Pi through BB

The tool and lifecycle hooks do not require terminal UI. BB 0.45.0's Pi provider starts the installed Pi CLI in RPC mode without disabling ordinary extension discovery. Live verification results are recorded in `docs/pi-memory/VALIDATION.md` in dotfiles.

If a BB environment does not load the extension, explicitly read the project's `MEMORY.md` with its normal file tool. Private memory/handoff lookup requires the correct checkout identity on that machine; do not pretend it is automatically available. Fix loading rather than silently writing alternate memory files. New workspaces and other machines have independent private stores.

## Tests

From dotfiles:

```sh
node --test tests/test-memory.mjs
bash tests/test-link.sh  # fake HOME only
```

Extension-boundary tests use jiti from the installed Pi release, following this repo's existing test pattern. Set `PI_PACKAGE_ROOT` if Pi is installed elsewhere. No test fixtures write memory into real projects.
