# Borrowed skills — provenance

Some skills in `agents/skills/` and `pi/skills/` are adapted from third-party repos. This file
records where each one came from, which upstream commit it was last reviewed
against, and what was deliberately changed locally. When checking for upstream
updates, diff the borrowed paths below between the pinned SHA and upstream HEAD.

Each source's license is recorded below; license files are not bundled with the skills. Upstream `agents/openai.yaml` files are not imported; locally maintained metadata is added only where needed to preserve Codex invocation policy.

## mattpocock/skills

- Upstream: https://github.com/mattpocock/skills
- Pinned SHA: `c55ee46` ("Modified the PR body template to make it easier to scan")
- License: MIT, Copyright (c) 2026 Matt Pocock

| Local skill | Upstream path | Local adaptations |
|---|---|---|
| `grilling/` | `skills/productivity/grilling/SKILL.md` | None — verbatim copy. |
| `grill-me/` | `skills/productivity/grill-me/SKILL.md` | Body reads `Read and follow ../grilling/SKILL.md` instead of upstream's `Call the Skill tool with "grilling"`; the sibling read works across shared skill directories. |
| `handoff/` | `skills/productivity/handoff/SKILL.md` | Save location hardcoded to `/tmp` (macOS `os.tmpdir()` returns a per-user `/var/folders/...` path); "suggested skills" worded as "which suggests skills that the agent should invoke" instead of "naming which skills the next agent should call the Skill tool for" (same reason as above). `argument-hint` frontmatter kept as upstream. |
| `diagnosing-bugs/` | `skills/engineering/diagnosing-bugs/SKILL.md`, `skills/engineering/diagnosing-bugs/scripts/hitl-loop.template.sh` | Added a "Light or full path" section at the top of `SKILL.md`: a clear low-risk fix takes a light path, the full phased process is for hard/recurring/intermittent/performance bugs. Script is verbatim. Upstream's secret-redaction section already incorporated. |
| `writing-for-agents/` | `skills/productivity/writing-for-agents/SKILL.md`, `skills/productivity/writing-for-agents/SKILL-MECHANICS.md` | None — verbatim copies. |
| `to-spec/` | `skills/engineering/to-spec/SKILL.md` | Upstream's issue-tracker publishing replaced with: show spec to user, offer to save under the project's docs (`docs/specs/YYYY-MM-DD-description.md`), with date/request/branch preamble. Kept local right-sizing and 2–3 checkable success examples from the earlier local `plan` skill (now deleted). |
| `to-tickets/` | `skills/engineering/to-tickets/SKILL.md` | Local-files mode only: removed the issue-tracker publishing branch, `setup-matt-pocock-skills` dependency, and issue templates; ticket files go to `.scratch/<feature-slug>/issues/` with `Status: ready`. |
| `implement/` | `skills/engineering/implement/SKILL.md` | Skill-tool reference replaced with a relative read of `../tdd/SKILL.md`; review and Git guidance now follows the host client's and project's rules without requiring Pi-only skills, profiles, or commands. |
| `tdd/` | `skills/engineering/tdd/SKILL.md`, `tests.md`, `mocking.md` | Removed references to unbundled `codebase-design` and Pi-only `code-review`; consult project architecture records and host review rules instead. |
| `domain-modeling/` | `skills/engineering/domain-modeling/SKILL.md`, `ADR-FORMAT.md`, `CONTEXT-FORMAT.md` | None — verbatim copies. |
| `grill-with-docs/` | `skills/engineering/grill-with-docs/SKILL.md` | Upstream's two Skill-tool calls replaced with relative reads of `../grilling/SKILL.md` and `../domain-modeling/SKILL.md` (same adaptation as `grill-me`). |
| `ask-matt/` | `skills/engineering/ask-matt/SKILL.md`, `PHASE-BOUNDARIES.md` | Claude Code specifics localized: `/clear` noted as pi's fresh-session equivalent; `/tdd`-invocation wording genericized; `/research` described as pi's `researcher` subagent; `/setup-matt-pocock-skills` precondition removed (this install is local-files only; doc paths stated instead). |
| `wayfinder/` | `skills/engineering/wayfinder/SKILL.md` | Local-markdown tracker only: map at `.scratch/<feature-slug>/map.md`, tickets as files under `tickets/` with `Status:`/`Blocked by:` front matter replacing tracker issues/labels/assignees; `setup-matt-pocock-skills` dependency removed; Skill-tool calls → relative reads or host-client research/delegation with inline fallback; `disable-model-invocation: true` and matching Codex policy metadata preserve user-only invocation. |
| `prototype/` | `skills/engineering/prototype/SKILL.md`, `LOGIC.md`, `UI.md` | Commit guidance now follows project contribution rules instead of depending on Pi-only `personal-workflow`. |
| `code-review/` | `skills/engineering/code-review/SKILL.md` | `setup-matt-pocock-skills` tracker note softened to a generic ask (pi installs carry no tracker doc). Parallel two-sub-agent structure kept (pi supports parallel background agents); protocol wording ("Skill tool") not present upstream in this file. |

## cursor/plugins (pstack)

- Upstream: https://github.com/cursor/plugins
- Pinned SHA: `fae2c6ed95821bd85f614a73e4842e13229fa5e5`
- License: MIT, Copyright (c) 2026 Lauren Tan.
- New commands are user-invoked with locally maintained Codex policy metadata. Existing `tdd` and `diagnosing-bugs` retain their invocation policies. No Cursor model configuration or whole-plugin installation is imported.

| Local skill | Upstream path (under `pstack/`) | Local adaptations |
|---|---|---|
| `blast-radius/` | `skills/blast-radius/SKILL.md` | Preserves evidence ladder, downstream investigation, and proof of safety assumptions; allows several assumptions, qualitative risk, and isolated checks. Removes required companion skills and automatic multi-model review. |
| `create-verification-skill/` | `skills/create-verification-skill/SKILL.md`, `skills/create-verification-skill/references/feature-map-example/`; `skills/maintain-verification-skill/SKILL.md` | Portable project-local output, repo-native harnesses, explicit mutation/ownership boundaries, and honest mapped-versus-executed coverage. Maintenance is a referenced branch; changed means a local diff, not an automatic PR. Examples use an illustrative CLI, not an imaginary control tool. |
| `why/` | `skills/why/SKILL.md`, `skills/why/references/epistemics.md` | Retains historical anchoring and calibrated confidence; narrows to available relevant sources, removes fixed MCP roster and mandatory delegated synthesis, and preserves material unknowns. |
| `unslop/` | `skills/unslop/SKILL.md` | Explicit editing scope and natural prose; preserves technical facts and uncertainty. Drops always-on wording, rigid punctuation/style bans, and blanket jargon blacklist. |
| `tdd/` | `skills/tdd/SKILL.md` | Selective additions to the existing Matt Pocock-derived skill: behavioral red verification, impractical-regression-check fallback, and before/after reporting. Retains feature TDD, agreed seams, and existing test-quality references. Does not import assertion blacklist. |
| `diagnosing-bugs/` | `skills/poteto-mode/playbooks/hillclimb.md`, `skills/principle-attack-the-premise/SKILL.md` | Adds disclosed `PERFORMANCE.md` with stable repeated measurement and correctness gating, plus a general premise-check after failed fixes. Retains diagnosis and correct-seam checks; shares cadence with tdd. Omits iteration quota, actor-imbalance recipe, mandatory delegation, decision-log skill, automatic Git/PR actions. |

The existing Matt Pocock entries above remain the provenance of the base skills. `ask-matt` gains local routing descriptions only.

## luchasarie/bro-skill

- Upstream: https://github.com/luchasarie/bro-skill
- Pinned SHA: `3aa8c40b1241111f73ab5360e770f7512193a20e`
- License: MIT, Copyright (c) 2026 Hermes Agent + Luka

| Local skill | Upstream path | Local adaptations |
|---|---|---|
| `bro/` | `SKILL.md` | Verbatim upstream `SKILL.md`; imported revision recorded above. |

## humanlayer/skills

- Upstream: https://github.com/humanlayer/skills
- Pinned SHA: `bba9d13ab34f0a87f1cc33df4dd196372393ddfc` (last commit touching `show-me`, 2026-09-12; copied 2026-10-01)
- License: MIT, Copyright (c) 2026 HumanLayer

| Local skill | Upstream path | Local adaptations |
|---|---|---|
| `show-me/` | `plugins/show-me/skills/show-me/SKILL.md` | None — verbatim copy of upstream `main`. Its `disable-model-invocation: true` keeps it user-invoked. |

## excel (retired)

The local skill has been removed. This section preserves its provenance; the skill and
bundled licenses remain in Git history under `home/skills/excel/` (the pre-restructure layout). Paths below describe
that historical layout, not current source or installed content.

- Upstream sources (pinned):
  - https://github.com/openai/skills @ `7b548893` — `skills/.curated/spreadsheet/` (Apache-2.0; later removed upstream by commit `fdf90d6`). Bundled license: `excel/LICENSE.openai-skills.txt`.
  - https://github.com/openai/role-specific-plugins @ `ebf5795` — `plugins/data-analytics/skills/spreadsheets/` (MIT). Bundled license: `excel/LICENSE.openai-role-specific-plugins.txt`.
- Local: `excel/` — original skill, not a copy. Conventions adapted from the pinned sources: formulas for derived values, restrained professional formatting, sources/attribution, charts, bounded edits, QA loops. Nothing from the unavailable `@oai/artifact-tool` tooling or plugin routing is used; commands are `asp` (agent-spreadsheet) and local `openpyxl`/`xlwings` scripts.
- **No Anthropic material**: Anthropic's public `skills/xlsx` was reviewed for comparison only; its license prohibits derivatives, and no text, scripts, assets, or structure from it were copied.
