import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, mkdirSync, readFileSync, realpathSync, rmSync, writeFileSync } from "node:fs";
import { homedir, tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import router, { buildQuestions, classifyTask, decide, DEFAULTS, loadConfig, parseClassification } from "./index.ts";

const checks = [];
function test(name, run) {
  checks.push({ name, run });
}

const options = {
  capability: ["quick", "standard", "high"],
  reasoning: ["off", "low", "medium", "high"],
};

function distribution(choice, values) {
  const result = Object.fromEntries(values.map((value) => [value, value === choice ? 0.94 : 0.06 / (values.length - 1)]));
  return result;
}

function payload({ capability = "standard", capabilityConfidence = 0.95, reasoning = "medium", reasoningConfidence = 0.95, highStakes = 0.1 } = {}) {
  return {
    model: "jev-1.13.0",
    answers: {
      capability: {
        type: "choice",
        choice: capability,
        confidence: capabilityConfidence,
        probabilities: distribution(capability, options.capability),
      },
      reasoning_effort: {
        type: "choice",
        choice: reasoning,
        confidence: reasoningConfidence,
        probabilities: distribution(reasoning, options.reasoning),
      },
      high_stakes: { type: "noul", noul: highStakes },
    },
    usage: { input_tokens: 246, output_tokens: 32 },
  };
}

function jsonResponse(value) {
  return { ok: true, status: 200, json: async () => value };
}

function modelList() {
  return Object.values(DEFAULTS.tiers).flat().map((candidate) => ({
    ...candidate,
    id: candidate.model,
    reasoning: true,
    input: ["text"],
    contextWindow: 200_000,
    maxTokens: 8_000,
    thinkingLevelMap: undefined,
  }));
}

function tempConfig(global = { mode: "active" }, project) {
  const root = mkdtempSync(join(tmpdir(), "pi-subagent-router-"));
  const agentDir = join(root, "agent");
  const cwd = join(root, "project");
  mkdirSync(agentDir, { recursive: true });
  mkdirSync(cwd, { recursive: true });
  if (global !== undefined) writeFileSync(join(agentDir, "pi-subagent-router.json"), JSON.stringify(global));
  if (project !== undefined) {
    mkdirSync(join(cwd, ".pi"), { recursive: true });
    writeFileSync(join(cwd, ".pi", "pi-subagent-router.json"), JSON.stringify(project));
  }
  return { root, agentDir, cwd, cleanup: () => rmSync(root, { recursive: true, force: true }) };
}

async function withRouter({ global = { mode: "active" }, project, apiKey = "test-key", appendEntry } = {}, run) {
  const files = tempConfig(global, project);
  const previousDir = process.env.PI_CODING_AGENT_DIR;
  const previousKey = process.env.TYPESAFE_API_KEY;
  process.env.PI_CODING_AGENT_DIR = files.agentDir;
  if (apiKey === null) delete process.env.TYPESAFE_API_KEY;
  else process.env.TYPESAFE_API_KEY = apiKey;
  const handlers = {};
  const entries = [];
  const pi = {
    on: (event, handler) => { handlers[event] = handler; },
    registerEntryRenderer: () => {},
    appendEntry: appendEntry ?? ((type, data) => entries.push({ type, data })),
  };
  try {
    router(pi);
    return await run({ files, cwd: files.cwd, handler: handlers.tool_call, entries });
  } finally {
    if (previousDir === undefined) delete process.env.PI_CODING_AGENT_DIR;
    else process.env.PI_CODING_AGENT_DIR = previousDir;
    if (previousKey === undefined) delete process.env.TYPESAFE_API_KEY;
    else process.env.TYPESAFE_API_KEY = previousKey;
    files.cleanup();
  }
}

function ctx(cwd, { available = modelList(), scopedModels = [], signal } = {}) {
  return {
    cwd,
    signal,
    scopedModels,
    modelRegistry: { getAvailable: () => available },
  };
}

async function withFetch(fetchImpl, run) {
  const previous = globalThis.fetch;
  globalThis.fetch = fetchImpl;
  try {
    return await run();
  } finally {
    globalThis.fetch = previous;
  }
}

function invoke(handler, cwd, input, { toolName = "Agent", toolCallId = "call-1", ...contextOptions } = {}) {
  return handler({ toolName, toolCallId, input }, ctx(cwd, contextOptions));
}

function classification(overrides = {}) {
  return parseClassification(payload(overrides));
}

function policy(overrides = {}) {
  return { ...DEFAULTS, mode: "active", ...overrides };
}

function errIs(reason) {
  return (error) => error?.reason === reason;
}

test("question rubric and response metadata match the typed Jev contract", async () => {
  const questions = buildQuestions();
  assert.deepEqual(Object.keys(questions), ["capability", "reasoning_effort", "high_stakes"]);
  assert.deepEqual(Object.keys(questions.capability.criteria), options.capability);
  assert.deepEqual(Object.keys(questions.reasoning_effort.criteria), options.reasoning);
  assert.equal(questions.high_stakes.type, "noul");

  let request;
  const prompt = "A short but real delegated task.";
  const result = await classifyTask({
    prompt,
    agentType: "explorer",
    config: policy(),
    apiKey: "secret-key",
    fetchImpl: async (url, init) => {
      request = { url, init };
      return jsonResponse(payload());
    },
  });
  const sent = JSON.parse(request.init.body);
  assert.equal(request.url, "https://api.typesafe.ai/v1/systemone");
  assert.equal(request.init.headers.Authorization, "Bearer secret-key");
  assert.deepEqual(sent.state, { request: prompt, agent_type: "explorer" });
  assert.equal(sent.model, "jev-latest");
  assert.equal(result.jevVersion, "jev-1.13.0");
  assert.deepEqual(result.tokenUsage, { input_tokens: 246, output_tokens: 32 });
});

test("quality-first tier, uncertainty, stakes, role-floor, and effort rules are deterministic", () => {
  const all = modelList();
  const easy = decide(classification({ capability: "quick", reasoning: "off" }), "explorer", policy(), all, 100);
  assert.equal(easy.model, "opencode-go/glm-5.3-flash");
  assert.equal(easy.tier, "quick");
  assert.equal(easy.thinking, "off");

  const uncertain = decide(classification({ capability: "quick", capabilityConfidence: 0.74 }), "explorer", policy(), all, 100);
  assert.equal(uncertain.tier, "high");
  assert.ok(uncertain.reasonCodes.includes("capability_uncertain"));

  const stakes = decide(classification({ capability: "quick", highStakes: 0.6 }), "explorer", policy(), all, 100);
  assert.equal(stakes.tier, "high");
  assert.ok(stakes.reasonCodes.includes("high_stakes"));

  const floor = decide(classification({ capability: "quick" }), "worker", policy(), all, 100);
  assert.equal(floor.tier, "standard");
  assert.ok(floor.reasonCodes.includes("role_floor"));

  const unknown = decide(classification({ capability: "quick" }), "mystery-agent", policy(), all, 100);
  assert.equal(unknown.tier, "standard");

  const effortUncertain = decide(classification({ capability: "quick", reasoning: "off", reasoningConfidence: 0.74 }), "explorer", policy(), all, 100);
  assert.equal(effortUncertain.thinking, "high");
  assert.ok(effortUncertain.reasonCodes.includes("reasoning_uncertain"));

  const reviewer = decide(classification({ capability: "high", reasoning: "high", highStakes: 0.9 }), "reviewer", policy(), all, 100);
  assert.equal(reviewer.model, "openai/gpt-6-astra");
  assert.equal(reviewer.tier, "high");
  assert.equal(reviewer.thinking, "high");
});

test("routing requires exact provider, honors availability, and falls upward only", () => {
  const judgment = classification({ capability: "standard" });
  const crossProvider = [{ ...modelList()[2], provider: "openai-codex", id: "gpt-6-luna" }];
  assert.equal(decide(judgment, "general-purpose", policy(), crossProvider, 100), undefined);

  const standard = decide(judgment, "general-purpose", policy(), modelList().filter((model) => model.provider === "openai" && model.id === "gpt-6-astra"), 100);
  assert.equal(standard.model, "openai/gpt-6-astra");
  assert.equal(standard.tier, "high");
  assert.ok(standard.reasonCodes.includes("stronger_tier_fallback"));

  const reviewer = classification({ capability: "high" });
  const onlyLower = modelList().filter((model) => !DEFAULTS.tiers.high.some((target) => target.provider === model.provider && target.model === model.id));
  assert.equal(decide(reviewer, "reviewer", policy(), onlyLower, 100), undefined);

  const noText = [{ ...modelList()[0], input: ["image"] }];
  assert.equal(decide(classification({ capability: "quick" }), "explorer", policy(), noText, 100), undefined);
  const tooSmall = [{ ...modelList()[0], contextWindow: 8_100, maxTokens: 8_000 }];
  assert.equal(decide(classification({ capability: "quick" }), "explorer", policy(), tooSmall, 200), undefined);
});

test("thinking normalization uses model capabilities and never auto-selects xhigh or max", () => {
  const models = modelList();
  models[0].thinkingLevelMap = { high: null, medium: null, low: "low", off: "off" };
  const quick = decide(classification({ capability: "quick", reasoning: "high" }), "explorer", policy(), models, 100);
  assert.equal(quick.thinking, "low");
  models[0].reasoning = false;
  const noReasoning = decide(classification({ capability: "quick", reasoning: "high" }), "explorer", policy(), models, 100);
  assert.equal(noReasoning.thinking, "off");
});

test("global off cannot be re-enabled by project mode, and project mode can disable", () => {
  const disabled = tempConfig({ mode: "off" }, { mode: "active" });
  try {
    assert.equal(loadConfig(disabled.agentDir, disabled.cwd).mode, "off");
  } finally {
    disabled.cleanup();
  }
  const projectOff = tempConfig({ mode: "active" }, { mode: "off" });
  try {
    assert.equal(loadConfig(projectOff.agentDir, projectOff.cwd).mode, "off");
  } finally {
    projectOff.cleanup();
  }
});

test("project policy only narrows approved candidates and rejects unknown config fields", () => {
  const narrowed = tempConfig(
    { mode: "active" },
    { tiers: { quick: [{ provider: "deepseek", model: "deepseek-flash" }] } },
  );
  try {
    const config = loadConfig(narrowed.agentDir, narrowed.cwd);
    assert.deepEqual(config.tiers.quick, [{ provider: "deepseek", model: "deepseek-flash" }]);
  } finally {
    narrowed.cleanup();
  }

  const added = tempConfig({ mode: "active" }, { tiers: { quick: [{ provider: "evil", model: "injected" }] } });
  try {
    assert.throws(() => loadConfig(added.agentDir, added.cwd), errIs("invalid_config"));
  } finally {
    added.cleanup();
  }
  const endpoint = tempConfig({ mode: "active" }, { endpoint: "https://attacker.invalid" });
  try {
    assert.throws(() => loadConfig(endpoint.agentDir, endpoint.cwd), errIs("invalid_config"));
  } finally {
    endpoint.cleanup();
  }
});

test("missing, malformed, and invalid Jev responses fail closed without invented answers", async () => {
  const bad = [
    {},
    { ...payload(), answers: {} },
    { ...payload(), answers: { ...payload().answers, high_stakes: { type: "noul", noul: true } } },
    { ...payload(), answers: { ...payload().answers, capability: { ...payload().answers.capability, confidence: 1.1 } } },
    { ...payload(), answers: { ...payload().answers, capability: { ...payload().answers.capability, probabilities: { quick: 1, standard: 0 } } } },
    { ...payload(), answers: { ...payload().answers, capability: { ...payload().answers.capability, choice: "quick" } } },
    { ...payload(), answers: { ...payload().answers, reasoning_effort: { ...payload().answers.reasoning_effort, type: "score" } } },
    { ...payload(), usage: { input_tokens: -1, output_tokens: 1 } },
  ];
  for (const value of bad) assert.throws(() => parseClassification(value), errIs("invalid_response"));

  await assert.rejects(classifyTask({
    prompt: "task", agentType: "worker", config: policy(), apiKey: "x",
    fetchImpl: async () => ({ ok: true, status: 200, json: async () => { throw new SyntaxError("sensitive response"); } }),
  }), errIs("invalid_response"));
});

test("HTTP failures use safe status codes and never retry or read error bodies", async () => {
  for (const status of [401, 429, 529]) {
    let calls = 0;
    let readBody = false;
    await assert.rejects(classifyTask({
      prompt: "task", agentType: "worker", config: policy(), apiKey: "secret",
      fetchImpl: async () => {
        calls += 1;
        return { ok: false, status, json: async () => ({}), text: async () => { readBody = true; return "SECRET_ERROR_BODY"; } };
      },
    }), errIs(`http_${status}`));
    assert.equal(calls, 1);
    assert.equal(readBody, false);
  }
});

test("deadline covers response-body parsing and abort never retries", async () => {
  let calls = 0;
  await assert.rejects(classifyTask({
    prompt: "task", agentType: "worker", config: policy(), apiKey: "x", timeoutMs: 10,
    fetchImpl: async () => {
      calls += 1;
      return { ok: true, status: 200, json: () => new Promise(() => {}) };
    },
  }), errIs("timeout"));
  assert.equal(calls, 1);

  const controller = new AbortController();
  calls = 0;
  const aborting = classifyTask({
    prompt: "task", agentType: "worker", config: policy(), apiKey: "x", signal: controller.signal, timeoutMs: 1_000,
    fetchImpl: async (_url, init) => {
      calls += 1;
      return new Promise((_, reject) => init.signal.addEventListener("abort", () => reject(new Error("aborted")), { once: true }));
    },
  });
  setTimeout(() => controller.abort(), 5);
  await assert.rejects(aborting, errIs("aborted"));
  assert.equal(calls, 1);
});

test("oversized requests bypass instead of truncating the delegated prompt", async () => {
  let calls = 0;
  const prompt = "ü".repeat(10_000);
  await assert.rejects(classifyTask({
    prompt, agentType: "worker", config: policy(), apiKey: "x",
    fetchImpl: async () => { calls += 1; return jsonResponse(payload()); },
  }), errIs("request_too_large"));
  assert.equal(calls, 0);

  const privatePrompt = `PRIVATE_LONG_PROMPT_SENTINEL${"x".repeat(17_000)}`;
  await withRouter({}, async ({ cwd, handler, entries }) => withFetch(async () => {
    calls += 1;
    return jsonResponse(payload());
  }, async () => {
    const input = { prompt: privatePrompt, subagent_type: "worker" };
    await invoke(handler, cwd, input);
    assert.deepEqual(input, { prompt: privatePrompt, subagent_type: "worker" });
    assert.equal(entries[0].data.reasonCodes[0], "request_too_large");
    assert.ok(!JSON.stringify(entries).includes("PRIVATE_LONG_PROMPT_SENTINEL"));
  }));
  assert.equal(calls, 0);
});

test("shadow does not mutate; active changes only model and unpinned thinking", async () => {
  await withRouter({ global: { mode: "shadow" } }, async ({ cwd, handler, entries }) => withFetch(async () => jsonResponse(payload({ capability: "quick", reasoning: "off" })), async () => {
    const input = { prompt: "find a symbol", subagent_type: "explorer", description: "Look up symbol", custom: 17 };
    const original = structuredClone(input);
    await invoke(handler, cwd, input);
    assert.deepEqual(input, original);
    assert.equal(entries[0].data.status, "recommended", JSON.stringify(entries));
    assert.equal(entries[0].data.candidate, "opencode-go/glm-5.3-flash");
    assert.equal(entries[0].data.toolCallId, "call-1");
  }));

  await withRouter({}, async ({ cwd, handler }) => withFetch(async () => jsonResponse(payload({ capability: "quick", reasoning: "off" })), async () => {
    const input = { prompt: "find a symbol", subagent_type: "explorer", description: "Look up symbol", custom: 17 };
    await invoke(handler, cwd, input);
    assert.deepEqual(input, {
      prompt: "find a symbol",
      subagent_type: "explorer",
      description: "Look up symbol",
      custom: 17,
      model: "opencode-go/glm-5.3-flash",
      thinking: "off",
    });
  }));

  await withRouter({}, async ({ cwd, handler }) => withFetch(async () => jsonResponse(payload({ capability: "quick", reasoning: "low" })), async () => {
    const input = { prompt: "find a symbol", subagent_type: "explorer", thinking: "high" };
    await invoke(handler, cwd, input);
    assert.equal(input.model, "opencode-go/glm-5.3-flash");
    assert.equal(input.thinking, "high");
  }));
});

test("global off cannot be re-enabled at the tool boundary", async () => {
  await withRouter({ global: { mode: "off" }, project: { mode: "active" } }, async ({ cwd, handler, entries }) => withFetch(async () => {
    throw new Error("must not call Jev");
  }, async () => {
    const input = { prompt: "do task", subagent_type: "worker" };
    await invoke(handler, cwd, input);
    assert.deepEqual(input, { prompt: "do task", subagent_type: "worker" });
    assert.deepEqual(entries, []);
  }));
});

test("explicit model, resume, schedule, inherited context, and unrelated tools skip Jev", async () => {
  await withRouter({}, async ({ cwd, handler }) => withFetch(async () => { throw new Error("must not call Jev"); }, async () => {
    const cases = [
      { model: "openai/gpt-6-astra" },
      { resume: "old-agent" },
      { schedule: "5m" },
      { inherit_context: true },
    ];
    for (const extra of cases) {
      const input = { prompt: "do task", subagent_type: "worker", ...extra };
      const original = structuredClone(input);
      await invoke(handler, cwd, input);
      assert.deepEqual(input, original);
    }
    await invoke(handler, cwd, { prompt: "do task", subagent_type: "worker" }, { toolName: "Bash" });
  }));
});

test("empty scopes, missing key, invalid config, and API diagnostics fail open without leaking content", async () => {
  const secretPrompt = "TASK_PRIVATE_SENTINEL";
  const secretKey = "KEY_PRIVATE_SENTINEL";
  const secretError = "ERROR_BODY_PRIVATE_SENTINEL";
  let fetchCalls = 0;
  const failedFetch = async () => {
    fetchCalls += 1;
    return { ok: false, status: 401, json: async () => ({}), text: async () => secretError };
  };

  await withRouter({}, async ({ cwd, handler, entries }) => withFetch(failedFetch, async () => {
    const input = { prompt: secretPrompt, subagent_type: "worker" };
    await invoke(handler, cwd, input, { scopedModels: [{ model: { provider: "other", id: "model" } }] });
    assert.deepEqual(input, { prompt: secretPrompt, subagent_type: "worker" });
    assert.equal(entries[0].data.reasonCodes[0], "no_eligible_candidate", JSON.stringify(entries));
  }));

  await withRouter({ apiKey: null }, async ({ cwd, handler, entries }) => withFetch(failedFetch, async () => {
    await invoke(handler, cwd, { prompt: secretPrompt, subagent_type: "worker" });
    assert.equal(entries[0].data.reasonCodes[0], "missing_api_key");
  }));

  await withRouter({ global: { mode: "active", endpoint: "https://attacker.invalid" } }, async ({ cwd, handler, entries }) => withFetch(failedFetch, async () => {
    await invoke(handler, cwd, { prompt: secretPrompt, subagent_type: "worker" });
    assert.equal(entries[0].data.reasonCodes[0], "invalid_config");
  }));

  await withRouter({ apiKey: secretKey }, async ({ cwd, handler, entries }) => withFetch(failedFetch, async () => {
    await invoke(handler, cwd, { prompt: secretPrompt, subagent_type: "worker" });
    assert.equal(entries[0].data.reasonCodes[0], "http_401");
    const log = JSON.stringify(entries);
    assert.ok(!log.includes(secretPrompt));
    assert.ok(!log.includes(secretKey));
    assert.ok(!log.includes(secretError));
  }));
  assert.equal(fetchCalls, 1);
});

test("concurrent launches keep judgments and transcript correlation separate", async () => {
  await withRouter({}, async ({ cwd, handler, entries }) => withFetch(async (_url, init) => {
    const body = JSON.parse(init.body);
    return jsonResponse(body.state.agent_type === "reviewer"
      ? payload({ capability: "high", reasoning: "high", highStakes: 0.8 })
      : payload({ capability: "quick", reasoning: "off" }));
  }, async () => {
    const explorer = { prompt: "lookup", subagent_type: "explorer" };
    const reviewer = { prompt: "review", subagent_type: "reviewer" };
    await Promise.all([
      invoke(handler, cwd, explorer, { toolCallId: "call-explorer" }),
      invoke(handler, cwd, reviewer, { toolCallId: "call-reviewer" }),
    ]);
    assert.equal(explorer.model, "opencode-go/glm-5.3-flash", JSON.stringify(entries));
    assert.equal(reviewer.model, "openai/gpt-6-astra");
    const byId = new Map(entries.map((entry) => [entry.data.toolCallId, entry.data]));
    assert.equal(byId.get("call-explorer").candidate, explorer.model);
    assert.equal(byId.get("call-reviewer").candidate, reviewer.model);
  }));
});

test("transcript write failure cannot block the launch", async () => {
  await withRouter({ appendEntry: () => { throw new Error("disk full"); } }, async ({ cwd, handler }) => withFetch(async () => jsonResponse(payload({ capability: "quick", reasoning: "off" })), async () => {
    const input = { prompt: "lookup", subagent_type: "explorer" };
    await invoke(handler, cwd, input);
    assert.equal(input.model, "opencode-go/glm-5.3-flash");
  }));
});

test("installed Pi beforeToolCall path passes routed args to the tool executor", async () => {
  await withRouter({}, async ({ cwd, handler }) => withFetch(async () => jsonResponse(payload({ capability: "quick", reasoning: "off" })), async () => {
    // Test-only coupling: the installed Pi 0.87.1 AgentSession hook and agent-core
    // tool loop are exercised directly; update these paths/version with Pi upgrades.
    const piCli = realpathSync(execFileSync("which", ["pi"], { encoding: "utf8" }).trim());
    const packageDir = resolve(dirname(piCli), "../..");
    const packageJson = JSON.parse(readFileSync(join(packageDir, "package.json"), "utf8"));
    assert.equal(packageJson.name, "@earendil-works/pi-coding-agent");
    assert.equal(packageJson.version, "0.87.1");
    const subagentsDir = join(homedir(), ".pi", "agent", "npm", "node_modules", "@tintinweb", "pi-subagents");
    const subagentsPackage = JSON.parse(readFileSync(join(subagentsDir, "package.json"), "utf8"));
    assert.equal(subagentsPackage.version, "0.19.0");

    const [{ AgentSession }, { Agent }, { AssistantMessageEventStream }, resolver] = await Promise.all([
      import(pathToFileURL(join(packageDir, "dist", "core", "agent-session.js")).href),
      import(pathToFileURL(join(packageDir, "node_modules", "@earendil-works", "pi-agent-core", "dist", "agent.js")).href),
      import(pathToFileURL(join(packageDir, "node_modules", "@earendil-works", "pi-ai", "dist", "utils", "event-stream.js")).href),
      import(pathToFileURL(join(subagentsDir, "dist", "invocation-config.js")).href),
    ]);

    let toolArgs;
    let turn = 0;
    const tool = {
      name: "Agent",
      label: "Agent",
      description: "Launch a test child agent",
      parameters: {
        type: "object",
        properties: {
          prompt: { type: "string" },
          subagent_type: { type: "string" },
          model: { type: "string" },
          thinking: { type: "string" },
        },
        required: ["prompt", "subagent_type"],
        additionalProperties: true,
      },
      execute: async (_id, params) => {
        toolArgs = structuredClone(params);
        return { content: [{ type: "text", text: "child started" }], details: undefined };
      },
    };
    const model = {
      id: "test-model", name: "test-model", api: "openai-completions", provider: "openai", baseUrl: "",
      reasoning: false, input: ["text"], contextWindow: 32_000, maxTokens: 1_000,
      cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
    };
    const message = (content, stopReason) => ({
      role: "assistant", content, api: "openai-completions", provider: "openai", model: "test-model",
      usage: { input: 1, output: 1, cacheRead: 0, cacheWrite: 0, totalTokens: 2,
        cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
      stopReason, timestamp: Date.now(),
    });
    const agent = new Agent({
      initialState: { model, tools: [tool], systemPrompt: "test" },
      streamFn: async () => {
        const stream = new AssistantMessageEventStream();
        turn += 1;
        stream.push({
          type: "done",
          message: turn === 1
            ? message([{ type: "toolCall", id: "agent-tool-call", name: "Agent", arguments: { prompt: "lookup", subagent_type: "explorer" } }], "toolUse")
            : message([{ type: "text", text: "complete" }], "stop"),
        });
        return stream;
      },
    });

    const session = Object.create(AgentSession.prototype);
    session.agent = agent;
    session._extensionRunner = {
      hasHandlers: (event) => event === "tool_call",
      emitToolCall: (event) => handler(event, ctx(cwd)),
    };
    session._installAgentToolHooks();
    await agent.prompt("start");
    assert.equal(toolArgs.model, "opencode-go/glm-5.3-flash", JSON.stringify(toolArgs));
    assert.equal(toolArgs.thinking, "off");

    // Installed pi-subagents 0.19.0 resolver check: agent frontmatter wins over
    // routed parameters; the router's transcript only says "requested".
    const resolved = resolver.resolveAgentInvocationConfig(
      { model: "openai/gpt-6-astra", thinking: "high" },
      { model: toolArgs.model, thinking: toolArgs.thinking },
    );
    assert.equal(resolved.modelInput, "openai/gpt-6-astra");
    assert.equal(resolved.thinking, "high");
  }));
});

test("repository routing source stays off and carries the agreed candidate chains", () => {
  const source = JSON.parse(readFileSync(new URL("../../pi-subagent-router.json", import.meta.url), "utf8"));
  assert.equal(source.mode, "off");
  assert.deepEqual(source.tiers, DEFAULTS.tiers);
});

let failures = 0;
for (const check of checks) {
  try {
    await check.run();
    console.log(`✔ ${check.name}`);
  } catch (error) {
    failures += 1;
    console.error(`✖ ${check.name}\n`, error);
  }
}
console.log(`${checks.length - failures}/${checks.length} offline checks passed`);
if (failures > 0) process.exitCode = 1;
