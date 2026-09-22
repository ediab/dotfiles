// Routing-logic self-check: run with `npm exec --yes --package=esbuild -- esbuild index.ts --bundle --format=esm --platform=node --outfile=/tmp/sar.mjs && node test.mjs`
import { decide, DEFAULTS } from "/tmp/sar.mjs";
const models = [
  { provider: "deepseek", id: "deepseek-flash", reasoning: true },
  { provider: "opencode-go", id: "kimi-k2.7-code", reasoning: true },
  { provider: "openai-codex", id: "gpt-5.6-terra", reasoning: true },
];
const assert = (cond, msg) => { if (!cond) { console.error("FAIL:", msg); process.exit(1); } };

// trivial chat → quick (deepseek-flash), thinking off
let r = decide({ kind: "chat", complexity: 0, capability: 0, deepReasoning: 0.1 }, "some-agent", DEFAULTS, models);
assert(r.model === "deepseek/deepseek-flash" && r.tier === "quick" && r.thinking === "off", `trivial: ${JSON.stringify(r)}`);

// architectural review agent → high floor, deep reasoning → thinking high
r = decide({ kind: "review", complexity: 3, capability: 3, deepReasoning: 0.9 }, "reviewer", DEFAULTS, models);
assert(r.model === "openai-codex/gpt-5.6-terra" && r.tier === "high" && r.thinking === "high", `review: ${JSON.stringify(r)}`);

// moderate task on a quick-floor agent stays quick despite high complexity? floor=quick, demand=1.2 → standard
r = decide({ kind: "explain", complexity: 1, capability: 1, deepReasoning: 0.4 }, "explorer", DEFAULTS, models);
assert(r.model === "opencode-go/kimi-k2.7-code" && r.tier === "standard" && r.thinking === "low", `explorer-mod: ${JSON.stringify(r)}`);

// floor wins over low demand: worker with trivial task still >= standard
r = decide({ kind: "chat", complexity: 0, capability: 0, deepReasoning: 0 }, "worker", DEFAULTS, models);
assert(r.tier === "standard" && r.model === "opencode-go/kimi-k2.7-code", `worker-floor: ${JSON.stringify(r)}`);

// deepReasoning nudge: 1.4 raw demand + 0.75 → rounds to 2
r = decide({ kind: "research", complexity: 2, capability: 0.7, deepReasoning: 0.9 }, "researcher", DEFAULTS, models);
assert(r.tier === "high", `nudge: ${JSON.stringify(r)}`);

// availability fallback: kill standard chain models → floor (standard) blocks the down-walk to quick, but high is available upward
r = decide({ kind: "chat", complexity: 1, capability: 1, deepReasoning: 0.3 }, "general-purpose", DEFAULTS, [models[0], models[2]]);
assert(r.model === "openai-codex/gpt-5.6-terra" && r.tier === "high" && r.reason.includes("fell back from standard"), `fallback-up: ${JSON.stringify(r)}`);

// floor blocks the down-walk entirely: only quick authenticated → no pick, agent default wins
r = decide({ kind: "chat", complexity: 1, capability: 1, deepReasoning: 0.3 }, "general-purpose", DEFAULTS, [models[0]]);
assert(r === undefined, `floor-blocks-downwalk: ${JSON.stringify(r)}`);

// non-reasoning model gets no thinking override (explorer: quick floor allows the down-walk)
r = decide({ kind: "chat", complexity: 1, capability: 1, deepReasoning: 0.9 }, "explorer", DEFAULTS, [{ provider: "deepseek", id: "deepseek-flash", reasoning: false }]);
assert(r.thinking === undefined, `no-reasoning: ${JSON.stringify(r)}`);

// unknown agent type → defaultFloor quick
r = decide({ kind: "chat", complexity: 0, capability: 0, deepReasoning: 0 }, "mystery-agent", DEFAULTS, models);
assert(r.tier === "quick", `default floor: ${JSON.stringify(r)}`);

// floor blocks downward fallback: reviewer (floor high) with only quick models available → no pick (agent default, not a flash model)
r = decide({ kind: "review", complexity: 3, capability: 3, deepReasoning: 0.9 }, "reviewer", DEFAULTS, [models[0]]);
assert(r === undefined, `floor-blocks-fallback: ${JSON.stringify(r)}`);

// upward fallback still works from the floor: reviewer, only standard authenticated → standard (up from floor? no — floor=high, standard idx 1 < floor 2 → undefined)
r = decide({ kind: "chat", complexity: 0, capability: 0, deepReasoning: 0 }, "reviewer", DEFAULTS, [models[1]]);
assert(r === undefined, `floor-blocks-upward-should-not: ${JSON.stringify(r)}`);

// upward fallback above chosen tier works for a quick-floor agent: only high authenticated
r = decide({ kind: "chat", complexity: 0, capability: 0, deepReasoning: 0.1 }, "mystery-agent", DEFAULTS, [models[2]]);
assert(r.tier === "high" && r.reason.includes("fell back"), `upward-fallback: ${JSON.stringify(r)}`);

// boolean noul handled like 1.0 (deep reasoning)
// (boolean conversion happens in jevClassify; covered there)

console.log("all routing checks pass");
