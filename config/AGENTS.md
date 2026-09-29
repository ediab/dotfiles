# Imported configuration subtree instructions

This directory is the transitional, history-preserving import of the former standalone
configuration checkout. The one current checkout is `~/Dev/dotfiles`; do not create or edit a
separate configs checkout. Ordinary local home files remain sourced from `config/` for
Milestone 1 and are planned for chezmoi in Milestone 2. Edit sources here, not their live
symlink targets.

## Ordinary home files

| Source in this subtree | Live location |
|---|---|
| `.zshrc`, `.zprofile`, `.zshenv`, `.tmux.conf` | matching files under `$HOME` |
| `starship.toml` | `~/.config/starship.toml` |
| `ghostty/config` | `~/.config/ghostty/config` |
| `herdr/config.toml` | `~/.config/herdr/config.toml` |
| `rpiv-advisor/advisor.json` | `~/.config/rpiv-advisor/advisor.json` |
| `vscode/settings.json`, `vscode/keybindings.json` | Code's User directory |

Firefox actively writes its profile, so use `firefox/sync.sh` instead of symlinking profile files.
Sensitive files (cookies, logins, certificates), storage, and extension binaries are not synced.

## VS Code

- `chat.disableAIFeatures: true` disables the built-in Chat / Copilot Chat UI.
- `github.copilot.enable: false` disables Copilot completions.
- `vscode/extensions.txt` is regenerated from `code --list-extensions` by `capture.sh` when available.

## Agent content and capture

Pi/agent content is not owned by this subtree. Sources live in the repository-root `home/`,
and `sync-agent-content.sh` is the sole owner of skills, Claude links, generated instructions,
and its local ownership manifest/backups. Run `~/Dev/dotfiles/rebuild.sh --sync-only` to deploy
agent content without package updates or copying `settings.json`.

`capture.sh` is the single capture job. It copies present live Pi `settings.json` and
`open-tui.json` files, refreshes `vscode/extensions.txt` best-effort, and commits only tracked
changes in its allowlist. It does not add untracked paths or unrelated staged paths. The
capture job is `com.diab.dotfiles.capture`; bootstrap installs it from root-level templates.

The following local agent state paths intentionally keep their legacy names so manifests,
backups, and overlays remain discoverable after the repository rename:

- `~/.local/state/pi-dotfiles/` — manifest and backups;
- `~/.config/pi-dotfiles/local/` — machine-local instruction overlays;
- `~/.cache/pi-dotfiles-agent-content/` — staged VPS agent content.

## VPS access and deployment

Use `ssh vps` (alias in `~/.ssh/config`). Host: `77.42.90.4`, user: `diab`, key:
`~/.ssh/id_rsa_nroot`.

These sources are copied by explicit scripts; the VPS does not read this checkout:

| Source | Deploy script | VPS target |
|---|---|---|
| `herdr/config.vps.toml` | `herdr/deploy-vps.sh` | `~/.config/herdr/config.toml` |
| `vps/.zshrc`, `.zshenv`, `.p10k.zsh`, `.tmux.conf` | `vps/deploy-vps.sh` | `$HOME` |
| `vps/vps-cleanup.sh`, `vps/vps-update-images.sh` | `vps/deploy-vps.sh` | `~/bin/`, user timers |
| `vps/systemd/*.{service,timer}` | `vps/deploy-vps.sh` | `~/.config/systemd/user/` |
| `vps/apt/51-vps-auto-updates` | `vps/deploy-vps.sh` | `/etc/apt/apt.conf.d/` |
| `vps/apps-AGENTS.md` | `vps/deploy-vps.sh` | `~/apps/AGENTS.md` |

`vps/deploy-vps.sh` also installs weekly upkeep: cleanup at Sun 04:30 (Docker cache cap,
protected build bases, caches, autoremove, journal cap; `~/logs/vps-cleanup.log`) and image
refresh at Sun 05:30 (snapshot, health-check, rollback tagging; `~/logs/vps-update-images.log`).
The `herdr-server.service` keeps the headless Herdr server available. The apt policy enables
security/base/ESM updates and a 03:30 automatic reboot; the package's own
`50unattended-upgrades` file is not managed here.

- `vps-cleanup.sh` runs Sunday at 04:30. It caps Docker build cache at 3 GB, preserves
  protected build bases, clears runner/npm/apt caches, runs autoremove, and applies a soft
  journal cap. It takes `~/.cache/vps-deploy.lock`, supports `--dry-run`, and logs to
  `~/logs/vps-cleanup.log`.
- `vps-update-images.sh` runs Sunday at 05:30. It snapshots third-party-image projects
  (`note-sx`, `karakeep-app`), verifies the archive before pulling, health-checks the result,
  and re-tags recorded image IDs on failure. It keeps three generations in `~/backups/<app>/`
  and logs to `~/logs/vps-update-images.log`.
- Both weekly jobs are persistent user timers. Locally built images and the push-to-deploy
  path are not touched by them.

The merged orchestrator is `~/Dev/dotfiles/config/bin/sync-vps.sh`. It runs these four steps
in order and continues after failures:

1. `~/Dev/dotfiles/deploy-vps.sh` — agent content and Pi configuration;
2. `config/vps/deploy-vps.sh` — shell files, upkeep scripts, systemd units, and apt policy;
3. `config/herdr/deploy-vps.sh` — Herdr config and reload;
4. `config/druk/deploy-druk.sh` — editor settings, extensions, and pi-opener.

It gates on exactly `home/`, top-level `deploy-vps.sh`, `config/vps/`,
`config/herdr/config.vps.toml`, and `config/druk/` against `~/.cache/sync-vps.stamp`. An idle
run makes no SSH connection; all steps run after a failure, and the stamp advances only after
all succeed. Logs are `/tmp/com.diab.sync-vps.{out,err}`.

```sh
~/Dev/dotfiles/config/bin/sync-vps.sh          # deploy if a source changed
~/Dev/dotfiles/config/bin/sync-vps.sh --force  # bypass only the orchestrator timestamp gate
```

Do not install/load `com.diab.sync-vps` before remote agent-content adoption is approved and
verified. Stage with `~/Dev/dotfiles/deploy-vps.sh --prepare-agent-content vps`, review the
remote `--adopt` dry-run, stop for human approval before `--adopt --yes`, then verify the
manifest and no-write preflight. Run `sync-vps.sh --force` once and verify all four steps and
the success stamp before installing the VPS job with:

```sh
~/Dev/dotfiles/install-launchd.sh sync-vps
```

Bootstrap installs capture only.
