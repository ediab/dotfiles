---
name: agentsmd-for-projects
description: Create or update a concise, repository-grounded AGENTS.md covering structure, tooling, architecture, verification, and change discipline.
disable-model-invocation: true
---

# AGENTS.md for projects

Create a short root `AGENTS.md` that tells coding agents how to work in this repository. Use the target repository supplied by the user, or the current repository when no target is supplied.

## 1. Inspect

Read applicable ancestor and repository `AGENTS.md` / `CLAUDE.md` files before drafting. Inspect the directory layout, README, package manifests, lockfiles, verification configuration, and relevant architecture documents or ADRs. For a monorepo, inspect workspace configuration and representative package manifests to establish ownership and scoped commands.

Finish inspection when you can identify the major code owners, actual tooling, available verification commands, and documented architectural boundaries. Resolve facts from repository evidence; ask the user only when a consequential policy or conflicting source cannot be resolved by inspection.

## 2. Draft

Use `# Repository Context` as the title. Prefer the following sections, adapting or omitting them when the repository warrants it:

- **Structure:** list the major directories and their responsibilities. Explain how to identify the owning package or component before editing, and when cross-boundary changes are warranted.
- **Package manager / tooling:** name the actual toolchain and any documented exclusivity rule. Include a small set of useful install and verification commands confirmed in manifests, configuration, or maintained documentation. Prefer scoped commands where supported.
- **Architecture:** state evidenced ownership boundaries and reuse expectations. Point to existing architecture documentation and ADRs, with the condition for reading each.
- **Verification:** require a concrete check for each code change. Prefer a focused test for changed behaviour, then component/package checks, then broader checks when boundaries are crossed. Require reporting what ran and what remains unverified; a command's existence is not evidence that it passed.
- **Change discipline:** match existing patterns, modify existing abstractions rather than creating parallel ones, make the smallest complete change, and remove obsolete code when replacing behaviour. Keep abstractions and dependencies tied to current requirements.

Write direct, actionable sentences and compact bullets. The section outline is a style guide, not a fixed template: single-package and non-JavaScript projects should read naturally without monorepo or JavaScript assumptions.

Keep repository facts separate from proposed policy. Preserve intentional existing instructions and identify conflicts explicitly. Any new normative rule not already established is a proposal for the user's approval, not an inferred repository fact.

Every named path must exist and every suggested command must be supported by repository evidence. Include directory summaries and command shortcuts only where they materially guide work; avoid exhaustive inventories and duplicated configuration. Keep detailed procedures in existing linked documents. Omit unsupported sections rather than inventing architecture, commands, or documentation.

## 3. Preview and approve

Show the complete proposed `AGENTS.md`, summarize material changes if updating an existing file, and list unresolved assumptions or proposed policies separately. Stop for approval before writing. If the user requests revisions, revise the preview and obtain approval for the new version.

## 4. Write and validate

After approval, create or update only the target root `AGENTS.md`. Preserve unrelated user changes; if the file changed after the preview, reconcile those changes before applying the approved draft.

Re-read the result and verify:

- every listed path and documentation pointer exists;
- commands match the repository's tooling and available scripts or documented invocations;
- architectural claims have repository evidence;
- approved policies are consistent with applicable instructions;
- the document is concise and contains no unresolved placeholders.

Report the file path, checks performed, and any remaining uncertainty. Do not run installs or broad test suites merely to validate this documentation, and do not claim application behaviour was verified.

## Success examples

- A pnpm monorepo gets evidenced package ownership and existing pnpm commands, with scoped checks where supported.
- A single-package Python repository gets its actual Python tooling and component boundaries, without copied JavaScript sections.
- A repository with an existing `AGENTS.md` gets a proposed update that preserves intentional rules and surfaces conflicts for approval.
