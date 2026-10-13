# Work setup: what changed today (2026-10-13)

Temporary; delete once the work setup is updated. Personal dotfiles commits `25db045` → `faa433f`. Use as a checklist to mirror at work.

## Target model

- **BB is the multi-agent hub.** Delegation happens only inside BB, as child threads. Standalone Pi is a single agent: no subagents, no agent-to-agent messaging, reviews stay inline.
- **One agent works end to end.** Extra agents only on request: one helper by default, two at most.
- **One `AGENTS.md` for every client.** The same file is linked into Pi, Claude and Codex. It holds policy only; procedures live in skills. Tool-specific rules go in the tool's own config.
- **Memory lives in the repo.** A versioned root `MEMORY.md` in each repo, read by every client inside and outside BB. BB memory is only for cross-project preferences. Per-tool memory is off.
- **Lean context.** No large SessionStart hook output; nothing loads that only one tool needs.

## 1. Global `AGENTS.md` (Pi, Claude, Codex)

- Removed the **Jev** section completely.
- **Browser section** is now generic. Lightpanda's rules moved into its MCP `description` in Pi's `mcp.json`, so only Pi sees them.
- **Delegation** is shortened to three bullets: BB child threads; standalone Pi single-agent; the orchestrator checks results.
- Removed duplicate lines: the "owner source-checks subagent claims" line and the "procedures live in skills" line in Context.
- Added a **Project memory** section.

Final file (copy as a base):

```md
# Global agent policy

Short policy, loaded every turn. Procedures live in skills — open the matching skill when the task needs it.

## Style
* Match my writing style: direct, concise, warm, and practical. Lead with the point, avoid unnecessary ceremony, and include enough context to explain constraints and next steps. Adjust formality and detail to the audience.

## Research
* Verify current or uncertain external facts from primary sources.
* Prefer the `context7` MCP server for library/API documentation — it returns current, version-pinned docs.

## Browser automation
* Use the client's search/fetch tools for ordinary search and reading (pi-web-access in Pi).
* Use a browser tool only for JavaScript-dependent pages, interaction, or visual rendering; prefer compact page structure and targeted extraction over full HTML.
* Close explicitly created browsing sessions when finished.

## Skills
* When a task matches a skill's description, read and follow that skill before acting.
* Do not copy skill procedures into this file.
* Create new personal skills in `~/.agents/skills/<name>`.

## Delegation and orchestration
* Launch agents or reviewers only when the user requests delegation or explicitly invokes a workflow that authorizes it. An ordinary review request stays inline; having the tools is not permission.
* Delegated workers return requests to their owner rather than delegating further. One orchestrator at a time; it checks delegated results against the sources.
* Inside BB, delegate via BB child threads and BB messaging. Standalone Pi stays single-agent, including reviews.

## Changes
* Preserve unrelated user changes; do not overwrite or revert them.
* Run the relevant check before reporting done; report checks that could not be run.
* A passing test suite is not proof a live service works.

## Context
* Project `AGENTS.md` / `CLAUDE.md` files layer on top of this file and take precedence where they are more specific.

## Project memory
* If the repository root has `MEMORY.md`, read it before starting work.
* Use the repository's versioned `MEMORY.md` as the single home for durable, verified facts that the code and docs don't show: operational paths, deploy or recovery steps, gotchas, decisions. Create it when there is something worth retaining; commits still require authorization. Never secrets, transient status, guesses, or anything already in `AGENTS.md`.
* Keep it short: update or remove stale entries rather than appending.
```

## 2. BB

- **New BB-only instructions** in `~/.bb/AGENTS.md`, kept in the repo as `bb/AGENTS.md` and copied into place manually:

  ```md
  # BB preferences

  ## Questions
  For necessary clarification questions in BB, prefer BB's `AskUserQuestion` tool when available; otherwise ask in chat. Leave Pi's `ask_user_question` tool for standalone terminal sessions.

  ## Memory
  Repository knowledge follows the global `MEMORY.md` policy, including inside BB. Do not create duplicate BB project memories for repository facts. Reserve BB memory for cross-project preferences and BB-wide operational facts, using global scope.
  ```

- Uninstalled the **agent-board** plugin. Removed sidebar panel and footer entries for plugins that aren't installed or are disabled (agent-board, file-manager, graph-studio, simple-notes, tasks, automations, provider-usage).
- **BB telemetry is off.**
- Removed the BB user skills **`bb-pi-control`** and **`bb-pi-health`** from `~/.bb/skills`. They were mostly "read BB's own skills first" wrappers.
- `diff-review` is the review skill inside BB and is **not** shared with the standalone clients. `ui-audit` and `web-design` now point to it.

## 3. Pi

**Packages**
- Removed **`pi-herdsman`**, **`pi-intercom`** and **`pi-review`** (multi-agent and review packages). Earlier today I also removed **`pi-extmgr`**, **`ponytail`** and **`@saccolabs/pi-claude-cli`**.
- Seven packages remain, **pinned to exact versions** in `settings.json`: `pi-web-access`, `@ff-labs/pi-fff`, `pi-code-previews`, `@juicesharp/rpiv-ask-user-question`, `@narumitw/pi-btw`, `pi-powerline-footer` and `pi-title`. The pins cover direct packages only, not their dependencies.

**Question and title packages load only outside BB**, because BB owns questions and thread titles. Their autoload is disabled in `settings.json` with `{"source": "npm:<pkg>@<ver>", "extensions": []}`, and a small extension `extensions/standalone-ui.ts` loads them only when `BB_THREAD_ID` is unset:

```ts
import { join } from "node:path";
import { getAgentDir, type ExtensionAPI } from "@earendil-works/pi-coding-agent";
export default async function standaloneUI(pi: ExtensionAPI): Promise<void> {
	if (process.env.BB_THREAD_ID) return;
	for (const name of ["@juicesharp/rpiv-ask-user-question", "pi-title"]) {
		const { default: register } = await import(join(getAgentDir(), "npm", "node_modules", name, "index.ts"));
		await register(pi);
	}
}
```

**MCP** (`~/.pi/agent/mcp.json`, all `"exposure": "codemode"`)
- Added **Lightpanda** (`lightpanda mcp --obey-robots`, telemetry and core dumps disabled). Its usage rules are in its `description`: text and page structure only, never screenshots; refresh structure after navigation; close sessions.
- Added **Fastmail**.
- **context7** is unchanged.

**Other**
- `pi-fff.json`: `{"enableHomeDirScanning": false}`.
- Archived the custom **Pi memory extension** and replaced it with the `MEMORY.md` rule. I moved the old notes into each repo's `MEMORY.md` and committed them.
- Archived the orchestration skill and agent profiles (implementer, researcher, reviewer, tester).

**Live clean-up** (outside git; check for the same leftovers at work)
- Deleted the leftover folders from removed packages in `~/.pi/agent/`: `pi-herdsman`, `intercom`, `missions`, `pi-blackhole`, `.extmgr-cache`, `run-history.jsonl` and `commandcode-models.json`.
- Run `npm ls --depth=0` in `~/.pi/agent/npm`. Removed packages can linger there (ponytail did), along with empty `@scope` folders.
- Deleted old Pi releases in `~/.pi/agent/install/releases/`, keeping only the current one.
- Check whether `~/.pi/agent/sessions` is a symlink. Here it pointed into the old oh-my-pi folder (`~/.omo`), so Pi sessions were stored there. Fixed by moving the sessions into a real `~/.pi/agent/sessions` folder and deleting `~/.omo` (1.2 GB).

## 4. Shared skills (`~/.agents/skills`, linked into Pi, Codex and Claude)

- **Deleted:** `code-review` and `personal-workflow/DELEGATION.md`.
- **`personal-workflow`:** delegation is now a short "Extra agents" section:
  - Default to one helper, at most two, and only for independent work with a checkable result.
  - Inside BB, use a child thread created with `--parent-self` and a self-contained brief: goal, baseline, owned paths, exclusions, checks, and "report only, no further delegation".
  - The main agent stays the owner: it integrates, verifies and runs the final checks. Report-only reviewers may share the checkout; concurrent writers need separate worktrees.
  - Yield to completion notifications instead of polling. Higher risk means stronger verification, not more implementers.
- **`handoff` renamed to `pi-handoff`** so it doesn't shadow BB's `handoff`. Pi's version writes a portable summary; BB's version moves sessions.
- **`implement`:** TDD is now opt-in explicitly.
- **Kept on purpose:** the planning and grilling skills (`grill-*`, `ask-matt`, `brainstorm`, `to-spec`, `to-tickets`, `wayfinder`) and the skills standalone Pi needs even though BB has similar ones (`pi-handoff`, `frontend-design`, `show-me`).

## 5. Codex

- `[features] memories = false`, and removed the `[memories]` table.
- Removed the **`lavish-axi` SessionStart hook**, whose output was about 2.3k tokens per session. The tool still works when called directly.
- Hook trust (`[hooks.state."…hooks.json:session_start:N:0"]`) is keyed by **list position**. When you remove a hook, renumber the remaining trust entries or Codex asks you to re-trust them.

## 6. Claude

- I didn't change it. The `lavish-axi` SessionStart hook is still there; consider removing it at work for the same token saving.

## Checklist for work

- [ ] Replace the global `AGENTS.md` with the version above, keeping work-specific sections.
- [ ] Add `~/.bb/AGENTS.md` (questions and memory scope).
- [ ] Pi: remove the multi-agent and review packages; pin the rest; add `standalone-ui.ts` with `extensions: []` for the question and title packages.
- [ ] Pi: move tool-specific rules into MCP `description`s.
- [ ] Retire any per-tool memory (Pi extension, Codex memories); start `MEMORY.md` per repo.
- [ ] Drop `lavish-axi` (and other noisy) SessionStart hooks; re-key the Codex hook trust entries.
- [ ] Remove the `code-review` skill, any `bb-pi-*` skills and `DELEGATION.md`; add the "Extra agents" section; rename `handoff` to `pi-handoff`.
- [ ] BB: uninstall unused plugins, clean the sidebar keys, turn telemetry off.
- [ ] Clean `~/.pi/agent`: leftover folders, orphan npm packages, old releases, and a `sessions` symlink if there is one.
- [ ] Start fresh Pi, BB, Codex and Claude sessions afterwards.
