---
name: vps-publishing
description: Deploy or recover apps using Coolify Cloud, GitHub Actions/GHCR and encrypted Cloudflare R2; review app data collection or schedules when adopting these tools; retire an old deployment or backup path after verified replacement.
---

# VPS publishing and recovery

Use this guide for the shared publishing/recovery tools. It records measured boundaries, not permission for a live mutation. Read `local-env` for host access and paths; follow the current project plan for authority and privacy scope.

## Choose the smallest useful change

For the assigned app, identify its current deployment owner, data producers, persistent state, recovery copies and consumers. Retain its runtime when changing deployment/recovery controls gives the benefit: native jobs need not become containers; a Vercel app need not move to Coolify; a dormant app need not restart.

**Done:** name what the new tools replace, what stays, the expected reduction in work/risk, and the behavior the replacement must preserve. Existing preparation is a candidate, not an accepted live implementation.

## Tool boundaries

| Tool | Owns | Does not establish |
|---|---|---|
| GitHub Actions | Checks, hosted build, exact release provenance, gated deployment job and completion outcome | That a deployment is healthy merely because a build passed |
| Private GHCR | Immutable image artifact selected by digest | Repository privacy from a 403/404, running-image identity from a tag |
| Coolify Cloud | Pull/start a prebuilt app on the configured host | Public TLS/auth ingress, application recovery, or final release success from `finished` |
| nginx | Existing public TLS, routing, authentication and denial rules | Which image actually serves an upstream without runtime/marker evidence |
| R2 + rclone crypt | Encrypted off-host recovery objects | A consistent source snapshot, a complete recovery point, or a successful app restore |
| Native timer/cron | Data producers and tightly coupled scheduled jobs retained where appropriate | Fresh inputs, successful work or delivery merely from exit 0 |

## Release sequence

1. Refresh real app/host state and applicable deploy triggers. Use an isolated source workspace when the normal checkout is dirty. Identify exactly one release authority.
2. Run caller-owned checks, build on hosted CI, prove positive private package identity, then record the buildx digest and full source/run/attempt marker. Use the recorded artifact, not later tag inspection.
3. Create the Coolify candidate without auto-deploy/domain generation, using an explicit loopback mapping on a checked-free port. Read configuration back before starting. nginx retains 80/443; Coolify uses proxy `None`. Use prebuilt images, not VPS builds.
4. Capture actual container→local image→registry digest identity and both configured/actual published bindings. Wait for startup health within a deadline. Two matching ready captures must bracket actual route checks; verify meaningful app behavior/data as well as the exact marker.
5. In an approved window, change only the app route, preserve TLS/auth/denial behavior, check nginx syntax and reload. Keep a scoped config backup and a tested restoration command. Stateful cutovers additionally quiesce the old writer before opening the new writer.
6. Prove rollback without overwriting newer data, restore the intended serving release, then run the actual hosted release path. Enable automatic releases only after its runtime/public verdict passes. Disable the old deployment writer; retain its recovery artifacts through observation.

**Done:** the exact checked artifact serves the real route, expected access rules/data behavior pass, rollback works, and the hosted job outcome follows the final verifier—not Coolify's status alone. Completion-email routing can be proven separately from receipt of a particular message; a structured log is not inbox acknowledgment.

## Coolify pitfalls verified in 4.4.6

Recheck the installed version and relevant source/API on upgrade; these are measured behaviors, not timeless API guarantees.

- **Loopback API/UI mismatch:** v4.4.6 `bootstrap/helpers/api.php` accepts only numeric port pairs. The UI's `portMappingRules()` accepts an IP-qualified mapping. Use the authenticated UI to save the explicit loopback mapping, then verify its API readback and runtime bindings. A public numeric-only mapping or a relaxed verifier is not an equivalent workaround. The owner prefers agent-owned UI changes; request sign-in when needed.
- **Registry config belongs to the SSH user:** `ApplicationDeploymentJob::prepare_builder_image` discovers that user's `$HOME/.docker/config.json` and mounts it read-only into the helper at `/root/.docker/config.json`. Logging in only to host root's config did not authorize the non-root user's helper. Use the existing read:packages credential, secure stdin and an explicit Docker config location. Prove the actual helper can pull the private digest, not only host root.
- **`finished` can precede health readiness:** the website's first hosted release saw `starting` then `healthy`. The shared CLI now waits only for startup health within its existing deadline before taking the final stable pair. Unhealthy, ambiguous, changed-identity, digest/port or deadline failures remain refusals.
- **No verified cleanup-off switch:** high threshold plus infrequent/non-forced cleanup reduces exposure; it does not disable cleanup, including unknown-usage paths. Disable unused volume/network deletion, keep app retention enabled, and verify protection for current/previous images. A stopped container can hold image bytes; removal of an extra alias can still lose that alias/digest reference. Retain independent recovery identity, not just a plausible tag.
- **Onboarding is not side-effect-free:** validation/background checks may create a Docker network, start helper/Sentinel containers and fetch apt metadata. Read back proxy, key, cleanup and collection settings before authorizing access. Compare unrelated services/listeners/start times and actual free bytes after operations.
- **Deploy-only role may need a separate build server:** the account rejected it without one. Enforce prebuilt-only deployment rather than inventing a role flag or building on the shared VPS.

Token roles stay separate: setup/configuration Read+Write, Deploy-only start, dedicated GHCR read:packages for host pulls, ephemeral GITHUB_TOKEN for repository metadata/build publishing. A package-read token is not private-repository access. Keep mailbox credentials in their existing native app; the chosen release channel is GitHub completion email.

## Restricted verifier

Use the checked-in reporter/comparator/SSH transport rather than making a new generic remote shell. Its dedicated identity has a forced allow-listed read-only command, one exact sudo grant, pinned host trust and no Docker-group or arbitrary-sudo access.

Install code/config under trusted root-owned paths. sshd reads public authorized_keys as the service user: root-owned files/directories must be readable by it while remaining non-writable. A root-owned 700 directory/600 public-key file caused real authentication failure; readable 755/644 corrected it without granting writes. Exercise the actual forced SSH command and negative controls, not merely `visudo` or a mock.

## Recovery sequence

1. Define the recovery unit: database plus uploads/config/secrets/dependency closure where needed. Inventory backup freshness and restore evidence separately from timer status.
2. Produce a consistent snapshot using the app's supported method. Give one producer a lock; capture exact files/bytes/hashes and provenance. Quiesce only under the app's approved plan.
3. Use the dedicated rclone client/config, unique destination and verified conditional-create path. Transfer a manifest with the recovery objects. Namespace organization is not an access boundary.
4. Independently download/decrypt required objects into a fresh isolated destination; require their presence and full byte/hash agreement. Restore the actual app/database there, suppress unintended mail/posting/collection, and exercise agreed behavior/access/data invariants.
5. Only after those checks write the completion receipt and enable the backup schedule. Prove failure/staleness notification and an affected schedule cycle. Retention/deletion is a later decision with exact preview and approval.

**Done:** retrieved production recovery bytes restore a usable isolated app with measured freshness/time and the required source closure. A synthetic transport exercise or historical archive does not establish current whole-app recovery.

### R2/rclone pitfalls verified with 1.75.2

- Use the dedicated absolute client and explicit `--config`; existing system rclone/remotes remain unchanged. The old 1.60.1 client committed multipart data then failed a version-specific HEAD.
- `copyto --immutable` overwrote in measurement. The verified create-only path uses `--header-upload 'If-None-Match: *'` on a unique destination; a pre-list check is advisory, not atomic. Retain locking and fail closed for unmeasured client behavior.
- Copying a missing remote prefix can exit 0 with no files. Assert the manifest and required recovered bytes; exit status, size or ETag alone is not recovery proof.
- Crypt protects content and filenames; key material must be recoverable independently of both VPS and bucket. Obscured rclone credentials are still secrets: consume configs programmatically, without printing them, copying them to prompts/images or putting values in argv/Git.
- Incomplete multipart abortion is different from completed-object deletion. Object credentials do not necessarily expose bucket lifecycle/public settings; use dashboard/account evidence rather than inferring policy from object API errors. A location hint is not a residency guarantee.

## Capacity and retirement

Measure peak simultaneous allocation: helper/Sentinel, pulled/unpacked image, candidate, retained rollback, snapshot, downloaded restore and temporary workspace. Docker Size, compressed transfer bytes and filesystem usage are different measurements. Refresh `df` at the affected filesystem; bounded pilots retain at least 5 GiB, broader rollout targets 10 GiB or an explicitly approved alternative. One heavy restore/build lane; no emergency pruning to meet a budget.

Retire redundant writers at cutover, not before recovery readiness. Keep redundant recovery for at least 7 days and a full successful affected schedule cycle, whichever is longer. Then propose exact obsolete files/triggers/helpers/objects, dependencies, byte savings and retained rollback before approved removal. Source, immutable evidence, Drive originals and the last good copy remain protected.

## Evidence and refresh

Verified 2026-10-12 against Coolify 4.4.6 and real hosted website release, R2/rclone 1.75.2 conditional-write/readback tests. The app's checked-in release scripts and current project PROGRESS/evidence outrank old preparation reports. Refresh version, capacity, expiry and runtime state before live operations. Keep credential values, private note contents and raw sensitive app logs out of this guide and worker prompts.
