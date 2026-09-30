---
name: local-env
description: Environment reference — VPS access and `ssh vps`, service deploys and restarts, the `~/Dev/dotfiles` repository, dotfile symlinks, and the dual-edit GitHub workflow. Use when touching the VPS, deploying a service, symlinks, dotfiles, or shell/terminal/editor config. Not for editing application code.
---

# Local environment

Lookup reference for this machine's environment. Not for editing application code — project code follows the project's own `AGENTS.md`.

## Dotfiles and agent content

The private `ediab/dotfiles` repository is checked out at `~/Dev/dotfiles`. Its `config/` directory is the imported transitional subtree for ordinary Mac, app, and VPS configuration; Milestone 2 will move ordinary home files to chezmoi. Until then, edit symlink sources in `~/Dev/dotfiles/config/` directly.

Pi/agent sources live under `~/Dev/dotfiles/home/` and are deployed by `bootstrap.sh`/`rebuild.sh`:
- portable skills: `home/shared-skills/` → `~/.agents/skills/` (with Claude links when Claude Code is installed);
- Pi-only skills: `home/skills/` → `~/.pi/agent/skills/`;
- extensions, agents, settings, and shared instructions: deployed by the repository scripts.

`sync-agent-content.sh` is the sole owner of shared/Pi-only skills, Claude links, generated instructions, and its machine-local ownership manifest/backups. Run `~/Dev/dotfiles/rebuild.sh --sync-only` to update managed agent content without package updates or copying `settings.json`.

The capture job (`capture.sh`) watches live Pi settings, copies existing `settings.json`/`open-tui.json` into `home/`, refreshes the VS Code extension list best-effort, and commits only tracked changes under its allowlist. Pi itself can rewrite `settings.json`; review any manual live changes before allowing them to be captured.

These legacy runtime paths intentionally remain unchanged across the repository rename so existing ownership state is still recognized:
- `~/.local/state/pi-dotfiles/` — agent-content manifest and backups;
- `~/.config/pi-dotfiles/local/` — machine-local instruction overlays;
- `~/.cache/pi-dotfiles-agent-content/` — staged VPS agent content.

Ordinary home config sources currently symlinked from `config/` include:
- `.zshrc`, `.zprofile`, `.zshenv`, `.tmux.conf` → matching files in `$HOME`;
- `starship.toml`, `ghostty/config`, `herdr/config.toml`, `rpiv-advisor/advisor.json` → matching paths under `~/.config/`;
- `vscode/settings.json` and `vscode/keybindings.json` → Code's User directory.

Firefox is exceptional: the profile is actively written, so use `config/firefox/sync.sh` rather than a symlink. `capture.sh` refreshes `config/vscode/extensions.txt` with `code --list-extensions` when available.

## VPS access

To access this VPS use `ssh vps` (alias defined in `~/.ssh/config`).
- Host: `77.42.90.4`
- User: `diab`
- IdentityFile: `~/.ssh/id_rsa_nroot`
- ControlMaster multiplexing enabled; LocalForward 18789, 18792, 19999.
- `~/Dev/dotfiles/deploy-vps.sh` deploys agent content and Pi configuration to the VPS.

Do not load VPS synchronization before the agent-content ownership manifest has been adopted with explicit approval. Stage first with `~/Dev/dotfiles/deploy-vps.sh --prepare-agent-content vps`, review the remote `--adopt` dry run, and stop for human approval before `--adopt --yes`. Then verify the manifest and no-write preflight, run `sync-vps.sh --force` once, and confirm all four steps and the success stamp before installing. `bootstrap.sh` installs the capture job only; use `install-launchd.sh sync-vps` after those checks.

The VPS orchestrator is `~/Dev/dotfiles/config/bin/sync-vps.sh`. It runs four steps in order (all steps continue after failure): agent content (`deploy-vps.sh`), VPS dotfiles (`config/vps/deploy-vps.sh`), Herdr (`config/herdr/deploy-vps.sh`), and druk (`config/druk/deploy-druk.sh`). It watches `home/`, top-level `deploy-vps.sh` and `reconcile-pi-packages.py`, `config/vps/`, `config/herdr/config.vps.toml`, and `config/druk/`. Unchanged inputs cause no SSH connection; the success stamp advances only if every step succeeds.

```sh
~/Dev/dotfiles/config/bin/sync-vps.sh          # deploy when a source changed
~/Dev/dotfiles/config/bin/sync-vps.sh --force  # bypass only the orchestrator's timestamp gate
```

## Dual-edit workflow (local `~/Dev` + VPS `~/apps`)

GitHub is the source of truth for every project that exists in both places. The VPS holds git clones under `~/apps`, never bare rsync copies.
- Edit wherever suits (local or `ssh vps` terminal), then commit and push from there; pull on the other side before editing.
- Never rsync/scp tracked code files to `~/apps`. rsync is only for secrets (`.env`, `.env.vps`), databases, and uploads (`db/`, `userfiles/`, `state/`, episode data).
- Deploy = push to the default branch, then on the VPS `git fetch` plus `git merge --ff-only` (or `git pull --ff-only`) from a clean tree, then the service's restart step. Never `--force` shared history; unmerged VPS work lives on a `vps-*` branch until reviewed.
- On the VPS, git remotes must use the `github-personal` SSH alias (the full-access key). Plain `git@github.com` authenticates as a limited deploy key that only reaches a couple of repos (fastmailai, tfl); `https` remotes with embedded tokens are forbidden.
- Service restart steps: mp3podcasts and redact_pdf via `docker compose up -d --build` in their `~/apps` dir; note-sx via `docker compose pull && docker compose up -d` (image-based) plus the nginx section of its `deploy.sh`; onyx via `docker compose up -d --build` (`scripts/sync_to_vps.sh` is legacy rsync — do not use for code); fousekis API via `sudo systemctl restart fousekis-api` (plain node, no build).
- Not code deploys, no git needed: `~/apps/fousekis-api` (runtime `.venv` plus empty `audio/`/`drafts/`; code lives in the fousekis repo), goatcounter (binary plus sqlite), karakeep/guacamole (third-party images). Runtime/third-party dirs generally have no git workflow.
