# BB setup and portable preferences

This folder records how to install/update BB and restore selected preferences. It is **not** a copy of `~/.bb`, and nothing here is automatically applied by `link.sh`.

## Files

- `install.sh`: explicitly install the latest stable npm runtime, or a specified stable version.
- `preferences.json`: last captured portable preferences from the Mac server.
- `snapshot.py`: refresh that file using an allowlist of general, appearance, and sidebar settings.
- `apply.py`: preview or explicitly restore those preferences to a chosen server.
- `plugins.json`: manually maintained plugin inventory with observed versions, sources, and monorepo subdirectories. It is documentation, not an automatic installer.
- `common.py`: shared preference allowlists and CLI calls.

Requirements: Python 3, Node.js supported by BB (0.45.0 supports Node 22.19+, 24, or 26), npm, and a working `bb` CLI for snapshot/restore. The runtime install needs network access and runs the native dependency build scripts for `better-sqlite3`, `node-pty`, and `@parcel/watcher`.

## Install or update the npm runtime

```sh
bash bb/install.sh             # resolve the latest stable npm release now
bash bb/install.sh 0.45.0      # install a specific stable release
```

The default location is `~/apps/bb-runtime`; override with `BB_RUNTIME_DIR`. Runtime packages and lockfiles stay there, **outside this repo**. The script does not start/stop services, create enrollment credentials, update the desktop app, or change `~/.bb`.

On the VPS, the existing `bb.service` uses `/home/diab/apps/bb-runtime`, and `~/bin/bb` invokes its CLI. After an approved update, restart explicitly:

```sh
systemctl --user restart bb.service
systemctl --user status bb.service
~/bin/bb machine list --json
```

Check a real task after updating; an active service alone is not proof an agent works. The Mac desktop app is a separate installation: update it through its supported app update mechanism, not this npm script. No automatic updater is scheduled by this folder.

## Capture current preferences

From the dotfiles root:

```sh
python3 bb/snapshot.py --server http://127.0.0.1:38886
```

This targets the **local server**, not necessarily the server currently selected in the desktop window. To capture a VPS server over SSH, run the script in the VPS dotfiles checkout against its localhost server. Direct BB Connect URLs may require authentication that the CLI must already have; these scripts do not mint sessions or bypass access controls.

Use `--bb /path/to/bb` if the CLI is not on PATH. Review `git diff -- bb/` before committing. Snapshot refreshes preferences only; update `plugins.json` separately after plugin installs, removals, or version changes.

The initial snapshot uses **Catppuccin** and **BB Sidebar**. Tokyo Night is installed but was not the active theme at capture time.

## Restore preferences

Install the required plugins first. `bb-sidebar/inbox` in the sidebar preferences requires the BB Sidebar plugin. Other panel IDs may refer to installed or bundled plugins.

```sh
python3 bb/apply.py --server http://127.0.0.1:38886          # preview, no network writes
python3 bb/apply.py --server http://127.0.0.1:38886 --apply  # explicitly write
```

Restore uses BB's supported CLI rather than editing its database. It stops on the first error, but changes already applied are **not rolled back**. Capture the target's preferences to a private backup before restoring if you need to recover its previous configuration. Do not overwrite this shared snapshot with the target's backup unless that is intended.

Tracked settings cover selected general preferences, theme ID, favicon color, sidebar organization, navigation/panel visibility, and footer layout. They deliberately omit:

- server addresses, account pairing, enrollment, machine IDs and access policies;
- project/thread IDs, collapsed-project/thread state, and conversation data;
- provider authentication, plugin secrets and arbitrary plugin configuration;
- custom CSS/themes, keyboard overrides, experiments, and provider-specific completed-turn settings;
- client-only preferences such as the desktop's selected server or browser-local light/dark mode.

Those omissions are intentional: this is a portable preference restore, not a complete server backup. Never symlink all of `~/.bb` into this public repo.

## Plugins and the sidebar workaround

Use the `source` in `plugins.json` with `bb plugin install`. For monorepos, also pass the recorded `--subdirectory`. Entries prefixed `builtin:` are shipped with BB rather than separate marketplace downloads; the inventory here records external plugins only. Version fields record what was observed, while semver source ranges can install newer compatible versions. Plugin installation runs full-trust code; review sources before installing.

The BB Sidebar entry needs a local workaround for version 0.2.31:

```sh
git clone --depth 1 --branch v0.2.31 https://github.com/yusuf8834/bb-sidebar.git "$HOME/.bb/local-plugins/bb-sidebar"
cd "$HOME/.bb/local-plugins/bb-sidebar"
npm install --save-prod 'react-day-picker@^9.14.0' --omit=dev --ignore-scripts --no-audit --no-fund
bb plugin build .
bb plugin install "path:$HOME/.bb/local-plugins/bb-sidebar"
```

Only clone if that destination does not already exist. This workaround was built and installed on the Mac; it is not a marketplace-tracking installation. Keep its folder in place. Verify whether the upstream release fixes the dependency before switching back to a managed install.

## Current server arrangement

- `diab.getbb.app`: the Mac server, with the plugins and preferences originally captured here.
- `diabvps.getbb.app`: a separate VPS server set up with a persistent `bb.service`.
- A machine was subsequently enrolled into `diab.getbb.app` by the user. Enrollment adds a worker; it does not migrate the server or reassign its address. Its post-enrollment status has not been verified here.

In the Mac desktop app, use **macOS menu bar → Window → Server** to choose a server. A Mac-hosted server must stay running for its workers to receive tasks. Settings captured here do not decide which server owns your data.

## Checks

```sh
python3 -m unittest discover -s tests -p 'test_bb.py'
bash -n bb/install.sh
python3 bb/apply.py --server http://127.0.0.1:38886
```

Sources: the installed BB 0.45.0 CLI help and package README, plus the official [multiple-device guide](https://github.com/get-bb/bb/blob/main/docs/multiple-devices.md). No settings, packages, credentials, services, or server addresses are changed simply by pulling this folder or running `link.sh`.
