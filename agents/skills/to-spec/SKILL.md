---
name: to-spec
description: Turn the current conversation into a spec and save it under the project's docs directory. No interview; just synthesis of what has already been discussed.
disable-model-invocation: true
---

This skill takes the current conversation context and codebase understanding and
produces a spec. Do NOT interview the user; just synthesize what you already know.

Before writing, resolve discoverable questions yourself by reading the code. Ask
the user only when a material product or architectural decision cannot be
inferred. Planning or saving a spec is not approval to implement it — offer
implementation as the next step and stop pending approval. If the user already
explicitly requested planning followed by implementation, proceed after planning
unless an unresolved decision needs their input.

## Process

1. Explore the repo to understand the current state of the codebase, if you
   haven't already. Use the project's shared domain vocabulary throughout the
   spec (see the `domain-modeling` skill / `CONTEXT.md` if one exists), and
   respect any ADRs in the area you're touching.

2. Sketch out the seams at which you're going to test the feature. Existing
   seams should be preferred to new ones. Use the highest seam possible. If new
   seams are needed, propose them at the highest point you can. The fewer seams
   across the codebase, the better — the ideal number is one.

   Check with the user that these seams match their expectations.

3. Write the spec using the template below, then show it to the user. Offer to
   save it to the project's `docs/specs/YYYY-MM-DD-description.md` (or the
   location the project already uses for specs). If saving or updating a spec
   was already requested, do it without asking again. Create the directory only
   when saving; prefix the saved spec with the date, the original request, the
   working directory, and the verified branch (or state that it is not a Git
   repository).

<spec-template>

## Problem Statement

The problem that the user is facing, from the user's perspective.

## Solution

The solution to the problem, from the user's perspective.

## User Stories

A LONG, numbered list of user stories. Each user story should be in the format of:

1. As an <actor>, I want a <feature>, so that <benefit>

<user-story-example>
1. As a mobile bank customer, I want to see balance on my accounts, so that I can make better informed decisions about my spending
</user-story-example>

This list of user stories should be extremely extensive and cover all aspects of the feature.

## Implementation Decisions

A list of implementation decisions that were made. This can include:

- The modules that will be built/modified
- The interfaces of those modules that will be modified
- Technical clarifications from the developer
- Architectural decisions
- Schema changes
- API contracts
- Specific interactions

Do NOT include specific file paths or code snippets. They may end up being outdated very quickly.

Exception: if a prototype produced a snippet that encodes a decision more precisely than prose can (state machine, reducer, schema, type shape), inline it within the relevant decision and note briefly that it came from a prototype. Trim to the decision-rich parts, not a working demo, just the important bits.

## Testing Decisions

A list of testing decisions that were made. Include:

- A description of what makes a good test (only test external behavior, not implementation details)
- The seams at which the work will be tested
- Which modules will be tested
- Prior art for the tests (i.e. similar types of tests in the codebase)

## Out of Scope

A description of the things that are out of scope for this spec.

## Further Notes

Any further notes about the feature.

</spec-template>

Right-size the spec: small, clear work gets a short spec (problem, solution,
decisions, out of scope); use the full template only for genuinely complex
work. Every non-trivial spec carries 2–3 concrete, checkable success examples
drafted by you from what the user already said — never ask the user to define
success as an open question. Propose them; the user confirms or edits them, and
they become the acceptance criteria for both the implementer and any reviewer.
Clear small fixes skip this: the request itself is the criterion.
