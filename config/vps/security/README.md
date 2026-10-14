# VPS runtime security monitoring

Reviewed source for the opt-in VPS security plan. `deploy-vps.sh` and `link.sh`
do not install these jobs. Source modules are copied to
`~/ops/vps-security/libexec/`; no second dotfiles checkout is needed on the VPS.
Private configuration belongs at `~/.config/vps-security-scan/config.json`
(mode 0600), never in this repository.

## Coverage and alert meanings

- The Healthchecks wrapper sends empty-body POST `/start`, `/0`, and `/1`
  pings. Logs, reports, credentials and ping URLs are not uploaded. The original
  app and disk commands remain unchanged and continue sending their existing mail.
- The app check includes eight HTTPS/auth boundaries, recovery receipts and
  credential reminders. Its exit status indicates health.
- The disk heartbeat indicates **successful execution**, not disk health: the
  original disk monitor returns zero after successfully sending warning mail.
  Its threshold/recovery emails remain enabled. Below the 10 GiB operating
  target is not necessarily an existing disk-alert condition.
- The daily scanner inspects all running containers and their immutable Docker
  image IDs, scans IDs sequentially, validates Trivy schema/image identity, and
  rechecks the runtime inventory. Errors, missing containers and incomplete
  inventory verification are not clean scans. Findings are reported separately
  from scan execution health; a successful scan may contain vulnerabilities.
- Native applications are explicitly excluded from this daily image coverage;
  lockfile review and native dependency CI must cover them separately.
- Changed findings, scan errors/recovery, and missing/stale/failed scan
  heartbeats use the existing xbot email transport with delivery-aware dedup.
  An hourly watchdog returns failure while the scanner is unhealthy.

## Bounds

The scan service is sequential and uses a nonblocking shared `flock`, 50% CPU,
2 GiB memory, lowered scheduling priority, per-image timeouts, an overall 6600s
budget and a 2h systemd cap. Reports/state use private directories and atomic
writes; count, age and total storage are bounded while preserving the latest
valid report. No image is pulled by this scanner.

The example requires 10 GiB free. A deployment may set the approved **5 GiB
hard floor** for scanning already-local images when capacity is temporarily
below the target. This does not authorize image pulls, cleanup, data deletion,
or ignoring the 10 GiB operating target. A DB refresh can require temporary
space: inspect current capacity and keep the hard floor throughout maintenance.

## Installation (explicit operator action)

1. Run `python3 -m unittest discover -s config/vps/security/tests -v`.
2. Back up installed units/drop-ins and original monitor checksums privately.
3. Copy these four Python files to `~/ops/vps-security/libexec/` (directory0700,
   files0600). Keep the original `~/bin/vps-app-health.py` and
   `~/bin/vps-disk-alert.py` untouched.
4. Populate private configuration from `examples/config.json`. Set private
   hosted ping URLs for app/disk/scan/watchdog and enable Healthchecks. Account
   API credentials stay off-host; the VPS receives only scoped ping URLs.
5. Install the four scan/watchdog unit files and the two monitor drop-ins into
   `~/.config/systemd/user/`. Run `systemd-analyze --user verify` and reload.
   Confirm the original monitor timers remain enabled.
6. Enable/start the daily scan timer first. Explicitly start the scan service
   and inspect its private report and resource properties. Then enable the
   hourly watchdog. Run both original monitor services through their wrappers.
7. Configure hosted periods: app15m +5m grace; disk/watchdog1h +10m;
   scan24h +2h. Validate actual mailbox delivery for failure, recovery and an
   isolated missed heartbeat. A successful HTTP request is not email proof.
8. Retain every old email path until a full relevant production schedule cycle
   and the independent delivery proofs pass. There is no automatic retirement.

The daily timer is noon Europe/London with up to5m randomized delay, avoiding
current overnight backups. Refresh the live schedule before applying these
assets. Hosted free-tier capacity is20checks; existing checks must not be deleted
or repurposed to make room.

## Rollback

Stop/disable only the two new timers; stop a new scan only after inspecting its
state. Restore the backed-up app/disk drop-ins (or remove only the installed
`healthchecks.conf` when none existed), restore the four new unit files if they
previously existed, and daemon-reload. Confirm the original monitor timers and
mail still work. Pause only the corresponding new hosted checks if needed.
Keep evidence and private state for review. No SSH, firewall, existing backup
or app deployment settings are managed here.

## Validation limits

The unit suite mocks Docker, Trivy, systemd and email. Live systemd controls,
exact-image scans, mailbox receipt and a full schedule cycle require separate
operational evidence. Existing xbot code/environment is a runtime dependency
for all local mail; upgrades must preserve that transport.
