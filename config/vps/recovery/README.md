# VPS off-host recovery retention (rolling seven days)

Reviewed **source-only** successor for the root retention job. `deploy-vps.sh`
and `link.sh` do not install this. No activation, grant or production change is
implied by publication; parent owns every privileged, live mutation.

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
operator's exact reviewed source hash (and optionally an unprivileged clean
committed Git diagnostic). Its historical adoption pin accepts only the frozen
baseline or the requested revision: it deliberately refuses the newer live
revision until the installation gate below is reconciled.

This successor incorporates the separately captured seven-family live program,
including Houses daily typed proofs, root morning receipts, recursive listing
counts and system-timer observation. Its exact source hash and captured live
hash are recorded in `provenance/reviewed-source.json`.

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
  ≥ 1. Houses daily additionally requires its typed conditional-create,
  independent-download, hash, table/sequence and cleanup proofs, a bounded
  unique file manifest containing `manifest.json` and `notebook.dump`, and an
  exact recursive remote listing count. The same precise identity is re-checked
  after cleanup.
* **Separate note-sx identities.** A receipt filename must match its local
  `capture_id`. Its verified `remote_prefix` names the remote recovery point;
  the producer assigns these IDs independently. Age and protection use the
  remote point's timestamp.
* **Local space policy unchanged.** Only `note-sx` capture duplicates under
  `/var/backups/note-sx/current-coolify-captures` and `houses` points under
  `/home/diab/ops/r2-recovery/points/houses` are removed locally, and only when
  they are at or older than the newest verified point. No seven local snapshots
  are retained.
* **Cleanup containment.** Every cleanup path component is opened relative to
  a retained directory descriptor with `O_NOFOLLOW`, starting at a trusted
  root-owned anchor. A missing root is a no-op. Recursive deletion is bounded
  to depth 64 and 200,000 entries; symlinks cannot redirect it outside the
  opened tree. Lock/status writes similarly bind their actual directory and
  file identities. These are component safeguards, not whole-service acceptance.
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

## Deployment gates (parent-owned; not activation instructions)

1. Publish and verify clean committed source unprivileged. Root must never run
   Git in an operator-writable checkout: filters and fsmonitor can execute code.
2. Reconcile the installer's historical frozen adoption pin with the freshly
   observed live revision, backed by the exact captured bytes and rollback
   receipt. Do not bypass its unknown-live refusal or use test-only overrides.
3. Stage fresh hash-verified copies under root-owned, non-writable ancestors;
   do not execute these installers directly from a user-writable checkout.
4. Complete transitive interpreter/helper/config, shared-mutex and receipt-path
   trust review and exact rollback/preimage acceptance. The legacy mutex under
   `~/ops` remains an integration gate, not a claimed root trust boundary.
5. Preserve the actually installed system timer/calendar and its observations;
   the historical user-unit templates below are not a migration recipe.
6. Require genuine recovery and failure-path/runtime acceptance before any
   activation or privilege removal. This publication meets none of those live
   gates by itself.

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
end-to-end seven-family plan/apply, malformed Houses daily proof refusal,
shipped-artifact callback/undefined-global checks, descriptor-bound cleanup, and installer guards (tampered source,
symlink/dangling live, unknown live content, rollback drift/tamper, test-path
isolation, quiescence, Git lineage, read-once rclone payload, ownership).
Tests use no rclone, no sudo and no VPS.

## Open decisions for parent

* Confirm the live retention sha256 before adoption.
* Recheck the actual system timer and root morning receipt paths against the
  captured live program before any activation.
* Approve the first exact dry-run manifest.
