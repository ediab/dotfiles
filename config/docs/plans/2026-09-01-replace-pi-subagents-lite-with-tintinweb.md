# Replace pi-subagents-lite with @tintinweb/pi-subagents

## Goal

Swap the currently installed `pi-subagents-lite` package for `@tintinweb/pi-subagents`, carrying over the agent definitions and tuned behavior so day-to-day usage feels the same (or better), and keeping `~/dev/pi-dotfiles` as the source of truth.

## Context

- pi 0.84.4 — meets tintinweb's `>= 0.84.0` peer requirement.
- Currently installed: `npm:pi-subagents-lite` in `~/.pi/agent/settings.json` packages list.
- Agent definitions live in `~/.pi/agent/agents/*.md` (Explore, general-purpose, reviewer). Tintinweb reads the same directory with a compatible frontmatter format — these files work as-is.
- Existing lite config (`subagents-lite.json`) and its tuned behaviors that need a tintinweb equivalent:
  - `general-purpose` mapped to model `opencode-go/ox-alpha-free` → tintinweb: create `~/.pi/agent/agents/general-purpose.md` override with `model: opencode-go/ox-alpha-free`.
  - `defaultMaxTurns: 40` → tintinweb: `defaultMaxTurns: 40` in `~/.pi/agent/subagents.json`.
  - `forceBackground: false` → dropped: keep tintinweb's `backgroundByDefault: true` (Claude Code-style background default).
  - `loadSkillsImplicitly: false` → tintinweb `skills: false` frontmatter in every agent file.
  - `loadExtensionsImplicitly: false` → tintinweb `extensions: false` frontmatter in every agent file.
  - `systemPromptMode: replace` → tintinweb's frontmatter `prompt_mode` defaults to `replace` — no action needed.
- Tintinweb ships 3 built-ins (general-purpose, Explore, Plan). The existing `Explore.md` and `general-purpose.md` files override the built-ins by name; Plan is new.
- pi-dotfiles flow: `home/settings.json` is the repo's source of truth; `rebuild.sh` copies repo → live (settings.json, agents, subagents-lite.json, models.json, prompts). `sync-settings.sh` auto-commits live → repo settings.json changes.
- Other pi sessions may be running; pi reads packages at session start, so removal/addition takes effect on new sessions.

## Approach

One `pi uninstall` + `pi install`, write a small `~/.pi/agent/subagents.json` for tuned defaults, add one agent-override file, remove the obsolete `subagents-lite.json`, and mirror everything in `~/dev/pi-dotfiles`.

## Steps

1. **Pre-flight** — commit any uncommitted pi-dotfiles changes (clean diff for review).
2. **Swap the package** — `pi uninstall pi-subagents-lite` then `pi install npm:@tintinweb/pi-subagents` (updates `~/.pi/agent/settings.json` packages list; `pi install` runs sync-settings.sh via launchd → auto-commits repo `home/settings.json`).
3. **Write `~/.pi/agent/subagents.json`** (global defaults, hand-edited per tintinweb docs):
   ```json
   {
     "defaultMaxTurns": 40
   }
   ```
   Turn limit carried over; `backgroundByDefault` stays at tintinweb's default (`true`). Everything else default.
4. **Update agent files** — add `skills: false` and `extensions: false` frontmatter to all three existing files (`Explore.md`, `general-purpose.md`, `reviewer.md`), matching lite's implicit-loading-off. Rewrite `general-purpose.md` to also pin `model: opencode-go/ox-alpha-free`, overriding the built-in and replacing lite's model mapping. Note: the `Plan` built-in has no file, so it keeps default skill/extension loading; override it later only if it's actually used.
5. **Delete obsolete config** — `rm ~/.pi/agent/subagents-lite.json`, and remove its copy step + file from `~/dev/pi-dotfiles` (bootstrap.sh, rebuild.sh, home/subagents-lite.json).
6. **Mirror to pi-dotfiles** — copy `~/.pi/agent/subagents.json` → `home/subagents.json`; add `home/agents/general-purpose.md`; update bootstrap.sh/rebuild.sh to deploy `subagents.json`; commit.
7. **Verify** (see below), then run `~/dev/pi-dotfiles/rebuild.sh --sync-only` to confirm idempotent re-deploy.

## Verification

- `pi install` output lists `@tintinweb/pi-subagents`; `settings.json` no longer references `pi-subagents-lite`.
- New pi session: `/agents` shows agent types including `general-purpose` (with the ox-alpha-free model), `Explore`, `reviewer`, `Plan`.
- In a new session: spawn an Explore agent (e.g. "use the Explore agent to list the files in this repo") → runs in background, call returns an ID, completion notification arrives (confirms `backgroundByDefault: true`).
- Spawn a trivial task with an extension-dependent expectation absent (e.g. Explore listing files) → confirms `extensions: false`/`skills: false` didn't break built-in tools (read/grep/find/bash/ls still available).
- Spawn a general-purpose agent on a trivial task → completes within ~40 turns, uses `opencode-go/ox-alpha-free` (visible in `/agents` or tool result).
- `pi-dotfiles` diff shows: settings.json updated (auto), subagents.json added + deployed by rebuild.sh, general-purpose.md added, subagents-lite.json references gone.

## Open Questions

- None blocking. Deferred by choice: `workflowsEnabled` pin (auto-standdown handles conflicts with other workflow tools).
