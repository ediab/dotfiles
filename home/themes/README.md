# Terminal themes

`terminal.json` and `terminal-tinted.json` are vendored unchanged from
[pi-terminal-theme](https://github.com/mavam/pi-terminal-theme) v0.2.0 by mavam.
The upstream MIT license is preserved in `LICENSE`.

Pi loads these as standalone themes from `~/.pi/agent/themes/`; no package is
required. `apply.sh --group themes` previews a configuration-only copy; add `--yes`
to apply. Explicit VPS deployment also copies them without deleting other locally
installed themes. Updates to these copies are manual.

`terminal` uses the standard ANSI palette. `terminal-tinted` additionally requires
custom terminal palette slots 16–23 for UI backgrounds and tool text.
