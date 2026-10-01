# Imported configuration subtree

`config/` is the history-preserving import of the former standalone configuration checkout.
The single repository is `ediab/dotfiles`, checked out at `~/Dev/dotfiles`; do not recreate a
second configs checkout. This directory holds ordinary Mac settings and app/VPS configuration.
No chezmoi migration is assumed.

See the [top-level README](../README.md) for the layout and `link.sh`, which links everything
in this subtree into place.

## Ownership boundaries

- Ordinary home files are symlinked from this subtree by `../link.sh` (macOS only). Edit their
  repo sources; the edits are already live.
- Agent content (skills, instructions, Pi/Claude/Codex settings) is not owned by this subtree.
  It lives in `../agents/`, `../pi/`, `../claude/` and `../codex/` and is linked by the same
  `link.sh`.
- Review, commit, and push changes yourself. There is no automatic capture/commit/push or VPS
  synchronization. The two old jobs were persistently disabled and their installed plists
  removed on this Mac.
- VPS deployment is separate and requires an explicit request. Maintained deployment helpers
  copy/merge configuration and perform only their documented optional reloads. Software,
  services, timers, and system policy are separate operations.

## Ordinary home files

| Source in `config/` | Live target |
|---|---|
| `.zshrc`, `.zprofile`, `.zshenv`, `.tmux.conf` | matching files under `$HOME` |
| `starship.toml` | `~/.config/starship.toml` |
| `topgrade.toml` | `~/.config/topgrade.toml` |
| `ghostty/config` | `~/.config/ghostty/config` |
| `herdr/config.toml` | `~/.config/herdr/config.toml` |
| `herdr-auto-title/config.env` | `~/.config/herdr-auto-title/config.env` |
| `rpiv-advisor/advisor.json` | `~/.config/rpiv-advisor/advisor.json` |
| `vscode/settings.json`, `vscode/keybindings.json` | Code's User directory |
| `vscode/extensions.txt` | saved extension inventory; refresh explicitly with `code --list-extensions` |
| `vscode/argv.json` | linked as `~/.vscode/argv.json` (macOS); contains the per-install `crash-reporter-id` — copy is byte-for-byte, repo is private, crash reporting is off anyway. VS Code rewrites through the symlink when toggling the crash-reporter UI, like it does for settings |
| `vscode/README.md` | one-page inventory of this dir; see it for what's covered where |

## Other maintained content

| Path | Owner / use |
|---|---|
| `Brewfile` | Homebrew formulas, casks, and taps; install with `brew bundle --file=...` |
| `herdr/plugins.txt` | Installed Herdr plugin list; refresh with `herdr plugin list` |
| `herdr/config.vps.toml` | VPS Herdr config; deploy with `herdr/deploy-vps.sh` |
| `vps/` | VPS shell files, upkeep scripts, user units, apt policy, and app-root instructions |
| `docs/tmux.md`, `docs/herdr.md` | Operator guides |

## Explicit VPS/app configuration deployment

Choose only the scope requested; there is no orchestrator or background job:

```sh
./config/vps/deploy-vps.sh              # shell files + ~/apps/AGENTS.md, optional tmux reload
./config/herdr/deploy-vps.sh            # Herdr config + reload
./config/druk/deploy-druk.sh            # local settings/pi-opener only
DEPLOY_DRUK_HOST=vps ./config/druk/deploy-druk.sh  # also merge remote settings
```

The VPS helper does not install weekly
upkeep, services, or apt policy; those operational assets remain here but require separate
installation/maintenance. Druk deployment does not download extensions; `extensions.txt`
remains an inventory.

## Setup

Clone the unified repository and run the linker; it creates the home-file links above (skipping
any destination whose contents differ from the repo, and exiting 1):

```sh
git clone git@github.com:ediab/dotfiles.git ~/Dev/dotfiles
~/Dev/dotfiles/link.sh
```

Software installation is separate. `Brewfile` is an inventory for a separately requested
Homebrew install (`brew bundle --file=config/Brewfile`). No machine installer or
background-job installation is provided.

For separately requested tmux plugin installation, TPM can be installed manually:

```sh
git clone https://github.com/tmux-plugins/tpm ~/.tmux/plugins/tpm
~/.tmux/plugins/tpm/bin/install_plugins
```

Tmux setup and configuration notes are in `config/docs/tmux.md`; Herdr notes are in
`config/docs/herdr.md`.
