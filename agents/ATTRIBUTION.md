# Third-party skills — provenance

## pstack

- Upstream port: https://github.com/michael-denyer/pstack-claude
- Original: https://github.com/cursor/plugins/tree/main/pstack, by Lauren Tan.
- Installed release: `0.9.86`, tag `v0.9.86`, commit `1dba27e50e8f18f146bb80f137f0690f8d773c2e`.
- License: MIT, with imported material and notices supplied by the upstream package.
- Installed through the native Claude Code plugin, Codex plugin and Pi package. No pstack skill files are copied into `agents/skills/` or modified locally.
- Host, BB delegation and safety overrides live in `agents/AGENTS.md`, not upstream files. See the root README for installation and updates.

## pbakaus/impeccable

- Upstream: https://github.com/pbakaus/impeccable
- Installed skill release: `4.6.0`; engine `0.1.15`, using `npx impeccable@4.6.0 install --providers=claude,codex,pi --scope=global --no-hooks --yes`.
- License: Apache-2.0; upstream `LICENSE` and `NOTICE.md` are bundled with the tracked Codex skill.
- The supported installer supplies provider-specific builds. `agents/skills/impeccable/` is the Codex build, unchanged; Claude/Pi native copies and Claude helper profiles are installed outside this repo. Runtime binaries are ignored by Git.
- No skill playbooks are patched. Pi excludes the shared duplicate, and the linker preserves Claude's native build. Automatic detector hooks are not installed.

## Dammyjay93/interface-design

- Upstream: https://github.com/Dammyjay93/interface-design
- Installed revision: `2f9be3206855bcb2d1d0af262c8bae25cba6658d`.
- License: MIT; upstream `LICENSE` is bundled in the skill folder.
- Installed core skill and Codex metadata are unchanged, via `skills@1.7.2`. Shared by Claude Code, Codex and Pi through the existing skill locations/links. Claude plugin commands are not installed.

## anthropics/skills

- Upstream: https://github.com/anthropics/skills
- Imported in local commit `0c6cdc4`; latest reviewed upstream commit touching the path: `41bbe19d1a1a7eaab5e7bb9050a417e5c6cffc8f` (2026-09-03).
- License: Apache-2.0; `LICENSE.txt` remains bundled in the skill folder.

| Local skill | Upstream path | Local adaptations |
|---|---|---|
| `frontend-design/` | `skills/frontend-design/SKILL.md`, `LICENSE.txt` | User-invoked with Codex policy metadata; brief clarification asks rather than invents the subject; visual guidance rewritten locally. |

## humanlayer/skills

- Upstream: https://github.com/humanlayer/skills
- Pinned SHA: `bba9d13ab34f0a87f1cc33df4dd196372393ddfc` (2026-09-12).
- License: MIT, Copyright (c) 2026 HumanLayer.

| Local skill | Upstream path | Local adaptations |
|---|---|---|
| `show-me/` | `plugins/show-me/skills/show-me/SKILL.md` | Verbatim; user-invoked. |

## Global policy references

The concise assumption/tradeoff, scoped-edit and checkable-outcome guidance in
`AGENTS.md` was informed by [Karpathy's original observations](https://x.com/karpathy/status/2015883857489522876)
and the [community-written Karpathy-inspired guidelines](https://github.com/multica-ai/andrej-karpathy-skills/blob/main/CLAUDE.md).
The latter is not Karpathy's own instruction file. No additional skill or plugin
is installed, and the full checklist is not copied into the global policy.

## Retired copies

All Matt Pocock-derived skills have been removed from active discovery, along with the local `personal-workflow`, adapted Cursor pstack skills and the luchasarie `bro` copy. Their prior attribution and adaptations remain in Git history. The local spreadsheet skill and its bundled license files are also retired and remain in Git history.
