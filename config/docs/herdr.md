# Herdr — keybinding reference

Press **`ctrl+b`** (prefix) first, then the key. All bindings below are active in this config (`herdr/config.toml`). Fits one page when printed from the markdown preview (A4, default margins).

<style>
@media print {
  h1 { font-size: 14pt; margin: 0 0 6pt; }
  h2 { font-size: 11pt; margin: 8pt 0 2pt; }
  body { font-size: 9pt; }
  table { font-size: 8.5pt; }
  th, td { padding: 2px 6px; }
  blockquote { margin: 4pt 0; font-size: 8.5pt; }
}
</style>

## Core

| Keys | Action |
|------|--------|
| `prefix+?` | Help |
| `prefix+s` | Settings |
| `prefix+q` | Detach (Herdr keeps running) |

## Workspaces

| Keys | Action |
|------|--------|
| `prefix+w` | Workspace picker |
| `prefix+g` | Goto (jump to workspace/pane) |
| `prefix+shift+n` | New workspace |
| `prefix+shift+g` | New worktree |
| `prefix+shift+w` | Rename workspace |
| `prefix+shift+d` | Close workspace (confirm) |

## Tabs

| Keys | Action |
|------|--------|
| `prefix+c` | New tab |
| `prefix+shift+t` | Rename tab |
| `prefix+1..9` | Switch to tab N |
| `prefix+p` / `prefix+n` | Previous / next tab |
| `prefix+shift+x` | Close tab |

## Panes

| Keys | Action |
|------|--------|
| `prefix+v` | Split vertically |
| `prefix+minus` | Split horizontally |
| `prefix+h/j/k/l` | Focus left / down / up / right |
| `prefix+tab` / `prefix+shift+tab` | Cycle panes |
| `prefix+x` | Close pane |
| `prefix+z` | Zoom pane (fullscreen) |
| `prefix+r` | Resize mode (arrows, `esc` exits) |
| `prefix+e` | Edit scrollback |
| `prefix+b` | Toggle sidebar |
| `prefix+shift+p` | Rename pane |

## Auto Title (kryptamine/herdr-auto-title)

Names every tab and pane after the work in it, so a pi session's tab carries that session's own
title instead of a number. A tab or pane you rename by hand (`prefix+shift+t`, `prefix+shift+p`)
is left alone from then on; clearing the name hands it back.

Settings live in `~/.config/herdr-auto-title/config.env`, linked from `config/herdr-auto-title/`,
and are read once at startup. This machine's file turns off the position number, the agent name
and branches, so a tab reads its session title and nothing else.

```sh
herdr plugin install kryptamine/herdr-auto-title      # new machine; builds from source (Go 1.24+)
herdr plugin action invoke herdr.auto-title.restart   # after upgrading or editing config.env
```
