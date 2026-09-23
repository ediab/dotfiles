---
name: implement
description: "Implement a piece of work based on a spec or set of tickets."
disable-model-invocation: true
---

Implement the work described by the user in the spec or tickets.

Use TDD where possible, at pre-agreed seams — for the loop rules, what makes a good test, and where seams go, read and follow `../tdd/SKILL.md`.

Run typechecking regularly, single test files regularly, and the full test suite once at the end.

Once done, review the work yourself as the owner (personal-workflow's substantial-change rule: re-read the changeset against the agreed intent and acceptance examples, state what was checked); a fresh `reviewer` subagent only when the user requests review delegation or the change is hard to reverse.

Commit your work to the current branch. Push, deploy, branch, or open PRs only when requested.
