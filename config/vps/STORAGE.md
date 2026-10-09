# VPS disk upkeep

## Operating policy

Keep at least 10 GiB available on the root filesystem. The existing weekly
`vps-cleanup.timer` bounds Docker build cache, removes unused/unprotected images,
clears npm/runner/apt caches and limits journal storage. It never removes application
volumes, live datasets or agent histories. `vps-cleanup.sh --dry-run` previews actions.
Application-specific archival and retention are separate; a backup upload alone
never frees the original files.

## Disk alerts

Sources: `vps-disk-alert.py`, `systemd/vps-disk-alert.service` and
`systemd/vps-disk-alert.timer`. Installed copies: `~/bin/vps-disk-alert.py` and
`~/.config/systemd/user/vps-disk-alert.{service,timer}` on the VPS.

The hourly user timer sends email at 80% used, escalates at 90% used or less than
5 GiB available, reminds daily while unhealthy and sends one recovery notice.
Percent usage excludes reserved filesystem blocks, as `df` does. Alert recovery
means below these thresholds, not necessarily that the 10 GiB target is met.
No deletion is triggered by an alert.

Delivery reuses the live `~/Dev/xbot` Python environment and its existing email
transport/configuration. This is a dependency: moving xbot or removing its environment
requires updating this unit. Credentials are not copied into the disk monitor.
Successful send state is private at `~/.local/state/vps-disk-alert/state.json`;
failed delivery leaves that state unchanged so the next hourly run retries.

Checks:

```sh
python3 tests/test-vps-disk-alert.py  # from the dotfiles checkout
ssh vps 'systemctl --user list-timers vps-disk-alert.timer --no-pager'
ssh vps 'journalctl --user -u vps-disk-alert.service -n 20 --no-pager'
```

Manually starting `vps-disk-alert.service` runs a real check and can send email.
Installation/updates are explicit maintenance, not part of `deploy-vps.sh`.
Editing repo sources does not update installed copies. Validate units with
`systemd-analyze --user verify`, then reload the user manager after installation.

## 2026-10-09 archival

Recovery archives are under the existing VPS rclone remote:
`gdrive:vps-storage-archives/20261009/`. They contain VPS EuroLeague rehearsal
data/checkouts and Mac repeated proof runs/historical candidates, with file-hash
catalogs. Complete archive retrieval was SHA-256 verified before source removal.

Detailed manifests/retrieval evidence are private under
`~/ops/storage-review-20261009/` on the VPS and
`~/data/storage-review-20261009/` on the Mac. Live datasets, credentials and Docker
volumes were excluded. The Mac EuroLeague backup rotation is documented in
`el-machine/ops/el-machine/README.md` and its installed live-estate README.

Drive returned intermittent `403 rateLimitExceeded` for rclone's shared API project.
This was not a storage-capacity error. Do not delete originals on upload success
alone: retrieve and verify first. If shared-project limits become persistent,
configure a dedicated Drive OAuth client as a separately approved credential change.
