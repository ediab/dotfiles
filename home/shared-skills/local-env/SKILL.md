---
name: local-env
description: Environment reference — VPS access and `ssh vps`, service deploys and restarts, the `~/Dev/dotfiles` repository, dotfile symlinks, and the dual-edit GitHub workflow. Use when touching the VPS, deploying a service, symlinks, dotfiles, or shell/terminal/editor config. Not for editing application code.
---

# Local environment

Lookup reference for this machine's environment. Not for editing application code — project code follows the project's own `AGENTS.md`.

## Dotfiles and agent content

The private `ediab/dotfiles` repository is checked out at `~/Dev/dotfiles`. `config/` holds ordinary Mac, app, and VPS configuration; `home/` holds agent-content sources. Edit ordinary dotfiles at their repo symlink sources.

Agent-content sources live under `home/`. Portable skills in `home/shared-skills/` are copied to `~/.agents/skills/`, with Claude links when Claude Code is installed. Client-specific skill sources and other client configuration use the destinations documented by the deployment scripts. Shared instructions combine `home/AGENTS.md` with optional repo, client, and machine overlays.

`sync-agent-content.sh` owns managed skills, Claude links, and generated instructions. Agent clients may rewrite live settings, so compare the live and repo versions instead of assuming they match.

For explicit save/apply work, invoke the `update-dotfiles` skill by name through the current client. This reference supplies paths, not permission to apply or deploy. The repo README documents scoped `apply.sh` commands; the old capture/auto-push and VPS-sync jobs have been retired on this Mac.

These legacy runtime paths intentionally remain unchanged across the repository rename so existing ownership state is still recognized:
- `~/.local/state/pi-dotfiles/` — agent-content manifest and backups;
- `~/.config/pi-dotfiles/local/` — machine-local instruction overlays;
- `~/.cache/pi-dotfiles-agent-content/` — staged VPS agent content.

Ordinary home config sources currently symlinked from `config/` include:
- `.zshrc`, `.zprofile`, `.zshenv`, `.tmux.conf` → matching files in `$HOME`;
- `starship.toml`, `ghostty/config`, `herdr/config.toml`, `rpiv-advisor/advisor.json` → matching paths under `~/.config/`;
- `vscode/settings.json` and `vscode/keybindings.json` → Code's User directory.

## VPS access

To access this VPS use `ssh vps` (alias defined in `~/.ssh/config`).
- Host: `77.42.90.4`
- User: `diab`
- IdentityFile: `~/.ssh/id_rsa_nroot`
- ControlMaster multiplexing enabled; LocalForward 18789, 18792, 19999.
- `~/Dev/dotfiles/deploy-vps.sh` deploys agent content and Pi configuration to the VPS.

VPS agent-content deployment requires its own adopted ownership manifest. On an explicitly requested first deployment, use `deploy-vps.sh --prepare-agent-content vps` to stage sources, review the remote helper's `--adopt` dry run, and obtain approval before `--adopt --yes`. Routine deployment requires a clean no-write preflight; local adoption does not authorize remote adoption.

VPS/app configuration helpers are independent: root `deploy-vps.sh` (agent config), `config/vps/deploy-vps.sh` (shell files/instructions), `config/herdr/deploy-vps.sh` (Herdr config/reload), and `config/druk/deploy-druk.sh` (local settings; `DEPLOY_DRUK_HOST=vps` also selects remote settings). Choose only the explicitly requested scope; package/service maintenance is separate.

## Dual-edit workflow (local `~/Dev` + VPS `~/apps`)

GitHub is the source of truth for every project that exists in both places. The VPS holds git clones under `~/apps`, never bare rsync copies.
- Edit wherever suits (local or `ssh vps` terminal), then commit and push from there; pull on the other side before editing.
- Never rsync/scp tracked code files to `~/apps`. rsync is only for secrets (`.env`, `.env.vps`), databases, and uploads (`db/`, `userfiles/`, `state/`, episode data).
- Deploy = push to the default branch, then on the VPS `git fetch` plus `git merge --ff-only` (or `git pull --ff-only`) from a clean tree, then the service's restart step. Never `--force` shared history; unmerged VPS work lives on a `vps-*` branch until reviewed.
- On the VPS, git remotes must use the `github-personal` SSH alias (the full-access key). Plain `git@github.com` authenticates as a limited deploy key that only reaches a couple of repos (fastmailai, tfl); `https` remotes with embedded tokens are forbidden.
- Service restart steps: mp3podcasts and redact_pdf via `docker compose up -d --build` in their `~/apps` dir; note-sx via `docker compose pull && docker compose up -d` (image-based) plus the nginx section of its `deploy.sh`; onyx via `docker compose up -d --build` (`scripts/sync_to_vps.sh` is legacy rsync — do not use for code); fousekis API via `sudo systemctl restart fousekis-api` (plain node, no build).
- Not code deploys, no git needed: `~/apps/fousekis-api` (runtime `.venv` plus empty `audio/`/`drafts/`; code lives in the fousekis repo), goatcounter (binary plus sqlite), karakeep/guacamole (third-party images). Runtime/third-party dirs generally have no git workflow.
