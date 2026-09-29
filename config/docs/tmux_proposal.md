# tmux for pi (pi.dev) + edxeth/pi-subagents

## 0. Prerequisites
- tmux 3.5+ (`tmux -V`). 3.2–3.4 works but omit `extended-keys-format`.
- Terminal with Kitty-keyboard/extended-key support: Ghostty, Kitty, WezTerm,
  iTerm2, Windows Terminal. xfce4-terminal, terminator and IntelliJ's terminal
  cannot distinguish Shift+Enter from Enter — no tmux config fixes that.
- Ghostty users: delete any legacy `keybind = shift+enter=text:\n` line. It
  sends a raw linefeed, indistinguishable from Ctrl+J, and kills real
  shift+enter detection inside tmux.

## 1. ~/.tmux.conf

```tmux
# ── pi key handling (mandatory) ───────────────────────────────────────────
set  -g extended-keys on
set  -g extended-keys-format csi-u        # tmux 3.5+ only; drop on 3.2–3.4

# ── terminal capabilities ─────────────────────────────────────────────────
set  -g default-terminal "tmux-256color"
set -ga terminal-features ",*:RGB,*:clipboard,*:hyperlinks"
set -sg escape-time 10                    # stop ESC lag in the pi TUI
set  -g focus-events on

# ── clipboard + OSC passthrough (agents emit OSC 52 / OSC 777) ────────────
set  -g allow-passthrough on              # note: lets inner progs write raw escapes
set  -g set-clipboard on

# ── knowing when a child agent finishes ───────────────────────────────────
set  -g monitor-bell on
set  -g bell-action any
set  -g monitor-activity on
set  -g visual-activity off
setw -g window-status-activity-style 'fg=yellow'
setw -g window-status-bell-style     'fg=red,bold'

# ── subagent window/pane hygiene ──────────────────────────────────────────
setw -g automatic-rename off               # let set_tab_title names stick
set  -g allow-rename off
set  -g remain-on-exit failed              # keep panes of children that crashed
set  -g destroy-unattached off             # parent-close-policy: continue survives
set  -g pane-border-status top
set  -g pane-border-format " #{pane_index} #{pane_current_command} "

# ── living with long agent output ─────────────────────────────────────────
set  -g history-limit 200000
set  -g mouse on
setw -g mode-keys vi
set  -g base-index 1
setw -g pane-base-index 1
set  -g renumber-windows on

# ── plugins ───────────────────────────────────────────────────────────────
set -g @plugin 'tmux-plugins/tpm'
set -g @plugin 'tmux-plugins/tmux-sensible'
set -g @plugin 'tmux-plugins/tmux-resurrect'
set -g @plugin 'tmux-plugins/tmux-continuum'
set -g @plugin 'tmux-plugins/tmux-yank'
set -g @plugin 'tmux-plugins/tmux-logging'
set -g @plugin 'Morantron/tmux-fingers'

set -g @resurrect-capture-pane-contents 'on'
set -g @continuum-restore 'on'
# Do NOT add `pi` to @resurrect-processes — you don't want six agents
# relaunching on reboot. Default behaviour already excludes it.

run '~/.tmux/plugins/tpm/tpm'
```

Apply: `tmux kill-server && tmux` (a full server restart is required for
`extended-keys`; sourcing the file is not enough). Then `prefix + I` to install
plugins.

## 2. Shell environment (~/.zshrc or ~/.bashrc)

```sh
export PI_SUBAGENT_MUX=tmux                 # force the backend, skip detection
export PI_SUBAGENT_ENABLE_SET_TAB_TITLE=1   # register the set_tab_title tool
export PI_SUBAGENT_RENAME_TMUX_WINDOW=1     # let children name their window
# export PI_SUBAGENT_RENAME_TMUX_SESSION=1  # optional, noisier
export PI_SUBAGENT_SHELL_READY_DELAY_MS=1200  # raise from 500 if rc is slow
```

Orchestrator sessions get their own tmux session and a distinct status colour:

```sh
alias pio='PI_ORCHESTRATOR_MODE=1 tmux new -A -s orchestrator "pi"'
```

## 3. Verification checklist
- `tmux -V` → 3.5 or later
- `tmux show -g extended-keys` → on
- `tmux show -g extended-keys-format` → csi-u
- `tmux show -g allow-passthrough` → on
- In pi: Shift+Enter inserts a newline, Enter submits
- Spawn one subagent → window is renamed to the child's title
- Copy inside pi → text lands in the system clipboard

## 4. Known gotchas
- **Symptom:** Shift+Enter submits instead of newline.
  **Cause:** server not fully restarted, or tmux < 3.5 with `csi-u` set.
  **Fallback:** pi binds Ctrl+J as a newline alias.
- **Symptom:** spawned pane sits at a prompt with mangled text.
  **Cause:** `PI_SUBAGENT_SHELL_READY_DELAY_MS` too low for your shell rc.
- **Symptom:** no desktop notifications from agent hooks.
  **Cause:** `allow-passthrough` off, or tmux not restarted after enabling it.
- **Symptom:** clipboard copy inside pi silently does nothing.
  **Cause:** tmux swallowing OSC 52 — needs `allow-passthrough` + `set-clipboard`.
- **Symptom:** child window names revert to `pi`.
  **Cause:** `automatic-rename` still on.
- **Symptom:** continuum autosave stops working.
  **Cause:** a theme plugin overwrote `status-right`. Load themes before continuum.

## 5. Deliberately omitted
- **tmux-agent-indicator / tmux-agent-sidebar** — pi-subagents already renders a
  live child widget above the editor; these are hook-driven for Claude Code,
  Codex and OpenCode, so they'd need a bridge to duplicate what you have.
- **Zellij placement tuning** — `PI_SUBAGENT_ZELLIJ_*` has no tmux equivalent.
  Manage layout density yourself (`select-layout main-vertical`, or break panes
  out into windows).
