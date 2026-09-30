# Imported configuration subtree

`config/` is the history-preserving import of the former standalone configuration checkout.
The single repository is `ediab/dotfiles`, checked out at `~/Dev/dotfiles`; do not recreate a
second configs checkout. This directory holds ordinary Mac settings and app/VPS configuration.
No chezmoi migration is assumed.

See the [top-level README](../README.md) for the manual save/apply workflow, agent-content
ownership, scoped configuration commands, and separately requested deployment.

## Ownership boundaries

- Ordinary home files are symlinked from this subtree. Edit their repo sources; keep the
  existing links intact. These edits are already live.
- Agent content lives in the top-level `home/` directory. `sync-agent-content.sh` alone owns
  shared/Pi-only skills, Claude links, generated instructions, and the local manifest/backups.
- Save application-written preferences explicitly. Review, commit, and push changes yourself.
  Use the explicitly invoked `update-dotfiles` skill for save/apply guidance once deployed.
- VPS deployment is separate and requires an explicit request. Maintained deployment helpers
  copy/merge configuration and perform only their documented optional reloads. Software,
  services, timers, and system policy are separate operations.
- There is no automatic capture/commit/push or VPS synchronization. The two old jobs were
  persistently disabled and their installed plists removed on this Mac.

Machine-local agent state intentionally keeps its legacy names across the repository rename:
`~/.local/state/pi-dotfiles/` (manifest/backups), `~/.config/pi-dotfiles/local/` (instruction
overlays), and `~/.cache/pi-dotfiles-agent-content/` (VPS staging). These paths preserve
existing ownership and avoid a new adoption migration.

## Ordinary home files

| Source in `config/` | Live target |
|---|---|
| `.zshrc`, `.zprofile`, `.zshenv`, `.tmux.conf` | matching files under `$HOME` |
| `starship.toml` | `~/.config/starship.toml` |
| `ghostty/config` | `~/.config/ghostty/config` |
| `herdr/config.toml` | `~/.config/herdr/config.toml` |
| `rpiv-advisor/advisor.json` | `~/.config/rpiv-advisor/advisor.json` |
| `vscode/settings.json`, `vscode/keybindings.json` | Code's User directory |
| `vscode/extensions.txt` | saved extension inventory; refresh explicitly with `code --list-extensions` |

## Other maintained content

| Path | Owner / use |
|---|---|
| `Brewfile` | Homebrew formulas, casks, and taps; install with `brew bundle --file=...` |
| `herdr/plugins.txt` | Installed Herdr plugin list; refresh with `herdr plugin list` |
| `herdr/config.vps.toml` | VPS Herdr config; deploy with `herdr/deploy-vps.sh` |
| `vps/` | VPS shell files, upkeep scripts, user units, apt policy, and app-root instructions |
| `docs/tmux.md`, `docs/herdr.md` | Operator guides |

## Explicit VPS/app configuration deployment

Choose only the scope requested; there is no four-step orchestrator or background job:

```sh
./deploy-vps.sh vps                     # repo-source agent configuration (from repo root)
./config/vps/deploy-vps.sh              # shell files + ~/apps/AGENTS.md, optional tmux reload
./config/herdr/deploy-vps.sh            # Herdr config + reload
./config/druk/deploy-druk.sh            # local settings/pi-opener only
DEPLOY_DRUK_HOST=vps ./config/druk/deploy-druk.sh  # also merge remote settings
```

Agent deployment preserves remote auth, runtime state, package declarations, and machine
settings. Its manifest requires separate explicit remote adoption and a clean preflight;
see the root README for staging/adoption guidance. The VPS helper does not install weekly
upkeep, services, or apt policy; those operational assets remain here but require separate
installation/maintenance. Druk deployment does not download extensions; `extensions.txt`
remains an inventory.

## Setup and app-specific sync

Clone the unified repository:

```sh
git clone git@github.com:ediab/dotfiles.git ~/Dev/dotfiles
```

Current local links point into `~/Dev/dotfiles/config/`. On a new Mac, create the parent
folders first, then link the managed sources:

```sh
cd ~/Dev/dotfiles
ln -s "$PWD/config/.zshrc" ~/.zshrc
ln -s "$PWD/config/.zprofile" ~/.zprofile
ln -s "$PWD/config/.zshenv" ~/.zshenv
ln -s "$PWD/config/.tmux.conf" ~/.tmux.conf
mkdir -p ~/.config/ghostty ~/.config/herdr ~/.config/rpiv-advisor
ln -s "$PWD/config/starship.toml" ~/.config/starship.toml
ln -s "$PWD/config/ghostty/config" ~/.config/ghostty/config
ln -s "$PWD/config/herdr/config.toml" ~/.config/herdr/config.toml
ln -s "$PWD/config/rpiv-advisor/advisor.json" ~/.config/rpiv-advisor/advisor.json
mkdir -p "$HOME/Library/Application Support/Code/User"
ln -s "$PWD/config/vscode/settings.json" "$HOME/Library/Application Support/Code/User/settings.json"
ln -s "$PWD/config/vscode/keybindings.json" "$HOME/Library/Application Support/Code/User/keybindings.json"
```

Inspect existing destinations first; preserve or back them up rather than replacing files
or links blindly. Software installation is separate from applying these links. `Brewfile`
is an inventory for a separately requested Homebrew install, not a dotfiles apply step.
No machine installer or background-job installation is provided.

For separately requested tmux plugin installation, TPM can be installed manually:

```sh
git clone https://github.com/tmux-plugins/tpm ~/.tmux/plugins/tpm
~/.tmux/plugins/tpm/bin/install_plugins
```

Tmux setup and configuration notes are in `config/docs/tmux.md`; Herdr notes are in
`config/docs/herdr.md`.
