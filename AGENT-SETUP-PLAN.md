# AI coding setup: approved implementation plan

Date: 17 October 2026.
Status: implemented on 17 October 2026. The configuration changes are in Git history; the VPS Claude Code live-session check remains blocked by an expired sign-in.

## Start here

Read this file, `agents/AGENTS.md`, `README.md`, `bb/README.md`, and the local-env skill before implementation. Read root `MEMORY.md` if one exists then. Inspect the current files and installed versions rather than assuming the audit snapshot is still current.

The user approved the direction below and asked to save it for a new session. Do not reopen settled preferences. Obtain a fresh instruction to begin implementation. Follow the normal approval rules for pushing, deployment, destructive operations, and credential changes; this document is not permission to perform those actions automatically.

### Agreed decisions: do not change these

1. Keep **BB + Pi** as the primary setup. Do not migrate to another interface or agent framework.
2. **Optimise the Mac first.** Record intended provider configuration in Git, then make the VPS follow it, preserving Linux-specific paths and excluding Mac desktop integrations and credentials.
3. **Keep existing permission settings and terminal aliases unchanged in this pass.** The user does not want repeated permission prompts. Do not remove broad Codex trust entries, introduce a sandbox, or add permission middleware as part of this work.
4. **Leave OpenCode model limits unchanged.** Do not remove or alter the DeepSeek Free context/output override. Leave the rest of OpenCode configuration alone unless a separate request authorizes changes.
5. **All pstack execution uses Pi.** Inside BB, every pstack worker is a BB child thread using provider `pi`. No Anthropic model calls, Claude Code workers, Codex workers, or automatic provider fallback for pstack.
6. Keep Claude Code and Codex available for separately chosen work, but remove their native pstack installations after Pi-only validation succeeds.
7. One agent is the ordinary default. General engineering principles and orchestration workflows are explicitly requested, not automatic prerequisites for routine work.
8. Use Impeccable as the default UI workflow. Keep Interface Design available when explicitly selected. Do not run both workflows for one task or maintain competing design records.
9. Disable Fastmail globally in Pi, retaining its configuration and credentials for explicit use when required. Do not revoke credentials or change OAuth scopes.
10. Remove silent startup relinking rather than replacing it with an automatic logged mutation.
11. Keep the existing meaningful-test policy, repository `MEMORY.md` policy, native compaction, and approval requirements for consequential external actions.
12. Keep upstream pstack unmodified. Use supported configuration and the personal BB adapter, not a fork or patches to installed files.

## Why this work exists

The review found concrete configuration drift and maintenance risks, not a reason to replace the whole stack. The intended result is a strong single agent, useful specialist skills, direct behavioral verification, and selective review. Do not replace removed complexity with a new orchestration or configuration-management framework.

The original audit was read-only. It inspected both machines, installed sources, BB settings, upstream changes, documentation, and research. No worker smoke tests or destructive cleanup reproductions were run.

## Baseline observed during the audit

Recheck these facts at implementation time:

- Both dotfiles checkouts and GitHub HEAD were at `47a31e6c1c1d7ff644d9a9839dfcd4407a4af279`.
- Both hosts had Pi `1.3.0`, Claude Code `2.1.301`, Codex CLI `0.163.0`, and OpenCode `1.19.2`.
- Active BB server: `0.46.1` on the VPS. The standalone SSH `bb` command reported `0.46.0`; the Mac BB CLI reported `0.46.1`.
- Mac installed pstack `0.9.86` in Pi, Claude Code, and Codex. VPS installed it in Pi and Codex, but not Claude Code despite enabled configuration.
- Mac had provider-specific Impeccable copies. VPS lacked the native Pi and Claude copies. The shared Codex copy existed; Pi excludes it to avoid duplicate/wrong-provider discovery.
- VPS `claude/settings.linux.json` had an uncommitted `"model": "haiku"`.
- Existing Mac dirty paths were `codex/config.toml` and `pi/settings.json`. The Codex diff included desktop/app-version state. Pi showed dirty status but no substantive filtered diff in the audit.
- Existing VPS dirty paths were `claude/settings.linux.json` and `pi/settings.json`.
- During the final handoff check, Mac `config/.zshrc` also appeared dirty. It was not edited as part of saving this plan. Reinspect and preserve that change before implementation.
- All four current pstack Pi model mappings appeared in `pi --list-models` on both hosts. This establishes catalog discovery, not working authentication or execution.
- VPS BB `AGENTS.md` and `skills/` matched their canonical repository copies when compared.
- BB live Claude and Codex native-memory settings were disabled. Native subagent disabling was false for both.
- BB's portable preferences and plugin inventory were stale: committed Catppuccin versus live Vercel, plus plugin additions/removals and enabled-state differences.
- BB ports `38886` and `38888` listened on loopback. Legacy `bb.service` was disabled/inactive. Do not start it.

### Operational boundaries

The checkout is live configuration through symlinks. Editing settings or switching branches can affect running tools. Use a separate worktree to prepare changes where useful, but **never run that worktree's `link.sh` against the real home directory**.

Active BB server data directory on VPS:

```text
/home/diab/.bb-machines/diab.getbb.app
```

Active user unit:

```text
bb-host-daemon-diab-getbb-app-host_23vgpbtjh7.service
```

BB user instructions and skills are explicitly copied to that server directory; `link.sh` does not install them. BB distributes generated runtime copies to execution hosts. Never edit the generated `~/.bb/runtime/global-skills/` copies.

## Phase 0: capture a safe baseline

- [ ] Inspect current Git status and diffs on both hosts. Preserve unrelated edits. Do not overwrite the VPS Haiku choice without reconciling it against the approved Mac-first target.
- [ ] Record declared and installed versions, symlink targets, native skill paths, and BB provider settings relevant to this change.
- [ ] Run the following on each host:

```sh
pi --list-models gpt-6
pi --list-models deepseek
```

- [ ] Query BB models in the actual execution environment or on its host, not implicitly on the server. Verify supported effort levels.
- [ ] Compare VPS BB user skills and instructions:

```sh
cd ~/Dev/dotfiles
diff -ru bb/skills ~/.bb-machines/diab.getbb.app/skills
diff ~/.bb-machines/diab.getbb.app/AGENTS.md bb/AGENTS.md
```

- [ ] Compare portable BB preferences without overwriting the committed snapshot first. **`bb/snapshot.py` writes `bb/preferences.json`; it is not a read-only command.** Use the existing read/projection functions to inspect differences or capture to a separate private location. Do not blindly commit live VPS state.
- [ ] Inspect `gh-axi`, `lavish-axi`, and `chrome-devtools-axi` before running them. If safe, measure startup duration and output size in the relevant startup environment. Do not claim a slowdown from one uncontrolled timing or turn them into skills automatically.

Exit condition: the intended changes can be distinguished from pre-existing user changes, and rollback values are recorded without copying secrets into Git or chat.

## Phase 1: concrete reliability and startup changes on Mac

### Pstack update

- [ ] Review the installed revision and upstream changes before updating.
- [ ] Use a reviewed pinned release containing both cleanup fixes below. At audit time the verified candidate was `0.9.92`, commit `7bad1ebc26faa268806bfbb84e5af55d178b68e4`.
- [ ] Preserve intended model assignments explicitly. Intervening releases changed feature/refactoring worker defaults; do not silently inherit them.
- [ ] Avoid affected cleanup routines until fixed. Do not reproduce data-loss cases against real worktrees.

Evidence:

- https://github.com/michael-denyer/pstack-claude/pull/277 — worktree audit overlooked ignored user files and reflog-only commits.
- https://github.com/michael-denyer/pstack-claude/pull/284 — Pi cleanup overlooked output when Git hid untracked files.
- https://github.com/michael-denyer/pstack-claude/compare/1dba27e50e8f18f146bb80f137f0690f8d773c2e...7bad1ebc26faa268806bfbb84e5af55d178b68e4

### Other changes

- [ ] In `pi/mcp.json`, add `"enabled": false` to `fastmail`. Retain its entry and credentials. Explain how to enable it explicitly through `/mcp`; do not imply that enablement automatically expires after the task.
- [ ] Remove the SessionStart entry that invokes `link.sh` from `claude/settings.json` and `claude/settings.linux.json`.
- [ ] Keep `link.sh` as an explicit reconciliation step after approved configuration updates. Its errors must remain visible.
- [ ] Align the local-commit wording in `agents/skills/local-env/SKILL.md` and `README.md` with `agents/AGENTS.md`: local commits/branches need no extra question, but pushes/deployments and other consequential actions retain approval requirements.

Exit condition: configuration parses, fresh sessions load, Fastmail is absent from ordinary sessions, and Claude startup no longer changes links.

## Phase 2: one canonical pstack installation, Pi-only execution

### Model policy

Keep these aliases in `pi/pstack-models.md`:

```text
pi models: opus=openai/gpt-6.1-sol, fable=openai/gpt-6-astra, sonnet=deepseek/deepseek-flash, haiku=openai/gpt-6-luna
```

These are pstack labels, **not permission to call similarly named Anthropic models**.

Use the smaller opt-in panels:

```text
arena runners: opus@high, sonnet@high
arena cross-judge pool: opus@high, sonnet@high
architect runners: opus@high, sonnet@high
interrogate reviewers: opus@high, fable@high, sonnet@high
```

- [ ] Validate supported levels before applying. DeepSeek Flash's inspected catalog offered `none`, `low`, `high`, and `max`, not `medium`; do not blindly inherit a medium session level.
- [ ] Retain `session hook: off`.
- [ ] Keep ordinary default model `openai/gpt-6.1-sol` at medium. Higher effort is task-specific, not universal.
- [ ] Make unavailable configured models a reported blocker. No silent alias, model, provider, or Anthropic fallback.

### BB adapter changes

Edit canonical `bb/skills/pstack-bb/SKILL.md`:

- [ ] Resolve the canonical pstack plugin root through the Pi package installation on the execution host.
- [ ] Require provider `pi` for every pstack child. Remove Claude-family provider routing and provider-specific installation discovery.
- [ ] Use the Pi role/model sheet as the canonical pstack mapping. Resolve aliases to exact Pi catalog IDs.
- [ ] Pass absolute role paths and required rubric/workflow paths. Reading only the role header while falling back to a generic review is not a successful check.
- [ ] Keep the existing host selection, committed-base, separate-writer-worktree, parent integration, no-recursive-delegation, and cancellation rules.
- [ ] For consequential reviews, use a separate worktree at an exact checkpoint commit. Do not commit unrelated changes to obtain the checkpoint. A worktree is edit isolation, not a sandbox.
- [ ] For reviews needing uncommitted changes in the parent environment, keep explicit no-edit instructions and before/after tracked, staged, and untracked-state checks.

### Validate before removing other installations

- [ ] Run one bounded Pi parent → Pi reviewer check through BB. Verify provider, exact model, effort, host, role/rubric reads, completion delivery, and unchanged reviewed work.
- [ ] Run one Pi-only isolated-writing check in a disposable fixture/worktree, then inspect the result and preserve intended output. No native subagent tools inside BB.
- [ ] Exercise the retained Sol/DeepSeek routes, with Astra checked before relying on the three-model panel. Keep validation bounded; no arbitrary benchmark suite.
- [ ] Confirm standalone Pi still has its question and native delegation tools. The pstack Pi extension remains installed.
- [ ] Verify that missing-model handling does not silently fall back. Prefer configuration/source validation or a non-dispatch check over deliberately triggering paid unintended calls.

Only after these checks pass:

- [ ] Remove pstack entries and its marketplace from `claude/settings*.json` and `codex/config*.toml`.
- [ ] Remove only the pstack-specific Codex hook-trust entry. Preserve unrelated session hooks and trust state.
- [ ] Remove `claude/pstack-models.md`, `codex/pstack-models.md`, and their `link.sh` entries.
- [ ] Uninstall native Claude/Codex pstack plugins using supported commands verified against current CLI help. Remove only obsolete links pointing to deleted sheets; do not leave dangling live links or delete unrelated files.
- [ ] Update `README.md` and `agents/ATTRIBUTION.md` to describe one Pi-managed installation per host.

Standalone Claude/Codex lose native pstack commands by design. They remain usable independently with shared instructions and personal skills. OpenCode's existing reference to Pi's skill tree is not a separate installation and stays unchanged.

## Phase 3: reduce automatic process and clarify instruction ownership

- [ ] Replace the blanket instruction to read/follow every matching skill with guidance that specialist skills supply task-specific knowledge or tool procedures. General principles and orchestration workflows are opt-in.
- [ ] Filter pstack's automatically advertised Pi skills using supported package resource filters, without deleting installed upstream files.
- [ ] Start with a small shortlist: `poteto-mode`, `blast-radius`, `benchmark-checklist`, `tdd`, `fix-ci`, and `interrogate`. Verify routing; adjust only for a concrete missing need. Explicit workflows can read other installed skills by path.
- [ ] Do not automatically load `how`, `why`, or `architect` for every ordinary explanation or change. Keep them available on explicit request. Never force `poteto-mode` merely because a project is large.
- [ ] Move the shared policy's “Inside BB…” delegation/tool-routing rule to canonical `bb/AGENTS.md`. Keep one-agent defaults, no recursive delegation, ownership, and safety policy in shared `agents/AGENTS.md`.
- [ ] Disable Claude and Codex native subagents inside BB using the supported provider settings. This prevents a second delegation route; it does not make them pstack workers.

Supported settings observed during the audit:

```sh
bb plugin config provider-claude-code set subagentsDisabled true
bb plugin config provider-codex set subagentsDisabled true
```

- [ ] Route normal UI work to Impeccable; select Interface Design only explicitly. Keep upstream skill content unchanged. Verify that both are not automatically loaded for the same task.
- [ ] Move `bb/skills/diff-review` to `agents/skills/diff-review`, correct its committed-versus-uncommitted review scope, and link it through the normal shared-skill mechanism.
- [ ] After fresh-session discovery succeeds, remove only the obsolete BB user copy of `diff-review` to avoid duplicate names. Preserve other BB skills. Keep `ui-audit` in BB for now.

Exit condition: ordinary tasks remain single-agent, explicitly invoked workflows still function, and each personal skill/instruction has one canonical owner.

## Phase 4: pilot practical verification in one application

Choose one frequently used application when implementation reaches this phase. The choice must come from repository evidence or the user's stated priority; do not invent which application is the main one. This is work in another repository, not a reason to add application verification to dotfiles.

- [ ] Prefer existing run/check scripts and tests. Write a short recipe before considering a generated verification framework.
- [ ] Capture exact launch, readiness, one important user journey, expected observable result, evidence location, and safe cleanup.
- [ ] Store the canonical skill at `.agents/skills/verify/SKILL.md`.
- [ ] If needed, add `.claude/skills/verify -> ../../.agents/skills/verify`. Verify actual discovery and avoid duplicate loading.
- [ ] Check effective Pi project trust in BB. Missing `trust.json` does not prove project skills are skipped: CLI flags or extensions may decide trust.
- [ ] If trust is needed, grant it to the specific approved repository. Do not broadly trust `~/Dev`, `~/apps`, or all BB workspaces by default.
- [ ] Execute the recipe end to end and confirm evidence survives cleanup. Use test data; no customer messages or production mutations.
- [ ] Commit the recipe and compatibility link in the application repository when ready. Push only with approval.

Do not automatically generate a comprehensive feature catalogue, install a new browser framework, add a maintenance loop, or roll the pattern out across every repository. Repeat only after the pilot proves useful.

## Phase 5: tidy, reconcile VPS, and document the result

- [ ] If measurements show an optional `*-axi` startup helper is costly/noisy and rarely needed, remove its startup invocation and use its existing command on demand. Create a skill only if it supplies useful non-obvious procedure.
- [ ] Review version-specific Codex `[[skills.config]]` disable entries. Preserve intended disabled capabilities; do not erase entries simply because paths look old.
- [ ] Decide which application-managed desktop/onboarding state should remain versioned. Prefer narrow cleanup over a new configuration generator or unsupported include mechanism.
- [ ] Refresh BB portable preferences and external-plugin inventory from reviewed live state. Do not store machine IDs, credentials, or arbitrary server configuration in the public repo.
- [ ] Trim obsolete “retired/removed” README history and document the actual tool routing: BB + Pi normally, direct Pi as an optional fallback, specialist workflows on request, pstack only via Pi.
- [ ] Add one small read-only consistency check using existing dependencies. It reports configured/installed versions, expected symlink targets, missing native skills, and relevant model-map drift. It does not install, repair, rewrite snapshots, or print secrets. Do not add an inventory test framework.
- [ ] Synchronise the reviewed Mac-derived configuration through Git under the normal push approval policy, then reconcile the VPS. Never copy Mac auth files or desktop paths to Linux.
- [ ] Resolve the VPS's unintended model/default differences against the approved target.
- [ ] Provision missing native UI skills required for the intended VPS workflow through the supported pinned installer. Preserve Pi's exclusion of the shared Codex Impeccable build.
- [ ] Do not install Claude pstack on the VPS: the target architecture removes it.
- [ ] Refresh the VPS's supported BB CLI entrypoint if needed without touching the active server or starting legacy `bb.service`.
- [ ] Copy reviewed BB user instructions and skills to the active VPS server directory through the documented explicit restore process. Remove only the specifically superseded `diff-review` copy; never blanket-sync with deletion.
- [ ] Start fresh provider sessions on both hosts and verify effective configuration.

## Validation and completion

Use relevant existing checks, not a new broad test suite:

- JSON/TOML parsing and shell syntax for changed configuration/scripts.
- `git diff --check` and final diff review preserving unrelated changes.
- Live client startup and effective skill/model/tool discovery on both hosts.
- Pi-only BB reviewer and isolated-writing checks from Phase 2.
- Fastmail absent from ordinary sessions; explicit enablement procedure documented.
- No startup relinking, no new routine permission prompts, no OpenCode limit changes.
- No pstack provider route to Claude Code/Codex or fallback to Anthropic.
- One executed application verification recipe, or a clearly named deferred application-selection blocker. Do not label an unexecuted recipe complete.
- BB skill/instruction canonical copies match their restored server copies.
- Consistency check detects the concrete drift types found in the audit.

Do not claim that configuration parsing proves workers or applications work. Report changes, checks actually run, and remaining limitations.

## Rollback

Keep changes in small, reviewable local commits or equivalent isolated units. Preserve the baseline and unrelated dirty work.

- Restore specific prior settings/pins and reconcile packages through their supported mechanisms. If restoring old pstack, continue avoiding the affected cleanup paths.
- Do not remove native Claude/Codex pstack until Pi-only checks pass. If consolidation fails, retain those installations while fixing the Pi path; never use them as an automatic fallback worker route.
- Restore recorded BB provider settings and the previous reviewed server instruction/skill copies if necessary.
- Fastmail rollback is a configuration toggle, not credential deletion or OAuth changes.
- If filtered skill discovery loses useful behavior, restore the previous package resource declaration without modifying upstream files.
- Never reset the user's whole working tree, overwrite unrelated live configuration, prune useful worktrees, or rewrite published history to roll back this work.

## Evidence and cautions for the next session

- `pi/settings.json` currently selects Sol at medium and excludes the shared Codex Impeccable build.
- `pi/pstack-models.md` owns the OpenAI/DeepSeek mappings.
- `bb/skills/pstack-bb/SKILL.md` currently contains cross-provider routing that must be replaced, not retained as fallback.
- `bb/snapshot.py` writes its output file directly.
- `bb/skills/diff-review/SKILL.md` currently describes working-tree review but uses a HEAD comparison in its core recipe.
- Pi 1.3.0 supports per-package skill filters and project trust via CLI override, extension, or saved decision. Trust loads executable resources as well as skills; it is not a sandbox.
- One worktree per writer reduces conflicting edits but does not constrain process authority or protect credentials.
- Keep the pstack Pi runtime extension initially: it supplies standalone question/delegation tools. Skills-only runtime removal was an experiment, not an approved prerequisite.
- Cosmetic Pi extension removal is optional and should follow evidence of low value or failures. Do not broaden this plan into a terminal UI rewrite.
