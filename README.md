# dotfiles

Public repo holding the latest Pi, Claude and Codex settings, the skills they use,
portable BB preferences and setup helpers, and ordinary Mac config. **The checkout is
the live copy:** `link.sh` symlinks the linked configuration below into place, so a
setting saved by an app or a skill you edit is already in the repo. BB is an exception:
its settings use explicit snapshot/restore commands rather than live symlinks.

## Layout

```
agents/AGENTS.md       -> ~/.pi/agent/AGENTS.md, ~/.codex/AGENTS.md, ~/.claude/CLAUDE.md
agents/ATTRIBUTION.md  credits for copied-in skills (not linked)
agents/skills/         -> ~/.agents/skills (Pi + Codex); one link per skill in ~/.claude/skills
pi/{extensions,themes}/ -> ~/.pi/agent/<same>
archive/               retired Pi delegation setup and Pi memory extension (not linked)
pi/*.json              -> ~/.pi/agent/<same> (settings, web-search, mcp)
pi/pi-title.jsonc      -> ~/.pi/agent/pi-title.jsonc (pi-title / title-in-border settings)
claude/                -> ~/.claude/ (platform settings, shared statusline-command.sh)
codex/                 -> ~/.codex/ (platform config, shared hooks.json, personal agents)
scripts/agent-hook.sh   optional session integrations, guarded when not installed
config/                other dotfiles (zsh, ghostty, starship, herdr, VS Code, VPS files)
bb/                    explicit install/update and portable preference snapshot/restore (not linked)
.env.example           names of the secrets ~/.env should hold (not linked)
tests/                 privileged note-sx deployment/update safety checks
```

## Pi installation

Install Pi separately from the Brewfile on macOS and Linux:

```sh
curl -fsSL https://pi.dev/install.sh | sh
pi --version
```

Use `pi update self` to update the installer-managed runtime. Pi packages still
live in `~/.pi/agent/npm` and `~/.pi/agent/git`; do not remove these directories
when switching away from a global npm installation. Configuration, credentials
and sessions remain in `~/.pi/agent`. Credentials stay machine-local and untracked;
use `pi auth check --provider deepseek` and `pi auth check --provider openai`
to check readiness without printing secrets.

## Pi packages and host-specific UI

`pi/settings.json` pins four npm packages and the pstack Git revision. After linking on another
machine, run `pi update --extensions` to reconcile the installed packages to those
pins. To upgrade, change the version in settings, reconcile, and confirm loading
in a fresh Pi session. These are direct-package pins, not a lockfile for their
transitive dependencies.

`pi/extensions/standalone-ui.ts` loads the title package only outside BB
(`BB_THREAD_ID` absent). Its `extensions: []` setting suppresses normal autoload,
so BB owns automatic titles. The guard imports the installed package, not a copy
or patch. Pstack supplies Pi's question tool; the old question package is removed.
Inside BB, prefer BB's own question tool.

## Pstack

[Pstack](https://github.com/michael-denyer/pstack-claude) provides on-demand
engineering workflows in Claude Code, Codex and Pi. Routine tasks run directly;
`poteto-mode` is reserved for explicit requests, typically large or complex projects. Release `0.9.86` is installed through each
harness's native plugin/package mechanism, not copied into the shared personal
skills directory. Claude uses tag `v0.9.86`; Codex and Pi use its commit
`1dba27e50e8f18f146bb80f137f0690f8d773c2e`. Keep all three aligned when updating.

After linking on a new machine with the CLIs installed, reconcile their installs:

```sh
claude plugin marketplace add michael-denyer/pstack-claude@v0.9.86
claude plugin install pstack@pstack-claude --scope user
codex plugin marketplace add michael-denyer/pstack-claude --ref 1dba27e50e8f18f146bb80f137f0690f8d773c2e
codex plugin add pstack@pstack-claude
pi update --extensions
```

The native SessionStart hooks remain installed, but routing is disabled by
`session hook: off` in each harness's `pstack-models.md`. `link.sh` links the
tracked `claude/`, `codex/` and `pi/` copies into the respective user directories.
These sheets set routing only; upstream model and effort defaults are unchanged.
Codex's Mac configuration retains the reviewed hook hash reported by `hooks/list`;
if you later enable routing, inspect hook trust in `/hooks` on a new machine.

Use `/pstack:poteto-mode <task>` in Claude Code, request `pstack:poteto-mode` in
Codex, or use `/skill:poteto-mode <task>` in Pi. Specific skills such as `bro`,
`how`, `architect` and `interrogate` remain directly available. Automatic routing
is off in all three harnesses; BB inherits that through its native providers.
Run the upstream `setup-pstack` skill when you want to choose models/effort.
Keep routing off unless you intentionally change the opt-in policy.

Matt Pocock's skills, the local pstack adaptations, the local `bro` copy and
`personal-workflow` are retired. Unrelated personal skills remain under
`agents/skills/`. Old names such as `to-spec`, `to-tickets`, `domain-modeling` and
`pi-handoff` no longer exist; they are not compatibility aliases.

### BB and delegation

No separate BB installation is needed. BB uses the native harness installations
on the thread's execution machine. Start a fresh thread/provider session after
installation; existing conversation context can still advertise retired skills.
Installing on the Mac does not install on the VPS or other enrolled machines.

Explicitly invoked workflows authorize their prescribed helpers, including in
standalone Pi; otherwise one agent is the default.
Inside BB, the shared policy translates dispatch, messaging, listing and stopping
to BB child threads and BB messaging. Upstream native tools may still be loaded;
the host policy takes precedence. No BB plugin or forked pstack runtime is added.
Read-only reviewers can share a stable checkout; concurrent writers need separate
worktrees and one integration owner. Worktrees separate edits, not OS permissions.

The earlier standalone single-agent setup is preserved in
[`archive/pi-delegation/`](archive/pi-delegation/README.md), outside active discovery.
Herdr remains an optional terminal workspace.

## UI skills

[Impeccable](https://github.com/pbakaus/impeccable) **4.6.0** and
[Interface Design](https://github.com/Dammyjay93/interface-design) are installed
unchanged through their supported installers. Taste Skill is not installed.
They retain upstream automatic skill selection; no additional routing policy is added.
Name the skill explicitly when you want a particular workflow to lead.

On another machine, install the native copies before verifying the setup:

```sh
npx --yes impeccable@4.6.0 install --providers=claude,codex,pi --scope=global --no-hooks --yes
DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 npx --yes skills@1.7.2 add https://github.com/Dammyjay93/interface-design/tree/2f9be3206855bcb2d1d0af262c8bae25cba6658d --skill interface-design --agent claude-code codex pi --global --yes
bash link.sh
```

Impeccable's installer provides separate Claude, Codex and Pi builds, helper-agent
profiles where supported, and engine **0.1.15**. Its Codex build lands in the linked
`agents/skills/impeccable/`; Claude and Pi keep their native user-directory copies.
`link.sh` deliberately leaves Claude's Impeccable copy alone, and Pi's `skills`
setting excludes the shared Codex copy to avoid duplicate discovery. Engine
binaries are machine-local and ignored by Git. Re-run the installer to provision
native copies and binaries; the npm version pins the installer, not an immutable
skill-download artifact.

Interface Design lives in `agents/skills/interface-design/`, read by Codex/Pi and
linked into Claude. Its core skill is shared; Claude plugin-only review commands
are not installed by the skills installer.

No Impeccable hooks are installed. Use its commands manually; do not run `init`
in dotfiles just to install the skill. `init` creates project product/design
context and belongs in an application checkout. Live mode and automatic hooks
are separate opt-in actions, not part of this setup.

## Project memory

The shared [`agents/AGENTS.md`](agents/AGENTS.md#project-memory) defines the policy:
repository facts live in a versioned root `MEMORY.md`, read by every client inside
and outside BB. Create it when there is useful knowledge to retain, not as an empty
file in every repo. Stage, commit and push only when authorized.

[`bb/AGENTS.md`](bb/AGENTS.md) reserves BB memory for global, cross-project preferences
and BB-wide operational knowledge, avoiding duplicate repository memory stores.
Restore that file explicitly as described in [`bb/README.md`](bb/README.md#bb-user-instructions).

The old Pi extension is archived in [`archive/pi-memory/`](archive/pi-memory/README.md)
and no longer loads. Its machine-local `~/.pi/agent/memory/` store has been removed.

## BB

See [`bb/README.md`](bb/README.md) for explicit install/update commands, portable
preference snapshot/restore, and the plugin inventory. BB runtime state and credentials
stay outside this repo. `link.sh` does not install, update, link, or apply BB settings.

## `link.sh`

No flags; prints what it does; rerun any time (Claude's `SessionStart` hook runs it too).
For each `source -> destination`:

1. Nothing there: create parent folders, then link.
2. Already the correct link: leave it.
3. Any other symlink: replace it.
4. A real file or folder identical to the repo copy: replace it with the link.
5. Anything else: print `SKIP <path> (differs from repo)` and leave it. Exit status is 1.

Also: Claude entries are skipped if `~/.claude` is missing, Codex entries if `~/.codex` is
missing, and `config/` links run only on macOS. Broken links into this repo in
`~/.claude/skills`, `~/.pi/agent/skills` and `~/.codex/agents` are removed (deleted or
renamed skills and agents). Links
are made under a temporary name and renamed over the destination with Python's `os.replace`,
so concurrent runs never see a half-made link. Each run also sets this clone's
`filter.pi-settings.clean` git config (see Platform settings).

## Adding or changing a skill

| What you do | Repo | Pi | Codex | Claude |
|---|---|---|---|---|
| Edit an existing skill, from any app | updated | yes | yes | yes |
| Create a skill in `~/.agents/skills` or `agents/skills/` | updated | yes | yes | after a Claude restart |
| An installer adds a skill to `~/.agents/skills` | shows in `git status` | yes | yes | after a Claude restart |

Claude reads only `~/.claude/skills` (which also holds its own synced skills), so it gets one
link per skill; `link.sh` creates them. Create new personal skills in `~/.agents/skills/<name>`.

## Warnings

- **The checkout is live.** Editing files, switching branches or `git pull` immediately
  changes what the apps see. Do experiments in a separate worktree.
- **No secrets in linked files.** Secrets live in `~/.env` (mode 600), never in the repo;
  `.env` is gitignored. Apps' auth files (`auth.json`, `~/.claude.json`, ...) stay out too.
- Tools rewrite their own settings (version stamps, trust entries), which shows up in
  `git status`. Commit when you like; nothing commits or pushes automatically.
- VPS agent content uses the same `link.sh` model (the repo is cloned at `~/Dev/dotfiles`
  there; active settings link to tracked platform configs). `config/vps`, `config/herdr` and `config/druk` keep
  their own explicit deploy scripts (see `config/README.md`).

## Platform settings

Pi settings and agent content are shared. `link.sh` selects `claude/settings.json`
and `codex/config.toml` on macOS, and `claude/settings.linux.json` and
`codex/config.linux.toml` on Linux, linking them to the clients' usual filenames.
The Mac files retain desktop integrations and local app paths; the Linux files
exclude those integrations and preserve the VPS's `/home/diab` project trust.
Keep shared behavior aligned when editing either platform variant.

Pi writes two machine-local keys into `pi/settings.json`: `lastChangelogVersion`
after every update and `deviceId` (a per-machine login ID). A git clean filter
(`.gitattributes`, configured by `link.sh` with `jq`) keeps both out of commits, so
they never dirty the tree or block a pull, and each machine keeps its own ID.

The local ggshield pre-commit hook (`.git/hooks/pre-commit`, untracked) falls back
to `GITGUARDIAN_API_KEY` from `~/.env`, because sandboxed agents cannot read the
macOS keychain where `ggshield auth login` stores the token. `claude/settings.json`
lets sandboxed commands reach `api.gitguardian.com` and the macOS `trustd` service
(ggshield checks TLS through it), so agent commits are scanned inside the sandbox.
These grants only matter where Claude Code's sandbox is on: BB's Claude Code threads
enable it. The interactive `claude` alias in `config/.zshrc` skips permissions and
runs unsandboxed (`claude-safe` keeps the configured permission mode).
`git push` and `ssh vps` still run outside it: the SSH key is unlocked by the
macOS SSH agent and keychain, which the sandbox blocks, so each push asks for
permission. That prompt is intentional.

Session hooks use `scripts/agent-hook.sh`; optional helpers and Herdr-installed
hooks are invoked only when present. Context7 credentials stay in each host's
`~/.env`, not in tracked settings. Claude's user MCP registrations remain in
its untracked `~/.claude.json`.

A reconciled machine should rerun `link.sh` with exit 0 and no `SKIP` or `FAIL`.
The linker still protects conflicting real files: for an approved reconciliation,
back them up privately outside the repo, then replace them with the tracked links.
This is a deliberate operation, never an automatic overwrite.

## New machine

1. `git clone git@github.com:ediab/dotfiles.git ~/Dev/dotfiles`
2. `~/Dev/dotfiles/link.sh` (resolve any `SKIP` by merging that file into the repo, deleting the live one, rerunning)
3. `brew bundle --file=~/Dev/dotfiles/config/Brewfile` (macOS), then install Pi using the command above
   and oh-my-zsh (`.zshrc` loads it from `~/.oh-my-zsh` when present):
   `sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" "" --unattended --keep-zshrc`
4. `cp ~/Dev/dotfiles/.env.example ~/.env && chmod 600 ~/.env`, then fill in the values
   (`GITGUARDIAN_API_KEY` is a GitGuardian personal access token with `scan` scope).
   Shell-only secrets (for example `ZAI_BASE_URL`/`ZAI_API_KEY` for the `glm` function)
   go in `~/.zshrc.secrets` (`chmod 600`), which `.zshrc` sources when present.
5. `cd ~/Dev/dotfiles && ggshield install -m local`, then add the `~/.env` token fallback
   above `ggshield secret scan pre-commit` in `.git/hooks/pre-commit`:
   ```sh
   if [ -z "${GITGUARDIAN_API_KEY:-}" ] && [ -r "$HOME/.env" ]; then
     GITGUARDIAN_API_KEY="$(sed -n 's/^GITGUARDIAN_API_KEY=//p' "$HOME/.env")"
     [ -n "$GITGUARDIAN_API_KEY" ] && export GITGUARDIAN_API_KEY
   fi
   ```
6. Add Claude's Context7 server (its config in `~/.claude.json` is not in the repo):
   `claude mcp add-json --scope user context7 '{"type":"http","url":"https://mcp.context7.com/mcp","headersHelper":"..."}'`
   where `headersHelper` is a command that prints `{"CONTEXT7_API_KEY":"<value read from ~/.env>"}`.

## Validation

Ordinary dotfiles do not need an automated test suite. Check changed syntax and
verify the result in the affected shell or client. Do not add tests for settings,
skill inventories, themes or UI preferences.

Only safety checks for consequential operational code are retained: backup
retention/deletion, privileged note-sx deployment/rollback, and monitor privilege
and credential boundaries. Run the relevant checks when changing that code, not
for routine dotfiles edits. Python checks require Python 3.11+.

```sh
python3.11 tests/test-note-sx-deploy.py
bash tests/test-note-sx-updater.sh
python3.11 -m unittest discover -s config/vps/recovery/tests
python3.11 -m unittest discover -s config/vps/security/tests
```

These checks use temporary fixtures and mocked services. They do not deploy
anything or prove live service health.

Credits for copied-in skills: [`agents/ATTRIBUTION.md`](agents/ATTRIBUTION.md).
