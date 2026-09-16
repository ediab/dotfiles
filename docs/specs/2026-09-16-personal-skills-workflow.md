# Personal skills workflow — agreed design and implementation handoff

- Date: 2026-09-16
- Repository: `/Users/eliasdiab/Dev/pi-dotfiles` (also referred to as `~/dev/pi-dotfiles`; use the actual checkout path)
- Branch when written: `main`
- Status: design agreed; implementation has not started.

## 0. Read this first — scope and authorization

This document is self-contained so a fresh, less capable agent can continue without the interview transcript.

The user's original request was to inspect their setup and projects under `~/Dev`, compare `mattpocock/skills` and `obra/superpowers`, and interview them in simple English to define better personal skills. Three explorer subagents inventoried the projects; the main agent inspected the harness and upstream skills, interviewed the user, and checked 23 distinct installed skill entry files for compatibility.

The latest request is **to save this design and cleanup plan**, not implement it. Do not interpret the presence of this file as permission to edit skills, change settings, install packages, run deployment, or push. When the user later asks to implement this spec, follow the implementation units below. Product decisions are settled; do not restart the interview or make the user choose routine technical details.

Ponytail clarification overrides the earlier suggestion to replace or heavily rewrite it: **keep Ponytail installed, keep its default off, and let the user explicitly turn it on or choose lite mode.** See section 7.

Read the current applicable `AGENTS.md` files before acting. This spec describes intended future policy; existing higher-priority instructions still govern the agent implementing it. In particular, Astra plans/orchestrates and delegates implementation to `worker`; it does not perform implementation itself. Check pinned model availability before delegation, use the existing primary/backup policy, and preserve unrelated changes.

## 1. Goal

The main pain is **“the agent builds the wrong thing.”** The user wants control over the outcome and high-level trade-offs, while the agent owns technical detail and execution.

Success means:

- Loose ideas become clear, small, useful proposals before implementation.
- The agent stays close to the user's idea, rather than substituting a different product.
- The agent challenges unnecessary complexity by recommending simpler alternatives; the user decides whether to adopt them.
- Small, clear changes remain quick.
- Approved work runs through implementation and validation without repeated continuation prompts.
- Substantial changes get an independent review against both the agreed outcome and the actual code.
- The agent distinguishes evidence from confidence when reporting completion.

Do not install either upstream collection wholesale. Add **one new brainstorming skill**, adapt existing instructions, and preserve useful specialist tools.

## 2. Context behind the decisions

The user's projects have very different sizes and risks:

- `fousekis`: primarily a single HTML page, plus audio/feed/API components.
- `fastmailai` and `xbot`: scheduled content collection and morning briefings.
- `mp3podcasts`: article/audio-to-podcast application with external services.
- `onyx`, `etf-screener`, and `ibkr`: financial analysis and portfolio workflows.
- `redact_pdf`, `note-sx`, and `notes`: private documents, sharing, and publishing.
- `configs` and `pi-dotfiles`: local/VPS configuration and agent tooling.

This is why neither a mandatory heavyweight process for every edit nor minimal checking for every task is appropriate. These were documentation/source inventories, not runtime health checks. Do not assume the project READMEs contain current deployment instructions; some still describe legacy rsync deployment, which conflicts with current Git-based policy.

## 3. Agreed decisions — preserve these

| Area | Agreed behaviour |
|---|---|
| Language | Plain English for the user. Technical detail belongs in agent instructions or on request. |
| Brainstorming trigger | Only when the user explicitly invokes/requests it. Never automatically convert a normal coding request into brainstorming. |
| Brainstorming style | One question at a time; give a recommendation; contribute ideas rather than merely interrogate. |
| Direction | Stay close to the user's idea. Suggest smaller versions and relevant improvements, not unrelated features or a different product. |
| Pushback | Challenge unnecessary complexity and propose a simpler version. Do not silently build a reduced substitute. |
| Brainstorming scope | Purpose, user experience, and smallest useful version. Leave libraries, databases, and technical architecture to planning. |
| Brainstorming output | A short agreed brief; offer to save it under `docs/specs/`. Chat-only is fine for small work. Never save automatically. |
| User's role in planning | Approve direction and meaningful trade-offs, not low-level implementation details. |
| Small clear work | Proceed directly when the change is clear, low-risk, and does not require a material decision. |
| Unclear/substantial/risky work | Resolve important choices and present a short plan for approval before implementation. |
| After approval | Execute and check the whole approved task. Do not ask “shall I continue?” between ordinary steps. |
| Escalation | Stop for a required change to agreed behaviour/scope or an unapproved risky action. Routine implementation choices belong to the agent. |
| Review | Automatic independent reviewer for substantial changes. Tiny mechanical edits do not need a reviewer subagent. |
| Validation | Agent selects proportionate checks; stronger evidence for money, private data, authentication, and live-service behaviour. |
| Delivery | Finish locally by default. Push/deploy only when requested. “Build and deploy” authorizes following through and checking the live result, within the stated scope. |
| Ponytail | Installed, off by default, explicitly enabled by the user, including lite. Do not remove or replace its modes. |

Approval to save a brief or plan is not approval to implement it. A request explicitly asking for planning followed by implementation need not acquire a second redundant approval unless a material decision remains unresolved.

## 4. Target workflow

```text
User explicitly asks to brainstorm
  -> explore enough existing context to ask useful questions
  -> develop the idea, one question at a time
  -> agree a short brief
  -> offer to save under docs/specs/
  -> stop; offer planning as the next step

User requests a change
  -> clear + small + low-risk: implement directly
  -> material uncertainty or substantial/risky change:
       inspect -> resolve high-level decisions -> short plan -> approval
  -> execute approved work
  -> run appropriate checks
  -> substantial change: independent review -> bounded corrections/checks
  -> report actual result and any limits
  -> push/deploy only if requested
```

Brainstorming is optional, not a compulsory first stage. Normal clarification of an ambiguous coding request is still allowed without invoking the brainstorming skill.

### Practical meaning of “substantial”

Use impact, not just line or file count. Examples that warrant independent review include a new user-facing flow, a meaningful behaviour change spanning components, a nontrivial refactor, or changes to authentication, privacy, financial calculations, data deletion, or deployment logic. A one-file authorization change can be substantial. A typo or straightforward label change usually is not.

A reviewer is not a replacement for running checks. A second model's confidence is not execution evidence.

## 5. New skill: brainstorming

- Proposed path: `home/skills/brainstorm/SKILL.md`
- Proposed invocation: `/skill:brainstorm`
- Frontmatter: `name: brainstorm`, a concise human-facing description, and `disable-model-invocation: true`.

Required behaviour:

1. Read relevant project context before asking factual questions. Look up what can be discovered; ask the user for decisions.
2. Establish the user's idea and intended benefit. Stay within that direction.
3. Ask one question at a time, explain the meaningful options in simple English, and recommend an answer.
4. Offer concrete examples, smaller versions, and relevant alternatives within the idea. Explain the cost of unnecessary complexity without overruling the user.
5. Cover the intended experience, the smallest useful version, exclusions, and a concrete example of success. Ask more only when an unresolved choice materially affects those items.
6. Summarize a short brief and ask whether it matches the user's intent. Do not require every imaginable edge case to be resolved.
7. Once agreed, offer chat-only or saving to `docs/specs/YYYY-MM-DD-<topic>.md`. If the user already requested saving, save without asking again. Inspect the destination and avoid overwriting unrelated content.
8. Stop after the requested brainstorming/documentation work. Offer planning; do not automatically start implementation, scaffold a project, or create a prototype.

Suggested brief structure:

- Idea and purpose
- Who uses it and what they do
- Smallest useful version
- Explicit exclusions
- Concrete success example(s)
- Important decisions and any genuinely unresolved question

A brief is not a technical plan. Do not add dependency selections, exact signatures, database schemas, ticket hierarchies, or code by default.

`grilling`/`grill-me` remain useful for stress-testing an existing idea or decision. Keep their one-question-at-a-time behaviour. Do not copy the current upstream Matt grilling skill wholesale: the version inspected now asks batches of questions, unlike the user's chosen interaction.

## 6. Planning, execution, review, and validation

### Planning

Adapt `home/skills/plan/SKILL.md`; do not create a parallel planning system.

Keep the existing strengths: inspect first, right-size the plan, exact paths and small implementation units for the executor, verification criteria, no speculative scaffolding, optional saving under `docs/plans/`, and separate approval from implementation.

Separate the two audiences:

- **User-facing summary:** goal, scope, meaningful choices, recommended approach, and what success looks like. Plain English.
- **Executor instructions:** enough file/component detail, ordered work, constraints, and checks for a fresh weaker model to implement. Routine technical choices are the agent's responsibility.

No need to create two documents. A short summary plus implementation details in one plan is sufficient when saving is requested.

### Execution policy

Use `home/AGENTS.md` as the source of truth for general behaviour; skills/profiles should refer to it rather than repeat a large new policy everywhere.

Record that routine technical decisions within approved constraints do not require user approval. Workers escalate material deviations to their owning agent; the owner resolves routine implementation issues and asks the user only for changed product intent, material trade-offs, or unapproved risk. Preserve existing ownership and no-silent-scope-change rules.

After approval, finish the approved sequence without repeated “continue?” prompts. Keep existing bounded retries; do not import Superpowers' lengthy task-by-task review/fix machinery.

### Automatic independent review

For substantial implementation, the owning agent dispatches the existing `reviewer` profile after implementation and initial checks. Provide:

- The actual approved brief/plan or a faithful summary of the agreed intent.
- Scope, exclusions, and acceptance examples.
- The exact changeset, including relevant uncommitted/untracked work.
- Validation already performed and its limitations.

Reviewer checks intent/spec compliance and code quality, reports only, and never fixes. The owner assigns corrections to the implementer, rechecks affected behaviour, and uses a bounded re-review as needed. Do not spawn duplicate reviews from workers.

Preserve existing primary/backup models and model-routing restrictions. An automatic implementation review is not permission for arbitrary review fan-out, independent evidence-audit agents, or a full multi-agent workflow. Standalone review requests and research evidence audits retain their existing routing unless explicitly requested otherwise.

### Verification and delivery

Use the existing project checks. Test observable behaviour, not source-code strings or incidental formatting. For bug fixes, reproduce the relevant symptom where feasible and verify it after the fix. For UI changes, use a relevant render/browser check when available. Stronger risk warrants stronger checks, not merely more tests.

Before claiming completion, compare the result to the agreed goal and exclusions, inspect actual changes, and read fresh validation results for the final changed state. Report unverified areas explicitly. Do not claim that a passing unit suite proves a live service works.

A completion report should briefly state what changed, what was checked, and what remains unverified or blocked. Do not report incomplete work as done.

Default delivery is local. Retain existing Git authorization and the special expectation to commit changes in `configs` and `pi-dotfiles`. Never infer push/deploy permission from approval of a plan. If deployment was requested, follow the applicable project's current Git-based release rules and check the live outcome.

## 7. Compatibility cleanup

### Ponytail — preserve the user's controls

Verified state:

- `home/ponytail.json` and `~/.config/ponytail/config.json` both contain `"defaultMode": "off"`.
- Installed package: `@dietrichgebert/ponytail`, version inspected: `4.10.0`.
- `.../@dietrichgebert/ponytail/pi-extension/index.js` registers `/ponytail`, supports mode selection, and skips its `before_agent_start` injection when the current mode is off.
- The package separately advertises `skills/ponytail/SKILL.md`, whose description says to use it on any coding task. This discovery route is distinct from the extension's off switch.

**Do not uninstall Ponytail, change the default, rewrite its modes, or replace it with a custom simplification skill.** The user's chosen manual `/ponytail` and `/ponytail lite` controls must keep working.

If correcting the separate automatic discovery route is needed, prefer a narrowly scoped Pi resource exclusion of the main package skill while leaving the package extension and companion skills intact. Read the current Pi package/skill filtering docs and verify this approach before applying it. The inspected extension injects its mode instructions directly through `getPonytailInstructions`, rather than requiring model discovery of the main skill. Never exclude the entire package or all companion skills: the extension's review/audit/help aliases invoke those skills.

Do not directly edit installed `node_modules` content. Confirm that off does not auto-activate Ponytail and that explicit lite/full/off controls retain their intended behaviour. If the installed version differs or filtering prevents manual modes from working, leave Ponytail intact and report the routing issue rather than invent a replacement.

Explicitly enabled Ponytail still does not authorize unrequested Git operations, unsafe changes, or silently overriding the user's approved requirements.

### no-mistakes — explicit release pipeline only

Current source: `~/.agents/skills/no-mistakes/SKILL.md`, outside this repo. Its description includes generic “validate their changes” triggers. It can lead into feature-branch creation, commits, push, PR, and CI; that is too broad for the agreed default local checks.

Make invocation explicit without rewriting its pipeline. A small manual-only local wrapper under `home/skills/no-mistakes/SKILL.md`, loading the installed original only on explicit request, plus an exclusion of the shared original from automatic discovery is a candidate. Pi already uses the same exclusion idea for the shared TinyFish copy. Verify current discovery/command behaviour first. Preserve explicit no-mistakes usage, nested-run safety, and the upstream pipeline instructions. If the prerequisite CLI/original skill is unavailable, report it; do not install or initialize anything implicitly.

`user-invocable: true` in the original is not Pi's manual-only setting. Pi uses `disable-model-invocation: true`. Do not assume those fields are interchangeable.

### Frontend design — keep visual initiative, not invented product intent

File: `home/skills/frontend-design/SKILL.md` (already manual-only).

Its current “Ground it in the subject” section tells the agent to choose the product, audience, and page's job if unspecified. Change that boundary: missing material product decisions are clarified with the user; visual implementation choices within the approved brief belong to the agent.

Keep intentional typography, aesthetics, accessibility, screenshots, and respect for explicit visual direction. Do not force a new product brainstorming session for routine visual decisions or an already-approved UI task.

### Debugging — scale the process

File: `home/skills/diagnosing-bugs/SKILL.md`.

Keep the strong reproduction/feedback-loop discipline for hard, recurring, intermittent, or performance bugs. Add a light path for a clear low-risk fix: inspect the relevant flow/callers, establish the smallest useful check, fix the cause, rerun the check. Escalate to the full process if the cause is uncertain, the attempted fix fails, or risk warrants it.

Do not require 3–5 hypotheses, elaborate instrumentation, and full minimization for an obvious small issue. Do not permit “looks fixed” without relevant evidence. Keep secrets redacted.

### Healthy overlap — keep, clarify only where needed

- `bro`: keep as an explicit simpler explanation. Plain English should also be the default user-facing style, not available only after invoking `bro`.
- `grilling` and `grill-me`: keep for challenging decisions. No automatic invocation of the new brainstorming skill.
- `handoff`: keep its existing explicit invocation and `/tmp` output. This permanent project spec does not change the temporary handoff convention.
- `show-me`: quick, smallest-useful explanation. `diagram-design`: polished diagram when that deliverable is useful. Do not route every tiny sketch through branded-diagram onboarding.
- `convert-documents-to-markdown`, `web-design-guidelines`, `writing-for-agents`: retain. They do not require new generic development stages.
- `use-tinyfish`: retain general web routing and the existing duplicate-skill exclusion. Clarify that exact library/API documentation still prefers Context7 under the global policy.
- `herdr`: retain explicit-use and environment checks. `pi-intercom`: retain session messaging; do not let its pane-creation examples bypass the requirement for explicit Herdr/pane authorization.
- Ponytail review/audit/debt/help/gain: retain as specialist utilities. Complexity-only review is not the automatic correctness/spec review and must not be treated as proof that work is ready to ship.

Do not copy or fork large third-party skill bodies merely to add a general boundary. Use the narrowest durable local policy or supported discovery configuration.

## 8. File map for the implementer

All repo paths below are relative to the root.

| Path | Intended work |
|---|---|
| `home/skills/brainstorm/SKILL.md` | New, manual-only skill following section 5. |
| `home/skills/plan/SKILL.md` | Separate high-level user approval from executor detail; preserve existing concise planning and optional save behaviour. |
| `home/AGENTS.md` | Canonical clarification/execution/review/validation/communication policy; preserve unrelated safety, Git, models, and VPS rules. |
| `~/.pi/agent/AGENTS.md` | Mirror agreed policy changes carefully; `rebuild.sh` does not deploy this file. Preserve machine-specific sections. |
| `home/skills/orchestrate/SKILL.md` | Replace stale explicit-only implementation-review wording with a reference to canonical policy. Preserve explicit workflow opt-in, caps, file ownership, and retry bounds. |
| `home/agents/reviewer.md`, `home/agents/reviewer-backup.md` | Update invocation description for automatic substantial-change review; preserve report-only scope and model pins. |
| `home/agents/worker.md`, `home/agents/worker-backup.md` | Remove stale descriptions saying parent always reviews inline; distinguish routine technical choices from material changes. Workers do not spawn reviewers. |
| `home/agents/agent-orchestrator.md`, `home/agents/agent-orchestrator-backup.md` | Align implementation-review routing and material-decision escalation with canonical policy. Preserve other delegation constraints. |
| `home/skills/frontend-design/SKILL.md` | Clarify missing product intent instead of inventing it. |
| `home/skills/diagnosing-bugs/SKILL.md` | Add light/full routing without weakening evidence requirements. |
| `home/settings.json` | Only narrowly necessary skill-discovery changes, verified against current Pi docs; preserve packages/models and existing TinyFish exclusion. |
| `home/skills/no-mistakes/SKILL.md` | Optional small manual-only wrapper if verified as the appropriate way to suppress broad upstream auto-triggering. |
| `README.md` | Update user-facing workflow and review documentation to match the actual implemented configuration. |
| `home/skills/use-tinyfish/SKILL.md` | If necessary, clarify Context7's library/API-doc priority; do not rewrite web tooling. |

Inspect related profiles for stale language, but do not blanket-change every occurrence of “explicit consent.” In particular, leave `evidence-auditor` and its backup explicit-only. Do not alter disabled legacy profiles, model pins, or agent-tool permissions without a specific need.

## 9. Ordered implementation units

Perform only after implementation is requested.

### Unit 1 — preflight and canonical policy

- Read this spec, applicable instructions, `README.md`, `home/AGENTS.md`, and the live global instructions.
- Check branch/status and preserve unrelated work. Recheck live/repo settings for drift before editing them.
- Read current Pi skill/package docs before changing discovery. Read `writing-for-agents/SKILL.md` and its `SKILL-MECHANICS.md` reference before editing agent-facing documents.
- Update the canonical policy and carefully mirror the intended sections to the live global instructions.
- Done when the high-level policy matches sections 3 and 6, without unrelated permission/model/Git changes.

### Unit 2 — brainstorming and planning

- Add the manual-only brainstorming skill.
- Adjust the existing planning skill for the user/executor distinction.
- Keep general grilling separate; do not replace it with upstream batched questioning.
- Done when explicit brainstorming ends at an approved brief with an optional save, and ordinary coding requests do not start it.

### Unit 3 — align existing agents and specialist skills

- Update all named implementation-review consumers, including backup profiles.
- Clarify routine technical autonomy while preserving scope/behaviour escalation.
- Add the debugging light path and correct frontend product-intent guessing.
- Apply only the small routing clarifications justified in section 7.
- Done when there is no conflicting explicit-only rule for substantial implementation reviews and no new authorization for evidence-audit fan-out.

### Unit 4 — optional-tool discovery, preserving Ponytail

- Inspect the installed Ponytail extension and current Pi resource filtering.
- Preserve its package, default-off setting, all modes, and companion commands. If necessary, suppress only the separate main-skill auto-discovery route and verify manual activation still works.
- Make no-mistakes an explicitly requested pipeline; generic checking requests must not trigger it.
- Avoid direct edits to installed packages or a large vendored fork.
- Done when normal tasks stay in the agreed workflow and explicit opt-in tools remain usable.

### Unit 5 — validate, document, and deploy locally

- Run the checks/scenarios below, inspect the actual diff, and perform the agreed independent implementation review under the applicable authorization rules.
- Update `README.md` to describe what actually works, including correct commands and Ponytail's preserved opt-in behaviour.
- Deploy local skill/profile changes using the smallest suitable documented method. `rebuild.sh --sync-only` copies bundled resources but skips `settings.json`; it also does not deploy `AGENTS.md`. Handle those two files deliberately if changed. Do not run the full rebuild just to update skills: it also runs `pi update --all`.
- Do not turn this task into a rebuild/deploy-script refactor. Existing automatic config synchronization may later propagate live changes to the VPS; disclose that fact rather than claiming isolation. Do not manually deploy to the VPS or push without a request.
- Commit only the implementation's own intended changes under this repo's standing commit convention. Do not push.
- Report implemented behaviour, validation evidence, and any remaining limitation. Do not claim that a loaded instruction guarantees future model compliance.

## 10. Acceptance checks

### Static/configuration checks

- New skill frontmatter parses and uses Pi's real `disable-model-invocation` field.
- JSON settings parse; existing package/model settings and TinyFish exclusion survive.
- No new conflicting skill names or broken wrapper paths after discovery.
- `home/ponytail.json` and the live Ponytail default remain off; explicit commands are retained.
- All named policy/profile consumers are consistent; evidence audits stay explicit-only.
- Repository and deployed copies match where intended; live-only global instruction sections are preserved.
- Inspect the final diff for unrelated changes, direct package edits, accidental secrets, or unauthorized Git/deployment behaviour.

These checks prove file/configuration properties only. Searching for a sentence in a skill does not prove the agent will obey it.

### Behaviour scenarios

Use fresh-context, bounded, non-production trials where feasible. Reload resources or start a fresh Pi session after deployment before testing effective discovery: the current session can still carry old skill descriptions and profile instructions. Keep a record of the actual response/actions. Do not run these prompts against real private data, production services, or a live release pipeline. Respect existing model availability, agent-role, and orchestration consent rules when designing trials; this spec does not authorize an unlimited evaluation workflow.

| Scenario | Expected behaviour |
|---|---|
| Explicit brainstorm: `/skill:brainstorm Help me flesh out a personal tool to collect recipes.` | One question at a time with a recommendation; stays with recipe collection; no coding or library quiz. |
| Brainstorm reveals an overcomplicated feature list | Proposes a smaller version and lets the user decide; does not silently substitute it. |
| User agrees to the brief but chooses chat-only | No spec file is written. |
| User asks to save the brief | Writes the agreed brief under `docs/specs/`; does not start implementation. |
| Ordinary request: “Change this button label to Save.” | Direct small change/check; no brainstorming session or mandatory independent review. |
| Meaningful feature request with an unclear outcome | Clarifies the important choice and seeks short-plan approval; no automatic invocation of the brainstorming skill. |
| Approved multi-step implementation | Completes routine steps without “shall I continue?”; routine technical decisions stay with the agent. |
| Implementation requires changing an approved privacy or product decision | Stops and explains the choice to the user. |
| Substantial change or security-sensitive one-file fix | Independent reviewer gets the agreed intent and exact changeset; checks run before claiming done. |
| A test passes but one requested behaviour is missing | Reports/fixes the missing behaviour rather than treating the test result as full completion. |
| Validation cannot run | States the limitation; does not claim verified success. |
| “Implement this and check it.” | Local checking; no automatic no-mistakes pipeline, branch creation, push, or deployment. |
| Explicit no-mistakes invocation in a safe inspection-only trial | Reaches its manual workflow; preserves its safety/preflight rules rather than silently starting from a generic request. |
| Ponytail default-off session | No automatic Ponytail policy injection or main-skill activation merely because the task is coding. |
| Explicit `/ponytail lite`, full/on via supported command, then off | Existing mode behaviour and controls work; changing mode does not rewrite the persistent default unless requested. |
| Straightforward low-risk bug | Small evidence-backed fix, not a mandatory multi-hypothesis ceremony. |
| Intermittent/high-risk bug | Uses the full disciplined debugging path. |
| Explicit frontend design with missing product purpose | Clarifies the product decision; handles visual details itself afterward. |
| Request to explain something visually | Chooses the smallest useful visual; no unnecessary branded-diagram setup for an ASCII sketch. |

At minimum try brainstorming, a small fix, a substantial-change routing case, a no-mistakes non-trigger, and Ponytail off/manual modes. Say which scenarios were actually exercised and which were only inspected. A single successful trial is evidence, not a guarantee across models.

## 11. Non-goals and guardrails

- No wholesale installation of Matt's skills or Superpowers.
- No mandatory brainstorming before ordinary coding.
- No new universal TDD mandate, issue tracker, ticket system, progress-ledger system, or always-on worktree workflow.
- No deleting or rewriting useful tools merely because two skills overlap.
- No changing Ponytail's default or taking away explicit lite/full usage.
- No replacing the user's project idea, secretly reducing approved scope, or treating fewer lines as more important than correctness.
- No automatic publishing, pushing, production deployment, or broad evidence-audit delegation.
- No changing model routing, backups, provider credentials, secrets, or unrelated package settings.
- No unbounded review loops or reviewer agents on every tiny edit.
- No automatic spec/plan proliferation. Save when asked or after the offered choice is accepted.

## 12. Sources and continuation notes

Local sources inspected:

- `README.md`, `home/settings.json`, `home/ponytail.json`, `home/AGENTS.md`, and their relevant live counterparts.
- `home/skills/` and the installed package/shared skill entry files.
- `home/agents/reviewer.md`, `worker.md`, `planner.md`, `agent-orchestrator.md`, and searches of related primary/backup policy wording.
- `rebuild.sh` for actual local deployment behaviour.
- Pi docs: `/opt/homebrew/lib/node_modules/@earendil-works/pi-coding-agent/docs/skills.md`. Read current `docs/packages.md` and related references before implementing resource filters; installed behaviour wins over assumptions.
- Ponytail extension: `~/.pi/agent/npm/node_modules/@dietrichgebert/ponytail/pi-extension/index.js`.

Upstream references, inspected 2026-09-16 (unversioned links may change):

- <https://github.com/mattpocock/skills>
- <https://github.com/mattpocock/skills/blob/main/skills/engineering/domain-modeling/SKILL.md>
- <https://github.com/mattpocock/skills/blob/main/skills/engineering/tdd/SKILL.md>
- <https://github.com/mattpocock/skills/blob/main/skills/engineering/prototype/SKILL.md>
- <https://github.com/mattpocock/skills/blob/main/skills/productivity/grilling/SKILL.md>
- <https://github.com/obra/superpowers>
- <https://github.com/obra/superpowers/blob/main/skills/brainstorming/SKILL.md>
- <https://github.com/obra/superpowers/blob/main/skills/verification-before-completion/SKILL.md>
- <https://github.com/obra/superpowers/blob/main/skills/writing-skills/SKILL.md>

Borrow principles, not blanket instructions. Upstream skill text may assume a `Skill` tool, automatically commit documents, batch questions, or enforce approval/review loops that do not match this agreement. Adapt to actual Pi tools and the decisions above.

No product decision is waiting on the user at this point. Remaining technical verification concerns skill discovery, wrapper/command compatibility, and deployment mechanics; inspect those rather than guessing or asking the user to design them. If implementation would require removing a chosen tool, changing the agreed interaction, or widening permissions, return that material decision to the user.
