/**
 * Routes fresh ordinary Agent launches using one bounded TypeSafe judgment.
 * The global mode defaults to off; project config can only disable or narrow it.
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { existsSync, readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

export type Tier = "quick" | "standard" | "high";
export type Mode = "off" | "shadow" | "active";
type Thinking = "off" | "minimal" | "low" | "medium" | "high";

const TIERS: Tier[] = ["quick", "standard", "high"];
const THINKING_LEVELS: Thinking[] = ["off", "minimal", "low", "medium", "high"];
const REQUEST_TIMEOUT_MS = 1_500;
const MAX_REQUEST_BYTES = 16_384;
const TYPESAFE_ENDPOINT = "https://api.typesafe.ai/v1/systemone";
const CONFIDENCE_THRESHOLD = 0.75;
const HIGH_STAKES_THRESHOLD = 0.6;

interface RouteTarget {
  provider: string;
  model: string;
}

interface RouterConfig {
  mode: Mode;
  endpoint: string;
  jevModel: string;
  maxRequestBytes: number;
  capabilityConfidenceThreshold: number;
  reasoningConfidenceThreshold: number;
  highStakesThreshold: number;
  agentFloors: Record<string, Tier>;
  defaultFloor: Tier;
  tiers: Record<Tier, RouteTarget[]>;
}

interface ConfigOverride {
  mode?: Mode;
  jevModel?: string;
  capabilityConfidenceThreshold?: number;
  reasoningConfidenceThreshold?: number;
  highStakesThreshold?: number;
  agentFloors?: Record<string, Tier>;
  defaultFloor?: Tier;
  tiers?: Partial<Record<Tier, RouteTarget[]>>;
}

export const DEFAULTS: RouterConfig = {
  mode: "off",
  endpoint: TYPESAFE_ENDPOINT,
  jevModel: "jev-latest",
  maxRequestBytes: MAX_REQUEST_BYTES,
  capabilityConfidenceThreshold: CONFIDENCE_THRESHOLD,
  reasoningConfidenceThreshold: CONFIDENCE_THRESHOLD,
  highStakesThreshold: HIGH_STAKES_THRESHOLD,
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
  defaultFloor: "standard",
  tiers: {
    quick: [
      { provider: "opencode-go", model: "glm-5.3-flash" },
      { provider: "deepseek", model: "deepseek-flash" },
    ],
    standard: [
      { provider: "openai-codex", model: "gpt-6-luna" },
      { provider: "opencode-go", model: "glm-5.3" },
      { provider: "deepseek", model: "deepseek-v4-pro" },
      { provider: "opencode-go", model: "kimi-k2.7-code" },
    ],
    high: [
      { provider: "openai-codex", model: "gpt-6-astra" },
      { provider: "opencode-go", model: "kimi-k3" },
    ],
  },
};

class RouterFailure extends Error {
  readonly reason: string;

  constructor(reason: string) {
    super(reason);
    this.reason = reason;
  }
}

function isRecord(value: unknown): value is Record<string, any> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function invalidConfig(): never {
  throw new RouterFailure("invalid_config");
}

function assertKeys(value: Record<string, unknown>, allowed: readonly string[]): void {
  if (Object.keys(value).some((key) => !allowed.includes(key))) invalidConfig();
}

function isTier(value: unknown): value is Tier {
  return typeof value === "string" && TIERS.includes(value as Tier);
}

function isMode(value: unknown): value is Mode {
  return value === "off" || value === "shadow" || value === "active";
}

function parseTargets(value: unknown): RouteTarget[] {
  if (!Array.isArray(value)) return invalidConfig();
  const targets = value.map((target): RouteTarget => {
    if (!isRecord(target)) return invalidConfig();
    assertKeys(target, ["provider", "model"]);
    if (
      typeof target.provider !== "string" ||
      !/^[a-z0-9][a-z0-9-]*$/i.test(target.provider) ||
      typeof target.model !== "string" ||
      !/^[a-z0-9][a-z0-9._-]*$/i.test(target.model)
    ) return invalidConfig();
    return { provider: target.provider, model: target.model };
  });
  if (new Set(targets.map((target) => `${target.provider}/${target.model}`)).size !== targets.length) {
    return invalidConfig();
  }
  return targets;
}

function parseTierOverrides(value: unknown): Partial<Record<Tier, RouteTarget[]>> {
  if (!isRecord(value)) return invalidConfig();
  assertKeys(value, TIERS);
  return Object.fromEntries(
    Object.entries(value).map(([tier, targets]) => [tier, parseTargets(targets)]),
  ) as Partial<Record<Tier, RouteTarget[]>>;
}

function parseOverride(value: unknown, project: boolean): ConfigOverride {
  if (!isRecord(value)) return invalidConfig();
  const allowed = project
    ? ["mode", "tiers"]
    : [
        "mode",
        "jevModel",
        "capabilityConfidenceThreshold",
        "reasoningConfidenceThreshold",
        "highStakesThreshold",
        "agentFloors",
        "defaultFloor",
        "tiers",
      ];
  assertKeys(value, allowed);
  const result: ConfigOverride = {};

  if (value.mode !== undefined) {
    if (!isMode(value.mode)) return invalidConfig();
    result.mode = value.mode;
  }
  if (!project && value.jevModel !== undefined) {
    if (typeof value.jevModel !== "string" || !/^[a-z0-9][a-z0-9.-]{0,99}$/i.test(value.jevModel)) {
      return invalidConfig();
    }
    result.jevModel = value.jevModel;
  }
  for (const key of [
    "capabilityConfidenceThreshold",
    "reasoningConfidenceThreshold",
    "highStakesThreshold",
  ] as const) {
    const threshold = value[key];
    if (threshold !== undefined) {
      if (project || typeof threshold !== "number" || !Number.isFinite(threshold) || threshold < 0 || threshold > 1) {
        return invalidConfig();
      }
      result[key] = threshold;
    }
  }
  if (!project && value.defaultFloor !== undefined) {
    if (!isTier(value.defaultFloor)) return invalidConfig();
    result.defaultFloor = value.defaultFloor;
  }
  if (!project && value.agentFloors !== undefined) {
    if (!isRecord(value.agentFloors)) return invalidConfig();
    result.agentFloors = {};
    for (const [name, tier] of Object.entries(value.agentFloors)) {
      if (!/^[a-z0-9-]+$/i.test(name) || !isTier(tier)) return invalidConfig();
      result.agentFloors[name] = tier;
    }
  }
  if (value.tiers !== undefined) result.tiers = parseTierOverrides(value.tiers);
  return result;
}

function readConfigFile(path: string): unknown | undefined {
  if (!existsSync(path)) return undefined;
  try {
    return JSON.parse(readFileSync(path, "utf8")) as unknown;
  } catch {
    return invalidConfig();
  }
}

function modeRank(mode: Mode): number {
  return mode === "off" ? 0 : mode === "shadow" ? 1 : 2;
}

/** Resolve per-call policy from Pi's configured agent directory and ctx.cwd. */
export function loadConfig(agentDir: string, cwd: string): RouterConfig {
  const globalOverride = parseOverride(readConfigFile(join(agentDir, "pi-subagent-router.json")) ?? {}, false);
  const config: RouterConfig = {
    ...DEFAULTS,
    ...globalOverride,
    agentFloors: { ...DEFAULTS.agentFloors, ...globalOverride.agentFloors },
    tiers: { ...DEFAULTS.tiers, ...globalOverride.tiers },
  };

  // Off is a user-level kill switch; project config is never consulted then.
  if (config.mode === "off") return config;

  const projectOverride = parseOverride(
    readConfigFile(join(cwd, ".pi", "pi-subagent-router.json")) ?? {},
    true,
  );
  if (projectOverride.mode && modeRank(projectOverride.mode) < modeRank(config.mode)) {
    config.mode = projectOverride.mode;
  }
  for (const tier of TIERS) {
    const allow = projectOverride.tiers?.[tier];
    if (!allow) continue;
    const allowed = new Set(allow.map((target) => `${target.provider}/${target.model}`));
    if (allow.some((target) => !config.tiers[tier].some((candidate) => candidate.provider === target.provider && candidate.model === target.model))) {
      return invalidConfig();
    }
    // Project files are allowlists only; global candidate preference order wins.
    config.tiers[tier] = config.tiers[tier].filter((target) => allowed.has(`${target.provider}/${target.model}`));
  }
  return config;
}

export function getAgentConfigDir(env: NodeJS.ProcessEnv = process.env): string {
  const configured = env.PI_CODING_AGENT_DIR;
  if (!configured) return join(homedir(), ".pi", "agent");
  if (configured === "~") return homedir();
  if (configured.startsWith("~/")) return join(homedir(), configured.slice(2));
  return configured;
}

// ---------------------------------------------------------------------------
// Jev request and answer validation
// ---------------------------------------------------------------------------

export function buildQuestions(): Record<string, unknown> {
  return {
    capability: {
      type: "choice",
      instructions: "How much model capability does this delegated request deserve to do well? Judge the task itself, not cost.",
      criteria: {
        quick: "Bounded mechanical work: a straightforward lookup, extraction, formatting, or tiny specified edit.",
        standard: "Ordinary multi-step work: familiar implementation or analysis with a few dependent steps.",
        high: "Ambiguous, cross-cutting, difficult-to-verify work where stronger reasoning materially improves correctness.",
      },
    },
    reasoning_effort: {
      type: "choice",
      instructions: "What reasoning effort should the child use, independently of model capability?",
      criteria: {
        off: "Straight lookup, extraction, or formatting.",
        low: "A small, clearly specified change.",
        medium: "Normal implementation with several dependent steps.",
        high: "Difficult debugging, architecture, or subtle correctness/security review.",
      },
    },
    high_stakes: {
      type: "noul",
      instructions: "Could a mistake in this delegated request materially affect security, data, deployment, or a consequential review?",
      criteria: {
        yes: "A mistake could have material consequences in one of those areas.",
        no: "A mistake would be readily reversible and have no material consequence in those areas.",
      },
    },
  };
}

const CAPABILITY_OPTIONS = ["quick", "standard", "high"] as const;
const EFFORT_OPTIONS = ["off", "low", "medium", "high"] as const;

interface ChoiceAnswer<T extends string> {
  choice: T;
  confidence: number;
}

export interface Classification {
  capability: ChoiceAnswer<(typeof CAPABILITY_OPTIONS)[number]>;
  reasoningEffort: ChoiceAnswer<(typeof EFFORT_OPTIONS)[number]>;
  highStakes: number;
  jevVersion: string;
  tokenUsage: { input_tokens: number; output_tokens: number };
}

function validProbability(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 1;
}

function parseChoice<T extends string>(answer: unknown, options: readonly T[]): ChoiceAnswer<T> {
  if (!isRecord(answer) || answer.type !== "choice" || !options.includes(answer.choice)) {
    throw new RouterFailure("invalid_response");
  }
  if (!validProbability(answer.confidence) || !isRecord(answer.probabilities)) {
    throw new RouterFailure("invalid_response");
  }
  const keys = Object.keys(answer.probabilities);
  if (keys.length !== options.length || options.some((option) => !keys.includes(option))) {
    throw new RouterFailure("invalid_response");
  }
  const probabilities = Object.values(answer.probabilities);
  if (!probabilities.every(validProbability) || Math.abs(probabilities.reduce((sum, p) => sum + p, 0) - 1) > 0.01) {
    throw new RouterFailure("invalid_response");
  }
  const selected = answer.probabilities[answer.choice] as number;
  if (selected !== Math.max(...(probabilities as number[]))) throw new RouterFailure("invalid_response");
  return { choice: answer.choice as T, confidence: answer.confidence };
}

export function parseClassification(payload: unknown): Classification {
  if (!isRecord(payload) || typeof payload.model !== "string" || payload.model.length === 0 || payload.model.length > 128) {
    throw new RouterFailure("invalid_response");
  }
  if (!isRecord(payload.answers)) throw new RouterFailure("invalid_response");
  const answers = payload.answers;
  if (Object.keys(answers).length !== 3 || !["capability", "reasoning_effort", "high_stakes"].every((key) => key in answers)) {
    throw new RouterFailure("invalid_response");
  }
  const highStakes = answers.high_stakes;
  if (!isRecord(highStakes) || highStakes.type !== "noul" || !validProbability(highStakes.noul)) {
    throw new RouterFailure("invalid_response");
  }
  const usage = payload.usage;
  if (
    !isRecord(usage) ||
    !Number.isSafeInteger(usage.input_tokens) || usage.input_tokens < 0 ||
    !Number.isSafeInteger(usage.output_tokens) || usage.output_tokens < 0
  ) throw new RouterFailure("invalid_response");
  return {
    capability: parseChoice(answers.capability, CAPABILITY_OPTIONS),
    reasoningEffort: parseChoice(answers.reasoning_effort, EFFORT_OPTIONS),
    highStakes: highStakes.noul,
    jevVersion: payload.model,
    tokenUsage: { input_tokens: usage.input_tokens, output_tokens: usage.output_tokens },
  };
}

interface ClassifyOptions {
  prompt: string;
  agentType: string;
  config: RouterConfig;
  apiKey: string;
  signal?: AbortSignal;
  fetchImpl?: typeof fetch;
  /** Test seam; production always uses the 1,500 ms deadline. */
  timeoutMs?: number;
}

export async function classifyTask(options: ClassifyOptions): Promise<Classification> {
  const body = JSON.stringify({
    model: options.config.jevModel,
    state: { request: options.prompt, agent_type: options.agentType },
    questions: buildQuestions(),
  });
  if (Buffer.byteLength(body, "utf8") > options.config.maxRequestBytes) {
    throw new RouterFailure("request_too_large");
  }
  if (options.signal?.aborted) throw new RouterFailure("aborted");

  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, options.timeoutMs ?? REQUEST_TIMEOUT_MS);
  const signal = options.signal ? AbortSignal.any([controller.signal, options.signal]) : controller.signal;
  let rejectAbort!: (error: Error) => void;
  const abortPromise = new Promise<never>((_, reject) => { rejectAbort = reject; });
  const onAbort = () => rejectAbort(new RouterFailure(options.signal?.aborted && !timedOut ? "aborted" : "timeout"));
  signal.addEventListener("abort", onAbort, { once: true });
  const fetchImpl = options.fetchImpl ?? globalThis.fetch;

  try {
    const pending = (async () => {
      const response = await fetchImpl(options.config.endpoint, {
        method: "POST",
        headers: { Authorization: `Bearer ${options.apiKey}`, "Content-Type": "application/json" },
        body,
        signal,
      });
      if (!response.ok) throw new RouterFailure(`http_${response.status}`);
      let payload: unknown;
      try {
        payload = await response.json();
      } catch {
        throw new RouterFailure("invalid_response");
      }
      return parseClassification(payload);
    })();
    return await Promise.race([pending, abortPromise]);
  } catch (error) {
    if (error instanceof RouterFailure) throw error;
    throw new RouterFailure(signal.aborted ? (options.signal?.aborted && !timedOut ? "aborted" : "timeout") : "network_error");
  } finally {
    clearTimeout(timer);
    signal.removeEventListener("abort", onAbort);
  }
}

// ---------------------------------------------------------------------------
// Deterministic tier policy
// ---------------------------------------------------------------------------

interface ModelCandidate {
  provider: string;
  id: string;
  reasoning?: boolean;
  thinkingLevelMap?: Record<string, string | null>;
  input?: string[];
  contextWindow?: number;
  maxTokens?: number;
  inputLimits?: { maxRequestBytes?: number };
}

export interface Decision {
  model: string;
  tier: Tier;
  thinking?: Thinking;
  capabilityConfidence: number;
  reasoningConfidence: number;
  highStakes: number;
  reasonCodes: string[];
}

function tierIndex(tier: Tier): number {
  return TIERS.indexOf(tier);
}

function compatibleModel(model: ModelCandidate, promptBytes: number): boolean {
  if (
    typeof model.provider !== "string" || typeof model.id !== "string" ||
    typeof model.reasoning !== "boolean" ||
    !Array.isArray(model.input) || !model.input.includes("text") ||
    !Number.isFinite(model.contextWindow) || !Number.isFinite(model.maxTokens) ||
    (model.contextWindow as number) <= (model.maxTokens as number) ||
    promptBytes + (model.maxTokens as number) > (model.contextWindow as number)
  ) return false;
  if (model.inputLimits?.maxRequestBytes !== undefined && promptBytes > model.inputLimits.maxRequestBytes) return false;
  if (model.thinkingLevelMap !== undefined && !isRecord(model.thinkingLevelMap)) return false;
  return true;
}

function normalizeThinking(model: ModelCandidate, requested: Thinking): Thinking | undefined {
  if (!model.reasoning) return "off";
  const supported = THINKING_LEVELS.filter((level) => model.thinkingLevelMap?.[level] !== null);
  const start = THINKING_LEVELS.indexOf(requested);
  for (let i = start; i < THINKING_LEVELS.length; i += 1) {
    if (supported.includes(THINKING_LEVELS[i])) return THINKING_LEVELS[i];
  }
  for (let i = start - 1; i >= 0; i -= 1) {
    if (supported.includes(THINKING_LEVELS[i])) return THINKING_LEVELS[i];
  }
  return undefined;
}

export function decide(
  classification: Classification,
  agentType: string,
  config: RouterConfig,
  available: ModelCandidate[],
  promptBytes: number,
): Decision | undefined {
  const reasonCodes: string[] = [];
  const uncertainCapability = classification.capability.confidence < config.capabilityConfidenceThreshold;
  const highStakes = classification.highStakes >= config.highStakesThreshold;
  let minimum = uncertainCapability || highStakes ? "high" : classification.capability.choice;
  if (uncertainCapability) reasonCodes.push("capability_uncertain");
  if (highStakes) reasonCodes.push("high_stakes");

  const floor = config.agentFloors[agentType] ?? config.defaultFloor;
  if (tierIndex(floor) > tierIndex(minimum)) {
    minimum = floor;
    reasonCodes.push("role_floor");
  }

  const requestedThinking: Thinking = classification.reasoningEffort.confidence < config.reasoningConfidenceThreshold
    ? "high"
    : classification.reasoningEffort.choice;
  if (classification.reasoningEffort.confidence < config.reasoningConfidenceThreshold) {
    reasonCodes.push("reasoning_uncertain");
  }

  const minimumIndex = tierIndex(minimum as Tier);
  for (let i = minimumIndex; i < TIERS.length; i += 1) {
    const tier = TIERS[i];
    for (const target of config.tiers[tier]) {
      const model = available.find((candidate) =>
        candidate.provider === target.provider && candidate.id === target.model && compatibleModel(candidate, promptBytes),
      );
      if (!model) continue;
      if (tier !== minimum) reasonCodes.push("stronger_tier_fallback");
      return {
        model: `${target.provider}/${target.model}`,
        tier,
        thinking: normalizeThinking(model, requestedThinking),
        capabilityConfidence: classification.capability.confidence,
        reasoningConfidence: classification.reasoningEffort.confidence,
        highStakes: classification.highStakes,
        reasonCodes,
      };
    }
  }
  return undefined;
}

// ---------------------------------------------------------------------------
// Pi tool-call integration
// ---------------------------------------------------------------------------

function scopedAvailable(ctx: any): ModelCandidate[] {
  const registry = ctx.modelRegistry as { getAvailable?: () => ModelCandidate[] } | undefined;
  if (!registry || typeof registry.getAvailable !== "function") throw new RouterFailure("no_model_registry");
  let available = registry.getAvailable();
  if (!Array.isArray(available)) throw new RouterFailure("no_model_registry");
  if (Array.isArray(ctx.scopedModels) && ctx.scopedModels.length > 0) {
    const allowed = new Set(ctx.scopedModels.flatMap((item: any) =>
      item?.model && typeof item.model.provider === "string" && typeof item.model.id === "string"
        ? [`${item.model.provider}/${item.model.id}`]
        : [],
    ));
    available = available.filter((model) => allowed.has(`${model.provider}/${model.id}`));
  }
  return available;
}

function hasCompatibleCandidate(config: RouterConfig, available: ModelCandidate[], promptBytes: number): boolean {
  return TIERS.some((tier) => config.tiers[tier].some((target) =>
    available.some((model) =>
      model.provider === target.provider && model.id === target.model && compatibleModel(model, promptBytes),
    ),
  ));
}

function recordNote(pi: ExtensionAPI, toolCallId: string, data: Record<string, unknown>): void {
  try {
    pi.appendEntry("subagent-router", { toolCallId, ...data });
  } catch {
    // Transcript persistence must never block a tool launch.
  }
}

export default function (pi: ExtensionAPI): void {
  void import("@earendil-works/pi-tui").then(({ Text }) => {
    pi.registerEntryRenderer("subagent-router", (entry, { expanded }, theme) => {
      const data = (entry.data ?? {}) as Record<string, unknown>;
      const status = data.status === "recommended" ? "recommended" : data.status === "requested" ? "requested" : "bypassed";
      const candidate = typeof data.candidate === "string" ? ` ${data.candidate}` : "";
      const reasons = Array.isArray(data.reasonCodes) ? data.reasonCodes.join(", ") : "";
      const summary = `${theme.fg("dim", `subagent-router · ${status}`)}${candidate}`;
      return new Text(summary + (expanded && reasons ? `\n${reasons}` : ""), 0, 0);
    });
  }).catch(() => {});

  pi.on("tool_call", async (event, ctx) => {
    if (event.toolName !== "Agent" || !isRecord(event.input)) return;
    const toolCallId = typeof event.toolCallId === "string" ? event.toolCallId : "unknown";
    const input = event.input as {
      prompt?: unknown;
      subagent_type?: unknown;
      model?: unknown;
      thinking?: unknown;
      resume?: unknown;
      schedule?: unknown;
      inherit_context?: unknown;
    };

    try {
      const config = loadConfig(getAgentConfigDir(), ctx.cwd);
      if (config.mode === "off") return;
      if (typeof input.model === "string" && input.model.length > 0) {
        recordNote(pi, toolCallId, { status: "bypassed", reasonCodes: ["explicit_model"] });
        return;
      }
      if (input.resume) {
        recordNote(pi, toolCallId, { status: "bypassed", reasonCodes: ["resume"] });
        return;
      }
      if (input.schedule) {
        recordNote(pi, toolCallId, { status: "bypassed", reasonCodes: ["scheduled"] });
        return;
      }
      if (input.inherit_context) {
        recordNote(pi, toolCallId, { status: "bypassed", reasonCodes: ["inherited_context_unknown"] });
        return;
      }
      if (typeof input.prompt !== "string" || input.prompt.trim().length === 0) {
        recordNote(pi, toolCallId, { status: "bypassed", reasonCodes: ["empty_prompt"] });
        return;
      }
      const apiKey = process.env.TYPESAFE_API_KEY;
      if (!apiKey) {
        recordNote(pi, toolCallId, { status: "bypassed", reasonCodes: ["missing_api_key"] });
        return;
      }
      const available = scopedAvailable(ctx);
      const promptBytes = Buffer.byteLength(input.prompt, "utf8");
      if (!hasCompatibleCandidate(config, available, promptBytes)) {
        recordNote(pi, toolCallId, { status: "bypassed", reasonCodes: ["no_eligible_candidate"] });
        return;
      }

      const started = performance.now();
      const classification = await classifyTask({
        prompt: input.prompt,
        agentType: typeof input.subagent_type === "string" ? input.subagent_type : "",
        config,
        apiKey,
        signal: ctx.signal,
      });
      const pick = decide(
        classification,
        typeof input.subagent_type === "string" ? input.subagent_type : "",
        config,
        available,
        promptBytes,
      );
      const latencyMs = Math.round(performance.now() - started);
      if (!pick) {
        recordNote(pi, toolCallId, {
          status: "bypassed",
          jevVersion: classification.jevVersion,
          tokenUsage: classification.tokenUsage,
          latencyMs,
          reasonCodes: ["no_eligible_candidate"],
        });
        return;
      }

      const originalThinking = input.thinking;
      const common = {
        tier: pick.tier,
        candidate: pick.model,
        proposedThinking: pick.thinking,
        thinkingRequested: config.mode === "active" ? (originalThinking ?? pick.thinking) : originalThinking,
        confidence: {
          capability: pick.capabilityConfidence,
          reasoningEffort: pick.reasoningConfidence,
        },
        highStakes: pick.highStakes,
        jevVersion: classification.jevVersion,
        tokenUsage: classification.tokenUsage,
        latencyMs,
        reasonCodes: pick.reasonCodes,
      };
      if (config.mode === "shadow") {
        recordNote(pi, toolCallId, { status: "recommended", ...common });
        return;
      }

      // pi-subagents' agent-file model/thinking pins still take precedence.
      input.model = pick.model;
      if (originalThinking === undefined && pick.thinking !== undefined) input.thinking = pick.thinking;
      recordNote(pi, toolCallId, { status: "requested", ...common });
    } catch (error) {
      const reason = error instanceof RouterFailure ? error.reason : "internal_error";
      recordNote(pi, toolCallId, { status: "bypassed", reasonCodes: [reason] });
    }
  });
}
