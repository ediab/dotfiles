# Confidence in historical evidence

Code shows what happens; it does not carry its own motivation. Commits, PRs, tickets, documents, and conversations are incomplete records. Assign each rationale claim a confidence tier and preserve that distinction in the answer.

| Tier | Evidence required | How to phrase it |
|---|---|---|
| Direct | Someone explicitly documented the reason in a relevant source. | “The PR states that X was added because Y,” with the citation. |
| Supported | Several independent clues converge, but none explicitly states the reason. | “The evidence points toward Y,” followed by the specific clues. |
| Inferred | A reasonable contextual interpretation without direct support. | “Given A and B, Y appears likely”; show the reasoning and alternatives. |
| Speculative | Thin evidence; multiple explanations fit equally well. | “One possibility is Y, but no direct evidence was found.” |
| Unknown | Relevant sources were searched without establishing the reason, or important evidence is unavailable. | Name the searches, gaps, and unanswered question. |

A direct citation proves what its author said, not that the explanation was complete, correct, or still applicable. Separate intention from demonstrated outcome.

## Common traps

- **Rationalization:** do not assume the author chose correctly and work backward from current code to a clean rationale.
- **Recency bias:** last-touch history can obscure the original constraint and later accretion.
- **Agreement with the user:** an embedded hypothesis is something to test, not a conclusion.
- **Absence of evidence:** an unsuccessful search does not prove a reason never existed.
- **Contradiction smoothing:** a ticket's customer requirement and a PR's cleanup rationale may both matter. Cite both and leave unresolved contradictions visible.

Use causal claims such as “was designed to” only with evidence for intent. Use “appears,” “suggests,” or “one reading is” for inference. Editing for clarity must not remove these qualifications.

## Before returning the answer

For each claim, check that the citation exists, supports the stated reason, and matches the confidence wording. Move unsupported claims into inference or speculation rather than inventing support. State material unknowns and what would resolve them; if no gap remains, explain the evidence that makes the answer complete.
