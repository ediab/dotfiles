# VPS service reference

Cached service-specific details and removal history, moved from `SKILL.md`; not a live inventory. Before acting, verify the relevant claims against `~/README.md`, `~/ops/`, and the live service configuration on the VPS. These details do not authorize deployment, restart, migration, or deletion.

## Service locations and restart steps

- Production mp3podcasts lives in `~/apps/mp3podcasts`.
- mp3podcasts and redact_pdf: `docker compose up -d --build` in their `~/apps` directory.
- note-sx: `docker compose pull && docker compose up -d` (image-based), plus the nginx section of its `deploy.sh`.
- onyx: `docker compose up -d --build`. Its `scripts/sync_to_vps.sh` is legacy rsync; follow the Git-based synchronization rules in `SKILL.md` for tracked code.
- The live Fousekis API remains in `~/apps/fousekis/api/`: `sudo systemctl restart fousekis-api` (plain node, no build).
- Third-party image bundles such as karakeep generally have no git workflow.

Restart commands alone are not proof of live-service health; verify the requested behaviour after deployment.

## Removed paths and services

- The obsolete VPS `~/dev/pi-dotfiles` checkout and empty lowercase `~/dev` directory were removed. The active configuration source is `~/Dev/dotfiles`.
- The legacy VPS `~/Dev/mp3podcasts` workspace and its recovery archive were permanently removed with approval.
- GoatCounter and the old `~/apps/fousekis-api` transcription environment were removed; the live Fousekis API is distinct from that retired environment.
