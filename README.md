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
pi/skills/<name>/      -> ~/.pi/agent/skills/<name> (Pi-only: code-review, explicit-only orchestrate)
pi/{agents,extensions,themes}/ -> ~/.pi/agent/<same>
pi/pi-herdsman/config.json -> ~/.pi/agent/pi-herdsman/config.json (config only; runtime state stays local)
pi/*.json              -> ~/.pi/agent/<same> (settings, web-search, pi-btw, mcp)
pi/pi-title.jsonc      -> ~/.pi/agent/pi-title.jsonc (pi-title / title-in-border settings)
claude/                -> ~/.claude/ (platform settings, shared statusline-command.sh)
codex/                 -> ~/.codex/ (platform config, shared hooks.json)
scripts/agent-hook.sh   optional session integrations, guarded when not installed
config/                other dotfiles (zsh, ghostty, starship, herdr, VS Code, VPS files)
bb/                    explicit install/update and portable preference snapshot/restore (not linked)
.env.example           names of the secrets ~/.env should hold (not linked)
tests/                 link, deploy, settings, Herdsman agents, title-border and BB checks
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

## Pi Herdsman

`pi/settings.json` pins `npm:pi-herdsman@0.21.3`. It requires Node >=22.19.0,
Pi >=1.0.4 and Herdr >=0.9.3. Install the package separately from linking:

```sh
./link.sh
pi install npm:pi-herdsman@0.21.3
herdr integration install pi
```

Start a fresh Pi session inside Herdr; `/agents` manages Agents and definitions.
The shipped release uses `agent_delegate`, `agent_list`, `agent_steer`,
`agent_interrupt`, `agent_reply`, and `agent_continue`; results arrive automatically.
Use its installed documentation, not newer upstream tool names.

Custom profiles retain their existing roles and tools, inherit project/global
policy and skills, and are leaves (`agents: []`, `excludeTools: ["agent", ...]`).
Delegation still requires explicit authorization. The orchestration workflow caps
active workers at four; this is owner-enforced policy, not a runtime semaphore.
Herdsman has no matching concurrency/depth settings or JavaScript workflow runner.
Ordinary `agent_delegate` runs in its caller's cwd, so the orchestration skill
sequences writers and parallelizes read-only work. Branch-isolated parallel
writers require the separate native Manager workflow and an explicitly configured
managed-Lead policy; the skill does not activate that or relax the no-nesting rule.

Only `config.json` is linked under `~/.pi/agent/pi-herdsman/`; mailboxes, result
artifacts, and sessions remain machine-local. Placement stays `split`, and Manager
activation is explicit. Existing sessions need restarting or `/reload` for the
new extension; do not disrupt other sessions or delete their histories.

## Pi intercom

`pi/settings.json` enables `npm:pi-intercom` for session-to-session messaging.
It is enabled by default; the local broker starts automatically when Pi connects,
so no separate service or tracked intercom config is needed. Use `/alias <name>`
to name a session and the `intercom` tool's `status` or `list` action to check connectivity.

After pulling dotfiles on another machine, run `./link.sh` and
`pi install npm:pi-intercom` to install the package. Restart existing Pi sessions
or run `/reload` to load it. Each machine has its own local broker;
pulling settings does not itself enable cross-machine messaging.

## Pi project memory

[`pi/extensions/memory/`](pi/extensions/memory/README.md) is a local extension package,
loaded automatically through the existing personal extensions link. New Pi sessions
recall the current checkout's root `MEMORY.md` and its private notes; existing sessions
need `/reload` or a restart. Automatic recall has also been checked in a real BB Pi thread.

Project memory is shareable; private notes and named task handoffs stay untracked under
`~/.pi/agent/memory/`, isolated by checkout and machine. Nothing is committed automatically.
Ask Pi to check memory status, save a verified lesson, select another project, or resume
a named handoff. Files are created lazily; no empty memories are seeded across `~/Dev`.
Private content still enters model context: this is not a secret vault.

See [`docs/pi-memory/DESIGN.md`](docs/pi-memory/DESIGN.md) for agreed boundaries and
[`VALIDATION.md`](docs/pi-memory/VALIDATION.md) for test results and limitations.

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
`~/.claude/skills` and `~/.pi/agent/skills` are removed (deleted or renamed skills), as are
retired repo links such as `~/.pi/agent/herdr.json`, `~/.pi/agent/subagents.json`,
and `~/.pi/agent/open-tui.json`. Links
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

## Tests

```sh
bash tests/test-link.sh            # link.sh against a fake HOME (never the real one)
bash tests/test-app-deploy.sh
python3 tests/test-researcher.py   # researcher scope and its web-tool provider
python3 tests/test-herdsman.py     # pinned package, strict agent schema, leaf policy and config
python3 tests/test-portable-settings.py # Linux settings, optional hooks, cross-platform statusline
node tests/test-title-in-border.mjs  # Pi title-in-border extension and powerline config
node --test tests/test-memory.mjs   # memory store, extension hooks and installed-SDK compaction
python3 -m unittest discover -s tests -p test_bb.py # BB preference boundaries
```

Credits for copied-in skills: [`agents/ATTRIBUTION.md`](agents/ATTRIBUTION.md).
