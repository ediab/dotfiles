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

/** Host key on the shared UI object: Pi's original setter/getter + inner factory. */
const UI_STATE = Symbol.for("pi.title-in-border.ui-state");

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
	width: number,
	name: string,
	borderColor: (text: string) => string,
): string | null {
	const lineWidth = visibleWidth(stripTerminalSequences(line));
	// Powerline chrome/fast paths render `" " + "─".repeat(width - 2)` (width - 1 cells); the
	// default editor renders a full-width rule. Accept both exact shapes only.
	const leading =
		lineWidth === width ? 0 : lineWidth === width - 1 ? 1 : undefined;
	if (leading === undefined) {
		return null;
	}
	const border = borderColor("─");
	// The rule run behind the decoration: pair `──`, space, label, space, and the rest are rules.
	// Cell budget: [indent][──][ ][label][ ][rules…≥1] must total lineWidth.
	const ruleRun = lineWidth - leading;
	let rest = ruleRun - 2 - 1 - 1; // minus pair and both separator spaces; ≥1 trailing rule stays
	if (rest < 1) {
		return null;
	}
	let label = name;
	const labelWidth = visibleWidth(label);
	const maxLabel = rest - 1;
	if (maxLabel < 4) {
		// Fewer than four cells for the name: keep the original line (plan's narrow fallback).
		return null;
	}
	if (labelWidth > maxLabel) {
		label = truncateToWidth(label, maxLabel, "…");
	}
	rest -= visibleWidth(label);
	if (rest < 1) {
		return null;
	}
	return (
		line.slice(0, leading) +
		border.repeat(2) +
		borderColor(` ${label} `) +
		border.repeat(rest)
	);
}

function isPlainRule(line: string): boolean {
	return /^ *─+$/.test(stripTerminalSequences(line));
}

function wrapFactory(
	inner: EditorFactory,
	getName: () => string | undefined,
): EditorFactory {
	return (tui, theme, keybindings) => {
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
			const decorated = decorateBorder(first, width, name, (text) =>
				borderColor.call(editor, text),
			);
			if (decorated === null) return lines;
			return [decorated, ...lines.slice(1)];
		};
		return editor;
	};
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

	// Reuse host originals across reloads, then drop stale state from old closures.
	const priorState = ui[UI_STATE] as UIState | undefined;
	const state: UIState = priorState ?? {
		originalSet,
		originalGet,
		inner: undefined,
	};

	// Each wrapper closes over its own reader, so a reloaded instance never consults
	// a stale closure from the previous one.
	const reader = () => pi.getSessionName();

	state.inner = undefined;
	ui[UI_STATE] = state;

	const remember = (factory: EditorFactory | undefined): void => {
		state.inner = factory;
		if (factory !== undefined) {
			state.originalSet(wrapFactory(factory, reader));
		}
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

	// Re-apply the inner factory we know about (or, on the very first install, whatever the
	// host currently has registered) so the wrapped factory is in place regardless of load order.
	remember(priorState ? priorState.inner : state.originalGet());
}

export default function titleInBorder(pi: ExtensionAPI): void {
	pi.on("session_start", (_event, ctx: ExtensionContext) => {
		if (ctx.mode !== "tui") {
			return;
		}
		installPatch(ctx.ui as unknown as Record<PropertyKey, unknown>, pi);
	});
}
