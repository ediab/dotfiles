/**
 * title-in-border — show the pi-title session name in the editor's top border.
 *
 * Complements pi-powerline-footer: Powerline rebuilds the editor's top border
 * inside its own render() and discards renderTopBorder(), so the title is
 * applied to the final rendered line instead. All other border content —
 * working status, scroll markers, unknown chrome — is left unchanged, and
 * the footer keeps its remaining segments (the session segment is removed
 * from settings by this feature).
 *
 * Intercepts ctx.ui.setEditorComponent/getEditorComponent on the shared
 * extension UI context during session_start in TUI mode, wrapping each
 * registered factory. The wrapper only overrides the instance's render()
 * to replace a plain horizontal rule with `── title ───` when a session
 * name is set.
 */

import type {
	ExtensionAPI,
	ExtensionContext,
	EditorFactory,
} from "@earendil-works/pi-coding-agent";
import type { EditorComponent } from "@earendil-works/pi-tui";
import {
	stripTerminalSequences,
	truncateToWidth,
	visibleWidth,
} from "@earendil-works/pi-tui";

/** Host key on one bound UI object: Pi's original setter/getter + inner factory. */
const UI_STATE = Symbol.for("pi.title-in-border.ui-state");
/** Factory key that lets a new UI binding remove a wrapper left by the prior binding. */
const WRAPPED_FACTORY = Symbol.for("pi.title-in-border.wrapped-factory");

interface UIState {
	/** setEditorComponent/getEditorComponent exactly as the host provided them. */
	originalSet: (factory: EditorFactory | undefined) => void;
	originalGet: () => EditorFactory | undefined;
	/** Unwrapped factory currently registered through the host setter. */
	inner: EditorFactory | undefined;
}

/** Strip ANSI/OSC/other terminal sequences, control chars, collapse whitespace, trim. */
function sanitizeName(raw: string): string {
	return (
		stripTerminalSequences(raw)
			.replace(/[\u0000-\u001f\u007f-\u009f]/g, " ")
			.replace(/\s+/g, " ")
			.trim()
	);
}

/** Rebuild a plain top-border rule line as `── title ───`, or null to keep it. */
function decorateBorder(
	line: string,
	name: string,
	borderColor: (text: string) => string,
): string | null {
	const match = /^( *)(─+)$/.exec(stripTerminalSequences(line));
	if (!match) {
		return null;
	}
	const [, indent, rules] = match;
	// Cell budget within the rule run: [──][ ][label][ ][rules…≥1].
	let rest = visibleWidth(rules) - 2 - 1 - 1;
	const maxLabel = rest - 1;
	if (maxLabel < 4) {
		return null;
	}
	let label = name;
	if (visibleWidth(label) > maxLabel) {
		label = truncateToWidth(label, maxLabel, "…");
	}
	rest -= visibleWidth(label);
	if (rest < 1) {
		return null;
	}
	return indent + borderColor(`── ${label} ${"─".repeat(rest)}`);
}

function isPlainRule(line: string): boolean {
	return /^ *─+$/.test(stripTerminalSequences(line));
}

function unwrapFactory(factory: EditorFactory): EditorFactory {
	let inner = factory;
	const seen = new Set<EditorFactory>();
	while (!seen.has(inner)) {
		seen.add(inner);
		const wrapped = (
			inner as EditorFactory & { [WRAPPED_FACTORY]?: EditorFactory }
		)[WRAPPED_FACTORY];
		if (!wrapped) break;
		inner = wrapped;
	}
	return inner;
}

function wrapFactory(
	inner: EditorFactory,
	getName: () => string | undefined,
): EditorFactory {
	const wrapped: EditorFactory = (tui, theme, keybindings) => {
		const editor: EditorComponent = inner(tui, theme, keybindings);
		const originalRender = editor.render.bind(editor);
		editor.render = (width: number): string[] => {
			const lines = originalRender(width);
			if (
				!Array.isArray(lines) ||
				lines.length === 0 ||
				typeof lines[0] !== "string"
			) {
				return lines;
			}
			const first = lines[0];
			const raw = getName();
			const name = raw === undefined ? undefined : sanitizeName(raw);
			if (!name || !isPlainRule(first)) {
				return lines;
			}
			const borderColor = (editor as { borderColor?: (text: string) => string })
				.borderColor;
			if (typeof borderColor !== "function") {
				return lines;
			}
			const decorated = decorateBorder(first, name, (text) =>
				borderColor.call(editor, text),
			);
			if (decorated === null) return lines;
			return [decorated, ...lines.slice(1)];
		};
		return editor;
	};
	Object.defineProperty(wrapped, WRAPPED_FACTORY, { value: inner });
	return wrapped;
}

function installPatch(
	ui: Record<PropertyKey, unknown>,
	pi: ExtensionAPI,
): void {
	const originalSet = ui.setEditorComponent as (
		factory: EditorFactory | undefined,
	) => void;
	const originalGet = ui.getEditorComponent as () => EditorFactory | undefined;
	if (
		typeof originalSet !== "function" ||
		typeof originalGet !== "function" ||
		typeof pi.getSessionName !== "function"
	) {
		return;
	}

	// Pi shares one mutable object within a binding but creates a new object when
	// extensions are rebound. Reuse same-object host methods and unwrap a factory
	// carried over through Pi's stable editor registration on a fresh binding.
	const priorState = ui[UI_STATE] as UIState | undefined;
	const state: UIState = priorState ?? {
		originalSet,
		originalGet,
		inner: undefined,
	};
	const currentInner = priorState?.inner ?? state.originalGet();
	const reader = () => pi.getSessionName();
	ui[UI_STATE] = state;

	const remember = (factory: EditorFactory): void => {
		const inner = unwrapFactory(factory);
		state.inner = inner;
		state.originalSet(wrapFactory(inner, reader));
	};

	ui.setEditorComponent = (factory: EditorFactory | undefined): void => {
		if (factory === undefined) {
			state.inner = undefined;
			state.originalSet(undefined);
			return;
		}
		remember(factory);
	};

	ui.getEditorComponent = (): EditorFactory | undefined => state.inner;

	// Re-apply immediately so repeated starts and either extension load order work.
	if (currentInner !== undefined) {
		remember(currentInner);
	}
}

export default function titleInBorder(pi: ExtensionAPI): void {
	pi.on("session_start", (_event, ctx: ExtensionContext) => {
		if (ctx.mode !== "tui") {
			return;
		}
		installPatch(ctx.ui as unknown as Record<PropertyKey, unknown>, pi);
	});
}
