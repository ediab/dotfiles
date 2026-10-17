# BB setup and portable preferences

This folder records how to install/update BB and restore selected preferences. It is **not** a copy of `~/.bb`, and nothing here is automatically applied by `link.sh`.

## Files

- `install.sh`: explicitly install the latest stable npm runtime, or a specified stable version.
- `AGENTS.md`: portable BB user instructions, copied explicitly into the server's data directory.
- `preferences.json`: last captured portable preferences from the active server.
- `snapshot.py`: refresh that file using an allowlist of general, appearance, and sidebar settings.
- `apply.py`: preview or explicitly restore those preferences to a chosen server.
- `plugins.json`: manually maintained plugin inventory with observed versions, sources, and monorepo subdirectories. It is documentation, not an automatic installer.
- `common.py`: shared preference allowlists and CLI calls.
- `skills/`: canonical BB user skills, including `pstack-bb` for pstack delegation.

Requirements: Python 3.11+ for the repository's Python checks (commands below use `python3.11` explicitly), Node.js supported by BB (0.45.0 supports Node 22.19+, 24, or 26), npm, and a working `bb` CLI for snapshot/restore. The runtime install needs network access and runs the native dependency build scripts for `better-sqlite3`, `node-pty`, and `@parcel/watcher`.

## Install or update the npm runtime

```sh
bash bb/install.sh             # resolve the latest stable npm release now
bash bb/install.sh 0.45.0      # install a specific stable release
```

The default location is `~/apps/bb-runtime`; override with `BB_RUNTIME_DIR`. Runtime packages and lockfiles stay there, **outside this repo**. The script does not start/stop services, create enrollment credentials, update the desktop app, or change `~/.bb`.

The VPS's `~/apps/bb-runtime` and `bb.service` are legacy. **Keep `bb.service` disabled and inactive**: starting it would compete with the active server for its port. Do not use this install script to update the active server.

The active VPS server uses `~/.bb-machines/diab.getbb.app` and the user unit
`bb-host-daemon-diab-getbb-app-host_23vgpbtjh7.service`. Inspect it with:

```sh
systemctl --user status bb-host-daemon-diab-getbb-app-host_23vgpbtjh7.service
bb status
bb machine list --json
```

Use BB's supported update mechanism for the active installation. Check a real task after updating; an active service alone is not proof an agent works. The Mac desktop app is a separate installation: update it through its supported app update mechanism, not this npm script. This folder schedules no automatic updates.

## BB user instructions

`bb/AGENTS.md` is the canonical copy of the BB-only preferences in `<dataDir>/AGENTS.md`
(default `~/.bb/AGENTS.md`). It sets question-tool routing and the BB memory boundary;
the shared `agents/AGENTS.md` remains the cross-client policy.

Run the following commands in `~/Dev/dotfiles` on the active server's machine.
For `diab.getbb.app`, that machine is the VPS and its data directory is
`~/.bb-machines/diab.getbb.app`, not the Mac's `~/.bb`. Use `bb status` to confirm
the target. For another server, replace `bb_data_dir` with its actual data directory.
Compare and merge any live differences before restoring:

```sh
bb_data_dir="$HOME/.bb-machines/diab.getbb.app"
diff -u "$bb_data_dir/AGENTS.md" bb/AGENTS.md
mkdir -p "$bb_data_dir"
cp bb/AGENTS.md "$bb_data_dir/AGENTS.md"
```

For an intentional live edit, review the reverse diff and copy it back to the repo.
Use fresh provider sessions after restoring. `link.sh` and `apply.py` do not copy this
file; server preferences and agent instructions are separate restore steps.

## BB skills in user scope

BB user skills live in `<dataDir>/skills/` on the active server. BB distributes
runtime copies to execution machines, including the Mac. Do not edit generated
`~/.bb/runtime/global-skills/` copies. These skills are separate from native
skills in `agents/` and from plugin skills.

`bb/skills/` is the canonical copy of `ui-audit` and `pstack-bb`. `diff-review`
lives in `agents/skills/` and is linked normally as a shared personal skill. Edit
this repo, sync it to the VPS through Git, then restore the intended BB skills
into the server's data directory. These are plain copies, not links;
`link.sh` and `apply.py` do not install them.

Run from `~/Dev/dotfiles` on the VPS after reviewing any differences:

```sh
bb_data_dir="$HOME/.bb-machines/diab.getbb.app"
diff -ru bb/skills "$bb_data_dir/skills"

# Restore only the skill you intend to change:
mkdir -p "$bb_data_dir/skills/pstack-bb"
cp bb/skills/pstack-bb/SKILL.md "$bb_data_dir/skills/pstack-bb/SKILL.md"

# Confirm discovery, then start a fresh provider session:
bb skill list --json
```

Repeat the copy for another reviewed skill. To restore all tracked skills after
reviewing their live differences, use:

```sh
rsync -a bb/skills/ "$bb_data_dir/skills/"
```

Do not use `--delete`. Preserve unrelated live skills and merge differences first.

To capture an intentional live edit, copy only that skill back into the repo
and review the diff. `bb skill update` can edit an existing user skill;
`bb skill install` installs a registry skill, not a local directory. A new local
skill is installed by creating its directory and `SKILL.md` in the server's user
skill root. There is no skill export/import command.

### Pstack delegation

The [`pstack-bb` skill](skills/pstack-bb/SKILL.md) adapts upstream pstack worker
operations to BB child threads. Every pstack child is a `pi` thread; Claude Code
and Codex are not pstack execution routes or fallback providers. The shared
[`agents/AGENTS.md`](../agents/AGENTS.md) and [`bb/AGENTS.md`](AGENTS.md) require
it before delegation inside BB. Standalone sessions retain their Pi pstack tools.
Keep the upstream package installed once per execution machine through Pi, and
leave its files unchanged.

Workers use the parent's machine. Readers and reviewers that need uncommitted
changes can share the parent's environment with explicit no-edit instructions and
before/after state checks; consequential reviews and writers use managed worktrees
from an explicit committed base. The adapter preserves pstack roles and review
gates, passes required role and rubric paths, validates model and effort choices
against the Pi catalog, and keeps integration with the parent. Reviewers' no-edit
instructions are not a read-only sandbox. Do not archive a worktree until useful
work is committed and preserved.

After an adapter update, verify discovery in a fresh BB session. Run a bounded
Pi reviewer check and an isolated-writing check. Inspect the child threads, target
machines, requested model/effort, role/rubric reads, completion messages, and
diffs. Confirm that no native subagent tools ran and that reviewers left the shared
tree unchanged.

## Capture current preferences

From the dotfiles root:

```sh
python3.11 bb/snapshot.py --server http://127.0.0.1:38886
```

This targets the **local server**, not necessarily the server currently selected in the desktop window. To capture a VPS server over SSH, run the script in the VPS dotfiles checkout against its localhost server. Direct BB Connect URLs may require authentication that the CLI must already have; these scripts do not mint sessions or bypass access controls.

Use `--bb /path/to/bb` if the CLI is not on PATH. Review `git diff -- bb/` before committing. Snapshot refreshes preferences only; update `plugins.json` separately after plugin installs, removals, or version changes.

The current snapshot was captured from the active VPS server on 2026-10-17. It
uses the **Vercel** theme, **BB Sidebar**, and the plugin inventory in
`plugins.json`. Restoring preferences does not install plugins; install the listed
plugins first.

## Restore preferences

Install the required plugins first. `bb-sidebar/inbox` in the sidebar preferences requires the BB Sidebar plugin. Other panel IDs may refer to installed or bundled plugins.

```sh
python3.11 bb/apply.py --server http://127.0.0.1:38886          # preview, no network writes
python3.11 bb/apply.py --server http://127.0.0.1:38886 --apply  # explicitly write
```

Restore uses BB's supported CLI rather than editing its database. It stops on the first error, but changes already applied are **not rolled back**. Capture the target's preferences to a private backup before restoring if you need to recover its previous configuration. Do not overwrite this shared snapshot with the target's backup unless that is intended.

Tracked settings cover selected general preferences, theme ID, favicon color, sidebar organization, navigation/panel visibility, and footer layout. They deliberately omit:

- server addresses, account pairing, enrollment, machine IDs and access policies;
- project/thread IDs, collapsed-project/thread state, and conversation data;
- provider authentication, plugin secrets and arbitrary plugin configuration;
- custom CSS/themes, keyboard overrides, experiments, and provider-specific completed-turn settings;
- client-only preferences such as the desktop's selected server or browser-local light/dark mode.

Those omissions are intentional: this is a portable preference restore, not a complete server backup. Never symlink all of `~/.bb` into this public repo.

## Plugins

Use the `source` in `plugins.json` with `bb plugin install`. For monorepos, also pass the recorded `--subdirectory`. Entries prefixed `builtin:` are shipped with BB rather than separate marketplace downloads; the inventory here records external plugins only. Version fields record what was observed, while semver source ranges can install newer compatible versions. Plugin installation runs full-trust code; review sources before installing.

BB Sidebar no longer needs the old 0.2.31 local build: since 0.2.34 it is a normal managed install from the source in `plugins.json`. Refresh the inventory from the live state after plugin changes:

```sh
bb plugin list --json | jq '{plugins: [.plugins[] | select(.source | startswith("builtin:") | not) | {id, version, enabled, source} + (if .subdirectory then {subdirectory} else {} end)] | sort_by(.id)}' > bb/plugins.json
```

## Current server arrangement

- The server for `diab.getbb.app` moved from the Mac to the VPS on 2026-10-14.
- Its data directory is `~/.bb-machines/diab.getbb.app` on the VPS, managed by the user unit listed above.
- The Mac is an execution machine, not the active server. The old VPS `bb.service` remains disabled and inactive.
- The preferences in this folder were originally captured from the Mac-hosted server; restoring them does not migrate a server or select its data directory.

In the Mac desktop app, use **macOS menu bar → Window → Server** to choose a server. Settings captured here do not decide which server owns your data.

## Checks

```sh
bash -n bb/install.sh
python3.11 bb/apply.py --server http://127.0.0.1:38886
```

Sources: the installed BB 0.45.0 CLI help and package README, plus the official [multiple-device guide](https://github.com/get-bb/bb/blob/main/docs/multiple-devices.md). No settings, packages, credentials, services, or server addresses are changed simply by pulling this folder or running `link.sh`.
