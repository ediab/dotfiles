# Working Principles

Project-level `AGENTS.md` / `CLAUDE.md` files layer on top of this one and take precedence where they are more specific.

* Make the smallest correct change that fully solves the task.
* Do not broaden scope or refactor unrelated code unless necessary.
* Inspect relevant code before modifying it. Follow existing project patterns and conventions.
* Do not guess APIs, types, file locations, or library behaviour when they can be verified from the repository or installed dependencies.
* Prefer simple implementations over additional abstractions unless complexity is justified by the task.
* If the task is sufficiently specified, proceed. Ask only when unresolved ambiguity would materially change the implementation.

## Repository Navigation

* Search for relevant files and symbols before reading large parts of the repository.
* Read enough surrounding code to understand interfaces, callers, tests, and local conventions before editing.
* Prefer existing utilities and abstractions over introducing duplicates.
* Treat repository documentation, configuration, tests, and source code as the source of truth.

## Changes

* Preserve existing behaviour unless the requested change requires otherwise.
* Avoid speculative backwards compatibility, fallback paths, or defensive abstractions that are not required.
* Do not remove apparently intentional functionality without confirming that it is part of the requested change.
* Keep changes localized and easy to review.
* Name literals whose meaning is not obvious at the call site.
* For bug fixes, check all callers of the changed function, fix the shared root cause, and verify sibling paths.
* Prefer deletion and reuse, but do not trade correctness or readability for a smaller diff.
* Comment only on non-obvious intent or constraints.

## Validation

* After modifying code, run the most relevant available tests, type checks, linters, or validation commands.
* Prefer targeted checks during iteration; run broader project checks when appropriate before finishing.
* Fix errors introduced by your changes. Do not hide failures by weakening tests, types, or validation.
* Report validation that could not be run.
* Add tests only when failure signals real breakage; skip assertions on styling, colors, or internal structure.

## Review delegation

* Review in the current session by default. Except for the substantial-implementation pass below, spawn a subagent to perform a review only when the user explicitly requests review delegation (for example, "use a reviewer subagent"). This applies regardless of the chosen agent type or tool.
* "Review this", `/review`, generic permission to use subagents, and invoking an orchestration skill or workflow do not by themselves authorize a review subagent. Keep review stages inline unless review delegation was explicitly requested.
* Exception: substantial implementations get an automatic fresh-reviewer pass under Personal workflow below. Standalone review requests still need an explicit request.

## Personal workflow

* Plain English for the user. Technical detail belongs in agent instructions or on request.
* Brainstorming only on explicit invocation (`/skill:brainstorm`): one question at a time with a recommendation; stay with the user's idea; propose smaller versions and let the user decide. End at an agreed short brief; offer chat-only or saving under `docs/specs/`; never auto-start implementation.
* Small, clear, low-risk changes: implement directly. Material uncertainty or substantial/risky changes: inspect first, resolve high-level decisions with the user, present a short plan for approval before implementing.
* Non-trivial plans carry 2–3 agent-proposed, checkable success examples; the user confirms or edits them. They become acceptance criteria for implementation and review. Clear small fixes skip this; the request itself is the criterion.
* After approval, execute the whole approved sequence without "shall I continue?" prompts. Routine technical decisions within approved constraints belong to the agent. Workers escalate material deviations to their owner; the owner asks the user only about changed product intent, material trade-offs, or unapproved risk.
* Substantial changes (a new user-facing flow, behaviour spanning components, a nontrivial refactor, auth/privacy/financial-calculation/data-deletion/deployment changes — impact, not size) get an automatic independent review: the owner dispatches a fresh `reviewer` with the agreed intent, acceptance examples, exact changeset, and validation performed. The reviewer reports only; the owner assigns corrections to the implementer and rechecks affected behaviour. Tiny mechanical edits stay inline.
* Validate proportionately; stronger evidence for money, private data, authentication, and live-service behaviour. Compare the result to the agreed goal and exclusions before claiming completion; state what was checked and what remains unverified. A passing test suite does not prove a live service works.
* Deliver locally by default. Push, deploy, branch, or open PRs only when requested.
* Delegation: the main agent owns the goal and result. Prefer one well-briefed helper over several loosely directed ones; parallelize genuinely independent work. At most 4 active leaf agents (enforced in subagents config). Set `run_in_background` explicitly: background with useful work meanwhile, foreground when the next step depends on the result. Brief every dispatch self-contained (goal, paths, scope, constraints, done-criteria). Use a fresh reviewer per independence check, never a resumed one. `fallbackSubagent` stays `none`.
* Task ownership is end-to-end, never an assembly line: the agent that investigates a change implements, tests, and corrects it. Do not delegate sequential stages of one task (explore → plan → code → fix chains) — every summary handed between agents is context the next agent will never have. Spawn subagents only for meaningfully independent parallel work or a fresh second opinion on a finished artifact, and when a subagent's findings matter, verify them against the underlying files or sources rather than acting on the summary. Delegating to a profile that inherits the full conversation (`worker` pins `inherit_context: true`) forks context instead of summarising it, but that mitigates rather than removes the loss — it is not a licence to split coherent tasks. Planning is never delegated: `/skill:plan` runs in the main session; the `planner` profile is retired.
* Ponytail stays installed with default off; it runs only on explicit user opt-in (`/ponytail lite`, `/ponytail full`). An enabled Ponytail never authorizes unrequested Git operations or overriding approved requirements.

## Model routing

Model IDs live in the agent profiles (`~/.pi/agent/agents/*.md`); this section states routing policy only.

* Implementation runs in the main session, whatever model it uses; there is no mandatory main → `worker` implementation hop. Delegate implementation to `worker` only for genuinely independent parallel workstreams under the Delegation rules — never through `general-purpose`, a model override, or workflow `model`/`effort` values.
* Before delegating, check the pinned model's availability. If it is unavailable, report the blocker — do not silently substitute another model, resume with an override, or retry on a second model as a quality-driven fallback. A failed dispatch is reported, not re-routed.
* Limits: distinguish an unavailable/unresolvable pinned model from an omitted model — the package may use the same model under another provider, then inherit the parent if the pin cannot resolve. Routing is policy, not enforcement; `Agent` profile pins do have enforcement. Workflow `agent()` dispatch lets script `model`/`effort` values override profile pins — so never pass `model` or `effort` alongside a model-pinned role, and always pass an explicit existing `agentType` (workflows default to `general-purpose`).

## Git

* Do not commit, push, rebase, reset, stash, or modify branches unless explicitly requested.
* Do not overwrite or revert unrelated working-tree changes.
* Assume other work may exist in the repository.
* **Standing exception:** `~/dev/configs` and `~/dev/pi-dotfiles` are repos where committing after an edit is expected (see Local environment). Pushing still requires an explicit request.

## Communication

* Be concise and technical.
* State important assumptions, material trade-offs, and unresolved risks.
* When finished, summarize what changed and any relevant validation performed.

## Local environment

### Library and API documentation

Use the `context7` MCP server for library/API documentation — it returns current, version-pinned docs, so it is more accurate than web search or guessing from memory.

Flow: `mcp({ tool: "context7_resolve-library-id", args: '{"libraryName": "react"}' })` to get a library ID, then `mcp({ tool: "context7_query-docs", args: '{"libraryId": ".../react", "topic": "hooks"}' })` for up-to-date docs. Prefer this for exact API signatures, current options, and version-pinned behavior.

### pi-dotfiles sync

Keep pi-dotfiles in sync with the live harness: whenever you install/remove a package, edit `~/.pi/agent/settings.json`, or add/edit a skill, extension, or agent, mirror that change in `~/dev/pi-dotfiles` (`home/settings.json`, `home/skills/`, `home/extensions/`, `home/agents/`) and commit it, so other machines reinstall identically. Packages need no manual mirroring — `sync-settings.sh` records `pi install`/`pi uninstall` into `home/settings.json` automatically. `rebuild.sh` deploys skills/extensions/agents/settings but **not** `AGENTS.md`; `bootstrap.sh` seeds it only when absent, so keep the repo copy in step by hand.

### Dotfiles & configs

Shell, terminal, and editor configs live in `~/dev/configs/` (git repo). Edit them there and commit, so they stay versioned and syncable across machines.

Symlinked (edit in `~/dev/configs/` directly):
- `.zshrc` → `~/.zshrc`
- `ghostty/config` → `~/.config/ghostty/config`
- `starship.toml` → `~/.config/starship.toml`
- `vscode/settings.json` → `~/Library/Application Support/Code/User/settings.json`
- `vscode/keybindings.json` → `~/Library/Application Support/Code/User/keybindings.json`

Pi agent files — `settings.json`, `extensions/` — are **not** in configs. They live in `~/dev/pi-dotfiles/home/` and are deployed to `~/.pi/agent/` as copies by `bootstrap.sh`/`rebuild.sh`. Edit them in `~/dev/pi-dotfiles/home/`, then run `~/dev/pi-dotfiles/rebuild.sh`. Note: `pi` itself rewrites `settings.json` (changelog version, installed-packages list); re-sync live→repo after such changes to avoid backup drift.

Also: `vscode/extensions.txt` — list of installed VS Code extensions, regenerated with `code --list-extensions`.

### VPS access

To access this VPS use `ssh vps` (alias defined in `~/.ssh/config`).
- Host: `77.42.90.4`
- User: `diab`
- IdentityFile: `~/.ssh/id_rsa_nroot`
- ControlMaster multiplexing enabled; LocalForward 18789, 18792, 19999.
- `deploy-vps.sh` mirrors this file to the VPS along with skills, extensions, agents and package configs.

### Dual-edit workflow (local `~/Dev` + VPS `~/apps`)

GitHub is the source of truth for every project that exists in both places. The VPS holds git clones under `~/apps`, never bare rsync copies.
- Edit wherever suits (local or `ssh vps` terminal), then commit and push from there; pull on the other side before editing.
- Never rsync/scp tracked code files to `~/apps`. rsync is only for secrets (`.env`, `.env.vps`), databases, and uploads (`db/`, `userfiles/`, `state/`, episode data).
- Deploy = push to the default branch, then on the VPS `git fetch` plus `git merge --ff-only` (or `git pull --ff-only`) from a clean tree, then the service's restart step. Never `--force` shared history; unmerged VPS work lives on a `vps-*` branch until reviewed.
- On the VPS, git remotes must use the `github-personal` SSH alias (the full-access key). Plain `git@github.com` authenticates as a limited deploy key that only reaches a couple of repos (fastmailai, tfl); `https` remotes with embedded tokens are forbidden.
- Service restart steps: mp3podcasts and redact_pdf via `docker compose up -d --build` in their `~/apps` dir; note-sx via `docker compose pull && docker compose up -d` (image-based) plus the nginx section of its `deploy.sh`; onyx via `docker compose up -d --build` (`scripts/sync_to_vps.sh` is legacy rsync — do not use for code); fousekis API via `sudo systemctl restart fousekis-api` (plain node, no build).
- Not code deploys, no git needed: `~/apps/fousekis-api` (runtime `.venv` plus empty `audio/`/`drafts/`; code lives in the fousekis repo), goatcounter (binary plus sqlite), karakeep/guacamole (third-party images).
