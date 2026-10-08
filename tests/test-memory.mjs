import assert from 'node:assert/strict';
import { execFileSync, spawn } from 'node:child_process';
import { createRequire } from 'node:module';
import { chmodSync, existsSync, lstatSync, mkdirSync, mkdtempSync, readFileSync, realpathSync, rmSync, symlinkSync, writeFileSync } from 'node:fs';
import { homedir, tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import test from 'node:test';
import { MemoryStore, projectRoot, revision } from '../pi/extensions/memory/store.mjs';

const repo = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const storePath = join(repo, 'pi/extensions/memory/store.mjs');
const extensionPath = join(repo, 'pi/extensions/memory/index.ts');
const install = join(homedir(), '.pi/agent/install');
const packageRoot = process.env.PI_PACKAGE_ROOT ?? join(install, 'releases', readFileSync(join(install, 'current-version'), 'utf8').trim(), 'node_modules/@earendil-works/pi-coding-agent');
const require = createRequire(join(packageRoot, 'package.json'));
const { createJiti } = require('jiti');
const host = dirname(dirname(require.resolve('@earendil-works/pi-tui/package.json')));
const typebox = require.resolve('typebox');
const jiti = createJiti(join(packageRoot, 'dist/index.js'), {
  moduleCache: false, fsCache: false,
  alias: {
    '@earendil-works/pi-coding-agent': join(packageRoot, 'dist/index.js'),
    '@earendil-works/pi-ai': join(host, 'pi-ai/dist/compat.js'),
    '@earendil-works/pi-ai/compat': join(host, 'pi-ai/dist/compat.js'),
    '@earendil-works/pi-agent-core': join(host, 'pi-agent-core/dist/index.js'),
    '@earendil-works/pi-tui': require.resolve('@earendil-works/pi-tui'),
    typebox, 'typebox/compile': typebox, 'typebox/value': typebox,
    '@sinclair/typebox': typebox,
  },
});

function fixture(t) {
  const dir = realpathSync(mkdtempSync(join(tmpdir(), 'home-memory-test-')));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  const agent = join(dir, 'agent');
  const a = join(dir, 'a');
  const b = join(dir, 'b');
  for (const path of [agent, a, b]) mkdirSync(path);
  for (const path of [a, b]) execFileSync('git', ['init', '-q', path]);
  return { dir, agent, a, b, store: new MemoryStore(agent) };
}

async function harness(f, cwd = f.a, branch = []) {
  const handlers = new Map();
  const tools = new Map();
  const entries = branch;
  const pi = {
    on(name, handler) { handlers.set(name, handler); },
    registerTool(tool) { tools.set(tool.name, tool); },
    appendEntry(customType, data) { entries.push({ type: 'custom', customType, data }); },
  };
  const ctx = { cwd, mode: 'rpc', hasUI: false, sessionManager: { getBranch: () => entries } };
  const factory = await jiti.import(extensionPath, { default: true });
  factory(pi);
  const emit = async (name, event = {}) => {
    const before = process.env.PI_CODING_AGENT_DIR;
    process.env.PI_CODING_AGENT_DIR = f.agent;
    try { return await handlers.get(name)({ type: name, ...event }, ctx); }
    finally {
      if (before === undefined) delete process.env.PI_CODING_AGENT_DIR;
      else process.env.PI_CODING_AGENT_DIR = before;
    }
  };
  await emit('session_start');
  return {
    entries, handlers, tools, emit,
    async call(params) {
      const result = await tools.get('memory').execute('test', params, undefined, undefined, ctx);
      return JSON.parse(result.content[0].text);
    },
    async snapshot() {
      const event = { systemPromptOptions: { sections: {} } };
      await emit('before_agent_start', event);
      return event.systemPromptOptions.sections.home_memory;
    },
  };
}

function runNode(source) {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, ['--input-type=module', '-e', source]);
    let stdout = '', stderr = '';
    child.stdout.on('data', (data) => { stdout += data; });
    child.stderr.on('data', (data) => { stderr += data; });
    child.on('error', reject);
    child.on('exit', (code) => code === 0 ? resolve(JSON.parse(stdout)) : reject(new Error(stderr)));
  });
}

test('initial scope follows nested cwd; parent directory and explicit non-Git selection work', (t) => {
  const f = fixture(t);
  mkdirSync(join(f.a, 'src'));
  assert.equal(projectRoot(join(f.a, 'src')), f.a);
  assert.equal(projectRoot(f.dir), null);
  assert.equal(projectRoot(f.dir, f.dir, true), f.dir);
  assert.throws(() => projectRoot(join(f.dir, 'missing')), /does not exist/);
  const alias = join(f.dir, 'alias');
  symlinkSync(f.a, alias);
  assert.equal(projectRoot(alias), f.a);
});

test('non-Git case aliases share one private store on case-insensitive filesystems', (t) => {
  const f = fixture(t);
  const folder = join(f.dir, 'CaseDir');
  const alias = join(f.dir, 'casedir');
  mkdirSync(folder);
  if (!existsSync(alias)) return t.skip('filesystem is case-sensitive');
  const root = projectRoot(folder, f.dir, true);
  const aliasRoot = projectRoot(alias, f.dir, true);
  assert.equal(aliasRoot, root);
  f.store.save(root, 'private', undefined, 'same project', 'missing');
  assert.equal(f.store.read(aliasRoot, 'private').content, 'same project');
});

test('Git discovery forces the C locale without changing the parent environment', (t) => {
  const f = fixture(t);
  const bin = join(f.dir, 'bin');
  mkdirSync(bin);
  writeFileSync(join(bin, 'git'), '#!/bin/sh\nif [ "$LC_ALL" != C ]; then echo "translated error" >&2; exit 128; fi\necho "fatal: not a git repository" >&2\nexit 128\n', { mode: 0o755 });
  const result = execFileSync(process.execPath, ['--input-type=module', '-e', `
    import assert from 'node:assert/strict';
    import { projectRoot } from ${JSON.stringify(pathToFileURL(storePath).href)};
    assert.equal(projectRoot(${JSON.stringify(f.dir)}), null);
    assert.equal(process.env.LC_ALL, 'fr_FR.UTF-8');
  `], { env: { ...process.env, PATH: bin, LC_ALL: 'fr_FR.UTF-8' } });
  assert.equal(result.length, 0);
});

test('missing files are normal and reads create no directories', (t) => {
  const f = fixture(t);
  assert.equal(f.store.read(f.a, 'private').revision, 'missing');
  assert.deepEqual(f.store.listHandoffs(f.a), []);
  assert.equal(existsSync(f.store.base), false);
  assert.equal(f.store.read(f.a, 'project').exists, false);
});

test('private/shareable memories survive new stores without leaking across projects', (t) => {
  const f = fixture(t);
  const shared = f.store.save(f.a, 'project', undefined, '# Shared\n', 'missing');
  const privateNote = f.store.save(f.a, 'private', undefined, '# Private\n', 'missing');
  assert.equal(shared.path, join(f.a, 'MEMORY.md'));
  assert.equal(lstatSync(privateNote.path).mode & 0o777, 0o600);
  assert.equal(lstatSync(f.store.base).mode & 0o777, 0o700);
  assert.equal(lstatSync(f.store.checkoutDir(f.a)).mode & 0o777, 0o700);
  assert.deepEqual(JSON.parse(readFileSync(join(f.store.checkoutDir(f.a), 'checkout.json'))), { root: f.a });
  assert.equal(new MemoryStore(f.agent).read(f.a, 'private').content, '# Private\n');
  assert.equal(f.store.read(f.b, 'private').exists, false);
  assert.equal(f.store.read(f.b, 'project').exists, false);
  assert.equal(execFileSync('git', ['-C', f.a, 'status', '--porcelain'], { encoding: 'utf8' }).trim(), '?? MEMORY.md');
});

test('stale writes fail without losing data; empty content clears memory', (t) => {
  const f = fixture(t);
  const note = f.store.save(f.a, 'project', undefined, 'first', 'missing');
  f.store.save(f.a, 'project', undefined, 'second', note.revision);
  assert.throws(() => f.store.save(f.a, 'project', undefined, 'lost update', note.revision), /changed since/);
  assert.equal(f.store.read(f.a, 'project').content, 'second');
  const current = f.store.read(f.a, 'project');
  assert.equal(f.store.save(f.a, 'project', undefined, '', current.revision).revision, revision(''));
  assert.equal(existsSync(`${current.path}.lock`), false);
});

test('independent concurrent processes cannot silently overwrite each other', async (t) => {
  const f = fixture(t);
  const source = `import { MemoryStore } from ${JSON.stringify(pathToFileURL(storePath).href)};
const store = new MemoryStore(${JSON.stringify(f.agent)});
try { store.save(${JSON.stringify(f.a)}, 'project', undefined, 'winner', 'missing'); console.log(JSON.stringify({saved:true})); }
catch (error) { console.log(JSON.stringify({saved:false,error:String(error)})); }`;
  const results = await Promise.all(Array.from({ length: 5 }, () => runNode(source)));
  assert.equal(results.filter((result) => result.saved).length, 1);
  assert.ok(results.filter((result) => !result.saved).every((result) => /busy|changed since/.test(result.error)));
  assert.equal(f.store.read(f.a, 'project').content, 'winner');
});

test('busy locks are never removed automatically', (t) => {
  const f = fixture(t);
  const lock = join(f.a, 'MEMORY.md.lock');
  writeFileSync(lock, 'a live owner');
  assert.throws(() => f.store.save(f.a, 'project', undefined, 'no', 'missing'), /busy/);
  assert.equal(readFileSync(lock, 'utf8'), 'a live owner');
});

test('named handoffs are separate, searchable and validated', (t) => {
  const f = fixture(t);
  f.store.save(f.a, 'handoff', 'alpha', 'Connector task A\n', 'missing');
  f.store.save(f.a, 'handoff', 'beta', 'Connector task B\n', 'missing');
  assert.deepEqual(f.store.listHandoffs(f.a), ['alpha', 'beta']);
  assert.equal(f.store.read(f.a, 'handoff', 'alpha').content, 'Connector task A\n');
  assert.equal(f.store.search(f.a, 'CONNECTOR').total, 2);
  assert.equal(f.store.search(f.b, 'connector').total, 0);
  for (const name of ['../escape', '/tmp/escape', '', 'a.md', undefined]) {
    assert.throws(() => f.store.read(f.a, 'handoff', name), /Handoff name/);
  }
  assert.throws(() => f.store.search(f.a, ''), /non-empty/);
});

test('search bounds output and reports omitted matches', (t) => {
  const f = fixture(t);
  f.store.save(f.a, 'project', undefined, 'needle\n'.repeat(120), 'missing');
  const result = f.store.search(f.a, 'needle');
  assert.equal(result.matches.length, 100);
  assert.equal(result.total, 120);
  assert.equal(result.truncated, true);
});

test('symlink targets, private directories and non-file memories are rejected', (t) => {
  const f = fixture(t);
  const outside = join(f.dir, 'outside.md');
  writeFileSync(outside, 'preserve');
  symlinkSync(outside, join(f.a, 'MEMORY.md'));
  assert.throws(() => f.store.read(f.a, 'project'), /regular file/);
  assert.throws(() => f.store.save(f.a, 'project', undefined, 'overwrite', 'missing'), /regular file/);
  assert.equal(readFileSync(outside, 'utf8'), 'preserve');
  symlinkSync(f.b, f.store.base);
  assert.throws(() => f.store.read(f.a, 'private'), /real directory/);
  mkdirSync(join(f.b, 'MEMORY.md'));
  assert.throws(() => f.store.read(f.b, 'project'), /regular file/);
});

test('read errors are not treated as missing memories', (t) => {
  const f = fixture(t);
  const path = join(f.a, 'MEMORY.md');
  writeFileSync(path, 'protected');
  chmodSync(path, 0);
  t.after(() => { if (existsSync(path)) chmodSync(path, 0o600); });
  assert.throws(() => f.store.read(f.a, 'project'), /EACCES/);
});

test('invalid checkout metadata cannot overwrite private memory or leave a lock', (t) => {
  const f = fixture(t);
  const before = f.store.save(f.a, 'private', undefined, 'preserve', 'missing');
  const metadata = join(f.store.checkoutDir(f.a), 'checkout.json');
  rmSync(metadata);
  mkdirSync(metadata);
  assert.throws(() => f.store.save(f.a, 'private', undefined, 'overwrite', before.revision), /metadata must be a regular file/);
  assert.equal(f.store.read(f.a, 'private').content, 'preserve');
  assert.equal(existsSync(`${before.path}.lock`), false);
});

test('private saves refuse an agent directory inside a Git repository', (t) => {
  const f = fixture(t);
  const agent = join(f.a, 'agent');
  mkdirSync(agent);
  const store = new MemoryStore(agent);
  assert.throws(() => store.save(f.a, 'private', undefined, 'private', 'missing'), /inside a Git repository/);
  assert.equal(existsSync(store.base), false);
});

test('Git worktrees have isolated private storage and branch-specific project memory', (t) => {
  const f = fixture(t);
  f.store.save(f.a, 'project', undefined, 'main branch', 'missing');
  execFileSync('git', ['-C', f.a, 'add', 'MEMORY.md']);
  execFileSync('git', ['-C', f.a, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'fixture']);
  const worktree = join(f.dir, 'worktree');
  execFileSync('git', ['-C', f.a, 'worktree', 'add', '-qb', 'fixture-branch', worktree]);
  assert.equal(projectRoot(worktree), worktree);
  f.store.save(f.a, 'private', undefined, 'checkout A', 'missing');
  assert.equal(f.store.read(worktree, 'private').exists, false);
  f.store.save(worktree, 'project', undefined, 'worktree branch', f.store.read(worktree, 'project').revision);
  assert.equal(f.store.read(f.a, 'project').content, 'main branch');
  assert.notEqual(f.store.checkoutDir(f.a), f.store.checkoutDir(worktree));
});

test('extension registers one non-UI tool and scope-isolated structured memory', async (t) => {
  const f = fixture(t);
  f.store.save(f.a, 'project', undefined, 'A shared', 'missing');
  f.store.save(f.a, 'private', undefined, 'A private', 'missing');
  f.store.save(f.b, 'project', undefined, 'B shared', 'missing');
  const a = await harness(f);
  const b = await harness(f, f.b);
  assert.deepEqual([...a.tools.keys()], ['memory']);
  assert.equal(a.tools.get('memory').executionMode, 'sequential');
  const snapshot = await a.snapshot();
  assert.match(snapshot, /A shared/);
  assert.match(snapshot, /A private/);
  assert.doesNotMatch(snapshot, /B shared/);
  assert.match(await b.snapshot(), /B shared/);
  assert.equal(await a.snapshot(), snapshot);
  assert.equal(a.handlers.has('context'), false);
});

test('memory snapshot refreshes at the next run while tool results refresh immediately', async (t) => {
  const f = fixture(t);
  const note = f.store.save(f.a, 'project', undefined, 'old', 'missing');
  const h = await harness(f);
  assert.match(await h.snapshot(), /old/);
  writeFileSync(note.path, 'external update');
  const event = { systemPromptOptions: { sections: {} } };
  await h.emit('before_agent_start', event);
  assert.match(event.systemPromptOptions.sections.home_memory, /Workers report/);
  assert.match(event.systemPromptOptions.sections.home_memory, /external update/);
  const [current] = await h.call({ action: 'read', layer: 'project' });
  const saved = await h.call({ action: 'save', layer: 'project', content: 'saved update', expectedRevision: current.revision });
  assert.equal(saved.content, 'saved update');
  assert.doesNotMatch(event.systemPromptOptions.sections.home_memory, /saved update/);
  assert.match(await h.snapshot(), /saved update/);
  assert.equal((await h.call({ action: 'status' })).errors.length, 0);
});

test('explicit lookup does not switch projects; selection survives resume and resets on branches', async (t) => {
  const f = fixture(t);
  f.store.save(f.b, 'project', undefined, 'B lookup', 'missing');
  const h = await harness(f);
  assert.equal((await h.call({ action: 'read', path: f.b }))[0].content, 'B lookup');
  assert.equal((await h.call({ action: 'status' })).project, f.a);
  await h.call({ action: 'select', path: f.b });
  assert.equal((await h.call({ action: 'status' })).project, f.b);
  const resumed = await harness(f, f.a, [
    { type: 'custom', customType: 'home-memory-selection', data: { root: join(f.dir, 'old-deleted-checkout'), handoff: null } },
    ...h.entries,
  ]);
  assert.equal((await resumed.call({ action: 'status' })).project, f.b);
  resumed.entries.length = 0;
  await resumed.emit('session_tree');
  assert.equal((await resumed.call({ action: 'status' })).project, f.a);
  await assert.rejects(h.call({ action: 'save', path: f.a, layer: 'project', content: 'bad', expectedRevision: 'missing' }), /path is only/);
});

test('outside a repository loads no project until explicitly selected', async (t) => {
  const f = fixture(t);
  const h = await harness(f, f.dir);
  assert.equal((await h.call({ action: 'status' })).project, null);
  assert.doesNotMatch(await h.snapshot(), /# Current project memory/);
  await assert.rejects(h.call({ action: 'read' }), /No active project/);
  await h.call({ action: 'select', path: f.a });
  assert.equal((await h.call({ action: 'status' })).project, f.a);
});

test('handoffs are not injected unless explicitly resumed, and remain separate on fresh sessions', async (t) => {
  const f = fixture(t);
  f.store.save(f.a, 'handoff', 'alpha', 'Task A', 'missing');
  f.store.save(f.a, 'handoff', 'beta', 'Task B', 'missing');
  const h = await harness(f);
  assert.doesNotMatch(await h.snapshot(), /# Current project memory/);
  assert.deepEqual((await h.call({ action: 'status' })).handoffs, ['alpha', 'beta']);
  await h.call({ action: 'resume', name: 'alpha' });
  assert.match(await h.snapshot(), /Task A/);
  assert.doesNotMatch(await h.snapshot(), /Task B/);
  const resumed = await harness(f, f.a, [...h.entries]);
  assert.match(await resumed.snapshot(), /Task A/);
  await h.call({ action: 'select', path: f.a });
  assert.doesNotMatch(await h.snapshot(), /# Current project memory/);
  await assert.rejects(h.call({ action: 'resume', name: 'missing' }), /does not exist/);
});

test('failed reads are visible in automatic context and status; no silent stale fallback', async (t) => {
  const f = fixture(t);
  mkdirSync(join(f.a, 'MEMORY.md'));
  const h = await harness(f);
  assert.match(await h.snapshot(), /Memory read failed/);
  assert.equal((await h.call({ action: 'status' })).errors.length, 1);
});

test('large memories warn without losing context and status reports overhead', async (t) => {
  const f = fixture(t);
  f.store.save(f.a, 'project', undefined, 'lesson\n'.repeat(160) + 'LAST LINE', 'missing');
  const h = await harness(f);
  assert.match(await h.snapshot(), /LAST LINE/);
  const status = await h.call({ action: 'status' });
  assert.equal(status.warnings.length, 1);
  assert.ok(status.estimatedSnapshotTokens > 0);
  assert.ok(status.loadMs >= 0);
});

test('unavailable saved selections stay visible until explicitly corrected', async (t) => {
  const f = fixture(t);
  const h = await harness(f, f.a, [{ type: 'custom', customType: 'home-memory-selection', data: { root: join(f.dir, 'gone'), handoff: null } }]);
  await h.emit('before_agent_start', { systemPromptOptions: { sections: {} } });
  assert.match(await h.snapshot(), /selection failed/);
  assert.equal((await h.call({ action: 'status' })).errors.length, 1);
  await h.call({ action: 'select', path: f.a });
  assert.equal((await h.call({ action: 'status' })).errors.length, 0);
});

test('concurrent first private saves coordinate directory creation and revisions', async (t) => {
  const f = fixture(t);
  const source = `import { MemoryStore } from ${JSON.stringify(pathToFileURL(storePath).href)};
const store = new MemoryStore(${JSON.stringify(f.agent)});
try { store.save(${JSON.stringify(f.a)}, 'private', undefined, 'winner', 'missing'); console.log(JSON.stringify({saved:true})); }
catch (error) { console.log(JSON.stringify({saved:false,error:String(error)})); }`;
  const results = await Promise.all(Array.from({ length: 5 }, () => runNode(source)));
  assert.equal(results.filter((result) => result.saved).length, 1);
  assert.ok(results.filter((result) => !result.saved).every((result) => /busy|changed since/.test(result.error)));
});

test('installed Pi SDK loads the memory tool and restores recall after real compaction without network inference', async (t) => {
  const f = fixture(t);
  f.store.save(f.a, 'project', undefined, 'SDK recall marker', 'missing');
  const sdk = await jiti.import(join(packageRoot, 'dist/index.js'));
  const ai = await jiti.import(join(host, 'pi-ai/dist/compat.js'));
  const captured = [];
  const settings = sdk.SettingsManager.inMemory({ packages: [], compaction: { keepRecentTokens: 32, reserveTokens: 100 } });
  const loader = new sdk.DefaultResourceLoader({
    cwd: f.a, agentDir: f.agent, settingsManager: settings,
    noSkills: true, noThemes: true, noPromptTemplates: true, noContextFiles: true,
    additionalExtensionPaths: [extensionPath],
    extensionFactories: [(pi) => {
      pi.registerTool({
        name: 'memory_nested_probe', label: 'Memory nested probe', description: 'Fixture nested calls',
        parameters: ai.Type.Object({}),
        async execute(_id, _params, _signal, _update, ctx) {
          const result = await ctx.executeTool('memory', { action: 'read' });
          assert.equal(result.isError, false);
          assert.equal(JSON.parse(result.result.content[0].text)[0].content, 'SDK recall marker');
          const invalid = await ctx.executeTool('memory', { action: 'invalid' });
          assert.equal(invalid.isError, true);
          assert.match(invalid.result.content[0].text, /Validation failed for tool "memory":/);
          assert.doesNotMatch(invalid.result.content[0].text, /Unknown memory action/);
          return { content: [{ type: 'text', text: 'Nested validation passed' }], details: undefined };
        },
      });
      pi.on('session_start', () => pi.registerProvider('memory-test', {
        api: 'openai-completions', baseUrl: 'https://memory-test.invalid', apiKey: 'non-secret-test-fixture',
        models: [{ id: 'mock', name: 'Mock', reasoning: false, input: ['text'], contextWindow: 128000, maxTokens: 1024, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 } }],
        streamSimple(model, context) {
          captured.push(structuredClone(context.messages));
          const stream = new ai.AssistantMessageEventStream();
          const message = { role: 'assistant', api: model.api, provider: model.provider, model: model.id, timestamp: 1, stopReason: 'pending', content: [], usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } } };
          queueMicrotask(() => {
            stream.push({ type: 'start', partial: message });
            message.content.push({ type: 'text', text: '' });
            stream.push({ type: 'text_start', contentIndex: 0, partial: message });
            message.content[0].text = 'fixture';
            stream.push({ type: 'text_delta', contentIndex: 0, delta: 'fixture', partial: message });
            stream.push({ type: 'text_end', contentIndex: 0, content: 'fixture', partial: message });
            message.stopReason = 'stop';
            stream.push({ type: 'done', reason: 'stop', message });
            stream.end();
          });
          return stream;
        },
      }));
      pi.on('session_before_compact', (event) => ({ compaction: {
        summary: 'Fixture task summary', firstKeptEntryId: event.preparation.firstKeptEntryId,
        tokensBefore: event.preparation.tokensBefore,
      } }));
    }],
  });
  const oldAgent = process.env.PI_CODING_AGENT_DIR;
  process.env.PI_CODING_AGENT_DIR = f.agent;
  let session;
  try {
    await loader.reload();
    const errors = loader.getExtensions().errors;
    assert.deepEqual(errors, []);
    const manager = sdk.SessionManager.inMemory(f.a);
    manager.appendMessage({ role: 'user', content: 'Fixture prior work. '.repeat(1000), timestamp: 1 });
    ({ session } = await sdk.createAgentSession({
      cwd: f.a, agentDir: f.agent, resourceLoader: loader, settingsManager: settings, sessionManager: manager,
      tools: ['memory', 'memory_nested_probe'],
    }));
    const runtimeErrors = [];
    await session.bindExtensions({ onError: (error) => runtimeErrors.push(error) });
    const model = session.modelRuntime.getModel('memory-test', 'mock');
    assert.ok(model, JSON.stringify({ providers: session.modelRuntime.getRegisteredProviderIds(), error: session.modelRuntime.getError(), runtimeErrors }));
    await session.setModel(model);
    assert.ok(session.getCallableToolNames().includes('memory'));
    await session.prompt('Fixture first request');
    const first = captured.at(-1);
    assert.match(JSON.stringify(first), /SDK recall marker/);
    assert.ok(manager.getBranch().some((entry) => entry.type === 'message'
      && entry.message.role === 'system' && JSON.stringify(entry.message).includes('SDK recall marker')));
    const probe = session.agent.state.tools.find((tool) => tool.name === 'memory_nested_probe');
    await probe.execute('nested-test', {});

    await session.prompt('Fixture unchanged memory');
    const unchanged = captured.at(-1);
    assert.deepEqual(unchanged.slice(0, first.length), first);
    assert.equal(unchanged.filter((message) => message.role === 'system').length,
      first.filter((message) => message.role === 'system').length);

    writeFileSync(join(f.a, 'MEMORY.md'), 'SDK updated marker');
    await session.prompt('Fixture updated memory');
    const updated = captured.at(-1);
    assert.deepEqual(updated.slice(0, unchanged.length), unchanged);
    assert.equal(updated.filter((message) => message.role === 'system').length,
      unchanged.filter((message) => message.role === 'system').length + 1);
    assert.match(JSON.stringify(updated.slice(unchanged.length)), /SDK updated marker/);

    session.setActiveToolsByName(['memory']);
    await session.prompt('Fixture changed tools');
    const changedTools = captured.at(-1);
    assert.deepEqual(changedTools.slice(0, updated.length), updated);
    assert.ok(changedTools.slice(updated.length).some((message) => message.role === 'system'));
    await session.compact();
    assert.ok(manager.getBranch().some((entry) => entry.type === 'compaction'));
    await session.prompt('Fixture after compaction');
    assert.match(JSON.stringify(captured.at(-1)), /SDK updated marker/);
    assert.equal(JSON.stringify(captured.at(-1)).split('SDK updated marker').length - 1, 1);
    assert.deepEqual(runtimeErrors, []);
  } finally {
    session?.dispose();
    if (oldAgent === undefined) delete process.env.PI_CODING_AGENT_DIR;
    else process.env.PI_CODING_AGENT_DIR = oldAgent;
  }
});
