# Work setup: what changed today (2026-10-16)

Today's change was to replace the mixed collection of copied and locally adapted
skills with one upstream pstack installation across Claude Code, Codex and Pi,
while keeping everyday work lightweight and larger workflows explicitly opt-in.

## One upstream skill stack

- Installed [michael-denyer/pstack-claude](https://github.com/michael-denyer/pstack-claude)
  **0.9.86** through each client's native mechanism: Claude Code and Codex plugins,
  and a Pi Git package. Claude uses tag `v0.9.86`; Codex and Pi use commit
  `1dba27e50e8f18f146bb80f137f0690f8d773c2e`.
- Removed the Matt Pocock-derived skills and local pstack adaptations, including
  the old planning/grilling workflows, `diagnosing-bugs`, `domain-modeling`,
  `prototype`, `tdd`, `pi-handoff` and `writing-for-agents`.
- Removed local copies of `bro`, `unslop`, `blast-radius`, `why` and
  `create-verification-skill`. Upstream equivalents remain available without
  duplicate discovery or local forks. Unrelated personal utilities were kept.
- Removed `personal-workflow` rather than maintain another everyday playbook.
  Its useful safeguards now live in the shared global policy.
- Deleted the retired Pi delegation and memory-extension archives. Neither was
  part of the active setup.

## Routine work stays direct; larger workflows are opt-in

- One agent is the default. A large or complex task does not automatically
  authorize `poteto-mode`; it runs only when explicitly requested.
- Disabled pstack's automatic session routing in all three clients with
  `session hook: off` in their tracked `pstack-models.md` files. `link.sh` now
  links those files into each client's user directory. Upstream model and
  effort defaults were left unchanged.
- An explicitly invoked workflow can use the helpers and reviews it prescribes,
  including in standalone Pi. This replaces the old blanket restriction that
  standalone Pi must never use helpers.
- Inside BB, delegation uses BB child threads and messaging. Outside BB, it uses
  the client's native tools. One orchestrator owns integration and verification.
- BB needs no separate pstack installation: it uses the native installation on
  the thread's execution machine. Today's installation was on the Mac, not a
  rollout to the VPS or other machines.

## Pi questions and titles

- Removed the duplicate `@juicesharp/rpiv-ask-user-question` package because
  pstack supplies Pi's question tool. Inside BB, prefer BB's own question tool.
- Simplified `pi/extensions/standalone-ui.ts` to load only `pi-title` outside BB.
  BB continues to own thread titles.

## Shared agent policy

Updated `agents/AGENTS.md`, shared by Pi, Claude Code and Codex:

- Read the relevant code, identify a checkable outcome, and surface consequential
  assumptions and tradeoffs. Resolve factual questions from evidence; ask only
  for decisions that genuinely need the user.
- Make scoped, simple changes that match the surrounding code. Avoid speculative
  abstractions and unrelated cleanup, and remove code made unused by the change.
- Verify the requested behavior and report what changed, what passed and what
  remains unverified. Tests alone do not prove a live service works.
- Keep commits, pushes, PRs, deployments and branch/history changes explicitly
  authorized. Invoking a workflow is not blanket permission for those actions.
- Write in plain, direct, warm language: prefer active voice, consistent technical
  terms, focused sentences and short paragraphs. Preserve exact commands,
  identifiers, values, units and uncertainty. Accuracy takes priority over brevity.
- Use clear steps for instructions, with conditions and warnings before actions.
  Choose prose, diagrams or interactive HTML according to what helps understanding;
  create explainer videos only when requested.

The writing guidance takes useful principles from Simplified Technical English
without imposing strict ASD-STE100 word limits, vocabulary or punctuation rules.
No additional writing skill was installed.

## Documentation and verification

- Updated the README, skill attribution, client settings, linker and tests for
  the new setup. The README has the installation commands for another machine.
- Verified all **63 upstream skills** (39 main skills and 24 principles), native
  discovery, Pi loading inside and outside BB, and disabled automatic routing.
- Linker, deployment-script, Pi integration, title UI and BB preference checks
  passed. The known portability-test failure remains: Mac and Linux Claude
  defaults differ. Those unrelated defaults were not changed.
- Live multi-agent workflows were not exercised. Start fresh client sessions or
  BB threads so old conversation context no longer advertises retired skills.
