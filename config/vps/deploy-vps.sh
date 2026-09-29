#!/bin/bash
# Deploy this repo's VPS-side files to `ssh vps`.
#
# Unlike the Mac, the VPS copies are NOT symlinked: nothing on the VPS reads this
# repo, so this directory is the source of truth and is pushed by script. The shell
# files here were captured byte-for-byte from the VPS, so a deploy with no local edits
# is a no-op you can use to verify drift:
#
#   for f in .zshrc .zshenv .p10k.zsh .tmux.conf; do
#       diff -q <(ssh vps "cat ~/$f") "$(dirname "$0")/$f" || echo "DRIFT: $f"
#   done
#
# What it deploys:
#   .zshrc, .zshenv, .p10k.zsh, .tmux.conf   shell dotfiles -> ~/
#   vps-cleanup.sh, vps-update-images.sh     weekly upkeep   -> ~/bin/ (chmod +x)
#   systemd/*.service, systemd/*.timer       user units      -> ~/.config/systemd/user/
#   apps-AGENTS.md                           app-root doc    -> ~/apps/AGENTS.md
#   vps/apps-AGENTS.md                        app-root doc    -> ~/apps/AGENTS.md
#   apt/51-vps-auto-updates                    update policy   -> /etc/apt/apt.conf.d/ (sudo)
#
# Note: /etc/apt/apt.conf.d/50unattended-upgrades is NOT deployed — it belongs to the
# package (shipped from /usr/share/unattended-upgrades/). Only our own 51- file is managed.
#
#   .zshrc     zsh: oh-my-zsh + plugins, PATH, aliases (mode 600 on the VPS)
#   .zshenv    PATH for *every* zsh invocation — must stay output-free (a single
#              line of stdout breaks the mosh MOSH-CONNECT handshake)
#   .p10k.zsh  Powerlevel10k prompt (wizard-generated: lean, ascii, 1 line)
#   .tmux.conf minimal mobile-friendly tmux (prefix C-a, status bar on top)
#
# This is deliberately a separate, simpler set than the Mac dotfiles at the repo
# root — the VPS has no starship/fzf/plugins, so do not sync those across.
#
# CAUTION: installers (bun, brew, pyenv, nvm) append their own blocks to the VPS
# ~/.zshrc. If one runs after a deploy, re-capture the file here (scp it back) or
# the next deploy reverts that block.
#
#   VPS_HOST=<ssh-alias>   override the target host (default: vps)

set -euo pipefail

HOST="${VPS_HOST:-vps}"
SRC="$(cd "$(dirname "$0")" && pwd)"
FILES=(.zshrc .zshenv .p10k.zsh .tmux.conf)
SCRIPTS=(vps-cleanup.sh vps-update-images.sh)
UNITS=(vps-cleanup.service vps-cleanup.timer vps-update-images.service vps-update-images.timer herdr-server.service)
APT_FILES=(51-vps-auto-updates)

for f in "${FILES[@]}"; do
    [ -f "$SRC/$f" ] || { echo "Not found: $SRC/$f" >&2; exit 1; }
done
for f in "${SCRIPTS[@]}"; do
    [ -f "$SRC/$f" ] || { echo "Not found: $SRC/$f" >&2; exit 1; }
done
for f in "${UNITS[@]}"; do
    [ -f "$SRC/systemd/$f" ] || { echo "Not found: $SRC/systemd/$f" >&2; exit 1; }
done
for f in "${APT_FILES[@]}"; do
    [ -f "$SRC/apt/$f" ] || { echo "Not found: $SRC/apt/$f" >&2; exit 1; }
done

echo "==> shell dotfiles"
for f in "${FILES[@]}"; do
    scp -q "$SRC/$f" "$HOST:~/$f"
    echo "Copied $f -> $HOST:~/$f"
done

# scp applies the *source* file's mode, and git does not track it — so the deployed
# .zshrc would end up world-readable or not depending on the checkout. Pin it to the
# 600 the VPS already used (same as the Mac copy) instead of letting it drift.
ssh "$HOST" 'chmod 600 ~/.zshrc'

echo "==> weekly upkeep scripts -> ~/bin"
ssh "$HOST" 'mkdir -p ~/bin ~/logs ~/.config/systemd/user'
for f in "${SCRIPTS[@]}"; do
    scp -q "$SRC/$f" "$HOST:~/bin/$f"
    echo "Copied $f -> $HOST:~/bin/$f"
done
ssh "$HOST" 'chmod +x ~/bin/vps-cleanup.sh ~/bin/vps-update-images.sh'

echo "==> user units -> ~/.config/systemd/user"
for f in "${UNITS[@]}"; do
    scp -q "$SRC/systemd/$f" "$HOST:~/.config/systemd/user/$f"
    echo "Copied $f -> $HOST:~/.config/systemd/user/$f"
done

echo "==> app-root doc -> ~/apps/AGENTS.md"
scp -q "$SRC/apps-AGENTS.md" "$HOST:~/apps/AGENTS.md"

echo "==> apt update/reboot policy -> /etc/apt/apt.conf.d"
for f in "${APT_FILES[@]}"; do
    scp -q "$SRC/apt/$f" "$HOST:/tmp/$f"
done
# Installed as root-owned 0644; needs the passwordless sudo this user has. The package's
# own 50unattended-upgrades is left alone — apt merges our origins with it.
ssh "$HOST" 'for f in 51-vps-auto-updates; do sudo install -m 644 -o root -g root "/tmp/$f" "/etc/apt/apt.conf.d/$f"; done; rm -f /tmp/51-vps-auto-updates'
# Hand-made copies of the package file, which made apt print
# "N: Ignoring file … invalid filename extension".
ssh "$HOST" 'sudo find /etc/apt/apt.conf.d -maxdepth 1 -name "50unattended-upgrades.bak-*" -delete'

echo "==> enable timers and the herdr server unit"
ssh "$HOST" 'sudo loginctl enable-linger "$USER" 2>/dev/null || true'
ssh "$HOST" 'systemctl --user daemon-reload && systemctl --user enable vps-cleanup.timer vps-update-images.timer herdr-server.service'
ssh "$HOST" 'systemctl --user start vps-cleanup.timer vps-update-images.timer'
# Only start the server if nothing (e.g. a manual `herdr`) is already serving.
ssh "$HOST" 'systemctl --user is-active --quiet herdr-server.service || systemctl --user start herdr-server.service || true'

# tmux caches its config in the running server, so re-source it when one is up.
# No server running (or the source fails) is not an error here.
ssh "$HOST" 'tmux source-file ~/.tmux.conf 2>/dev/null || true'

echo ""
echo "Deployed. zsh changes apply to new shells on $HOST (in an existing shell: 'reload')."
echo "Weekly: vps-cleanup (Sun 04:30), vps-update-images (Sun 05:30); herdr server kept up."
