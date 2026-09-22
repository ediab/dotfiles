# Brief: Jev-routed subagent models + notify-mode session routing

Date: 2026-02-06

## Idea & purpose

Borrow the pi-jev-model-router architecture (typed judgment → tier mapping → gated switching → fail-open) to give pi automatic model + thinking-level selection at subagent launches, and to evaluate (not yet adopt) adaptive main-session routing.

## Who uses it

Daily pi sessions with the existing agent roster (`~/.pi/agent/agents/` — explorer, worker, reviewer, codebase-analyzer, etc.).

## Smallest useful version (v1)

1. A small pi extension that intercepts agent spawns (Agent tool + pi-subagents `agent()` calls).
2. On spawn: one Jev typed judgment on the subtask → task kind + complexity + capability deserved → maps to a tier from the approved tier chains (quick / standard / high, ordered fallback lists — first authenticated model wins, next is fallback; a model that errors/quota-fails is avoided for the rest of the session).
3. Per-agent-type tier floor (explorer ≥ quick, worker ≥ standard, reviewer ≥ high — tunable in one config file).
4. Thinking level set alongside the model (Jev's `needs_deep_reasoning` → low/high, clamped by what the model supports).
5. Decision logged in the transcript: model, tier, kind, why. Fails open — Jev unreachable or unknown model → launch on the default model with a warning.
6. Main session: install pi-jev-model-router in notify mode for a few days; it logs what it *would* do, changes nothing.
7. No budget caps in v1 — the config keeps the `budget` block shape so caps can be enabled later without redesign.

## Explicit exclusions (v1)

- Budget caps / pressure downgrades
- Per-provider quota tracking
- Boundary-only routing mode
- `/jev-route`-style arbitrary-text classification
- Confirm-mode overlays

## Concrete success example

A plan request delegates to a `codebase-analyzer`; the extension judges it
`research · complexity 1.4 · capability 1.2` → `standard`, launches it on the
standard chain's first available model, thinking `low`, and the transcript shows:

```
subagent-router → standard: codebase-analyzer, research, floor standard
```

A quick "find where X is logged" spawn goes to `quick` on a flash model.
Nothing blocks; a dead API key degrades to default-model launches with a
status-line warning.

## Open prerequisite

- TypeSafe API key with `jev-latest` access (`TYPESAFE_API_KEY`) — needed by both the subagent extension and the notify-mode trial. No key found on the machine as of 2026-02-06.
- User input: the actual approved model list + per-agent floors (one config edit).

## Decisions made

- Judge: external Jev typed judgment (not model self-assessment, not heuristics).
- Enforcement: extension intercepts spawn; the chat launches normally.
- Model list: tier chains with per-agent-type minimum tiers.
- Main session: try pi-jev-model-router in notify mode first; per-prompt judging (1 cheap Jev request) with rare, gated switches (deadband + cache-penalty + stickiness). Revisit a custom boundary-only router if the per-prompt judging proves annoying.
- Budget: deferred to v2; config shape reserved.
