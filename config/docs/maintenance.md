# Maintenance guide

One operational guide for keeping this Mac's software and configuration maintained.
Live as of 2026-10-01.

## Division of responsibility

| What | How | Cadence |
|---|---|---|
| 6 allowlisted brew formulae | `brew autoupdate` launch agent | weekly, unattended (AC only) |
| Other brew formulae/casks | manual `brew upgrade <pkg>` | on demand |
| npm, bun, uv, rustup, tmux/oh-my-zsh/tldr/vscode, agent CLIs | `topgrade` (manual, allowlisted) | weekly/fortnightly |
| macOS updates | Software Update: automatic downloads + Security Responses on | review weekly; major upgrades manually |
| App Store apps | existing `mas-autoupdate` launch agent (`mas upgrade` daily) | automatic |
| Other GUI apps | the app's own updater; optionally install `brew install --cask latest` | on demand |
| Homebrew cache | `brew cleanup -s` | alongside the monthly inventory refresh |
| dotfiles repo | review, commit, push explicitly | with changes |

## Homebrew: allowlisted weekly autoupdate

Homebrew upgrades **only** `bat eza jq ripgrep tldr wget` — weekly, on AC power, with
notifications only on failure. No casks, no `--greedy`, no cleanup, no login run, no GUI
sudo. Everything else in Brew — node, rust, herdr, druk, claude-usage, and all casks —
is upgraded manually, because unattended upgrades of runtimes, databases, container
tooling and agent/editor tooling are too risky.

Exact setup command (run once; verify with `brew autoupdate status --verbose`):

```sh
brew autoupdate start 1w --upgrade --only=bat,eza,jq,ripgrep,tldr,wget --ac-only --notify-on-error
```

- **Dependencies caveat:** the allowlisted packages pull small libraries (libgit2,
  openssl, oniguruma, pcre2, zstd, …). Those get upgraded with them; that is expected
  and safe — they are not runtimes or services.
- **Failure check:** `brew autoupdate logs --lines=50`. Errors also appear as macOS
  notifications. After any Homebrew self-update (e.g. a macOS upgrade), run
  `brew autoupdate status` once to confirm the agent survived.
- **Rollback** — the previous job (daily, all formulae + casks, cleanup, login run,
  all notifications, GUI sudo) can be reconstructed with:

  ```sh
  brew autoupdate start --upgrade --cleanup --ac-only --notify --sudo
  ```

  (It ran `brew update && brew upgrade --no-ask --formula -v && brew upgrade --no-ask
  --cask -v && brew cleanup` every 86400 s with `RunAtLoad`.)

## Package inventory

`config/Brewfile` is the canonical, restorable inventory of this Mac. It is a
dependency-correct inventory, not a version-locked snapshot.

- **Refresh (manual, ~monthly or after significant package changes):**

  ```sh
  brew bundle dump --file=/tmp/brew-dump-fresh
  diff config/Brewfile /tmp/brew-dump-fresh   # review, don't blind-copy
  # merge reviewed changes into config/Brewfile, then ask for a commit
  ```

  Keep intentional options (`trusted:`, versioned names like `ghostty@tip`, narrowly
  scoped taps) when merging; check the new package's origin before adding a new tap.
- **New-machine restore:** clone `ediab/dotfiles`, `./link.sh`, then
  `brew bundle --file=config/Brewfile`.
- **Check:** `brew bundle check --file=config/Brewfile` (ignorable known noise:
  outdated `font-geist-mono` and the libtiff/webp circular-dependency warning).

## Topgrade: manual non-Brew maintenance

`topgrade` (config symlinked from `config/topgrade.toml`) updates everything **except**
Brew, macOS, App Store, Office, gems and git repos. The `only` allowlist in the config
selects: bun + bun packages, node/npm globals, uv, rustup, tmux plugins (tpm),
oh-my-zsh, tldr pages, VS Code extensions, and the agent CLIs (pi, claude + its
plugins, antigravity, gcloud, gh extensions, skills).

Routine (weekly or fortnightly):

```sh
topgrade --dry-run    # preview exactly what will run — always look first
topgrade              # then run for real; approve each step's prompts yourself
```

- Never run Topgrade on a schedule or unattended; it is the manual path.
- Adding a new package manager later? Its Topgrade step stays **off** until you add
  the step name to `only` in `config/topgrade.toml`.
- Remote machines are excluded (`remote_topgrades = []`) — never VPS-updated from here.

## macOS updates (System Settings — manual, UI only)

1. System Settings → General → Software Update → ⓘ (Automatic Updates):
   - **On:** "Download new updates when available".
   - **On:** "Install Security Responses and system files".
   - **Off:** "Install macOS updates" — approve major upgrades manually after checking
     app compatibility.
2. Weekly-ish: open Software Update and install any pending security updates.
3. Major upgrades (x.0 releases): run manually, with time and a current backup.

## GUI apps

Apps update via their own updaters (e.g. Microsoft AutoUpdate, Obsidian, Ghostty via
`brew upgrade ghostty@tip` by hand). App Store apps are covered by the existing
`com.user.mas-autoupdate` launch agent (`mas upgrade` daily). The `latest` cask
(aggregates third-party app updaters) is **not currently installed**; install it with
`brew install --cask latest` if wanted — it does not cover every GUI app either.

## Cleanup

`brew cleanup` is no longer part of the autoupdate job (policy: no extra unattended
work). Run `brew cleanup -s` roughly monthly, or whenever disk feels tight. Mole exists
for a deep clean of an *identified* need only — never scheduled, never blanket.

## Configuration backup

`~/Dev/dotfiles` is the single active checkout; `link.sh` symlinks its files into
`$HOME`, `~/.config` and app dirs, so edits are live immediately. Backup = explicit
review → commit → push (there are no auto-commit, push or VPS-sync jobs; the retired
ones are archived, not installed). Do not publish app-written settings or secrets:
secrets live in the Keychain and `~/.env`, never in the repo.

## Legacy checkout archive

`~/Dev/configs` was reconciled into this repo and archived at
`~/Archive/configs-2026-10-01` (clean tree, no unpushed commits; a README-ARCHIVE.md
inside records the audit). Removal conditions (also in the archive README): 90+ days
of dotfiles being the sole active checkout, the old TINYFISH key rotated or confirmed
dead, and a final skim finding nothing wanted. Restore by `mv` back to `~/Dev/configs`
if an overlooked dependency ever appears.
