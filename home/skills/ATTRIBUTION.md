# Borrowed skills — provenance

Some skills in this directory are adapted from third-party repos. This file
records where each one came from, which upstream commit it was last reviewed
against, and what was deliberately changed locally. When checking for upstream
updates, diff the borrowed paths below between the pinned SHA and upstream HEAD.

Both upstreams are MIT licensed. Their `agents/openai.yaml` files were
deliberately not copied (repo-wide removal — pi has no use for them).

## mattpocock/skills

- Upstream: https://github.com/mattpocock/skills
- Pinned SHA: `c55ee46` ("Modified the PR body template to make it easier to scan")
- License: MIT, Copyright (c) 2026 Matt Pocock

| Local skill | Upstream path | Local adaptations |
|---|---|---|
| `grilling/` | `skills/productivity/grilling/SKILL.md` | None — verbatim copy. |
| `grill-me/` | `skills/productivity/grill-me/SKILL.md` | Body reads `Read and follow ../grilling/SKILL.md` instead of upstream's `Call the Skill tool with "grilling"` (pi has no Skill tool; the relative read is the pi equivalent). |
| `handoff/` | `skills/productivity/handoff/SKILL.md` | Save location hardcoded to `/tmp` (macOS `os.tmpdir()` returns a per-user `/var/folders/...` path); "suggested skills" worded as "which suggests skills that the agent should invoke" instead of "naming which skills the next agent should call the Skill tool for" (same reason as above). `argument-hint` frontmatter kept as upstream. |
| `diagnosing-bugs/` | `skills/engineering/diagnosing-bugs/SKILL.md`, `skills/engineering/diagnosing-bugs/scripts/hitl-loop.template.sh` | Added a "Light or full path" section at the top of `SKILL.md`: a clear low-risk fix takes a light path, the full phased process is for hard/recurring/intermittent/performance bugs. Script is verbatim. Upstream's secret-redaction section already incorporated. |
| `writing-for-agents/` | `skills/productivity/writing-for-agents/SKILL.md`, `skills/productivity/writing-for-agents/SKILL-MECHANICS.md` | None — verbatim copies. |
| `to-spec/` | `skills/engineering/to-spec/SKILL.md` | Upstream's issue-tracker publishing replaced with: show spec to user, offer to save under the project's docs (`docs/specs/YYYY-MM-DD-description.md`), with date/request/branch preamble. Kept local right-sizing and 2–3 checkable success examples from the earlier local `plan` skill (now deleted). |
| `to-tickets/` | `skills/engineering/to-tickets/SKILL.md` | Local-files mode only: removed the issue-tracker publishing branch, `setup-matt-pocock-skills` dependency, and issue templates; ticket files go to `.scratch/<feature-slug>/issues/` with `Status: ready`. |
| `implement/` | `skills/engineering/implement/SKILL.md` | Skill-tool reference replaced with a relative read of `../tdd/SKILL.md`; upstream's `/code-review` step replaced with personal-workflow's owner-review rule (reviewer subagent only when requested); added "push/deploy/PRs only when requested" guard matching the local Git policy. |
| `tdd/` | `skills/engineering/tdd/SKILL.md`, `tests.md`, `mocking.md` | `codebase-design` Skill-tool call replaced with a pointer to the upstream skill (not imported). |
| `domain-modeling/` | `skills/engineering/domain-modeling/SKILL.md`, `ADR-FORMAT.md`, `CONTEXT-FORMAT.md` | None — verbatim copies. |
| `grill-with-docs/` | `skills/engineering/grill-with-docs/SKILL.md` | Upstream's two Skill-tool calls replaced with relative reads of `../grilling/SKILL.md` and `../domain-modeling/SKILL.md` (same adaptation as `grill-me`). |

## excel

- Upstream sources (pinned):
  - https://github.com/openai/skills @ `7b548893` — `skills/.curated/spreadsheet/` (Apache-2.0; later removed upstream by commit `fdf90d6`). Bundled license: `excel/LICENSE.openai-skills.txt`.
  - https://github.com/openai/role-specific-plugins @ `ebf5795` — `plugins/data-analytics/skills/spreadsheets/` (MIT). Bundled license: `excel/LICENSE.openai-role-specific-plugins.txt`.
- Local: `excel/` — original skill, not a copy. Conventions adapted from the pinned sources: formulas for derived values, restrained professional formatting, sources/attribution, charts, bounded edits, QA loops. Nothing from the unavailable `@oai/artifact-tool` tooling or plugin routing is used; commands are `asp` (agent-spreadsheet) and local `openpyxl`/`xlwings` scripts.
- **No Anthropic material**: Anthropic's public `skills/xlsx` was reviewed for comparison only; its license prohibits derivatives, and no text, scripts, assets, or structure from it were copied.

## humanlayer/skills

- Upstream: https://github.com/humanlayer/skills
- Pinned SHA: `ca7c808` (Merge pull request #9, "fix/show-me-user-invocation")
- License: MIT, Copyright (c) 2026 HumanLayer

| Local skill | Upstream path | Local adaptations |
|---|---|---|
| `show-me/` | `plugins/show-me/skills/show-me/SKILL.md` | Kept upstream's `disable-model-invocation: true` (user-invoked only); replaced the `Bash(open path/to/...)` snippet with a plain ` ```bash / open ...` block (pi convention); flattened the trailing `### guidance` header into the body. |
