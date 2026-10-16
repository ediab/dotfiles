# pstack model configuration

Per-role overrides for pstack skills. Delete a role line to use the skill default.
`inherit-parent` and `auto` use the parent session's model. Each panel entry
counts as one agent, including aliases. An optional `@low`, `@medium`, `@high`,
`@xhigh`, or `@max` suffix overrides the default effort for that entry.
`default effort: session` preserves the parent's reasoning effort.
`session hook: off` disables automatic poteto-mode routing.

pi models: opus=openai/gpt-6.1-sol, fable=openai/gpt-6-astra, sonnet=deepseek/deepseek-flash, haiku=openai/gpt-6-luna

feature, refactoring: opus
bug-fix: fable
perf-issue: fable
hillclimb: fable
judgment and prose: opus
strongest judgment: fable
how explorer: opus
how explainer: opus
why investigators: opus
why synthesizer: opus
reflect tooling: opus
reflect judgment, divergent, synthesizer: opus
arena runners: opus, fable, sonnet, haiku
arena cross-judge pool: opus, fable, sonnet, haiku
swarm workers: opus
architect runners: opus, fable, sonnet, haiku
interrogate reviewers: opus, fable, sonnet, haiku

default effort: session
session hook: off
