# pi-dotfiles

Elias's personal [pi](https://github.com/earendil-works/pi) (coding-agent harness) setup.
One repo, one command, and a fresh machine ends up with the same pi config every time.

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
- **Custom skills** — every directory under `home/skills/`, copied to `~/.pi/agent/skills/`
  (the path pi actually scans).
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
  (`defaultMode: lite`, so ponytail is active on coding tasks and names the lazier alternative in one line —
  switch levels with `/ponytail full`/`/ponytail ultra`, off with `stop ponytail`). This is the same file
  pi's `/ponytail default` command writes. The package's broad main skill
  (`ponytail`, "use on ANY coding task") is excluded from discovery in
  `home/settings.json` so activation comes only from the default mode (no double-trigger); the extension, its `/ponytail` mode
  commands, and the companion skills (`ponytail-review/-audit/-debt/-gain/-help`)
  keep working.
- **Custom models** — `home/models.json` deployed to `~/.pi/agent/models.json`
  (provider + model defs).
- **Web-search config** — `home/web-search.json` deployed to `~/.pi/agent/web-search.json`
  (pi-web-access routing: TinyFish primary, Exa fallback). The TinyFish key is a macOS
  Keychain lookup (`!security find-generic-password …`), so `bootstrap.sh` leaves the file
  alone; `deploy-vps.sh` writes a Linux variant that reads `~/.pi/agent/tinyfish-api-key`
  (0600, managed directly on the VPS — deploy never overwrites it).
- **Agent config** — `home/settings.json` deployed as the canonical pi agent settings, and
  `home/AGENTS.md` seeded to `~/.pi/agent/AGENTS.md` (only when absent).

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
3. Copies `home/skills/`, `home/extensions/`, and seeds `home/AGENTS.md`.
4. Installs the launchd auto-sync agent (`com.pi-dotfiles.sync-settings.plist`, templated
   with your repo path) so `settings.json` changes flow back into the repo automatically.

## Daily use

Edit the config files under `home/` in place, then re-apply:

```sh
./rebuild.sh
```

That's `pi update --all` plus a re-sync of `home/skills/`, `home/extensions/`,
`home/agents/`, `home/subagents.json`, `home/models.json`,
`home/web-search.json`, `home/settings.json` into `~/.pi/agent/`.

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
| `home/skills/`, `home/extensions/`, `home/agents/`, `home/subagents.json`, `home/models.json`, `home/web-search.json`, `home/ponytail.json`, `home/open-tui.json` | repo → live | edit in the repo, then `./rebuild.sh`; live edits are overwritten (copy back after tuning subagents) |
| `home/AGENTS.md` | repo → live (seed only) | seeded only when absent — local-only environment facts (VPS, symlinks, deploy) live in the `local-env` skill, not in this file |
| `auth.json`, `mcp.json`, `models-store.json`, `code-previews.json`, sessions, caches | never in repo | secrets, runtime state, and per-machine package configs, by design (`deploy-vps.sh` still mirrors `code-previews.json` onto the VPS) |

Bottom line: your settings reflect into the repo by themselves; the repo is the source of
truth for skills, extensions, and the base `settings.json` that gets deployed to new machines.

## Make it yours

This repo is Elias's. If you clone it, review these before you run `bootstrap.sh`:

- **Packages**: `pi install <pkg>` / `pi uninstall <pkg>` on a live machine —
  `sync-settings.sh` records it in `home/settings.json` — or edit `home/settings.json`'s
  `packages` list directly.
- **Skills**: add/remove a directory under `home/skills/` — no script edit needed, every
  dir is deployed automatically.
- **Extensions**: everything under `home/extensions/` is copied; no script edit needed.
- `home/settings.json` carries hand-written `skills` exclusions,
  `"!**/.agents/skills/use-tinyfish"` and `"!**/.agents/skills/simplify"`.
  External installers drop their bundled skills into every harness dir they recorded —
  including the canonical `~/.agents/skills/` that serves codex/opencode — and pi scans
  that dir too, so the same skill loads twice and pi opens with a `[Skill conflict]`
  warning. The `!` globs hide the shared copies from pi (`~` is not expanded in these
  patterns, so the glob form is required); drop one if you stop using that skill elsewhere.
  The pi-side copies in `~/.pi/agent/skills/` are mirrored into `home/skills/` and deployed
  like any other skill. `tinyfish connect` rewrites the live copy when TinyFish updates, so copy it back
  (`cp ~/.pi/agent/skills/use-tinyfish/SKILL.md ~/Dev/pi-dotfiles/home/skills/use-tinyfish/`)
  before the next `./rebuild.sh`, which would otherwise push the older snapshot over it.

**Heads-up:**

- `home/AGENTS.md` is Elias's personal agent policy. If you clone this repo you'd silently
  inherit it — edit or delete it if you don't want that.
- `home/settings.json` is the repo copy of your live pi agent settings. pi itself rewrites
  the live file (changelog version, installed-packages list). `sync-settings.sh` (below)
  keeps the repo copy fresh automatically; if you edit the live file by hand, re-sync it
  back into the repo before your next `./rebuild.sh` to avoid clobbering local changes.

## Repo tour

- `home/` — the actual config files, mirroring `~/.pi/agent/` one-to-one:
  `home/settings.json` -> `~/.pi/agent/settings.json`, `home/skills/` -> `~/.pi/agent/skills/`,
  `home/extensions/` -> `~/.pi/agent/extensions/`, `home/agents/` -> `~/.pi/agent/agents/`,
  `home/subagents.json` -> `~/.pi/agent/subagents.json`,
  `home/models.json` -> `~/.pi/agent/models.json`,
  `home/web-search.json` -> `~/.pi/agent/web-search.json`,
  `home/open-tui.json` -> `~/.pi/agent/open-tui.json`,
  `home/ponytail.json` -> `~/.config/ponytail/config.json` (ponytail's own config dir, not pi's),
  `home/AGENTS.md` -> `~/.pi/agent/AGENTS.md`.
  Editing a file here is editing your deployed config.
- `bootstrap.sh` — fresh-machine setup. Run once.
- `rebuild.sh` — re-apply the config after any change. Run this every time. Supports
  `--sync-only` to deploy skills/extensions without touching installed packages or settings.
- `sync-settings.sh` — auto-syncs the live `~/.pi/agent/settings.json` back into
  `home/settings.json` when pi rewrites it. Triggered by the launchd agent
  `com.pi-dotfiles.sync-settings.plist` (a template in this repo, installed and path-substituted
  by `bootstrap.sh` step 4; watch path: `~/.pi/agent/settings.json`).
- `deploy-vps.sh` — mirrors the local harness onto the VPS (`ssh vps`): settings, auth,
  skills, agents, `home/AGENTS.md`, extensions, models/subagents, the per-machine
  package configs (`open-tui.json`, `code-previews.json`), a Linux variant of `web-search.json`
  plus its key file, then reconciles installed packages against the canonical list.
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

Files are **copied**, not symlinked. The dotfiles-style `home/` mirror keeps the repo
looking like the live tree, but pi manages `~/.pi/agent/` itself — it rewrites
`settings.json` on every install and package code is written into `extensions/` and
`skills/` — so a symlink would drag third-party package code into this repo. Copy on
bootstrap/rebuild, and `sync-settings.sh` copies the settings back when pi changes it.

The VPS side is push-based: `deploy-vps.sh` mirrors `~/.pi/agent/` onto `ssh vps` from
this machine (nothing on the VPS reads this repo), and it runs on a timer from the configs
repo's `com.diab.sync-vps` agent rather than by hand.
