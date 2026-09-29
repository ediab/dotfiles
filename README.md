# pi-dotfiles

Elias's personal [pi](https://github.com/earendil-works/pi) (coding-agent harness) setup.
One repo keeps portable skills and instructions aligned across Pi, Codex, and Claude Code.

## Why this repo exists separately from `configs`

Two repos, one rule: **if the app writes the live file at runtime → it lives here
(copy-deployed). If the app only reads it → it lives in `configs` (symlinked).**

pi manages `~/.pi/agent/` itself — it rewrites `settings.json` on every install and
package code is written into `extensions/` and `skills/` — so a symlink would drag
third-party package code into this repo. Files are **copied** on bootstrap/rebuild
instead (see *How the sync works*). Shell, terminal, and editor configs are read-only
from the app's perspective, so symlinks are fine and simpler — those are `configs`.

This keeps this repo a shareable template ("Make it yours" below) while `configs`
stays plainly personal.

## What you get

Running the bootstrap installs:

- **pi harness** — via npm (`@earendil-works/pi-coding-agent`), falling back to the official
  curl installer (`https://pi.dev/install.sh`) if npm fails.
- **pi packages** — the canonical list is the `packages` array in `home/settings.json`. It stays
  in sync automatically: when you `pi install` / `pi uninstall` on a live machine,
  `sync-settings.sh` records the change in the repo. `bootstrap.sh` installs every package
  in that list. Package-installed skills come along automatically with their packages —
  nothing extra to do.
- **Custom skills** — portable skills under `home/shared-skills/` are copied to
  `~/.agents/skills/` for Pi and Codex, with per-skill links into `~/.claude/skills/`
  when Claude Code is installed. Pi-only skills under `home/skills/` are copied to
  `~/.pi/agent/skills/`.
- **Generated global instructions** — `home/AGENTS.md`, an optional client overlay under
  `home/instructions/`, and an optional machine overlay under
  `~/.config/pi-dotfiles/local/` generate `~/.pi/agent/AGENTS.md`, `~/.codex/AGENTS.md`,
  and `~/.claude/CLAUDE.md` only for installed clients. Edits are drift-guarded and backed up.
- **Custom extensions** — every file under `home/extensions/` (`terminal-status-title.js`),
  copied to `~/.pi/agent/extensions/`. Herdr's integration file is deliberately not vendored
  here (see *What it does NOT install*).
- **Custom agents** — every `.md` under `home/agents/`, copied to `~/.pi/agent/agents/`
  (user agents for `@tintinweb/pi-subagents`).
  `explorer` replaces the built-in `Explore`; disabled overrides keep `Explore`
  and `Plan` from reappearing. Planning runs in the main session via the `plan` skill.
- **Subagent config** — `home/subagents.json` deployed to `~/.pi/agent/subagents.json`
  (`backgroundByDefault`, `reportUsage`, `showCost`, `maxConcurrent: 4` — at most
  4 active leaf agents per task; reviewers and follow-ups count).
- **Open-TUI config** — `home/open-tui.json` deployed to `~/.pi/agent/open-tui.json`
  (footer segments, telemetry toggles, thinking peek).
- **Plan skill** — `home/skills/plan/` (`/skill:plan` or automatic for substantial
  architectural choices: read-only investigation, right-sized plan, offer to save
  to `docs/plans/` unless saving was already requested).
- **Brainstorm skill** — `home/skills/brainstorm/` (`/skill:brainstorm`, explicit
  invocation only: one question at a time with a recommendation, ends at an
  agreed short brief, chat-only or saved to `docs/specs/`; never auto-starts
  implementation).
- **Ponytail default** — `home/ponytail.json` deployed to `~/.config/ponytail/config.json`
  (`defaultMode: off`, so ponytail is opt-in per session via `/ponytail lite`/`full`/`ultra`). This is the same file
  pi's `/ponytail default` command writes. The package's broad main skill
  (`ponytail`, "use on ANY coding task") is excluded from discovery in
  `home/settings.json` so activation comes only from the default mode (no double-trigger); the extension, its `/ponytail` mode
  commands, and the companion skills (`ponytail-review/-audit/-debt/-gain/-help`)
  keep working.
- **Web-search config** — `home/web-search.json` deployed to `~/.pi/agent/web-search.json`
  (pi-web-access routing: TinyFish primary, Exa fallback). The TinyFish key is a macOS
  Keychain lookup (`!security find-generic-password …`), so `bootstrap.sh` leaves the file
  alone; `deploy-vps.sh` writes a Linux variant that reads `~/.pi/agent/tinyfish-api-key`
  (0600, managed directly on the VPS — deploy never overwrites it).
- **Agent config** — `home/settings.json` is the canonical Pi agent settings. The shared
  policy in `home/AGENTS.md` is composed with optional client and machine overlays by
  `sync-agent-content.sh`.

## What it does NOT install

- MCP servers (`~/.pi/agent/mcp.json`)
- Auth / API keys (`~/.pi/agent/auth.json`)
- Provider / model / theme settings (configure those in `~/.pi/agent/settings.json` after
  bootstrap, or edit `home/settings.json` and rebuild)
- The Herdr integration file — `herdr integration install pi` writes and updates
  `~/.pi/agent/extensions/herdr-agent-state.ts` (`HERDR_INTEGRATION_VERSION=8`; check with
  `herdr integration status`, which flags outdated installs). Vendoring it here would let
  `./rebuild.sh` push an older copy over a newer one, and the file no-ops unless
  `HERDR_ENV=1` anyway — so the repo leaves it to Herdr. The `herdr` skill alone does not
  install it.

## Fresh-machine setup

Clone and run (recommended — fully self-contained):

```sh
git clone https://github.com/ediab/pi-dotfiles.git
cd pi-dotfiles
./bootstrap.sh
```

Or run directly via curl (note: the bundled skills and extensions won't be present without
a clone — `bootstrap.sh` will warn and skip them; clone for the full set):

```sh
curl -fsSL https://raw.githubusercontent.com/ediab/pi-dotfiles/main/bootstrap.sh | bash
```

`bootstrap.sh` does four things, in order:

1. Installs the pi harness if it isn't already installed.
2. Deploys `home/settings.json` and installs every package in its `packages` list.
3. Runs `sync-agent-content.sh` for shared/Pi-only skills and generated instructions, then
   deploys `home/extensions/` and the remaining Pi configuration.
4. Installs the launchd auto-sync agent (`com.pi-dotfiles.sync-settings.plist`, templated
   with your repo path) so `settings.json` changes flow back into the repo automatically.

## Daily use

Edit the config files under `home/` in place, then re-apply:

```sh
./rebuild.sh
```

That's `pi update --all` plus the content helper (skills and generated instructions),
`home/extensions/`, `home/agents/`, `home/subagents.json`, `home/web-search.json`, and
`home/settings.json` into their managed destinations.

### Code review

`pi-review` (from the `packages` list) adds two commands:

- `/review` — review uncommitted changes, a base branch, a commit, a GitHub PR (checked out
  locally with `gh`), or a folder snapshot. Reports prioritized findings plus a verdict, and
  separates feedback for the agent from callouts for the human.
- `/end-review` — close an active review session: return only, return and summarize, or
  return and queue the fixing work.

A `REVIEW_GUIDELINES.md` beside the project's `.pi/` directory is appended to the review
prompt, so a repo carries its own review rules without touching this harness.

`home/agents/reviewer.md` is the complementary path, not a duplicate: `/review` runs the
review in the current session, while `reviewer` is a fresh-context, report-only subagent,
used when you explicitly request review delegation. Substantial changes (deletion, auth,
money, live deploy) are reviewed inline by the owner, who offers a fresh reviewer rather
than dispatching one. “Review this”, `/review`, and generic orchestration requests keep
the review inline.
The same explicit-delegation rule applies to research evidence: the owner synthesizes and source-checks it inline rather than dispatching an audit agent.

### Subagent models

Primaries run cheap; implementation happens in the main session — subagents are for
independent parallel work and fresh second opinions, not a default implementation hop.
No profile sets `model:`; subagents inherit the dispatching session's model. There are no
backup profiles and no automatic failover — a failed dispatch is reported as a blocker, not
silently retried on another model. Never pass a `model`/`effort` override unless the user
explicitly names a model (in workflows, always pass an explicit existing `agentType` —
workflows default to `general-purpose`, and orchestrators are forbidden in workflows).

Also: the built-in `general-purpose` profile is overridden; `worker-astra`, `agent-orchestrator`, and `planner` are retired (implementation runs in the main session; use main-session orchestration via `/skill:orchestrate` and main-session planning via `/skill:plan`). No subagent profile runs on Astra; Astra is only ever the main session.

### Observational memory

`pi-observational-memory` runs memory workers (observer/reflector/dropper) that pre-build a
session ledger so compaction becomes a fast, model-free projection. Config lives under the
top-level `observational-memory` key in `home/settings.json`.

Defaults are correct for this setup, so only one key is set:

- `showWorkerNotifications: false` — routine worker progress is hidden (matches the quiet-UI
  prefs above); failures, compaction notices, and `/om:*` output still show.
- Everything else defaults. `model` stays unset so workers follow the rotating session model
  (commandcode custom APIs are supported); the deepseek-flash models' 1M context / 64K max
  output mean `agentMaxTokens` never clamps badly and `compactAfterTokens: 81000` never
  fires late.

Coexists with `@lll9p/pi-better-compaction`: when OM has a non-empty projection it owns the
compaction summary (it loads later, so its hook result wins); the empty-projection fallback
delegates to the native summarizer, which better-compaction upgrades with a cheaper model.

V3 ignores V2 settings and memory formats — no V2 keys exist here, nothing to migrate.
Settings reference: https://github.com/elpapi42/pi-observational-memory/blob/master/docs/configuration.md

### Keeping the repo in sync

| What | Direction | How |
|---|---|---|
| `settings.json` (provider, model, theme, packages) | live → repo, **automatic** | launchd agent (installed by `bootstrap.sh` step 4) watches the live file; `sync-settings.sh` commits any `pi`-made change within seconds |
| `home/shared-skills/`, `home/skills/`, `home/extensions/`, `home/agents/`, Pi config files | repo → live | edit the correct source directory, then `./rebuild.sh`; the helper owns only its recorded skill paths |
| `home/AGENTS.md`, `home/instructions/` | repo → generated live files | shared policy + optional client overlay + `~/.config/pi-dotfiles/local/{pi,codex,claude}.md`; drift is backed up and stops that target |
| `~/.config/pi-dotfiles/local/` | machine → generated live files | optional, untracked client-specific facts; preserved across regeneration |
| `auth.json`, `mcp.json`, `models-store.json`, `code-previews.json`, sessions, caches | never in repo | secrets, runtime state, and per-machine package configs, by design (`deploy-vps.sh` still mirrors `code-previews.json` onto the VPS). `models.json` is gone: it declared only the deprecated `opencode-go/omen-alpha` shim; provider models come from the built-in catalog |

Bottom line: settings reflect into the repo by themselves; the repo owns portable and
Pi-only skill sources, extensions, and shared/client instruction sources. Machine overlays,
ownership state, hashes, and backups stay local.

## Make it yours

This repo is Elias's. If you clone it, review these before you run `bootstrap.sh`:

- **Packages**: `pi install <pkg>` / `pi uninstall <pkg>` on a live machine —
  `sync-settings.sh` records it in `home/settings.json` — or edit `home/settings.json`'s
  `packages` list directly.
- **Skills**: add portable skills under `home/shared-skills/` and Pi-only skills under
  `home/skills/`. `sync-agent-content.sh` deploys only these repo-owned sources, records
  exactly which paths it owns, and refuses same-name unmanaged collisions. Ordinary runs
  prune only paths in that machine's manifest. If the manifest is missing, nothing is
  pruned and existing destinations need explicit adoption again.
- **Third-party skills**: inspect candidates with `npx skills@latest add owner/repo --list`.
  After review, vendor portable skills into `home/shared-skills/` or Pi-specific skills into
  `home/skills/`, preserve their license and attribution, and remove vendored names from the
  Vercel lockfile. A skill name has one owner. `show-me` is upstream/Vercel-owned; keep it
  outside these source folders and install it with `npx skills add humanlayer/skills --skill show-me -g`.
  `bro` is the exception: its reviewed upstream copy is vendored verbatim in this repo.
- **First migration**: inspect before applying. `--adopt` prints the audited path/action plan
  without changing anything; only the approved local command applies it:

  ```sh
  ./sync-agent-content.sh --adopt
  ./sync-agent-content.sh --adopt --yes
  ```

  Backups and the ownership manifest stay in `~/.local/state/pi-dotfiles/`. Use `--force --yes`
  only after reviewing a generated-instruction drift backup.
- **Extensions**: everything under `home/extensions/` is copied; no script edit needed.
- `home/settings.json` keeps `"!**/.agents/skills/use-tinyfish"` and
  `"!**/.agents/skills/simplify"` so Pi does not load externally owned shared copies twice
  (Pi does not expand `~` in these glob patterns). `-skills/use-tinyfish/SKILL.md` also stays
  as protection if `tinyfish connect` recreates a Pi-local copy. Neither skill is mirrored
  into this repo; external installers keep ownership and the sync helper leaves them alone.
- The vendored `bro` skill uses each client's native invocation: Pi `/skill:bro`, Codex
  `$bro`, and Claude Code `/bro`. These are client-specific entry points; no extra
  slash-command wrappers are installed.

**Heads-up:**

- `home/AGENTS.md` is Elias's personal shared agent policy. If you clone this repo you'd
  inherit it in every installed client — edit or delete it if you don't want that. Put
  machine-only content in `~/.config/pi-dotfiles/local/{pi,codex,claude}.md` instead.
- `home/settings.json` is the repo copy of your live pi agent settings. pi itself rewrites
  the live file (changelog version, installed-packages list). `sync-settings.sh` (below)
  keeps the repo copy fresh automatically; if you edit the live file by hand, re-sync it
  back into the repo before your next `./rebuild.sh` to avoid clobbering local changes.

## Repo tour

- `home/` — configuration sources: `home/shared-skills/` -> `~/.agents/skills/` with Claude
  links, `home/skills/` -> `~/.pi/agent/skills/`, `home/AGENTS.md` plus
  `home/instructions/<client>.md` -> generated `AGENTS.md`/`CLAUDE.md` targets,
  `home/settings.json` -> `~/.pi/agent/settings.json`, plus Pi extensions, agents, and configs.
  The helper's machine-local manifest, instruction hashes, and backups live under
  `~/.local/state/pi-dotfiles/`; local instruction overlays live under
  `~/.config/pi-dotfiles/local/`.
- `bootstrap.sh` — fresh-machine setup. Run once.
- `rebuild.sh` — re-apply the config after any change. Supports `--sync-only` to deploy
  skills, generated instructions, extensions, and agent config without package updates or
  the `settings.json` copy.
- `sync-settings.sh` — auto-syncs the live `~/.pi/agent/settings.json` back into
  `home/settings.json` when pi rewrites it. Triggered by the launchd agent
  `com.pi-dotfiles.sync-settings.plist` (a template in this repo, installed and path-substituted
  by `bootstrap.sh` step 4; watch path: `~/.pi/agent/settings.json`).
- `deploy-vps.sh` — syncs settings, auth, agents, extensions, and package configs to the VPS.
  It stages skill and instruction sources under `~/.cache/pi-dotfiles-agent-content/` and runs
  the same helper there; native skill roots are never rsynced with `--delete`. Use
  `deploy-vps.sh --prepare-agent-content [host]` to stage only, then review/apply the helper
  remotely with `--adopt` as needed. Normal deploy never enables adoption or force.
  `mcp.json` stays per-machine (its `youtube-music` server runs a local macOS node build).
  Normally invoked automatically by the configs repo's `com.diab.sync-vps` launch agent
  (change-gated, every 15 minutes); run it by hand when you want the VPS updated now.
  Stable interface: `deploy-vps.sh [host]`. It reads only its own `home/` plus the live
  `~/.pi/agent/` files noted here (`settings.json`, `auth.json`, `code-previews.json`) —
  nothing outside this repo — and takes the target host as `$1` (default `vps`), so the
  configs orchestrator can call it without knowing its internals.
- `CONCEPTS.md` — shared domain vocabulary (glossary, tracked). `docs/specs/` holds
  saved briefs/plans (tracked); `docs/plans/` is gitignored scaffolding recreated on demand.
  All historical documents were removed on 2026-09-16 as stale — the workflow spec had
  been fully implemented and the rest described retired setups.

## How the sync works

`sync-agent-content.sh` is the only writer of deployed skills and generated global
instructions. It copies shared skills to `~/.agents/skills/`, links those copies into Claude
when installed, copies Pi-only skills into `~/.pi/agent/skills/`, and prunes only paths listed
in its machine-local manifest. Other clients' skill directories and unmanaged skills are
left alone. Instruction targets combine the generated header, shared policy, repo overlay,
and optional local overlay; hashes detect edits, and backups are retained under
`~/.local/state/pi-dotfiles/backups/`.

`bootstrap.sh` and `rebuild.sh` call the helper locally. `deploy-vps.sh` stages the same
sources in a dedicated remote directory and calls the same helper against the VPS's own
manifest and local overlay. No local state or local overlay is sent to the VPS.
