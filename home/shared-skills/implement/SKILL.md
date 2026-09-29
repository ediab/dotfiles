---
name: implement
description: "Implement a piece of work based on a spec or set of tickets."
disable-model-invocation: true
---

Implement the work described by the user in the spec or tickets.

Use TDD where possible, at pre-agreed seams — for the loop rules, what makes a good test, and where seams go, read and follow `../tdd/SKILL.md`.

Run typechecking regularly, single test files regularly, and the full test suite once at the end.

Once done, review the changes against the current project's instructions and the owner's review and delegation rules. Keep the review inline by default; delegate only when the host client and user authorize it. Use an available review workflow if requested, without assuming a named agent, skill, or slash command exists.

Follow the project's and host client's Git policy for commits, branches, and publishing. Push, deploy, or open PRs only when requested.
