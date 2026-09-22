/**
 * pi-subagent-router — routes subagent spawns to the right model tier.
 *
 * On every "Agent" tool call, one cheap Jev (TypeSafe System One) judgment
 * scores the subtask (task kind, complexity 0-3, capability deserved,
 * deep-reasoning probability). Code composes a demand score, applies the
 * agent-type floor, and picks the first authenticated model from that tier's
 * candidate chain. The chosen model + thinking level are written into the
 * tool call before it executes; the chat doesn't have to do anything.
 *
 * Routing never blocks a launch: missing key, timeout, or unknown model means
 * the spawn runs on the agent type's default with a transcript note.
 *
 * Config: ~/.pi/agent/pi-subagent-router.json (or <cwd>/.pi/), merged over defaults.
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { existsSync, readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

type Tier = "quick" | "standard" | "high";
const TIERS: Tier[] = ["quick", "standard", "high"];

interface RouteTarget {
  provider: string;
  model: string;
}

interface Config {
  enabled: boolean;
  apiKeyEnv: string;
  apiKey?: string;
  endpoint: string;
  jevModel: string;
  timeoutMs: number;
  minPromptChars: number;
  /** Per-agent-type minimum tier. Unknown types fall back to `defaultFloor`. */
  agentFloors: Record<string, Tier>;
  defaultFloor: Tier;
  tiers: Record<Tier, RouteTarget[]>;
}

export const DEFAULTS: Config = {
  enabled: true,
  apiKeyEnv: "TYPESAFE_API_KEY",
  endpoint: "https://api.typesafe.ai/v1/systemone",
  jevModel: "jev-latest",
  timeoutMs: 3500,
  minPromptChars: 12,
  agentFloors: {
    explorer: "quick",
    "codebase-locator": "quick",
    "artifacts-locator": "quick",
    "precedent-locator": "quick",
    worker: "standard",
    "codebase-analyzer": "standard",
    "codebase-pattern-finder": "standard",
    "integration-scanner": "standard",
    "scope-tracer": "standard",
    researcher: "standard",
    "web-search-researcher": "standard",
    "general-purpose": "standard",
    reviewer: "high",
    "claim-verifier": "high",
    "diff-auditor": "high",
    "slice-verifier": "high",
    "artifact-code-reviewer": "high",
    "artifact-coverage-reviewer": "high",
    "artifacts-analyzer": "high",
  },
  defaultFloor: "quick",
  tiers: {
    quick: [
      { provider: "deepseek", model: "deepseek-flash" },
      { provider: "opencode-go", model: "glm-5.3-flash" },
      { provider: "opencode-go", model: "deepseek-v4-flash" },
    ],
    standard: [
      { provider: "opencode-go", model: "kimi-k2.7-code" },
      { provider: "opencode-go", model: "glm-5.2" },
      { provider: "deepseek", model: "deepseek-v4-pro" },
    ],
    high: [
      { provider: "openai-codex", model: "gpt-5.6-terra" },
      { provider: "opencode-go", model: "kimi-k3" },
      { provider: "commandcode", model: "claude-sonnet-5" },
    ],
  },
};

function readConfigFile(path: string): Partial<Config> | undefined {
  if (!existsSync(path)) return undefined;
  try {
    return JSON.parse(readFileSync(path, "utf-8"));
  } catch (error) {
    console.warn(
      `pi-subagent-router: ignoring unreadable config ${path}:`,
      error instanceof Error ? error.message : error,
    );
    return undefined;
  }
}

function loadConfig(cwd: string): Config {
  const global = readConfigFile(join(homedir(), ".pi", "agent", "pi-subagent-router.json")) ?? {};
  const project = readConfigFile(join(cwd, ".pi", "pi-subagent-router.json")) ?? {};
  // Project config may steer routing only — it never sets the endpoint, key, or
  // key env name. An untrusted repo otherwise could point the authenticated
  // fetch (key + prompt in the body) at its own server.
  const {
    endpoint: _e,
    apiKey: _k,
    apiKeyEnv: _v,
    jevModel: _m,
    ...projectSafe
  } = project as Partial<Config>;
  const merged = {
    ...DEFAULTS,
    ...global,
    ...projectSafe,
    agentFloors: { ...DEFAULTS.agentFloors, ...global.agentFloors, ...projectSafe.agentFloors },
    tiers: { ...DEFAULTS.tiers, ...global.tiers, ...projectSafe.tiers },
  } as Config;
  return merged;
}

// ---------------------------------------------------------------------------
// Jev client (typed judgments; fails open)
// ---------------------------------------------------------------------------

const TASK_KINDS: Record<string, string> = {
  plan: "Deciding what to build, sequencing work, or designing an approach before editing",
  implement: "Writing or changing code, scripts, or configuration to produce a concrete result",
  write: "Producing prose, documentation, comments, or other non-code content from scratch",
  debug: "Diagnosing a failure, error, or unexpected behavior and finding its root cause",
  refactor: "Restructuring existing code without changing intended behavior",
  review: "Auditing code, a diff, a document, or a plan for problems and risks",
  research: "Searching, reading, and synthesizing external information or unfamiliar APIs",
  explain: "Answering a question or explaining how something works",
  operate: "Running commands, tooling, git, deploys, or environment setup",
  chat: "Small talk, acknowledgements, or a request with no real work attached",
};

interface Analysis {
  kind: string;
  complexity: number; // 0..3
  capability: number; // 0..3
  deepReasoning: number; // 0..1
}

function num(v: unknown): number | undefined {
  return typeof v === "number" && Number.isFinite(v) ? v : undefined;
}

function buildQuestions(): Record<string, unknown> {
  return {
    task_kind: {
      type: "choice",
      instructions:
        "Which single kind of work does `request` (a subtask delegated to a subagent) ask for? Pick the closest kind even when ambiguous.",
      criteria: TASK_KINDS,
    },
    complexity: {
      type: "score",
      instructions: "How hard is `request` to do well, judged only on the work itself? Ignore cost.",
      criteria: [
        "Trivial: one obvious step, no design decisions, answer is known or mechanical",
        "Moderate: a few dependent steps using familiar patterns, little ambiguity",
        "Complex: multiple files or interacting constraints, real tradeoffs to weigh",
        "Architectural: cross-cutting design, high stakes, long horizon, easy to get subtly wrong",
      ],
    },
    capability_deserved: {
      type: "score",
      instructions:
        "Setting price aside, how much model capability does this subtask deserve to get a good outcome? Judge by stakes, difficulty, and how much a stronger model would improve the result.",
      criteria: [
        "Minimal: any fast small model answers this just as well",
        "Standard: a competent mid-tier model is enough",
        "High: a strong frontier model materially improves the outcome",
        "Maximum: correctness matters more than cost; use the best available",
      ],
    },
    needs_deep_reasoning: {
      type: "noul",
      instructions:
        "Does doing `request` well require extended multi-step reasoning rather than recall, lookup, or a short direct edit?",
      criteria: {
        true: "The work hinges on reasoning through non-obvious steps or edge cases",
        false: "The work is recall, lookup, formatting, or a short direct change",
      },
    },
  };
}

export async function jevClassify(
  prompt: string,
  config: Config,
  apiKey: string,
  signal?: AbortSignal,
): Promise<Analysis> {
  const body = {
    model: config.jevModel,
    // 4-question judgment; long prompts only add cost/latency, truncate.
    state: { request: prompt.slice(0, 2000), environment: { context: "subagent_launch" } },
    questions: buildQuestions(),
  };
  let lastError: unknown;
  // Shared deadline: all attempts fit inside timeoutMs total, 250ms backoff.
  const deadline = Date.now() + config.timeoutMs;
  for (let attempt = 0; attempt < 3; attempt += 1) {
    if (attempt > 0) {
      if (Date.now() >= deadline) break;
      await new Promise((r) => setTimeout(r, 250));
    }
    const remaining = Math.max(250, deadline - Date.now());
    const timeout = AbortSignal.timeout(remaining);
    try {
      const res = await fetch(config.endpoint, {
        method: "POST",
        headers: { Authorization: `Bearer ${apiKey}`, "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: signal ? AbortSignal.any([timeout, signal]) : timeout,
      });
      if (res.status === 429 || res.status === 529) throw new Error(`overloaded ${res.status}`);
      if (!res.ok) {
        const detail = await res.text().catch(() => "");
        const fatal = new Error(`TypeSafe ${res.status}: ${detail.slice(0, 200)}`) as Error & {
          fatal?: boolean;
        };
        fatal.fatal = true;
        throw fatal;
      }
      const payload = (await res.json()) as { answers?: Record<string, any> };
      const a = payload.answers ?? {};
      return {
        kind: typeof a.task_kind?.choice === "string" ? a.task_kind.choice : "chat",
        complexity: num(a.complexity?.score) ?? 1,
        capability: num(a.capability_deserved?.score) ?? 1,
        // API may answer boolean or numeric; a boolean true/false must not collapse to 0.
        deepReasoning:
          typeof a.needs_deep_reasoning?.noul === "boolean"
            ? a.needs_deep_reasoning.noul
              ? 1
              : 0
            : (num(a.needs_deep_reasoning?.noul) ?? 0),
      };
    } catch (error) {
      lastError = error;
      if ((error as { fatal?: boolean }).fatal) break;
    }
  }
  throw lastError instanceof Error ? lastError : new Error("Jev request failed");
}

// ---------------------------------------------------------------------------
// Decision
// ---------------------------------------------------------------------------

interface Pick {
  model: string; // "provider/modelId"
  thinking?: string;
  tier: Tier;
  reason: string;
}

function tierIndex(tier: Tier | string, fallback?: number): number {
  const i = TIERS.indexOf(tier as Tier);
  return i >= 0 ? i : (fallback ?? 1);
}

export function decide(
  analysis: Analysis,
  agentType: string,
  config: Config,
  available: Array<{ provider: string; id: string; reasoning?: boolean }>,
): Pick | undefined {
  // demand = 0.55*complexity + 0.45*capability, nudged by deep reasoning
  let demand = 0.55 * analysis.complexity + 0.45 * analysis.capability;
  if (analysis.deepReasoning >= 0.65) demand += 0.75;
  else if (analysis.deepReasoning <= 0.2) demand -= 0.25;
  demand = Math.min(3, Math.max(0, demand));

  // Unknown floor string (typo) falls back to the default floor, not standard.
  const floor = config.agentFloors[agentType] ?? config.defaultFloor;
  const floorIdx = tierIndex(floor, tierIndex(config.defaultFloor));
  const idx = Math.min(TIERS.length - 1, Math.max(Math.round(demand), floorIdx));
  const tier = TIERS[idx];

  // Walk the chosen tier's chain first, then neighbouring tiers (nearest first),
  // so an unavailable chain never blocks routing. Downward fallback stops at the
  // agent-type floor — a floor is a minimum, not a starting point.
  const ordered: Array<{ targets: RouteTarget[]; tierIdx: number }> = [
    { targets: config.tiers[tier] ?? [], tierIdx: idx },
  ];
  for (let off = 1; off < TIERS.length; off += 1) {
    if (idx - off >= floorIdx)
      ordered.push({ targets: config.tiers[TIERS[idx - off]] ?? [], tierIdx: idx - off });
    if (idx + off < TIERS.length) ordered.push({ targets: config.tiers[TIERS[idx + off]] ?? [], tierIdx: idx + off });
  }

  for (const { targets, tierIdx: effectiveIdx } of ordered) {
    for (const target of targets) {
      // Exact provider+id wins; bare-id match only as last resort so a same-id
      // model from another provider can't shadow the configured target.
      const model =
        available.find((m) => m.provider === target.provider && m.id === target.model) ??
        available.find((m) => m.id === target.model);
      if (!model) continue;
      const thinking =
        model.reasoning === false
          ? undefined
          : analysis.deepReasoning >= 0.65
            ? "high"
            : analysis.deepReasoning >= 0.3
              ? "low"
              : "off";
      const usedTier = TIERS[effectiveIdx];
      return {
        model: `${model.provider}/${model.id}`,
        thinking,
        tier: usedTier,
        reason:
          `${analysis.kind} · complexity ${analysis.complexity.toFixed(2)}/3 · ` +
          `capability ${analysis.capability.toFixed(2)}/3 · reasoning ${analysis.deepReasoning.toFixed(2)} → ${usedTier}` +
          (usedTier !== tier ? ` (fell back from ${tier})` : "") +
          (floor !== "quick" ? ` · floor ${floor} (${agentType})` : ""),
      };
    }
  }
  return undefined; // nothing authenticated on any chain
}

// ---------------------------------------------------------------------------
// Wiring
// ---------------------------------------------------------------------------

export default function (pi: ExtensionAPI) {
  const cwd = process.cwd();
  const config = loadConfig(cwd);

  // Transcript card (best effort: hosts without pi-tui still persist entries).
  void import("@earendil-works/pi-tui")
    .then(({ Text }) => {
      pi.registerEntryRenderer("subagent-router", (entry, { expanded }, theme) => {
        const d = (entry.data ?? {}) as { routed?: string; skipped?: string; reason?: string };
        const line = d.routed
          ? `${theme.fg("accent", "subagent-router →")} ${d.routed}`
          : `${theme.fg("dim", "subagent-router · not routed")} — ${d.skipped ?? ""}`;
        const reason = expanded && d.reason ? `\n${d.reason}` : "";
        const text = new Text(line + reason, 0, 0);
        return text;
      });
    })
    .catch(() => {});

  // appendEntry throws on session-write failure, and a thrown tool_call handler
  // blocks the launch — routing must never be the reason a spawn fails.
  const note = (data: Record<string, unknown>) => {
    try {
      pi.appendEntry("subagent-router", data);
    } catch {
      /* transcript note is best effort */
    }
  };

  pi.on("tool_call", async (event, ctx) => {
    if (!config.enabled) return;
    if (event.toolName !== "Agent") return;
    const input = event.input as {
      prompt: string;
      subagent_type?: string;
      model?: string;
      thinking?: string;
    };

    // Explicit caller choices win — never fight the chat.
    if (input.model) {
      note({ skipped: "explicit model on the spawn", model: input.model });
      return;
    }
    if (!input.prompt || input.prompt.length < config.minPromptChars) return;

    const apiKey = config.apiKey ?? process.env[config.apiKeyEnv];
    const registry = (ctx as { modelRegistry?: unknown }).modelRegistry as
      | { getAvailable?(): unknown[]; getAll(): unknown[] }
      | undefined;
    if (!apiKey || !registry) {
      note({ skipped: !apiKey ? "no TYPESAFE_API_KEY" : "no model registry" });
      return;
    }

    try {
      const analysis = await jevClassify(input.prompt, config, apiKey, (ctx as { signal?: AbortSignal }).signal);
      let available = (registry.getAvailable?.() ?? registry.getAll()) as Array<{
        provider: string;
        id: string;
        reasoning?: boolean;
      }>;
      // Scoped session: routing may only pick from the scoped set — empty
      // intersection means skip routing, not fall back to the full catalogue.
      const scoped = (ctx as unknown as { scopedModels?: readonly unknown[] }).scopedModels;
      if (Array.isArray(scoped) && scoped.length > 0) {
        const scopedKeys = new Set(
          scoped.map((s) => {
            const m = s as { model: { provider: string; id: string } };
            return `${m.model.provider}/${m.model.id}`.toLowerCase();
          }),
        );
        available = available.filter((m) => scopedKeys.has(`${m.provider}/${m.id}`.toLowerCase()));
        if (available.length === 0) {
          note({ skipped: "no scoped model on any tier chain — using agent default" });
          return;
        }
      }

      const pick = decide(analysis, input.subagent_type ?? "", config, available);
      if (!pick) {
        note({ skipped: "no available model on tier chain — using agent default" });
        return;
      }

      input.model = pick.model;
      if (input.thinking === undefined && pick.thinking) input.thinking = pick.thinking;
      note({
        routed: `${pick.model}${pick.thinking ? ` · thinking ${pick.thinking}` : ""}`,
        reason: pick.reason,
      });
    } catch (error) {
      // Fail open: launch proceeds on the agent type's default model.
      note({
        skipped: `jev unavailable (${error instanceof Error ? error.message.slice(0, 120) : "error"}) — using agent default`,
      });
    }
  });
}
