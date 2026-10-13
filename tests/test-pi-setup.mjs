/** Offline integration checks using the installed Pi loader; no model calls or sessions. */
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, readFileSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { homedir, tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import test from "node:test";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const agentDir = process.env.PI_CODING_AGENT_DIR ?? join(homedir(), ".pi", "agent");
const install = join(agentDir, "install");
const packageRoot = process.env.PI_PACKAGE_ROOT ?? join(
  install, "releases", readFileSync(join(install, "current-version"), "utf8").trim(),
  "node_modules", "@earendil-works/pi-coding-agent",
);
const { DefaultResourceLoader, SettingsManager } = await import(
  pathToFileURL(join(packageRoot, "dist/index.js")).href
);
const { loadExtensions, clearExtensionCache } = await import(
  pathToFileURL(join(packageRoot, "dist/core/extensions/loader.js")).href
);
const { loadSkills, formatSkillsForPrompt } = await import(
  pathToFileURL(join(packageRoot, "dist/core/skills.js")).href
);
const settings = JSON.parse(readFileSync(join(root, "pi/settings.json"), "utf8"));
const guardedNames = ["@juicesharp/rpiv-ask-user-question", "pi-title"];
const extensionPath = join(root, "pi/extensions/standalone-ui.ts");
const sourceOf = entry => typeof entry === "string" ? entry : entry.source;
const nameOf = entry => sourceOf(entry).slice(4, sourceOf(entry).lastIndexOf("@"));

function fixture(t, bb) {
  const temp = mkdtempSync(join(tmpdir(), "pi-setup-"));
  const oldAgentDir = process.env.PI_CODING_AGENT_DIR;
  const oldThread = process.env.BB_THREAD_ID;
  process.env.PI_CODING_AGENT_DIR = temp;
  if (bb) process.env.BB_THREAD_ID = "test-thread";
  else delete process.env.BB_THREAD_ID;
  clearExtensionCache();
  t.after(() => {
    if (oldAgentDir === undefined) delete process.env.PI_CODING_AGENT_DIR;
    else process.env.PI_CODING_AGENT_DIR = oldAgentDir;
    if (oldThread === undefined) delete process.env.BB_THREAD_ID;
    else process.env.BB_THREAD_ID = oldThread;
    clearExtensionCache();
    rmSync(temp, { recursive: true, force: true });
  });
  return temp;
}

function registrations(result) {
  assert.deepEqual(result.errors, []);
  return {
    tools: result.extensions.flatMap(e => [...e.tools.keys()]),
    commands: result.extensions.flatMap(e => [...e.commands.keys()]),
    hooks: result.extensions.flatMap(e => [...e.handlers.keys()]),
  };
}

test("all seven direct packages are pinned to installed versions", () => {
  assert.equal(settings.packages.length, 7);
  for (const entry of settings.packages) {
    const source = sourceOf(entry);
    assert.match(source, /^npm:(?:@[^/]+\/)?[^@]+@\d+\.\d+\.\d+$/);
    const installed = JSON.parse(readFileSync(
      join(agentDir, "npm/node_modules", nameOf(entry), "package.json"), "utf8",
    ));
    assert.equal(source, `npm:${installed.name}@${installed.version}`);
  }
  for (const name of guardedNames) {
    const entry = settings.packages.find(e => nameOf(e) === name);
    assert.deepEqual(entry.extensions, [], `${name} must not also autoload`);
  }
});

test("BB guard neither imports missing packages nor registers tools, commands or title hooks", async t => {
  const temp = fixture(t, true); // Deliberately has no npm directory.
  const result = await loadExtensions([extensionPath], temp);
  assert.deepEqual(registrations(result), { tools: [], commands: [], hooks: [] });
});

for (const bb of [false, true]) {
  test(`${bb ? "BB" : "standalone"}: configured package filtering and reload register each feature at most once`, async t => {
    const temp = fixture(t, bb);
    symlinkSync(join(agentDir, "npm"), join(temp, "npm"), "dir");
    const loader = new DefaultResourceLoader({
      cwd: temp,
      agentDir: temp,
      settingsManager: SettingsManager.inMemory({
        packages: settings.packages.filter(e => guardedNames.includes(nameOf(e))),
        extensions: [extensionPath],
      }),
      noSkills: true,
      noThemes: true,
      noPromptTemplates: true,
      noContextFiles: true,
    });
    for (let reload = 0; reload < 2; reload++) {
      await loader.reload();
      const actual = registrations(loader.getExtensions());
      assert.deepEqual(actual.tools, bb ? [] : ["ask_user_question"]);
      assert.deepEqual(actual.commands, bb ? [] : ["title"]);
      if (bb) assert.deepEqual(actual.hooks, []);
      else {
        assert.ok(actual.hooks.includes("before_agent_start"));
        assert.ok(actual.hooks.includes("agent_settled"));
      }
    }
  });
}

test("personal pi-handoff coexists with BB's automatically discoverable handoff", t => {
  const temp = fixture(t, true);
  const bbSkills = join(temp, "skills/handoff");
  mkdirSync(bbSkills, { recursive: true });
  writeFileSync(join(bbSkills, "SKILL.md"),
    "---\nname: handoff\ndescription: Transfer BB sessions between providers.\n---\nUse BB handoff.\n");
  const loaded = loadSkills({
    cwd: temp, agentDir: temp, includeDefaults: false,
    skillPaths: [join(root, "agents/skills"), join(temp, "skills")],
  });
  assert.deepEqual(loaded.diagnostics, []);
  assert.equal(loaded.skills.find(s => s.name === "pi-handoff")?.disableModelInvocation, true);
  assert.equal(loaded.skills.find(s => s.name === "handoff")?.disableModelInvocation, false);
  const prompt = formatSkillsForPrompt(loaded.skills);
  assert.match(prompt, /<name>handoff<\/name>/);
  assert.doesNotMatch(prompt, /<name>pi-handoff<\/name>/);
  assert.match(readFileSync(join(root, "agents/skills/pi-handoff/agents/openai.yaml"), "utf8"),
    /allow_implicit_invocation: false/);
});
