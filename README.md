# configs

Dotfiles and terminal/editor configuration, versioned for sync across machines.

## Why this repo exists separately from `pi-dotfiles`

Two repos, one rule: **if the app writes the live file at runtime → it lives in
`pi-dotfiles` (copy-deployed). If the app only reads it → it lives here (symlinked).**

Shell, terminal, editor, Herdr, and VPS configs are read-only from the app's
perspective, so a symlink (Mac) or a push script (VPS, which can't read this repo)
is enough — no copy-back dance needed. pi's `~/.pi/agent/`, which pi itself rewrites,
is the exception, and it gets its own repo so it stays a shareable template.

## Files

| File | Symlink target | Purpose |
|------|---------------|---------|
| `.zshrc` | `~/.zshrc` | Zsh config (oh-my-zsh, aliases, fzf, starship, tools) |
| `.zprofile` | `~/.zprofile` | Login shell: brew shellenv, PATH entries |
| `.zshenv` | `~/.zshenv` | Every zsh invocation: cargo env |
| `Brewfile` | _(none — install via `brew bundle install`)_ | Homebrew formulas, casks, and taps |
| `.tmux.conf` | `~/.tmux.conf` | Tmux config (Ghostty-optimized, pi-subagents, 8 plugins) |
| `starship.toml` | `~/.config/starship.toml` | Prompt theme |
| `ghostty/config` | `~/.config/ghostty/config` | Terminal emulator (Catppuccin Mocha theme) |
| `vscode/settings.json` | `~/Library/Application Support/Code/User/settings.json` | Editor settings |
| `vscode/keybindings.json` | `~/Library/Application Support/Code/User/keybindings.json` | Custom keybindings |
| `vscode/extensions.txt` | _(none — regenerated via `code --list-extensions`)_ | Installed extension list |
| `herdr/plugins.txt` | _(none — regenerated via `herdr plugin list`)_ | Installed Herdr plugin list |
| `herdr/config.toml` | `~/.config/herdr/config.toml` | Herdr config (keybindings, UI) |
| `rpiv-advisor/advisor.json` | `~/.config/rpiv-advisor/advisor.json` | Pi advisor extension: reviewer model, effort, model blocklist, guidance |
| `herdr/config.vps.toml` | _(none — deploy via `herdr/deploy-vps.sh`)_ | Herdr config for the VPS (`ssh vps`), headless toast delivery |
| `vps/` | _(none — deploy via `vps/deploy-vps.sh`)_ | VPS shell dotfiles (`.zshrc`, `.zshenv`, `.p10k.zsh`, `.tmux.conf`) — the rows below cover the rest of `vps/` |
| `vps/vps-cleanup.sh`, `vps/vps-update-images.sh` | _(none — deployed to `~/bin`, run by user timers)_ | Weekly VPS disk cleanup and third-party container image refresh |
| `vps/systemd/*.{service,timer}` | _(none — deployed to `~/.config/systemd/user`)_ | Timers for those two jobs, plus `herdr-server.service` |
| `vps/apt/51-vps-auto-updates` | _(none — deployed to `/etc/apt/apt.conf.d`)_ | unattended-upgrades policy: origins, 03:30 auto-reboot, kernel cleanup |
| `vps/apps-AGENTS.md` | _(none — deployed to `~/apps/AGENTS.md`)_ | VPS app-root process doc (deploys, auto-updates, weekly upkeep) |
| `bin/sync-vps.sh` | _(none — runs as `com.diab.sync-vps`)_ | Syncs the `pi-dotfiles`, `vps/`, and `herdr/` deploys to `ssh vps` |
| `firefox/` | _(none — sync via `firefox/sync.sh`)_ | Firefox profile configs (prefs, chrome CSS, extensions, bookmarks) |

## Docs

- `AGENTS.md` — Project-specific instructions for LLM coding agents working in this repo
- `docs/tmux.md` — Beginner's guide tuned to this exact tmux config
- `docs/herdr.md` — Herdr keybindings guide (built-ins + plugin bindings)
- `docs/tmux_proposal.md` — Reference proposal for pi-subagents tmux integration

## Auto-commit

A launch agent auto-commits and pushes changes every 15 minutes:

```sh
cp ~/dev/configs/launchd/com.diab.autocommit-configs.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.diab.autocommit-configs.plist
```

This also keeps `vscode/extensions.txt` up to date automatically.

## VPS sync

A second launch agent pushes the VPS deploys every 15 minutes (and at login):

```sh
cp ~/dev/configs/launchd/com.diab.sync-vps.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.diab.sync-vps.plist
```

`bin/sync-vps.sh` is the single orchestrator for all VPS deploys. It runs four steps —
`~/dev/pi-dotfiles/deploy-vps.sh` (pi harness), `vps/deploy-vps.sh`, `herdr/deploy-vps.sh`,
`druk/deploy-druk.sh` — but only when something under their source paths changed since the
last successful run, so an idle tick makes no SSH connection. (There used to be a step
`nvim/deploy-vps.sh`; Neovim was removed from the Mac and the VPS in favour of druk.)

`pi-dotfiles` is treated as a dependency with a stable interface: the orchestrator calls
`deploy-vps.sh [host]` and watches its `home/` for changes, without knowing its
internals (its per-step contract is documented in the pi-dotfiles README). The other
three steps are this repo's own scripts, configured via env (`VPS_HOST`,
`HERDR_VPS_HOST`, `DEPLOY_DRUK_HOST`).

```sh
~/dev/configs/bin/sync-vps.sh            # deploy now if anything changed
~/dev/configs/bin/sync-vps.sh --force    # deploy regardless
```

A failing step never blocks the others, the stamp (`~/.cache/sync-vps.stamp`) only advances
when all four succeeded, and a failure raises a macOS notification at most once an hour.
Logs: `/tmp/com.diab.sync-vps.{out,err}`.

`vps/deploy-vps.sh` does more than dotfiles: it also installs the VPS's own weekly upkeep
(`~/bin/vps-cleanup.sh` + `~/bin/vps-update-images.sh` on user timers), the `herdr-server`
unit, the `unattended-upgrades` policy into `/etc/apt/apt.conf.d/`, and `~/apps/AGENTS.md`.
The schedule, protected images and log paths are in AGENTS.md.

## Setup on a new machine

```sh
git clone git@github.com:ediab/configs.git ~/dev/configs
ln -s ~/dev/configs/.zshrc ~/.zshrc
ln -s ~/dev/configs/.zprofile ~/.zprofile
ln -s ~/dev/configs/.zshenv ~/.zshenv
ln -s ~/dev/configs/.tmux.conf ~/.tmux.conf
ln -s ~/dev/configs/starship.toml ~/.config/starship.toml
ln -s ~/dev/configs/ghostty/config ~/.config/ghostty/config
ln -s ~/dev/configs/herdr/config.toml ~/.config/herdr/config.toml
mkdir -p ~/.config/rpiv-advisor
ln -s ~/dev/configs/rpiv-advisor/advisor.json ~/.config/rpiv-advisor/advisor.json
ln -s ~/dev/configs/vscode/settings.json ~/Library/Application\ Support/Code/User/settings.json
ln -s ~/dev/configs/vscode/keybindings.json ~/Library/Application\ Support/Code/User/keybindings.json

# Homebrew packages (run after installing Homebrew)
brew bundle --file=~/dev/configs/Brewfile

# Auto-commit agent
cp ~/dev/configs/launchd/com.diab.autocommit-configs.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.diab.autocommit-configs.plist

# VPS sync agent
cp ~/dev/configs/launchd/com.diab.sync-vps.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.diab.sync-vps.plist
```

## Firefox

Firefox configs are backed up via a sync script (not symlinked, since Firefox actively writes to these files).
Bookmark backups (`firefox/bookmarkbackups/`, Firefox's own dated snapshots) are gitignored —
only the latest is pulled on demand (`./firefox/sync.sh --latest`); the versioned backup is
the live profile plus `prefs.js`, `chrome/`, and extension/container data below.

```sh
cd ~/dev/configs/firefox && ./sync.sh            # full sync incl. latest bookmark backup
./firefox/sync.sh --latest                       # bookmark backup only
```

To restore on a new machine, close Firefox and copy the files into a fresh profile directory:

```sh
PROFILE=~/".mozilla/firefox/xxxxxxxx.your-profile"
cp ~/dev/configs/firefox/prefs.js "$PROFILE/"
cp ~/dev/configs/firefox/extension-preferences.json "$PROFILE/"
cp ~/dev/configs/firefox/extension-settings.json "$PROFILE/"
cp ~/dev/configs/firefox/containers.json "$PROFILE/"
cp ~/dev/configs/firefox/handlers.json "$PROFILE/"
cp ~/dev/configs/firefox/search.json.mozlz4 "$PROFILE/"
cp ~/dev/configs/firefox/chrome/userChrome.css "$PROFILE/chrome/"
cp ~/dev/configs/firefox/chrome/userContent.css "$PROFILE/chrome/"
cp -r ~/dev/configs/firefox/chrome/theme/ "$PROFILE/chrome/theme/"
cp ~/dev/configs/firefox/bookmarkbackups/*.jsonlz4 "$PROFILE/bookmarkbackups/"
```

## Tmux plugins

```sh
git clone https://github.com/tmux-plugins/tpm ~/.tmux/plugins/tpm
~/.tmux/plugins/tpm/bin/install_plugins
```
