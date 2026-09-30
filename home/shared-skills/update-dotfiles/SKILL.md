---
name: update-dotfiles
description: Explicitly save live settings into the dotfiles repo or apply repo configuration locally.
disable-model-invocation: true
---

# Update dotfiles

Run only when explicitly invoked. Treat dotfiles as configuration: software management,
Git publication, and VPS deployment are separate requests.

## Procedure

1. **Inspect.** Work in `~/Dev/dotfiles`. Read its README and relevant scripts; use
   `local-env` for machine-specific paths. Inspect staged and unstaged changes. Compare
   the selected repo/live files and preserve unrelated work before choosing a direction.
2. **Scope.** Follow the requested action and preferences:
   - **Save:** live → repo, for preferences changed inside an application.
   - **Apply:** repo → local machine, for configuration edited in the repo.
   - Ordinary symlinked dotfiles are already live; edit their repo sources and keep links.
   Ask if direction is unclear. If both sides contain independent edits, show the conflict
   and resolve it before overwriting. A bare invocation means inspect, not apply everything.
3. **Check side effects.** Inspect commands before execution. On macOS, verify retired
   `com.diab.dotfiles.capture` and `com.diab.sync-vps` jobs have not been reinstalled/loaded.
   If unexpected auto-push/deployment remains active, stop before writes and ask permission
   to pause it. Report inability to check rather than assuming jobs are inactive.
4. **Save or apply only the agreed scope.**
   - **Save:** validate live settings, then edit only approved portable preferences into
     their repo source. Preserve repo-only/unselected keys. Strip runtime `deviceId`,
     `lastChangelogVersion`, host-specific paths/proxy, and machine-only package declarations;
     include portable package declarations only when explicitly selected. Skip missing live
     files rather than emptying defaults. Refresh inventories only when requested. Keep
     auth, API keys, `.env`, MCP configuration, sessions/caches, and runtime stores out of Git;
     show changed key names, not secret values. Review the intended key changes before editing.
   - **Apply:** use `./apply.sh --file <relative-source>` or explicit `--group` selections.
     Preview first, then repeat the reviewed scope with `--yes`. Settings preserve machine
     fields and live packages by default; `--include-packages` needs separate approval because
     Pi may install the declared packages at startup. Use named files for JSON, profiles,
     extensions, or themes instead of applying unrelated pending changes.
   - Managed skills/generated instructions use `--group agent-content`, which delegates to
     `sync-agent-content.sh` and prints its **whole** plan. Stop if the request does not cover
     that plan. Missing adoption, collisions, or instruction drift need user resolution;
     preserve ownership safeguards and machine overlays. First-time adoption/forced drift
     replacement is separate permission, not implied by an ordinary apply.
5. **Verify.** Validate changed settings and run relevant repo checks. For saves, confirm
   the selected preferences in the repo and review the final diff. For applies, compare
   the selected destinations/effective settings, accounting for preserved machine fields,
   and confirm unselected files remain untouched. Report changed files, backups, checks,
   and anything unapplied. Commit, push, and remote deployment only on a separate request.
