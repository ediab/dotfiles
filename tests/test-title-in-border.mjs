/**
 * Tests for pi/extensions/title-in-border.ts at the extension boundary.
 *
 * Loads the real TypeScript extension via jiti (as Pi's loader does), supplies a
 * minimal Pi API plus a shared UI object, records session_start, and emulates
 * editor registration with Powerline-style factories. Private helpers are not
 * imported; behavior is exercised through the public event/factory/render flow.
 *
 * Run:
 *   PI_PACKAGE_ROOT="$(npm root -g)/@earendil-works/pi-coding-agent" \
 *     node --test tests/test-title-in-border.mjs
 *
 * Requires jiti and @earendil-works/pi-tui from the Pi installation; no
 * dependencies are added to the dotfiles repo.
 */

import { createRequire } from "node:module";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import assert from "node:assert/strict";

const REPO_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const EXTENSION_PATH = join(
  REPO_ROOT,
  "pi",
  "extensions",
  "title-in-border.ts",
);

const packageRoot =
  process.env.PI_PACKAGE_ROOT ??
  join(
    process.env.npm_config_prefix ?? "/opt/homebrew/lib/node_modules",
    "@earendil-works/pi-coding-agent",
  );

for (const dir of [packageRoot, join(packageRoot, "node_modules", "jiti")]) {
  if (!existsSync(join(dir, "package.json"))) {
    console.error(
      `test-title-in-border: Pi installation not found at ${packageRoot}\n` +
        `Set PI_PACKAGE_ROOT to the @earendil-works/pi-coding-agent package directory.`,
    );
    process.exit(1);
  }
}

const require = createRequire(join(packageRoot, "package.json"));
const { createJiti } = require("jiti");

// Host packages resolved exactly as Pi's loader resolves them for extensions.
const piTuiEntry = join(
  packageRoot,
  "node_modules",
  "@earendil-works",
  "pi-tui",
  "dist",
  "index.js",
);
const piAgentEntry = join(
  packageRoot,
  "node_modules",
  "@earendil-works",
  "pi-agent-core",
  "dist",
  "index.js",
);
const piAiEntry = join(
  packageRoot,
  "node_modules",
  "@earendil-works",
  "pi-ai",
  "dist",
  "compat.js",
);
const typeboxEntry = require.resolve("typebox", { paths: [packageRoot] });

// Mirrors Pi's loader: fresh module cache per import, host packages resolved
// relative to the Pi package. virtualModules are only present in pi's bundled
// runtime; the unbundled dist tree resolves them from Pi's node_modules.
const jiti = createJiti(join(packageRoot, "dist", "index.js"), {
  moduleCache: false,
  fsCache: false, // pick up edits to the extension between runs; Pi itself relies on fresh reads
  alias: {
    "@earendil-works/pi-coding-agent": join(packageRoot, "dist", "index.js"),
    "@earendil-works/pi-tui": piTuiEntry,
    "@earendil-works/pi-agent-core": piAgentEntry,
    "@earendil-works/pi-ai": piAiEntry,
    "@earendil-works/pi-ai/compat": piAiEntry,
    typebox: typeboxEntry,
    "typebox/compile": typeboxEntry,
    "typebox/value": typeboxEntry,
    "@sinclair/typebox": typeboxEntry,
    "@sinclair/typebox/compile": typeboxEntry,
    "@sinclair/typebox/value": typeboxEntry,
  },
});
const loadExtension = () => jiti.import(EXTENSION_PATH, { default: true });

const { visibleWidth, stripTerminalSequences } = require(
  join(
    packageRoot,
    "node_modules",
    "@earendil-works",
    "pi-tui",
    "dist",
    "utils.js",
  ),
);

const NO_COLOR = (text) => `«${text}»`; // visible sentinel around colored spans
const stripSentinels = (line) =>
  stripTerminalSequences(line).replace(/[«»]/g, "");

function makeFakeEditor(extra = {}) {
  return {
    borderColor: NO_COLOR,
    render(width) {
      return ["─".repeat(width)];
    },
    ...extra,
  };
}

function makeUI(host = {}) {
  host.setCalls ??= [];
  const listeners = new Map();
  const ui = {
    setEditorComponent(factory) {
      host.setCalls.push(factory);
      host.editorFactory = factory;
    },
    getEditorComponent() {
      return host.editorFactory;
    },
    get __hostSetCalls() {
      return host.setCalls;
    },
    get __editorFactory() {
      return host.editorFactory;
    },
  };
  return { ui, listeners, host };
}

/** Minimal ExtensionAPI shape; only session_start + getSessionName are used. */
function makePi(name, uiBundle, { mode = "tui" } = {}) {
  const handlers = new Map();
  return {
    pi: {
      on(event, handler) {
        const list = handlers.get(event) ?? [];
        list.push(handler);
        handlers.set(event, list);
        return () => {
          const current = handlers.get(event) ?? [];
          handlers.set(
            event,
            current.filter((h) => h !== handler),
          );
        };
      },
      getSessionName: () => name(),
    },
    handlers,
    async emitSessionStart(reason = "startup") {
      const ctx = {
        mode,
        hasUI: mode === "tui",
        ui: uiBundle.ui,
      };
      for (const handler of handlers.get("session_start") ?? []) {
        await handler({ type: "session_start", reason }, ctx);
      }
    },
  };
}

/** Factory that behaves like Powerline's: chain the previous factory, override render. */
function makePowerlineFactory(track) {
  track.instances ??= [];
  return (tui, theme, keybindings) => {
    const inner = track.previousFactory?.(tui, theme, keybindings);
    const editor = makeFakeEditor();
    editor.isPowerline = true;
    editor.inner = inner;
    track.instances.push(editor);
    editor.render = (width) => {
      // Powerline chrome: rebuild line 0 as " " + rule(width - 2)
      const base = inner ? inner.render(width) : [" " + "─".repeat(width - 2)];
      return [" " + "─".repeat(width - 2), ...base.slice(1)];
    };
    return editor;
  };
}

async function freshExtension() {
  return await loadExtension();
}

test("module loads and default export is a function", async () => {
  const factory = await freshExtension();
  assert.equal(typeof factory, "function");
});

test("configuration keeps the requested powerline layout and cost display", () => {
  const settings = JSON.parse(
    readFileSync(join(REPO_ROOT, "pi", "settings.json"), "utf8"),
  );
  const title = JSON.parse(
    readFileSync(join(REPO_ROOT, "pi", "pi-title.jsonc"), "utf8"),
  );
  assert.equal(settings.powerline.placement, "below");
  assert.deepEqual(settings.powerline.layout.left, [
    "model",
    "thinking",
    "shell_mode",
    "path",
    "git",
    "queue",
    "context_pct",
    "cache_read",
    "cost",
  ]);
  assert.equal(settings.powerline.layout.left.includes("session"), false);
  assert.deepEqual(settings.powerline.cost, {
    subscriptionDisplay: "reported-cost",
    currency: "GBP",
  });
  assert.equal(title.maxTokens, 30);
  assert.equal(title.maxLength, 60);
});

test("decorates a plain border with the session title, preserving width and other lines", async () => {
  const factory = await freshExtension();
  let name = "Fix login flow";
  const { ui } = makeUI();
  const piBundle = makePi(() => name, { ui });
  factory(piBundle.pi);
  await piBundle.emitSessionStart();
  assert.equal((piBundle.handlers.get("session_start") ?? []).length, 1);

  // Extension with no prior factory: register through the patched setter.
  const track = { previousFactory: ui.getEditorComponent() };
  ui.setEditorComponent(makePowerlineFactory(track));
  const editor = ui.__editorFactory(NO_COLOR, {}, {});
  assert.equal(editor.isPowerline, true);

  // Powerline chrome line at width 60: " " + 58 rules = 59 cells.
  ui.setEditorComponent(makePowerlineFactory(track));
  const editor2 = ui.__editorFactory(NO_COLOR, {}, {});
  const lines = editor2.render(60);
  // Cells: indent(1) + pair(2) + " " + name(14) + " " + remaining rules(40) = 59.
  assert.equal(
    stripSentinels(lines[0]),
    " ── Fix login flow " + "─".repeat(40),
  );
  // visible width preserved (sentinels count as visible text; assert on the stripped line)
  assert.equal(visibleWidth(stripSentinels(lines[0])), 59);
  // The complete border content after the indent uses one border-color span.
  assert.equal(lines[0], ` «── Fix login flow ${"─".repeat(40)}»`);

  // Full-width rule (default editor shape, no leading indent):
  let defaultName = "Plain editor";
  const { ui: ui2 } = makeUI();
  const piBundle2 = makePi(() => defaultName, { ui: ui2 });
  factory(piBundle2.pi);
  await piBundle2.emitSessionStart();
  ui2.setEditorComponent(() => makeFakeEditor());
  const plainEditor = ui2.__editorFactory(NO_COLOR, {}, {});
  const plainLines = plainEditor.render(60);
  assert.equal(
    stripSentinels(plainLines[0]),
    "── Plain editor " + "─".repeat(44),
  );
  assert.equal(visibleWidth(stripSentinels(plainLines[0])), 60);
  // all other rendered lines remain unchanged
  ui.setEditorComponent(() =>
    makeFakeEditor({
      render(width) {
        return [" " + "─".repeat(width - 2), "middle line", "─".repeat(width)];
      },
    }),
  );
  const multi = ui.__editorFactory(NO_COLOR, {}, {}).render(60);
  assert.equal(multi[1], "middle line");
  assert.equal(multi[2], "─".repeat(60));
});

test("missing, blank, or control-only names return the original border", async () => {
  const factory = await freshExtension();
  const cases = [undefined, "", "   ", "\x07\x1b"];
  for (const value of cases) {
    let name = value;
    const { ui } = makeUI();
    const piBundle = makePi(() => name, { ui });
    factory(piBundle.pi);
    await piBundle.emitSessionStart();
    const track = { previousFactory: ui.getEditorComponent() };
    ui.setEditorComponent(makePowerlineFactory(track));
    const editor = ui.__editorFactory(NO_COLOR, {}, {});
    const lines = editor.render(50);
    assert.equal(
      lines[0],
      " " + "─".repeat(48),
      `case ${JSON.stringify(value)}`,
    );
  }
});

test("working/status text, scroll markers, and unknown first lines are unchanged", async () => {
  const factory = await freshExtension();
  let name = "Working session";
  const { ui } = makeUI();
  const piBundle = makePi(() => name, { ui });
  factory(piBundle.pi);
  await piBundle.emitSessionStart();

  // Working status embedded in the border (default editor, powerline off):
  // line 0 is borderColor('── ') + status + borderColor(' ────') — not a plain rule.
  const working = "«─«─ ⟳ working…« ────";
  ui.setEditorComponent(() =>
    makeFakeEditor({
      render(width) {
        return [working, "body"];
      },
    }),
  );
  const workingEditor = ui.__editorFactory(NO_COLOR, {}, {});
  assert.equal(workingEditor.render(60)[0], working);

  // Powerline scroll marker shape: " ↑───…" (its fast path builds this when scrolled).
  ui.setEditorComponent(() =>
    makeFakeEditor({
      render(width) {
        return [" ↑" + "─".repeat(58), "body"];
      },
    }),
  );
  const scrollEditor = ui.__editorFactory(NO_COLOR, {}, {});
  assert.equal(scrollEditor.render(60)[0], " ↑" + "─".repeat(58));

  // Arbitrary unknown first-line content.
  ui.setEditorComponent(() =>
    makeFakeEditor({
      render(width) {
        return ["??unknown??", "body"];
      },
    }),
  );
  const unknownEditor = ui.__editorFactory(NO_COLOR, {}, {});
  assert.equal(unknownEditor.render(60)[0], "??unknown??");

  // Empty render output passes through.
  ui.setEditorComponent(() =>
    makeFakeEditor({
      render(width) {
        return [];
      },
    }),
  );
  const emptyEditor = ui.__editorFactory(NO_COLOR, {}, {});
  assert.deepEqual(emptyEditor.render(60), []);
});

test("name changes between renders appear without reinstalling the editor", async () => {
  const factory = await freshExtension();
  let name = "First";
  const { ui } = makeUI();
  const piBundle = makePi(() => name, { ui });
  factory(piBundle.pi);
  await piBundle.emitSessionStart();
  const track = { previousFactory: ui.getEditorComponent() };
  ui.setEditorComponent(makePowerlineFactory(track));
  const editor = ui.__editorFactory(NO_COLOR, {}, {});
  assert.match(stripTerminalSequences(editor.render(60)[0]), /First/);
  const callsBefore = ui.__hostSetCalls.length;

  name = "Second";
  assert.match(stripTerminalSequences(editor.render(60)[0]), /Second/);
  assert.equal(ui.__hostSetCalls.length, callsBefore);
});

test("border color callback changes are picked up per render", async () => {
  const factory = await freshExtension();
  let name = "Colorful";
  let color = NO_COLOR;
  const { ui } = makeUI();
  const piBundle = makePi(() => name, { ui });
  factory(piBundle.pi);
  await piBundle.emitSessionStart();
  const track = { previousFactory: ui.getEditorComponent() };
  ui.setEditorComponent(makePowerlineFactory(track));
  const editor = ui.__editorFactory(NO_COLOR, {}, {});
  // Read borderColor at render time: mutate it and re-render.
  editor.borderColor = (text) => `[${text}]`;
  const lines = editor.render(60);
  assert.match(lines[0], /^ \[── Colorful ─+\]$/);
});

test("narrow widths fall back safely to the original border", async () => {
  const factory = await freshExtension();
  let name = "Title";
  const { ui } = makeUI();
  const piBundle = makePi(() => name, { ui });
  factory(piBundle.pi);
  await piBundle.emitSessionStart();
  const track = { previousFactory: ui.getEditorComponent() };
  ui.setEditorComponent(makePowerlineFactory(track));
  const editor = ui.__editorFactory(NO_COLOR, {}, {});
  // Powerline line at width w has w-1 cells; the fused look keeps the original line while
  // fewer than 4 cells remain for the name: no room at w <= 10, Title fits at 11.
  for (const width of [8, 9, 10]) {
    assert.equal(
      editor.render(width)[0],
      " " + "─".repeat(width - 2),
      `width ${width}`,
    );
  }
  // At width 11 the label truncates with an ellipsis and keeps one trailing rule.
  assert.match(stripSentinels(editor.render(11)[0]), /…/);
  // Wide enough: decorated.
  assert.match(stripTerminalSequences(editor.render(14)[0]), /Title/);
});

test("long titles truncate with an ellipsis and keep a trailing rule", async () => {
  const factory = await freshExtension();
  let name = "A very long session title that will not fit";
  const { ui } = makeUI();
  const piBundle = makePi(() => name, { ui });
  factory(piBundle.pi);
  await piBundle.emitSessionStart();
  const track = { previousFactory: ui.getEditorComponent() };
  ui.setEditorComponent(makePowerlineFactory(track));
  const editor = ui.__editorFactory(NO_COLOR, {}, {});
  const width = 40;
  const lines = editor.render(width);
  const stripped = stripSentinels(lines[0]);
  assert.equal(visibleWidth(stripped), width - 1);
  assert.match(stripped, /^ ── A very long .*… ─+$/);
  assert.match(stripped, /─$/);
});

test("unicode titles: CJK, emoji, combining marks; no injected control sequences", async () => {
  const factory = await freshExtension();
  for (const [name, frag] of [
    ["今日は良い天気です", "今日"],
    ["🚀 Launch day!! 🎉", "🚀"],
    ["café normalizer", "café"],
  ]) {
    let sessionName = name;
    const { ui } = makeUI();
    const piBundle = makePi(() => sessionName, { ui });
    factory(piBundle.pi);
    await piBundle.emitSessionStart();
    const track = { previousFactory: ui.getEditorComponent() };
    ui.setEditorComponent(makePowerlineFactory(track));
    const editor = ui.__editorFactory(NO_COLOR, {}, {});
    const width = 30;
    const lines = editor.render(width);
    assert.equal(
      visibleWidth(stripSentinels(lines[0])),
      width - 1,
      JSON.stringify(name),
    );
    assert.ok(
      stripSentinels(lines[0]).includes(frag),
      `${frag} visible for ${JSON.stringify(name)}`,
    );
    // No escape/control sequences injected beyond the sentinel color sentinels.
    assert.doesNotMatch(lines[0], /\x1b/);
  }
});

test("preserves the matched leading indent and visible width", async () => {
  const factory = await freshExtension();
  const { ui } = makeUI();
  const piBundle = makePi(() => "Four", { ui });
  factory(piBundle.pi);
  await piBundle.emitSessionStart();
  const original = "  " + "─".repeat(15);
  ui.setEditorComponent(() =>
    makeFakeEditor({
      render() {
        return [original, "body"];
      },
    }),
  );
  const line = ui.__editorFactory(NO_COLOR, {}, {}).render(80)[0];
  assert.equal(stripSentinels(line).slice(0, 2), "  ");
  assert.equal(visibleWidth(stripSentinels(line)), visibleWidth(original));
  assert.equal(stripSentinels(line), "  ── Four " + "─".repeat(7));
});

test("registration order: powerline first, extension second still decorates", async () => {
  const factory = await freshExtension();
  let name = "Order B";
  const { ui } = makeUI();
  // Register powerline BEFORE the extension's session_start.
  const track = { previousFactory: undefined };
  ui.setEditorComponent(makePowerlineFactory(track));
  const piBundle = makePi(() => name, { ui });
  factory(piBundle.pi);
  await piBundle.emitSessionStart();
  // Extension re-applies the currently registered (inner) factory.
  const editor = ui.__editorFactory(NO_COLOR, {}, {});
  assert.equal(editor.isPowerline, true);
  assert.match(stripTerminalSequences(editor.render(60)[0]), /Order B/);
});

test("repeated session_start immediately reapplies without double-wrapping", async () => {
  const factory = await freshExtension();
  let name = "Repeated";
  const { ui } = makeUI();
  const piBundle = makePi(() => name, { ui });
  factory(piBundle.pi);
  await piBundle.emitSessionStart();
  const powerlineFactory = makePowerlineFactory({
    previousFactory: ui.getEditorComponent(),
  });
  ui.setEditorComponent(powerlineFactory);
  const callsBefore = ui.__hostSetCalls.length;

  await piBundle.emitSessionStart();
  await piBundle.emitSessionStart();

  assert.equal(ui.__hostSetCalls.length, callsBefore + 2);
  assert.equal(ui.getEditorComponent(), powerlineFactory);
  const editor = ui.__editorFactory(NO_COLOR, {}, {});
  const stripped = stripSentinels(editor.render(80)[0]);
  assert.equal(stripped.split("Repeated").length - 1, 1);
});

test("later factory replacement swaps the inner factory without chaining", async () => {
  const factory = await freshExtension();
  let name = "Swapped";
  const { ui } = makeUI();
  const piBundle = makePi(() => name, { ui });
  factory(piBundle.pi);
  await piBundle.emitSessionStart();
  const firstTrack = { previousFactory: ui.getEditorComponent() };
  ui.setEditorComponent(makePowerlineFactory(firstTrack));
  const secondFactory = makePowerlineFactory({ previousFactory: undefined });
  ui.setEditorComponent(secondFactory);
  assert.equal(ui.getEditorComponent(), secondFactory);
  const editor = ui.__editorFactory(NO_COLOR, {}, {});
  const stripped = stripTerminalSequences(editor.render(60)[0]);
  assert.equal(stripped.split("Swapped").length - 1, 1);
});

test("autocomplete-driven re-registration keeps decoration and passes through the getter", async () => {
  const factory = await freshExtension();
  let name = "Autocomplete";
  const { ui } = makeUI();
  const piBundle = makePi(() => name, { ui });
  factory(piBundle.pi);
  await piBundle.emitSessionStart();
  const track = { previousFactory: ui.getEditorComponent() };
  const powerlineFactory = makePowerlineFactory(track);
  ui.setEditorComponent(powerlineFactory);
  // Powerline re-registers the same factory on first keystroke:
  ui.setEditorComponent(powerlineFactory);
  assert.equal(ui.getEditorComponent(), powerlineFactory);
  const editor = ui.__editorFactory(NO_COLOR, {}, {});
  assert.match(stripTerminalSequences(editor.render(60)[0]), /Autocomplete/);
});

test("powerline off/on cycles keep working without double decoration", async () => {
  const factory = await freshExtension();
  let name = "Toggle";
  const { ui } = makeUI();
  const piBundle = makePi(() => name, { ui });
  factory(piBundle.pi);
  await piBundle.emitSessionStart();
  const track = { previousFactory: ui.getEditorComponent() };
  const powerlineFactory = makePowerlineFactory(track);
  // On:
  ui.setEditorComponent(powerlineFactory);
  // Off: powerline clears the factory.
  ui.setEditorComponent(undefined);
  assert.equal(ui.getEditorComponent(), undefined);
  // On again:
  ui.setEditorComponent(powerlineFactory);
  const editor = ui.__editorFactory(NO_COLOR, {}, {});
  const stripped = stripTerminalSequences(editor.render(60)[0]);
  assert.equal(stripped.split("Toggle").length - 1, 1);
});

test("reload with a new UI binding unwraps the prior wrapper", async () => {
  const factory1 = await freshExtension();
  let staleReaderThrows = false;
  const host = {};
  const { ui: ui1 } = makeUI(host);
  const piBundle1 = makePi(() => {
    if (staleReaderThrows) throw new Error("stale reader");
    return "Before reload";
  }, { ui: ui1 });
  factory1(piBundle1.pi);
  await piBundle1.emitSessionStart();
  const powerlineFactory = makePowerlineFactory({
    previousFactory: ui1.getEditorComponent(),
  });
  ui1.setEditorComponent(powerlineFactory);
  assert.match(
    stripSentinels(ui1.__editorFactory(NO_COLOR, {}, {}).render(60)[0]),
    /Before reload/,
  );

  staleReaderThrows = true;
  const { ui: ui2 } = makeUI(host);
  const factory2 = await freshExtension();
  const piBundle2 = makePi(() => "After reload", { ui: ui2 });
  factory2(piBundle2.pi);
  await piBundle2.emitSessionStart("reload");

  assert.equal(ui2.getEditorComponent(), powerlineFactory);
  const stripped = stripSentinels(
    ui2.__editorFactory(NO_COLOR, {}, {}).render(60)[0],
  );
  assert.equal(stripped.split("After reload").length - 1, 1);
  assert.doesNotMatch(stripped, /Before reload/);

  // Title extension first, then Powerline re-registering on the new binding.
  const replacementPowerline = makePowerlineFactory({
    previousFactory: ui2.getEditorComponent(),
  });
  ui2.setEditorComponent(replacementPowerline);
  assert.equal(ui2.getEditorComponent(), replacementPowerline);
  const replaced = stripSentinels(
    ui2.__editorFactory(NO_COLOR, {}, {}).render(60)[0],
  );
  assert.equal(replaced.split("After reload").length - 1, 1);
});

test("a reloaded extension instance uses its own session-name reader", async () => {
  const factory = await freshExtension();
  let name = "Before reload";
  const { ui } = makeUI();
  const piBundle1 = makePi(() => name, { ui });
  factory(piBundle1.pi);
  await piBundle1.emitSessionStart();
  const track = { previousFactory: ui.getEditorComponent() };
  ui.setEditorComponent(makePowerlineFactory(track));
  let editor = ui.__editorFactory(NO_COLOR, {}, {});
  assert.match(stripTerminalSequences(editor.render(60)[0]), /Before reload/);

  // Reload: a NEW extension module instance with its OWN pi object/session reader;
  // powerline re-registers its factory during session_start, as in real pi.
  name = "After reload";
  const factory2 = await freshExtension();
  let reloadedName = "Reloaded name";
  const piBundle2 = makePi(() => reloadedName, { ui });
  factory2(piBundle2.pi);
  await piBundle2.emitSessionStart("reload");
  ui.setEditorComponent(makePowerlineFactory(track));
  editor = ui.__editorFactory(NO_COLOR, {}, {});
  const stripped = stripSentinels(editor.render(60)[0]);
  assert.match(stripped, /Reloaded name/);
  assert.doesNotMatch(stripped, /After reload/);
});

test("obsolete session-name reader that throws is not consulted after reload", async () => {
  const factory = await freshExtension();
  let throwingReader = true;
  const { ui } = makeUI();
  const piBundle1 = makePi(
    () => {
      if (throwingReader) throw new Error("stale ctx");
      return "old name";
    },
    { ui },
  );
  factory(piBundle1.pi);
  await piBundle1.emitSessionStart();
  const track = { previousFactory: ui.getEditorComponent() };
  ui.setEditorComponent(makePowerlineFactory(track));
  let editor = ui.__editorFactory(NO_COLOR, {}, {});

  // Reload with a working reader. Reapplication must happen during session_start,
  // before Powerline has another chance to register its factory.
  const factory2 = await freshExtension();
  const piBundle2 = makePi(() => "Fresh", { ui });
  factory2(piBundle2.pi);
  await piBundle2.emitSessionStart("reload");
  editor = ui.__editorFactory(NO_COLOR, {}, {});
  assert.match(stripSentinels(editor.render(60)[0]), /Fresh/);
});

test("reload reuses the same underlying factory through the shared UI object", async () => {
  const factory = await freshExtension();
  const { ui } = makeUI();
  const piBundle1 = makePi(() => "One", { ui });
  factory(piBundle1.pi);
  await piBundle1.emitSessionStart();
  const track = { previousFactory: ui.getEditorComponent() };
  ui.setEditorComponent(makePowerlineFactory(track));
  const powerlineFactory = ui.getEditorComponent();

  const factory2 = await freshExtension();
  const piBundle2 = makePi(() => "Two", { ui });
  factory2(piBundle2.pi);
  await piBundle2.emitSessionStart("reload");
  // Powerline re-registers the same factory on session_start; the extension reuses it.
  ui.setEditorComponent(powerlineFactory);
  assert.equal(ui.getEditorComponent(), powerlineFactory);
  const editor = ui.__editorFactory(NO_COLOR, {}, {});
  assert.match(stripTerminalSequences(editor.render(60)[0]), /Two/);
});

test("non-TUI contexts are not patched; setEditorComponent stays host", async () => {
  const factory = await freshExtension();
  let name = "Print mode";
  const { ui } = makeUI();
  const piBundle = makePi(() => name, { ui }, { mode: "print" });
  factory(piBundle.pi);
  await piBundle.emitSessionStart();
  const anyFactory = makePowerlineFactory({ previousFactory: undefined });
  ui.setEditorComponent(anyFactory);
  // Host setter stored it directly; getEditorComponent is the host one.
  assert.equal(ui.__editorFactory, anyFactory);
  const editor = ui.__editorFactory(NO_COLOR, {}, {});
  assert.doesNotMatch(
    stripTerminalSequences(editor.render(60)[0]),
    /Print mode/,
  );
});

test("setEditorComponent(undefined) forwards to the host without installing a fallback", async () => {
  const factory = await freshExtension();
  let name = "Cleared";
  const { ui } = makeUI();
  const piBundle = makePi(() => name, { ui });
  factory(piBundle.pi);
  await piBundle.emitSessionStart();
  ui.setEditorComponent(undefined);
  assert.equal(ui.__editorFactory, undefined);
  assert.equal(ui.getEditorComponent(), undefined);
  // Host setter received the undefined pass-through (it always does through the patch).
  assert.equal(ui.__hostSetCalls[ui.__hostSetCalls.length - 1], undefined);
});

test("wrapped editor keeps instance methods, callbacks, and autocomplete behavior", async () => {
  const factory = await freshExtension();
  let name = "Methods";
  const { ui } = makeUI();
  const piBundle = makePi(() => name, { ui });
  factory(piBundle.pi);
  await piBundle.emitSessionStart();
  const submitted = [];
  const editorExtras = {
    getText: () => "draft text",
    setText: (t) => (editorExtras.__text = t),
    handleInput: (data) => (editorExtras.__input = data),
    setAutocompleteProvider: (p) => (editorExtras.__provider = p),
    onSubmit: undefined,
  };
  const track = { previousFactory: ui.getEditorComponent() };
  ui.setEditorComponent((tui, theme, keybindings) =>
    makeFakeEditor(editorExtras),
  );
  const editor = ui.__editorFactory(NO_COLOR, {}, {});
  assert.equal(editor.getText(), "draft text");
  editor.setText("new");
  assert.equal(editorExtras.__text, "new");
  editor.handleInput("x");
  assert.equal(editorExtras.__input, "x");
  editor.setAutocompleteProvider("PROVIDER");
  assert.equal(editorExtras.__provider, "PROVIDER");
  // render still decorates: wrap applied to the base editor render only.
  // (This editor's base render is the plain rule.)
  assert.match(stripTerminalSequences(editor.render(60)[0]), /Methods/);
});

test("render receiver is preserved: methods see the real editor instance", async () => {
  const factory = await freshExtension();
  let name = "Receiver";
  const { ui } = makeUI();
  const piBundle = makePi(() => name, { ui });
  factory(piBundle.pi);
  await piBundle.emitSessionStart();
  const seen = [];
  ui.setEditorComponent(() => {
    const editor = makeFakeEditor({
      getOwn() {
        return seen.push("called") && "self";
      },
      render(width) {
        // `this` must be the editor instance (bound original render).
        this.getOwn();
        return [" " + "─".repeat(width - 2)];
      },
    });
    return editor;
  });
  const editor = ui.__editorFactory(NO_COLOR, {}, {});
  editor.render(60);
  assert.equal(seen.length, 1);
});
