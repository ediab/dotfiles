---
name: blast-radius
description: Investigate downstream breakage and test the assumptions that make a change safe.
disable-model-invocation: true
license: MIT
---

# Blast radius

Review a change's effects beyond its diff. Listing direct callers is a starting point, not the deliverable. Find the safety assumptions that matter, then test them against real code.

## Evidence ladder

For each assumption, reach the strongest evidence that is proportionate and safe, and say where you stopped:

1. **Asserted:** a plausible explanation without supporting evidence. Mark it unproven.
2. **Cited:** an actual `file:line`, pinned dependency source, or documented contract.
3. **Traced:** the concrete failure path and the condition that prevents or permits it.
4. **Executed:** a test or script calling real code, with a meaningful assertion and recorded output.
5. **Exercised:** the relevant behavior reproduced in an isolated running app.

A citation is not an executed check. A passing check proves only the cases and assumptions it exercises.

## Investigation

1. **Pin the change and intent.** Read the requested diff or files, changed/deleted symbols, and relevant surrounding code. State the base and scope. Inspect commits and PR context when available; if intent is materially unclear, ask before judging safety.
2. **Name the safety assumptions.** Identify the facts the change depends on, such as “this operation only deletes expired entries.” Several contracts may require several assumptions. Spend effort proving those, not producing a long list of imaginary risks.
3. **Look where symbol search stops.** Trace callers and downstream consumers, then inspect serialization, API responses, database columns, other languages reading the same bytes, feature flags, and indirect entry points. Check pinned library versions and local patches. Follow execution order, asynchronous work, teardown, and ownership when they affect the contract.
4. **Try to break the assumptions.** Walk a concrete triggering case. Cite the real input path and affected consumer. Distinguish confirmed risks, plausible unresolved risks, and paths checked and cleared. Describe likelihood qualitatively from evidence; do not invent probabilities or callers.
5. **Run the cheapest meaningful proof.** Use an existing test or a temporary script that imports the actual code/library. Assert the risky behavior, run it, and retain the command and relevant output. When the check needs app state, use a disposable local instance.

This is an investigation, not permission to repair product code, change branches, or ship. Keep proof artifacts separate from unrelated work. Clean up only resources you created and preserve useful evidence. Shared/live data, external mutations, or paid actions require explicit permission. If access or a safe check is unavailable, report the assumption as unproven and name the missing check.

Work in the current context by default. Independent delegated review is optional only when requested under the host's review rules; a broad change does not authorize automatic fan-out.

## Report

- **Change:** what changed, including non-obvious effects and the reviewed scope.
- **Assumptions:** each safety fact, evidence level, citations, and executed proof or an explicit “unproven.”
- **Risks:** concrete failure path, affected consumer, impact, and evidence or next check.
- **Cleared:** cases checked and why the evidence clears them.
- **Remaining checks:** the cheapest useful test or repro for what is still unresolved.

Redact secrets in commands, outputs, and artifacts. Keep claims within the evidence; do not describe the change as safe merely because the report sounds convincing.
