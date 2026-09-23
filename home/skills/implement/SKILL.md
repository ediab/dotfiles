---
name: implement
description: "Implement a piece of work based on a spec or set of tickets."
disable-model-invocation: true
---

Implement the work described by the user in the spec or tickets.

Use TDD where possible, at pre-agreed seams — for the loop rules, what makes a good test, and where seams go, read and follow `../tdd/SKILL.md`.

Run typechecking regularly, single test files regularly, and the full test suite once at the end.

Once done, review the work per the owner's rules in `../../personal-workflow/SKILL.md` (substantial-change review; a fresh `reviewer` subagent only when the user requests review delegation or the change is hard to reverse). For a structured two-axis pass, run `/skill:code-review` — its two parallel review subagents are pre-authorized by that skill itself.

Commit your work to the current branch. Push, deploy, branch, or open PRs only when requested.
