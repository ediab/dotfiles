---
name: tdd
description: Test-driven development. Use when the user wants to build features or fix bugs test-first, mentions "red-green-refactor", or wants integration tests.
---

# Test-Driven Development

TDD is the red → green loop. This skill is the reference that makes that loop produce tests worth keeping: what a good test is, where tests go, the anti-patterns, and the rules of the loop. Every section applies on every cycle: consult them before and during the loop, not after.

When exploring the codebase, read `CONTEXT.md` (if it exists) so test names and interface vocabulary match the project's domain language, and respect ADRs in the area you're touching.

## What a good test is

Tests verify behavior through public interfaces, not implementation details. Code can change entirely; tests shouldn't. A good test reads like a specification: "user can checkout with valid cart" tells you exactly what capability exists, and it survives refactors because it doesn't care about internal structure.

See [tests.md](tests.md) for examples and [mocking.md](mocking.md) for mocking guidelines.

## Seams: where tests go

A **seam** is the public boundary you test at: the interface where you observe behavior without reaching inside. Tests live at seams, never against internals.

**Test only at pre-agreed seams.** Before writing any test, write down the seams under test and confirm them with the user. No test is written at an unconfirmed seam. You can't test everything, so agreeing the seams up front is how testing effort lands on the critical paths and complex logic instead of every edge case.

Ask: "What's the public interface, and which seams should we test?"

When the shape of that interface is itself in question (how deep the module is, where the seam belongs, what the interface should expose), consult the project's architecture documentation and decision records for the vocabulary and constraints.

## Anti-patterns

- **Implementation-coupled**: mocks internal collaborators, tests private methods, or verifies through a side channel (querying the database instead of using the interface). The tell: the test breaks when you refactor but behavior hasn't changed.
- **Tautological**: the assertion recomputes the expected value the way the code does (`expect(add(a, b)).toBe(a + b)`, a snapshot derived by hand the same way, a constant asserted equal to itself), so it passes by construction and can never disagree with the code. Expected values must come from an independent source of truth: a known-good literal, a worked example, the spec.
- **Horizontal slicing**: writing all tests first, then all implementation. Bulk tests verify _imagined_ behavior: you test the _shape_ of things rather than user-facing behavior, the tests go insensitive to real changes, and you commit to test structure before understanding the implementation. Work in **vertical slices** instead: one test → one implementation → repeat, each test a **tracer bullet** that responds to what the last cycle taught you.

## Rules of the loop

- **Red before green.** Write and run the failing test first. Confirm it fails for the intended behavioral reason, not a syntax error, missing dependency, or unrelated setup failure. Then write only enough code to pass it. Don't anticipate future tests or add speculative features.
- **One slice at a time.** One seam, one test, one minimal implementation per cycle.
- **Refactoring is not part of the loop.** It belongs in the review stage, following the project's and host client's review rules, not the red → green implementation cycle.

## When a permanent regression test is impractical

For a bug fix, prefer a focused regression test at an agreed seam. If no honest, practical permanent test reaches the real bug, document the missing seam or prohibitive setup instead of adding a brittle test that mostly checks mocks, timing, or unrelated fixtures.

Use the closest useful executable check: a targeted script, CLI command, browser drive, replay, or focused integration check. Assert the reported symptom, run it before changing production code when possible, then rerun after the fix. Record why a permanent test could not be added and what the substitute leaves unverified. If no meaningful check can run, report the blocker rather than claim the bug is fixed.

This fallback is for impractical bug/regression tests. It does not turn explicitly requested feature TDD into post-hoc verification, change the agreed-seam policy, or permit changing assertions to fit a wrong implementation.

## Evidence at completion

Name the failing-before test or executable check and the behavioral failure it produced, then the passing-after invocation and result. Include relevant nearby checks and limitations. If failing-before evidence could not be demonstrated, say why and identify the substitute evidence; do not describe an unobserved red as if it happened.
