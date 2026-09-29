# Imported configuration subtree

`config/` is the history-preserving import of the former standalone configuration checkout. It is a
transitional layout for Milestone 1; the single repository is `ediab/dotfiles`, checked out at
`~/Dev/dotfiles`. Do not recreate a second configs checkout. Milestone 2 will move ordinary
home files out of this subtree and into the chezmoi source root.

Until then, this directory remains the source for ordinary Mac settings and exceptional app
configuration. See the top-level `README.md` for agent-content ownership and the complete
repository overview.

## Ownership boundaries

- Ordinary home files are currently symlinked from this subtree. Edit the source here; do not
  edit or replace a live symlink target separately. These files are planned for chezmoi in
  Milestone 2, but are not managed by chezmoi yet.
- Agent content lives in the top-level `home/` directory. `sync-agent-content.sh` alone owns
  shared/Pi-only skills, Claude links, generated instructions, and the local manifest/backups.
- `capture.sh` is the one capture committer. It captures only the two live Pi JSON files and
  tracked changes under `config/`; untracked files and unrelated staged paths stay out of its
  commit. It refreshes the VS Code extension list best-effort.
- Firefox data is actively written by Firefox, so use `firefox/sync.sh`; do not symlink the
  profile files.
- VPS changes stay explicit in this subtree's deploy scripts; they are not managed by
  chezmoi.

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
| `Brewfile` | installed with `brew bundle --file=...` |
| `vscode/extensions.txt` | refreshed from `code --list-extensions` by `capture.sh` |

## Other maintained content

| Path | Owner / use |
|---|---|
| `Brewfile` | Homebrew formulas, casks, and taps; install with `brew bundle --file=...` |
| `herdr/plugins.txt` | Installed Herdr plugin list; refresh with `herdr plugin list` |
| `herdr/config.vps.toml` | VPS Herdr config; deploy with `herdr/deploy-vps.sh` |
| `vps/` | VPS shell files, upkeep scripts, user units, apt policy, and app-root instructions |
| `firefox/` | Firefox profile backup sources and the exceptional sync script |
| `bin/sync-vps.sh` | Change-gated four-step VPS orchestrator |
| `docs/tmux.md`, `docs/herdr.md` | Operator guides |
| `docs/tmux_proposal.md` | Historical tmux integration proposal |

## VPS synchronization

Run the merged orchestrator from the repository root:

```sh
~/Dev/dotfiles/config/bin/sync-vps.sh            # deploy when inputs changed
~/Dev/dotfiles/config/bin/sync-vps.sh --force    # bypass only the timestamp gate
```

It runs, in order, top-level `deploy-vps.sh` (agent content), `config/vps/deploy-vps.sh`,
`config/herdr/deploy-vps.sh`, and `config/druk/deploy-druk.sh`. It watches exactly top-level
`home/` and `deploy-vps.sh`, plus `config/vps/`, `config/herdr/config.vps.toml`, and
`config/druk/`. An idle run opens no SSH connection. Every step runs after a failure; the
success stamp advances only when all four succeed. Logs are `/tmp/com.diab.sync-vps.{out,err}`.

Do not install/load the VPS launchd job until the remote agent-content ownership manifest has
been explicitly adopted and verified, and one forced orchestrator run has completed all four
steps successfully. `bootstrap.sh` installs only capture; afterward the VPS job is installed
separately with:

```sh
~/Dev/dotfiles/install-launchd.sh sync-vps
```

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
brew bundle --file="$PWD/config/Brewfile"
```

`bootstrap.sh` installs the capture job from the root `launchd/` templates. Do not copy or load
the old launchd plist files by hand.

Firefox is synced, not symlinked, because it actively writes profile files:

```sh
cd ~/Dev/dotfiles/config/firefox && ./sync.sh
~/Dev/dotfiles/config/firefox/sync.sh --latest
```

To restore into a fresh Firefox profile, close Firefox and copy the versioned preferences,
containers, handlers, search, and Chrome CSS/theme files from `config/firefox/`. The live
profile remains the source for sensitive files, storage, and extension binaries.

```sh
PROFILE="$HOME/Library/Application Support/Firefox/Profiles/<profile>"
cp config/firefox/prefs.js "$PROFILE/"
cp config/firefox/extension-preferences.json "$PROFILE/"
cp config/firefox/extension-settings.json "$PROFILE/"
cp config/firefox/containers.json "$PROFILE/"
cp config/firefox/handlers.json "$PROFILE/"
cp config/firefox/search.json.mozlz4 "$PROFILE/"
cp config/firefox/chrome/userChrome.css "$PROFILE/chrome/"
cp config/firefox/chrome/userContent.css "$PROFILE/chrome/"
cp -R config/firefox/chrome/theme/ "$PROFILE/chrome/theme/"
```

Tmux plugins can be installed with TPM:

```sh
git clone https://github.com/tmux-plugins/tpm ~/.tmux/plugins/tpm
~/.tmux/plugins/tpm/bin/install_plugins
```

Tmux setup and configuration notes are in `config/docs/tmux.md`; Herdr notes are in
`config/docs/herdr.md`.
