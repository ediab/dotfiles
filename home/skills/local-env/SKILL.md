---
name: local-env
description: Environment reference — VPS access and `ssh vps`, service deploys and restarts, deploy-vps.sh and sync-vps.sh, pi-dotfiles sync via rebuild.sh, dotfile symlinks, and the dual-edit GitHub workflow. Use when touching the VPS, deploying a service, symlinks, dotfiles, pi-dotfiles sync, or shell/terminal/editor config. Not for editing application code.
---

# Local environment

Lookup reference for this machine's environment. Not for editing application code — project code follows the project's own `AGENTS.md`.

## pi-dotfiles sync

Keep pi-dotfiles as the source of truth. Edit portable skills in `home/shared-skills/`, Pi-only skills in `home/skills/`, extensions in `home/extensions/`, and agents in `home/agents/`. `rebuild.sh` runs the shared deployment helper for skills and generated instructions; it also deploys Pi extensions, agents, and config. `rebuild.sh --sync-only` skips package updates and the `settings.json` copy. Packages need no manual mirroring — `sync-settings.sh` records `pi install`/`pi uninstall` into `home/settings.json` automatically. Edit global policy in `home/AGENTS.md`, client-specific repo instructions in `home/instructions/`, or machine-only additions under `~/.config/pi-dotfiles/local/`; do not copy live edits into the repo except after reviewing and choosing to adopt them.

## Dotfiles and configs

Shell, terminal, and editor configs live in `~/dev/configs/` (git repo). Edit them there and commit, so they stay versioned and syncable across machines.

Symlinked (edit in `~/dev/configs/` directly):
- `.zshrc` → `~/.zshrc`
- `ghostty/config` → `~/.config/ghostty/config`
- `starship.toml` → `~/.config/starship.toml`
- `vscode/settings.json` → `~/Library/Application Support/Code/User/settings.json`
- `vscode/keybindings.json` → `~/Library/Application Support/Code/User/keybindings.json`

Pi agent settings and extensions live in `~/dev/pi-dotfiles/home/` and are deployed by `bootstrap.sh`/`rebuild.sh`. Portable skills live in `home/shared-skills/` and deploy to `~/.agents/skills/` (with Claude links when Claude Code is installed); Pi-only skills live in `home/skills/` and deploy to `~/.pi/agent/skills/`. Edit sources in the repo, then run `~/dev/pi-dotfiles/rebuild.sh`. Note: `pi` itself rewrites `settings.json` (changelog version, installed-packages list); re-sync live→repo after such changes to avoid backup drift.

Also: `vscode/extensions.txt` — list of installed VS Code extensions, regenerated with `code --list-extensions`.

## VPS access

To access this VPS use `ssh vps` (alias defined in `~/.ssh/config`).
- Host: `77.42.90.4`
- User: `diab`
- IdentityFile: `~/.ssh/id_rsa_nroot`
- ControlMaster multiplexing enabled; LocalForward 18789, 18792, 19999.
- `deploy-vps.sh` (in `~/dev/pi-dotfiles`) mirrors this file to the VPS along with skills, extensions, agents and package configs.

## Dual-edit workflow (local `~/Dev` + VPS `~/apps`)

GitHub is the source of truth for every project that exists in both places. The VPS holds git clones under `~/apps`, never bare rsync copies.
- Edit wherever suits (local or `ssh vps` terminal), then commit and push from there; pull on the other side before editing.
- Never rsync/scp tracked code files to `~/apps`. rsync is only for secrets (`.env`, `.env.vps`), databases, and uploads (`db/`, `userfiles/`, `state/`, episode data).
- Deploy = push to the default branch, then on the VPS `git fetch` plus `git merge --ff-only` (or `git pull --ff-only`) from a clean tree, then the service's restart step. Never `--force` shared history; unmerged VPS work lives on a `vps-*` branch until reviewed.
- On the VPS, git remotes must use the `github-personal` SSH alias (the full-access key). Plain `git@github.com` authenticates as a limited deploy key that only reaches a couple of repos (fastmailai, tfl); `https` remotes with embedded tokens are forbidden.
- Service restart steps: mp3podcasts and redact_pdf via `docker compose up -d --build` in their `~/apps` dir; note-sx via `docker compose pull && docker compose up -d` (image-based) plus the nginx section of its `deploy.sh`; onyx via `docker compose up -d --build` (`scripts/sync_to_vps.sh` is legacy rsync — do not use for code); fousekis API via `sudo systemctl restart fousekis-api` (plain node, no build).
- Not code deploys, no git needed: `~/apps/fousekis-api` (runtime `.venv` plus empty `audio/`/`drafts/`; code lives in the fousekis repo), goatcounter (binary plus sqlite), karakeep/guacamole (third-party images). Runtime/third-party dirs generally have no git workflow.

## VPS config sync

`ssh vps` box config is pushed from `~/dev/configs`, never edited on the box. Entry point:

```sh
~/dev/configs/bin/sync-vps.sh            # deploy only if a source changed
~/dev/configs/bin/sync-vps.sh --force    # deploy unconditionally / re-align drift
```

Runs four steps in order (all run even if one fails): pi-dotfiles harness
(`~/dev/pi-dotfiles/deploy-vps.sh`: skills, extensions, settings, package reconcile),
VPS dotfiles (`configs/vps/deploy-vps.sh`: shell rc files, upkeep scripts, systemd
timers, apt policy, `~/apps/AGENTS.md`), Herdr VPS config
(`configs/herdr/deploy-vps.sh`), Neovim config (`configs/nvim/deploy-vps.sh`).
Gated on a stamp (`~/.cache/sync-vps.stamp`) so a tick with no edits costs nothing;
the stamp advances only when every step succeeded, failures retry next tick and
notify at most hourly. A launchd agent (`configs/launchd/com.diab.sync-vps.plist`)
runs it every 15 min and at login; logs in `/tmp/com.diab.sync-vps.{out,err}`.
