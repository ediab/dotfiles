# Pi performance and token-usage audit

Revised 2026-09-29 after checking the original findings against the live config, the Pi docs, provider docs and published research.

**Historical baseline:** measurements below describe the setup before the package removals
and router deletion; they are not measurements of the current lean setup. The later repo
cleanup removes stale workflow/config references, fixes package reconciliation, sets `/btw`
to DeepSeek Flash/high, and corrects the web-summary model. Those repo changes still need
an explicitly requested local apply (and a separate VPS deployment if wanted) to reach live
configuration, except the inactive observational-memory key, whose live removal was separately
approved to prevent the legacy capture job from restoring it. Package reconciliation is a
separate software-management action, not implied by a configuration apply.
Re-measure before claiming gains.

## Verdict: simplify the setup, don't reinstall

The historical investigation found configuration/workflow overhead, not a broken installation.
Some recommendations below have since been addressed; remaining effort/cache hypotheses
still need an A/B test against the current setup.

**Evidence labels used below**

- **[audit]** measured in the original investigation; not re-measured in this revision.
- **[local]** checked during the historical audit against files in this repo or `~/.pi/agent`; not evidence that those files/settings still exist.
- **[docs]** stated in Pi or provider documentation.
- **[inference]** my reasoning from the above; not directly measured.

## What the measurements show

The usage sample covered 16 main sessions and 10 linked subagents, excluding the investigation itself. **[audit]**

| Finding | Measurement | Meaning |
|---|---:|---|
| Heavy initial context | 23,216 tokens median on first requests | Substantial overhead before useful work begins |
| Growing conversation history | 124,716 tokens median per request | Long sessions repeatedly carry a lot of context |
| Caching generally works | 94.1% of main input context was cache reads | Large token totals are not the same as fresh processing or spend |
| Extensive reasoning | 69.3% of output tokens were reasoning | Much of what is generated is not the answer you see |
| Very high effort settings | 75% of requests recorded `max` or `xhigh` | History favours thoroughness over speed |

**Added in this revision [local]:** a bounded scan of the 20 newest session files shows the model mix is almost entirely OpenAI Codex, not the DeepSeek default:

| Provider / model | Assistant turns |
|---|---:|
| openai-codex / gpt-6-luna | 573 |
| openai-codex / gpt-5.6-sol | 251 |
| opencode-go / gpt-6-luna | 158 |
| openai-codex / gpt-6-astra | 108 |
| pi-claude-cli / claude-sonnet-5 | 15 |
| opencode-go / glm-5.3-flash | 2 |

Recorded thinking-level changes in the same files: `high` 22, `xhigh` 10, `max` 7, `low` 3, `medium` 2, `off` 1. Level changes trend upward, and each one is a mid-session change (see finding 1).

**Historical context:** the default was `deepseek-flash` during that sample, but most traffic
used other models. The current repo default is OpenAI; consult `home/settings.json` rather
than treating this historical model mix as the present workload.

## Findings, with justification

### 1. Effort should be set per model, not globally to `medium`

**Original recommendation:** "Try medium reasoning for ordinary work."

**Revised recommendation:** set `modelThinkingLevels` in `home/settings.json` (keyed `provider/modelId`) and stop raising effort mid-session:

| Model | Suggested startup level | Reason |
|---|---|---|
| `openai-codex/gpt-6-luna`, `gpt-5.6-sol` | `medium` | Bulk of traffic; OpenAI documents lower effort as a speed/token trade-off and recommends comparing on representative tasks |
| `openai-codex/gpt-6-astra` | `high` (`xhigh`/`max` opt-in) | Reserved for hard work |
| `deepseek/deepseek-flash` | `low` | See below: `medium` does nothing here |
| `pi-btw` side channel | `high` | The approved repo cleanup changes `max` to `high`, keeping `deepseek/deepseek-flash`; latency has not been re-measured |

**Justification**

- **`medium` is a no-op on DeepSeek. [docs]** DeepSeek's thinking-mode page maps requested `medium` and `xhigh` to `high`; only `low` and `max` differ. Changing `defaultThinkingLevel` to `medium` would leave the default model unchanged.
- **Reasoning also inflates later input on DeepSeek. [docs]** For requests that carry `tools`, all prior `reasoning_content` must be passed back and is concatenated into context. Heavy reasoning therefore costs output now and input on every later turn. This links the 69.3% reasoning share to the 124,716-token median context, a connection the original audit did not make. **[inference]** for how much of the median it explains.
- **Effort changes can break the cache. [docs]** OpenAI's caching doc lists `model`, `tools` and `reasoning.effort` as settings that can stop the prefix from matching. Setting effort once at startup keeps the prefix stable. The upward drift in recorded level changes above is a plausible source of some cache misses, but the logs do not prove it. **[inference]**
- **Benchmark caveat.** I did not find a trustworthy coding-specific benchmark of effort level versus quality; what exists is vendor material. Treat the suggested levels as hypotheses for the measurement plan, not conclusions.

### 2. Tool definitions are the main context cost; cut overlapping delegation systems

**Finding:** Pi-subagents, Herdr and Pi-tasks account for 76% of registered extension-tool definition bytes; instructions plus tool definitions total roughly 114 KB before history. **[audit]** This is a size measurement, not a billed-token count.

**Status:** addressed in package declarations: `@tintinweb/pi-subagents` remains;
`pi-tasks` and `pi-herdr` are removed. The old 76%/114 KB figures are not current tool costs.
Compact Agent descriptions are configured; the separate workflow description remains full.

**Justification**

- **Use package filters, not runtime toggling. [docs]** Pi's filter syntax (`extensions: []`, `!pattern`) applies when the session starts. That keeps the tool list, and so the cached prefix, stable. Pi's docs also describe `setActiveTools` and `deferred`/`hidden` exposure levels for extensions; I could not confirm those are user-settable rather than author-only, so I am not relying on them.
- **Filters work per package and resource type, not per tool. [docs]** You can drop an extension; you cannot drop one tool out of it.
- **Tool-heavy prompts cost accuracy as well as tokens, but the numbers are from much larger libraries. [docs]** Anthropic reports an 85% token reduction and accuracy gains (Opus 4: 49% to 74% on MCP evals) from deferring tool definitions in large tool libraries. Your set is far smaller, so expect a smaller effect.
- **Multi-agent orchestration is expensive by design. [docs]** Anthropic's own data: agents use about 4x the tokens of chat and multi-agent systems about 15x, worth it only for high-value, parallelisable work. This supports having one delegation path used deliberately.

### 3. Broad skill triggers load procedure text unnecessarily

**Finding:** Ponytail's description says "Use on ANY coding task" (confirmed in its `SKILL.md` **[local]**), which conflicts with your policy of opting in. The investigation session loaded about 30 KB of procedural guidance. **[audit]**

**Status:** Ponytail is removed, not vendored or made explicit-only. Its old broad trigger
is no longer part of this setup. Keep remaining heavyweight procedures explicitly invoked
where their current skills specify that policy.

**Justification**

- **Mechanism. [docs]** Pi puts each skill's name, description and path in the system prompt on every request and loads the full `SKILL.md` only when the task matches. A broad description therefore both costs tokens every turn and invites full loads. `disable-model-invocation: true` keeps a skill out of automatic selection; it then runs only via `/skill:name`.
- **Precedent in this repo. [local]** Seven local skills (brainstorm, to-spec, to-tickets, frontend-design, ...) already use that flag.

### 4. Router escalation sends uncertain work to the heaviest tier

**Finding:** both helpers in the investigation were routed to Astra/high with uncertainty/high-stakes classifications; routing itself took only 316-547 ms. **[audit]** The consequential choice is the heavyweight execution, not the routing latency.

**Status:** the Jev router and its configuration have been deleted. There are no router
thresholds to tune. Agents now use profile/session models; `explorer` has an explicit model.
The two historical helper runs do not establish the cost of the current arrangement.

### 5. Cache misses are expensive but unexplained

**Finding:** 54 requests accounted for 64.5% of non-cache-read input; the logs do not establish why. **[audit]**

**Status:** `home/settings.json` now enables `showCacheMissNotices`; confirm the live setting
before diagnosing cache behavior. This is instrumentation, not evidence that cache misses
have been resolved.

**Justification**

- **Don't guess a fix. [docs]** Both OpenAI and DeepSeek require the whole rendered prefix to match; any change to tools, model, effort or compaction earlier in the prompt invalidates everything after it. That gives a checklist of candidates (mid-session effort or model switches, tool set changes, compaction, idle gaps beyond cache lifetime) but no way to say which applies here without the notices. **[inference]**
- **Cost context. [docs]** On DeepSeek Flash a cache hit is $0.003/M versus $0.15/M for a miss (off-peak), a 50x ratio, but absolute spend on Flash is small; the pain there is mostly latency. Token spend matters more on the Codex tiers.

### 6. Session length and compaction

**Recommendation:** start a fresh session when changing tasks, carrying decisions over manually. Do not compact constantly.

**Justification**

- **Compaction is a rare, costly event. [docs]** Pi auto-compacts when `contextTokens > contextWindow - reserveTokens` (default reserve 16,384), so on a 1M-context model such as DeepSeek Flash it would not trigger until near 984K. Summarization requests skip cache writes, cost their own LLM usage, and replace earlier content, which changes the prefix for later requests.
- **Optional lever:** `compaction.modelOverrides` can adjust thresholds per model. Treat it as something to test, not a default change.

### 7. What not to do

- **Don't reinstall.** Nothing indicates a broken install.
- **Don't trim `AGENTS.md`.** The generated file is 1.3 KB **[local]**. The heavy prefix is tool definitions. A 2026 ICML-track study ("Evaluating AGENTS.md", ETH Zurich) found LLM-generated context files reduced success by about 3% on average and raised cost by over 20%, and recommends keeping them minimal. You already do.
- **Don't compact aggressively** (finding 6).

## Where to make changes

Edit repo sources after comparing them with live settings. Follow the explicitly invoked
[`update-dotfiles`](../../home/shared-skills/update-dotfiles/SKILL.md) save/apply procedure; see the root
[README](../../README.md) for current script side effects. `sync-agent-content.sh` owns managed
skills and generated instructions, not package JSON files. Use `apply.sh` with explicit
files/groups, inspect its preview, then add `--yes` for only that scope. Settings preserve
machine fields and package declarations by default. Commit, push, and VPS deployment
remain explicit requests. Legacy provisioning/background automation has been retired;
the two Mac jobs were persistently disabled and their installed plists removed.

## Measurement plan

The current repo already enables Open-TUI telemetry. No current-vs-historical latency
comparison has been run; first establish a new baseline after applying the approved cleanup.

1. **Check measurement visibility.** Confirm live telemetry matches `home/open-tui.json`.
   Cache-miss notices and footer token display remain optional instrumentation changes,
   requiring approval; they are not part of the cleanup.
2. **Measure the lean setup:** one delegation system, removed Ponytail/router, compact Agent
   descriptions, and `/btw` high. Test per-model effort separately if desired.
3. **Run three tasks:** a read-only investigation, a small edit, a multi-file change. Same model, current versus lean, at least three runs each, since single runs are noisy.
4. **Record:** ttft, total tokens, cache-read %, wall-clock time, and pass/fail on the result.
5. **Test effort separately** from tool and skill trimming, so each change is attributable.

## Validation and limitations

- The original investigation made no configuration changes. The later approved cleanup
  edits repo sources and, with separate approval, removes the inactive observational-memory
  key from live settings. Local configuration apply, package management, VPS deployment,
  and performance measurement remain separate steps.
- Measurements marked **[audit]** were not re-measured. The model-mix table is from a bounded scan of the 20 newest session files, not the full history.
- End-to-end latency under an A/B test has not been measured.
- Some summarization and memory usage was not accounted for in the logs; recorded dollar estimates are not subscription bills.
- No coding-specific effort-versus-quality benchmark was found; effort recommendations rest on provider documentation and need local confirmation.

## Sources

- Pi docs: [settings](https://pi.dev/docs/latest/settings), [packages](https://pi.dev/docs/latest/packages), [skills](https://pi.dev/docs/latest/skills), [compaction](https://pi.dev/docs/latest/compaction), [extensions](https://pi.dev/docs/latest/extensions)
- DeepSeek: [thinking mode](https://api-docs.deepseek.com/guides/thinking_mode), [pricing](https://api-docs.deepseek.com/quick_start/pricing/), [context caching](https://api-docs.deepseek.com/guides/kv_cache)
- OpenAI: [prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching), [reasoning models](https://developers.openai.com/api/docs/guides/reasoning)
- Anthropic: [multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system), [advanced tool use](https://www.anthropic.com/engineering/advanced-tool-use)
- Research: [Evaluating AGENTS.md (arXiv 2602.11988)](https://arxiv.org/html/2602.11988v1)
