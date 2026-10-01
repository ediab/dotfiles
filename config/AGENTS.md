# Imported configuration subtree instructions

This directory is the history-preserving import of the former standalone configuration
checkout. The one current checkout is `~/Dev/dotfiles`; do not create or edit a separate
configs checkout. Ordinary local home files are sourced from `config/` through symlinks made
by the root `link.sh`. Edit their repo sources and keep the links intact. No chezmoi migration is assumed.

## Ordinary home files

| Source in this subtree | Live location |
|---|---|
| `.zshrc`, `.zprofile`, `.zshenv` | matching files under `$HOME` |
| `starship.toml` | `~/.config/starship.toml` |
| `topgrade.toml` | `~/.config/topgrade.toml` |
| `ghostty/config` | `~/.config/ghostty/config` |
| `herdr/config.toml` | `~/.config/herdr/config.toml` |
| `herdr-auto-title/config.env` | `~/.config/herdr-auto-title/config.env` |
| `rpiv-advisor/advisor.json` | `~/.config/rpiv-advisor/advisor.json` |
| `vscode/settings.json`, `vscode/keybindings.json` | Code's User directory |

## VS Code

- `chat.disableAIFeatures: true` disables the built-in Chat / Copilot Chat UI.
- `github.copilot.enable: false` disables Copilot completions.
- `vscode/extensions.txt` is a saved inventory; refresh it explicitly from `code --list-extensions` when requested.

## Agent content

Agent content is not owned by this subtree. Skills, instructions and Pi/Claude/Codex settings
live in the repository-root `agents/`, `pi/`, `claude/` and `codex/`, and the root `link.sh`
links them into place. Read the root README before changing links. Editing dotfiles does not
implicitly authorize committing, pushing, managing packages, or VPS deployment. There is no
automatic capture, commit/push, or VPS synchronization. The old Mac jobs were persistently
disabled and their installed definitions removed; do not recreate them.

## VPS access and deployment

Use `ssh vps` (alias in `~/.ssh/config`). Host: `77.42.90.4`, user: `diab`, key:
`~/.ssh/id_rsa_nroot`.

These sources are copied by explicit scripts; the VPS does not read this checkout:

| Source | Deploy script | VPS target |
|---|---|---|
| `herdr/config.vps.toml` | `herdr/deploy-vps.sh` | `~/.config/herdr/config.toml` |
| `vps/.zshrc`, `.zshenv`, `.p10k.zsh` | `vps/deploy-vps.sh` | `$HOME` |
| `vps/apps-AGENTS.md` | `vps/deploy-vps.sh` | `~/apps/AGENTS.md` |

`vps/deploy-vps.sh` copies only shell files and app-root instructions and keeps `.zshrc`
private (0600). It does not install,
remove, start, or enable maintenance scripts, services, timers, apt policy, or lingering.

Operational sources are retained for separately requested maintenance: `vps/systemd/`,
`vps/apt/51-vps-auto-updates`, `vps-cleanup.sh`, and `vps-update-images.sh`. Saved timer
specifications describe weekly cleanup at Sun 04:30 and image refresh at Sun 05:30.
The saved Herdr service keeps the headless server available; the saved apt policy covers
security/base/ESM updates and a 03:30 reboot. Existing remote service state is not changed
by configuration deployment; do not infer live health from these source definitions.

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

For an explicitly requested deployment, choose only the requested helper:

- `config/vps/deploy-vps.sh` — shell files and app-root instructions;
- `config/herdr/deploy-vps.sh` — Herdr config and reload;
- `config/druk/deploy-druk.sh` — local editor preference merge and pi-opener config;
  `DEPLOY_DRUK_HOST=vps` also merges remote settings. No extension downloads.

There is no all-app orchestrator or change-triggered deployment. Agent content is linked on
the VPS from `~/Dev/dotfiles` by the root `link.sh`, which selects tracked Linux client settings. Updates still require an explicit deployment request.
