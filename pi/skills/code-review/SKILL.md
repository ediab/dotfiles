---
name: code-review
description: "Review the changes since a fixed point (commit, branch, tag, or merge-base) along two axes: Standards (does the code follow this repo's documented coding standards?) and Spec (does the code match what the originating issue/spec asked for?). Runs independent reviewers in parallel (BB child threads inside BB; Pi subagents in standalone Pi) and reports them side by side. Use when the user wants to review a branch, a PR, work-in-progress changes, or asks to \"review since X\"."
---

Two-axis review of the diff between `HEAD` and a fixed point the user supplies:

- **Standards**: does the code conform to this repo's documented coding standards?
- **Spec**: does the code faithfully implement the originating issue / spec?

Both axes run as **independent parallel reviewers** so they don't pollute each other's context, then this skill aggregates their findings. Read `personal-workflow` before dispatch: inside BB (`BB_THREAD_ID` is set), use BB child threads; in standalone Pi, use one asynchronous `pi-subagents` workflow. Both reviewers count toward the owner's delegation cap.

An explicit user invocation of this dedicated two-axis review authorizes only the report-only reviewers described here, subject to applicable user/project rules. Automatic skill loading for an ordinary review request is not independent permission to delegate. When delegation is not authorized, review inline and retain the two report headings.

The issue tracker should have been provided to you (e.g. `docs/agents/issue-tracker.md`). If it's missing and no spec path or tracker doc exists, ask the user where the spec lives; if there is none, the **Spec** axis will skip and report "no spec available".

## Process

### 1. Pin the fixed point

Whatever the user said is the fixed point (a commit SHA, branch name, tag, `main`, `HEAD~5`, etc.). If they didn't specify one, ask for it.

Capture the diff command once: `git diff <fixed-point>...HEAD` (three-dot, so the comparison is against the merge-base). Also note the list of commits via `git log <fixed-point>..HEAD --oneline`.

Before going further, confirm the fixed point resolves (`git rev-parse <fixed-point>`) and the diff is non-empty. A bad ref or empty diff should fail here, not inside two parallel sub-agents.

### 2. Identify the spec source

Look for the originating spec, in this order:

1. Issue references in the commit messages (`#123`, `Closes #45`, GitLab `!67`, etc.), fetched via the workflow in `docs/agents/issue-tracker.md`.
2. A path the user passed as an argument.
3. A spec file under `docs/`, `specs/`, or `.scratch/` matching the branch name or feature.
4. If nothing is found, ask the user where the spec is. If they say there isn't one, the **Spec** sub-agent will skip and report "no spec available".

### 3. Identify the standards sources

Anything in the repo that documents how code should be written, such as `CODING_STANDARDS.md` or `CONTRIBUTING.md`.

On top of whatever the repo documents, the Standards axis always carries the **smell baseline** below: a fixed set of Fowler code smells (_Refactoring_, ch.3) that applies even when a repo documents nothing. Two rules bind it:

- **The repo overrides.** A documented repo standard always wins; where it endorses something the baseline would flag, suppress the smell.
- **Always a judgement call.** Each smell is a labelled heuristic ("possible Feature Envy"), never a hard violation. Like any standard here, skip anything tooling already enforces.

Each smell reads *what it is* → *how to fix*; match it against the diff:

- **Mysterious Name**: a function, variable, or type whose name doesn't reveal what it does or holds. → rename it; if no honest name comes, the design's murky.
- **Duplicated Code**: the same logic shape appears in more than one hunk or file in the change. → extract the shared shape, call it from both.
- **Feature Envy**: a method that reaches into another object's data more than its own. → move the method onto the data it envies.
- **Data Clumps**: the same few fields or params keep travelling together (a type wanting to be born). → bundle them into one type, pass that.
- **Primitive Obsession**: a primitive or string standing in for a domain concept that deserves its own type. → give the concept its own small type.
- **Repeated Switches**: the same `switch`/`if`-cascade on the same type recurs across the change. → replace with polymorphism, or one map both sites share.
- **Shotgun Surgery**: one logical change forces scattered edits across many files in the diff. → gather what changes together into one module.
- **Divergent Change**: one file or module is edited for several unrelated reasons. → split so each module changes for one reason.
- **Speculative Generality**: abstraction, parameters, or hooks added for needs the spec doesn't have. → delete it; inline back until a real need shows.
- **Message Chains**: long `a.b().c().d()` navigation the caller shouldn't depend on. → hide the walk behind one method on the first object.
- **Middle Man**: a class or function that mostly just delegates onward. → cut it, call the real target direct.
- **Refused Bequest**: a subclass or implementer that ignores or overrides most of what it inherits. → drop the inheritance, use composition.

### 4. Run authorized reviewers in parallel

Choose the host-specific branch before launching; do not mix runners or switch to another runner after a failed launch without the user's approval.

**Inside BB (`BB_THREAD_ID` is set):** read `bb-cli` and its thread-creation/operation references. Resolve the current project, environment, machine, and Pi model. Create one BB child thread per available axis with the current thread as parent (`--parent-self`), an explicit project and `--provider pi`, and the verified model. Attach to the current environment for these report-only readers; never let them edit shared files. Pass each self-contained brief through `--prompt-file` or stdin. Each brief must identify the repo/base/ref, relevant files, standards/spec, expected output, and the boundary: report only, no edits, no further delegation. The children do not inherit this conversation or the native `reviewer` profile. Yield to BB completion notifications, then collect both final outputs and verify material findings against the source before aggregation.

**Standalone Pi:** read `pi-subagents`, check `subagent({ action: "list", capabilities: true })` for an executable `reviewer`, and load its workflow guidance. Launch both reviewers inside one asynchronous workflow. Write the script in one fenced code block tagged `js workflow`, then call `subagent({ workflow: true, async: true })` in the same reply:

```js workflow
const [standards, spec] = await runs.all([
  { key: "standards", label: "Review standards compliance", agent: "reviewer", context: "fresh", task: "<standards brief>" },
  { key: "spec", label: "Review spec conformance", agent: "reviewer", context: "fresh", task: "<spec brief>" }
]);
return "## Standards\n\n" + standards.output + "\n\n## Spec\n\n" + spec.output;
```

Yield to native completion notifications rather than polling or blocking on `bg_wait`. The main agent collects the completed result and verifies material findings before presenting the report.

**Standards child brief** — its `task` should include:

- The full diff command and commit list.
- The list of standards-source files you found in step 3, **plus the smell baseline from step 3** pasted in full (the child has no other access to it).
- The brief: "Report, per file/hunk where relevant, (a) every place the diff violates a documented standard: cite the standard (file + the rule); and (b) any baseline smell you spot: name it and quote the hunk. Distinguish hard violations from judgement calls: documented-standard breaches can be hard, but baseline smells are always judgement calls, and a documented repo standard overrides the baseline. Skip anything tooling enforces. Under 400 words."

**Spec child brief** — its `task` should include:

- The diff command and commit list.
- The path or fetched contents of the spec.
- The brief: "Report: (a) requirements the spec asked for that are missing or partial; (b) behaviour in the diff that wasn't asked for (scope creep); (c) requirements that look implemented but where the implementation looks wrong. Quote the spec line for each finding. Under 400 words."

If the spec is missing, omit the Spec reviewer and note this in the final report. In standalone Pi, also adjust `runs.all`, its destructuring, and the returned text so they refer only to the Standards result.

### 5. Aggregate

Present the two reports under `## Standards` and `## Spec` headings, verbatim or lightly cleaned. Do **not** merge or rerank findings, because the two axes are deliberately separate (see _Why two axes_).

End with a one-line summary: total findings per axis, and the worst issue _within each axis_ (if any). Don't pick a single winner across axes: that's the reranking the separation exists to prevent.

## Why two axes

A change can pass one axis and fail the other:

- Code that follows every standard but implements the wrong thing → **Standards pass, Spec fail.**
- Code that does exactly what the issue asked but breaks the project's conventions → **Spec pass, Standards fail.**

Reporting them separately stops one axis from masking the other.
