# VPS app root

These are deploy checkouts; GitHub is the source of truth.

- Keep trees clean; update with fetch plus fast-forward-only, then restart the service.
- Commit and push VPS edits; never leave uncommitted drift.
- Use `github-personal` remotes; plain `github.com` is limited here.
- Do not accept rsync/scp overwrites of tracked code; only secrets and data.
- Third-party image bundles such as `karakeep-app` have no git workflow. The live Fousekis API code is in `fousekis/api/`; its old transcription environment, GoatCounter and Termix were retired.

This file is versioned in the dotfiles repo at `config/vps/apps-AGENTS.md` and deployed by
`config/vps/deploy-vps.sh` — edit it there, not on the VPS.

## Automated deploys (push to main)

- App GitHub workflows use the forced-command gate. note-sx is mapped directly to `/usr/local/sbin/note-sx-deploy`; it does not run Git, Compose, or caller-supplied paths. Other enabled services use `/home/diab/bin/vps-deploy.sh <service>` or their existing dedicated gate route.
- The generic helper serializes on the deployer flock, requires a clean default-branch tree, fetches read-only over HTTPS, and fast-forwards before its service-specific action. Current enabled generic actions include Compose rebuild (redact_pdf, greek_embassy_bot), fousekis-api restart (fousekis), venv smoke check (morning-brief), Quartz build (notes), and no restart (personal_website). `cratch` and `tfl` retain their existing dedicated inhibit/helper routes; do not replace them with stale generic templates. **Onyx and mp3podcasts are intentionally paused**: the forced SSH gate rejects their CI service names, and the dispatcher denies their manual and `restart-inner` routes before Git or Docker work. Their containers must remain exited with restart policy `no` until separately reauthorized.
- note-sx's root helper uses a root-owned transaction lock and fixed input paths, holds the existing diab-owned cleanup lock through the owning account, and runs under a shutdown inhibit. The root-owned first-update hold is temporary: while held, weekly/push/manual no-argument calls log `update=held`, return nonzero, and do no pull/stop/snapshot/activation. The first cutover keeps running `e340...`; it does not pull a newer `latest`. The helper's privileged modes require root; the dedicated deployer sudoers entry accepts only the no-argument helper route. This route restriction is not effective containment while broader legacy authority remains; see the residual-authority note below. Release the hold only after owner/parent compatibility review, and only if `latest` still matches the reviewed digest recorded in the hold. That one-time release restores the existing automatic update policy; it is not per-release approval.
- Other restarts run under `/usr/local/sbin/vps-deploy-inhibit` so the nightly OS reboot waits for deploys. The inhibit wrapper and generic deploy helper reject legacy note-sx restart routes.
- The CI key remains behind `/usr/local/sbin/vps-deploy-ssh-gate`; the dedicated note-sx sudoers entry accepts only the argument-free helper route. Existing inhibit-wrapper and `systemctl restart` entries for tfl and fousekis-api remain. Per-repo secrets remain `VPS_HOST` / `VPS_USER` / `VPS_SSH_KEY`.

Residual authority: deployer retains broader legacy sudo and Docker-root-equivalent authority until the separate ticket 12/13 withdrawal. The no-argument deployment rule is route-level restriction, not effective containment.

## OS auto-updates

- `unattended-upgrades` installs updates from the base, security and ESM pockets with an automatic reboot at 03:30. The policy is `/etc/apt/apt.conf.d/51-vps-auto-updates`, versioned at `config/vps/apt/51-vps-auto-updates` in the dotfiles repo — edit it there, then install it by hand from `~/Dev/dotfiles`: `sudo install -m 644 config/vps/apt/51-vps-auto-updates /etc/apt/apt.conf.d/51-vps-auto-updates`. No deploy script installs it.
- `50unattended-upgrades` is the package's own file (shipped from `/usr/share/unattended-upgrades/`) and is not managed here. apt merges the origins from both files, so general updates still install if that one is ever replaced by an upgrade. Do not hand-edit it: that is what left a stray `.bak-*` file behind and made apt warn about an invalid filename extension.
- Kernels left over from reboots are reaped by `Remove-Unused-Kernel-Packages` during unattended runs; the weekly cleanup only runs `autoremove`.
- A reboot is cut short of an in-flight deploy by the `vps-deploy-inhibit` shutdown inhibit.

## Weekly upkeep (installed separately; timers are user units)

- `~/bin/vps-cleanup.sh` — Sunday 04:30: caps the Docker build cache at 3 GB (`--max-used-space`; the older `--keep-storage` is a *floor*, not a cap), removes images no container uses except the protected build bases (the Playwright image greek_embassy_bot builds from), clears runner/npm/apt caches and runs `apt-get autoremove`. It takes the same `~/.cache/vps-deploy.lock` as `vps-deploy.sh` so pruning cannot race a build, is `--dry-run`-able, is idempotent, and exits non-zero if a step failed. The journal cap is soft — active journal files are exempt. Log: `~/logs/vps-cleanup.log`.
- `~/bin/vps-update-images.sh` — Sunday 05:30: argument-free trampoline to the fixed note-sx root helper; the timer and schedule stay unchanged. Legacy `--locked` flock re-execs fail closed so an already-queued old caller cannot deadlock by asking the helper to reacquire its lock. While the temporary first-update hold is active, ordinary callers log a held event and return nonzero without selecting/pulling an image or touching the service. After root-console release, the helper resolves and pins the linux/amd64 digest behind upstream `latest`, pulls it before stopping the app, confirms no running container mounts its data, snapshots the stopped `db/` and `userfiles/`, validates the archive, then activates and health-checks the digest. It retains three new root-only snapshots in `/var/backups/note-sx`; existing `~/backups/note-sx` archives stay untouched. Archive readability is checked, but no live data restore has been proven; no automatic DB/upload restore is performed. Log: `~/logs/vps-update-images.log`.
- `herdr-server.service` — keeps the headless Herdr server running across reboots.
- Locally built images and the explicit `deploy.sh --nginx` / `deploy.sh --tls` admin actions are never touched by the weekly jobs. The default note-sx `deploy.sh` path only invokes the fixed root helper; it does not rsync the app tree or copy env files.
