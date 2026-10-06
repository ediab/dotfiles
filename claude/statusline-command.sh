#!/usr/bin/env bash
# Claude Code two-line statusline.
#   line 1: cwd · git branch [status] · worktree/agent/vim        model · effort
#   line 2: context bar · 5h/7d limits · cost · lines · duration · cache
# Nerd Font glyphs by default; set CC_SL_NERD=0 for plain Unicode. Runs on bash 3.2 (macOS default).

input=$(cat)

# ---------- icons ----------
if [ "${CC_SL_NERD:-1}" = 1 ]; then
  I_DIR=$'' I_GIT=$'' I_WT=$'' I_CTX=$'' I_COST=$'' I_TIME=$''
  I_MODEL=$'' I_LIM=$'' I_CACHE=$''
else
  I_DIR="" I_GIT="⎇" I_WT="wt:" I_CTX="" I_COST="" I_TIME=""
  I_MODEL="" I_LIM="" I_CACHE=""
fi

# ---------- colors ----------
R=$'\e[0m' B=$'\e[1m' D=$'\e[2m'
RED=$'\e[31m' GRN=$'\e[32m' YEL=$'\e[33m' BLU=$'\e[34m' MAG=$'\e[35m' CYN=$'\e[36m'

# ---------- extract fields (one jq call) ----------
eval "$(printf '%s' "$input" | jq -r '
  @sh "cwd=\(.workspace.current_dir // .cwd // "")",
  @sh "model=\(.model.display_name // "")",
  @sh "effort=\(.effort.level // "")",
  @sh "fast=\(.fast_mode // false)",
  @sh "ctx_pct=\(.context_window.used_percentage // "")",
  @sh "ctx_used=\(.context_window.total_input_tokens // "")",
  @sh "ctx_size=\(.context_window.context_window_size // "")",
  @sh "cost=\(.cost.total_cost_usd // "")",
  @sh "dur_ms=\(.cost.total_duration_ms // "")",
  @sh "l_add=\(.cost.total_lines_added // 0)",
  @sh "l_del=\(.cost.total_lines_removed // 0)",
  @sh "h5=\(.rate_limits.five_hour.used_percentage // "")",
  @sh "h5_reset=\(.rate_limits.five_hour.resets_at // "")",
  @sh "d7=\(.rate_limits.seven_day.used_percentage // "")",
  @sh "cache_obs=\(.prompt_cache.caching_observed // false)",
  @sh "cache_warm=\(.prompt_cache.warm // false)",
  @sh "cache_hit=\(.prompt_cache.hit_ratio // "")",
  @sh "vim=\(.vim.mode // "")",
  @sh "agent=\(.agent.name // "")",
  @sh "wt=\(.worktree.name // .workspace.git_worktree // "")"
' 2>/dev/null)"

# ---------- helpers ----------
# stress color: green < 50, yellow < 80, red otherwise (override thresholds via $2 $3)
stress() { local p=${1%.*}; p=${p:-0}
  if   [ "$p" -ge "${3:-80}" ]; then printf '%s' "$RED"
  elif [ "$p" -ge "${2:-50}" ]; then printf '%s' "$YEL"
  else printf '%s' "$GRN"; fi; }

fmt_tok() { local n=${1%.*}; n=${n:-0}
  if   [ "$n" -ge 1000000 ]; then awk -v n="$n" 'BEGIN{printf "%.1fM", n/1e6}'
  elif [ "$n" -ge 1000 ];    then printf '%dk' $((n / 1000))
  else printf '%d' "$n"; fi; }

fmt_dur() { local s=$(($1 / 1000))
  if   [ "$s" -ge 3600 ]; then printf '%dh%02dm' $((s / 3600)) $((s % 3600 / 60))
  elif [ "$s" -ge 60 ];   then printf '%dm' $((s / 60))
  else printf '%ds' "$s"; fi; }

rep() { local o="" i=0; while [ "$i" -lt "$2" ]; do o+="$1"; i=$((i + 1)); done; printf '%s' "$o"; }

# ---------- git (cached 5s per directory) ----------
git_seg=""
if [ -n "$cwd" ] && git -C "$cwd" rev-parse --git-dir >/dev/null 2>&1; then
  key=$(printf '%s' "$cwd" | cksum | cut -d' ' -f1)
  cache="${TMPDIR:-/tmp}/cc_sl_git_${key}"
  now=$(date +%s)
  if [ "$(uname)" = Darwin ]; then
    mtime=$(stat -f %m "$cache" 2>/dev/null || echo 0)
  else
    mtime=$(stat -c %Y "$cache" 2>/dev/null || echo 0)
  fi
  if [ $((now - mtime)) -ge 5 ]; then
    GIT_OPTIONAL_LOCKS=0 git -C "$cwd" status --porcelain=v2 --branch --show-stash 2>/dev/null | awk '
      /^# branch.head/ { head=$3 }
      /^# branch.oid/  { oid=substr($3,1,7) }
      /^# branch.ab/   { a=substr($3,2); b=substr($4,2) }
      /^# stash/       { st=$3 }
      /^[12] /         { x=substr($2,1,1); y=substr($2,2,1); if (x!=".") s++; if (y!=".") m++ }
      /^u /            { c++ }
      /^\? /           { u++ }
      END { if (head=="(detached)") head="HEAD@" oid
            printf "%d|%d|%d|%d|%d|%d|%d|%s\n", s, m, u, c, st, a, b, head }' > "$cache.tmp.$$" \
      && mv "$cache.tmp.$$" "$cache"
  fi
  # head goes last: read hands the rest of the line to it, so a | in a branch name is safe.
  IFS='|' read -r g_s g_m g_u g_c g_st g_a g_b g_head < "$cache"
  flags=""
  [ "${g_c:-0}" -gt 0 ] && flags+="${RED}=${g_c}${R} "
  [ "${g_m:-0}" -gt 0 ] && flags+="${YEL}!${g_m}${R} "
  [ "${g_s:-0}" -gt 0 ] && flags+="${GRN}+${g_s}${R} "
  [ "${g_u:-0}" -gt 0 ] && flags+="${D}?${g_u}${R} "
  [ "${g_st:-0}" -gt 0 ] && flags+="${D}≡${g_st}${R} "
  if   [ "${g_a:-0}" -gt 0 ] && [ "${g_b:-0}" -gt 0 ]; then flags+="${YEL}⇕${g_a}/${g_b}${R} "
  elif [ "${g_a:-0}" -gt 0 ]; then flags+="${GRN}⇡${g_a}${R} "
  elif [ "${g_b:-0}" -gt 0 ]; then flags+="${YEL}⇣${g_b}${R} "; fi
  git_seg="${BLU}${I_GIT} ${g_head}${R}"
  [ -n "$flags" ] && git_seg+=" ${D}[${R}${flags% }${D}]${R}"
fi

# ---------- line 1 ----------
SEP=" ${D}│${R} "
l1=()
dir_name=$(basename "${cwd:-?}")
parent=$(basename "$(dirname "${cwd:-?}")")
[ "$parent" != "/" ] && [ "$parent" != "$(basename "$HOME")" ] && dir_name="$parent/$dir_name"
[ -n "$cwd" ] && l1+=("${CYN}${B}${I_DIR:+$I_DIR }${dir_name}${R}")
[ -n "$git_seg" ] && l1+=("$git_seg")
[ -n "$wt" ]    && l1+=("${MAG}${I_WT}${wt}${R}")
[ -n "$agent" ] && l1+=("${MAG}@${agent}${R}")
[ -n "$vim" ]   && l1+=("${D}${vim}${R}")

m=""
[ -n "$model" ] && m="${MAG}${B}${I_MODEL:+$I_MODEL }${model}${R}"
[ -n "$effort" ] && m+="${D} · ${R}${effort}"
[ "$fast" = true ] && m+=" ${YEL}⚡${R}"
[ -n "$m" ] && l1+=("$m")

# ---------- line 2 ----------
l2=()
if [ -n "$ctx_pct" ]; then
  pct=${ctx_pct%.*}; pct=${pct:-0}
  w=10; filled=$(( (pct * w + 50) / 100 )); [ "$filled" -gt "$w" ] && filled=$w
  c=$(stress "$pct")
  bar="${c}$(rep █ "$filled")${D}$(rep ░ $((w - filled)))${R}"
  seg="${I_CTX:+$c$I_CTX$R }${bar} ${c}${pct}%${R}"
  [ -n "$ctx_used" ] && [ -n "$ctx_size" ] && seg+="${D} · ${R}$(fmt_tok "$ctx_used")${D}/${R}$(fmt_tok "$ctx_size")"
  l2+=("$seg")
fi

if [ -n "$h5" ]; then
  seg="${D}${I_LIM:+$I_LIM }5h${R} $(stress "$h5" 70 90)${h5%.*}%${R}"
  if [ -n "$h5_reset" ]; then
    left=$(( h5_reset - $(date +%s) ))
    if [ "$left" -gt 0 ]; then
      if [ "$left" -ge 3600 ]; then seg+="${D} ↻$((left / 3600))h$(printf '%02d' $((left % 3600 / 60)))m${R}"
      else seg+="${D} ↻$((left / 60))m${R}"; fi
    fi
  fi
  l2+=("$seg")
fi
[ -n "$d7" ] && l2+=("${D}7d${R} $(stress "$d7" 70 90)${d7%.*}%${R}")

[ -n "$cost" ] && l2+=("${YEL}${I_COST:+$I_COST }\$$(printf '%.2f' "$cost")${R}")
{ [ "${l_add:-0}" -gt 0 ] || [ "${l_del:-0}" -gt 0 ]; } && l2+=("${GRN}+${l_add}${R} ${RED}−${l_del}${R}")
[ -n "$dur_ms" ] && [ "${dur_ms%.*}" -gt 0 ] && l2+=("${D}${I_TIME:+$I_TIME }$(fmt_dur "${dur_ms%.*}")${R}")

if [ "$cache_obs" = true ]; then
  if [ "$cache_warm" = true ] && [ -n "$cache_hit" ]; then
    hp=$(awk -v h="$cache_hit" 'BEGIN{printf "%d", h*100}')
    # inverted stress: high hit rate is good
    if   [ "$hp" -ge 70 ]; then cc=$GRN; elif [ "$hp" -ge 40 ]; then cc=$YEL; else cc=$RED; fi
    l2+=("${D}${I_CACHE:+$I_CACHE }cache${R} ${cc}${hp}%${R}")
  else
    l2+=("${D}${I_CACHE:+$I_CACHE }cache${R} ${YEL}cold${R}")
  fi
fi

# ---------- render ----------
join() { local out="" p; for p in "$@"; do out+="${out:+$SEP}$p"; done; printf '%s' "$out"; }
printf '%s\n' "$(join "${l1[@]}")"
[ ${#l2[@]} -gt 0 ] && printf '%s\n' "$(join "${l2[@]}")"
exit 0
