# Put user-local binaries (moshi, moshi-hook, mosh helpers) on PATH for
# ALL zsh invocations, including non-interactive `ssh host <cmd>` sessions.
# Required so Moshi/mosh bootstrap can find ~/.local/bin/moshi. Keep this
# file output-free: any stdout here breaks the mosh MOSH-CONNECT handshake.
export PATH="$HOME/.local/bin:$PATH"
