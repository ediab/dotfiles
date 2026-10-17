# Third-party skills — provenance

## pstack

- Upstream port: https://github.com/michael-denyer/pstack-claude
- Original: https://github.com/cursor/plugins/tree/main/pstack, by Lauren Tan.
- Installed release: `0.9.92`, tag `v0.9.92`, commit `7bad1ebc26faa268806bfbb84e5af55d178b68e4`.
- License: MIT, with imported material and notices supplied by the upstream package.
- Installed once per host through the Pi package. Claude Code and Codex have no native pstack installation. No pstack skill files are copied into `agents/skills/` or modified locally.
- Host, BB delegation and safety overrides live in `agents/AGENTS.md` and `bb/AGENTS.md`, not upstream files. See the root README for installation and updates.

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

The local `frontend-design/` copy of [Anthropic's frontend-design skill](https://github.com/anthropics/skills/tree/main/skills/frontend-design)
was retired once Impeccable, which builds on that skill, covered the same ground at greater depth.
Its prior attribution, bundled Apache-2.0 license and local adaptations remain in Git history.
