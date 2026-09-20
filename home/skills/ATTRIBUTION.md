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

## humanlayer/skills

- Upstream: https://github.com/humanlayer/skills
- Pinned SHA: `ca7c808` (Merge pull request #9, "fix/show-me-user-invocation")
- License: MIT, Copyright (c) 2026 HumanLayer

| Local skill | Upstream path | Local adaptations |
|---|---|---|
| `show-me/` | `plugins/show-me/skills/show-me/SKILL.md` | Kept upstream's `disable-model-invocation: true` (user-invoked only); replaced the `Bash(open path/to/...)` snippet with a plain ` ```bash / open ...` block (pi convention); flattened the trailing `### guidance` header into the body. |
