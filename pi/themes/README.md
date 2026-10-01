# Terminal themes

`terminal.json` and `terminal-tinted.json` are vendored unchanged from
[pi-terminal-theme](https://github.com/mavam/pi-terminal-theme) v0.2.0 by mavam.
Upstream license: MIT.

Pi loads these as standalone themes from `~/.pi/agent/themes/`, which `link.sh` links to
this folder; no package is required. Updates to these copies are manual.

`terminal` uses the standard ANSI palette. `terminal-tinted` additionally requires
custom terminal palette slots 16–23 for UI backgrounds and tool text.
