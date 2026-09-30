---
name: why
description: Investigate a design decision's history and distinguish documented reasons from inference.
disable-model-invocation: true
license: MIT
---

# Why

Find what led to the code's shape, not a story that makes the current code sound sensible. This is historical investigation, not runtime diagnosis or permission to change the design.

Read [the confidence framework](references/epistemics.md) before evaluating evidence.

## Procedure

1. **Anchor the question.** Identify the decision, paths, line ranges, and symbols. State a narrow interpretation when context resolves an ambiguous referent; ask when different interpretations would materially change the investigation.
2. **Trace its lineage.** Read the current code and relevant ADRs/docs, then inspect introduction and subsequent changes rather than stopping at the latest blame. Useful commands:
   ```bash
   git blame -L <start>,<end> -- <file>
   git log --follow -p -- <file>
   git log --oneline -20 -- <file>
   git show <commit> -- <file>
   git log -1 --format=%B <commit>
   ```
   These are command shapes: substitute real paths and revisions. In an unversioned checkout or shallow history, report the limitation rather than pretending the missing record was searched.
3. **Follow the evidence.** Read relevant commit messages, code comments, tests introduced with the change, and linked decisions. Where available, inspect PR bodies, discussions, reviews, and linked issues; for example:
   ```bash
   gh pr view <number> --json title,body,comments,reviews,closingIssuesReferences
   ```
   Git/docs alone are enough to start. Use connected organizational sources only when they can answer a remaining question and access is available. Do not install tools, request broad access, or search every source category for a narrow question. Name important unavailable or unsearched sources.
4. **Compare explanations.** Treat the user's proposed reason as one hypothesis. Look for contrary evidence and changed constraints. Code behavior and test shape can support an interpretation but do not establish author intent without a documented reason. Surface conflicting records rather than selecting the tidiest one.
5. **Calibrate and cite.** Check each rationale claim against the confidence framework. Citations must resolve to the relevant historical version, commit, document section, or discussion. Separate what was documented then from what is true now.

The owner investigates and synthesizes. Delegate only genuinely independent source investigation when warranted under the host's rules; no fixed reviewer roster or mandatory handoff.

## Report

Keep the answer proportionate to the question:

- **Question and code anchor:** the bounded decision and paths/symbols.
- **Documented reasons:** direct evidence with citations.
- **Supported interpretations:** converging evidence, or clearly labeled inference.
- **Alternatives and unknowns:** conflicting explanations and what the record cannot establish.
- **Sources consulted:** the actual searches, useful null results, and material access/coverage gaps.

An honest “unknown” is a completed investigation when the relevant record has been checked. Do not turn “we found no rationale” into “there was no rationale.”

When this precedes a change, finish with **Preserve / Change / Avoid / Risk** constraints derived from the evidence, distinguishing historical constraints from current recommendations. Implementation still follows the user's approval and project rules. Redact private information before sharing evidence.
