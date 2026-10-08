---
name: bb-pi-health
description: "Read-only audit of Pi integration with BB: versions, package paths, models, skills, trust and credential exposure, workflow conflicts, and plugin diagnostics. Use when asked to check or troubleshoot the BB–Pi setup, not to control a running task."
---

# BB–Pi health

Inspect the requested setup and separate confirmed failures, configuration risks,
and optional improvements. This is a read-only audit: installation, updates,
configuration edits, authentication, retries, and worker launches require a
separate user request. Do not submit model prompts as an implicit health check.

## Establish scope

Read `bb-cli` and `pi-provider`. Use `bb status --json` to identify the data
root, selected environment, and machine. Default to that machine; a request to
check all machines must name and inspect each separately.

Local shell paths describe the local machine only. Use BB host-aware inspection
for another machine, or report it uninspected. Record the actual Pi agent root
from runtime configuration when available; otherwise check the conventional
`~/.pi/agent` root and state that assumption. Resolve symlinks before recommending
edits, especially when dotfiles are the source of truth.

## Inspect proportionately

Start with the inventory, then follow evidence into the relevant branch:

- **Versions and availability:** `bb --version`, `pi --version`, Node version,
  and BB's provider catalog for the selected environment/machine. Read the
  installed Pi documentation for version-sensitive behavior. Installed does
  not mean latest; verify release sources only if currency matters.
- **Model routing:** allowlisted default provider/model/thinking settings,
  actual session selection when available, and `bb provider models pi` on the
  target machine. A catalog entry proves discovery, not authenticated inference.
- **Resources:** `pi list`, configured resource paths/filters, local extensions,
  agent definitions, and discovered skills. Check missing paths, symlink targets,
  and duplicate names within the same effective provider/scope. Duplicate entries
  in a multi-provider BB catalog are not automatically runtime collisions.
- **BB integration:** bounded plugin status summaries (ID, enabled, status,
  diagnostics), `bb skill cli-skills-status --json`, and relevant tool routing.
  Missing CLI skill copies affect standalone agents; BB-injected skills may
  already work inside BB. Terminal-only UI extensions need not be removed:
  check their mode guards and RPC support before calling them incompatible.
- **Trust and exposure:** project-trust settings, actual BB Pi permission modes,
  extensions that load credentials, and credential-file/parent-directory modes.
  Trust governs project resource loading, not tool access. RPC cannot display
  Pi's built-in trust prompt; explain the effect before recommending `ask`.
  Worktrees and prompt instructions do not provide process isolation.
- **Workflow consistency:** compare user workflow, custom agents/review skills,
  installed `pi-herdsman` guidance, and its effective configuration. Check
  foreground/background assumptions, authorization rules, context inheritance,
  and separate BB-thread/Pi-child concurrency limits. A configured preference
  may be deliberate; label conflicts rather than silently fixing them.

Read the relevant installed Pi docs before interpreting settings, packages,
extensions, skills, or security. Stop expanding the audit when there is enough
evidence to answer the request; an inventory is not a reason to read sessions or
all third-party source files.

## Keep secrets out of the audit

Project only known-safe configuration fields before returning results to the
model. Never print complete settings, environment dumps, `~/.env`, authentication
files, private headers, tokens, or signed URLs. Inspect file metadata and
credential presence without reading values. Withholding values only in the
final answer is too late if they already entered tool output.

Treat logs and plugin diagnostics as potentially sensitive; inspect bounded,
redacted extracts. Check containing-directory permissions before claiming a
credential file is accessible to other users. Propose narrowly scoped credentials
and project-specific environment variables rather than broad credential loading.

## Report

1. **Scope:** machine/environment and files inspected; remote machines skipped.
2. **Working:** facts established by the checks, not assumed end-to-end health.
3. **Issues:** observation, evidence source, impact, and smallest proposed fix.
   Separate failures from risks and preferences; explain each in plain English.
4. **Limits:** extension behaviors/authentication/live services not tested.

Recommend existing BB skills before adding wrappers or more extensions. State
exactly what a proposed fix would change; keep the audit read-only until the
user authorizes that fix. Route requests to operate an existing thread/run to
`bb-pi-control` instead of making control actions part of the audit.
