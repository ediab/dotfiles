---
name: brainstorm
description: Develop a loose idea into a short agreed brief, one question at a time. Explicit invocation only.
disable-model-invocation: true
---

# Brainstorm

Develop the user's idea with them. You only run when explicitly invoked
(`/skill:brainstorm` or an explicit brainstorming request). Never convert a
normal coding request into brainstorming.

## How to run it

1. Read relevant project context before asking factual questions. Look up what
   can be discovered; ask the user for decisions.
2. Establish the user's idea and intended benefit. Stay within that direction:
   suggest smaller versions and relevant improvements, never an unrelated
   feature or a different product.
3. Ask one question at a time. Explain the meaningful options in simple
   English and recommend an answer. Contribute ideas; don't merely
   interrogate.
4. Challenge unnecessary complexity: propose a simpler version and explain
   its cost trade-off. The user decides; never silently substitute the
   reduced version.
5. Cover only what materially matters: the intended experience, the smallest
   useful version, explicit exclusions, and one concrete success example.
   Ask more only when an unresolved choice affects those items.
6. Summarize a short brief and ask whether it matches the user's intent.
   Do not require every edge case to be resolved.

## The brief

Keep it short:

- Idea and purpose
- Who uses it and what they do
- Smallest useful version
- Explicit exclusions
- Concrete success example(s)
- Important decisions and any genuinely unresolved question

A brief is not a technical plan: no dependency selections, signatures,
schemas, ticket hierarchies, or code by default.

## Finishing

Once agreed, offer chat-only or saving to `docs/specs/YYYY-MM-DD-<topic>.md`.
If saving was already requested, save without asking again; inspect the
destination and avoid overwriting unrelated content. Then stop: offer
planning as the next step. Never start implementation, scaffolding, or a
prototype from brainstorming.
