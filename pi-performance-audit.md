# Pi performance and token-usage audit

## Verdict: simplify the setup, don’t reinstall

Both investigations are complete. **There’s measurable overhead from your configuration and workflow**, but no evidence so far that the installation itself is broken.

## What the measurements show

The usage sample covered **16 main sessions and 10 linked subagents**, excluding this investigation.

| Finding | Measurement | Meaning |
|---|---:|---|
| Heavy initial context | **23,216 tokens median** on first requests | Substantial overhead before useful work begins |
| Growing conversation history | **124,716 tokens median** per request | Long sessions repeatedly carry considerable context |
| Caching generally works | **94.1%** of main input context was cache reads | Huge token totals aren’t equivalent to fresh processing or spending |
| Extensive reasoning | **69.3% of output tokens** were reasoning | Much of the generated work isn’t the answer you see |
| Very high effort settings | **75% of requests recorded `max` or `xhigh`** | Historical usage strongly favors thoroughness over speed |

The investigation session used **high**, not max. However, `home/settings.json` also sets high as the default and hides thinking blocks—making work potentially feel like unexplained waiting.

## What’s inefficient in the structure

### 1. Too much overlapping orchestration

Pi-subagents, Herdr, and Pi-tasks together account for **76% of registered extension-tool definition bytes**. The measured instructions and extension-tool definitions total roughly **114 KB**, before history. That’s a size measurement—not an exact billed token count.

### 2. Procedures activate too broadly

Ponytail says “use on ANY coding task,” despite your personal policy making it opt-in. Other broad triggers load lengthy workflow instructions. This investigation itself loaded about **30 KB of procedural guidance**.

Pi already supports [explicit-only skills](https://pi.dev/docs/latest/skills); you don’t need to delete useful procedures to stop loading them unnecessarily.

### 3. Automatic routing isn’t necessarily economical

Both helpers here were routed to **Astra/high**, with uncertainty/high-stakes classifications. The routing requests themselves took only **316–547 ms**; the more consequential choice was assigning heavyweight execution.

### 4. Occasional cache misses are expensive

Just **54 requests accounted for 64.5% of non-cache-read input**. The logs don’t establish why most occurred, so I wouldn’t prescribe a cache “fix” yet.

## Recommendations, in order

1. **Try medium reasoning for ordinary work.** Reserve high/max for genuinely difficult tasks. [OpenAI explicitly identifies lower effort as a speed/token trade-off](https://developers.openai.com/api/docs/guides/reasoning).
2. **Make one delegation system the default.** Keep the others available on demand rather than exposing all their instructions constantly.
3. **Make heavyweight procedural skills explicit-only**, starting with Ponytail; narrow the remaining triggers.
4. **Tune routing so uncertainty doesn’t routinely escalate read-only investigations.**
5. **Start a fresh session when changing tasks**, while preserving relevant decisions. Don’t compact constantly: compaction itself costs work and can disrupt [cache reuse](https://developers.openai.com/api/docs/guides/prompt-caching).
6. **Enable cache-miss notices** so fresh-input spikes become visible.

**Next step:** a reversible “lean” configuration, compared against the current setup on the same task and model, then test reasoning effort separately.

## Validation and limitations

No configuration changes were made during the investigation. Configuration evidence was verified and session measurements spot-checked, but **end-to-end latency under an A/B test has not been measured**. Some summarization/memory usage also wasn’t accounted for in the logs; recorded dollar estimates are not subscription bills.
