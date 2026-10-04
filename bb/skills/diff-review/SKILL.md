---
name: diff-review
description: >-
  Single-ranked review of the diff between HEAD and a fixed point, run inline
  in this thread with no sub-agents. Findings land in one severity-ranked list
  (P1 must-fix before merge / P2 should-fix / P3 nice-to-have) with a concrete
  next action for each finding, and the review closes with the checks that were
  run plus what was not covered. Use when the user asks to review a branch, a
  diff, or work-in-progress changes as a ranked fix list rather than a
  standards/spec two-axis report.
---

Review the diff between `HEAD` and a fixed point the user names (a commit,
branch, tag, `HEAD~n` — ask only when they did not specify one). Record the
exact diff command the way the user stated it: for a branch it is usually
`git diff <fixed-point>...HEAD` (three dots, merge-base), for stacked lines
`git log --oneline <fixed-point>..HEAD` and `git diff HEAD~1` per commit.

Keep the review in this thread. Do not spawn sub-agents for the axes, and do
not re-refer the user to `code-review`; the two skills answer different
questions and a user asking for "a ranked list of what to fix" means this one.

## Steps

### 1. Pin the fixed point and the diff

Confirm the fixed point resolves before reading anything else:

```bash
git rev-parse --verify <fixed-point>^{commit}
```

Then take the diff once and reuse it for every step:

```bash
git diff <fixed-point>...HEAD
```

If the diff is empty, stop and say which files differ from the fixed point
(`git diff --stat <fixed-point>...HEAD`) rather than reviewing nothing.

### 2. Read for real problems, not style notes

Walk each hunk once and flag only things a reviewer would act on:

- **Correctness risks**: reads of mutable state across awaits, errors swallowed
  without a comment, arguments in a call-site order the signature cannot self-
  describe, reliance on external-call behaviour that the surrounding code does
  not establish.
- **Process facts the diff itself disconfirms**: e.g. the commit message says
  "tests only" but the diff changes product code, or a TODO in the diff claims
  a check that no code in the change performs.
- **Comments and commits that lie**: a claim in a code comment or commit body
  contradicted by what the code now does.

Do **not** comment on: style the repo already lints or formats, naming, or
"consider splitting this function". Those belong to a standards-oriented
review; this skill's findings are things that would be wrong or misspecified,
not opinions on structure.

Line items should read: file:line, what is wrong in one sentence, and what to
do about it in one sentence. No trailing "none found, LGTM" filler.

### 3. Rank into P1 / P2 / P3

When the review is complete, sort findings:

- **P1** — would break the feature, lose data, or fail a gate. Merge blocker.
- **P2** — would work today but is doing the wrong thing or will misbehave in a
  case the current tests do not cover.
- **P3** — improvement worth making now, not worth blocking on.

Every P1/P2 gets a concrete next action ("extract the parse into a helper so
both call sites share it"), not "consider refactoring".

### 4. Run the checks

Run `check` scripts and test suites the repo defines – e.g. `npm run check`,
`pytest`, `go test ./...` – according to what the repo actually has; do not
invent a runner. Do **not** treat a green suite as proof a live service is
correct; only as proof the checked code paths pass.

If a check cannot be run, record it in the report as "not run: <reason>".
Never report checks you did not run as passing.

### 5. Report

```
## diff-review: <fixed-point> → HEAD

### Findings
N. P2 — file:line — one-sentence problem. Next action: ...

### Checks run
- `<command>` — 47 passed, 0 failed
- not run: e2e suite — not locally executable in this environment

### Coverage
Reviewed hunks across N files. Not reviewed: <files skipped and why, e.g.
generated lockfile or vendored code>.
```

Findings are one ranked list, not sections per axis. Do not split findings
into "correctness" vs "process" buckets in the report — the P-suffix already
carries priority and the file/line already carries location.

## Related

- `code-review` covers the two-axis standards+spec framing with a smell
  baseline; use that instead when the user asks about standards or spec com-
  pliance rather than a ranked fix list.
- `tdd` for turning P1/P2 findings into failing tests instead of descriptions.

## Pivot rules

- If the user asks for a standards/spec two-axis review, defer to the
  `code-review` skill instead of forcing this structure.
- If the user supplies their own checklist, use it in place of step 2 and
  still rank and report through steps 3–5.
- If the repo has no runnable checks, say so under "Checks run" and skip to
  step 5 — do not invent commands.
