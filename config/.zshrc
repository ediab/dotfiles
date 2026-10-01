# ==============================================
# 0. CORE ZSH OPTIONS  (must run before oh-my-zsh)
# ==============================================

# Auto-dedupe PATH-like arrays for the rest of this file's life.
# This is why the duplicate ~/.local/bin entries below are harmless now.
typeset -U path fpath manpath PATH FPATH MANPATH

setopt AUTO_CD                # type a directory name to cd into it
setopt AUTO_PUSHD             # every cd pushes onto the dir stack
setopt PUSHD_IGNORE_DUPS
setopt INTERACTIVE_COMMENTS   # allow "# comments" at the prompt
setopt EXTENDED_GLOB
setopt NO_BEEP
setopt NO_FLOW_CONTROL        # frees up ctrl-s / ctrl-q

# Uncomment this + the `zprof` line at the bottom to profile startup time.
# zmodload zsh/zprof

# ==============================================
# 1. OH-MY-ZSH
# ==============================================

export ZSH="$HOME/.oh-my-zsh"

# Theme unset — Starship (section 8) owns the prompt.
ZSH_THEME=""

# CHANGED: dropped the `z` plugin. zoxide (section 8) provides `z` and the two
# fight over the same command name.
plugins=(
  git
  herdr
  web-search
  copypath
)

ENABLE_CORRECTION="false"       # no "did you mean" autocorrect
COMPLETION_WAITING_DOTS="true"

source $ZSH/oh-my-zsh.sh

# ==============================================
# 2. HISTORY  (must come AFTER oh-my-zsh, which sets its own tiny defaults)
# ==============================================

HISTFILE="$HOME/.zsh_history"
HISTSIZE=200000
SAVEHIST=200000

setopt EXTENDED_HISTORY        # record timestamp + duration
setopt SHARE_HISTORY           # live-share history across all open panes
setopt HIST_IGNORE_ALL_DUPS    # a repeated command only appears once
setopt HIST_IGNORE_SPACE       # leading space = never written to disk
setopt HIST_REDUCE_BLANKS
setopt HIST_VERIFY             # expand !! and show it before running
setopt HIST_FCNTL_LOCK         # safer concurrent writes

# Reminder: prefix any command containing a token/key with a single space and
# it stays out of ~/.zsh_history entirely.

# ==============================================
# 3. ENVIRONMENT & PATHS
# ==============================================

export LANG=en_US.UTF-8
# CHANGED: BROWSER is executed as a command with the URL appended, so it must be
# an executable — not an app name. macOS `open` uses the default browser
# (Firefox). "open -a Safari" broke that (pi's MCP OAuth ran
# `open -a "open -a Safari" url` and failed).
export BROWSER="/usr/bin/open"

# druk blocks the terminal by nature, so no --wait flag needed
# (the old `code --wait` needed --wait or git commits aborted instantly).
export EDITOR='druk'
export VISUAL="$EDITOR"

export ENABLE_TOOL_SEARCH=true
export PI_ASK_USER_DISPLAY_MODE=inline

# pi-subagents tmux integration
export PI_SUBAGENT_MUX=tmux
export PI_SUBAGENT_ENABLE_SET_TAB_TITLE=1
export PI_SUBAGENT_RENAME_TMUX_WINDOW=1
export PI_SUBAGENT_SHELL_READY_DELAY_MS=1200

# Homebrew (Apple Silicon)
[[ -d "/opt/homebrew/bin" ]] && export PATH="/opt/homebrew/bin:$PATH"

# Ruby
export PATH="/opt/homebrew/opt/ruby/bin:$PATH"

# Bun
export BUN_INSTALL="$HOME/.bun"
export PATH="$BUN_INSTALL/bin:$PATH"
[[ -s "$HOME/.bun/_bun" ]] && source "$HOME/.bun/_bun"

# Local bins, antigravity (dupes collapse via typeset -U above)
export PATH="$HOME/.local/bin:$PATH"
export PATH="$HOME/.antigravity/antigravity/bin:$PATH"
export PATH="$HOME/.antigravity-ide/antigravity-ide/bin:$PATH"

# REMOVED: export DISPLAY=":0"
# On macOS this only matters with XQuartz running, and it makes some tools
# wrongly believe an X display is available. Add it back if you actually use X11.

# Secrets (ZAI_API_KEY etc). Sourced before the aliases that reference it.
[[ -f ~/.zshrc.secrets ]] && source ~/.zshrc.secrets

# ==============================================
# 4. PYTHON
# ==============================================

# Python runs via uv; pyenv removed (was only 3.10.13 + orphaned passport_bot env).


# ==============================================
# 5. ALIASES
# ==============================================

# --- shell management ---
alias zshconfig="$EDITOR ~/.zshrc"
alias gconfig="$EDITOR ~/.config/ghostty/config"
alias sconfig="$EDITOR ~/.config/starship.toml"
alias hconfig="$EDITOR ~/.config/herdr/config.toml"
alias cheat='open -a markemark ~/Desktop/cheatsheet.md'
alias reload="exec zsh"        # exec beats re-sourcing: no duplicated state
alias c="clear"
alias v="druk"

# --- modern replacements (brew install eza bat) ---
alias ls="eza --icons --group-directories-first"
alias ll="eza --icons --group-directories-first -l"
alias la="eza --icons --group-directories-first -la"
alias lt="eza --icons --tree --level=2"
alias cat="bat --paging=never --style=plain"   # no surprise pager in scripts

# --- search ---
alias rgi='command rg -i'
alias rgf='command rg --files'
alias rgh='command rg --hidden --glob "!.git"'

# --- git ---
alias gs='git status'
alias gp='git push'
alias gc='git commit -m'
alias gpl='git pull'
alias ga='git add'
alias gaa='git add --all'
alias gb='git branch'
alias gco='git checkout'
alias gcb='git checkout -b'
alias gd='git diff'
alias gl='git log --oneline --graph --decorate'
alias grh='git reset --hard'
alias gst='git stash'
alias gsp='git stash pop'
alias lg='lazygit'

# --- AI tooling ---
# NOTE the single quotes on glm: they defer variable expansion until the alias
# is *run*, so it still works if ~/.zshrc.secrets loads later or changes.
alias glm='ANTHROPIC_MODEL=GLM-4.7 ANTHROPIC_BASE_URL=$ZAI_BASE_URL ANTHROPIC_AUTH_TOKEN=$ZAI_API_KEY claude --dangerously-skip-permissions'

# --- herdr / remote ---
# Thin local client attached to the VPS Herdr server: panes and agents keep
# running there, the UI (theme, sidebar, keybindings) is drawn locally, and
# image paste is bridged from the local clipboard.
# Run it from a plain Ghostty surface — launching herdr inside a Herdr pane is
# blocked by default. To allow that, set experimental.allow_nested = true in
# ~/.config/herdr/config.toml.
alias hvps='herdr --remote vps'
alias claude="claude --dangerously-skip-permissions --model opusplan"
alias codex="codex --dangerously-bypass-approvals-and-sandbox"
alias gemini="NODE_NO_WARNINGS=1 gemini"
alias gem="gemini"

# Unaliased escape hatches, for when you're somewhere you don't want a yolo agent.
alias claude-safe='command claude'
alias codex-safe='command codex'

# --- antigravity ---
alias agm="antigravity --manager"
# CHECK THIS ONE: the original was `alias agy="agy --dangerously-skip-permissions"`,
# which is self-referential. If `agy` isn't a real binary on PATH, this never
# worked. Change `antigravity` below to whatever the real command is.
alias agy="antigravity --dangerously-skip-permissions"

# --- misc ---
alias tailscale="/Applications/Tailscale.app/Contents/MacOS/Tailscale"
alias sibyl-web="cd ~/Dev/Sibyl && uv run sibyl-web"
alias notes-publish='rsync -a --delete "$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/Elias'\''s Vault/Published/" ~/Dev/notes/content/ && cd ~/Dev/notes && npx quartz sync --no-pull'

# --- tmux (sessions that survive disconnect/reboot) ---
alias tl='tmux ls'                # what's running?
alias tn='tmux new -s'            # tn work
alias tt='tmux attach -t '        # tt work
alias pio='PI_ORCHESTRATOR_MODE=1 tmux new -A -s orchestrator "pi"'  # pi orchestrator session

# ==============================================
# 6. FUNCTIONS
# ==============================================

# Run the IRC bot from any directory, defaulting to the repo config.
ircbot() {
  uv run --project $HOME/Dev/irc_bot irc-bot "${@:-$HOME/Dev/irc_bot/bot_config.md}"
}

# Delete local branches whose remotes are gone.
gprune() {
  git fetch --prune
  local gone_branches
  gone_branches=$(git branch -vv | grep ': gone]' | grep -vE '^[*+] ' | awk '{print $1}')
  if [ -n "$gone_branches" ]; then
    echo "Deleting local branches that are gone on remote:"
    echo "$gone_branches"
    echo "$gone_branches" | xargs git branch -d
  else
    echo "No gone branches to prune."
  fi
}

# Make a directory and cd into it.
mkcd() { mkdir -p "$1" && cd "$1"; }

# ==============================================
# 7. SSH / KEYCHAIN
# ==============================================

# CHANGED: added the interactive guard. `security unlock-keychain` prompts for a
# password, so without `-o interactive` any non-interactive `ssh host 'cmd'`
# hangs forever waiting on stdin.
if [[ -n "$SSH_CONNECTION" && -o interactive ]]; then
  security unlock-keychain ~/Library/Keychains/login.keychain-db
fi

# ==============================================
# 8. TOOLS — ORDER IN THIS SECTION MATTERS
# ==============================================

# --- 8.1 fzf keybindings (ctrl-r, ctrl-t, alt-c) ---
export FZF_DEFAULT_OPTS="--height 40% --layout=reverse --border --info=inline"
if command -v fd >/dev/null 2>&1; then
  export FZF_DEFAULT_COMMAND='fd --type f --hidden --follow --exclude .git'
  export FZF_CTRL_T_COMMAND="$FZF_DEFAULT_COMMAND"
  export FZF_ALT_C_COMMAND='fd --type d --hidden --follow --exclude .git'
fi
command -v fzf >/dev/null 2>&1 && source <(fzf --zsh)

# --- 8.2 fzf-tab ---
# This zstyle is REQUIRED by fzf-tab and was missing: oh-my-zsh enables zsh's
# own menu selection, which shadows fzf-tab's UI.
zstyle ':completion:*' menu no
zstyle ':completion:*' matcher-list 'm:{a-zA-Z}={A-Za-z}'   # case-insensitive
zstyle ':fzf-tab:complete:cd:*' fzf-preview 'eza -1 --icons --color=always $realpath'
zstyle ':fzf-tab:complete:__zoxide_z:*' fzf-preview 'eza -1 --icons --color=always $realpath'
zstyle ':fzf-tab:*' switch-group '<' '>'

# completion appearance
zstyle ':completion:*' list-colors ${(s.:.)LS_COLORS}
zstyle ':completion:*' group-name ''
[[ -f "/opt/homebrew/opt/fzf-tab/share/fzf-tab/fzf-tab.zsh" ]] && \
  source "/opt/homebrew/opt/fzf-tab/share/fzf-tab/fzf-tab.zsh"

# --- 8.3 zoxide (provides `z`) ---
command -v zoxide >/dev/null 2>&1 && eval "$(zoxide init zsh)"

# --- 8.4 prompt ---
command -v starship >/dev/null 2>&1 && eval "$(starship init zsh)"

# --- 8.5 autosuggestions + syntax highlighting (must load LAST) ---
ZSH_AUTOSUGGEST_STRATEGY=(history)
ZSH_AUTOSUGGEST_MANUAL_REBIND=1        # measurably faster on long command lines
ZSH_AUTOSUGGEST_BUFFER_MAX_SIZE=20

[[ -f /opt/homebrew/share/zsh-autosuggestions/zsh-autosuggestions.zsh ]] && \
  source /opt/homebrew/share/zsh-autosuggestions/zsh-autosuggestions.zsh
[[ -f /opt/homebrew/opt/zsh-fast-syntax-highlighting/share/zsh-fast-syntax-highlighting/fast-syntax-highlighting.plugin.zsh ]] && \
  source /opt/homebrew/opt/zsh-fast-syntax-highlighting/share/zsh-fast-syntax-highlighting/fast-syntax-highlighting.plugin.zsh

# ==============================================
# 9. KEYBINDINGS  (after the plugins that define the widgets)
# ==============================================

bindkey '^ '   autosuggest-accept       # ctrl+space: accept whole suggestion
bindkey '^[[A' history-substring-search-up   2>/dev/null
bindkey '^[[B' history-substring-search-down 2>/dev/null
bindkey '^[[1;5C' forward-word          # ctrl+right
bindkey '^[[1;5D' backward-word         # ctrl+left

# zprof   # uncomment with the zmodload at the top to profile startup
# TinyFish API key — stored in macOS Keychain (service "tinyfish-api-key"), not in this file.
# Add/update with: security add-generic-password -s tinyfish-api-key -a tinyfish -w '<key>' -U
if command -v security >/dev/null 2>&1; then
  TINYFISH_API_KEY="$(security find-generic-password -s tinyfish-api-key -a tinyfish -w 2>/dev/null || true)"
  if [ -n "$TINYFISH_API_KEY" ]; then export TINYFISH_API_KEY; fi
fi
