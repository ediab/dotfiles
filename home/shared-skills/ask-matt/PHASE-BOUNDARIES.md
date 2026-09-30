# Phase boundaries

A **phase** is a meaningful chunk of work, such as exploration, implementation, or QA. The boundary is the point where one phase is complete and the next is about to begin. Make context-management decisions there; in the middle of a phase, continue or delegate the remaining work.

## The five options

| Option | What it does |
|---|---|
| **Continue** | Stay in the current context; no information is lost. |
| **Reset** | Start with an empty context when the current one is irrelevant to the next phase. |
| **Hand off** | Write a portable note so another client, directory, or person can pick up the work. |
| **Delegate** | Send a self-contained task to an independent agent and receive its result. |
| **Summarize** | Compress the context when it still matters but needs more room. |

## The decision tree

Work top to bottom at the boundary. The first **yes** wins.

**1. Can you continue in this context?** Continue when the next phase needs the current reasoning as a primary source, or comfortably fits in the remaining context. For example, implementation often benefits from the exploration and decisions that came before it. Continuing costs nothing and loses nothing, so rule it out before other options.

**2. Is the current context irrelevant?** If the exploration, decisions, and dead ends are all disposable, reset. This is the cheapest way to recover a full context. Resetting relevant context is costly: it loses the rationale behind the work, which may not be recoverable from a diff alone.

**3. Does the work need to travel?** Hand off when moving to another client or repository, sending work to a collaborator, or forking a side task without disrupting the current phase. A handoff buys portability; use it only when something needs to travel.

**4. Can the task run without your steering?** Delegate a tightly scoped, independently useful task when the agent can complete it without further decisions from you. Independent review is a common example.

**5. Otherwise, summarize.** When the context still matters, the work stays with you, and it needs more room, summarize it for continuation. Preserve decisions and rationale rather than only listing completed steps.

Summarization is the default only after the earlier choices fail. The failure mode of starting there is a fresh context that is confidently wrong about a decision flattened out of the summary.

## Primary and secondary sources

Every option except **Continue** turns the current conversation into a secondary source: a summary replaces the full reasoning. The trade is consistent:

| Source | Information | Noise | Room to move |
|---|---|---|---|
| Primary (continue) | Full | More | Less |
| Secondary (handoff or summary) | Lossy | Less | More |

This is why continuing comes first. Pay the lossiness only when staying costs more than it saves.

## These are judgment calls

The questions are not objective; the same boundary can go either way. The value is in asking them in order, at the boundary rather than mid-phase.
