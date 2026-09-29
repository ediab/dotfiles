# tmux — quick guide

> Tuned to your `~/.tmux.conf`. Nothing here is generic — every key is one you have.

## The one idea

**Your session survives you walking away.** Close the terminal, drop SSH, shut the laptop — the processes inside keep running. `detach` is not `quit`. Splitting panes is the garnish; **persistence** is the meal.

This is why tmux is the right tool for running long-lived things like `pi`: start it in a session, detach, come back hours later, it's still there.

## The prefix

Every tmux command starts with a prefix key. Yours is **`C-a`** (hold Ctrl, press `a`).

So "do X" means: press `C-a`, release, then press X.

---

## Sessions (from your shell, not inside tmux)

Session aliases in your `~/.zshrc`:

| alias | does | example |
|-------|------|---------|
| `tl`  | list running sessions | `tl` |
| `tn`  | new named session      | `tn work` |
| `tt`  | attach to a session    | `tt work` |
| `pio` | pi orchestrator session | `pio` |

**Name your sessions.** Unnamed ones become `0`, `1`, `2` and you lose track fast.

### Inside tmux (session keys)

| key | action |
|-----|--------|
| `C-a d` | **detach** (the one that matters — session keeps running) |
| `C-a s` | list sessions (picker) |
| `C-a $` | rename current session |

---

## Windows (like tabs, inside a session)

| key | action |
|-----|--------|
| `C-a c` | new window |
| `C-a n` / `C-a p` | next / previous window |
| `C-a 1` … `C-a 9` | jump to window N (yours are 1-indexed) |
| `C-a ,` | rename window |
| `C-a w` | list windows |
| `C-a &` | kill window (or just `exit` the shell) |

---

## Panes (splits inside a window)

| key | action |
|-----|--------|
| `C-a \|` | split **left/right** (note: keeps your current directory) |
| `C-a -`  | split **top/bottom** (keeps current directory) |
| `C-a h j k l` | move focus left/down/up/right |
| `C-a H J K L` | resize (holdable: press repeatedly) |
| `C-a z` | zoom the active pane to full-window, toggle again to undo |
| `C-a x` | kill pane (or `exit` the shell) |

Don't like a layout? `C-a space` cycles built-in presets (even-horizontal, tiled, etc.).

---

## Copy mode (vi keys)

Enter copy mode to scroll back, search, or copy:

| key | action |
|-----|--------|
| `C-a [` | enter copy mode |
| `h j k l` / arrows | move |
| `/` | search forward, `?` backward (press `Enter`, `n`/`N` next/prev) |
| `v` | start selection, move to extend |
| `y` | yank selection to **system clipboard** (tmux-yank) |
| `q` or `Esc` | leave copy mode |

Mouse scroll also enters copy mode automatically.

---

## Your `pi` workflow

**Shell env vars (already in your `~/.zshrc`):**
```sh
export PI_SUBAGENT_MUX=tmux                 # pi uses tmux for subagents
export PI_SUBAGENT_ENABLE_SET_TAB_TITLE=1   # subagents can name their windows
export PI_SUBAGENT_RENAME_TMUX_WINDOW=1
export PI_SUBAGENT_SHELL_READY_DELAY_MS=1200
```

**Run pi in a fresh named session (recommended):**
```
tn pi             # create session "pi"
pi                # launch pi inside it
```

Detach with `C-a d`, come back with `tt pi`. It survived.

**Dedicated orchestrator session:**
```
pio               # alias: opens a session named "orchestrator" with PI_ORCHESTRATOR_MODE=1
```

**Fork a sub-agent from the current context (one keybind):**
- `C-a f` → opens a popup that grabs the last 2000 lines of the current pane, asks you for an instruction, and launches `pi` in a new window primed with that context.
- Where it lives: `~/fork-agent.sh` (you can read/edit it).

## pi-subagents: what tmux now shows you

When pi spawns a subagent:
- **Window titles** update to show the child agent's name (e.g. "reviewer", "planner"). This works because `automatic-rename` and `allow-rename` are off, letting pi set the title.
- **When a background agent finishes**, the window status bar turns **red** (bell) or **yellow** (activity). Glance at your status bar to see if work completed while you were in another window.
- **Pane borders** show `[pane#] [process name]` at the top of each split, so you always know what's running where.
- **Shift+Enter** inserts a newline in pi's TUI (multiline input). Plain Enter submits. This works because `extended-keys` is on and Ghostty supports it.
- **Clipboard** works end-to-end: copy inside pi lands in your system clipboard (via OSC 52 passthrough).

---

## Persistence — reboot survival (tmux-resurrect + tmux-continuum)

- **Auto-save** every 15 minutes.
- **Auto-restore** when tmux starts (`@continuum-restore on`).
- **Pane text** is also saved and restored (`@resurrect-capture-pane-contents on`).
- Manual: `C-a Ctrl-s` to save now, `C-a Ctrl-r` to restore.

**After a reboot**, just run `tt <name>` (or `tmux`) — your layout, panes, working directories, and scrollback text come back. Running programs (like a live `pi`) won't be re-launched, but the structure and text history are preserved.

---

## Sidebar (tmux-sidebar)

- `C-a Tab` → toggle a file tree on the left (uses `tree -C -L 2`).
- Hit `C-a Tab` again to hide it. If you never use it, tell the agent and it'll remove two lines.

## tmux-fingers (keyboard-driven copy)

Copy anything on screen without reaching for the mouse. Jump to paths, hashes, URLs, IPs, or any word.

| key | action |
|-----|--------|
| `C-a F` | enter fingers mode — every match gets a label (letter pair) |
| type the label | yank it to clipboard |

Built-in patterns: files, git SHAs, hex numbers, URLs, IPs, UUIDs, and more. Faster than copy mode for grabbing one thing.

## tmux-logging (save pane output)

| key | action |
|-----|--------|
| `C-a P` | toggle logging for the current pane (start/stop) |
| `C-a alt-p` | save the visible pane text to a file now |
| `C-a alt-P` | save the full scrollback history (all 200k lines) |

Logs land in `~/` with timestamped names. Useful for capturing long agent output or saving a transcript to reference later.

---

## Config & reload

- Your config: `~/.tmux.conf`
- After editing it, **restart the tmux server** for key-handling changes (`tmux kill-server && tmux`). For minor edits, `C-a r` reloads in-place.

## Useful escape hatches

| key | action |
|-----|--------|
| `C-a ?` | list all keybindings (life-saver when you forget one) |
| `C-a :` | command prompt (run any tmux command manually) |
| exit the shell in the last pane | closes the session |

## Beginner tips

- You can just **close the terminal window** — the session keeps running. `C-a d` is the "clean" detach but not required.
- **Mouse works**: click to focus panes, drag borders to resize, scroll = copy mode.
- `C-a ?` lists every key. Bookmark this page; reach for that list when you forget one.
- Forgot a session name? `tl` from your shell, or `C-a s` from inside tmux.