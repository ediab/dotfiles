---
name: web-design
description: >-
  Build, restyle, or polish web UI with deliberate choices grounded in the
  product's subject: visible hierarchy, disciplined typography, spacing,
  and color, held to accessibility and responsive quality bars, and verified
  in a rendered browser layout before reporting done. Use when a task builds
  or changes web pages, components, dashboards, or landing pages rather than
  backend logic, CLI tooling, or throwaway design-question prototypes.
---

Designing web UI is a sequence of verifiable commitments, not a vibe. This
skill covers the three phases that repeat on every web project — ground,
build, verify — and the quality bars that survive between them. The single
rule that precedes them: every visual choice traces to what the product is
for. A trading dashboard, a pediatric clinic site, and a flea-market listing
page have genuinely different correct answers for the same CSS properties.

## Ground before styling

Confirm the design brief exists before writing styles. For each of these,
state it from the user's request or the surrounding project; ask only for
the one that neither source supplies:

- **Product and audience** — what this is, and who uses it. An internal ops
  tool for three analysts and a public marketing page for first-time
  visitors make opposite density and polish trades.
- **Screen's job** — the one thing a visitor must accomplish here. Everything
  downstream ranks below that action.
- **Where this lives** — the route, component folder, and who else renders
  nearby. Start from the project, from the design surface.

Then read before building. Check the framework and the CSS approach —
Tailwind, CSS modules, styled-components, plain sheets — the component
library and design tokens that already exist, and the sibling screens a
visitor walks through to reach this one. Extend the established system by
default; introduce a new pattern only when the existing one cannot express
what the screen needs, and say so when that happens. A redesign the user
never asked for is a defect; scope to the requested surface.

Completion: you can name the product, the audience, the screen's job, and
the system you are building inside, before any CSS changes.

## Build: hierarchy first, then surfaces

Design the ranking before the pixels. Answer: what is the single most
important element on this screen, and what does the user read or touch
first, second, third? Make the answer visible:

- **One primary action per view**, carried by the most weight (filled
  button). Secondary actions step down visibly — outline, then text link.
- **Weight is earned**: typeface size, weight, contrast against the
  background, and surrounding space are the levers; don't add weight with
  decoration.
- **Alignment beats centering**: set content on a consistent edge and a
  grid column (an 8px-based spacing scale or the project's tokens); and keep
  body text reading in blocks, not floating.
- **Spacing groups what belongs together**: related items sit closer than
  unrelated ones. The space between two elements is a claim about their
  relationship, so keep the same claim consistent across the page.

### Typography

One primary typeface family for the interface; weights and sizes below
already do hierarchy work. Bars to respect: body copy at 16px or more,
line-height between 1.4 and 1.6 for UI text, and a measure of roughly
45–75 characters per line. Don't use display sizes for body or squeeze a
calendar into a font that has no digits with stable tab alignment; choose
family by what the text is — UI, report, marketing — not by novelty.

### Color

Derive the palette from roles before swatches: background, surface, text,
primary, plus success/warning/danger states, then darken/lighten within
each role rather than inventing neighbors. Contrast is a hard bar, checked
on the actual surfaces used: body text ≥ 4.5:1, large text ≥ 3:1,
borders and glyph fills ≥ 3:1 against their behind. Confirm both themes
when the project supports light and dark.

### Spacing and layout

Use the spacing scale the project has, or a simple 4px-based one
(4/8/12/16/24…) as the only values. Responsive from constraints outward:
content boxes hold up on a 360px viewport because their minima, wraps,
and scroll rules were decided, then let them expand on wider viewports.
Never let an overflow rule be accidental: decide explicitly per element
whether it truncates (text with ellipsis + full value available
elsewhere), spreads (media and tables), or is fixed.

### Interactions and states

Every interactive element has hover, focus-visible, active, disabled, and
loading states — design them in the first pass, because a control without
a feedback story shifts the whole page's trust. Every block of content
also has empty, loading, and error variants; an empty state explains what
will appear here and one action toward it, an error says what happened
and the next step. Touch targets keep at least 24×24px with spacing, and
icon-only controls carry an accessible name.

### Accessibility

Accessibility bars are quality bars, not extras; this section is a gate,
not a suggestion:

- Semantic HTML: real headings in order, labels tied to inputs, buttons
  are buttons (a div with click handlers is not).
- The primary flow is operable with keyboard alone; focus is visible
  everywhere and moves in reading order.
- Information never rides on color alone (add label or icon), text sits on
  surfaces meeting the contrast bars above.
- Motion respects `prefers-reduced-motion`; media has alt or is
  programmatically hidden when decorative.

Completion: the ranking, system choice, and state inventory exist in
writing before the styling pass, and each changed screen has its primary
action and its states defined.

## Verify by rendering

Design claims are unverified until the page renders. Forward-loop with
bb (see the bb-cli skill for server commands and the browser-control
reference), and use screenshots at the widths and themes the project
ships: narrow (360px), mid, wide, and dark mode when present.

For a rendered walk, prefer the repo's own dev-server flow to a bespoke
setup. Then drive it hands-on: the flow a visitor actually performs —
load on mobile, scan the hierarchy, tap every primary action, keyboard
through the first transaction — and check the actual rather than the
intended result. If the task includes backend data, a clean render on
empty state does not prove the loaded state; render with real or seeded
fixture data.

Look in the order the user reads: hierarchy (primary action obvious at a
glance), rhythm (spacing and alignment lines hold), typography (sizes,
line lengths, truncations), color roles and contrast, then states —
hover, focus, empty, error. Fix, re-render, and re-screenshot; a change
that was not re-rendered is not verified. Diff a screenshot against the
previous pass or the committed baseline for regression comparison when
one exists.

If the environment cannot drive a browser, say so in the report rather
than claiming verification. A green `check` script does not tell you what
the layout does at 360px.

Completion: rendered evidence exists for each changed surface at the
widths it ships, every fix was re-rendered, and remaining gaps appear in
the report as unverified items rather than silent omissions.

## Report

End with a compact summary in this shape:

- **Changed** — the list of files and surfaces, one line each.
- **Decisions made without asking** — every aesthetic or ranking call the
  user should confirm (palette shifts, hierarchy calls, dropped content),
  so they can overturn any of them cheaply.
- **Verified** — what was rendered and exercised, at which widths and
  themes, and which checks ran or could not run at all (with why).
- **Open design questions** — questions a design decision would resolve,
  phrased concretely for the user; do not ship an unresolved one silently.

## Pivots

- Build a throwaway prototype instead when the design question is still
  "what should this look like": that is the `prototype` skill's job, and
  its answer feeds back into this one as the confirmed direction.
- Hand the rendered page to `code-review` or `diff-review` once the work
  is a code change with a base to compare against; design craft and code
  review are different passes.
- Run the project's defined lint/a11y/check cycle at the end of the
  styling pass as part of Verify, not as a substitute for rendering.
