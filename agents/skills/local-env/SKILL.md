---
name: local-env
description: Environment reference — VPS access and `ssh vps`, service deploys and restarts, the `~/Dev/dotfiles` repository, dotfile symlinks, and the dual-edit GitHub workflow. Use when touching the VPS, deploying a service, symlinks, dotfiles, or shell/terminal/editor config. Not for editing application code.
---

# Local environment

Lookup reference for this machine's environment. Not for editing application code — project code follows the project's own `AGENTS.md`.

## Dotfiles and agent content

The private `ediab/dotfiles` repository is checked out at `~/Dev/dotfiles`. The checkout is the live copy: `link.sh` symlinks its files into `~/.pi`, `~/.claude`, `~/.codex`, `~/.agents` and `$HOME`, so editing the repo (or a tool saving a setting) changes what the apps see immediately. `link.sh` takes no flags and is safe to rerun; it prints `SKIP` and exits 1 if a destination differs from the repo. Do not experiment on the main checkout; use a separate worktree.

- `agents/` — `AGENTS.md` (linked as Pi's `AGENTS.md`, Codex's `AGENTS.md` and Claude's `CLAUDE.md`) and `skills/` (linked as `~/.agents/skills`, plus one link per skill in `~/.claude/skills`). Create new personal skills in `~/.agents/skills/<name>`; Claude sees them after its next start.
- `pi/`, `claude/`, `codex/` — each client's settings, plus Pi-only skills, agent profiles, extensions and themes.
- `config/` — ordinary Mac, app and VPS configuration, linked into `$HOME` on macOS only.
- Secrets live in `~/.env` (never in the repo; `.env.example` lists the names).

Ordinary home config sources linked from `config/`:
- `.zshrc`, `.zprofile`, `.zshenv`, `.tmux.conf` → matching files in `$HOME`;
- `starship.toml`, `ghostty/config`, `herdr/config.toml`, `rpiv-advisor/advisor.json` → matching paths under `~/.config/`;
- `vscode/settings.json` and `vscode/keybindings.json` → Code's User directory.

Committing, pushing and VPS deployment still need an explicit request.

## VPS access

To access this VPS use `ssh vps` (alias defined in `~/.ssh/config`).
- Host: `77.42.90.4`
- User: `diab`
- IdentityFile: `~/.ssh/id_rsa_nroot`
- ControlMaster multiplexing enabled; LocalForward 18789, 18792, 19999.

VPS agent content is not yet on the `link.sh` model; until it is migrated, do not deploy agent content to the VPS.

VPS/app configuration helpers are independent: `config/vps/deploy-vps.sh` (shell files/instructions), `config/herdr/deploy-vps.sh` (Herdr config/reload), and `config/druk/deploy-druk.sh` (local settings; `DEPLOY_DRUK_HOST=vps` also selects remote settings). Choose only the explicitly requested scope; package/service maintenance is separate.

## Dual-edit workflow (local `~/Dev` + VPS `~/apps`)

GitHub is the source of truth for every project that exists in both places. The VPS holds git clones under `~/apps`, never bare rsync copies.
- Edit wherever suits (local or `ssh vps` terminal), then commit and push from there; pull on the other side before editing.
- Never rsync/scp tracked code files to `~/apps`. rsync is only for secrets (`.env`, `.env.vps`), databases, and uploads (`db/`, `userfiles/`, `state/`, episode data).
- Deploy = push to the default branch, then on the VPS `git fetch` plus `git merge --ff-only` (or `git pull --ff-only`) from a clean tree, then the service's restart step. Never `--force` shared history; unmerged VPS work lives on a `vps-*` branch until reviewed.
- On the VPS, git remotes must use the `github-personal` SSH alias (the full-access key). Plain `git@github.com` authenticates as a limited deploy key that only reaches a couple of repos (fastmailai, tfl); `https` remotes with embedded tokens are forbidden.
- Service restart steps: mp3podcasts and redact_pdf via `docker compose up -d --build` in their `~/apps` dir; note-sx via `docker compose pull && docker compose up -d` (image-based) plus the nginx section of its `deploy.sh`; onyx via `docker compose up -d --build` (`scripts/sync_to_vps.sh` is legacy rsync — do not use for code); fousekis API via `sudo systemctl restart fousekis-api` (plain node, no build).
- Not code deploys, no git needed: `~/apps/fousekis-api` (runtime `.venv` plus empty `audio/`/`drafts/`; code lives in the fousekis repo), goatcounter (binary plus sqlite), karakeep/guacamole (third-party images). Runtime/third-party dirs generally have no git workflow.
