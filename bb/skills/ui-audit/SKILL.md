---
name: ui-audit
description: >-
  Audit existing web UI source or a diff against this skill's bundled interface
  rules — semantics, keyboard and focus, forms, typography, color, layout,
  states, media, motion — and report each violation as a terse file:line line
  naming the rule that failed. Use when the task is to review, audit, or check
  UI code for compliance ("audit these components", "check the new screen for
  a11y", "review this diff against the UI rules"); building or restyling UI
  belongs to web-design, and logic-level review to diff-review. Fully offline:
  every rule lives here, nothing is fetched at run time.
---

Audit UI source files against the rule catalog below. One pass, read-only, no
fixes, no builds: the deliverable is a findings report the user acts on — or
hands to another pass.

## Scope the surface

- Explicit paths or globs win; expand globs to concrete files before reading.
- No surface given: audit the working-tree diff (changed plus untracked files)
  when the workspace is a git repo with changes; otherwise ask which files or
  pattern to review — in BB, use `AskUserQuestion`.
- In a thread whose workspace lives on another host, read files with
  `bb files`; local shell tools would read the wrong disk.
- Skip non-UI files (config, API code, logic-only tests) with a one-line note
  in the report rather than silently.

Completion: the file list is concrete, and every file in it has been read in
full — excerpts and samples are not an audit.

## Apply the catalog

Check every file against every rule. A finding is a violated rule at a
location; apply the whole catalog even where the first sections look clean —
exhaustive by rule, not by attention.

### Markup and semantics

- Interactive elements are real controls: `<button>` for actions, `<a href>`
  for navigation. A clickable `div` or `span` is a finding.
- Heading levels descend without skips, one `<h1>` per view; headings carry
  structure, styling lives in CSS.
- Lists, data tables, and definitions use their elements: `<ul>/<ol>/<dl>`,
  `<th scope>` on data tables; `<table>` is reserved for data.
- Landmarks (`<main>`, `<nav>`, `<header>`, `<footer>`) appear where content
  warrants; repeated landmarks carry an accessible name.
- `<html lang>` matches the copy language; the document has a `<title>`.

### Keyboard and focus

- Everything operable by pointer is operable by keyboard; custom menus, tabs,
  and dialogs manage focus, close on Escape, and — for dialogs — trap focus
  and return it on close.
- Focus stays visible: where a default outline was removed, a replacement
  exists that a keyboard user can see on every theme the project ships.
- Tab and arrow traversal moves through widgets in reading order and exits
  every widget; no keyboard traps.

### Forms

- Every control has an associated visible label or programmatic name;
  placeholder text alone is not a label.
- Input `type` and `inputmode` match the data; autocomplete attributes are set
  on identity and payment fields.
- Validation errors are announced (`aria-invalid`, `aria-describedby` pointing
  at error text) and the message says what to fix, not only that it failed.
- The submit path guards double submits: pending state on the button, using
  the disabled/loading treatment the rest of the surface uses.

### Typography and text

- Body copy runs ≥16px with line-height 1.4–1.6 and a paragraph measure near
  45–75 characters.
- Truncated text keeps its full value reachable (title, tooltip, or
  expansion).
- Paragraph-length uppercase or justified text is a finding; short labels may
  use either deliberately.

### Color and contrast

- Text sits at ≥4.5:1 against its background (≥3:1 for large text); borders
  and icon fills that carry meaning sit at ≥3:1. When a ratio cannot be
  settled from source alone, list it under unverified instead of guessing.
- State — error, success, warning — carries a second signal (text or icon)
  wherever color alone would carry it.
- Both themes checked when the project ships light and dark; focus and
  disabled styles survive both.

### Layout and responsive

- Content holds at a 360px viewport: text-holding flex/grid children carry
  min-width semantics (`min-w-0`), and the page forces no horizontal scroll.
- Every overflow is decided — truncate with the full value available, wrap,
  or scroll — and the same element type decides the same way across the
  surface.
- Media scales inside its container; spacing comes from the project's scale
  or a 4px-based one; touch targets are ≥24×24px with spacing between (≥44px
  on touch-first surfaces).

### Media and motion

- Meaningful images have alt text; decorative ones have empty alt and are
  hidden from the tree; icon-only controls carry an accessible name.
- Animation honors `prefers-reduced-motion`; essential information survives
  with motion off.
- Media does not autoplay with sound; loading reserves space (skeleton or
  sized box) so content does not shift on arrival.

### States and interaction

- Every interactive element defines hover, focus-visible, active, disabled,
  and where relevant loading; every content block defines empty, loading, and
  error variants.
- Cursor matches affordance: pointer on controls, text cursor in inputs.
- Empty states say what appears here and offer one action toward it; error
  states say what happened and the next step.

### Content

- Controls are named by outcome ("Save draft"); links carry context — a bare
  "click here" is a finding.
- Dates, numbers, and counts follow one format across the surface.

## Report

One line per finding, grouped by file, with the path rendered as a Markdown
link in BB chat so it opens on click:

    path/to/file.tsx:42 — Rule name — what fails

- **Findings** — every violated rule with its location; a file's findings
  stay together.
- **Coverage** — files read × rules applied; rules marked not applicable and
  why; and what a static pass cannot settle (computed contrast values,
  rendered behavior) listed as unverified rather than assumed clean.

Zero findings still gets a report: file and rule counts, plus the unverified
list.

Completion: every file read fully, every rule applied or marked not
applicable, and the findings/coverage report emitted.

## Pivots

- Building or restyling the UI rather than auditing it: `web-design`. Audit
  after the change, not instead of it.
- Logic, architecture, or security in the same diff: `diff-review` or
  `code-review`; this skill judges the interface layer only.
- A finding that needs visual confirmation: rendered browser verification is
  the follow-up — name it in the report as unverified rather than claiming it.
