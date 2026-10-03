---
name: local-env
description: Environment reference for dotfiles and symlinks, shell/terminal/editor configuration, VPS access, local/VPS code synchronization, and service deployment. Read when working in a VPS checkout or synchronizing code between machines. Not needed for ordinary local application implementation.
---

# Local environment

Environment and cross-machine operating rules. Application implementation follows the project's instructions; VPS access, synchronization, and deployment also follow this skill.

## Dotfiles and agent content

The public `ediab/dotfiles` repository is checked out at `~/Dev/dotfiles`. The checkout is the live copy: `link.sh` symlinks its files into `~/.pi`, `~/.claude`, `~/.codex`, `~/.agents` and `$HOME`, so editing the repo (or a tool saving a setting) changes what the apps see immediately. `link.sh` takes no flags and is safe to rerun. It replaces symlinks pointing elsewhere, converts identical real files/directories into links, and preserves conflicting real files/directories with `SKIP` and exit status 1.

Use a separate worktree for experiments, but do not run its `link.sh` against your real home: it would repoint live links to that worktree.

The VPS runs the same model: the repo is cloned at `~/Dev/dotfiles` there and `./link.sh` is run after pulling. The VPS links tracked Linux settings and shares Pi settings, skills, `AGENTS.md`, extensions and themes; run `./link.sh` after pulling so new links are ready before starting an agent.

- `agents/` — `AGENTS.md` (linked as Pi's `AGENTS.md`, Codex's `AGENTS.md` and Claude's `CLAUDE.md`) and `skills/` (linked as `~/.agents/skills`, plus one link per skill in `~/.claude/skills`). Create new personal skills in `~/.agents/skills/<name>`; Claude sees them after its next start. On the VPS, run `./link.sh` once after adding a skill.
- `pi/`, `claude/`, `codex/` — each client's settings, plus Pi-only skills, agent profiles, extensions and themes. `link.sh` selects `claude/settings.linux.json` and `codex/config.linux.toml` on Linux; the usual filenames are the Mac variants. Settings conflicts are protected, not normal VPS exceptions; a reconciled machine has zero skips.
- `config/` — ordinary Mac, app and VPS configuration, linked into `$HOME` on macOS only.
- Secrets live in `~/.env` (never in the repo; `.env.example` lists the names).

Ordinary home config sources linked from `config/`:
- `.zshrc`, `.zprofile`, `.zshenv` → matching files in `$HOME`;
- `starship.toml`, `ghostty/config`, `herdr/config.toml` → matching paths under `~/.config/`;
- `vscode/settings.json` and `vscode/keybindings.json` → Code's User directory.

Committing, pushing and VPS deployment still need an explicit request.

## VPS access

To access this VPS use `ssh vps` (alias defined in `~/.ssh/config`).
- Host: `77.42.90.4`
- User: `diab`
- IdentityFile: `~/.ssh/id_rsa_nroot`
- ControlMaster multiplexing enabled; LocalForward 18789, 18792, 19999.

VPS/app configuration helpers are independent: `config/vps/deploy-vps.sh` (shell files/instructions), `config/herdr/deploy-vps.sh` (Herdr config/reload), and `config/druk/deploy-druk.sh` (local settings; `DEPLOY_DRUK_HOST=vps` also selects remote settings). Choose only the explicitly requested scope; package/service maintenance is separate.

## VPS folder layout

Consult `~/README.md` on the VPS for the current service/data inventory and `~/ops/` for change and recovery records. Before deploying, restarting, moving, or retiring a VPS service, read [VPS-REFERENCE.md](VPS-REFERENCE.md) and verify its relevant claims against the live VPS inventory and service configuration.

- `~/apps/` holds deployed checkouts and runtime/third-party service bundles. `~/Dev/` holds development/configuration repositories; use uppercase `Dev` for new checkouts.
- `~/Dev/dotfiles` is the active configuration source; use the dotfiles linking workflow above for agent configuration.
- `~/Dev/xbot` is a live-path exception: systemd and cron depend on it. Keep it in place until a separately approved migration.
- `~/backups/<app>/` holds application recovery backups; `~/backups/changes/` holds one-off change snapshots. `~/archive/retired-projects/` and `~/archive/historical/` hold inactive material. Retention decisions require checking recovery value, not just age.
- Keep `~/bin/`, `~/logs/`, `~/actions-runner/`, and `~/actions-runner-work/` at their existing paths: service and maintenance configuration depends on them. Leave app-local data, secrets, and Docker-managed volumes in place.

## Dual-edit workflow (local `~/Dev` + VPS `~/apps`)

GitHub is the source of truth for every project that exists in both places. Deployed VPS clones normally live under `~/apps` (xbot is the exception above), never bare rsync copies.
- Edit wherever suits (local or `ssh vps` terminal), then commit and push from there; pull on the other side before editing.
- Never rsync/scp tracked code files to `~/apps`. rsync is only for secrets (`.env`, `.env.vps`), databases, and uploads (`db/`, `userfiles/`, `state/`, episode data).
- Deploy = push to the default branch, then on the VPS `git fetch` plus `git merge --ff-only` (or `git pull --ff-only`) from a clean tree, then the service's restart step. Never `--force` shared history; unmerged VPS work lives on a `vps-*` branch until reviewed.
- On the VPS, git remotes must use the `github-personal` SSH alias (the full-access key). Plain `git@github.com` authenticates as a limited deploy key that only reaches a couple of repos (morning-brief, tfl); `https` remotes with embedded tokens are forbidden.
- Third-party image bundles generally have no git workflow; consult the service reference for the appropriate update and restart steps.
