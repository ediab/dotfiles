# VPS off-host recovery retention (rolling seven days)

Reviewed source for the root retention job. `deploy-vps.sh` and `link.sh` do
not install this. Parent owns every privileged, live mutation.

## Canonical authority

No versioned source for the deployed retention script exists in `ediab/dotfiles`
at `788b00d` or `9d7f5ac`. The live program is adopted here as a **frozen
baseline**:

* `baseline/lean-recovery-retention.frozen.py` — exact audited capture, sha256
  `dbcada01236b45c97faec60d0348f953520ebec23bf70a3a1f7d3439d56385ef`,
  9969 bytes (matches live size and mode `0755 root:root`).
* `provenance/frozen-baseline.json`, `provenance/rclone-1.75.2.json`,
  `provenance/reviewed-source.json`.

`recovery_retention.py` is the reviewed successor. The installer requires the
operator's exact reviewed source hash (and optionally a clean committed Git
blob) and refuses any live file that is neither the pinned baseline nor that
revision.

## Policy

* **Rolling seven days.** A verified point is kept while its age is at most
  `7 * 86400` seconds. The boundary is deterministic: a point exactly seven days
  old is kept; one second older is eligible for deletion.
* **Newest verified point is always kept**, however old it is.
* **Strict ordering only.** A point is never deleted unless it is *strictly*
  older than the newest verified point. Equal timestamps and fractional-second
  ties are kept (`not-strictly-older-than-newest-verified`).
* **Only positively verified points may be deleted.** A point is verified when a
  passing receipt names its exact remote namespace child. Points with no passing
  receipt are preserved (`no-passing-receipt`).
* **Mandatory proof, no silent skip.** Each family's newest receipt must pass its
  full proof; a missing mandatory proof refuses the whole run instead of
  silently preserving everything and reporting success.
* **Never delete newer/in-progress/ambiguous data.** Unparsable names, nested
  paths, future timestamps and points newer than the newest verified point are
  preserved.
* **Validation before mutation.** Immediately before the first delete the plan is
  recomputed, protected points are re-bound with their exact receipt-bound set
  shape, and every candidate is re-validated (still verified, strictly older
  than protected, strictly outside the window). Any protected-point, policy or
  proof drift refuses before a single delete is issued. The delete commands
  themselves are irreversible once issued; correctness rests on pre-mutation
  validation, not on atomicity.
* **Receipt-bound set shape.** `note-sx` and the app state points must list
  exactly `readback_file_count` / `object_count` objects with integer sizes;
  `morning-brief` state/config use `rclone size` and require count and bytes
  ≥ 1. The same precise identity is re-checked after cleanup.
* **Separate note-sx identities.** A receipt filename must match its local
  `capture_id`. Its verified `remote_prefix` names the remote recovery point;
  the producer assigns these IDs independently. Age and protection use the
  remote point's timestamp.
* **Local space policy unchanged.** Only `note-sx` capture duplicates under
  `/var/backups/note-sx/current-coolify-captures` and `houses` points under
  `/home/diab/ops/r2-recovery/points/houses` are removed locally, and only when
  they are at or older than the newest verified point. No seven local snapshots
  are retained.
* Timestamps come from the point's own `YYYYMMDDThhmmss[frac]Z[-.]` identity,
  parsed strictly (`strptime`), never from mtime or lexicographic ordering.
* Root-only invocation, `RCLONE_*` environment refusal, pinned rclone client
  version, `~/ops/r2-rollout-live.lock` exclusion and private manifests are kept.
* The frozen `--retire-legacy` capability is **not** carried into the new
  policy; no legacy purge exists here.

## Trusted inputs

* `rclone`: `/usr/local/libexec/vps-recovery/bin/rclone`, root-owned, pinned to
  the official v1.75.2 linux-amd64 build by sha256. Installed by
  `install_rclone_trusted.py`.
* config: `/etc/vps-recovery/rclone.conf`, a **root-owned private snapshot**.
  The retention job validates that both files are root-owned regular files
  under root-owned, non-group/world-writable ancestors before every run.
  The parent alone copies the credentials securely from the existing
  `~/.config/vps-backups/rclone.conf`; this worker never reads them. Other
  backup/recovery jobs keep using the existing diab-owned config unchanged
  pending the wider privilege migration.

## Dry-run manifest

Every invocation writes a private (mode 0600, root-owned) manifest under
`/var/lib/vps-recovery/manifests/` and prints only its path, sha256 and counts.
The manifest, schema `vps-recovery-retention-manifest/v1`, records each family's
`protected` point (name, timestamp, shape, expected count) and every remote
point's `name`, `timestamp`, `verified`, `newest_verified`, `decision`
(`keep`/`delete`) and machine-readable `reason`.

No per-run human approval is required for the steady scheduled policy. The
parent reviews the first exact dry-run manifest, then the timer runs plain
`--apply`. For extra safety an operator may pass `--manifest <reviewed>.json`;
`--apply` then refuses unless the freshly recomputed delete set equals it.

## Deployment (parent-owned, ordered)

1. Confirm the live sha256 as root:
   `sha256sum /usr/local/libexec/vps-recovery/lean-recovery-retention.py` and
   compare with `provenance/frozen-baseline.json`.
2. Create the root-owned config snapshot securely (parent only), e.g.
   `/etc/vps-recovery` mode 0755 root:root and
   `/etc/vps-recovery/rclone.conf` mode 0600 root:root.
3. Trusted dependency (no network, no download):
   `python3 config/vps/recovery/install_rclone_trusted.py --artifact /home/diab/.config/vps-backups/bin/rclone`
   for the dry verification, then `--apply --operator-quiesced` as root. The
   artifact bytes are read once with `O_NOFOLLOW`, hashed and installed; the
   installed target is re-hashed before `rclone version` runs.
4. Code adoption:
   `sudo python3 config/vps/recovery/install_recovery_retention.py --expected-source-sha256 <reviewed> --verify-only`
   then `--apply --operator-quiesced` (add `--source-repo /path/to/dotfiles` to
   require a clean committed Git blob). The installer validates trusted
   ancestors, refuses symlinks/dangling links, backs up the current live file
   under `/var/backups/vps-recovery/`, writes atomically and re-hashes.
5. Units are user units: copy `systemd/lean-recovery-retention.{service,timer}`
   to `~/.config/systemd/user/`, `systemctl --user daemon-reload`, run a
   dry-run manifest, then enable the timer.

## Rollback

* Code: `--rollback` reads the recorded `last-backup.json` receipt, verifies the
  backup hash, refuses when the live file drifted from `replaced_with_sha256`,
  then restores atomically.
* Dependency: restore `/var/backups/vps-recovery/rclone/rclone.*` over the
  trusted path and re-check `sha256sum` and `rclone version`.
* Units: disable `lean-recovery-retention.timer`, restore previous unit files
  and `systemctl --user daemon-reload`. The frozen script continues to read the
  original `diab`-owned rclone binary/config, which are left in place.

## Tests

```sh
python3.12 -m unittest discover -s config/vps/recovery/tests -v
```

Covers: seven-day boundary, protected old latest, timestamp/fraction ties,
malformed names, failed/new/in-progress and unverified points, mixed
timestamps, missing mandatory proof, no premature deletes, protected-point
drift with zero purge, candidate revalidation, receipt-bound set shape, an
end-to-end six-family plan/apply, and installer guards (tampered source,
symlink/dangling live, unknown live content, rollback drift/tamper, test-path
isolation, quiescence, Git lineage, read-once rclone payload, ownership).
Tests use no rclone, no sudo and no VPS.

## Open decisions for parent

* Confirm the live retention sha256 before adoption.
* Confirm the morning linked-receipt `verified` key (observed read-only on
  2026-10-14; subreceipts carry `verified`/`stamp`/`completed`).
* Approve the first exact dry-run manifest.
