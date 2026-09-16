---
name: plan
description: Plan before implementation when explicitly asked to plan or when substantial architectural choices need resolution. A task spanning multiple files alone does not require this skill.
---

# Plan

Explore the relevant code before proposing changes.

Keep investigation read-only; do not implement or edit code while planning.
Read-only tools and shell commands are fine. The only permitted writes are to
the plan document (and its directory) when the user has requested or approved
saving or updating it.

Resolve discoverable questions yourself by reading code. Ask the user only when
a material product or architectural decision cannot be inferred.

Produce a concise implementation-ready plan containing (at most):

- Goal and scope
- Important decisions and rationale
- Relevant files/components
- 2–6 implementation units
- Tests / verification
- Material risks or dependencies

Separate two audiences in one plan: a short user-facing summary (goal,
scope, meaningful choices, recommended approach, what success looks like —
plain English, no implementation detail) plus executor instructions with
enough file/component detail, ordered work, constraints, and checks for a
fresh weaker model to implement. Routine technical choices are the agent's
responsibility, not the user's approval list.

Right-size the plan. Simple work gets a simple plan (goal + files + steps);
use the full list only for genuinely complex work.

Write every plan so a weaker model in a fresh chat with zero memory can
implement it: exact file paths, small ordered steps, what "done" looks like
per step, and what NOT to touch. No vague language.

Every non-trivial plan carries 2–3 concrete, checkable success examples
drafted by you from what the user already said — never ask the user to
define success as an open question. Propose them (e.g. "the digest
contains at most ten stories", "changing the layout does not change which
stories are picked"); the user confirms or edits one, and they become the
acceptance criteria for both the implementer and any reviewer. Clear small
fixes skip this: the request itself is the criterion.

Describe WHAT must change and the important constraints. Do not pre-write
implementation code, exact signatures, or detailed shell command sequences
unless they are necessary to communicate the design.

When complete, show the plan and offer to save it to the project's
`docs/plans/YYYY-MM-DD-description.md`. If saving or updating a plan was already
requested, do it without asking again. Create `docs/plans/` only when saving;
prefix the saved plan with date, original request, working directory, and the
verified branch (or state that it is not a Git repository).

Planning or saving a plan is not approval to implement it. Offer implementation
as the next step and stop pending approval. If the user already explicitly
requested planning followed by implementation, proceed after planning unless
an unresolved decision needs their input.

Delegated planning: a planning subagent returns the plan plus unresolved
decisions to its parent and never saves, edits, or implements — the
owning/main agent handles saving, approval, and any later implementation.
