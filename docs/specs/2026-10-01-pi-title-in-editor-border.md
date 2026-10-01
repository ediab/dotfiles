# Pi title in editor top border

Spec from a brainstorm on 2026-10-01; revised the same day after a source review against pi 0.99.2,
pi-powerline-footer 0.19.0, and pi-title 0.1.7. Status: agreed direction, not yet implemented.

## Idea and purpose

Move the pi-title session title from the Powerline row into the editor box's top border line,
Claude Code style. Keep Powerline below the editor, with all its other segments unchanged:

```
── Session title ─────────────────────────────────
  > prompt here
─────────────────────────────────────────────────
  model ❯ thinking ❯ path ❯ git ❯ …
```

Today Powerline's `session` segment displays the title inside pi. This change moves it into
the editor's top border instead of duplicating it above and below the input.

Herdr captures the terminal title, but that does not imply its visible tab or pane label uses
it. Updating Herdr labels is outside this change; leave Herdr behavior unchanged.

## Who uses it and what they do

The owner, running pi in terminals (mostly herdr panes). They open a session, glance at the
editor, and know which work they are in without checking tab titles. Title generation itself
is untouched: pi-title keeps doing what it does.

## Why the obvious approach fails

Overriding `CustomEditor.renderTopBorder` does not work with pi-powerline-footer, which the owner
always runs:

- Powerline overrides `render` on its editor instance and rebuilds line 0 itself as
  `" " + "─".repeat(width - 2)` (`index.ts` ~3392), on both its chrome and fast-render paths
  (both on by default). `renderTopBorder` output is discarded.
- Powerline does not render a previously registered editor; it reads `getEditorComponent()` only
  to pass autocomplete through. An editor registered before powerline is dropped.
- Powerline re-registers its own factory on every `session_start` and on the first keystroke when
  no autocomplete provider is installed yet (`index.ts` ~3373). Either replaces a one-time wrapper.

## Smallest useful version

One new file: `dotfiles/pi/extensions/title-in-border.ts` (`~/.pi/agent/extensions`
symlinks to that directory), plus one settings change. No new settings, commands, or config UI.

In `dotfiles/pi/settings.json`, remove `"session"` from `powerline.layout.left`. Keep
`powerline.placement: "below"` and every other segment, its order, and its options unchanged.
Do not change pi-title's title generation or terminal-title behavior.

1. **Decorate the rendered output, not `renderTopBorder`.** The wrapper factory calls the inner
   factory, then overrides `render` on the returned instance. Powerline installs its own override
   inside its factory, so ours always runs last. After rendering, inspect `lines[0]`:
   - Plain border (ANSI-stripped, matches `^ *─+$`): rebuild it as `── title ───` with the same
     leading indent and the same visible width.
   - Anything else — pi's embedded working status, `↑ N more`, powerline's `↑───` scroll marker,
     unknown content — return unchanged.
2. **Wrap every registration.** `ctx.ui` is one shared, mutable object across extensions
   (`ExtensionRunner.uiContext`). On each `session_start`, replace on that object:
   - `setEditorComponent(f)`: remember `f` as the inner factory, then call pi's original setter
     with `wrap(f)`.
   - `getEditorComponent()`: return the inner factory, never the wrapper, so powerline's chaining
     cannot double-wrap.
   - Then re-apply the current inner factory through the patched setter.

   This covers powerline's re-registrations, its first-keystroke reset, and `/powerline` off/on,
   and makes extension load order irrelevant.
3. **Survive `/reload`.** Store pi's original setter/getter and the current inner factory on the
   `ui` object under a `Symbol.for(...)` key. A reloaded extension instance re-patches from the
   stored originals instead of stacking on a stale closure from the old instance.
4. **No factory, no title.** `setEditorComponent(undefined)` passes through unwrapped and pi
   restores its default editor. A fallback `CustomEditor` would lose up-arrow prompt history
   (stored per editor instance; pi does not migrate it on swap). Since powerline is always on,
   the cost is "no title while powerline is disabled".

Rendering details:

- Read `pi.getSessionName()` on every render. `setSessionName` emits `session_info_changed`, and
  interactive mode responds with `requestRender()`, so pi-title updates and `/title set …` appear
  on the next frame with no event hooks and no caching.
- Sanitize the title: strip ANSI and control characters, collapse whitespace, trim. Empty after
  sanitizing counts as no title.
- Color the whole line with the editor instance's `borderColor` read at render time. Pi assigns it
  after the factory returns and changes it with thinking level and bash mode.
- Layout: `── ` + label + ` ` + `─` × rest. Truncate the label with `…` to fit, keeping at least
  one trailing `─`. If fewer than 4 cells remain for the label, leave the border unchanged.

## Explicit exclusions

- Title only: no model, git, cost, or context segments in the border
- The pi-powerline-footer row stays below the editor (`powerline.placement: "below"` is already
  set); only its `session` segment is removed, with all other segments unchanged
- No duplicate title in Powerline, including its overflow or secondary row
- Title generation and terminal-title behavior untouched
- Herdr behavior unchanged; making its visible tab/pane labels follow the title is out of scope
- Bottom border stays plain
- No colors beyond the editor's current border color
- No title when no editor factory is registered (see step 4)

## Concrete success examples

1. Send one prompt in a fresh session; pi-title generates a name; the editor's plain top border
   immediately reads `── Session title ──────`. Powerline remains below the editor with the same
   other segments and no title or session-ID fallback.
2. `/title set Foo` updates the plain top border to `── Foo ──────` on the next render. After
   `/reload`, the title still appears only in that border, not in Powerline.
3. A brand-new session with no name shows the plain border, byte-for-byte identical to today,
   and no session segment in Powerline. While pi is working or the prompt scrolls, any border
   content pi or Powerline puts there takes precedence over the title.

## Verification

Manual, with powerline on unless noted:

- Fresh session: plain border before naming; title appears after pi-title names it, never in
  Powerline; no session-ID fallback in Powerline before naming
- Footer layout: Powerline stays below the editor; every non-session segment retains its order
  and options; no title appears in overflow or the secondary row on narrow terminals
- First keystroke in a fresh session: title survives powerline's autocomplete re-registration
- Bash mode (`$` prompt): title still shown, border color follows bash mode
- `/title set Foo`, then a long title in a ~20-column terminal: truncation with `…`, then fallback
  to the plain border when too narrow
- `/reload`, `/resume`, `/new`: title tracks the active session, no double-wrapping or duplicate
  title in Powerline
- Herdr behavior and pi-title generation/terminal-title behavior remain unchanged; visible
  Herdr label updates are not an acceptance criterion
- `/powerline` off: plain default editor, no title; `/powerline` on: title returns
- Powerline off at startup: plain default editor, working status still embedded in its border
- Multi-line prompt that scrolls: scroll marker shown instead of the title

## Decisions and known risks

- Chose the exact fused look (this spec) over the zero-code alternative (title-only powerline
  bar placed above the editor)
- Accepted: this depends on undocumented pi internals — that `ctx.ui` is a single shared,
  mutable object, and that editor instances expose an overridable `render` — and may need
  touch-ups after pi or powerline updates
- Accepted: the "plain border" check is string-shape based; if powerline changes its border
  format, the title silently disappears rather than corrupting the line
- Follow-up: file an upstream request for a supported hook (a pi editor-border decoration API, or
  a top-border label in pi-powerline-footer) and delete this extension if one lands
