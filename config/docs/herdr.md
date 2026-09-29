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

## Annotate (plannotator/herdr-annotate)

| Keys | Action |
|------|--------|
| Select text, then `prefix+a` | Annotate the selection (`ctrl+s` saves) |
| `prefix+shift+a` | Copy all annotations as Markdown |
| `prefix+m` | Manage: `y` copy · `c` copy all · `Shift+C` copy+archive · `d d` delete |
| `prefix+o` | Focus notification target |
| `prefix+d` | Review documents in the focused pane's folder |
| `prefix+shift+o` | Review the agent's last reply, send feedback (`e`) |
| Ctrl-click a `file://….md` link | Open that file in the annotator |

## Smart Rename (iurysza/herdr-tab-smart-rename)

| Keys | Action |
|------|--------|
| `prefix+t` | Smart-rename current tab |
| `prefix+alt+t` | Smart-rename all tabs |

## Oh My Zsh (robbyrussell/herdr-ohmyzsh)

| Keys | Action |
|------|--------|
| `prefix+shift+r` | Reload Oh My Zsh in every idle pane (`hreload`) |

Shell helpers (inside a Herdr pane): `hsplit [right|down] [cmd]`, `htab [label]`, `hagent NAME [KIND]`, `hworktree BRANCH [BASE]`, `hreload`. Slow commands (>10s) show in the sidebar and toast on finish.

> Installed plugins: `annotate`, `tab-smart-rename`, `ohmyzsh.shell` — tracked in `herdr/plugins.txt` (regenerate with `herdr plugin list`).
