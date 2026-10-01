# VS Code config

Complete, self-contained: everything user-facing VS Code reads lives here or is listed here.

| file | what it is |
|---|---|
| `settings.json` | linked into `~/Library/Application Support/Code/User/` by `link.sh`; edit either side, they're the same file |
| `keybindings.json` | same link target; currently `[]` (defaults only) |
| `argv.json` | linked as `~/.vscode/argv.json`; stored verbatim including the per-install `crash-reporter-id` (inert — crash reporting is off). VS Code rewrites through the symlink, like it does for `settings.json` |
| `extensions.txt` | inventory snapshot of `code --list-extensions` (18 extensions); **not** auto-installed. Real install source is the Brewfile (`vscode` resources). Refresh by running `code --list-extensions > extensions.txt` here |

Covered elsewhere, not duplicated:
- which extensions to install → `../Brewfile`
- per-project settings → live in each project's `.vscode/`
