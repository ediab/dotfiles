import { createHash, randomUUID } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import {
  closeSync, constants, fstatSync, fsyncSync, lstatSync, mkdirSync,
  openSync, readFileSync, readdirSync, realpathSync, renameSync,
  unlinkSync, writeFileSync,
} from 'node:fs';
import { dirname, isAbsolute, join, resolve } from 'node:path';

export const revision = (text) => createHash('sha256').update(text).digest('hex');

function stat(path) {
  try { return lstatSync(path); }
  catch (error) { if (error.code === 'ENOENT') return null; throw error; }
}

function directory(path, create = false) {
  const info = stat(path);
  if (info) {
    if (!info.isDirectory() || info.isSymbolicLink()) throw new Error(`Not a real directory: ${path}`);
  } else if (create) {
    try { mkdirSync(path, { mode: 0o700 }); }
    catch (error) {
      if (error.code !== 'EEXIST') throw error;
      directory(path);
    }
  }
  return Boolean(info) || create;
}

export function projectRoot(path, cwd = process.cwd(), explicit = false) {
  const input = resolve(cwd, path);
  if (!stat(input)) throw new Error(`Project path does not exist: ${input}`);
  const canonical = realpathSync.native(input);
  const info = stat(canonical);
  const start = info.isDirectory() ? canonical : dirname(canonical);
  let root;
  try {
    root = execFileSync('git', ['-C', start, 'rev-parse', '--show-toplevel'], {
      encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], timeout: 5000,
      env: { ...process.env, LC_ALL: 'C', GIT_DIR: undefined, GIT_WORK_TREE: undefined, GIT_COMMON_DIR: undefined },
    }).trim();
  } catch (error) {
    if (!String(error.stderr).includes('not a git repository')) throw error;
    if (!explicit) return null;
    if (!info.isDirectory()) throw new Error('Select a directory for a non-Git project');
    root = start;
  }
  return realpathSync.native(root);
}

function handoffName(name) {
  if (typeof name !== 'string' || !/^[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}$/.test(name)) {
    throw new Error('Handoff name must be 1–80 letters, digits, underscores or hyphens, starting with a letter or digit');
  }
  return name;
}

export class MemoryStore {
  constructor(agentDir) {
    this.agentDir = realpathSync(agentDir);
    this.base = join(this.agentDir, 'memory');
  }

  checkoutDir(root) { return join(this.base, revision(root)); }

  privateDirs(root, create = false) {
    const paths = [this.base, this.checkoutDir(root)];
    for (const path of paths) if (!directory(path, create)) return false;
    return true;
  }

  target(root, layer, name) {
    if (!isAbsolute(root) || realpathSync(root) !== root || !stat(root)?.isDirectory()) {
      throw new Error('Project root must be a canonical directory');
    }
    if (layer === 'project') return join(root, 'MEMORY.md');
    if (!['private', 'handoff'].includes(layer)) throw new Error(`Unknown memory layer: ${layer}`);
    this.privateDirs(root);
    if (layer === 'private') return join(this.checkoutDir(root), 'MEMORY.md');
    const folder = join(this.checkoutDir(root), 'handoffs');
    if (this.privateDirs(root)) directory(folder);
    return join(folder, `${handoffName(name)}.md`);
  }

  read(root, layer, name) {
    const path = this.target(root, layer, name);
    const info = stat(path);
    if (!info) return { layer, name, path, exists: false, content: '', revision: 'missing' };
    if (!info.isFile() || info.isSymbolicLink()) throw new Error(`Memory must be a regular file, not a link: ${path}`);
    const fd = openSync(path, constants.O_RDONLY | constants.O_NOFOLLOW);
    let content;
    try {
      if (!fstatSync(fd).isFile()) throw new Error(`Memory must be a regular file: ${path}`);
      content = readFileSync(fd, 'utf8');
    } finally { closeSync(fd); }
    return { layer, name, path, exists: true, content, revision: revision(content) };
  }

  listHandoffs(root) {
    if (!this.privateDirs(root)) return [];
    const folder = join(this.checkoutDir(root), 'handoffs');
    if (!directory(folder)) return [];
    return readdirSync(folder, { withFileTypes: true })
      .filter((entry) => entry.isFile() && /^[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}\.md$/.test(entry.name))
      .map((entry) => entry.name.slice(0, -3)).sort();
  }

  save(root, layer, name, content, expectedRevision) {
    if (typeof content !== 'string' || typeof expectedRevision !== 'string') {
      throw new Error('Save requires content and the revision returned by read ("missing" for a new file)');
    }
    const path = this.target(root, layer, name);
    if (layer !== 'project') {
      // Private memory must stay outside repositories, even if the agent directory was relocated.
      if (projectRoot(this.agentDir)) throw new Error('Private Pi agent directory is inside a Git repository');
      this.privateDirs(root, true);
      if (layer === 'handoff') directory(dirname(path), true);
    }
    const lockPath = `${path}.lock`;
    let lock;
    try { lock = openSync(lockPath, 'wx', 0o600); }
    catch (error) {
      if (error.code === 'EEXIST') throw new Error(`Memory is busy: ${lockPath}. Retry after its owner finishes; never remove a live writer's lock.`);
      throw error;
    }
    const temp = `${path}.${randomUUID()}.tmp`;
    try {
      writeFileSync(lock, `${process.pid}\n`);
      const before = this.read(root, layer, name);
      if (before.revision !== expectedRevision) throw new Error('Memory changed since your read; read again and merge before saving');
      if (layer !== 'project') {
        const metadata = join(this.checkoutDir(root), 'checkout.json');
        const info = stat(metadata);
        if (info && !info.isFile()) throw new Error(`Checkout metadata must be a regular file: ${metadata}`);
        const fd = openSync(metadata, constants.O_WRONLY | constants.O_CREAT | constants.O_TRUNC | constants.O_NOFOLLOW, 0o600);
        try { writeFileSync(fd, `${JSON.stringify({ root })}\n`); }
        finally { closeSync(fd); }
      }
      const fd = openSync(temp, 'wx', layer === 'project' ? (stat(path)?.mode & 0o777) || 0o644 : 0o600);
      try { writeFileSync(fd, content); fsyncSync(fd); }
      finally { closeSync(fd); }
      // ponytail: locks protect package writers, not editors; recheck just before rename to catch most external edits.
      if (this.read(root, layer, name).revision !== expectedRevision) throw new Error('Memory changed during save; read again and merge');
      renameSync(temp, path);
      return this.read(root, layer, name);
    } finally {
      try {
        try { unlinkSync(temp); } catch (error) { if (error.code !== 'ENOENT') throw error; }
      } finally {
        closeSync(lock);
        unlinkSync(lockPath);
      }
    }
  }

  search(root, query) {
    if (typeof query !== 'string' || !query.trim()) throw new Error('Search requires a non-empty literal query');
    const records = [this.read(root, 'project'), this.read(root, 'private'),
      ...this.listHandoffs(root).map((name) => this.read(root, 'handoff', name))];
    const matches = [];
    let total = 0;
    for (const record of records) {
      for (const [index, text] of record.content.split('\n').entries()) {
        if (!text.toLowerCase().includes(query.toLowerCase())) continue;
        total++;
        if (matches.length < 100) matches.push({ path: record.path, line: index + 1, text });
      }
    }
    return { matches, total, truncated: total > matches.length };
  }
}
