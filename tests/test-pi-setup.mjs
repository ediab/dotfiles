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
const { loadSkills } = await import(
  pathToFileURL(join(packageRoot, "dist/core/skills.js")).href
);
const settings = JSON.parse(readFileSync(join(root, "pi/settings.json"), "utf8"));
const guardedNames = ["pi-title"];
const pstackRoot = join(agentDir, "git/github.com/michael-denyer/pstack-claude");
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

test("npm packages and pstack are pinned to installed versions", () => {
  assert.equal(settings.packages.length, 5);
  for (const entry of settings.packages.filter(e => sourceOf(e).startsWith("npm:"))) {
    const source = sourceOf(entry);
    assert.match(source, /^npm:(?:@[^/]+\/)?[^@]+@\d+\.\d+\.\d+$/);
    const installed = JSON.parse(readFileSync(
      join(agentDir, "npm/node_modules", nameOf(entry), "package.json"), "utf8",
    ));
    assert.equal(source, `npm:${installed.name}@${installed.version}`);
  }
  const pstack = settings.packages.find(e => sourceOf(e).startsWith("git:"));
  assert.match(sourceOf(pstack), /^git:github\.com\/michael-denyer\/pstack-claude@[a-f0-9]{40}$/);
  const { execFileSync } = process.getBuiltinModule("node:child_process");
  assert.equal(execFileSync("git", ["-C", pstackRoot, "rev-parse", "HEAD"], { encoding: "utf8" }).trim(),
    sourceOf(pstack).split("@")[1]);
  assert.ok(!settings.packages.some(e => sourceOf(e).includes("rpiv-ask-user-question")));
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
      assert.deepEqual(actual.tools, []);
      assert.deepEqual(actual.commands, bb ? [] : ["title"]);
      if (bb) assert.deepEqual(actual.hooks, []);
      else {
        assert.ok(actual.hooks.includes("before_agent_start"));
        assert.ok(actual.hooks.includes("agent_settled"));
      }
    }
  });
}

for (const bb of [false, true]) {
  test(`${bb ? "BB" : "standalone"}: pstack stays available without automatic routing or collisions`, async t => {
    const temp = fixture(t, bb);
    for (const dir of ["npm", "git"]) symlinkSync(join(agentDir, dir), join(temp, dir), "dir");
    symlinkSync(join(root, "pi/pstack-models.md"), join(temp, "pstack-models.md"));
    const loader = new DefaultResourceLoader({
      cwd: temp,
      agentDir: temp,
      settingsManager: SettingsManager.inMemory({
        packages: settings.packages.filter(e => sourceOf(e).startsWith("git:") || guardedNames.includes(nameOf(e))),
        extensions: [extensionPath],
      }),
      noThemes: true,
      noPromptTemplates: true,
      noContextFiles: true,
    });
    for (let reload = 0; reload < 2; reload++) {
      await loader.reload();
      const actual = registrations(loader.getExtensions());
      assert.deepEqual([...actual.tools].sort(), [
        "agent", "ask_user_question", "list_agents", "schedule_wakeup", "send_message", "stop_agent",
      ]);
      assert.deepEqual([...actual.commands].sort(), bb ? ["loop"] : ["loop", "title"]);
      const extension = loader.getExtensions().extensions.find(e => e.path.endsWith("pstack/pi/index.ts"));
      assert.ok(extension);
      const event = { systemPromptOptions: { sections: {} } };
      for (const handler of extension.handlers.get("before_agent_start") ?? []) await handler(event, {});
      assert.equal(event.systemPromptOptions.sections["pstack-session-start"], undefined);
      assert.match(event.systemPromptOptions.sections["pstack-models"], /^session hook: off$/m);
      const { skills, diagnostics } = loader.getSkills();
      assert.deepEqual(diagnostics, []);
      const upstream = skills.filter(s => s.filePath.includes("pstack-claude/plugins/pstack/skills/"));
      assert.equal(upstream.length, 63);
      assert.equal(new Set(skills.map(s => s.name)).size, skills.length);
      for (const name of ["poteto-mode", "bro", "unslop"]) assert.ok(upstream.some(s => s.name === name));
    }
  });
}

test("UI skills load once and Pi selects its native Impeccable build", async t => {
  const temp = fixture(t, false);
  const loader = new DefaultResourceLoader({
    cwd: temp,
    agentDir,
    settingsManager: SettingsManager.inMemory({ skills: settings.skills }),
    noExtensions: true,
    noThemes: true,
    noPromptTemplates: true,
    noContextFiles: true,
  });
  await loader.reload();
  const { skills, diagnostics } = loader.getSkills();
  assert.deepEqual(diagnostics, []);
  for (const name of ["impeccable", "interface-design"]) {
    assert.equal(skills.filter(s => s.name === name).length, 1, name);
  }
  assert.equal(skills.find(s => s.name === "impeccable").filePath,
    join(agentDir, "skills/impeccable/SKILL.md"));
  assert.ok(!skills.some(s => s.name === "design-taste-frontend"));
});

test("personal skills and BB handoff have no retired copies or upstream name collisions", t => {
  const temp = fixture(t, true);
  const bbSkills = join(temp, "skills/handoff");
  mkdirSync(bbSkills, { recursive: true });
  writeFileSync(join(bbSkills, "SKILL.md"),
    "---\nname: handoff\ndescription: Transfer BB sessions between providers.\n---\nUse BB handoff.\n");
  const loaded = loadSkills({
    cwd: temp, agentDir: temp, includeDefaults: false,
    skillPaths: [join(root, "agents/skills"), join(pstackRoot, "plugins/pstack/skills"), join(temp, "skills")],
  });
  assert.deepEqual(loaded.diagnostics, []);
  const names = new Set(loaded.skills.map(s => s.name));
  for (const retired of ["grilling", "grill-me", "grill-with-docs", "to-spec", "to-tickets", "implement",
    "diagnosing-bugs", "domain-modeling", "prototype", "retro", "wayfinder", "writing-for-agents",
    "pi-handoff", "personal-workflow"]) assert.ok(!names.has(retired), retired);
  assert.ok(names.has("handoff"));
});
