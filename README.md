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
pi/skills/code-review  -> ~/.pi/agent/skills/code-review (Pi-only)
pi/skills/orchestrate  -> ~/.pi/agent/skills/orchestrate (Pi-only, explicit-only orchestration)
pi/{agents,extensions,themes}/ -> ~/.pi/agent/<same>
pi/herdr.json          -> ~/.pi/agent/herdr.json (pi-herdr settings: caps, depth, notifications)
pi/*.json              -> ~/.pi/agent/<same> (settings, web-search, pi-btw, mcp)
claude/                -> ~/.claude/ (platform settings, shared statusline-command.sh)
codex/                 -> ~/.codex/ (platform config, shared hooks.json)
scripts/agent-hook.sh   optional session integrations, guarded when not installed
config/                other dotfiles (zsh, ghostty, starship, herdr, VS Code, VPS files)
bb/                    explicit install/update and portable preference snapshot/restore (not linked)
.env.example           names of the secrets ~/.env should hold (not linked)
tests/                 link, deploy, settings, herdr agents, title-border and BB checks
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

## Pi intercom

`pi/settings.json` enables `npm:pi-intercom` for session-to-session messaging.
It is enabled by default; the local broker starts automatically when Pi connects,
so no separate service or tracked intercom config is needed. Use `/alias <name>`
to name a session and the `intercom` tool's `status` or `list` action to check connectivity.

After pulling dotfiles on another machine, run `./link.sh` and
`pi install npm:pi-intercom` to install the package. Restart existing Pi sessions
or run `/reload` to load it. Each machine has its own local broker;
pulling settings does not itself enable cross-machine messaging.

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
retired repo links such as `~/.pi/agent/subagents.json` and `~/.pi/agent/open-tui.json`. Links
are made under a temporary name and renamed over the destination with Python's `os.replace`,
so concurrent runs never see a half-made link.

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
4. `cp ~/Dev/dotfiles/.env.example ~/.env && chmod 600 ~/.env`, then fill in the values
5. Add Claude's Context7 server (its config in `~/.claude.json` is not in the repo):
   `claude mcp add-json --scope user context7 '{"type":"http","url":"https://mcp.context7.com/mcp","headersHelper":"..."}'`
   where `headersHelper` is a command that prints `{"CONTEXT7_API_KEY":"<value read from ~/.env>"}`.

## Tests

```sh
bash tests/test-link.sh            # link.sh against a fake HOME (never the real one)
bash tests/test-app-deploy.sh
python3 tests/test-researcher.py   # researcher scope and its web-tool provider
python3 tests/test-herdr.py        # pi-herdr contract (package, agent defs, defaults)
python3 tests/test-portable-settings.py # Linux settings, optional hooks, cross-platform statusline
node tests/test-title-in-border.mjs  # Pi title-in-border extension and powerline config
python3 -m unittest discover -s tests -p test_bb.py # BB preference boundaries
```

Credits for copied-in skills: [`agents/ATTRIBUTION.md`](agents/ATTRIBUTION.md).
