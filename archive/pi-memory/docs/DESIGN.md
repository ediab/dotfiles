# Home Pi memory — confirmed design

The user confirmed this design, including its final rules and acceptance examples. The implementation plan in [PLAN.md](PLAN.md) was approved and implemented. Automated checks and live standalone/BB recall results are in [VALIDATION.md](VALIDATION.md).

## Agreed boundaries

- Build a home-only Pi package; sharing an implementation with work is out of scope.
- Home projects are independent. Their common parent directory is not a shared memory scope.
- Use split ownership: shareable project knowledge belongs to its project; private knowledge and transient task state belong outside tracked repositories.
- Target Pi, including occasional use of Pi through BB. Fresh-session automatic recall has been verified through BB on the Mac. Claude and Codex integration are out of scope.
- Keep this design in dotfiles. Dotfiles is public: private memory content and work-specific material must not be stored here.
- Preserve existing instructions, documentation and unrelated working-tree changes.

## Agreed first-version behaviour

- Default project storage is one root `MEMORY.md`; directories and component scopes are added only when needed.
- Automatically retrieve current-project memory. Other projects require explicit lookup initially.
- Private memory is local to each machine, outside tracked repositories. No private-memory synchronization in the first version.
- Pi may curate meaningful findings automatically within the relevant scope. Changes remain uncommitted; workers propose updates rather than overwrite shared files.

## Verified Pi documentation

- Context instructions are discovered from the agent directory, cwd and ancestors, not automatically from descendant directories.
- Extensions support lifecycle/context hooks and external storage. The exact retrieval and refresh implementation remains to be selected.
- Nested tool execution through `ctx.executeTool()` emits tool hooks, including Codemode's supported tool calls. This does not mean arbitrary shell filesystem access is observed.

## Agreed isolation and handoffs

- Private memory is project-specific. General preferences and procedures remain in existing global policy and skills.
- Private memory is isolated by checkout, including Git worktrees. Tracked project memory follows its branch.
- Handoffs are separate named tasks in private storage, saved on explicit request or explicit pause. Resume selects a handoff explicitly.
- The initial active project is the repository containing cwd. Outside a repository, project selection is explicit. Switching to another project is explicit rather than inferred from prose or file access.

## Confirmed design contract

- Keep the home-only local package in dotfiles and load it globally; do not publish an npm package initially.
- Use root `MEMORY.md` for shareable project knowledge and a private, untracked per-checkout store under the Pi agent directory for private `MEMORY.md` and named handoffs. Create files lazily.
- Automatically present only the active project's concise durable memories. Handoffs and other projects require explicit selection or lookup.
- Keep current memory available after compaction; detect file changes at agent-run boundaries rather than watch every file or scan every repository. Verify the concrete hook against installed SDK types before implementation.
- Missing memory is normal. Read failures are reported rather than silently treated as absence. Source and canonical documentation outrank saved memory.
- When sharing suitability is uncertain, save privately or ask. Private storage is not a secret vault: never deliberately record credentials or sensitive datasets. This is a curation policy, not a guarantee of automatic secret detection.
- Use conflict-aware updates for package-managed writes. Workers propose changes to the owner; independent sessions must detect changes made since their read rather than silently replace another session's updates.
- Verify automatic loading in Pi through BB; if unavailable, document an explicit Markdown lookup fallback and the limitation. Do not claim automatic BB support from standalone Pi tests.
- Explicit lookup, project selection, save and status operations must work without terminal UI and without extra model requests.

## Confirmed acceptance examples

1. Fresh Pi sessions in projects A and B automatically receive only their own tracked and private memory. A session launched outside a repository loads no project until explicitly selected.
2. A meaningful discovery survives a fresh session. Another session's update is not silently overwritten. A branch worktree has independent private memory, and private content is not written into dotfiles or project memory.
3. Two named handoffs in one project can be selected independently. Compaction and memory edits do not leave the active memory permanently missing or stale. Test recall in a real Pi-through-BB session and report any fallback required.

## Validation

Retrieval, refresh, compaction and conflict-aware saves were exercised against the implementation. Fresh standalone Pi sessions and a real Pi-through-BB task recalled project and private fixture memories. Local loading latency and estimated memory context overhead were measured. See [VALIDATION.md](VALIDATION.md) for scope, evidence and remaining limits.

Private memory is outside Git, but relevant content still enters the selected model provider's context. The review follow-up approved carrying the automatic snapshot in a structured system-prompt section: snapshots and subsequent changes are recorded in normal Pi/BB session history, and automatic refresh happens at the next agent-run boundary. Memory remains labelled reference data, not authoritative instructions.
