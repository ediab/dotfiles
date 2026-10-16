# VPS runtime security monitoring

Reviewed source for the opt-in VPS security plan. `deploy-vps.sh` and `link.sh`
do not install these jobs. Source modules are copied to
`~/ops/vps-security/libexec/`; no second dotfiles checkout is needed on the VPS.
Private configuration belongs at `~/.config/vps-security-scan/config.json`
(mode 0600), never in this repository.

## Protected system profile — source-only until migration acceptance

`systemd-system/` and the three `examples/*-system.json` files are the opt-in
replacement profile. They are **not installed by publishing this source**, and
must not be enabled by copying the units alone. A reviewed, receipt-bound
installer, preserved private configuration/state, filesystem ACLs, rollback and
real launch acceptance are prerequisites. The legacy user profile below remains
operational until the replacement is accepted; never run both timer sets.

- Root-owned code under `/usr/local/libexec/vps-security-scan` and exact private
  configs under `/etc/vps-security-scan` are required. Configs must be root-owned
  mode0640 with the appropriate role group, not unreadable root0600 or public0644.
  The containing directories and all imported code must be root-owned and
  non-writable by either role. Python uses `-E -s -B`; `-I` would hide local imports.
- Image scan uses `vps-image-scan`; native scan and both watchdogs use the distinct
  `vps-native-scan`. Neither account may have global Docker or `diab` membership.
  Only the image scan **unit** receives Docker supplementary membership. This
  scanner still has root-equivalent Docker capability while executing; it is not
  a Docker isolation boundary. Protect every transitive executable/import input.
- Separate private state lives under `/var/lib/vps-security-scan/{image,native}`.
  Both jobs lock the existing root-owned0660 `/run/vps-security-scan/scan.lock`;
  they must not create/chmod it as a scan user. The Trivy database is image-owned
  at `/var/cache/vps-security-scan/trivy`, with native read-only ACLs only on the
  database files and required traversals. Image updates refresh those ACLs.
  Native filesystem scanning uses the memory cache and `--skip-db-update`.
  A bounded real native scan against this read-only cache is mandatory before
  enabling its timer. The existing1.5GiB DB must move on the same filesystem into
  an absent destination, not be duplicated; migration/ACL preimages need receipts.
- Native access must be restricted to active venvs, manifests and traversal.
  Three live app roots otherwise deny the new UID. Do not add the broad `diab`
  group, recursively grant app-root access, inherit default ACLs, or expose app
  `.env`/data/database directories. Future release hooks must renew narrow ACLs.
- A root socket-activated fixed read-only broker exposes sanitized scan/unit
  metadata and one Houses user-unit binding query. It does not expose a general
  sudo command, Docker API, arbitrary path/argv or the user's D-Bus. The Houses
  query drops UID/groups before executing its fixed systemctl command. Clients
  check root peer identity, the socket/ancestors, schema and freshness. Raw
  findings, requests, secret configuration and command output are not returned.
- Both mail senders validate the complete accessible root-owned transport tree,
  including transitive modules/bytecode, before importing it. Runtime read ACLs
  are still required; ownership validation does not grant access.
- The system units use filesystem protection, NoNewPrivileges, restricted
  capabilities/address families and resource bounds. Unlike the legacy user
  units, the new prototype does **not** yet use a SystemCallFilter. Do not infer
  syscall confinement or successful live launch from a passing mocked unit test.
- Keep the existing Healthchecks identities, calendar schedules and notification
  state. Never fabricate LastTrigger or a scheduled success using a manual scan.
  Local recovery stays quiet; broker outages are deduplicated problem alerts.

The accepted capacity outcome is roughly7GiB free with a **5GiB hard floor**.
The previous10GiB aspiration does not authorize protected-data deletion or paid
expansion. Existing app/disk alerting and recovery retention stay in force.

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
- Native applications are excluded from daily image coverage and checked by the
  separate weekly native scan described below.
- New/changed findings, scan errors, and missing/stale/failed scan heartbeats
  use the existing xbot email transport with delivery-aware dedup. Local scanner
  and watchdog recoveries, including all findings clearing, advance notification
  state quietly without email. A successful scan that still has findings after an
  error is a problem notification, **not** a quiet recovery. Failed problem-email
  delivery must not advance notification state. An hourly watchdog returns failure
  while the scanner is unhealthy. Original app/disk mail and independent hosted
  Healthchecks notifications are unchanged.

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

## Native dependency monitoring


The native scan is a separate, opt-in job that never runs package managers,
never executes application or installer scripts, never reads app `.env` files
and never pulls images. It writes `artifact_type: filesystem` reports under
`native-scan-*.json`, distinct from image reports, and shares the same
`state_dir/scan.lock` as the image scanner.

Fixed targets (configuration cannot add arbitrary paths):

| Application | Active runtime | Coverage claim |
|---|---|---|
| TFL | `/var/lib/tfl/current` under `/var/lib/tfl/releases` | verifies `tfl.service` `WorkingDirectory`/`User`/npm argv, inventories installed `node_modules` name/version and binds them to the release `package-lock.json` |
| xbot | `/home/diab/Dev/xbot/.venv` | installed metadata against hash-pinned `requirements.lock` |
| morning-brief | `/home/diab/apps/morning-brief/.venv` | installed metadata against `requirements-lock.txt` |
| el-machine | `/home/diab/apps/el-machine/.venv` | installed metadata against `uv.lock` (legitimate uv cache hardlinks allowed) |
| houses | `/home/diab/apps/houses/pipeline/.venv` | verifies `houses-health.service` (user unit) working directory, installed metadata against `uv.lock` |

Inputs are sanitized to package name/version only; `direct_url`, source paths,
package bodies and environment files never enter the scratch manifest or report.
Trivy runs `fs --scanners vuln --list-all-pkgs --offline-scan --skip-db-update`,
and a report is accepted only when the exact artifact path, ecosystem and full
package set match the inventory. A partial or failed run is an error, never
"clean", and never advances the previous finding baseline or claims RESOLVED.

Ownership/writability policy for installed metadata: files and directories must
be world-write free. Group-write is permitted only when nobody outside the file
owner, root and the scanner user is in the owning group, considering both the
primary group (via passwd) and explicit supplementary members (via group); a
shared-group or foreign-owner entry is refused, and `package-metadata-owner-unsupported`
is reported explicitly with the inventory failure detail. Ancestor checks are
bounded to the application root, and the scanner never chmods or modifies a live
file. TFL's generated `node_modules/.package-lock.json` regular file is the only
hidden npm entry skipped; symlinks or unknown hidden entries still refuse.
Default targets resolve authoritative metadata owners from `xbot-app`,
`morning-brief-app` and `el-machine-app`. xbot and el-machine additionally verify
system-unit working directory, user, executable and complete argv, like TFL;
checking an npm executable substring is insufficient for Python units. Missing
owner accounts do not allow arbitrary foreign metadata owners. Group/world-write
and path-containment refusal checks remain unchanged.

Housekeeping: a 5 GiB hard floor, per-target and overall timeouts, 25% CPU and
1 GiB memory in the unit, sequential execution, private reports (24 files /
45 days / 256 MiB) and a 24-hour scratch sweep. Problem changes are emailed through the
root-owned xbot transport snapshot at `/usr/local/lib/vps-monitor-transport`
with delivery-aware dedup; local recoveries remain quiet. Native Healthchecks URLs are
separate from app/disk/image URLs and disabled until separately provisioned.

The user units use NoNewPrivileges, syscall restrictions and resource bounds.
They do not claim filesystem or account isolation: this host disables the
unprivileged user namespaces needed by systemd filesystem/device sandboxes.
The live launch test must pass before timers are enabled.

### Native installation (explicit operator action)

1. Copy `native_scanner.py`, `native_watchdog.py` and
   `native_healthcheck_wrapper.py` beside the existing `core.py` in
   `~/ops/vps-security/libexec/` (do not replace existing files).
2. Copy `examples/native.json` to
   `~/.config/vps-security-scan/native.json` with mode 0600. Healthchecks stays
   disabled pending parent account setup.
3. Copy the four `systemd/vps-native-scan*.{service,timer}` files to
   `~/.config/systemd/user/`, run `systemd-analyze --user verify`, and confirm
   the existing app/disk/image timers stay enabled.
4. Start the weekly scan once by hand, inspect its private report and resource
   properties, then enable the hourly native watchdog. Keep image and native
   scans sharing the nonblocking lock.

### Native rollback

Disable only `vps-native-scan.timer` and `vps-native-scan-watchdog.timer`, remove
only the four new units and the three native modules/config if approved, then
daemon-reload. Preserve native reports and notification state. Existing
app-health, disk, image-scan and credential-reminder timers and the xbot email
transport stay untouched.

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

The retained tests cover privilege, filesystem and credential boundaries using
temporary fixtures and mocked system calls. General scanner, alert and heartbeat
integration suites are not retained. Live systemd controls, exact-image scans,
mailbox receipt and a full schedule cycle require separate operational evidence. The protected root-owned xbot transport snapshot and its private environment
are runtime dependencies for local mail; upgrades must preserve that transport.
