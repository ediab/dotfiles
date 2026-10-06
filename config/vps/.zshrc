# Powerlevel10k instant prompt. Keep this near the top of ~/.zshrc.
if [[ -r "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh" ]]; then
  source "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh"
fi

export ZSH="$HOME/.oh-my-zsh"
ZSH_THEME="powerlevel10k/powerlevel10k"

plugins=(
  git
  z
  zsh-autosuggestions
  zsh-syntax-highlighting
  web-search
  copypath
)

DISABLE_UNTRACKED_FILES_DIRTY="true"
ENABLE_CORRECTION="false"
COMPLETION_WAITING_DOTS="true"

if [[ -d "$ZSH" ]]; then
  source "$ZSH/oh-my-zsh.sh"
fi

export LANG="en_US.UTF-8"
export PATH="$HOME/.local/bin:$PATH"

if command -v code >/dev/null 2>&1; then
  export EDITOR="code"
elif command -v druk >/dev/null 2>&1; then
  export EDITOR="druk"
elif command -v vim >/dev/null 2>&1; then
  export EDITOR="vim"
else
  export EDITOR="nano"
fi

if [[ -d "$HOME/.bun/bin" ]]; then
  export BUN_INSTALL="$HOME/.bun"
  export PATH="$BUN_INSTALL/bin:$PATH"
fi

if command -v pyenv >/dev/null 2>&1; then
  export PYENV_ROOT="$HOME/.pyenv"
  export PATH="$PYENV_ROOT/bin:$PATH"
  eval "$(pyenv init --path)"
  eval "$(pyenv init -)"
  if command -v pyenv-virtualenv-init >/dev/null 2>&1; then
    eval "$(pyenv virtualenv-init -)"
  fi
fi

if command -v conda >/dev/null 2>&1; then
  __conda_setup="$(conda shell.zsh hook 2>/dev/null)"
  if [[ $? -eq 0 ]]; then
    eval "$__conda_setup"
  fi
  unset __conda_setup
  conda config --set auto_activate_base false >/dev/null 2>&1 || true
fi

# Keep terminal erase and delete behavior consistent across SSH clients.
if [[ -o interactive ]]; then
  stty erase '^?' 2>/dev/null
  bindkey '^?' backward-delete-char
  bindkey '^H' backward-delete-char
fi

alias zshconfig='$EDITOR ~/.zshrc'
alias reload='source ~/.zshrc'
alias c='clear'

if command -v eza >/dev/null 2>&1; then
  alias ls='eza --icons --group-directories-first'
  alias ll='eza --icons --group-directories-first -l'
  alias la='eza --icons --group-directories-first -la'
elif command -v exa >/dev/null 2>&1; then
  alias ls='exa --icons --group-directories-first'
  alias ll='exa --icons --group-directories-first -l'
  alias la='exa --icons --group-directories-first -la'
fi

if command -v bat >/dev/null 2>&1; then
  alias cat='bat'
elif command -v batcat >/dev/null 2>&1; then
  alias cat='batcat'
fi

alias gemini='NODE_NO_WARNINGS=1 gemini'
alias gem='gemini'
alias lg='lazygit'
alias agm='antigravity --manager'
alias agy='agy --dangerously-skip-permissions'

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


[[ -f "$HOME/.p10k.zsh" ]] && source "$HOME/.p10k.zsh"


# nvm
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"

# opencode
[ -d "$HOME/.opencode/bin" ] && export PATH="$HOME/.opencode/bin:$PATH"

# bun completions
[ -s "$HOME/.bun/_bun" ] && source "$HOME/.bun/_bun"

# bun
export BUN_INSTALL="$HOME/.bun"
export PATH="$BUN_INSTALL/bin:$PATH"

# Homebrew
[ -x /home/linuxbrew/.linuxbrew/bin/brew ] && eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv zsh)"
