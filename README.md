# dotfiles

Elias's private `ediab/dotfiles` repository stores ordinary home configuration and
agent content for Pi, Codex, and Claude Code. It is a configuration repo, not a
machine installer.

## Working model

- Edit ordinary dotfiles through their existing repo-backed symlinks.
- Edit agent content in the repo, then explicitly **apply** it locally.
- When an application changes its live settings, explicitly **save** the preferences
  you want to keep back into the repo.
- Review, commit, and push changes yourself. VPS deployment is a separate request.
- Install and update software separately. Saving or applying dotfiles does not authorize
  package installation, removal, or updates.

No new dotfiles manager or chezmoi migration is part of this direction.

Saving and applying configuration never installs software, commits/pushes changes, or
starts background synchronization. The old installer/capture/orchestrator scripts are
retired. The capture and VPS-sync jobs were persistently disabled and their installed
plists removed on this Mac; any old installation on another machine needs separate removal.

## Daily use

The explicitly invoked [`update-dotfiles`](home/shared-skills/update-dotfiles/SKILL.md) skill
owns the save/apply procedure. Once deployed to Pi, examples are:

```text
/skill:update-dotfiles save my live Pi settings into the repo
/skill:update-dotfiles apply the agent-content changes I made locally
```

A bare invocation starts with inspection, not an all-files apply. The skill compares
live and repo versions, preserves unrelated work, checks for unexpected background side
effects, and verifies the requested result. It selects only the approved files/preferences.
It does not commit, push, or deploy to the VPS without an explicit request.

[`local-env`](home/shared-skills/local-env/SKILL.md) is the companion environment reference:
repo location, symlink sources, machine-specific paths, and VPS access. It does not
provide permission to apply or deploy.

Saving is a scoped edit/copy through the skill, not a daemon or a whole live-directory
capture. Applying uses `apply.sh`: it requires explicit files/groups and previews by default.

```sh
./apply.sh --file web-search.json                 # preview one file
./apply.sh --file web-search.json --yes           # apply just that file
./apply.sh --file agents/researcher.md --yes       # one profile
./apply.sh --group themes --yes                   # standalone themes + license
./apply.sh --group agent-content                  # full skill/instruction ownership plan
```

Other groups are `configs` (the five maintained JSON preference files), `agents`, and
`extensions`. Repeat `--file`/`--group` to combine scopes. `agent-content` means **all** managed
skills and installed-client instructions, not a single edited skill. Inspect its complete
plan before adding `--yes`; first-time adoption remains a separate approval.

JSON is validated before writes. Replacements are atomic and previous bytes are backed up
under `~/.local/state/pi-dotfiles/backups/apply/`. Unselected and foreign files are not pruned;
symlink destinations/parents are refused rather than silently writing elsewhere.

## Sources and destinations

| Source | Destination / use |
|---|---|
| `config/` ordinary home files | Existing symlinks into `$HOME`, `~/.config/`, and app config locations; see [`config/README.md`](config/README.md) |
| `home/shared-skills/` | Portable skills copied to `~/.agents/skills/`, with per-skill Claude links when Claude Code is installed |
| `home/skills/` | Pi-only skills copied to `~/.pi/agent/skills/` |
| `home/AGENTS.md`, `home/instructions/` | Shared policy and client overlays composed into installed clients' global instructions |
| `home/extensions/`, `home/agents/` | Custom Pi extensions and agent profiles copied to `~/.pi/agent/` |
| `home/themes/` | Standalone Pi themes and their license copied to `~/.pi/agent/themes/` by scoped apply or explicit VPS deployment |
| `home/settings.json` | Versioned Pi settings; compare with live `~/.pi/agent/settings.json` before saving or applying |
| Other `home/*.json` | Pi/package preferences, including subagents, Open-TUI, side questions, and web-search configuration |
| `config/vscode/extensions.txt` | Saved VS Code extension inventory; refresh explicitly when wanted |
| `config/vps/`, `config/herdr/`, `config/druk/` | Sources for separate VPS/app deployment scripts |

Ordinary symlinked settings are already live when edited. Pi rewrites its own
`settings.json`, and copied agent content does not change live until applied. These are
different ownership models; do not copy all of `~/.pi/agent/` into Git.

The `packages` array in `home/settings.json` records Pi package declarations. Saving
that array is configuration capture, not permission to reconcile installed packages.
Applying settings preserves live `packages`, `deviceId`, `lastChangelogVersion`,
`sessionDir`, and `httpProxy` by default. Only an explicitly approved `--include-packages`
changes package declarations; **Pi may install declared packages at startup**, although
`apply.sh` itself never runs package commands. Review that consequence separately.

## Agent-content ownership

`sync-agent-content.sh` is the sole owner of managed skills, Claude links, and generated
global instructions. It copies repo-owned sources and prunes only paths recorded in
that machine's manifest. Unmanaged skills and other clients' directories stay untouched.
A same-name unmanaged collision blocks applying; a missing manifest does not authorize
pruning or adopting existing destinations.

The helper defaults to a dry run. For an explicitly requested local agent-content apply,
inspect the plan first:

```sh
./lint-agent-content.sh
./sync-agent-content.sh --dry-run
```

Only apply a reviewed plan whose scope matches the request using `--yes`. First-time
adoption is a separate approval: inspect `--adopt` before authorizing `--adopt --yes`.
Keep the safeguards intact rather than deleting live skill directories to bypass them.

Generated instructions combine the shared policy, optional repo client overlay, and
optional machine overlay. Drift is detected and backed up; forced replacement requires
review and approval. Edit the sources, not the generated live instruction file.

Machine-local state intentionally retains its existing paths:

- `~/.local/state/pi-dotfiles/` — ownership manifest, instruction hashes, and backups;
- `~/.config/pi-dotfiles/local/{pi,codex,claude}.md` — optional untracked instruction overlays;
- `~/.cache/pi-dotfiles-agent-content/` — VPS staging directory.

Keeping these paths preserves ownership and avoids another adoption migration.

### Adding content

- Put portable skills in `home/shared-skills/` and Pi-only skills in `home/skills/`.
  A skill name has one source owner. Preserve attribution and licenses for vendored content.
- Keep externally installed skills outside these managed source folders. `show-me` is
  upstream-owned; `bro` is a reviewed, verbatim vendored exception.
- The shared-skill exclusions in `home/settings.json` prevent duplicate loading of
  externally owned skills. Their rationale lives in [`CONCEPTS.md`](CONCEPTS.md).
- Put custom extensions in `home/extensions/` and profiles in `home/agents/`; the deployment
  scripts discover these files without an inventory edit.
- Keep machine-only instruction facts in the untracked local overlays.

## Secrets and externally owned files

Auth/API keys, `.env` values, MCP configuration, sessions, caches, `models-store.json`,
and `code-previews.json` stay outside Git. `home/.env.example` is a template, not a place
for real values. MCP servers and credentials remain machine-specific.

Herdr owns `~/.pi/agent/extensions/herdr-agent-state.ts`. Do not vendor it here or overwrite
it through dotfiles deployment. Herdr's skill and its installed integration are separate.

Web-search preferences are versioned, but TinyFish credentials are not: local lookup uses
the macOS Keychain; the VPS lookup uses its own `~/.pi/agent/tinyfish-api-key` file. The
explicit VPS script changes only the lookup, without reading/transferring credentials.

## Maintained commands and explicit deployment

| Command | Scope / side effects |
|---|---|
| `apply.sh` | Selected local configuration only; preview by default, backups on replacement |
| `sync-agent-content.sh` | Manifest-backed skill/instruction helper; dry run by default, `--yes` applies the whole printed plan |
| `lint-agent-content.sh` | Checks skill ownership and shared/Pi-only boundaries |
| `deploy-vps.sh [host]` | Explicit repo-source agent/config deployment; keeps remote package declarations, auth, runtime state, and overlays |
| `config/vps/deploy-vps.sh` | VPS shell dotfiles and app-root instructions; optional tmux reload, no service/timer/apt-policy provisioning |
| `config/herdr/deploy-vps.sh` | Herdr config copy and reload only |
| `config/druk/deploy-druk.sh` | Local editor preference merge; remote copy/merge only with `DEPLOY_DRUK_HOST=<host>`; no extension downloads |

Invoke only the requested deployment helper. There is no automatic four-step orchestrator.
Operational VPS scripts, systemd/apt assets, `Brewfile`, and extension inventories are retained
for separately authorized maintenance or installation. Configuration deployment does not
install/activate those assets or alter existing services.

For an explicitly requested VPS agent-content deployment, the remote machine needs its
own ownership adoption. `deploy-vps.sh --prepare-agent-content [host]` stages sources only;
review the printed remote adoption plan and obtain approval before applying it. Normal
deployment requires the remote manifest and a clean preflight. No local ownership state
or machine overlay is sent to the VPS.

No live VPS deployment accompanies this cleanup. Existing remote services and machine-local
ownership/backups/overlays stay intact; a passing fixture is not proof of live service health.

## Agent workflows and documentation

Planning and implementation are explicit: `brainstorm`, `to-spec`, `to-tickets`, and
`implement` own their respective procedures. `personal-workflow` owns execution/Git gates;
agent profile files and JSON settings are the source of truth for models and runtime options.

`/review` reviews in the current session; the `reviewer` profile is a fresh-context,
report-only subagent used when explicitly requested. Project `REVIEW_GUIDELINES.md` files
can supply review rules. See the relevant skills/profiles rather than duplicating their
procedures here.

- `CONCEPTS.md` — shared domain vocabulary and configuration rationale.
- `docs/audits/` — historical investigations; measurements describe their recorded baseline, not current performance.
- `config/docs/` — imported configuration guides and historical records.
