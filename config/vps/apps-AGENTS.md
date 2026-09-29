# VPS app root

These are deploy checkouts; GitHub is the source of truth.

- Keep trees clean; update with fetch plus fast-forward-only, then restart the service.
- Commit and push VPS edits; never leave uncommitted drift.
- Use `github-personal` remotes; plain `github.com` is limited here.
- Do not accept rsync/scp overwrites of tracked code; only secrets and data.
- Runtime/third-party dirs (`fousekis-api`, goatcounter, karakeep/guacamole) have no git workflow.

This file is versioned in the configs repo (`vps/apps-AGENTS.md`) and deployed by
`vps/deploy-vps.sh` — edit it there, not here.

## Automated deploys (push to main)

- Each git repo has a `Deploy to VPS` GitHub workflow: on push to main it SSHs in as `deployer` and runs `/home/diab/bin/vps-deploy.sh <service>` (absolute path, pinned action, 30m timeout, per-service concurrency).
- The helper serializes on a flock, requires a clean tree on the default branch, fetches (read-only token over https) plus fast-forward-only merge, then restarts per the map: compose rebuild (ai-cookbook, mp3podcasts, onyx, redact_pdf, greek_embassy_bot), compose pull (note-sx), npm build plus service restart (tfl), fousekis-api restart (fousekis), venv smoke check (fastmailai), quartz build (notes), nothing (personal_website).
- Restarts run under a shutdown inhibit (`/usr/local/sbin/vps-deploy-inhibit`) so the nightly OS reboot waits for deploys.
- SSH is confined: the deploy key lives only in deployer's `authorized_keys` behind the forced-command gate (`/usr/local/sbin/vps-deploy-ssh-gate`); deployer sudo is limited to the inhibit wrapper plus `systemctl restart` for tfl and fousekis-api. Per-repo secrets are `VPS_HOST` / `VPS_USER` / `VPS_SSH_KEY`.

## OS auto-updates

- `unattended-upgrades` installs updates from the base, security and ESM pockets with an automatic reboot at 03:30. The policy is `/etc/apt/apt.conf.d/51-vps-auto-updates`, versioned in the configs repo and installed by `vps/deploy-vps.sh` — edit it there.
- `50unattended-upgrades` is the package's own file (shipped from `/usr/share/unattended-upgrades/`) and is not managed here. apt merges the origins from both files, so general updates still install if that one is ever replaced by an upgrade. Do not hand-edit it: that is what left a stray `.bak-*` file behind and made apt warn about an invalid filename extension.
- Kernels left over from reboots are reaped by `Remove-Unused-Kernel-Packages` during unattended runs; the weekly cleanup only runs `autoremove`.
- A reboot is cut short of an in-flight deploy by the `vps-deploy-inhibit` shutdown inhibit.

## Weekly upkeep (com.diab.sync-vps deploys these; timers are user units)

- `~/bin/vps-cleanup.sh` — Sunday 04:30: caps the Docker build cache at 3 GB (`--max-used-space`; the older `--keep-storage` is a *floor*, not a cap), removes images no container uses except the protected build bases (the Playwright image greek_embassy_bot builds from), clears runner/npm/apt caches and runs `apt-get autoremove`. It takes the same `~/.cache/vps-deploy.lock` as `vps-deploy.sh` so pruning cannot race a build, is `--dry-run`-able, is idempotent, and exits non-zero if a step failed. The journal cap is soft — active journal files are exempt. Log: `~/logs/vps-cleanup.log`.
- `~/bin/vps-update-images.sh` — Sunday 05:30: stops each third-party-image project (note-sx, karakeep-app), snapshots its data into `~/backups/<app>/` (3 generations), verifies the archive with `tar -tzf` and refuses to pull if it is unusable, then pulls, recreates, health-checks, and re-tags the recorded image IDs if the project ends up unhealthy. Takes the same lock as `vps-deploy.sh`. Log: `~/logs/vps-update-images.log`.
- `herdr-server.service` — keeps the headless Herdr server running across reboots.
- Locally built images and the `deploy.sh`-managed nginx step are never touched by the weekly jobs; they belong to the push path.
