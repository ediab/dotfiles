---
name: unslop
description: Edit supplied writing for clarity, specificity, and a natural voice while preserving meaning.
disable-model-invocation: true
license: MIT
---

# Unslop

Edit the requested text, not the whole repository. Unlike a restatement of the previous reply, this can work on a supplied draft, document, or passage.

## Procedure

1. Identify the text, audience, intended tone, and requested editing scope. Ask only when ambiguity materially changes the edit.
2. Scan for the patterns below and rewrite the passages where a change improves understanding.
3. Compare the result with the original. Preserve factual meaning, decisions, technical identifiers, paths, commands, numbers, names, citations, and quoted evidence. Keep uncertainty that reflects the evidence.
4. Return the edited text, or a concise summary of the requested file edits. Flag factual gaps rather than silently resolving them. Do not fetch new evidence or introduce new claims unless asked.

## Patterns to fix

- **Empty framing and filler.** Cut “It is important to note that,” generic conclusions, chatbot preambles, and praise that adds nothing. “In order to” usually becomes “To.”
- **Vague attribution.** “Experts believe” needs a supplied source or an explicit gap. Do not invent an authority. Deleting unsupported material must not hide an important uncertainty; flag substantive unsupported claims.
- **Inflated wording.** Prefer “use” over “utilize” and “help” over “facilitate.” Keep a precise technical term when it helps this audience.
- **Synonym cycling.** Give each concept one consistent name. Avoid ornamental substitutes that make one thing look like several.
- **Forced contrasts and groupings.** Replace “not just X, but Y” with the actual point when the framing adds nothing. Use the natural number of items, not a forced triad or meaningless “from X to Y” range.
- **Feeling instead of mechanism.** “The database stays close at hand” says little. State the actual mechanism already supported by the draft, such as “`.toSQL()` returns the string sent to the database.” If the mechanism is missing, flag the gap rather than manufacture it.
- **Unmeasured improvement.** “Significantly faster” needs evidence. Retain supplied measurements; do not invent a delta or turn a possibility into a result.
- **Dense or over-compressed sentences.** Split clauses that require backtracking. Keep articles and verbs rather than making the reader decode fragments, arrows, or abbreviations.
- **Needless abstraction and flourish.** Replace metaphor with concrete actions when it obscures the meaning. A term such as “API surface” is not automatically wrong; its usefulness depends on the audience.
- **Excessive hedging.** “Could potentially possibly” can become “may.” Keep the “may” when the evidence is uncertain.
- **Hidden actors.** Prefer an active sentence when the responsible actor is known. Passive voice is appropriate when the actor is unknown or beside the point.
- **Distracting presentation.** Simplify repetitive labels, excessive emphasis, or decoration when they impede reading. Follow the document's useful conventions; punctuation, headings, lists, and emphasis are tools, not banned forms.

Natural prose is the goal, not mechanical compliance with a word blacklist. Preserve the author's intended voice and leave a good sentence alone. This skill is explicitly invoked; it does not mandate rewriting every future response or unrelated file.
